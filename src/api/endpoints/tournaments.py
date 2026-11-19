from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from src.api.api_blueprint import api
from src.api.coach_access import (
    can_manage_club_sports_entity,
    get_club_sports_entity_error,
    get_player_serializer,
    get_team_access_resolver,
    get_team_assignment_error,
    redact_sports_money_for_user,
    serialize_with_player_for_user,
)
from src.api.finance_access import (
    FINANCE_DEPENDENCY_ERROR,
    can_access_finance,
    can_configure_sports_finance,
    charge_blocks_roster_change,
    get_finance_access_error,
    get_finance_payload_error,
    get_sports_finance_error,
)
from src.api.integrity_errors import violates_named_constraint
from src.api.models import (
    db,
    MatchSession,
    Player,
    PlayerPayment,
    Team,
    TeamPlayer,
    Tournament,
    TournamentPlayer,
    TournamentTeam,
)
from src.api.payment_charge_helpers import (
    add_charge_if_absent,
    parse_money,
    split_money_exactly,
)
from src.api.season_service import (
    get_season_operation_error,
    get_team_operation_error,
    lock_team_lifecycle,
    lock_active_season_for_operation,
    resolve_season_for_read,
)
from src.api.team_player_status import TEAM_PLAYER_STATUS_ACTIVE
from src.api.utils import error_response, get_current_user


VALID_TOURNAMENT_STATUSES = [
    "active",
    "completed",
    "cancelled"
]
TOURNAMENT_TEAM_UNIQUE_CONSTRAINTS = {
    "unique_team_per_tournament",
    "tournament_teams.tournament_id, tournament_teams.team_id",
}
TOURNAMENT_PLAYER_UNIQUE_CONSTRAINTS = {
    "unique_player_per_tournament_team",
    "tournament_players.tournament_team_id, tournament_players.player_id",
}
# Cancelar no toca cargos: los pagados y sus recibos se conservan. Mientras no
# exista una regla para los pendientes, deben resolverse antes de cancelar.
TOURNAMENT_PENDING_CHARGES_ERROR = (
    (
        "El torneo tiene cargos de inscripción pendientes. Cóbralos o "
        "cancélalos antes de cancelar el torneo."
    ),
    "TOURNAMENT_HAS_PENDING_CHARGES",
    409
)

def _tournament_payload(tournament, user):
    return {
        **redact_sports_money_for_user(user, tournament.serialize()),
        "season_name": tournament.season.name if tournament.season else None,
        "season_status": tournament.season.status if tournament.season else None,
        "can_manage": can_manage_club_sports_entity(user),
    }


def _tournament_entry_payload(entry, user, team_access=None):
    resolve_access = team_access or get_team_access_resolver(user)
    serialized = redact_sports_money_for_user(user, entry.serialize())
    tournament_payload = serialized.get("tournament")

    if tournament_payload and entry.tournament:
        tournament_payload = {
            **tournament_payload,
            "season_id": entry.tournament.season_id,
            "season_name": (
                entry.tournament.season.name
                if entry.tournament.season
                else None
            ),
            "season_status": (
                entry.tournament.season.status
                if entry.tournament.season
                else None
            ),
        }

    return {
        **serialized,
        "tournament": tournament_payload,
        **resolve_access(entry.team),
    }


def _match_summary_payload(match, user, team_access=None):
    resolve_access = team_access or get_team_access_resolver(user)
    team = match.team

    return {
        **redact_sports_money_for_user(user, match.serialize()),
        **resolve_access(team),
        "team_name": team.name if team else None,
        "category_name": (
            team.category.name if team and team.category else None
        ),
    }


def _get_tournament_read_model(tournament_ids, user, include_matches=False):
    """Build list/detail metrics with a bounded number of queries."""
    result = {
        tournament_id: {
            "entries": [],
            "matches": [],
            "total_teams": 0,
            "active_roster_count": 0,
            "total_roster_count": 0,
            "open_matches_count": 0,
            "completed_matches_count": 0,
            "total_matches": 0,
        }
        for tournament_id in tournament_ids
    }

    if not tournament_ids:
        return result

    entries = (
        TournamentTeam.query
        .options(
            joinedload(TournamentTeam.team).joinedload(Team.category),
            joinedload(TournamentTeam.tournament),
        )
        .filter(TournamentTeam.tournament_id.in_(tournament_ids))
        .order_by(TournamentTeam.created_at.asc())
        .all()
    )
    entries_by_id = {entry.id: entry for entry in entries}
    team_access = get_team_access_resolver(user)

    roster_counts = defaultdict(lambda: {"active": 0, "total": 0})
    for entry_id, status, count in (
        db.session.query(
            TournamentPlayer.tournament_team_id,
            TournamentPlayer.status,
            func.count(TournamentPlayer.id),
        )
        .filter(TournamentPlayer.tournament_team_id.in_(entries_by_id))
        .group_by(TournamentPlayer.tournament_team_id, TournamentPlayer.status)
        .all()
        if entries_by_id
        else []
    ):
        roster_counts[entry_id]["total"] += count
        if status == "active":
            roster_counts[entry_id]["active"] = count

    eligible_counts = dict(
        db.session.query(
            TournamentPlayer.tournament_team_id,
            func.count(TournamentPlayer.id),
        )
        .join(
            TournamentTeam,
            TournamentTeam.id == TournamentPlayer.tournament_team_id,
        )
        .join(Player, Player.id == TournamentPlayer.player_id)
        .join(
            TeamPlayer,
            (TeamPlayer.team_id == TournamentTeam.team_id)
            & (TeamPlayer.player_id == TournamentPlayer.player_id)
            & TeamPlayer.left_at.is_(None),
        )
        .filter(
            TournamentPlayer.tournament_team_id.in_(entries_by_id),
            TournamentPlayer.status == "active",
            Player.is_active.is_(True),
            TeamPlayer.status == TEAM_PLAYER_STATUS_ACTIVE,
        )
        .group_by(TournamentPlayer.tournament_team_id)
        .all()
        if entries_by_id
        else []
    )

    match_counts = defaultdict(lambda: {"open": 0, "completed": 0, "total": 0})
    for entry_id, is_completed, count in (
        db.session.query(
            MatchSession.tournament_team_id,
            MatchSession.is_completed,
            func.count(MatchSession.id),
        )
        .filter(MatchSession.tournament_team_id.in_(entries_by_id))
        .group_by(MatchSession.tournament_team_id, MatchSession.is_completed)
        .all()
        if entries_by_id
        else []
    ):
        match_counts[entry_id]["total"] += count
        key = "completed" if is_completed else "open"
        match_counts[entry_id][key] += count

    for entry in entries:
        roster = roster_counts[entry.id]
        matches = match_counts[entry.id]
        payload = {
            **_tournament_entry_payload(entry, user, team_access),
            "active_roster_count": roster["active"],
            "total_roster_count": roster["total"],
            "currently_eligible_players_count": eligible_counts.get(entry.id, 0),
            "open_matches_count": matches["open"],
            "completed_matches_count": matches["completed"],
            "total_matches": matches["total"],
            # Backwards-compatible alias used by existing clients.
            "total_players": roster["active"],
        }
        tournament_metrics = result[entry.tournament_id]
        tournament_metrics["entries"].append(payload)
        tournament_metrics["total_teams"] += 1
        tournament_metrics["active_roster_count"] += roster["active"]
        tournament_metrics["total_roster_count"] += roster["total"]
        tournament_metrics["open_matches_count"] += matches["open"]
        tournament_metrics["completed_matches_count"] += matches["completed"]
        tournament_metrics["total_matches"] += matches["total"]

    if include_matches and entries_by_id:
        matches = (
            MatchSession.query
            .options(
                joinedload(MatchSession.team).joinedload(Team.category),
                joinedload(MatchSession.tournament_team),
            )
            .filter(MatchSession.tournament_team_id.in_(entries_by_id))
            .order_by(MatchSession.date.desc(), MatchSession.id.asc())
            .all()
        )
        for match in matches:
            entry = entries_by_id[match.tournament_team_id]
            result[entry.tournament_id]["matches"].append(
                _match_summary_payload(match, user, team_access)
            )

    return result


