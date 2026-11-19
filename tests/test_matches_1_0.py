from datetime import date
from pathlib import Path

import pytest

from src.api.models import (
    MatchEvent,
    MatchPlayer,
    MatchSession,
    PlayerMatchStat,
    TeamPlayer,
    Tournament,
    TournamentTeam,
    db,
)
from tests.sports.helpers import event_payload, zero_stats


def _headers(auth_headers, world):
    return auth_headers(world.owner_a)


def _attendance_payload(rows, *, override=None):
    override = override or {}
    return [
        {
            "match_player_id": row.id,
            "attendance_status": override.get(row.id, row.attendance_status or "present"),
            "position": row.position,
        }
        for row in rows
        if row.is_called
    ]


def _participation_payload(rows, selected_ids):
    return [
        {"match_player_id": row.id, "did_play": row.id in selected_ids}
        for row in rows
        if row.is_called and row.attendance_status in ("present", "late")
    ]


def _ready_summary_match(client, world, auth_headers, match_factory):
    created = match_factory(
        world,
        capture_mode="summary",
        on_court_count=6,
    )
    selected_ids = {row.id for row in created.rows[:6]}
    response = client.put(
        f"/api/matches/{created.match.id}/roster/participation",
        headers=_headers(auth_headers, world),
        json={"players": _participation_payload(created.rows, selected_ids)},
    )
    assert response.status_code == 200

    for row in created.rows[:6]:
        response = client.post(
            f"/api/match-players/{row.id}/stats",
            headers=_headers(auth_headers, world),
            json=zero_stats(),
        )
        assert response.status_code == 200

    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=_headers(auth_headers, world),
        json={"home_sets": 3, "opponent_sets": 1},
    )
    assert response.status_code == 200
    return created


@pytest.mark.parametrize(
    ("mutation", "expected_blocker"),
    [
        ("empty", "callup"),
        ("attendance", "attendance"),
        ("mode", "capture_mode"),
        ("lineup", "lineup"),
        ("stats", "stats"),
        ("result", "result"),
    ],
)
def test_finalize_preflight_blocks_each_incomplete_stage(
    client, world, auth_headers, match_factory, mutation, expected_blocker
):
    if mutation == "empty":
        created = match_factory(
            world,
            capture_mode=None,
            called=False,
            attendance_status=None,
        )
    else:
        created = match_factory(
            world,
            capture_mode="summary",
            on_court_count=6,
        )
        for row in created.rows[:6]:
            db.session.add(PlayerMatchStat(match_player_id=row.id))
        created.match.home_sets = 3
        created.match.opponent_sets = 1
        created.match.result = "win"
        db.session.commit()

        if mutation == "attendance":
            created.rows[-1].attendance_status = None
        elif mutation == "mode":
            created.match.capture_mode = None
        elif mutation == "lineup":
            created.rows[5].is_on_court = False
        elif mutation == "stats":
            db.session.delete(created.rows[0].performance_stats)
        elif mutation == "result":
            created.match.home_sets = 0
            created.match.opponent_sets = 0
            created.match.result = None
        db.session.commit()

    response = client.put(
        f"/api/matches/{created.match.id}/finalize",
        headers=_headers(auth_headers, world),
    )
    assert response.status_code == 409
    payload = response.get_json()
    assert payload["code"] == "MATCH_NOT_READY"
    assert expected_blocker in {item["section"] for item in payload["blockers"]}
    assert db.session.get(MatchSession, created.match.id).is_completed is False


def test_finalize_success_and_repeat_are_idempotent(
    client, world, auth_headers, match_factory
):
    created = _ready_summary_match(client, world, auth_headers, match_factory)
    url = f"/api/matches/{created.match.id}/finalize"
    first = client.put(url, headers=_headers(auth_headers, world))
    second = client.put(url, headers=_headers(auth_headers, world))
    assert first.status_code == second.status_code == 200
    assert first.get_json()["match"]["is_completed"] is True
    assert second.get_json()["match"]["is_completed"] is True


