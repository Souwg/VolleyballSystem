import pytest

from src.api.models import MatchPlayer, MatchSubstitution, db


def _lineup(client, headers, created, rows):
    return client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=headers,
        json={"players": [row.id for row in rows]},
    )


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