def _get_club_tournament_team(tournament_team_id, user):
    return TournamentTeam.query.join(Tournament).filter(
        TournamentTeam.id == tournament_team_id,
        Tournament.club_id == user.club_id
    ).first()


def _get_tournament_team_for_update(tournament_team_id):
    # Mismo orden en todos los flujos: Tournament, TournamentTeam y cargos. Bloquear
    # el torneo serializa estas escrituras con completarlo o cancelarlo; el estado
    # del torneo debe comprobarse después de esta llamada.
    tournament_id = db.session.query(
        TournamentTeam.tournament_id
    ).filter_by(id=tournament_team_id).scalar()

    Tournament.query.filter_by(
        id=tournament_id
    ).populate_existing().with_for_update(key_share=True).first()

    return TournamentTeam.query.filter_by(
        id=tournament_team_id
    ).populate_existing().with_for_update().first()


def _lock_tournament(tournament_id):
    # Primer lock de todo flujo que cambie el torneo o sus filas hijas (mismo
    # orden que _get_tournament_team_for_update). FOR NO KEY UPDATE no frena las
    # FK que lo referencian, pero sí a quien lo complete, cancele o inscriba.
    return Tournament.query.filter_by(
        id=tournament_id
    ).populate_existing().with_for_update(key_share=True).first()


def _lock_tournament_entries(tournament_id):
    return (
        TournamentTeam.query
        .filter_by(tournament_id=tournament_id)
        .order_by(TournamentTeam.id.asc())
        .populate_existing()
        .with_for_update()
        .all()
    )


def _cancel_tournament_charges_error(tournament, user):
    """Revalidate cancellation Finance blockers under deterministic locks."""
    entries = _lock_tournament_entries(tournament.id)
    entry_ids = [entry.id for entry in entries]

    charges = (
        PlayerPayment.query
        .filter(
            PlayerPayment.club_id == tournament.club_id,
            PlayerPayment.tournament_team_id.in_(entry_ids),
            PlayerPayment.payment_type == "tournament",
            PlayerPayment.match_id.is_(None),
        )
        .order_by(PlayerPayment.id.asc())
        .populate_existing()
        .with_for_update()
        .all()
        if entry_ids
        else []
    )
    blocking_count = sum(
        charge.status in ["pending", "overdue"] for charge in charges
    )

    if not blocking_count:
        return None

    # Un coach no ve finanzas: recibe el aviso genérico de dependencias.
    if not can_access_finance(user):
        return (*FINANCE_DEPENDENCY_ERROR, None)

    return (*TOURNAMENT_PENDING_CHARGES_ERROR, blocking_count)


def _get_registration_charges_for_update(club_id, tournament_team_id):
    # El estado se lee ya bloqueado: un pago simultáneo no puede perderse.
    return PlayerPayment.query.filter_by(
        club_id=club_id,
        tournament_team_id=tournament_team_id,
        match_id=None,
        payment_type="tournament"
    ).populate_existing().with_for_update().all()


@api.route("/tournaments", methods=["POST"])
@jwt_required()
def create_tournament():
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para registrar torneos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    entity_error = get_club_sports_entity_error(user)

    if entity_error:
        return error_response(*entity_error)

    body = request.get_json() or {}

    finance_error = get_finance_payload_error(
        user,
        body,
        ("default_referee_fee",)
    )

    if finance_error:
        return error_response(*finance_error)

    name = body.get("name")
    organizer_name = body.get("organizer_name")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    default_referee_fee = body.get("default_referee_fee", 0)

    if name:
        name = " ".join(str(name).strip().split())

    if organizer_name:
        organizer_name = " ".join(
            str(organizer_name).strip().split()
        )

    if not name:
        return error_response(
            "El nombre del torneo es obligatorio",
            "TOURNAMENT_NAME_REQUIRED",
            400
        )

    if not start_date:
        return error_response(
            "La fecha de inicio es obligatoria",
            "TOURNAMENT_START_DATE_REQUIRED",
            400
        )

    try:
        parsed_start_date = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()
    except (TypeError, ValueError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )

    parsed_end_date = None

    if end_date:
        try:
            parsed_end_date = datetime.strptime(
                end_date,
                "%Y-%m-%d"
            ).date()
        except (TypeError, ValueError):
            return error_response(
                "Formato de fecha inválido. Usa YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400
            )

        if parsed_end_date < parsed_start_date:
            return error_response(
                "La fecha de finalización no puede ser anterior al inicio",
                "INVALID_TOURNAMENT_DATE_RANGE",
                400
            )

    parsed_referee_fee, amount_error = parse_money(
        default_referee_fee,
        "El costo de arbitraje"
    )

    if amount_error:
        return amount_error

    existing_tournament = Tournament.query.filter(
        Tournament.club_id == user.club_id,
        func.lower(Tournament.name) == name.lower(),
        Tournament.start_date == parsed_start_date
    ).first()

    if existing_tournament:
        return error_response(
            "Ya existe un torneo con ese nombre y fecha",
            "TOURNAMENT_ALREADY_EXISTS",
            409
        )

    # transition_season bloquea las Season con FOR UPDATE: no se usa un id de
    # temporada leído antes de esperar ese lock.
    season = lock_active_season_for_operation(user.club_id)

    if not season:
        return error_response(
            "El club no tiene una temporada activa configurada",
            "ACTIVE_SEASON_REQUIRED",
            409
        )

    tournament = Tournament(
        club_id=user.club_id,
        season_id=season.id,
        name=name,
        organizer_name=organizer_name or None,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        default_referee_fee=parsed_referee_fee,
        status="active",
        created_by=user.id
    )

    db.session.add(tournament)
    db.session.commit()

    return jsonify({
        "message": "Torneo registrado correctamente",
        "tournament": _tournament_payload(tournament, user)
    }), 201