def test_preflight_does_not_trust_match_step(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, called=False, capture_mode=None)
    created.match.match_step = 4
    db.session.commit()
    response = client.get(
        f"/api/matches/{created.match.id}/preflight",
        headers=_headers(auth_headers, world),
    )
    assert response.status_code == 200
    assert response.get_json()["preflight"]["callup"]["ready"] is False


def test_attendance_requires_exact_atomic_snapshot(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, attendance_status=None)
    headers = _headers(auth_headers, world)
    full = _attendance_payload(created.rows)

    subset = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=headers,
        json={"players": full[:-1]},
    )
    assert (subset.status_code, subset.get_json()["code"]) == (409, "MATCH_ROSTER_CHANGED")
    assert all(row.attendance_status is None for row in MatchPlayer.query.filter_by(match_id=created.match.id))

    duplicate = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=headers,
        json={"players": [*full, full[0]]},
    )
    assert (duplicate.status_code, duplicate.get_json()["code"]) == (400, "DUPLICATE_MATCH_ATTENDANCE")

    outsider = dict(full[-1], match_player_id="outside")
    stale = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=headers,
        json={"players": [*full[:-1], outsider]},
    )
    assert (stale.status_code, stale.get_json()["code"]) == (409, "MATCH_ROSTER_CHANGED")

    success = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=headers,
        json={"players": full},
    )
    assert success.status_code == 200
    assert all(row.attendance_status == "present" for row in MatchPlayer.query.filter_by(match_id=created.match.id))


def test_callup_change_is_blocked_after_attendance_without_data_loss(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    before = [(row.id, row.is_called, row.attendance_status) for row in created.rows]
    response = client.post(
        f"/api/matches/{created.match.id}/roster",
        headers=_headers(auth_headers, world),
        json={"players": [{"player_id": row.player_id} for row in created.rows[:-1]]},
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "MATCH_CALLUP_LOCKED")
    after = [(row.id, row.is_called, row.attendance_status) for row in MatchPlayer.query.filter_by(match_id=created.match.id).order_by(MatchPlayer.id)]
    assert sorted(before) == after


def test_attendance_cannot_silently_clear_saved_lineup_or_participation(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, capture_mode="summary")
    headers = _headers(auth_headers, world)
    lineup = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=headers,
        json={"players": [row.id for row in created.rows[:6]]},
    )
    assert lineup.status_code == 200

    before = [
        (row.id, row.attendance_status, row.did_play, row.is_on_court)
        for row in MatchPlayer.query.filter_by(match_id=created.match.id)
        .order_by(MatchPlayer.id)
        .all()
    ]
    response = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=headers,
        json={
            "players": _attendance_payload(
                created.rows,
                override={created.rows[0].id: "absent"},
            )
        },
    )

    assert (response.status_code, response.get_json()["code"]) == (
        409,
        "MATCH_HISTORY_LOCKED",
    )
    after = [
        (row.id, row.attendance_status, row.did_play, row.is_on_court)
        for row in MatchPlayer.query.filter_by(match_id=created.match.id)
        .order_by(MatchPlayer.id)
        .all()
    ]
    assert after == before


def test_summary_participation_requires_full_playable_snapshot_and_starters(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, capture_mode="summary", on_court_count=6)
    headers = _headers(auth_headers, world)
    selected_ids = {row.id for row in created.rows[:6]}
    payload = _participation_payload(created.rows, selected_ids)

    subset = client.put(
        f"/api/matches/{created.match.id}/roster/participation",
        headers=headers,
        json={"players": payload[:-1]},
    )
    assert (subset.status_code, subset.get_json()["code"]) == (409, "MATCH_ATTENDANCE_CHANGED")

    payload[0]["did_play"] = False
    starter = client.put(
        f"/api/matches/{created.match.id}/roster/participation",
        headers=headers,
        json={"players": payload},
    )
    assert (starter.status_code, starter.get_json()["code"]) == (400, "STARTING_LINEUP_MUST_PARTICIPATE")


