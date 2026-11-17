from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from src.api.api_blueprint import api
from src.api.integrity_errors import violates_named_constraint
from src.api.models import (
    db,
    Player,
    Season,
    Team,
    TeamCoachAssignment,
    TeamPlayer,
    Tournament,
)
from src.api.onboarding_service import finish_club_onboarding_if_complete
from src.api.season_service import (
    build_season_activation_preflight,
    get_season_open_activities,
    lock_club_seasons_for_update,
)
from src.api.utils import error_response, get_current_user
from src.api.team_player_status import VALID_TEAM_PLAYER_STATUSES


OPEN_PLAYER_CONSTRAINTS = (
    "uq_team_players_open_player",
    "team_players.team_id, team_players.player_id",
)
OPEN_NUMBER_CONSTRAINTS = (
    "uq_team_players_open_number",
    "team_players.team_id, team_players.player_number",
)
TEAM_UNIQUE_CONSTRAINTS = (
    "unique_team_gender_per_category",
    "uq_teams_scope_lower_name",
    "teams.name, teams.gender, teams.category_id, teams.club_id, teams.season_id",
)
ACTIVE_SEASON_CONSTRAINTS = (
    "uq_seasons_active_per_club",
    "unique constraint failed: seasons.club_id",
)


def _owner_or_error(user):
    if user.role == "club_owner":
        return None

    return error_response(
        "Solo el dueño del club puede gestionar temporadas",
        "FORBIDDEN",
        403,
    )


def _club_season_or_error(season_id, user):
    season = db.session.get(Season, season_id)

    if not season or season.club_id != user.club_id:
        return None, error_response(
            "Temporada no encontrada",
            "SEASON_NOT_FOUND",
            404,
        )

    return season, None


def _parse_season_fields(body, current=None):
    name_value = body.get("name", current.name if current else "")
    name = " ".join(str(name_value or "").strip().split())
    if not name:
        return None, error_response(
            "El nombre de la temporada es obligatorio",
            "SEASON_NAME_REQUIRED",
            400,
        )

    start_value = body.get(
        "start_date",
        current.start_date.isoformat() if current and current.start_date else "",
    )
    try:
        start_date = datetime.strptime(str(start_value or ""), "%Y-%m-%d").date()
    except ValueError:
        return None, error_response(
            "La fecha de inicio debe usar el formato YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400,
        )

    if "end_date" in body:
        end_value = body.get("end_date")
    else:
        end_value = (
            current.end_date.isoformat()
            if current and current.end_date
            else None
        )

    end_date = None
    if end_value:
        try:
            end_date = datetime.strptime(str(end_value), "%Y-%m-%d").date()
        except ValueError:
            return None, error_response(
                "La fecha de finalización debe usar el formato YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400,
            )

    if end_date and end_date < start_date:
        return None, error_response(
            "La fecha de finalización no puede ser anterior al inicio",
            "INVALID_SEASON_DATE_RANGE",
            400,
        )

    return {
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
    }, None


def _season_payload(season, include_teams=False):
    data = season.serialize()
    teams = Team.query.filter_by(
        club_id=season.club_id,
        season_id=season.id,
    ).order_by(Team.name).all()
    data["total_teams"] = len(teams)
    data["active_teams"] = sum(team.status == "active" for team in teams)
    tournament_count = Tournament.query.filter_by(
        club_id=season.club_id,
        season_id=season.id,
    ).count()
    data["can_delete"] = (
        season.status == "planned"
        and not teams
        and tournament_count == 0
    )

    if season.status == "active":
        data["open_activities"] = get_season_open_activities(season)

    if season.status == "planned":
        active_team_ids = [team.id for team in teams if team.status == "active"]
        total_players = 0
        teams_with_players = set()
        teams_with_coach = set()
        if active_team_ids:
            memberships = TeamPlayer.query.with_entities(
                TeamPlayer.team_id
            ).filter(
                TeamPlayer.team_id.in_(active_team_ids),
                TeamPlayer.left_at.is_(None),
            ).all()
            total_players = len(memberships)
            teams_with_players = {row[0] for row in memberships}
            teams_with_coach = {
                row[0]
                for row in TeamCoachAssignment.query.with_entities(
                    TeamCoachAssignment.team_id
                ).filter(
                    TeamCoachAssignment.club_id == season.club_id,
                    TeamCoachAssignment.team_id.in_(active_team_ids),
                    TeamCoachAssignment.removed_at.is_(None),
                ).distinct().all()
            }
        data["preparation"] = {
            "total_players": total_players,
            "teams_without_players": len(active_team_ids) - len(teams_with_players),
            "teams_without_coach": len(active_team_ids) - len(teams_with_coach),
        }

    if include_teams:
        data["teams"] = [
            {
                **team.serialize(),
                "total_players": TeamPlayer.query.filter_by(
                    team_id=team.id,
                    left_at=None,
                ).count(),
            }
            for team in teams
        ]

    return data