@api.route("/tournaments", methods=["GET"])
@jwt_required()
def get_tournaments():
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar torneos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    status = request.args.get("status")

    season, season_error, _ = resolve_season_for_read(
        user.club_id,
        request.args.get("season_id"),
    )

    if season_error:
        return error_response(*season_error)

    query = Tournament.query.filter_by(
        club_id=user.club_id,
        season_id=season.id
    )

    if status:
        if status not in VALID_TOURNAMENT_STATUSES:
            return error_response(
                "Estado de torneo inválido",
                "INVALID_TOURNAMENT_STATUS",
                400
            )

        query = query.filter(
            Tournament.status == status
        )

    tournaments = query.order_by(
        Tournament.start_date.desc()
    ).all()

    metrics_by_tournament = _get_tournament_read_model(
        [tournament.id for tournament in tournaments],
        user,
    )
    result = []

    for tournament in tournaments:
        metrics = metrics_by_tournament[tournament.id]
        result.append({
            **_tournament_payload(tournament, user),
            **{
                key: value
                for key, value in metrics.items()
                if key not in ["entries", "matches"]
            },
            "teams": metrics["entries"],
        })

    return jsonify({
        "season": season.serialize(),
        "total_tournaments": len(result),
        "tournaments": result
    }), 200

@api.route("/tournaments/<string:tournament_id>", methods=["GET"])
@jwt_required()
def get_tournament_detail(tournament_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar torneos",
            "FORBIDDEN",
            403
        )

    tournament = Tournament.query.get(tournament_id)

    if not tournament:
        return error_response(
            "Torneo no encontrado",
            "TOURNAMENT_NOT_FOUND",
            404
        )

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403
        )

    metrics = _get_tournament_read_model(
        [tournament.id],
        user,
        include_matches=True,
    )[tournament.id]
    pending_admin_count = (
        PlayerPayment.query
        .join(
            TournamentTeam,
            TournamentTeam.id == PlayerPayment.tournament_team_id,
        )
        .filter(
            TournamentTeam.tournament_id == tournament.id,
            PlayerPayment.club_id == tournament.club_id,
            PlayerPayment.payment_type == "tournament",
            PlayerPayment.match_id.is_(None),
            PlayerPayment.status.in_(["pending", "overdue"]),
        )
        .count()
    )

    return jsonify({
        "tournament": {
            **_tournament_payload(tournament, user),
            **{
                key: value
                for key, value in metrics.items()
                if key not in ["entries", "matches"]
            },
            "teams": metrics["entries"],
            "matches": metrics["matches"],
            "has_pending_admin_dependencies": pending_admin_count > 0,
            **(
                {"pending_admin_dependencies_count": pending_admin_count}
                if can_access_finance(user)
                else {}
            ),
        }
    }), 200

@api.route("/tournaments/<string:tournament_id>", methods=["PUT"])
@jwt_required()
def update_tournament(tournament_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para editar torneos",
            "FORBIDDEN",
            403
        )

    tournament = Tournament.query.get(tournament_id)

    if not tournament:
        return error_response(
            "Torneo no encontrado",
            "TOURNAMENT_NOT_FOUND",
            404
        )

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403
        )

    entity_error = get_club_sports_entity_error(user)

    if entity_error:
        return error_response(*entity_error)

    body = request.get_json() or {}

    finance_error = get_finance_payload_error(
        user,
        body,
        ("default_referee_fee",)
    )

    if finance_error:
        return error_response(*finance_error)

    if "status" in body:
        return error_response(
            (
                "El estado del torneo debe cambiarse mediante "
                "la acción correspondiente"
            ),
            "INVALID_TOURNAMENT_STATUS",
            400
        )

    # Metadata and terminal transitions share the first lock. Authorization,
    # Season and status are revalidated only after waiting for it.
    tournament = _lock_tournament(tournament.id)

    if not tournament or tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403,
        )

    entity_error = get_club_sports_entity_error(user)

    if entity_error:
        return error_response(*entity_error)

    season_error = get_season_operation_error(tournament.season)

    if season_error:
        return error_response(*season_error)

    if tournament.status != "active":
        return error_response(
            "El torneo ya no está activo. Actualiza la vista para continuar.",
            "TOURNAMENT_NOT_ACTIVE",
            409,
        )

    name = body.get("name")
    organizer_name = body.get("organizer_name")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    default_referee_fee = body.get("default_referee_fee")

    if name is not None:
        name = " ".join(str(name).strip().split())

        if not name:
            return error_response(
                "El nombre del torneo es obligatorio",
                "TOURNAMENT_NAME_REQUIRED",
                400
            )

    if organizer_name is not None:
        organizer_name = " ".join(
            str(organizer_name).strip().split()
        )

    parsed_start_date = tournament.start_date

    if start_date is not None:
        if not start_date:
            return error_response(
                "La fecha de inicio es obligatoria",
                "TOURNAMENT_START_DATE_REQUIRED",
                400
            )

        try:
            parsed_start_date = datetime.strptime(
                start_date,
                "%Y-%m-%d"
            ).date()
        except (TypeError, ValueError):
            return error_response(
                "Formato de fecha inválido. Usa YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400
            )

    parsed_end_date = tournament.end_date

    if end_date is not None:
        if end_date == "":
            parsed_end_date = None
        else:
            try:
                parsed_end_date = datetime.strptime(
                    end_date,
                    "%Y-%m-%d"
                ).date()
            except (TypeError, ValueError):
                return error_response(
                    "Formato de fecha inválido. Usa YYYY-MM-DD",
                    "INVALID_DATE_FORMAT",
                    400
                )

    if parsed_end_date and parsed_end_date < parsed_start_date:
        return error_response(
            "La fecha de finalización no puede ser anterior al inicio",
            "INVALID_TOURNAMENT_DATE_RANGE",
            400
        )

    parsed_referee_fee = tournament.default_referee_fee

    if default_referee_fee is not None:
        parsed_referee_fee, amount_error = parse_money(
            default_referee_fee,
            "El costo de arbitraje"
        )

        if amount_error:
            return amount_error

    final_name = name if name is not None else tournament.name

    existing_tournament = Tournament.query.filter(
        Tournament.club_id == user.club_id,
        func.lower(Tournament.name) == final_name.lower(),
        Tournament.start_date == parsed_start_date,
        Tournament.id != tournament.id
    ).first()

    if existing_tournament:
        return error_response(
            "Ya existe un torneo con ese nombre y fecha",
            "TOURNAMENT_ALREADY_EXISTS",
            409
        )

    if name is not None:
        tournament.name = name

    if organizer_name is not None:
        tournament.organizer_name = organizer_name or None

    tournament.start_date = parsed_start_date
    tournament.end_date = parsed_end_date
    tournament.default_referee_fee = parsed_referee_fee

    db.session.commit()

    return jsonify({
        "message": "Torneo actualizado correctamente",
        "tournament": _tournament_payload(tournament, user)
    }), 200


