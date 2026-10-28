from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import db, Team, TrainingAuditEvent, TrainingSession
from src.api.training_audit_service import (
    TRAINING_AUDIT_ACTIONS,
    add_training_audit_event,
    get_club_training,
    validate_correction_reason,
)
from src.api.training_service import (
    TrainingRosterFrozenError,
    sync_training_roster,
)
from src.api.utils import error_response, get_current_user


TRAINING_METADATA_FIELDS = {
    "date",
    "start_time",
    "end_time",
    "location",
}


def _validate_training_metadata(values):
    date = values.get("date")
    start_time = values.get("start_time")
    end_time = values.get("end_time")
    location = values.get("location")

    if not date:
        return None, (
            "La fecha del entrenamiento es obligatoria",
            "TRAINING_DATE_REQUIRED",
            400
        )

    if not start_time:
        return None, (
            "La hora de inicio es obligatoria",
            "TRAINING_START_TIME_REQUIRED",
            400
        )

    if not end_time:
        return None, (
            "La hora de finalización es obligatoria",
            "TRAINING_END_TIME_REQUIRED",
            400
        )

    if not location or not str(location).strip():
        return None, (
            "La ubicación del entrenamiento es obligatoria",
            "TRAINING_LOCATION_REQUIRED",
            400
        )

    try:
        parsed_date = datetime.strptime(str(date), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, (
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )

    try:
        parsed_start_time = datetime.strptime(
            str(start_time),
            "%H:%M"
        ).time()
        parsed_end_time = datetime.strptime(
            str(end_time),
            "%H:%M"
        ).time()
    except (ValueError, TypeError):
        return None, (
            "Formato de hora inválido. Usa HH:MM",
            "INVALID_TIME_FORMAT",
            400
        )

    if parsed_end_time <= parsed_start_time:
        return None, (
            "La hora de finalización debe ser posterior a la hora de inicio",
            "INVALID_TRAINING_TIME_RANGE",
            400
        )

    return {
        "date": parsed_date,
        "start_time": parsed_start_time,
        "end_time": parsed_end_time,
        "location": str(location).strip(),
    }, None


def _serialize_training_detail(training):
    team = training.team

    return {
        **training.serialize(),
        "team_name": team.name,
        "team_gender": team.gender,
        "category_id": team.category_id,
        "category_name": (
            team.category.name
            if team.category
            else None
        )
    }


def _audit_value(field, value):
    if value is None:
        return None

    if field == "date":
        return value.isoformat()

    if field in ["start_time", "end_time"]:
        return value.strftime("%H:%M")

    return value


def _transition_training_status(training_id, target_status):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para cambiar el estado del entrenamiento",
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

    if training.status == target_status:
        return jsonify({
            "message": "El entrenamiento ya tenía este estado",
            "training": training.serialize()
        }), 200

    if training.status != "scheduled":
        current_status = (
            "completado"
            if training.status == "completed"
            else "cancelado"
        )
        action = (
            "completarse"
            if target_status == "completed"
            else "cancelarse"
        )

        return error_response(
            (
                f"Este entrenamiento ya fue {current_status} "
                f"y no puede {action}."
            ),
            "INVALID_TRAINING_STATUS",
            409
        )

    updated_count = TrainingSession.query.filter_by(
        id=training.id,
        status="scheduled"
    ).update(
        {"status": target_status},
        synchronize_session=False
    )

    if updated_count != 1:
        db.session.rollback()
        training = TrainingSession.query.get(training_id)

        if training and training.status == target_status:
            return jsonify({
                "message": "El entrenamiento ya tenía este estado",
                "training": training.serialize()
            }), 200

        return error_response(
            "El estado del entrenamiento cambió y la transición ya no es válida.",
            "INVALID_TRAINING_STATUS",
            409
        )

    db.session.commit()
    training = TrainingSession.query.get(training_id)

    message = (
        "Entrenamiento completado correctamente"
        if target_status == "completed"
        else "Entrenamiento cancelado correctamente"
    )

    return jsonify({
        "message": message,
        "training": training.serialize()
    }), 200


@api.route("/trainings", methods=["POST"])
@jwt_required()
def create_training():

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    team_id = body.get("team_id")
    date = body.get("date")
    start_time = body.get("start_time")
    end_time = body.get("end_time")
    location = body.get("location")

    # ✅ VALIDACIONES VAN AQUÍ
    if not team_id:
        return error_response(
            "La categoría es obligatoria",
            "TEAM_ID_REQUIRED",
            400
        )

    if not date:
        return error_response(
            "La fecha del entrenamiento es obligatoria",
            "TRAINING_DATE_REQUIRED",
            400
        )

    if not start_time:
        return error_response(
            "La hora de inicio es obligatoria",
            "TRAINING_START_TIME_REQUIRED",
            400
        )

    if not end_time:
        return error_response(
            "La hora de finalización es obligatoria",
            "TRAINING_END_TIME_REQUIRED",
            400
        )

    if not location or not str(location).strip():
        return error_response(
            "La ubicación del entrenamiento es obligatoria",
            "TRAINING_LOCATION_REQUIRED",
            400
        )

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )

    try:
        parsed_start_time = datetime.strptime(
            start_time,
            "%H:%M"
        ).time()

        parsed_end_time = datetime.strptime(
            end_time,
            "%H:%M"
        ).time()

    except (ValueError, TypeError):
        return error_response(
            "Formato de hora inválido. Usa HH:MM",
            "INVALID_TIME_FORMAT",
            400
        )

    if parsed_end_time <= parsed_start_time:
        return error_response(
            "La hora de finalización debe ser posterior a la hora de inicio",
            "INVALID_TRAINING_TIME_RANGE",
            400
        )

    location = location.strip()

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    training = TrainingSession(
        team_id=team.id,
        date=parsed_date,
        start_time=parsed_start_time,
        end_time=parsed_end_time,
        location=location,
        status="scheduled",
        created_by=user.id
    )

    db.session.add(training)
    db.session.flush()

    sync_result = sync_training_roster(training)

    if sync_result["total_players"] == 0:
        db.session.rollback()

        return error_response(
            "El equipo debe tener al menos un deportista para crear un entrenamiento",
            "TEAM_HAS_NO_PLAYERS",
            409
        )

    db.session.commit()

    return jsonify({
        "message": "Entrenamiento creado",
        "training": training.serialize()
    }), 201


