from datetime import date, time

import pytest

from src.api.models import (
    Attendance,
    MatchEvent,
    MatchPlayer,
    MatchSession,
    MatchSubstitution,
    Player,
    PlayerMatchStat,
    TeamPlayer,
    TrainingAuditEvent,
    TrainingPlayer,
    TrainingSession,
    db,
)
from src.api.training_service import sync_training_roster
from tests.sports.helpers import event_payload, zero_stats


CORRECTION_REASON = "Corrección documentada del registro histórico"


def _training(world, status="scheduled", team=None):
    training = TrainingSession(
        team=team or world.team_a,
        date=date(2026, 8, 10),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha principal",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    db.session.flush()
    sync_training_roster(training)
    training.status = status
    db.session.commit()
    return training


def _archive(client, world, auth_headers, team=None):
    response = client.put(
        f"/api/teams/{(team or world.team_a).id}/archive",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200
    return response


def _reactivate(client, world, auth_headers):
    response = client.put(
        f"/api/teams/{world.team_a.id}/reactivate",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200
    return response


def _training_state(training_id):
    db.session.expire_all()
    training = db.session.get(TrainingSession, training_id)
    return (
        training.status,
        training.date,
        training.start_time,
        training.end_time,
        training.location,
        sorted(
            row.player_id
            for row in TrainingPlayer.query.filter_by(
                training_id=training_id
            ).all()
        ),
        sorted(
            (row.player_id, row.status)
            for row in Attendance.query.filter_by(session_id=training_id).all()
        ),
    )


def _match_state(match_id):
    db.session.expire_all()
    match = db.session.get(MatchSession, match_id)
    rows = MatchPlayer.query.filter_by(match_id=match_id).all()
    return (
        match.is_completed,
        match.home_sets,
        match.opponent_sets,
        match.result,
        match.capture_mode,
        match.match_step,
        sorted(
            (
                row.player_id,
                row.is_called,
                row.attendance_status,
                row.did_play,
                row.is_on_court,
                row.position,
            )
            for row in rows
        ),
        MatchEvent.query.filter_by(match_id=match_id).count(),
        MatchSubstitution.query.filter_by(match_id=match_id).count(),
        PlayerMatchStat.query.join(MatchPlayer).filter(
            MatchPlayer.match_id == match_id
        ).count(),
    )


TRAINING_MUTATIONS = {
    "attendance": lambda training, world: (
        "post",
        f"/api/trainings/{training.id}/attendance",
        {
            "attendance": [
                {"player_id": world.players_a[0].id, "status": "present"}
            ]
        },
    ),
    "sync_roster": lambda training, world: (
        "put",
        f"/api/trainings/{training.id}/sync-roster",
        None,
    ),
    "complete": lambda training, world: (
        "put",
        f"/api/trainings/{training.id}/complete",
        None,
    ),
    "cancel": lambda training, world: (
        "put",
        f"/api/trainings/{training.id}/cancel",
        None,
    ),
    "update": lambda training, world: (
        "put",
        f"/api/trainings/{training.id}",
        {
            "date": "2026-08-12",
            "start_time": "18:00",
            "end_time": "20:00",
            "location": "Otra cancha",
        },
    ),
}


def _send(client, headers, request):
    method, url, payload = request
    kwargs = {"headers": headers}

    if payload is not None:
        kwargs["json"] = payload

    return getattr(client, method)(url, **kwargs)


@pytest.mark.parametrize("mutation", sorted(TRAINING_MUTATIONS))
def test_training_mutation_payload_is_valid_on_active_team(
    client, world, auth_headers, mutation
):
    training = _training(world)
    request = TRAINING_MUTATIONS[mutation](training, world)

    response = _send(client, auth_headers(world.coach_a), request)

    assert response.status_code == 200


@pytest.mark.parametrize("user_key", ["owner_a", "coach_a"])
@pytest.mark.parametrize("mutation", sorted(TRAINING_MUTATIONS))
def test_archived_team_rejects_training_mutation(
    client, world, auth_headers, mutation, user_key
):
    training = _training(world)
    training_id = training.id
    _archive(client, world, auth_headers)
    before = _training_state(training_id)
    request = TRAINING_MUTATIONS[mutation](training, world)

    response = _send(client, auth_headers(getattr(world, user_key)), request)

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    assert _training_state(training_id) == before


def test_archived_team_sync_does_not_change_training_roster(
    client, world, auth_headers
):
    training = _training(world)
    training_id = training.id
    newcomer = Player(
        first_name="Nueva",
        last_name="Archivo",
        sex="female",
        main_position="setter",
        is_active=True,
        club=world.club_a,
    )
    db.session.add(TeamPlayer(
        team=world.team_a,
        player=newcomer,
        player_number=70,
        status="active",
    ))
    db.session.commit()
    _archive(client, world, auth_headers)

    response = client.put(
        f"/api/trainings/{training_id}/sync-roster",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert TrainingPlayer.query.filter_by(
        training_id=training_id,
        player_id=newcomer.id,
    ).first() is None


def test_archive_does_not_change_open_activities(
    client, world, auth_headers, match_factory
):
    training = _training(world)
    created = match_factory(world)
    training_before = _training_state(training.id)
    match_before = _match_state(created.match.id)

    _archive(client, world, auth_headers)

    assert _training_state(training.id) == training_before
    assert _match_state(created.match.id) == match_before
    assert db.session.get(TrainingSession, training.id).status == "scheduled"
    assert db.session.get(MatchSession, created.match.id).is_completed is False


def _match_for_mutation(world, match_factory, mutation):
    config = {
        "roster": {"called": False},
        "roster_status": {"called": True, "attendance_status": None},
        "capture_mode": {},
        "starting_lineup": {},
        "substitution": {"on_court_count": 6, "did_play": False},
        "participation": {"capture_mode": "summary"},
        "stats": {"capture_mode": "summary", "did_play": True},
        "event": {"on_court_count": 6},
        "delete_event": {"on_court_count": 6},
        "result": {},
        "finalize": {},
    }[mutation]
    created = match_factory(world, **config)

    if mutation == "capture_mode":
        created.match.capture_mode = "summary"

    if mutation == "finalize":
        created.match.home_sets = 3
        created.match.opponent_sets = 1
        created.match.result = "win"

    db.session.commit()
    return created


def _match_request(client, world, auth_headers, created, mutation):
    match = created.match
    rows = created.rows
    base = f"/api/matches/{match.id}"

    if mutation == "roster":
        return (
            "post",
            f"{base}/roster",
            {"players": [{"player_id": row.player_id} for row in rows[:6]]},
        )

    if mutation == "roster_status":
        return (
            "put",
            f"{base}/roster/status",
            {
                "players": [
                    {"match_player_id": row.id, "attendance_status": "present"}
                    for row in rows[:6]
                ]
            },
        )

    if mutation == "capture_mode":
        return ("put", f"{base}/capture-mode", {"capture_mode": "live"})

    if mutation == "starting_lineup":
        return (
            "put",
            f"{base}/starting-lineup",
            {"players": [row.id for row in rows[:6]]},
        )

    if mutation == "substitution":
        return (
            "post",
            f"{base}/substitutions",
            {
                "player_out_id": rows[0].id,
                "player_in_id": rows[6].id,
                "set_number": 1,
            },
        )

    if mutation == "participation":
        return (
            "put",
            f"{base}/roster/participation",
            {"players": [{"match_player_id": rows[0].id, "did_play": True}]},
        )

    if mutation == "stats":
        return ("post", f"/api/match-players/{rows[0].id}/stats", zero_stats())

    if mutation == "event":
        return ("post", "/api/match-events", event_payload(match, rows[0]))

    if mutation == "delete_event":
        event_response = client.post(
            "/api/match-events",
            headers=auth_headers(world.owner_a),
            json=event_payload(match, rows[0]),
        )
        assert event_response.status_code == 201
        event_id = MatchEvent.query.filter_by(match_id=match.id).one().id
        return ("delete", f"/api/match-events/{event_id}", None)

    if mutation == "result":
        return ("put", f"{base}/result", {"home_sets": 3, "opponent_sets": 1})

    return ("put", f"{base}/finalize", None)


MATCH_MUTATIONS = [
    "capture_mode",
    "delete_event",
    "event",
    "finalize",
    "participation",
    "result",
    "roster",
    "roster_status",
    "starting_lineup",
    "stats",
    "substitution",
]


@pytest.mark.parametrize("mutation", MATCH_MUTATIONS)
def test_match_mutation_payload_is_valid_on_active_team(
    client, world, auth_headers, match_factory, mutation
):
    created = _match_for_mutation(world, match_factory, mutation)
    request = _match_request(client, world, auth_headers, created, mutation)

    response = _send(client, auth_headers(world.coach_a), request)

    assert response.status_code in [200, 201], response.get_json()


@pytest.mark.parametrize("user_key", ["owner_a", "coach_a"])
@pytest.mark.parametrize("mutation", MATCH_MUTATIONS)
def test_archived_team_rejects_match_mutation(
    client, world, auth_headers, match_factory, mutation, user_key
):
    created = _match_for_mutation(world, match_factory, mutation)
    match_id = created.match.id
    request = _match_request(client, world, auth_headers, created, mutation)
    _archive(client, world, auth_headers)
    before = _match_state(match_id)

    response = _send(client, auth_headers(getattr(world, user_key)), request)

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    assert _match_state(match_id) == before


def test_training_reads_remain_available_on_archived_team(
    client, world, auth_headers
):
    training = _training(world)
    headers = auth_headers(world.coach_a)
    _archive(client, world, auth_headers)

    for url in [
        f"/api/trainings/{training.id}",
        f"/api/trainings/{training.id}/attendance",
        f"/api/trainings/{training.id}/players",
        f"/api/trainings/{training.id}/audit",
        f"/api/teams/{world.team_a.id}/trainings",
    ]:
        assert client.get(url, headers=headers).status_code == 200, url


def test_match_reads_remain_available_on_archived_team(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, on_court_count=6)
    assert client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    ).status_code == 201
    headers = auth_headers(world.coach_a)
    _archive(client, world, auth_headers)

    for url in [
        f"/api/matches/{created.match.id}",
        f"/api/matches/{created.match.id}/roster",
        f"/api/match-players/{created.rows[0].id}/stats",
        f"/api/teams/{world.team_a.id}/matches",
    ]:
        assert client.get(url, headers=headers).status_code == 200, url

    assert MatchEvent.query.filter_by(match_id=created.match.id).count() == 1


def test_get_roster_does_not_write_on_archived_team(
    client, world, auth_headers
):
    match = MatchSession(
        team=world.team_a,
        date=date(2026, 8, 11),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(match)
    db.session.commit()
    match_id = match.id
    assert MatchPlayer.query.filter_by(match_id=match_id).count() == 0
    _archive(client, world, auth_headers)

    response = client.get(
        f"/api/matches/{match_id}/roster",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert MatchPlayer.query.filter_by(match_id=match_id).count() == 0


def test_get_roster_derives_open_match_without_writing_on_active_team(
    client, world, auth_headers
):
    match = MatchSession(
        team=world.team_a,
        date=date(2026, 8, 11),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(match)
    db.session.commit()

    response = client.get(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 200
    assert len(response.get_json()["players"]) == len(world.players_a)
    assert MatchPlayer.query.filter_by(match_id=match.id).count() == 0


def test_performance_history_is_identical_after_archive(
    client, world, auth_headers, match_factory
):
    created = match_factory(
        world,
        capture_mode="summary",
        is_completed=True,
        did_play=True,
    )
    player_id = created.rows[0].player_id
    headers = auth_headers(world.owner_a)
    url = f"/api/players/{player_id}/performance"
    params = {"season_id": world.season_a.id}
    before = client.get(url, headers=headers, query_string=params).get_json()
    assert before["summary"]["matches_played"] == 1

    _archive(client, world, auth_headers)

    after = client.get(url, headers=headers, query_string=params)
    assert after.status_code == 200
    data = after.get_json()
    assert data["summary"] == before["summary"]
    assert data["totals"] == before["totals"]


def test_explicit_training_corrections_stay_allowed_on_archived_team(
    client, world, auth_headers
):
    training = _training(world, status="completed")
    player_id = world.players_a[0].id
    db.session.add(Attendance(
        session_id=training.id,
        player_id=player_id,
        status="absent",
    ))
    db.session.commit()
    _archive(client, world, auth_headers)
    headers = auth_headers(world.coach_a)

    attendance_response = client.post(
        f"/api/trainings/{training.id}/corrections/attendance",
        headers=headers,
        json={
            "reason": CORRECTION_REASON,
            "attendance": [{"player_id": player_id, "status": "present"}],
        },
    )
    metadata_response = client.post(
        f"/api/trainings/{training.id}/corrections/metadata",
        headers=headers,
        json={
            "reason": CORRECTION_REASON,
            "changes": {"location": "Sede corregida"},
        },
    )

    assert attendance_response.status_code == 200
    assert metadata_response.status_code == 200
    assert TrainingAuditEvent.query.filter_by(
        training_id=training.id
    ).count() == 2
    assert db.session.get(TrainingSession, training.id).status == "completed"


def test_explicit_training_corrections_stay_allowed_on_closed_season(
    client, world, auth_headers
):
    training = _training(world, status="completed")
    world.season_a.status = "closed"
    db.session.commit()

    response = client.post(
        f"/api/trainings/{training.id}/corrections/metadata",
        headers=auth_headers(world.coach_a),
        json={
            "reason": CORRECTION_REASON,
            "changes": {"location": "Sede corregida"},
        },
    )

    assert response.status_code == 200
    assert TrainingAuditEvent.query.filter_by(
        training_id=training.id
    ).count() == 1


def test_training_correction_requires_closed_activity_on_archived_team(
    client, world, auth_headers
):
    training = _training(world)
    _archive(client, world, auth_headers)

    response = client.post(
        f"/api/trainings/{training.id}/corrections/metadata",
        headers=auth_headers(world.coach_a),
        json={
            "reason": CORRECTION_REASON,
            "changes": {"location": "Sede corregida"},
        },
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "INVALID_TRAINING_STATUS"


def test_cancelled_training_cannot_reactivate_while_team_is_archived(
    client, world, auth_headers
):
    training = _training(world, status="cancelled")
    _archive(client, world, auth_headers)
    url = f"/api/trainings/{training.id}/reactivate"
    payload = {"reason": CORRECTION_REASON}
    headers = auth_headers(world.coach_a)

    archived_response = client.post(url, headers=headers, json=payload)

    assert archived_response.status_code == 409
    assert archived_response.get_json()["code"] == "TEAM_ARCHIVED"
    assert db.session.get(TrainingSession, training.id).status == "cancelled"

    _reactivate(client, world, auth_headers)

    assert client.post(url, headers=headers, json=payload).status_code == 200


def test_reactivating_team_restores_only_operations_allowed_by_lifecycle(
    client, world, auth_headers, match_factory
):
    scheduled = _training(world)
    completed = _training(world, status="completed")
    cancelled = _training(world, status="cancelled")
    open_match = match_factory(world)
    finished_match = match_factory(world, is_completed=True)
    headers = auth_headers(world.coach_a)
    _archive(client, world, auth_headers)

    _reactivate(client, world, auth_headers)

    db.session.expire_all()
    assert db.session.get(TrainingSession, scheduled.id).status == "scheduled"
    assert db.session.get(TrainingSession, completed.id).status == "completed"
    assert db.session.get(TrainingSession, cancelled.id).status == "cancelled"
    assert db.session.get(MatchSession, finished_match.match.id).is_completed

    assert client.put(
        f"/api/trainings/{scheduled.id}/complete", headers=headers
    ).status_code == 200

    locked_training = client.put(
        f"/api/trainings/{completed.id}",
        headers=headers,
        json={
            "date": "2026-08-12",
            "start_time": "18:00",
            "end_time": "20:00",
            "location": "Otra cancha",
        },
    )
    assert locked_training.status_code == 409
    assert locked_training.get_json()["code"] == "TRAINING_LOCKED"

    cancelled_attendance = client.post(
        f"/api/trainings/{cancelled.id}/attendance",
        headers=headers,
        json={
            "attendance": [
                {"player_id": world.players_a[0].id, "status": "present"}
            ]
        },
    )
    assert cancelled_attendance.status_code == 409
    assert cancelled_attendance.get_json()["code"] == "TRAINING_CANCELLED"

    open_result = client.put(
        f"/api/matches/{open_match.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 1},
    )
    assert open_result.status_code == 200

    finished_result = client.put(
        f"/api/matches/{finished_match.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 1},
    )
    assert finished_result.status_code == 409
    assert finished_result.get_json()["code"] == "MATCH_FINALIZED"


def test_archived_state_takes_precedence_over_closed_season(
    client, world, auth_headers
):
    training = _training(world)
    _archive(client, world, auth_headers)
    world.season_a.status = "closed"
    db.session.commit()

    response = client.put(
        f"/api/trainings/{training.id}/complete",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    assert db.session.get(TrainingSession, training.id).status == "scheduled"


def test_closed_season_rejects_normal_activity_mutations(
    client, world, auth_headers, match_factory
):
    training = _training(world)
    created = match_factory(world)
    world.season_a.status = "closed"
    db.session.commit()
    headers = auth_headers(world.coach_a)

    training_response = client.put(
        f"/api/trainings/{training.id}/complete", headers=headers
    )
    match_response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 1},
    )

    assert training_response.status_code == 409
    assert training_response.get_json()["code"] == "SEASON_CLOSED"
    assert match_response.status_code == 409
    assert match_response.get_json()["code"] == "SEASON_CLOSED"


def test_cross_tenant_response_is_not_affected_by_archived_state(
    client, world, auth_headers, match_factory
):
    training = _training(world)
    created = match_factory(world)
    _archive(client, world, auth_headers)
    headers = auth_headers(world.coach_b)

    for response in [
        client.put(f"/api/trainings/{training.id}/complete", headers=headers),
        client.post(
            f"/api/trainings/{training.id}/attendance",
            headers=headers,
            json={"attendance": []},
        ),
        client.put(
            f"/api/matches/{created.match.id}/result",
            headers=headers,
            json={"home_sets": 3, "opponent_sets": 1},
        ),
        client.post(
            "/api/match-events",
            headers=headers,
            json=event_payload(created.match, created.rows[0]),
        ),
    ]:
        assert response.status_code == 403
        assert response.get_json()["code"] == "FORBIDDEN"

    assert db.session.get(TrainingSession, training.id).status == "scheduled"
    assert world.team_a.status == "archived"


def test_staff_remains_forbidden_on_archived_team_activities(
    client, world, auth_headers, match_factory
):
    training = _training(world)
    created = match_factory(world)
    _archive(client, world, auth_headers)
    headers = auth_headers(world.staff_a)

    training_response = client.put(
        f"/api/trainings/{training.id}/complete", headers=headers
    )
    match_response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 1},
    )

    assert training_response.status_code == 403
    assert training_response.get_json()["code"] == "FORBIDDEN"
    assert match_response.status_code == 403
    assert match_response.get_json()["code"] == "FORBIDDEN"
