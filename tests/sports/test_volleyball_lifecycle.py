import pytest

from src.api.models import MatchEvent, MatchSession, PlayerMatchStat, db
from tests.sports.helpers import event_payload, zero_stats


@pytest.mark.parametrize("mode", ["live", "summary"])
def test_capture_mode_can_be_selected_before_history(
    client, world, auth_headers, match_factory, mode
):
    created = match_factory(world, capture_mode=None)
    response = client.put(
        f"/api/matches/{created.match.id}/capture-mode",
        headers=auth_headers(world.owner_a),
        json={"capture_mode": mode},
    )
    assert response.status_code == 200
    assert response.get_json()["match"]["capture_mode"] == mode


def test_legacy_null_without_history_requires_mode(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode=None, on_court_count=1)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_CAPTURE_MODE_REQUIRED"


def test_legacy_null_with_stats_is_locked(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode=None, on_court_count=1)
    db.session.add(PlayerMatchStat(match_player_id=created.rows[0].id))
    db.session.commit()
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_CAPTURE_MODE_LEGACY_LOCKED"


def test_capture_mode_cannot_change_after_history(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode="live", on_court_count=1)
    client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )
    response = client.put(
        f"/api/matches/{created.match.id}/capture-mode",
        headers=auth_headers(world.owner_a),
        json={"capture_mode": "summary"},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_CAPTURE_MODE_LOCKED"


def test_summary_mode_rejects_live_events(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode="summary", on_court_count=1)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )
    assert (response.status_code, response.get_json()["code"]) == (
        409, "MATCH_EVENTS_NOT_AVAILABLE"
    )


def test_live_mode_rejects_manual_summary_stats(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode="live", did_play=True)
    response = client.post(
        f"/api/match-players/{created.rows[0].id}/stats",
        headers=auth_headers(world.owner_a),
        json=zero_stats(),
    )
    assert (response.status_code, response.get_json()["code"]) == (
        409, "MATCH_STATS_MANAGED_BY_LIVE"
    )


def test_open_match_history_blocks_starting_lineup_rewrite(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, on_court_count=6)
    headers = auth_headers(world.owner_a)
    client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0]),
    )
    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=headers,
        json={"players": [row.id for row in created.rows[1:7]]},
    )
    assert (response.status_code, response.get_json()["code"]) == (
        409, "MATCH_HISTORY_LOCKED"
    )


def test_open_match_history_blocks_removing_affected_player_only(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, on_court_count=1)
    headers = auth_headers(world.owner_a)
    client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0]),
    )
    response = client.post(
        f"/api/matches/{created.match.id}/roster",
        headers=headers,
        json={"players": [
            {"player_id": row.player_id} for row in created.rows[1:]
        ]},
    )
    assert (response.status_code, response.get_json()["code"]) == (
        409, "MATCH_HISTORY_LOCKED"
    )


def test_match_step_live_flow(client, world, auth_headers, match_factory):
    created = match_factory(world, called=False, attendance_status=None)
    headers = auth_headers(world.owner_a)
    assert created.match.match_step == 0
    response = client.post(
        f"/api/matches/{created.match.id}/roster",
        headers=headers,
        json={"players": [{"player_id": row.player_id} for row in created.rows[:6]]},
    )
    assert response.status_code == 200
    assert db.session.get(MatchSession, created.match.id).match_step == 1
    response = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=headers,
        json={"players": [{"match_player_id": row.id, "attendance_status": "present"} for row in created.rows[:6]]},
    )
    assert response.status_code == 200
    assert db.session.get(MatchSession, created.match.id).match_step == 2
    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=headers,
        json={"players": [row.id for row in created.rows[:6]]},
    )
    assert response.status_code == 200
    assert db.session.get(MatchSession, created.match.id).match_step == 3
    client.put(
        f"/api/matches/{created.match.id}/result", headers=headers,
        json={"home_sets": 3, "opponent_sets": 0},
    )
    assert db.session.get(MatchSession, created.match.id).match_step == 3
    assert client.put(f"/api/matches/{created.match.id}/finalize", headers=headers).status_code == 200
    assert db.session.get(MatchSession, created.match.id).is_completed is True