@api.route("/seasons", methods=["GET"])
@jwt_required()
def get_seasons():
    user = get_current_user()

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar temporadas",
            "FORBIDDEN",
            403,
        )

    seasons = Season.query.filter_by(club_id=user.club_id).order_by(
        Season.start_date.desc(),
        Season.created_at.desc(),
    ).all()

    return jsonify({
        "seasons": [_season_payload(season) for season in seasons]
    }), 200


@api.route("/seasons/<string:season_id>", methods=["GET"])
@jwt_required()
def get_season_detail(season_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar temporadas",
            "FORBIDDEN",
            403,
        )

    season, season_error = _club_season_or_error(season_id, user)

    if season_error:
        return season_error

    return jsonify({"season": _season_payload(season, include_teams=True)}), 200


@api.route("/seasons", methods=["POST"])
@jwt_required()
def create_planned_season():
    user = get_current_user()
    role_error = _owner_or_error(user)

    if role_error:
        return role_error

    fields, field_error = _parse_season_fields(request.get_json() or {})
    if field_error:
        return field_error

    season = Season(
        club_id=user.club_id,
        **fields,
        status="planned",
        created_by=user.id,
    )
    db.session.add(season)
    db.session.commit()

    return jsonify({
        "message": "Temporada planificada creada correctamente",
        "season": _season_payload(season),
    }), 201


@api.route("/seasons/<string:season_id>", methods=["PATCH"])
@jwt_required()
def edit_planned_season(season_id):
    user = get_current_user()
    role_error = _owner_or_error(user)
    if role_error:
        return role_error

    seasons = lock_club_seasons_for_update(user.club_id)
    season = next((row for row in seasons if row.id == season_id), None)
    if not season:
        return error_response("Temporada no encontrada", "SEASON_NOT_FOUND", 404)
    if season.status != "planned":
        return error_response(
            "Solo una temporada en preparación puede editarse",
            "SEASON_NOT_PLANNED",
            409,
        )

    fields, field_error = _parse_season_fields(
        request.get_json() or {},
        current=season,
    )
    if field_error:
        db.session.rollback()
        return field_error

    season.name = fields["name"]
    season.start_date = fields["start_date"]
    season.end_date = fields["end_date"]
    db.session.commit()
    return jsonify({
        "message": "Temporada actualizada correctamente",
        "season": _season_payload(season),
    }), 200


@api.route("/seasons/<string:season_id>", methods=["DELETE"])
@jwt_required()
def delete_empty_planned_season(season_id):
    user = get_current_user()
    role_error = _owner_or_error(user)
    if role_error:
        return role_error

    seasons = lock_club_seasons_for_update(user.club_id)
    season = next((row for row in seasons if row.id == season_id), None)
    if not season:
        return error_response("Temporada no encontrada", "SEASON_NOT_FOUND", 404)
    if season.status != "planned":
        return error_response(
            "Solo una temporada en preparación puede eliminarse",
            "SEASON_NOT_PLANNED",
            409,
        )

    dependencies = {
        "teams": Team.query.filter_by(
            club_id=user.club_id,
            season_id=season.id,
        ).count(),
        "tournaments": Tournament.query.filter_by(
            club_id=user.club_id,
            season_id=season.id,
        ).count(),
    }
    if any(dependencies.values()):
        db.session.rollback()
        return jsonify({
            "error": True,
            "code": "SEASON_HAS_DEPENDENCIES",
            "message": "La temporada ya tiene estructura o actividad asociada",
            "details": dependencies,
        }), 409

    db.session.delete(season)
    db.session.commit()
    return jsonify({"message": "Temporada eliminada correctamente"}), 200


@api.route("/seasons/<string:target_season_id>/preflight", methods=["GET"])
@jwt_required()
def get_season_preflight(target_season_id):
    user = get_current_user()
    role_error = _owner_or_error(user)
    if role_error:
        return role_error

    target, target_error = _club_season_or_error(target_season_id, user)
    if target_error:
        return target_error
    if target.status != "planned":
        return error_response(
            "La temporada destino debe estar en preparación",
            "SEASON_NOT_PLANNED",
            409,
        )

    source = Season.query.filter_by(
        club_id=user.club_id,
        status="active",
    ).first()
    return jsonify(build_season_activation_preflight(target, source)), 200


