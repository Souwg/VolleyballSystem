from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError

from src.api.api_blueprint import api
from src.api.coach_access import get_team_access_resolver
from src.api.integrity_errors import violates_named_constraint
from src.api.models import db, Category, Season, Team, TeamPlayer
from src.api.request_validation import text_field
from src.api.season_service import (
    get_active_season_for_club,
    resolve_season_for_read,
)
from src.api.utils import error_response, get_current_user


CATEGORY_UNIQUE_CONSTRAINTS = {
    "unique_category_per_club",
    "uq_categories_club_lower_name",
}


def _category_usage_by_id(club_id):
    rows = db.session.query(
        Team.category_id,
        func.count(Team.id),
        func.max(case((Season.status == "closed", 1), else_=0)),
    ).join(
        Season,
        (Season.id == Team.season_id) & (Season.club_id == Team.club_id),
    ).filter(
        Team.club_id == club_id,
    ).group_by(Team.category_id).all()

    return {
        category_id: {
            "total_teams_all_seasons": total_teams,
            "has_historical_teams": bool(has_historical_teams),
            "can_delete": total_teams == 0,
        }
        for category_id, total_teams, has_historical_teams in rows
    }


def _serialize_category_with_usage(category, usage_by_id=None):
    usage = (usage_by_id or {}).get(category.id, {})
    total_teams = usage.get("total_teams_all_seasons", 0)

    return {
        **category.serialize(),
        "total_teams_all_seasons": total_teams,
        "has_historical_teams": usage.get("has_historical_teams", False),
        "can_delete": total_teams == 0,
    }


@api.route("/categories", methods=["POST"])
@jwt_required()
def create_category():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear categorías",
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

    name = text_field(body, "name")
    description = text_field(body, "description")

    if name:
        name = " ".join(name.strip().split())

    if description:
        description = " ".join(description.strip().split())

    if not name:
        return error_response(
            "Nombre de la categoría requerido",
            "CATEGORY_NAME_REQUIRED",
            400
        )

    existing_category = Category.query.filter(
        Category.club_id == user.club_id,
        func.lower(Category.name) == name.lower()
    ).first()

    if existing_category:
        return error_response(
            "Ya existe una categoría con ese nombre",
            "CATEGORY_ALREADY_EXISTS",
            409
        )

    category = Category(
        name=name,
        description=description or None,
        club_id=user.club_id
    )

    try:
        db.session.add(category)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()

        if not violates_named_constraint(
            error,
            CATEGORY_UNIQUE_CONSTRAINTS,
        ):
            raise

        return error_response(
            "Ya existe una categoría con ese nombre",
            "CATEGORY_ALREADY_EXISTS",
            409
        )

    return jsonify({
        "message": "Categoría creada correctamente",
        "category": category.serialize()
    }), 201


@api.route("/categories", methods=["GET"])
@jwt_required()
def get_categories():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar categorías",
            "FORBIDDEN",
            403
        )

    categories = Category.query.filter_by(
        club_id=user.club_id
    ).order_by(Category.name).all()
    category_usage = _category_usage_by_id(user.club_id)
    requested_season_id = request.args.get("season_id")
    explicit_season = requested_season_id is not None

    if explicit_season:
        season, season_error, _ = resolve_season_for_read(
            user.club_id,
            requested_season_id,
        )

        if season_error:
            return error_response(*season_error)
    else:
        season = get_active_season_for_club(user.club_id)

    season_id = season.id if season else None

    result = []

    for category in categories:
        teams_query = Team.query.filter_by(
            category_id=category.id,
            club_id=user.club_id,
            season_id=season_id,
        )

        if not explicit_season:
            teams_query = teams_query.filter_by(status="active")

        teams = teams_query.all()

        team_ids = [team.id for team in teams]

        total_players = 0

        if team_ids:
            memberships = TeamPlayer.query.filter(
                TeamPlayer.team_id.in_(team_ids),
            )

            if not explicit_season:
                memberships = memberships.filter(
                    TeamPlayer.left_at.is_(None)
                )

            total_players = memberships.count()

        result.append({
            **_serialize_category_with_usage(category, category_usage),
            "total_teams": len(teams),
            "total_players": total_players
        })

    return jsonify({
        "season": season.serialize() if season else None,
        "categories": result
    }), 200