def test_zero_summary_row_counts_as_reviewed(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, capture_mode="summary", on_court_count=6)
    for row in created.rows[:6]:
        db.session.add(PlayerMatchStat(match_player_id=row.id))
    db.session.commit()
    response = client.get(
        f"/api/matches/{created.match.id}/preflight",
        headers=_headers(auth_headers, world),
    )
    stats = response.get_json()["preflight"]["stats"]
    assert stats["ready"] is True
    assert stats["counts"] == {"reviewed": 6, "required": 6}


def test_event_history_is_tenant_safe_and_ordered(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, capture_mode="live", on_court_count=6)
    headers = _headers(auth_headers, world)
    first = client.post("/api/match-events", headers=headers, json=event_payload(created.match, created.rows[0], set_number=1))
    second = client.post("/api/match-events", headers=headers, json=event_payload(created.match, created.rows[1], action="serve", result="ace", set_number=2))
    response = client.get(f"/api/matches/{created.match.id}/events", headers=headers)
    assert response.status_code == 200
    assert [event["id"] for event in response.get_json()["events"]] == [first.get_json()["event"]["id"], second.get_json()["event"]["id"]]
    denied = client.get(f"/api/matches/{created.match.id}/events", headers=auth_headers(world.owner_b))
    assert denied.status_code == 403


def test_tournament_transition_and_child_writes_share_lifecycle_boundary(
    client, world, auth_headers, match_factory
):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name="Copa",
        start_date=date(2026, 10, 1),
        status="active",
        created_by=world.owner_a.id,
    )
    entry = TournamentTeam(tournament=tournament, team=world.team_a, status="active")
    db.session.add_all([tournament, entry])
    db.session.flush()
    created = match_factory(world, capture_mode="summary", on_court_count=6)
    created.match.tournament_team_id = entry.id
    db.session.commit()

    blocked = client.put(
        f"/api/tournaments/{tournament.id}/complete",
        headers=_headers(auth_headers, world),
    )
    assert (blocked.status_code, blocked.get_json()["code"]) == (409, "TOURNAMENT_HAS_OPEN_MATCHES")

    tournament.status = "completed"
    db.session.commit()
    write = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=_headers(auth_headers, world),
        json={"home_sets": 3, "opponent_sets": 0},
    )
    assert (write.status_code, write.get_json()["code"]) == (409, "TOURNAMENT_NOT_ACTIVE")


def test_create_rejects_team_without_eligible_players_atomically(
    client, world, auth_headers
):
    TeamPlayer.query.filter_by(team_id=world.team_a.id).update({"status": "inactive"})
    db.session.commit()
    response = client.post(
        "/api/matches",
        headers=_headers(auth_headers, world),
        json={
            "team_id": world.team_a.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
            "match_type": "official",
        },
    )
    assert (response.status_code, response.get_json()["code"]) == (409, "TEAM_HAS_NO_ELIGIBLE_PLAYERS")
    assert MatchSession.query.filter_by(team_id=world.team_a.id).count() == 0


def test_frontend_contract_contains_stale_guards_and_safe_flow():
    root = Path(__file__).parents[1]
    matches = (root / "src/front/js/pages/matches/matches.js").read_text()
    detail = (root / "src/front/js/pages/matches/matchDetail.js").read_text()
    live = (root / "src/front/js/pages/matches/LiveMatch.js").read_text()
    stats = (root / "src/front/js/pages/matches/playerMatchStats.js").read_text()
    flux = (root / "src/front/js/store/flux.js").read_text()

    assert "loadRequestId" in matches and "useSearchParams" in matches
    assert "loadRequestId" in detail and "match-preflight-list" in detail
    assert "Marcar todas presentes" in detail and "role=\"dialog\"" in detail
    assert "finalizeReturnFocusRef" in detail and "focusableSelector" in detail
    assert "location.search" in detail and "detailPath" in live
    assert "window.confirm" in live and "getMatchEvents" in live
    assert "setAttacksErrors((prev)" not in stats
    assert "clubMatchesRequestId" in flux and "STALE_RESPONSE" in flux