def transition_tournament_status(tournament_id, target_status):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para cambiar el estado del torneo",
            "FORBIDDEN",
            403
        )

    tournament = Tournament.query.get(tournament_id)

    if not tournament:
        return error_response(
            "Torneo no encontrado",
            "TOURNAMENT_NOT_FOUND",
            404
        )

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403
        )

    entity_error = get_club_sports_entity_error(user)

    if entity_error:
        return error_response(*entity_error)

    tournament = _lock_tournament(tournament.id)

    if not tournament or tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403,
        )

    entity_error = get_club_sports_entity_error(user)

    if entity_error:
        return error_response(*entity_error)

    season_error = get_season_operation_error(tournament.season)

    if season_error:
        return error_response(*season_error)

    if tournament.status == target_status:
        return jsonify({
            "message": (
                "Torneo completado correctamente"
                if target_status == "completed"
                else "Torneo cancelado correctamente"
            ),
            "tournament": _tournament_payload(tournament, user)
        }), 200

    if tournament.status != "active":
        return error_response(
            "El estado actual del torneo no permite esta transición",
            "INVALID_TOURNAMENT_STATUS",
            409
        )

    # Shared order with Match sports writes: Tournament -> Match. Locking the
    # open children makes the blocker and the transition one atomic decision.
    open_matches = (
        MatchSession.query
        .join(
            TournamentTeam,
            TournamentTeam.id == MatchSession.tournament_team_id,
        )
        .filter(
            TournamentTeam.tournament_id == tournament.id,
            MatchSession.is_completed.is_(False),
        )
        .order_by(MatchSession.id.asc())
        .populate_existing()
        .with_for_update()
        .all()
    )

    if open_matches:
        return jsonify({
            "error": True,
            "message": (
                "Completa los partidos abiertos antes de cambiar el estado "
                "del torneo."
            ),
            "code": "TOURNAMENT_HAS_OPEN_MATCHES",
            "open_matches_count": len(open_matches),
            "open_match_ids": [match.id for match in open_matches],
        }), 409

    if target_status == "cancelled":
        charges_error = _cancel_tournament_charges_error(tournament, user)

        if charges_error:
            message, code, status, blocking_count = charges_error

            if blocking_count is None:
                return error_response(message, code, status)

            return jsonify({
                "error": True,
                "message": message,
                "code": code,
                "pending_charges_count": blocking_count,
            }), status

    updated_count = Tournament.query.filter(
        Tournament.id == tournament.id,
        Tournament.status == "active"
    ).update(
        {"status": target_status},
        synchronize_session=False
    )

    if updated_count == 0:
        db.session.rollback()
        tournament = Tournament.query.get(tournament_id)

        if tournament.status == target_status:
            return jsonify({
                "message": (
                    "Torneo completado correctamente"
                    if target_status == "completed"
                    else "Torneo cancelado correctamente"
                ),
                "tournament": _tournament_payload(tournament, user)
            }), 200

        return error_response(
            "El estado actual del torneo no permite esta transición",
            "INVALID_TOURNAMENT_STATUS",
            409
        )

    db.session.commit()
    tournament = Tournament.query.get(tournament_id)

    return jsonify({
        "message": (
            "Torneo completado correctamente"
            if target_status == "completed"
            else "Torneo cancelado correctamente"
        ),
        "tournament": _tournament_payload(tournament, user)
    }), 200


@api.route(
    "/tournaments/<string:tournament_id>/complete",
    methods=["PUT"]
)
@jwt_required()
def complete_tournament(tournament_id):
    return transition_tournament_status(
        tournament_id,
        "completed"
    )


@api.route(
    "/tournaments/<string:tournament_id>/cancel",
    methods=["PUT"]
)
@jwt_required()
def cancel_tournament(tournament_id):
    return transition_tournament_status(
        tournament_id,
        "cancelled"
    )

