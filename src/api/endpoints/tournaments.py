from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from src.api.api_blueprint import api
from src.api.models import (
    db,
    MatchSession,
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
from src.api.season_service import get_active_season_for_club
from src.api.utils import error_response, get_current_user


VALID_TOURNAMENT_STATUSES = [
    "active",
    "completed",
    "cancelled"
]

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

    body = request.get_json() or {}

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

    season = get_active_season_for_club(user.club_id)

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
        "tournament": tournament.serialize()
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

    season = get_active_season_for_club(user.club_id)

    if not season:
        return error_response(
            "El club no tiene una temporada activa",
            "ACTIVE_SEASON_REQUIRED",
            409
        )

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

    result = []

    for tournament in tournaments:
        result.append({
            **tournament.serialize(),
            "total_teams": len(tournament.team_entries),
            "teams": [
                entry.serialize()
                for entry in tournament.team_entries
            ]
        })

    return jsonify({
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

    teams = TournamentTeam.query.filter_by(
        tournament_id=tournament.id
    ).order_by(TournamentTeam.created_at.asc()).all()

    return jsonify({
        "tournament": {
            **tournament.serialize(),
            "teams": [
                {
                    **entry.serialize(),
                    "total_players": TournamentPlayer.query.filter_by(
                        tournament_team_id=entry.id,
                        status="active"
                    ).count(),
                    "total_matches": MatchSession.query.filter_by(
                        tournament_team_id=entry.id
                    ).count()
                }
                for entry in teams
            ]
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

    if tournament.status != "active":
        return error_response(
            "Solo puedes editar torneos activos",
            "TOURNAMENT_NOT_ACTIVE",
            409
        )

    body = request.get_json() or {}

    if "status" in body:
        return error_response(
            (
                "El estado del torneo debe cambiarse mediante "
                "la acción correspondiente"
            ),
            "INVALID_TOURNAMENT_STATUS",
            400
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
        "tournament": tournament.serialize()
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

    if tournament.status == target_status:
        return jsonify({
            "message": (
                "Torneo completado correctamente"
                if target_status == "completed"
                else "Torneo cancelado correctamente"
            ),
            "tournament": tournament.serialize()
        }), 200

    if tournament.status != "active":
        return error_response(
            "El estado actual del torneo no permite esta transición",
            "INVALID_TOURNAMENT_STATUS",
            409
        )

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
                "tournament": tournament.serialize()
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
        "tournament": tournament.serialize()
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

    db.session.add(tournament_team)
    db.session.commit()

    return jsonify({
        "message": "Equipo inscrito correctamente",
        "tournament_team": tournament_team.serialize()
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

    entries = TournamentTeam.query.filter_by(
        tournament_id=tournament.id
    ).order_by(TournamentTeam.created_at.asc()).all()

    result = []

    for entry in entries:
        active_players = TournamentPlayer.query.filter_by(
            tournament_team_id=entry.id,
            status="active"
        ).count()

        matches_count = MatchSession.query.filter_by(
            tournament_team_id=entry.id
        ).count()

        result.append({
            **entry.serialize(),
            "total_players": active_players,
            "total_matches": matches_count
        })

    return jsonify({
        "tournament": tournament.serialize(),
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
            "No tienes permisos para consultar jugadoras del torneo",
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

    players = []

    for membership in team_memberships:
        registration = registered_map.get(
            membership.player_id
        )

        players.append({
            "player_id": membership.player_id,
            "player_number": membership.player_number,
            "team_status": membership.status,
            "is_registered": (
                registration is not None
                and registration.status == "active"
            ),
            "registration_status": (
                registration.status
                if registration
                else None
            ),
            "player": membership.player.serialize()
        })

    return jsonify({
        "tournament_team": tournament_team.serialize(),
        "total_players": len(players),
        "registered_count": sum(
            1
            for player in players
            if player["is_registered"]
        ),
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
            "La lista de jugadoras es inválida",
            "INVALID_TOURNAMENT_PLAYERS",
            400
        )

    normalized_player_ids = list({
        str(player_id).strip()
        for player_id in player_ids
        if str(player_id).strip()
    })

    valid_memberships = TeamPlayer.query.filter(
        TeamPlayer.team_id == tournament_team.team_id,
        TeamPlayer.left_at.is_(None),
        TeamPlayer.player_id.in_(normalized_player_ids)
    ).all() if normalized_player_ids else []

    valid_player_ids = {
        membership.player_id
        for membership in valid_memberships
    }

    invalid_player_ids = set(
        normalized_player_ids
    ) - valid_player_ids

    if invalid_player_ids:
        return error_response(
            "Una o más jugadoras no pertenecen al equipo",
            "PLAYER_NOT_IN_TEAM",
            400
        )

    existing_rows = TournamentPlayer.query.filter_by(
        tournament_team_id=tournament_team.id
    ).all()

    existing_map = {
        row.player_id: row
        for row in existing_rows
    }

    selected_ids = set(normalized_player_ids)

    removed_player_ids = {
        player_id
        for player_id, row in existing_map.items()
        if row.status == "active" and player_id not in selected_ids
    }

    removed_player_charges = []

    if removed_player_ids:
        removed_player_charges = PlayerPayment.query.filter(
            PlayerPayment.club_id == user.club_id,
            PlayerPayment.player_id.in_(removed_player_ids),
            PlayerPayment.tournament_team_id == tournament_team.id,
            PlayerPayment.match_id.is_(None),
            PlayerPayment.payment_type == "tournament"
        ).all()

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
                "No puedes retirar una jugadora con cargos de inscripción "
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

    db.session.commit()

    active_registrations = TournamentPlayer.query.filter_by(
        tournament_team_id=tournament_team.id,
        status="active"
    ).all()

    return jsonify({
        "message": "Jugadoras inscritas correctamente",
        "total_players": len(active_registrations),
        "players": [
            row.serialize()
            for row in active_registrations
        ]
    }), 200

@api.route(
    "/tournament-teams/<string:tournament_team_id>/registration-charges/preview",
    methods=["GET"]
)
@jwt_required()
def preview_tournament_registration_charges(tournament_team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para consultar el reparto de inscripción",
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

    tournament = tournament_team.tournament

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta participación",
            "FORBIDDEN",
            403
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
            "Debes inscribir al menos una jugadora antes de repartir el costo",
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

        if user.role == "staff":
            player_data = {
                "id": registration.player.id,
                "first_name": registration.player.first_name,
                "last_name": registration.player.last_name
            }

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

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para generar cargos de inscripción",
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

    tournament = tournament_team.tournament

    if tournament.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta participación",
            "FORBIDDEN",
            403
        )

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
            "Debes inscribir al menos una jugadora antes de generar los cargos",
            "TOURNAMENT_PLAYERS_REQUIRED",
            400
        )

    existing_charges = PlayerPayment.query.filter_by(
        club_id=user.club_id,
        tournament_team_id=tournament_team.id,
        match_id=None,
        payment_type="tournament"
    ).all()

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

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para consultar cargos de torneos",
            "FORBIDDEN",
            403
        )

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

    return jsonify({
        "team": team.serialize(),
        "tournament_entries": [
            entry.serialize()
            for entry in entries
        ]
    }), 200