@api.route(
    "/seasons/<string:target_season_id>/teams/duplicate",
    methods=["POST"],
)
@jwt_required()
def duplicate_season_teams(target_season_id):
    user = get_current_user()
    role_error = _owner_or_error(user)

    if role_error:
        return role_error

    body = request.get_json() or {}
    source_id = body.get("source_season_id")
    team_ids = body.get("team_ids")

    if not source_id:
        return error_response(
            "La temporada de origen es obligatoria",
            "SOURCE_SEASON_REQUIRED",
            400,
        )

    if not isinstance(team_ids, list) or not team_ids:
        return error_response(
            "Selecciona al menos un equipo",
            "TEAM_SELECTION_REQUIRED",
            400,
        )

    seasons = lock_club_seasons_for_update(user.club_id)
    by_id = {season.id: season for season in seasons}
    target = by_id.get(target_season_id)
    source = by_id.get(source_id)

    if not target or not source:
        return error_response("Temporada no encontrada", "SEASON_NOT_FOUND", 404)
    if target.status != "planned":
        return error_response(
            "La temporada destino debe estar planificada",
            "SEASON_NOT_PLANNED",
            409,
        )
    if source.status != "active":
        return error_response(
            "La temporada de origen ya no es la temporada activa",
            "SEASON_TRANSITION_CONFLICT",
            409,
        )

    normalized_ids = list(dict.fromkeys(str(team_id) for team_id in team_ids))
    source_teams = Team.query.filter(
        Team.club_id == user.club_id,
        Team.season_id == source.id,
        Team.status == "active",
        Team.id.in_(normalized_ids),
    ).all()

    if len(source_teams) != len(normalized_ids):
        return error_response(
            "Uno o más equipos no pertenecen a la temporada de origen",
            "TEAM_NOT_FOUND",
            404,
        )

    for source_team in source_teams:
        already_exists = Team.query.filter(
            Team.club_id == user.club_id,
            Team.season_id == target.id,
            Team.category_id == source_team.category_id,
            Team.gender == source_team.gender,
            func.lower(Team.name) == source_team.name.lower(),
        ).first()

        if already_exists:
            return error_response(
                "Este equipo ya fue preparado en la temporada destino",
                "TEAM_ALREADY_COPIED",
                409,
            )

    copied_teams = [
        Team(
            name=source_team.name,
            gender=source_team.gender,
            category_id=source_team.category_id,
            club_id=user.club_id,
            season_id=target.id,
            status="active",
        )
        for source_team in source_teams
    ]
    db.session.add_all(copied_teams)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()

        if not violates_named_constraint(error, TEAM_UNIQUE_CONSTRAINTS):
            raise

        return error_response(
            "Uno de los equipos ya fue preparado en la temporada destino",
            "TEAM_ALREADY_COPIED",
            409,
        )

    return jsonify({
        "message": "Estructura de equipos duplicada correctamente",
        "teams": [team.serialize() for team in copied_teams],
    }), 201