@api.route(
    "/tournaments/<string:tournament_id>/teams",
    methods=["POST"]
)
@jwt_required()
def add_team_to_tournament(tournament_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para inscribir equipos",
            "FORBIDDEN",
            403
        )

    tournament = Tournament.query.get(tournament_id)

    if not tournament:
        return error_response(
            "Torneo no encontrado",
            "TOURNAMENT_NOT_FOUND",
            404
        )

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403
        )

    # El estado se lee ya bloqueado: completar o cancelar en paralelo espera a
    # esta inscripción, o esta ve el torneo cerrado y no inscribe.
    tournament = _lock_tournament(tournament.id)

    season_error = get_season_operation_error(tournament.season)

    if season_error:
        return error_response(*season_error)

    if tournament.status != "active":
        return error_response(
            "Solo puedes inscribir equipos en torneos activos",
            "TOURNAMENT_NOT_ACTIVE",
            409
        )

    body = request.get_json() or {}

    team_id = body.get("team_id")
    registration_fee = body.get("registration_fee", 0)

    if not team_id:
        return error_response(
            "El equipo es obligatorio",
            "TEAM_ID_REQUIRED",
            400
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    # Linked Match creation and roster writes use the same parent order:
    # Tournament -> Team/Season. Revalidate the Team after waiting so an
    # archive or Season transition cannot leave a stale registration behind.
    team = lock_team_lifecycle(team.id, user.club_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    assignment_error = get_team_assignment_error(user, team)

    if assignment_error:
        return error_response(*assignment_error)

    team_error = get_team_operation_error(team)

    if team_error:
        return error_response(*team_error)

    finance_error = get_finance_payload_error(
        user,
        body,
        ("registration_fee",)
    )

    if finance_error:
        return error_response(*finance_error)

    existing_entry = TournamentTeam.query.filter_by(
        tournament_id=tournament.id,
        team_id=team.id
    ).first()

    if existing_entry:
        return error_response(
            "Este equipo ya está inscrito en el torneo",
            "TEAM_ALREADY_IN_TOURNAMENT",
            409
        )

    parsed_registration_fee, amount_error = parse_money(
        registration_fee,
        "El costo de inscripción"
    )

    if amount_error:
        return amount_error

    tournament_team = TournamentTeam(
        tournament_id=tournament.id,
        team_id=team.id,
        registration_fee=parsed_registration_fee,
        status="active"
    )

    try:
        db.session.add(tournament_team)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()

        if not violates_named_constraint(
            error,
            TOURNAMENT_TEAM_UNIQUE_CONSTRAINTS,
        ):
            raise

        return error_response(
            "Este equipo ya está inscrito en el torneo",
            "TEAM_ALREADY_IN_TOURNAMENT",
            409,
        )

    return jsonify({
        "message": "Equipo inscrito correctamente",
        "tournament_team": _tournament_entry_payload(tournament_team, user)
    }), 201

@api.route(
    "/tournaments/<string:tournament_id>/teams",
    methods=["GET"]
)
@jwt_required()
def get_tournament_teams(tournament_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar equipos del torneo",
            "FORBIDDEN",
            403
        )

    tournament = Tournament.query.get(tournament_id)

    if not tournament:
        return error_response(
            "Torneo no encontrado",
            "TOURNAMENT_NOT_FOUND",
            404
        )

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este torneo",
            "FORBIDDEN",
            403
        )

    metrics = _get_tournament_read_model([tournament.id], user)[tournament.id]
    result = metrics["entries"]

    return jsonify({
        "tournament": _tournament_payload(tournament, user),
        "total_teams": len(result),
        "teams": result
    }), 200

@api.route(
    "/tournament-teams/<string:tournament_team_id>/players",
    methods=["GET"]
)
@jwt_required()
def get_tournament_team_players(tournament_team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar el roster del torneo",
            "FORBIDDEN",
            403
        )

    tournament_team = TournamentTeam.query.get(
        tournament_team_id
    )

    if not tournament_team:
        return error_response(
            "Participación de torneo no encontrada",
            "TOURNAMENT_TEAM_NOT_FOUND",
            404
        )

    if tournament_team.tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta participación",
            "FORBIDDEN",
            403
        )

    team_memberships = TeamPlayer.query.filter_by(
        team_id=tournament_team.team_id,
        left_at=None
    ).order_by(TeamPlayer.player_number.asc()).all()

    registered_rows = TournamentPlayer.query.filter_by(
        tournament_team_id=tournament_team.id
    ).all()

    registered_map = {
        row.player_id: row
        for row in registered_rows
    }

    serialize_player = get_player_serializer(
        user,
        [
            *(membership.player for membership in team_memberships),
            *(row.player for row in registered_rows),
        ]
    )

    players = []

    for membership in team_memberships:
        registration = registered_map.get(
            membership.player_id
        )

        players.append({
            "player_id": membership.player_id,
            "player_number": membership.player_number,
            "team_status": membership.status,
            "membership_open": True,
            "is_registered": (
                registration is not None
                and registration.status == "active"
            ),
            "registration_status": (
                registration.status
                if registration
                else None
            ),
            "currently_eligible": (
                membership.status == TEAM_PLAYER_STATUS_ACTIVE
                and membership.player.is_active
            ),
            "player": serialize_player(membership.player)
        })

    # Una inscripción existente sigue en el roster aunque su membership se
    # haya cerrado: si no se enviara, guardar la plantilla la retiraría.
    closed_registered_ids = set(registered_map) - {
        membership.player_id
        for membership in team_memberships
    }

    latest_closed_memberships = {}

    if closed_registered_ids:
        closed_memberships = TeamPlayer.query.filter(
            TeamPlayer.team_id == tournament_team.team_id,
            TeamPlayer.left_at.isnot(None),
            TeamPlayer.player_id.in_(closed_registered_ids)
        ).order_by(TeamPlayer.left_at.asc()).all()

        latest_closed_memberships = {
            membership.player_id: membership
            for membership in closed_memberships
        }

    for player_id in sorted(closed_registered_ids):
        registration = registered_map[player_id]
        membership = latest_closed_memberships.get(player_id)

        players.append({
            "player_id": player_id,
            "player_number": (
                membership.player_number
                if membership
                else None
            ),
            "team_status": None,
            "membership_open": False,
            "is_registered": registration.status == "active",
            "registration_status": registration.status,
            "currently_eligible": False,
            "player": serialize_player(registration.player)
        })

    matches = (
        MatchSession.query
        .options(joinedload(MatchSession.team).joinedload(Team.category))
        .filter_by(tournament_team_id=tournament_team.id)
        .order_by(MatchSession.date.desc(), MatchSession.id.asc())
        .all()
    )
    team_access = get_team_access_resolver(user)

    return jsonify({
        "tournament_team": _tournament_entry_payload(tournament_team, user),
        "total_players": len(players),
        "registered_count": sum(
            1
            for player in players
            if player["is_registered"]
        ),
        "withdrawn_count": sum(
            1
            for player in players
            if player["registration_status"] == "withdrawn"
        ),
        "currently_eligible_count": sum(
            1
            for player in players
            if player["is_registered"] and player["currently_eligible"]
        ),
        "matches": [
            _match_summary_payload(match, user, team_access)
            for match in matches
        ],
        "players": players
    }), 200

