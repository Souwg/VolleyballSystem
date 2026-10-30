from dataclasses import replace
from datetime import date

import pytest

from src.api.models import (
    MatchPlayer,
    MatchSession,
    MatchSubstitution,
    Team,
    TeamPlayer,
    db,
)
from src.api.sports import (
    SportAdapter,
    VolleyballAdapter,
    sport_adapter_registry,
)
from tests.sports.helpers import register_test_period_adapter


def _lineup(client, headers, created, rows):
    return client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=headers,
        json={"players": [row.id for row in rows]},
    )


def _register_test_lineup_adapter(
    monkeypatch,
    world,
    *,
    lineup_size,
    supports_lineup=True,
):
    code = "TEST_LINEUP"
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code=code,
        name="Deporte de prueba",
        capabilities=replace(
            volleyball.capabilities,
            supports_lineup=supports_lineup,
            lineup_size=lineup_size,
        ),
        positions=volleyball.positions,
    )

    monkeypatch.setitem(
        sport_adapter_registry._adapters,
        code,
        adapter,
    )
    world.sport.code = code
    db.session.commit()

    return adapter


@pytest.mark.parametrize("count,expected", [(5, 400), (6, 200), (7, 400)])
def test_lineup_requires_exactly_six(client, world, auth_headers, match_factory, count, expected):
    created = match_factory(world)
    response = _lineup(client, auth_headers(world.owner_a), created, created.rows[:count])
    assert response.status_code == expected
    if expected == 400:
        assert response.get_json()["code"] == "STARTING_LINEUP_MUST_HAVE_6"


@pytest.mark.parametrize("status", ["present", "late"])
def test_playable_attendance_is_eligible(client, world, auth_headers, match_factory, status):
    created = match_factory(world, attendance_status=status)
    assert _lineup(client, auth_headers(world.coach_a), created, created.rows[:6]).status_code == 200


@pytest.mark.parametrize(
    "called,status,code",
    [(True, "absent", "PLAYER_NOT_ELIGIBLE_FOR_LINEUP"), (False, None, "PLAYER_NOT_CALLED")],
)
def test_ineligible_player_is_rejected(
    client, world, auth_headers, match_factory, called, status, code
):
    created = match_factory(world)
    created.rows[0].is_called = called
    created.rows[0].attendance_status = status
    db.session.commit()
    response = _lineup(client, auth_headers(world.owner_a), created, created.rows[:6])
    assert response.status_code == 400
    assert response.get_json()["code"] == code


def test_player_from_another_match_is_rejected(client, world, auth_headers, match_factory):
    first = match_factory(world)
    second = match_factory(world, tenant="b")
    selected = first.rows[:5] + [second.rows[0]]
    response = _lineup(client, auth_headers(world.owner_a), first, selected)
    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_STARTING_LINEUP"