@api.route("/teams/<string:target_team_id>/roster/copy", methods=["POST"])
@jwt_required()
def copy_team_roster(target_team_id):
    user = get_current_user()
    role_error = _owner_or_error(user)

    if role_error:
        return role_error

    # Same first lock as transition/structure copy. Lifecycle is re-read after
    # waiting, so no roster can be inserted into a target that became active.
    lock_club_seasons_for_update(user.club_id)
    target = db.session.get(Team, target_team_id)

    if not target or target.club_id != user.club_id:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    if target.status != "active":
        return error_response(
            "El equipo destino está archivado",
            "TEAM_ARCHIVED",
            409,
        )

    if not target.season or target.season.status != "planned":
        return error_response(
            "El equipo destino debe pertenecer a una temporada planificada",
            "SEASON_NOT_PLANNED",
            409,
        )

    body = request.get_json() or {}
    source_team_id = body.get("source_team_id")
    player_ids = body.get("player_ids")
    requested_players = body.get("players")

    if not source_team_id:
        return error_response(
            "El equipo de origen es obligatorio",
            "SOURCE_TEAM_REQUIRED",
            400,
        )

    if requested_players is not None and not isinstance(requested_players, list):
        return error_response(
            "La selección de deportistas no es válida",
            "INVALID_PLAYER_SELECTION",
            400,
        )

    if requested_players is None and (not isinstance(player_ids, list) or not player_ids):
        return error_response(
            "Selecciona al menos una jugadora",
            "PLAYER_SELECTION_REQUIRED",
            400,
        )

    if requested_players == []:
        return error_response(
            "Selecciona al menos una deportista",
            "PLAYER_SELECTION_REQUIRED",
            400,
        )

    source = db.session.get(Team, source_team_id)

    if not source or source.club_id != user.club_id:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    if (
        source.status != "active"
        or not source.season
        or source.season.status != "active"
    ):
        return error_response(
            "El equipo origen debe pertenecer a la temporada activa",
            "SOURCE_TEAM_NOT_ACTIVE",
            409,
        )

    if requested_players is None:
        normalized_ids = list(dict.fromkeys(str(player_id) for player_id in player_ids))
        request_by_id = {player_id: None for player_id in normalized_ids}
    else:
        request_by_id = {}
        for item in requested_players:
            if not isinstance(item, dict) or not item.get("player_id"):
                return error_response(
                    "La selección de deportistas no es válida",
                    "INVALID_PLAYER_SELECTION",
                    400,
                )
            player_id = str(item["player_id"])
            if player_id in request_by_id:
                return error_response(
                    "Una deportista aparece más de una vez",
                    "INVALID_PLAYER_SELECTION",
                    400,
                )
            request_by_id[player_id] = item
        normalized_ids = list(request_by_id)

    source_memberships = TeamPlayer.query.join(Player).filter(
        TeamPlayer.team_id == source.id,
        TeamPlayer.player_id.in_(normalized_ids),
        TeamPlayer.left_at.is_(None),
        Player.club_id == user.club_id,
    ).all()

    if len(source_memberships) != len(normalized_ids):
        return error_response(
            "Una o más jugadoras no pertenecen al roster de origen",
            "PLAYER_NOT_IN_TEAM",
            400,
        )

    memberships_by_player = {
        membership.player_id: membership for membership in source_memberships
    }
    prepared = []
    for player_id in normalized_ids:
        source_membership = memberships_by_player[player_id]
        player = source_membership.player
        item = request_by_id[player_id]

        if not player.is_active:
            return error_response(
                "Una o más deportistas están inactivas en el club",
                "PLAYER_INACTIVE",
                409,
            )

        if target.gender != "mixed" and player.sex != target.gender:
            return error_response(
                "Una o más deportistas no son compatibles con la rama destino",
                "PLAYER_GENDER_MISMATCH",
                409,
            )

        if item is None:
            if source_membership.status == "inactive":
                return error_response(
                    "Revisa explícitamente la disponibilidad de la deportista",
                    "PLAYER_STATUS_REVIEW_REQUIRED",
                    409,
                )
            player_number = source_membership.player_number
            target_status = source_membership.status
        else:
            player_number = item.get("player_number")
            target_status = item.get("status")

        try:
            player_number = int(player_number)
        except (TypeError, ValueError):
            return error_response(
                "El dorsal destino debe ser numérico",
                "INVALID_PLAYER_NUMBER",
                400,
            )

        if player_number < 1 or player_number > 99:
            return error_response(
                "El dorsal destino debe estar entre 1 y 99",
                "INVALID_PLAYER_NUMBER",
                400,
            )

        if target_status not in VALID_TEAM_PLAYER_STATUSES:
            return error_response(
                "La disponibilidad destino no es válida",
                "INVALID_PLAYER_STATUS",
                400,
            )

        prepared.append((source_membership, player_number, target_status))

    existing_players = {
        row[0]
        for row in TeamPlayer.query.with_entities(TeamPlayer.player_id).filter(
            TeamPlayer.team_id == target.id,
            TeamPlayer.left_at.is_(None),
            TeamPlayer.player_id.in_(normalized_ids),
        ).all()
    }
    if existing_players:
        return error_response(
            "Una o más jugadoras ya pertenecen al equipo destino",
            "PLAYER_ALREADY_IN_TEAM",
            409,
        )

    target_numbers = [player_number for _, player_number, _ in prepared]
    occupied_number = TeamPlayer.query.filter(
        TeamPlayer.team_id == target.id,
        TeamPlayer.left_at.is_(None),
        TeamPlayer.player_number.in_(target_numbers),
    ).first()

    if occupied_number or len(target_numbers) != len(set(target_numbers)):
        return error_response(
            "Uno de los números seleccionados ya está ocupado en el equipo destino",
            "PLAYER_NUMBER_DUPLICATED",
            409,
        )

    memberships = [
        TeamPlayer(
            team_id=target.id,
            player_id=source_membership.player_id,
            player_number=player_number,
            status=target_status,
        )
        for source_membership, player_number, target_status in prepared
    ]
    db.session.add_all(memberships)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if violates_named_constraint(error, OPEN_PLAYER_CONSTRAINTS):
            return error_response(
                "Una o más deportistas ya pertenecen al equipo destino",
                "PLAYER_ALREADY_IN_TEAM",
                409,
            )
        if violates_named_constraint(error, OPEN_NUMBER_CONSTRAINTS):
            return error_response(
                "Uno de los dorsales ya está ocupado en el equipo destino",
                "PLAYER_NUMBER_DUPLICATED",
                409,
            )
        raise

    return jsonify({
        "message": "Roster preparado correctamente",
        "memberships": [membership.serialize() for membership in memberships],
    }), 201


