from flask import jsonify, request
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import (
    db,
    Attendance,
    Player,
    Team,
    TeamPlayer,
    TrainingPlayer,
    TrainingSession,
)
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

    memberships = TeamPlayer.query.filter_by(
        player_id=player.id
    ).all()

    if player.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )


    for membership in memberships:
        team = Team.query.get(membership.team_id)

        if not team or team.club_id != user.club_id:
            return error_response(
                "No tienes acceso",
                "FORBIDDEN",
                403
            )

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
            **player.serialize(),
            "teams": [
                {
                    "id": m.team.id,
                    "name": m.team.name,
                    "gender": m.team.gender,
                    "category_id": m.team.category_id,
                    "category_name": m.team.category.name if m.team.category else None,
                    "player_number": m.player_number,
                    "status": m.status
                }
                for m in memberships
            ]
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
