from datetime import date, time
from pathlib import Path

import pytest

from src.api.models import (
    Attendance,
    TrainingPlayer,
    TrainingSession,
    db,
)
from src.api.training_service import sync_training_roster
from src.api.time_utils import get_club_today


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = ("present", "late", "absent")


def _training(
    world,
    *,
    status="scheduled",
    with_roster=True,
    training_date=date(2026, 11, 18),
):
    training = TrainingSession(
        team=world.team_a,
        date=training_date,
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha principal",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    db.session.flush()

    if with_roster:
        sync_training_roster(training)

    training.status = status
    db.session.commit()
    return training


def _roster(training):
    return TrainingPlayer.query.filter_by(training_id=training.id).all()


def _attendance_payload(rows, status="present"):
    return [
        {"player_id": row.player_id, "status": status}
        for row in rows
    ]


def _seed_attendance(training, rows, status="present"):
    db.session.add_all([
        Attendance(
            session_id=training.id,
            player_id=row.player_id,
            status=status,
        )
        for row in rows
    ])
    db.session.commit()


def test_normal_attendance_requires_and_saves_complete_snapshot(
    client, world, auth_headers
):
    training = _training(world)
    rows = _roster(training)

    response = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.coach_a),
        json={
            "roster_player_ids": [row.player_id for row in rows],
            "attendance": _attendance_payload(rows),
        },
    )

    assert response.status_code == 200
    assert len(response.get_json()["attendance"]) == len(rows)
    assert Attendance.query.filter_by(session_id=training.id).count() == len(rows)


def test_partial_attendance_is_rejected_without_erasing_previous_rows(
    client, world, auth_headers
):
    training = _training(world)
    rows = _roster(training)
    _seed_attendance(training, rows, status="late")

    response = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.owner_a),
        json={"attendance": _attendance_payload(rows[:-1])},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TRAINING_ATTENDANCE_INCOMPLETE"
    assert response.get_json()["missing_count"] == 1
    assert {
        row.status
        for row in Attendance.query.filter_by(session_id=training.id).all()
    } == {"late"}
    assert Attendance.query.filter_by(session_id=training.id).count() == len(rows)


def test_loaded_roster_change_is_rejected_without_reusing_stale_payload(
    client, world, auth_headers
):
    training = _training(world)
    rows = _roster(training)
    loaded_ids = [row.player_id for row in rows]
    db.session.delete(rows[-1])
    db.session.commit()

    response = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.owner_a),
        json={
            "roster_player_ids": loaded_ids,
            "attendance": _attendance_payload(rows),
        },
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TRAINING_ROSTER_CHANGED"
    assert Attendance.query.filter_by(session_id=training.id).count() == 0


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (
            lambda rows, world: [
                {"player_id": rows[0].player_id, "status": "present"},
                {"player_id": rows[0].player_id, "status": "absent"},
            ],
            "DUPLICATE_ATTENDANCE_PLAYER",
        ),
        (
            lambda rows, world: [
                {"player_id": row.player_id, "status": "excused"}
                for row in rows
            ],
            "INVALID_ATTENDANCE_STATUS",
        ),
        (
            lambda rows, world: [
                *_attendance_payload(rows),
                {"player_id": world.players_b[0].id, "status": "present"},
            ],
            "PLAYER_NOT_IN_TRAINING",
        ),
    ],
)
def test_attendance_rejects_duplicate_unknown_status_and_outsider(
    client, world, auth_headers, payload, expected_code
):
    training = _training(world)
    response = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.owner_a),
        json={"attendance": payload(_roster(training), world)},
    )

    assert response.status_code in [400, 403]
    assert response.get_json()["code"] == expected_code
    assert Attendance.query.filter_by(session_id=training.id).count() == 0


