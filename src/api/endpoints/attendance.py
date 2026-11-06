from flask import jsonify, request
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.coach_access import (
    can_edit_player_profile,
    get_team_access_resolver,
    get_team_assignment_error,
    is_current_membership,
    serialize_player_for_user,
)
from src.api.models import (
    db,
    Attendance,
    Player,
    Team,
    TeamPlayer,
    TrainingPlayer,
    TrainingSession,
)
from src.api.request_validation import InputValidationError
from src.api.season_service import get_team_operation_error
from src.api.training_audit_service import (
    TRAINING_AUDIT_ACTIONS,
    add_training_audit_event,
    get_club_training,
    validate_correction_reason,
)
from src.api.utils import error_response, get_current_user


@api.route("/trainings/<string:training_id>/attendance", methods=["POST"])
@jwt_required()
def save_attendance(training_id):

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para registrar asistencia",
            "FORBIDDEN",
            403
        )

    training = (
        TrainingSession.query
        .filter_by(id=training_id)
        .with_for_update()
        .first()
    )

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este entrenamiento",
            "FORBIDDEN",
            403
        )

    assignment_error = get_team_assignment_error(user, team)

    if assignment_error:
        return error_response(*assignment_error)

    team_error = get_team_operation_error(team)

    if team_error:
        return error_response(*team_error)

    if training.status == "cancelled":
        return error_response(
            "No puedes registrar asistencia en un entrenamiento cancelado",
            "TRAINING_CANCELLED",
            409
        )

    if training.status == "completed":
        return error_response(
            "Este entrenamiento está cerrado y solo admite correcciones históricas.",
            "TRAINING_LOCKED",
            409
        )

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return error_response(
            "Formato de asistencia inválido",
            "INVALID_ATTENDANCE_FORMAT",
            400
        )
    attendance_list = body.get("attendance")

    if attendance_list is None or attendance_list == []:
        return error_response(
            "Lista de asistencia requerida",
            "ATTENDANCE_REQUIRED",
            400
        )

    if not isinstance(attendance_list, list):
        return error_response(
            "Formato de asistencia inválido",
            "INVALID_ATTENDANCE_FORMAT",
            400
        )

    allowed_player_ids = {
        player_id for (player_id,) in db.session.query(TrainingPlayer.player_id)
        .join(Player, TrainingPlayer.player_id == Player.id)
        .filter(
            TrainingPlayer.training_id == training.id,
            Player.club_id == user.club_id
        ).all()
    }

    allowed_status = ["present", "late", "absent"]
    received_player_ids = set()
    validated_attendance = []

    for item in attendance_list:
        if not isinstance(item, dict):
            return error_response(
                "Formato de asistencia inválido",
                "INVALID_ATTENDANCE_FORMAT",
                400
            )

        player_id = item.get("player_id")
        status = item.get("status", "present")

        if not player_id:
            return error_response(
                "Identificador de jugador requerido",
                "PLAYER_ID_REQUIRED",
                400
            )

        if not isinstance(player_id, str) or player_id not in allowed_player_ids:
            return error_response(
                "Uno de los jugadores no pertenece a este entrenamiento",
                "PLAYER_NOT_IN_TRAINING",
                403
            )

        if player_id in received_player_ids:
            return error_response(
                "No puedes registrar dos veces al mismo jugador",
                "DUPLICATE_ATTENDANCE_PLAYER",
                400
            )

        if status not in allowed_status:
            return error_response(
                "Estado de asistencia inválido",
                "INVALID_ATTENDANCE_STATUS",
                400
            )

        received_player_ids.add(player_id)
        validated_attendance.append(Attendance(
            session_id=training.id,
            player_id=player_id,
            status=status
        ))

    try:
        Attendance.query.filter_by(session_id=training.id).delete()
        db.session.add_all(validated_attendance)
        db.session.commit()
    except InputValidationError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        return error_response(
            "No se pudo guardar la asistencia",
            "ATTENDANCE_SAVE_FAILED",
            500
        )

    return jsonify({
        "message": "Asistencia guardada correctamente"
    }), 200


