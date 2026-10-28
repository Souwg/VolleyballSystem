from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from src.api.api_blueprint import api
from src.api.models import db, Category, Team, TeamPlayer
from src.api.utils import error_response, get_current_user


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

    name = body.get("name")
    description = body.get("description")

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

    db.session.add(category)
    db.session.commit()

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

    result = []

    for category in categories:
        teams = Team.query.filter_by(
            category_id=category.id,
            club_id=user.club_id
        ).all()

        team_ids = [team.id for team in teams]

        total_players = 0

        if team_ids:
            total_players = TeamPlayer.query.filter(
                TeamPlayer.team_id.in_(team_ids)
            ).count()

        result.append({
            **category.serialize(),
            "total_teams": len(teams),
            "total_players": total_players
        })

    return jsonify({
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

    teams = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id
    ).order_by(Team.name).all()

    serialized_teams = []

    for team in teams:
        total_players = TeamPlayer.query.filter_by(team_id=team.id).count()

        serialized_teams.append({
            **team.serialize(),
            "total_players": total_players
        })

    return jsonify({
        "category": category.serialize(),
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

    name = body.get("name")
    description = body.get("description")

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

    db.session.commit()

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

    teams = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id
    ).order_by(Team.name).all()

    serialized_teams = []

    for team in teams:
        total_players = TeamPlayer.query.filter_by(team_id=team.id).count()

        serialized_teams.append({
            **team.serialize(),
            "total_players": total_players
        })

    return jsonify({
        "category": category.serialize(),
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

    teams_count = Team.query.filter_by(category_id=category.id).count()

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