def test_match_step_summary_flow(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode="summary", did_play=False)
    headers = auth_headers(world.owner_a)
    response = client.put(
        f"/api/matches/{created.match.id}/roster/participation",
        headers=headers,
        json={"players": [{"match_player_id": created.rows[0].id, "did_play": True}]},
    )
    assert response.status_code == 200
    assert db.session.get(MatchSession, created.match.id).match_step == 3
    response = client.post(
        f"/api/match-players/{created.rows[0].id}/stats",
        headers=headers,
        json=zero_stats(),
    )
    assert response.status_code == 200
    assert db.session.get(MatchSession, created.match.id).match_step == 4
    assert {"id", "match_player_id", "attacks_total", "blocks_errors"} <= set(response.get_json()["stats"])


def _completed_with_event(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=6)
    headers = auth_headers(world.owner_a)
    event = client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0]),
    ).get_json()["event"]
    created.match.is_completed = True
    db.session.commit()
    return created, headers, event


def test_completed_match_blocks_new_event(client, world, auth_headers, match_factory):
    created, headers, _ = _completed_with_event(client, world, auth_headers, match_factory)
    response = client.post("/api/match-events", headers=headers, json=event_payload(created.match, created.rows[0]))
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_COMPLETED")


def test_completed_match_blocks_event_delete(client, world, auth_headers, match_factory):
    _, headers, event = _completed_with_event(client, world, auth_headers, match_factory)
    response = client.delete(f"/api/match-events/{event['id']}", headers=headers)
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_FINALIZED")
    assert MatchEvent.query.count() == 1


def test_completed_match_blocks_substitution(client, world, auth_headers, match_factory):
    created = match_factory(world, is_completed=True, on_court_count=6)
    response = client.post(
        f"/api/matches/{created.match.id}/substitutions",
        headers=auth_headers(world.owner_a),
        json={"player_out_id": created.rows[0].id, "player_in_id": created.rows[6].id, "set_number": 1},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_COMPLETED")


def test_completed_match_blocks_lineup(client, world, auth_headers, match_factory):
    created = match_factory(world, is_completed=True)
    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=auth_headers(world.owner_a), json={"players": [row.id for row in created.rows[:6]]},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_COMPLETED")


def test_completed_match_blocks_capture_mode_change(client, world, auth_headers, match_factory):
    created = match_factory(world, is_completed=True)
    response = client.put(
        f"/api/matches/{created.match.id}/capture-mode",
        headers=auth_headers(world.owner_a), json={"capture_mode": "summary"},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_CAPTURE_MODE_LOCKED")


def test_completed_match_blocks_summary_stats(client, world, auth_headers, match_factory):
    created = match_factory(world, capture_mode="summary", is_completed=True, did_play=True)
    response = client.post(
        f"/api/match-players/{created.rows[0].id}/stats",
        headers=auth_headers(world.owner_a), json=zero_stats(),
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_FINALIZED")


def test_completed_match_blocks_roster_change(client, world, auth_headers, match_factory):
    created = match_factory(world, is_completed=True)
    response = client.post(
        f"/api/matches/{created.match.id}/roster",
        headers=auth_headers(world.owner_a),
        json={"players": [{"player_id": row.player_id} for row in created.rows[:7]]},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_COMPLETED")


def test_completed_match_blocks_attendance_change(client, world, auth_headers, match_factory):
    created = match_factory(world, is_completed=True)
    response = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=auth_headers(world.owner_a),
        json={"players": [{"match_player_id": created.rows[0].id, "attendance_status": "absent"}]},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_COMPLETED")


def test_completed_match_blocks_participation_change(client, world, auth_headers, match_factory):
    created = match_factory(
        world, capture_mode="summary", is_completed=True, did_play=True
    )
    response = client.put(
        f"/api/matches/{created.match.id}/roster/participation",
        headers=auth_headers(world.owner_a),
        json={"players": [{"match_player_id": created.rows[0].id, "did_play": False}]},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_COMPLETED")