def test_player_from_another_team_is_rejected(
    client,
    world,
    auth_headers,
    match_factory,
):
    created = match_factory(world)
    other_team = Team(
        name="Team alterno",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    other_membership = TeamPlayer(
        team=other_team,
        player=world.players_a[7],
        player_number=8,
        status="active",
    )
    other_match = MatchSession(
        team=other_team,
        date=date(2026, 10, 27),
        opponent_name="Otro rival",
        match_type="official",
        capture_mode="live",
        created_by=world.owner_a.id,
    )
    other_row = MatchPlayer(
        match=other_match,
        player=world.players_a[7],
        player_number=8,
        is_called=True,
        attendance_status="present",
        position=world.players_a[7].main_position,
    )
    db.session.add_all([
        other_team,
        other_membership,
        other_match,
        other_row,
    ])
    db.session.commit()

    response = _lineup(
        client,
        auth_headers(world.owner_a),
        created,
        created.rows[:5] + [other_row],
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_STARTING_LINEUP"


def test_starting_lineup_uses_adapter_lineup_size(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    adapter = _register_test_lineup_adapter(
        monkeypatch,
        world,
        lineup_size=4,
    )
    valid_match = match_factory(world)
    oversized_match = match_factory(world)

    valid_response = _lineup(
        client,
        auth_headers(world.owner_a),
        valid_match,
        valid_match.rows[:4],
    )
    oversized_response = _lineup(
        client,
        auth_headers(world.owner_a),
        oversized_match,
        oversized_match.rows[:6],
    )

    assert adapter.capabilities.lineup_size == 4
    assert valid_response.status_code == 200
    assert oversized_response.status_code == 400
    assert oversized_response.get_json()["code"] == (
        "STARTING_LINEUP_MUST_HAVE_6"
    )
    assert MatchPlayer.query.filter_by(
        match_id=valid_match.match.id,
        is_on_court=True,
    ).count() == 4


def test_missing_adapter_does_not_fallback_to_six(
    client,
    world,
    auth_headers,
    match_factory,
):
    world.sport.code = "UNREGISTERED"
    db.session.commit()
    created = match_factory(world)

    response = _lineup(
        client,
        auth_headers(world.owner_a),
        created,
        created.rows[:6],
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_LINEUP_NOT_SUPPORTED"


@pytest.mark.parametrize(
    "supports_lineup,lineup_size",
    [(False, 6), (True, 0), (True, True)],
)
def test_invalid_lineup_capabilities_fail_explicitly(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
    supports_lineup,
    lineup_size,
):
    _register_test_lineup_adapter(
        monkeypatch,
        world,
        lineup_size=lineup_size,
        supports_lineup=supports_lineup,
    )
    created = match_factory(world)

    response = _lineup(
        client,
        auth_headers(world.owner_a),
        created,
        created.rows[:6],
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_LINEUP_NOT_SUPPORTED"


def test_lineup_snapshot_and_contract(client, world, auth_headers, match_factory):
    created = match_factory(world)
    response = _lineup(client, auth_headers(world.owner_a), created, created.rows[:6])
    assert response.status_code == 200
    persisted = MatchPlayer.query.filter_by(match_id=created.match.id).order_by(MatchPlayer.player_number).all()
    assert len(persisted) == 8
    assert sum(row.is_on_court for row in persisted) == 6
    assert all(row.did_play and row.position for row in persisted[:6])
    payload_row = response.get_json()["players"][0]
    assert {"id", "match_id", "player_id", "player_number", "is_called", "did_play", "is_on_court", "position"} <= set(payload_row)


@pytest.mark.parametrize("set_number", [1, 5])
def test_valid_substitution_preserves_six_on_court(
    client, world, auth_headers, match_factory, set_number
):
    created = match_factory(world, on_court_count=6)
    response = client.post(
        f"/api/matches/{created.match.id}/substitutions",
        headers=auth_headers(world.coach_a),
        json={
            "player_out_id": created.rows[0].id,
            "player_in_id": created.rows[6].id,
            "set_number": set_number,
        },
    )
    assert response.status_code == 201
    assert MatchPlayer.query.filter_by(match_id=created.match.id, is_on_court=True).count() == 6
    assert db.session.get(MatchPlayer, created.rows[0].id).is_on_court is False
    incoming = db.session.get(MatchPlayer, created.rows[6].id)
    assert incoming.is_on_court is True and incoming.did_play is True
    assert MatchSubstitution.query.count() == 1
    assert {"id", "match_id", "set_number", "player_out_id", "player_in_id"} <= set(response.get_json()["substitution"])


@pytest.mark.parametrize("set_number", [0, 6])
def test_invalid_substitution_set_is_rejected(
    client, world, auth_headers, match_factory, set_number
):
    created = match_factory(world, on_court_count=6)
    response = client.post(
        f"/api/matches/{created.match.id}/substitutions",
        headers=auth_headers(world.owner_a),
        json={"player_out_id": created.rows[0].id, "player_in_id": created.rows[6].id, "set_number": set_number},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_SET_NUMBER"


@pytest.mark.parametrize(
    "set_number,expected_status",
    [(1, 400), (2, 201), (4, 201), (5, 400)],
)
def test_substitution_uses_adapter_period_range(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
    set_number,
    expected_status,
):
    register_test_period_adapter(
        monkeypatch,
        world,
        period_min=2,
        period_max=4,
    )
    created = match_factory(world, on_court_count=6)

    response = client.post(
        f"/api/matches/{created.match.id}/substitutions",
        headers=auth_headers(world.owner_a),
        json={
            "player_out_id": created.rows[0].id,
            "player_in_id": created.rows[6].id,
            "set_number": set_number,
        },
    )

    assert response.status_code == expected_status

    if expected_status == 400:
        assert response.get_json()["code"] == "INVALID_SET_NUMBER"
    else:
        assert response.get_json()["substitution"]["set_number"] == (
            set_number
        )


@pytest.mark.parametrize(
    "out_index,in_index,code",
    [(6, 7, "PLAYER_OUT_NOT_ON_COURT"), (0, 1, "PLAYER_IN_ALREADY_ON_COURT"), (0, 0, "INVALID_SUBSTITUTION")],
)
def test_invalid_substitution_is_rejected(
    client, world, auth_headers, match_factory, out_index, in_index, code
):
    created = match_factory(world, on_court_count=6)
    response = client.post(
        f"/api/matches/{created.match.id}/substitutions",
        headers=auth_headers(world.owner_a),
        json={"player_out_id": created.rows[out_index].id, "player_in_id": created.rows[in_index].id, "set_number": 1},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == code