@api.route("/seasons/<string:target_season_id>/transition", methods=["POST"])
@jwt_required()
def transition_season(target_season_id):
    user = get_current_user()
    role_error = _owner_or_error(user)

    if role_error:
        return role_error

    body = request.get_json() or {}
    source_season_id = body.get("source_season_id")
    if body.get("confirm_activation") is not True:
        return error_response(
            "Confirma explícitamente la activación de la temporada",
            "SEASON_ACTIVATION_CONFIRMATION_REQUIRED",
            400,
        )

    seasons = lock_club_seasons_for_update(user.club_id)
    by_id = {season.id: season for season in seasons}
    target = by_id.get(target_season_id)
    source = next(
        (season for season in seasons if season.status == "active"),
        None,
    )

    if not target:
        return error_response(
            "Temporada no encontrada",
            "SEASON_NOT_FOUND",
            404,
        )

    if source and not source_season_id:
        return error_response(
            "La temporada activa cambió mientras preparabas la transición",
            "SEASON_TRANSITION_CONFLICT",
            409,
        )

    if source and source_season_id != source.id:
        return error_response(
            "La temporada activa cambió mientras preparabas la transición",
            "SEASON_TRANSITION_CONFLICT",
            409,
        )

    if not source and source_season_id:
        return error_response(
            "El ciclo de temporadas cambió; vuelve a revisar la activación",
            "SEASON_TRANSITION_CONFLICT",
            409,
        )

    if target.status != "planned":
        return error_response(
            "La temporada destino debe estar planificada",
            "SEASON_NOT_PLANNED",
            409,
        )

    if target.end_date and target.end_date < target.start_date:
        return error_response(
            "Las fechas de la temporada destino no son válidas",
            "INVALID_SEASON_DATE_RANGE",
            409,
        )

    preflight = build_season_activation_preflight(target, source)
    blocker_codes = {blocker["code"] for blocker in preflight["blockers"]}
    if "SEASON_TEAM_REQUIRED" in blocker_codes:
        return error_response(
            "Prepara al menos un equipo antes de activar la temporada",
            "SEASON_TEAM_REQUIRED",
            409,
        )

    open_activities = {
        key: preflight["summary"][key]
        for key in (
            "scheduled_trainings",
            "open_matches",
            "active_tournaments",
        )
    }
    if any(open_activities.values()):
        return jsonify({
            "error": True,
            "code": "SEASON_HAS_OPEN_ACTIVITIES",
            "message": (
                "La temporada tiene actividades deportivas abiertas que "
                "deben completarse o cancelarse antes de la transición"
            ),
            "details": open_activities,
        }), 409

    if "TARGET_ROSTER_INVALID" in blocker_codes:
        return jsonify({
            "error": True,
            "code": "TARGET_ROSTER_INVALID",
            "message": "El roster preparado contiene datos que deben corregirse",
            "details": preflight["blockers"],
        }), 409

    if source:
        source.status = "closed"
        db.session.flush()
    target.status = "active"

    try:
        finish_club_onboarding_if_complete(target.club)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()

        if not violates_named_constraint(error, ACTIVE_SEASON_CONSTRAINTS):
            raise

        return error_response(
            "No se pudo completar la transición de temporada",
            "SEASON_TRANSITION_CONFLICT",
            409,
        )

    return jsonify({
        "message": "Nueva temporada activada correctamente",
        "mode": "transition" if source else "recovery",
        "source_season": _season_payload(source) if source else None,
        "target_season": _season_payload(target),
    }), 200
