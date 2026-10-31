from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from src.api.api_blueprint import api
from src.api.models import (
    db,
    Category,
    MatchSession,
    Player,
    Season,
    Team,
    TeamPlayer,
    TournamentTeam,
    TrainingSession,
)
from src.api.season_service import (
    get_active_season_for_club,
    get_season_structure_operation_error,
    get_team_membership_operation_error,
    resolve_season_for_read,
)
from src.api.utils import error_response, get_current_user


@api.route("/categories/<string:category_id>/teams", methods=["POST"])
@jwt_required()
def create_team(category_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear equipos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes permisos para crear equipos en esta categoría",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    name = body.get("name")
    gender = body.get("gender")
    season_id = body.get("season_id")

    if name:
        name = " ".join(name.strip().split())

    if not name:
        return error_response(
            "Nombre del equipo requerido",
            "TEAM_NAME_REQUIRED",
            400
        )

    allowed_gender = ["female", "male", "mixed"]

    if gender not in allowed_gender:
        return error_response(
            "La rama es inválida",
            "INVALID_TEAM_GENDER",
            400
        )

    if season_id:
        season = db.session.get(Season, season_id)

        if not season or season.club_id != user.club_id:
            return error_response(
                "Temporada no encontrada",
                "SEASON_NOT_FOUND",
                404
            )

        if season.status != "planned":
            return error_response(
                "La temporada indicada debe estar planificada",
                "SEASON_NOT_PLANNED",
                409
            )
    else:
        season = get_active_season_for_club(user.club_id)

        if not season:
            return error_response(
                "El club no tiene una temporada activa configurada",
                "ACTIVE_SEASON_REQUIRED",
                409
            )

    existing_team = Team.query.filter(
        Team.club_id == user.club_id,
        Team.season_id == season.id,
        Team.category_id == category.id,
        Team.gender == gender,
        func.lower(Team.name) == name.lower()
    ).first()

    if existing_team:
        return error_response(
            "Ya existe este equipo en esa categoría y rama",
            "TEAM_ALREADY_EXISTS",
            409
        )

    team = Team(
        name=name,
        gender=gender,
        category_id=category.id,
        club_id=user.club_id,
        season_id=season.id
    )

    db.session.add(team)
    db.session.commit()

    return jsonify({
        "message": "Equipo creado correctamente",
        "team": team.serialize()
    }), 201


@api.route("/teams", methods=["GET"])
@jwt_required()
def get_teams():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar equipos",
            "FORBIDDEN",
            403
        )

    season, season_error, explicit_season = resolve_season_for_read(
        user.club_id,
        request.args.get("season_id"),
    )

    if season_error:
        return error_response(*season_error)

    query = Team.query.filter_by(
        club_id=user.club_id,
        season_id=season.id,
    )

    if not explicit_season:
        query = query.filter_by(status="active")

    teams = query.order_by(Team.name).all()

    return jsonify({
        "season": season.serialize(),
        "teams": [t.serialize() for t in teams]
    }), 200


@api.route("/teams/<string:team_id>", methods=["GET"])
@jwt_required()
def get_team_detail(team_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar equipos",
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

    total_players = TeamPlayer.query.filter_by(
        team_id=team.id,
        left_at=None
    ).count()

    return jsonify({
        "team": team.serialize(),
        "stats": {
            "total_players": total_players
        }
    }), 200


@api.route("/teams/<string:team_id>", methods=["PUT"])
@jwt_required()
def update_team(team_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede editar equipos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
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
            "No tienes permisos para editar este equipo",
            "FORBIDDEN",
            403
        )

    season_error = get_season_structure_operation_error(team.season)
    if season_error:
        return error_response(*season_error)

    body = request.get_json() or {}

    name = body.get("name")
    gender = body.get("gender")

    if name:
        name = " ".join(str(name).strip().split())

    if not name:
        return error_response(
            "Nombre del equipo requerido",
            "TEAM_NAME_REQUIRED",
            400
        )

    allowed_gender = ["female", "male", "mixed"]

    if gender not in allowed_gender:
        return error_response(
            "La rama es inválida",
            "INVALID_TEAM_GENDER",
            400
        )

    existing_team = Team.query.filter(
        Team.club_id == user.club_id,
        Team.season_id == team.season_id,
        Team.category_id == team.category_id,
        Team.gender == gender,
        func.lower(Team.name) == name.lower(),
        Team.id != team.id
    ).first()

    if existing_team:
        return error_response(
            "Ya existe este equipo en esa categoría y rama",
            "TEAM_ALREADY_EXISTS",
            409
        )

    if gender != team.gender and gender != "mixed":
        incompatible_player = TeamPlayer.query.join(Player).filter(
            TeamPlayer.team_id == team.id,
            TeamPlayer.left_at.is_(None),
            Player.sex != gender
        ).first()

        if incompatible_player:
            return error_response(
                "No puedes cambiar la rama porque hay deportistas incompatibles en este equipo",
                "TEAM_GENDER_HAS_PLAYERS",
                409
            )

    team.name = name
    team.gender = gender

    db.session.commit()

    return jsonify({
        "message": "Equipo actualizado correctamente",
        "team": team.serialize()
    }), 200


@api.route("/teams/<string:team_id>/archive", methods=["PUT"])
@jwt_required()
def archive_team(team_id):
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede archivar equipos",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    season_error = get_season_structure_operation_error(team.season)
    if season_error:
        return error_response(*season_error)

    team.status = "archived"
    db.session.commit()

    return jsonify({
        "message": "Equipo archivado correctamente",
        "team": team.serialize()
    }), 200


@api.route("/teams/<string:team_id>/reactivate", methods=["PUT"])
@jwt_required()
def reactivate_team(team_id):
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede reactivar equipos",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    season_error = get_season_structure_operation_error(team.season)

    if season_error:
        return error_response(*season_error)

    team.status = "active"
    db.session.commit()

    return jsonify({
        "message": "Equipo reactivado correctamente",
        "team": team.serialize()
    }), 200


@api.route("/teams/<string:team_id>", methods=["DELETE"])
@jwt_required()
def delete_team(team_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede eliminar equipos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
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
            "No tienes permisos para eliminar este equipo",
            "FORBIDDEN",
            403
        )

    season_error = get_season_structure_operation_error(team.season)
    if season_error:
        return error_response(*season_error)

    players_count = TeamPlayer.query.filter_by(team_id=team.id).count()

    if players_count > 0:
        return error_response(
            "No puedes eliminar este equipo porque tiene jugadores registrados",
            "TEAM_HAS_PLAYERS",
            409
        )

    trainings_count = TrainingSession.query.filter_by(team_id=team.id).count()

    if trainings_count > 0:
        return error_response(
            "No puedes eliminar este equipo porque tiene entrenamientos históricos",
            "TEAM_HAS_TRAININGS",
            409
        )

    if (
        MatchSession.query.filter_by(team_id=team.id).first() is not None
        or TournamentTeam.query.filter_by(team_id=team.id).first() is not None
    ):
        return error_response(
            "No puedes eliminar este equipo porque tiene historial registrado",
            "TEAM_HAS_HISTORY",
            409
        )

    try:
        db.session.delete(team)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(
            "No puedes eliminar este equipo porque tiene información vinculada",
            "TEAM_HAS_HISTORY",
            409
        )

    return jsonify({
        "message": "Equipo eliminado correctamente"
    }), 200