@api.route("/categories/<string:category_id>", methods=["GET"])
@jwt_required()
def get_category_detail(category_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para consultar categorías",
            "FORBIDDEN",
            403
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
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    requested_season_id = request.args.get("season_id")
    explicit_season = requested_season_id is not None

    if explicit_season:
        season, season_error, _ = resolve_season_for_read(
            user.club_id,
            requested_season_id,
        )

        if season_error:
            return error_response(*season_error)
    else:
        season = get_active_season_for_club(user.club_id)

    season_id = season.id if season else None

    teams_query = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id,
        season_id=season_id,
    )

    if not explicit_season:
        teams_query = teams_query.filter_by(status="active")

    teams = teams_query.order_by(Team.name).all()

    serialized_teams = []
    team_access = get_team_access_resolver(user)

    for team in teams:
        membership_query = TeamPlayer.query.filter_by(team_id=team.id)

        if not explicit_season:
            membership_query = membership_query.filter_by(left_at=None)

        total_players = membership_query.count()

        serialized_teams.append({
            **team.serialize(),
            **team_access(team),
            "total_players": total_players
        })

    return jsonify({
        "category": _serialize_category_with_usage(
            category,
            _category_usage_by_id(user.club_id),
        ),
        "season": season.serialize() if season else None,
        "total_teams": len(serialized_teams),
        "teams": serialized_teams
    }), 200

@api.route("/categories/<string:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede editar categorías",
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
            "No tienes permisos para editar esta categoría",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    name = text_field(body, "name")
    description = text_field(body, "description")

    if name:
        name = " ".join(str(name).strip().split())

    if description is not None:
        description = " ".join(str(description).strip().split())

    if not name:
        return error_response(
            "Nombre de la categoría requerido",
            "CATEGORY_NAME_REQUIRED",
            400
        )

    existing_category = Category.query.filter(
        Category.club_id == user.club_id,
        func.lower(Category.name) == name.lower(),
        Category.id != category.id
    ).first()

    if existing_category:
        return error_response(
            "Ya existe una categoría con ese nombre",
            "CATEGORY_ALREADY_EXISTS",
            409
        )

    category.name = name
    category.description = description or None

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()

        if not violates_named_constraint(
            error,
            CATEGORY_UNIQUE_CONSTRAINTS,
        ):
            raise

        return error_response(
            "Ya existe una categoría con ese nombre",
            "CATEGORY_ALREADY_EXISTS",
            409
        )

    return jsonify({
        "message": "Categoría actualizada correctamente",
        "category": category.serialize()
    }), 200


@api.route("/categories/<string:category_id>/teams", methods=["GET"])
@jwt_required()
def get_category_teams(category_id):

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

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    requested_season_id = request.args.get("season_id")
    explicit_season = requested_season_id is not None

    if explicit_season:
        season, season_error, _ = resolve_season_for_read(
            user.club_id,
            requested_season_id,
        )

        if season_error:
            return error_response(*season_error)
    else:
        season = get_active_season_for_club(user.club_id)

    season_id = season.id if season else None

    teams_query = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id,
        season_id=season_id,
    )

    if not explicit_season:
        teams_query = teams_query.filter_by(status="active")

    teams = teams_query.order_by(Team.name).all()

    serialized_teams = []
    team_access = get_team_access_resolver(user)

    for team in teams:
        membership_query = TeamPlayer.query.filter_by(team_id=team.id)

        if not explicit_season:
            membership_query = membership_query.filter_by(left_at=None)

        total_players = membership_query.count()

        serialized_teams.append({
            **team.serialize(),
            **team_access(team),
            "total_players": total_players
        })

    return jsonify({
        "category": category.serialize(),
        "season": season.serialize() if season else None,
        "teams": serialized_teams
    }), 200


@api.route("/categories/<string:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede eliminar categorías",
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
            "No tienes permisos para eliminar esta categoría",
            "FORBIDDEN",
            403
        )

    teams_count = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id,
    ).count()

    if teams_count > 0:
        return error_response(
            "No puedes eliminar una categoría que tiene equipos",
            "CATEGORY_HAS_TEAMS",
            409
        )

    db.session.delete(category)
    db.session.commit()

    return jsonify({
        "message": "Categoría eliminada correctamente"
    }), 200