@api.route(
    "/tournament-teams/<string:tournament_team_id>/players",
    methods=["PUT"]
)
@jwt_required()
def update_tournament_team_players(tournament_team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar las inscripciones",
            "FORBIDDEN",
            403
        )

    tournament_team = TournamentTeam.query.get(
        tournament_team_id
    )

    if not tournament_team:
        return error_response(
            "Participación de torneo no encontrada",
            "TOURNAMENT_TEAM_NOT_FOUND",
            404
        )

    if tournament_team.tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta participación",
            "FORBIDDEN",
            403
        )

    assignment_error = get_team_assignment_error(user, tournament_team.team)

    if assignment_error:
        return error_response(*assignment_error)

    season_error = get_season_operation_error(
        tournament_team.tournament.season
    )

    if season_error:
        return error_response(*season_error)

    team_error = get_team_operation_error(tournament_team.team)

    if team_error:
        return error_response(*team_error)

    tournament_team = _get_tournament_team_for_update(tournament_team.id)

    team = lock_team_lifecycle(
        tournament_team.team_id,
        user.club_id,
    )

    if not team:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    assignment_error = get_team_assignment_error(user, team)

    if assignment_error:
        return error_response(*assignment_error)

    team_error = get_team_operation_error(team)

    if team_error:
        return error_response(*team_error)

    season_error = get_season_operation_error(tournament_team.tournament.season)

    if season_error:
        return error_response(*season_error)

    if tournament_team.tournament.status != "active":
        return error_response(
            "Solo puedes modificar participantes en torneos activos",
            "TOURNAMENT_NOT_ACTIVE",
            409
        )

    if tournament_team.status != "active":
        return error_response(
            "La participación del equipo no está activa",
            "TOURNAMENT_TEAM_NOT_ACTIVE",
            409
        )

    body = request.get_json() or {}

    player_ids = body.get("player_ids")

    if not isinstance(player_ids, list):
        return error_response(
            "La lista de deportistas es inválida",
            "INVALID_TOURNAMENT_PLAYERS",
            400
        )

    normalized_player_ids = list({
        str(player_id).strip()
        for player_id in player_ids
        if str(player_id).strip()
    })

    existing_rows = (
        TournamentPlayer.query
        .filter_by(tournament_team_id=tournament_team.id)
        .order_by(TournamentPlayer.player_id.asc())
        .populate_existing()
        .with_for_update()
        .all()
    )

    existing_map = {
        row.player_id: row
        for row in existing_rows
    }

    selected_ids = set(normalized_player_ids)

    player_ids_requiring_availability = {
        player_id
        for player_id in selected_ids
        if (
            player_id not in existing_map
            or existing_map[player_id].status != "active"
        )
    }

    if player_ids_requiring_availability:
        locked_players = (
            Player.query
            .filter(Player.id.in_(player_ids_requiring_availability))
            .order_by(Player.id.asc())
            .populate_existing()
            .with_for_update()
            .all()
        )
        locked_memberships = (
            TeamPlayer.query
            .filter(
                TeamPlayer.team_id == tournament_team.team_id,
                TeamPlayer.player_id.in_(player_ids_requiring_availability),
                TeamPlayer.left_at.is_(None),
            )
            .order_by(TeamPlayer.player_id.asc())
            .populate_existing()
            .with_for_update()
            .all()
        )
        players_by_id = {player.id: player for player in locked_players}
        memberships_by_player = {
            membership.player_id: membership
            for membership in locked_memberships
        }

        missing_memberships = (
            player_ids_requiring_availability - set(memberships_by_player)
        )

        if missing_memberships:
            if missing_memberships <= set(existing_map):
                return error_response(
                    (
                        "Una o más personas dejaron de estar disponibles para "
                        "una nueva inscripción en el torneo"
                    ),
                    "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT",
                    409,
                )

            return error_response(
                "Una o más personas no pertenecen actualmente al equipo",
                "PLAYER_NOT_IN_TEAM",
                400,
            )

        available_player_ids = {
            player_id
            for player_id in player_ids_requiring_availability
            if (
                player_id in players_by_id
                and players_by_id[player_id].club_id == user.club_id
                and players_by_id[player_id].is_active
                and memberships_by_player[player_id].status
                == TEAM_PLAYER_STATUS_ACTIVE
            )
        }

        if available_player_ids != player_ids_requiring_availability:
            return error_response(
                (
                    "Una o más personas dejaron de estar disponibles para una "
                    "nueva inscripción en el torneo"
                ),
                "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT",
                409,
            )

    active_player_ids = {
        player_id
        for player_id, row in existing_map.items()
        if row.status == "active"
    }

    # El reparto depende de toda la plantilla: con cargos existentes, el Coach
    # no puede cambiarla aunque quien entra o sale no tenga cargo propio.
    if (
        not can_configure_sports_finance(user)
        and active_player_ids != selected_ids
        and any(
            charge_blocks_roster_change(charge)
            for charge in _get_registration_charges_for_update(
                user.club_id,
                tournament_team.id
            )
        )
    ):
        db.session.rollback()
        return error_response(*FINANCE_DEPENDENCY_ERROR)

    removed_player_ids = active_player_ids - selected_ids

    removed_player_charges = []

    if removed_player_ids and can_configure_sports_finance(user):
        removed_player_charges = PlayerPayment.query.filter(
            PlayerPayment.club_id == user.club_id,
            PlayerPayment.player_id.in_(removed_player_ids),
            PlayerPayment.tournament_team_id == tournament_team.id,
            PlayerPayment.match_id.is_(None),
            PlayerPayment.payment_type == "tournament"
        ).populate_existing().with_for_update().all()

    locked_registration_charge = next(
        (
            charge
            for charge in removed_player_charges
            if charge.status == "paid" or charge.has_receipt_history
        ),
        None
    )

    if locked_registration_charge:
        return error_response(
            (
                "No puedes retirar a una persona con cargos de inscripción "
                "pagados o con recibo"
            ),
            "TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED",
            409
        )

    for charge in removed_player_charges:
        if charge.status in ["pending", "overdue", "cancelled"]:
            db.session.delete(charge)

    for player_id, row in existing_map.items():
        if player_id in selected_ids:
            row.status = "active"
        else:
            row.status = "withdrawn"

    for player_id in selected_ids:
        if player_id in existing_map:
            continue

        registration = TournamentPlayer(
            tournament_team_id=tournament_team.id,
            player_id=player_id,
            status="active"
        )

        db.session.add(registration)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()

        if not violates_named_constraint(
            error,
            TOURNAMENT_PLAYER_UNIQUE_CONSTRAINTS,
        ):
            raise

        return error_response(
            "El roster cambió mientras se guardaba. Actualiza e inténtalo de nuevo.",
            "TOURNAMENT_ROSTER_CHANGED",
            409,
        )

    active_registrations = TournamentPlayer.query.filter_by(
        tournament_team_id=tournament_team.id,
        status="active"
    ).all()

    serialize_player = get_player_serializer(
        user,
        [row.player for row in active_registrations]
    )

    return jsonify({
        "message": "Roster del torneo actualizado correctamente",
        "total_players": len(active_registrations),
        "players": [
            serialize_with_player_for_user(row, user, serialize_player)
            for row in active_registrations
        ]
    }), 200

