from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from src.api.api_blueprint import api
from src.api.models import db, Player, Season, Team, TeamPlayer
from src.api.season_service import get_season_open_activities
from src.api.utils import error_response, get_current_user


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


def _season_payload(season, include_teams=False):
    data = season.serialize()
    teams = Team.query.filter_by(
        club_id=season.club_id,
        season_id=season.id,
    ).order_by(Team.name).all()
    data["total_teams"] = len(teams)
    data["active_teams"] = sum(team.status == "active" for team in teams)

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

    body = request.get_json() or {}
    name = " ".join(str(body.get("name") or "").strip().split())

    if not name:
        return error_response(
            "El nombre de la temporada es obligatorio",
            "SEASON_NAME_REQUIRED",
            400,
        )

    try:
        start_date = datetime.strptime(
            str(body.get("start_date") or ""), "%Y-%m-%d"
        ).date()
    except ValueError:
        return error_response(
            "La fecha de inicio debe usar el formato YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400,
        )

    end_date = None
    if body.get("end_date"):
        try:
            end_date = datetime.strptime(
                str(body["end_date"]), "%Y-%m-%d"
            ).date()
        except ValueError:
            return error_response(
                "La fecha de finalización debe usar el formato YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400,
            )

    if end_date and end_date < start_date:
        return error_response(
            "La fecha de finalización no puede ser anterior al inicio",
            "INVALID_SEASON_DATE_RANGE",
            400,
        )

    season = Season(
        club_id=user.club_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        status="planned",
        created_by=user.id,
    )
    db.session.add(season)
    db.session.commit()

    return jsonify({
        "message": "Temporada planificada creada correctamente",
        "season": _season_payload(season),
    }), 201


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

    target, target_error = _club_season_or_error(target_season_id, user)

    if target_error:
        return target_error

    if target.status != "planned":
        return error_response(
            "La temporada destino debe estar planificada",
            "SEASON_NOT_PLANNED",
            409,
        )

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

    source, source_error = _club_season_or_error(source_id, user)

    if source_error:
        return source_error

    normalized_ids = list(dict.fromkeys(str(team_id) for team_id in team_ids))
    source_teams = Team.query.filter(
        Team.club_id == user.club_id,
        Team.season_id == source.id,
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
    except IntegrityError:
        db.session.rollback()
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

    if not source_team_id:
        return error_response(
            "El equipo de origen es obligatorio",
            "SOURCE_TEAM_REQUIRED",
            400,
        )

    if not isinstance(player_ids, list) or not player_ids:
        return error_response(
            "Selecciona al menos una jugadora",
            "PLAYER_SELECTION_REQUIRED",
            400,
        )

    source = db.session.get(Team, source_team_id)

    if not source or source.club_id != user.club_id:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    normalized_ids = list(dict.fromkeys(str(player_id) for player_id in player_ids))
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

    source_numbers = [membership.player_number for membership in source_memberships]
    occupied_number = TeamPlayer.query.filter(
        TeamPlayer.team_id == target.id,
        TeamPlayer.left_at.is_(None),
        TeamPlayer.player_number.in_(source_numbers),
    ).first()

    if occupied_number or len(source_numbers) != len(set(source_numbers)):
        return error_response(
            "Uno de los números seleccionados ya está ocupado en el equipo destino",
            "PLAYER_NUMBER_DUPLICATED",
            409,
        )

    memberships = [
        TeamPlayer(
            team_id=target.id,
            player_id=membership.player_id,
            player_number=membership.player_number,
            status="active",
        )
        for membership in source_memberships
    ]
    db.session.add_all(memberships)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(
            "El roster destino cambió mientras se preparaba la copia",
            "ROSTER_COPY_CONFLICT",
            409,
        )

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

    source_season_id = (request.get_json() or {}).get("source_season_id")

    if not source_season_id:
        return error_response(
            "La temporada activa de origen es obligatoria",
            "SOURCE_SEASON_REQUIRED",
            400,
        )

    seasons = Season.query.filter_by(club_id=user.club_id).with_for_update().all()
    by_id = {season.id: season for season in seasons}
    source = by_id.get(source_season_id)
    target = by_id.get(target_season_id)

    if not source or not target:
        return error_response(
            "Temporada no encontrada",
            "SEASON_NOT_FOUND",
            404,
        )

    if source.id == target.id or source.status != "active":
        return error_response(
            "La temporada de origen debe ser la temporada activa actual",
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

    if not Team.query.filter_by(
        club_id=user.club_id,
        season_id=target.id,
        status="active",
    ).first():
        return error_response(
            "Prepara al menos un equipo antes de activar la temporada",
            "SEASON_TEAM_REQUIRED",
            409,
        )

    open_activities = get_season_open_activities(source)
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

    source.status = "closed"
    db.session.flush()
    target.status = "active"

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(
            "No se pudo completar la transición de temporada",
            "SEASON_TRANSITION_CONFLICT",
            409,
        )

    return jsonify({
        "message": "Nueva temporada activada correctamente",
        "source_season": _season_payload(source),
        "target_season": _season_payload(target),
    }), 200