def test_complete_rejects_empty_roster(client, world, auth_headers):
    training = _training(world, with_roster=False)

    response = client.put(
        f"/api/trainings/{training.id}/complete",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TRAINING_ROSTER_EMPTY"
    assert db.session.get(TrainingSession, training.id).status == "scheduled"


@pytest.mark.parametrize("marked_count", [0, 3])
def test_complete_rejects_missing_attendance(
    client, world, auth_headers, marked_count
):
    training = _training(world)
    rows = _roster(training)
    _seed_attendance(training, rows[:marked_count])

    response = client.put(
        f"/api/trainings/{training.id}/complete",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["code"] == "TRAINING_ATTENDANCE_INCOMPLETE"
    assert payload["roster_count"] == len(rows)
    assert payload["attendance_count"] == marked_count
    assert payload["missing_count"] == len(rows) - marked_count
    assert db.session.get(TrainingSession, training.id).status == "scheduled"


def test_complete_rejects_physical_duplicate_that_masks_missing_player(
    client, world, auth_headers
):
    training = _training(world)
    rows = _roster(training)
    db.session.add_all([
        Attendance(
            session_id=training.id,
            player_id=rows[0].player_id,
            status=status,
        )
        for status in ("present", "absent")
    ] + [
        Attendance(
            session_id=training.id,
            player_id=row.player_id,
            status="present",
        )
        for row in rows[2:]
    ])
    db.session.commit()

    response = client.put(
        f"/api/trainings/{training.id}/complete",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["code"] == "TRAINING_ATTENDANCE_INCOMPLETE"
    assert payload["attendance_count"] == len(rows) - 2
    assert db.session.get(TrainingSession, training.id).status == "scheduled"


def test_complete_with_full_attendance_is_idempotent(
    client, world, auth_headers
):
    training = _training(world)
    rows = _roster(training)
    _seed_attendance(training, rows)
    headers = auth_headers(world.coach_a)
    url = f"/api/trainings/{training.id}/complete"

    first = client.put(url, headers=headers)
    second = client.put(url, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert db.session.get(TrainingSession, training.id).status == "completed"


def test_cancelled_training_cannot_complete(client, world, auth_headers):
    training = _training(world, status="cancelled")

    response = client.put(
        f"/api/trainings/{training.id}/complete",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "INVALID_TRAINING_STATUS"


def test_training_list_exposes_compact_attendance_progress(
    client, world, auth_headers
):
    training = _training(world)
    rows = _roster(training)
    _seed_attendance(training, rows[:3])

    response = client.get(
        "/api/trainings",
        headers=auth_headers(world.owner_a),
    )
    item = next(
        row for row in response.get_json()["trainings"]
        if row["id"] == training.id
    )

    assert item["roster_count"] == len(rows)
    assert item["attendance_count"] == 3
    assert item["present_count"] == 3
    assert item["attendance_complete"] is False
    assert item["category_name"] == world.category_a.name
    assert item["season_id"] == world.season_a.id


def test_dashboard_pending_attendance_excludes_completed(
    client, world, auth_headers
):
    club_today = get_club_today(world.club_a)
    scheduled = _training(world, training_date=club_today)
    completed = _training(
        world,
        status="completed",
        training_date=club_today,
    )

    response = client.get(
        "/api/club/dashboard",
        headers=auth_headers(world.owner_a),
    )
    pending = response.get_json()["sections"]["operations"]["pending_attendance"]
    pending_ids = {row["id"] for row in pending["trainings"]}

    assert scheduled.id in pending_ids
    assert completed.id not in pending_ids


def test_training_frontend_contracts_are_explicit_and_date_safe():
    list_source = (
        ROOT / "src/front/js/pages/trainings/trainings.js"
    ).read_text()
    team_list_source = (
        ROOT / "src/front/js/pages/trainings/teamTrainings.js"
    ).read_text()
    create_source = (
        ROOT / "src/front/js/pages/trainings/createTraining.js"
    ).read_text()
    detail_source = (
        ROOT / "src/front/js/pages/trainings/trainingDetail.js"
    ).read_text()
    toggle_source = (
        ROOT / "src/front/js/component/ui/attendanceToggle.js"
    ).read_text()
    date_source = (
        ROOT / "src/front/js/utils/dateOnly.js"
    ).read_text()

    assert 'new Date(date)' not in list_source
    assert 'new Date(date)' not in team_list_source
    assert 'new Date(Number(year), Number(month) - 1, Number(day))' in date_source
    assert 'className="training-card-link"' in list_source
    assert 'aria-pressed={selected}' in toggle_source
    assert "Presente" in toggle_source
    assert "Marcar todos presentes" in detail_source
    assert "completeReady" in detail_source
    assert "location.state?.from" in detail_source
    assert "Cambios sin guardar" in detail_source
    assert "Tienes cambios de asistencia sin guardar" in detail_source
    assert "loadRequestId" in list_source
    assert "loadRequestId" in team_list_source
    assert "loadRequestId" in create_source
    assert "loadRequestId" in detail_source