@api.route(
    "/trainings/<string:training_id>/corrections/attendance",
    methods=["POST"]
)
@jwt_required()
def correct_training_attendance(training_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para corregir asistencia",
            "FORBIDDEN",
            403
        )

    training = get_club_training(
        training_id,
        user.club_id,
        lock=True
    )

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    assignment_error = get_team_assignment_error(user, training.team)

    if assignment_error:
        return error_response(*assignment_error)

    # Excepción deliberada al guard de get_team_operation_error: la corrección
    # exige motivo y queda auditada, por lo que sigue disponible con el equipo
    # archivado o la temporada cerrada. Las mutaciones normales no pasan por aquí.
    if training.status != "completed":
        return error_response(
            "La asistencia histórica solo puede corregirse en un entrenamiento completado.",
            "INVALID_TRAINING_STATUS",
            409
        )

    body = request.get_json(silent=True) or {}

    if not isinstance(body, dict):
        return error_response(
            "Formato de asistencia inválido",
            "INVALID_ATTENDANCE_FORMAT",
            400
        )

    reason, reason_error = validate_correction_reason(body.get("reason"))

    if reason_error:
        return error_response(*reason_error)

    attendance_list = body.get("attendance")

    if not isinstance(attendance_list, list) or not attendance_list:
        return error_response(
            "Lista de asistencia requerida",
            "ATTENDANCE_REQUIRED",
            400
        )

    snapshot_rows = (
        TrainingPlayer.query
        .join(Player, Player.id == TrainingPlayer.player_id)
        .filter(
            TrainingPlayer.training_id == training.id,
            Player.club_id == user.club_id
        )
        .all()
    )
    snapshot_by_player_id = {
        row.player_id: row
        for row in snapshot_rows
    }
    allowed_statuses = ["present", "late", "absent"]
    received_player_ids = set()
    proposed_statuses = {}

    for item in attendance_list:
        if not isinstance(item, dict):
            return error_response(
                "Formato de asistencia inválido",
                "INVALID_ATTENDANCE_FORMAT",
                400
            )

        player_id = item.get("player_id")
        status = item.get("status")

        if not isinstance(player_id, str) or not player_id:
            return error_response(
                "Identificador de jugador requerido",
                "PLAYER_ID_REQUIRED",
                400
            )

        if player_id in received_player_ids:
            return error_response(
                "No puedes corregir dos veces al mismo jugador",
                "DUPLICATE_ATTENDANCE_PLAYER",
                400
            )

        if player_id not in snapshot_by_player_id:
            return error_response(
                "Uno de los jugadores no pertenece al historial de este entrenamiento",
                "PLAYER_NOT_IN_TRAINING",
                403
            )

        if status not in allowed_statuses:
            return error_response(
                "Estado de asistencia inválido",
                "INVALID_ATTENDANCE_STATUS",
                400
            )

        received_player_ids.add(player_id)
        proposed_statuses[player_id] = status

    existing_rows = Attendance.query.filter(
        Attendance.session_id == training.id,
        Attendance.player_id.in_(received_player_ids)
    ).all()
    existing_by_player_id = {
        row.player_id: row
        for row in existing_rows
    }
    differences = []

    for player_id, new_status in proposed_statuses.items():
        current_row = existing_by_player_id.get(player_id)
        old_status = current_row.status if current_row else None

        if old_status == new_status:
            continue

        snapshot = snapshot_by_player_id[player_id]
        player_name = " ".join(
            part
            for part in [
                snapshot.player.first_name,
                snapshot.player.last_name,
            ]
            if part
        )
        differences.append({
            "player_id": player_id,
            "player_name": player_name,
            "from": old_status,
            "to": new_status,
        })

    if not differences:
        return error_response(
            "La corrección no contiene cambios reales",
            "CORRECTION_NO_CHANGES",
            400
        )

    for change in differences:
        row = existing_by_player_id.get(change["player_id"])

        if row:
            row.status = change["to"]
        else:
            db.session.add(Attendance(
                session_id=training.id,
                player_id=change["player_id"],
                status=change["to"]
            ))

    audit_event = add_training_audit_event(
        training,
        user,
        TRAINING_AUDIT_ACTIONS["attendance"],
        {"players": differences},
        reason
    )

    try:
        db.session.commit()
    except InputValidationError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        return error_response(
            "No se pudo guardar la corrección de asistencia",
            "TRAINING_CORRECTION_FAILED",
            500
        )

    return jsonify({
        "message": "Asistencia histórica corregida correctamente",
        "attendance": [
            row.serialize()
            for row in Attendance.query.filter_by(
                session_id=training.id
            ).all()
        ],
        "audit_event": audit_event.serialize()
    }), 200