@api.route(
    "/tournament-teams/<string:tournament_team_id>/registration-fee",
    methods=["PUT"]
)
@jwt_required()
def update_tournament_team_registration_fee(tournament_team_id):
    user = get_current_user()

    tournament_team = _get_club_tournament_team(tournament_team_id, user)

    if not tournament_team:
        return error_response(
            "Participación de torneo no encontrada",
            "TOURNAMENT_TEAM_NOT_FOUND",
            404
        )

    finance_error = get_sports_finance_error(user)

    if finance_error:
        return error_response(*finance_error)

    tournament_team = _get_tournament_team_for_update(tournament_team.id)

    if tournament_team.tournament.status != "active":
        return error_response(
            "Solo puedes cambiar la inscripción en torneos activos",
            "TOURNAMENT_NOT_ACTIVE",
            409
        )

    if tournament_team.status != "active":
        return error_response(
            "La participación del equipo no está activa",
            "TOURNAMENT_TEAM_NOT_ACTIVE",
            409
        )

    body = request.get_json() or {}
    registration_fee = body.get("registration_fee")

    if registration_fee in [None, ""]:
        return error_response(
            "El costo de inscripción debe ser mayor que cero",
            "INVALID_TOURNAMENT_REGISTRATION_FEE",
            400
        )

    parsed_registration_fee, amount_error = parse_money(
        registration_fee,
        "El costo de inscripción"
    )

    if amount_error:
        return amount_error

    if parsed_registration_fee <= 0:
        return error_response(
            "El costo de inscripción debe ser mayor que cero",
            "INVALID_TOURNAMENT_REGISTRATION_FEE",
            400
        )

    # Los cargos pendientes no se recalculan aquí: los reemplaza generar de nuevo.
    if any(
        charge.status == "paid" or charge.has_receipt_history
        for charge in _get_registration_charges_for_update(
            user.club_id,
            tournament_team.id
        )
    ):
        db.session.rollback()
        return error_response(
            (
                "No puedes cambiar la inscripción porque uno o más "
                "cargos ya fueron pagados o tienen recibo"
            ),
            "TOURNAMENT_REGISTRATION_CHARGES_LOCKED",
            409
        )

    tournament_team.registration_fee = parsed_registration_fee
    db.session.commit()

    return jsonify({
        "message": "Costo de inscripción actualizado correctamente",
        "tournament_team": _tournament_entry_payload(tournament_team, user)
    }), 200


