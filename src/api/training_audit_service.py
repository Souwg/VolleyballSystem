from src.api.models import db, Team, TrainingAuditEvent, TrainingSession


TRAINING_AUDIT_ACTIONS = {
    "metadata": "training_metadata_corrected",
    "attendance": "training_attendance_corrected",
    "reactivated": "training_reactivated",
}

CORRECTION_REASON_MAX_LENGTH = 500


def get_club_training(training_id, club_id, lock=False):
    query = (
        TrainingSession.query
        .join(Team, Team.id == TrainingSession.team_id)
        .filter(
            TrainingSession.id == training_id,
            Team.club_id == club_id
        )
    )

    if lock:
        query = query.with_for_update(of=TrainingSession)

    return query.first()


def validate_correction_reason(value):
    if not isinstance(value, str) or not value.strip():
        return None, (
            "El motivo de la corrección es obligatorio",
            "CORRECTION_REASON_REQUIRED",
            400
        )

    reason = value.strip()

    if len(reason) > CORRECTION_REASON_MAX_LENGTH:
        return None, (
            "El motivo no puede superar los 500 caracteres",
            "CORRECTION_REASON_TOO_LONG",
            400
        )

    return reason, None


def add_training_audit_event(
    training,
    user,
    action,
    changes,
    reason
):
    event = TrainingAuditEvent(
        training_id=training.id,
        club_id=user.club_id,
        action=action,
        changes_json=changes,
        reason=reason,
        created_by=user.id
    )
    db.session.add(event)
    return event