@api.route("/trainings/<string:training_id>/attendance", methods=["GET"])
@jwt_required()
def get_attendance(training_id):

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar asistencia",
            "FORBIDDEN",
            403
        )

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    allowed_player_ids = {
        player_id for (player_id,) in db.session.query(TrainingPlayer.player_id)
        .join(Player, TrainingPlayer.player_id == Player.id)
        .filter(
            TrainingPlayer.training_id == training.id,
            Player.club_id == user.club_id
        ).all()
    }

    attendance = Attendance.query.filter(
        Attendance.session_id == training.id,
        Attendance.player_id.in_(allowed_player_ids)
    ).all()

    return jsonify({
        "attendance": [a.serialize() for a in attendance]
    }), 200

@api.route("/trainings/<string:training_id>/players", methods=["GET"])
@jwt_required()
def get_training_players(training_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar entrenamientos",
            "FORBIDDEN",
            403
        )

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    snapshot = TrainingPlayer.query.filter_by(
        training_id=training.id
    ).order_by(TrainingPlayer.player_number).all()

    players = []

    for row in snapshot:
        if not row.player:
            continue

        players.append({
            "id": row.player.id,
            "first_name": row.player.first_name,
            "last_name": row.player.last_name,
            "player_number": row.player_number,
            "sex": row.player.sex
        })

    return jsonify({
        "players": players
    }), 200

@api.route("/players/<string:player_id>/attendance", methods=["GET"])
@jwt_required()
def get_player_attendance(player_id):

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para consultar asistencia",
            "FORBIDDEN",
            403
        )

    player = Player.query.get(player_id)

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    memberships = TeamPlayer.query.join(Team).filter(
        TeamPlayer.player_id == player.id,
        Team.club_id == user.club_id,
    ).order_by(
        TeamPlayer.joined_at.desc(),
        TeamPlayer.id.desc(),
    ).all()

    if player.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    team_access = get_team_access_resolver(user)

    def serialize_membership(membership):
        return {
            "id": membership.team.id,
            "name": membership.team.name,
            "gender": membership.team.gender,
            "category_id": membership.team.category_id,
            "category_name": (
                membership.team.category.name
                if membership.team.category
                else None
            ),
            "player_number": membership.player_number,
            "status": membership.status,
            "membership_id": membership.id,
            "joined_at": membership.joined_at.isoformat(),
            "left_at": (
                membership.left_at.isoformat()
                if membership.left_at
                else None
            ),
            "season_id": membership.team.season_id,
            "season_name": (
                membership.team.season.name
                if membership.team.season
                else None
            ),
            "season_status": (
                membership.team.season.status
                if membership.team.season
                else None
            ),
            "team_status": membership.team.status,
            "is_current": is_current_membership(membership),
            **team_access(membership.team),
        }

    current_memberships = [
        membership for membership in memberships
        if is_current_membership(membership)
    ]
    historical_memberships = [
        membership for membership in memberships
        if not is_current_membership(membership)
    ]

    attendance_records = Attendance.query.join(TrainingSession).join(Team).filter(
        Attendance.player_id == player.id,
        Team.club_id == user.club_id
    ).order_by(TrainingSession.date.desc()).all()

    history = []
    present = 0
    late = 0
    absent = 0

    for record in attendance_records:
        if record.status == "present":
            present += 1
        elif record.status == "late":
            late += 1
        elif record.status == "absent":
            absent += 1

        history.append({
            "training_id": record.session_id,
            "date": record.session.date.isoformat(),
            "location": record.session.location,
            "status": record.status
        })

    total = present + late + absent
    attendance_rate = (
        round(((present + late) / total) * 100)
        if total > 0
        else 0
    )

    return jsonify({
        "player": {
            **serialize_player_for_user(player, user),
            "can_edit_profile": can_edit_player_profile(user, player),
            "teams": [
                serialize_membership(membership)
                for membership in current_memberships
            ],
            "historical_teams": [
                serialize_membership(membership)
                for membership in historical_memberships
            ],
        },
        "summary": {
            "present": present,
            "late": late,
            "absent": absent,
            "total_sessions": total,
            "attendance_rate": attendance_rate
        },
        "history": history
    }), 200