@api.route(
    "/tournament-teams/<string:tournament_team_id>/registration-charges/preview",
    methods=["GET"]
)
@jwt_required()
def preview_tournament_registration_charges(tournament_team_id):
    user = get_current_user()

    tournament_team = _get_club_tournament_team(tournament_team_id, user)

    if not tournament_team:
        return error_response(
            "Participación de torneo no encontrada",
            "TOURNAMENT_TEAM_NOT_FOUND",
            404
        )

    finance_error = get_sports_finance_error(user)

    if finance_error:
        return error_response(*finance_error)

    tournament = tournament_team.tournament

    registration_fee = Decimal(
        str(tournament_team.registration_fee or 0)
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    if registration_fee <= 0:
        return error_response(
            "El costo de inscripción debe ser mayor que cero",
            "INVALID_TOURNAMENT_REGISTRATION_FEE",
            400
        )

    registered_players = TournamentPlayer.query.filter_by(
        tournament_team_id=tournament_team.id,
        status="active"
    ).order_by(
        TournamentPlayer.created_at.asc()
    ).all()

    if not registered_players:
        return error_response(
            "Debes inscribir al menos una persona antes de repartir el costo",
            "TOURNAMENT_PLAYERS_REQUIRED",
            400
        )

    distributed_amounts = split_money_exactly(
        registration_fee,
        len(registered_players)
    )

    existing_charges = PlayerPayment.query.filter_by(
        club_id=user.club_id,
        tournament_team_id=tournament_team.id,
        match_id=None,
        payment_type="tournament"
    ).all()

    existing_by_player = {
        charge.player_id: charge
        for charge in existing_charges
    }

    players_preview = []

    for index, registration in enumerate(registered_players):
        existing_charge = existing_by_player.get(
            registration.player_id
        )

        player_data = registration.player.serialize()

        team_membership = TeamPlayer.query.filter_by(
            team_id=tournament_team.team_id,
            player_id=registration.player_id,
            left_at=None
        ).first()

        players_preview.append({
            "tournament_player_id": registration.id,
            "player_id": registration.player_id,
            "player_number": (
                team_membership.player_number
                if team_membership
                else None
            ),
            "player": player_data,
            "amount": float(distributed_amounts[index]),
            "existing_charge": (
                existing_charge.serialize()
                if existing_charge
                else None
            )
        })

    has_locked_charges = any(
        charge.status == "paid" or charge.has_receipt_history
        for charge in existing_charges
    )

    return jsonify({
        "tournament_team": tournament_team.serialize(),
        "registration_fee": float(registration_fee),
        "currency_code": tournament.club.currency_code,
        "registered_players_count": len(registered_players),
        "existing_charges_count": len(existing_charges),
        "has_locked_charges": has_locked_charges,
        "can_generate": (
            tournament.status == "active"
            and not has_locked_charges
        ),
        "players": players_preview
    }), 200

@api.route(
    "/tournament-teams/<string:tournament_team_id>/registration-charges",
    methods=["POST"]
)
@jwt_required()
def generate_tournament_registration_charges(tournament_team_id):
    user = get_current_user()

    tournament_team = _get_club_tournament_team(tournament_team_id, user)

    if not tournament_team:
        return error_response(
            "Participación de torneo no encontrada",
            "TOURNAMENT_TEAM_NOT_FOUND",
            404
        )

    finance_error = get_sports_finance_error(user)

    if finance_error:
        return error_response(*finance_error)

    tournament_team = _get_tournament_team_for_update(tournament_team.id)
    tournament = tournament_team.tournament

    if tournament.status != "active":
        return error_response(
            "Solo puedes generar cargos en torneos activos",
            "TOURNAMENT_NOT_ACTIVE",
            409
        )

    if tournament_team.status != "active":
        return error_response(
            "La participación del equipo no está activa",
            "TOURNAMENT_TEAM_NOT_ACTIVE",
            409
        )

    registration_fee = Decimal(
        str(tournament_team.registration_fee or 0)
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    if registration_fee <= 0:
        return error_response(
            "El costo de inscripción debe ser mayor que cero",
            "INVALID_TOURNAMENT_REGISTRATION_FEE",
            400
        )

    registered_players = TournamentPlayer.query.filter_by(
        tournament_team_id=tournament_team.id,
        status="active"
    ).order_by(
        TournamentPlayer.created_at.asc()
    ).all()

    if not registered_players:
        return error_response(
            "Debes inscribir al menos una persona antes de generar los cargos",
            "TOURNAMENT_PLAYERS_REQUIRED",
            400
        )

    existing_charges = _get_registration_charges_for_update(
        user.club_id,
        tournament_team.id
    )

    protected_charges = [
        charge
        for charge in existing_charges
        if charge.status == "paid" or charge.has_receipt_history
    ]

    if protected_charges:
        return error_response(
            (
                "No puedes recalcular la inscripción porque uno o más "
                "cargos ya fueron pagados o tienen recibo"
            ),
            "TOURNAMENT_REGISTRATION_CHARGES_LOCKED",
            409
        )

    # Sustituimos únicamente cargos que aún no tienen valor financiero definitivo.
    for charge in existing_charges:
        if charge.status in ["pending", "overdue", "cancelled"]:
            db.session.delete(charge)

    db.session.flush()

    distributed_amounts = split_money_exactly(
        registration_fee,
        len(registered_players)
    )

    created_charges = []

    tournament_name = (
        tournament.name
        if tournament
        else "Torneo"
    )

    team_name = (
        tournament_team.team.name
        if tournament_team.team
        else "Equipo"
    )

    for index, registration in enumerate(registered_players):
        charge = PlayerPayment(
            club_id=user.club_id,
            player_id=registration.player_id,
            tournament_team_id=tournament_team.id,
            match_id=None,
            payment_type="tournament",
            amount=distributed_amounts[index],
            currency_code=tournament.club.currency_code,
            status="pending",
            due_date=tournament.start_date,
            notes=(
                f"Inscripción al torneo {tournament_name}"
                f" · Equipo: {team_name}"
            ),
            created_by=user.id
        )

        charge = add_charge_if_absent(
            charge=charge,
            identity_filters={
                "club_id": user.club_id,
                "player_id": registration.player_id,
                "tournament_team_id": tournament_team.id,
                "payment_type": "tournament"
            },
            constraint_name=(
                "uq_player_payments_tournament_charge"
            )
        )

        created_charges.append(charge)

    db.session.commit()

    return jsonify({
        "message": "Cargos de inscripción generados correctamente",
        "registration_fee": float(registration_fee),
        "currency_code": tournament.club.currency_code,
        "total_charges": len(created_charges),
        "charges": [
            charge.serialize()
            for charge in created_charges
        ]
    }), 201


@api.route("/tournament-registration-charges", methods=["GET"])
@jwt_required()
def get_tournament_registration_charge_contexts():
    user = get_current_user()

    finance_error = get_finance_access_error(user)

    if finance_error:
        return error_response(*finance_error)

    entries = TournamentTeam.query.join(
        Tournament
    ).filter(
        Tournament.club_id == user.club_id
    ).order_by(
        Tournament.start_date.desc(),
        TournamentTeam.created_at.asc()
    ).all()

    contexts = []

    for entry in entries:
        registered_players_count = TournamentPlayer.query.filter_by(
            tournament_team_id=entry.id,
            status="active"
        ).count()

        existing_charges = PlayerPayment.query.filter_by(
            club_id=user.club_id,
            tournament_team_id=entry.id,
            match_id=None,
            payment_type="tournament"
        ).all()

        contexts.append({
            "tournament_team": entry.serialize(),
            "registered_players_count": registered_players_count,
            "existing_charges_count": len(existing_charges),
            "has_locked_charges": any(
                charge.status == "paid" or charge.has_receipt_history
                for charge in existing_charges
            )
        })

    return jsonify({
        "total_entries": len(contexts),
        "entries": contexts
    }), 200

@api.route(
    "/teams/<string:team_id>/tournament-entries",
    methods=["GET"]
)
@jwt_required()
def get_team_tournament_entries(team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar torneos",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    entries = TournamentTeam.query.join(
        Tournament
    ).filter(
        TournamentTeam.team_id == team.id,
        TournamentTeam.status == "active",
        Tournament.status == "active",
        Tournament.club_id == user.club_id
    ).order_by(
        Tournament.start_date.desc()
    ).all()

    team_access = get_team_access_resolver(user)
    entry_ids = [entry.id for entry in entries]
    eligible_counts = dict(
        db.session.query(
            TournamentPlayer.tournament_team_id,
            func.count(TournamentPlayer.id),
        )
        .join(
            TournamentTeam,
            TournamentTeam.id == TournamentPlayer.tournament_team_id,
        )
        .join(Player, Player.id == TournamentPlayer.player_id)
        .join(
            TeamPlayer,
            (TeamPlayer.team_id == TournamentTeam.team_id)
            & (TeamPlayer.player_id == TournamentPlayer.player_id)
            & TeamPlayer.left_at.is_(None),
        )
        .filter(
            TournamentPlayer.tournament_team_id.in_(entry_ids),
            TournamentPlayer.status == "active",
            Player.is_active.is_(True),
            TeamPlayer.status == TEAM_PLAYER_STATUS_ACTIVE,
        )
        .group_by(TournamentPlayer.tournament_team_id)
        .all()
        if entry_ids
        else []
    )

    return jsonify({
        "team": {**team.serialize(), **team_access(team)},
        "tournament_entries": [
            {
                **_tournament_entry_payload(entry, user, team_access),
                "currently_eligible_players_count": eligible_counts.get(
                    entry.id,
                    0,
                ),
            }
            for entry in entries
        ]
    }), 200
