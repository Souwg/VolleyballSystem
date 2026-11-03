from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from src.api.api_blueprint import api
from src.api.models import db, Team, TeamCoachAssignment, User
from src.api.season_service import (
    get_team_membership_operation_error,
    lock_team_lifecycle,
)
from src.api.utils import error_response, get_current_user


def _owner_team_or_error(team_id):
    user = get_current_user()

    if user.role != "club_owner":
        return None, None, error_response(
            "Solo el dueño del club puede gestionar los entrenadores del equipo",
            "FORBIDDEN",
            403,
        )

    team = db.session.get(Team, team_id)

    if not team or team.club_id != user.club_id:
        return None, None, error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404,
        )

    return user, team, None


def _lock_team_lifecycle(team_id, club_id):
    # Orden fijo Team -> Season -> User. archive_team solo toma la fila del Team,
    # transition_season las de Season y los cambios de usuario la del User, así
    # que no hay ciclo posible. La FK de la asignación no basta: su FOR KEY SHARE
    # no choca con esos UPDATE.
    return lock_team_lifecycle(team_id, club_id, exclusive=True)


def _lock_coach(user_id, club_id):
    return User.query.filter_by(
        id=user_id,
        club_id=club_id,
    ).populate_existing().with_for_update(read=True).first()


def _open_assignment(team_id, user_id):
    return TeamCoachAssignment.query.filter_by(
        team_id=team_id,
        user_id=user_id,
        removed_at=None,
    )


def _assignment_response(assignment, message, status):
    return jsonify({
        "message": message,
        "assignment": assignment.serialize(),
    }), status


@api.route("/teams/<string:team_id>/coaches", methods=["GET"])
@jwt_required()
def get_team_coaches(team_id):
    _, team, error = _owner_team_or_error(team_id)

    if error:
        return error

    assignments = TeamCoachAssignment.query.filter_by(
        team_id=team.id,
        club_id=team.club_id,
        removed_at=None,
    ).order_by(TeamCoachAssignment.assigned_at.asc()).all()

    return jsonify({
        "team": {
            "id": team.id,
            "name": team.name,
            "status": team.status,
            "season_id": team.season_id,
        },
        "coaches": [
            {
                "assignment_id": assignment.id,
                "user_id": assignment.user_id,
                "full_name": assignment.user.full_name,
                "email": assignment.user.email,
                "role": assignment.user.role,
                "is_active": assignment.user.is_active,
                "assigned_at": assignment.assigned_at.isoformat(),
                "assigned_by": assignment.assigned_by,
                "removed_at": None,
            }
            for assignment in assignments
        ],
    }), 200


@api.route("/teams/<string:team_id>/coaches", methods=["POST"])
@jwt_required()
def assign_team_coach(team_id):
    user, team, error = _owner_team_or_error(team_id)

    if error:
        return error

    body = request.get_json(silent=True)
    coach_id = body.get("user_id") if isinstance(body, dict) else None

    if not isinstance(coach_id, str) or not coach_id.strip():
        return error_response(
            "El entrenador es obligatorio",
            "COACH_ID_REQUIRED",
            400,
        )

    team = _lock_team_lifecycle(team.id, user.club_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404,
        )

    coach = _lock_coach(coach_id.strip(), user.club_id)

    if not coach:
        return error_response(
            "Entrenador no encontrado",
            "COACH_NOT_FOUND",
            404,
        )

    if coach.role != "coach":
        return error_response(
            "Solo un usuario con rol de entrenador puede asignarse a un equipo",
            "USER_NOT_COACH",
            409,
        )

    if not coach.is_active:
        return error_response(
            "No puedes asignar un entrenador con la cuenta desactivada",
            "COACH_INACTIVE",
            409,
        )

    team_error = get_team_membership_operation_error(team)

    if team_error:
        return error_response(*team_error)

    existing = _open_assignment(team.id, coach.id).first()

    if existing:
        return _assignment_response(
            existing,
            "El entrenador ya estaba asignado a este equipo",
            200,
        )

    assignment = TeamCoachAssignment(
        club_id=team.club_id,
        team_id=team.id,
        user_id=coach.id,
        assigned_by=user.id,
    )
    db.session.add(assignment)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = _open_assignment(team_id, coach_id.strip()).first()

        if existing:
            return _assignment_response(
                existing,
                "El entrenador ya estaba asignado a este equipo",
                200,
            )

        return error_response(
            "No se pudo asignar el entrenador al equipo",
            "COACH_ASSIGNMENT_CONFLICT",
            409,
        )

    return _assignment_response(
        assignment,
        "Entrenador asignado correctamente",
        201,
    )


@api.route("/teams/<string:team_id>/coaches/<string:user_id>", methods=["DELETE"])
@jwt_required()
def remove_team_coach(team_id, user_id):
    _, team, error = _owner_team_or_error(team_id)

    if error:
        return error

    assignment = _open_assignment(
        team.id,
        user_id,
    ).with_for_update().first()

    if not assignment:
        return jsonify({
            "message": "El entrenador no estaba asignado a este equipo",
            "removed": False,
        }), 200

    assignment.removed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "Entrenador retirado del equipo",
        "removed": True,
    }), 200