@api.route(
    "/trainings/<string:training_id>/complete",
    methods=["PUT"]
)
@jwt_required()
def complete_training(training_id):
    return _transition_training_status(
        training_id,
        "completed"
    )


@api.route(
    "/trainings/<string:training_id>/cancel",
    methods=["PUT"]
)
@jwt_required()
def cancel_training(training_id):
    return _transition_training_status(
        training_id,
        "cancelled"
    )


@api.route(
    "/trainings/<string:training_id>/sync-roster",
    methods=["PUT"]
)
@jwt_required()
def sync_training_session_roster(training_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para actualizar participantes",
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

    try:
        sync_result = sync_training_roster(training)
    except TrainingRosterFrozenError:
        return error_response(
            "Los participantes de este entrenamiento ya no pueden modificarse.",
            "TRAINING_ROSTER_FROZEN",
            409
        )

    db.session.commit()

    return jsonify({
        "message": (
            "Participantes actualizados: "
            f"{sync_result['added_count']} agregados, "
            f"{sync_result['removed_count']} retirados"
        ),
        "training": training.serialize(),
        "sync": sync_result
    }), 200

@api.route("/trainings/<string:training_id>", methods=["GET"])
@jwt_required()
def get_training_detail(training_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
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
            "No tienes acceso a este entrenamiento",
            "FORBIDDEN",
            403
        )

    return jsonify({
        "training": {
            **training.serialize(),
            "team_name": team.name,
            "team_gender": team.gender,
            "category_id": team.category_id,
            "category_name": (
                team.category.name
                if team.category
                else None
            )
        }
    }), 200

@api.route("/trainings/<string:training_id>", methods=["PUT"])
@jwt_required()
def update_training(training_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para editar entrenamientos",
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

    if training.status != "scheduled":
        return error_response(
            "Este entrenamiento está cerrado y solo admite correcciones históricas.",
            "TRAINING_LOCKED",
            409
        )

    body = request.get_json(silent=True) or {}

    if not isinstance(body, dict):
        return error_response(
            "La información del entrenamiento es inválida",
            "INVALID_TRAINING_CORRECTION_FIELDS",
            400
        )

    parsed_values, validation_error = _validate_training_metadata(body)

    if validation_error:
        return error_response(*validation_error)

    training.date = parsed_values["date"]
    training.start_time = parsed_values["start_time"]
    training.end_time = parsed_values["end_time"]
    training.location = parsed_values["location"]

    db.session.commit()

    return jsonify({
        "message": "Entrenamiento actualizado correctamente",
        "training": _serialize_training_detail(training)
    }), 200


@api.route(
    "/trainings/<string:training_id>/corrections/metadata",
    methods=["POST"]
)
@jwt_required()
def correct_training_metadata(training_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para corregir entrenamientos",
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

    if training.status not in ["completed", "cancelled"]:
        return error_response(
            "Este entrenamiento no requiere una corrección histórica.",
            "INVALID_TRAINING_STATUS",
            409
        )

    body = request.get_json(silent=True) or {}

    if not isinstance(body, dict):
        return error_response(
            "Los cambios de la corrección son inválidos",
            "INVALID_TRAINING_CORRECTION_FIELDS",
            400
        )

    reason, reason_error = validate_correction_reason(body.get("reason"))

    if reason_error:
        return error_response(*reason_error)

    proposed_changes = body.get("changes")

    if not isinstance(proposed_changes, dict):
        return error_response(
            "Los cambios de la corrección son inválidos",
            "INVALID_TRAINING_CORRECTION_FIELDS",
            400
        )

    unknown_fields = set(proposed_changes) - TRAINING_METADATA_FIELDS

    if unknown_fields:
        return error_response(
            "La corrección contiene campos no permitidos",
            "INVALID_TRAINING_CORRECTION_FIELDS",
            400
        )

    current_values = {
        "date": training.date.isoformat() if training.date else None,
        "start_time": (
            training.start_time.strftime("%H:%M")
            if training.start_time
            else None
        ),
        "end_time": (
            training.end_time.strftime("%H:%M")
            if training.end_time
            else None
        ),
        "location": training.location,
    }
    final_values = {
        **current_values,
        **proposed_changes,
    }
    parsed_values, validation_error = _validate_training_metadata(
        final_values
    )

    if validation_error:
        return error_response(*validation_error)

    differences = {}

    for field in TRAINING_METADATA_FIELDS:
        old_value = getattr(training, field)
        new_value = parsed_values[field]

        if old_value != new_value:
            differences[field] = {
                "from": _audit_value(field, old_value),
                "to": _audit_value(field, new_value),
            }

    if not differences:
        return error_response(
            "La corrección no contiene cambios reales",
            "CORRECTION_NO_CHANGES",
            400
        )

    for field in differences:
        setattr(training, field, parsed_values[field])

    audit_event = add_training_audit_event(
        training,
        user,
        TRAINING_AUDIT_ACTIONS["metadata"],
        differences,
        reason
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return error_response(
            "No se pudo guardar la corrección",
            "TRAINING_CORRECTION_FAILED",
            500
        )

    return jsonify({
        "message": "Información histórica corregida correctamente",
        "training": _serialize_training_detail(training),
        "audit_event": audit_event.serialize()
    }), 200


@api.route(
    "/trainings/<string:training_id>/reactivate",
    methods=["POST"]
)
@jwt_required()
def reactivate_training(training_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para reactivar entrenamientos",
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

    if training.status != "cancelled":
        return error_response(
            "Solo un entrenamiento cancelado puede reactivarse.",
            "INVALID_TRAINING_STATUS",
            409
        )

    body = request.get_json(silent=True) or {}

    if not isinstance(body, dict):
        return error_response(
            "El motivo de reactivación es inválido",
            "CORRECTION_REASON_REQUIRED",
            400
        )

    reason, reason_error = validate_correction_reason(body.get("reason"))

    if reason_error:
        return error_response(*reason_error)

    changes = {
        "status": {
            "from": "cancelled",
            "to": "scheduled",
        }
    }
    training.status = "scheduled"
    audit_event = add_training_audit_event(
        training,
        user,
        TRAINING_AUDIT_ACTIONS["reactivated"],
        changes,
        reason
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return error_response(
            "No se pudo reactivar el entrenamiento",
            "TRAINING_REACTIVATION_FAILED",
            500
        )

    return jsonify({
        "message": "Entrenamiento reactivado correctamente",
        "training": _serialize_training_detail(training),
        "audit_event": audit_event.serialize()
    }), 200


@api.route(
    "/trainings/<string:training_id>/audit",
    methods=["GET"]
)
@jwt_required()
def get_training_audit(training_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver este historial",
            "FORBIDDEN",
            403
        )

    training = get_club_training(training_id, user.club_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    events = TrainingAuditEvent.query.filter_by(
        training_id=training.id,
        club_id=user.club_id
    ).order_by(
        TrainingAuditEvent.created_at.desc(),
        TrainingAuditEvent.id.desc()
    ).all()

    return jsonify({
        "audit_events": [event.serialize() for event in events]
    }), 200

@api.route("/teams/<string:team_id>/trainings", methods=["GET"])
@jwt_required()
def get_team_trainings(team_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
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

    # Seguridad multi-tenant
    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    trainings = TrainingSession.query.filter_by(team_id=team.id)\
        .order_by(TrainingSession.date.desc())\
        .all()

    return jsonify({
        "team": team.serialize(),
        "total_trainings": len(trainings),
        "trainings": [t.serialize() for t in trainings]
    }), 200

@api.route("/trainings", methods=["GET"])
@jwt_required()
def get_all_trainings():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
            "FORBIDDEN",
            403
        )

    trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == user.club_id
    ).order_by(TrainingSession.date.desc()).all()

    return jsonify({
        "total_trainings": len(trainings),
        "trainings": [
        {
            **t.serialize(),
            "team_name": t.team.name
        }
        for t in trainings
    ]
    }), 200
