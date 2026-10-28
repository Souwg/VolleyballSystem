from src.api.models import MatchSession, db
from tests.sports.helpers import add_stats


def _get_performance(client, headers, player_id):
    return client.get(f"/api/players/{player_id}/performance", headers=headers)


def test_open_match_is_provisional_only(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1)
    add_stats(created.rows[0], attacks_total=1, attacks_positive=1)
    response = _get_performance(client, auth_headers(world.owner_a), created.rows[0].player_id)
    data = response.get_json()
    assert response.status_code == 200
    assert len(data["matches"]) == 1
    assert len(data["provisional_matches"]) == 1
    assert data["official_matches"] == []
    assert data["summary"]["matches_played"] == 0
    assert data["summary"]["points_total"] == 0


def test_completed_match_is_official(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1, is_completed=True)
    add_stats(created.rows[0], attacks_total=1, attacks_positive=1)
    data = _get_performance(
        client, auth_headers(world.coach_a), created.rows[0].player_id
    ).get_json()
    assert len(data["official_matches"]) == 1
    assert data["provisional_matches"] == []
    assert data["summary"]["matches_played"] == 1
    assert data["summary"]["points_total"] == 1


def test_open_match_does_not_contaminate_official_totals(
    client, world, auth_headers, match_factory
):
    open_match = match_factory(world, on_court_count=1)
    official = match_factory(world, on_court_count=1, is_completed=True)
    add_stats(open_match.rows[0], attacks_total=4, attacks_positive=4)
    add_stats(official.rows[0], attacks_total=2, attacks_positive=1)
    data = _get_performance(
        client, auth_headers(world.staff_a), world.players_a[0].id
    ).get_json()
    assert len(data["matches"]) == 2
    assert len(data["official_matches"]) == 1
    assert len(data["provisional_matches"]) == 1
    assert data["totals"]["attacks_total"] == 2
    assert data["summary"]["points_total"] == 1


def test_performance_formulas_and_rounding(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1, is_completed=True)
    match = db.session.get(MatchSession, created.match.id)
    match.home_sets = 3
    match.opponent_sets = 2
    match.result = "win"
    db.session.commit()
    add_stats(
        created.rows[0],
        attacks_total=4, attacks_positive=3, attacks_errors=1,
        receptions_total=4, receptions_positive=2,
        defenses_total=5, defenses_positive=3,
        sets_total=4, sets_positive=3, sets_errors=1,
        serves_total=5, serves_aces=2, serves_errors=1,
        blocks_total=4, blocks_points=2, blocks_errors=1,
    )
    data = _get_performance(
        client, auth_headers(world.owner_a), created.rows[0].player_id
    ).get_json()
    summary = data["summary"]
    assert summary == {
        "matches_played": 1,
        "matches_with_stats": 1,
        "actions_total": 26,
        "points_total": 7,
        "errors_total": 4,
        "attack_efficiency": 50,
        "attack_positive_rate": 75,
        "reception_positive_rate": 50,
        "defense_positive_rate": 60,
        "set_positive_rate": 75,
        "serve_ace_rate": 40,
        "block_point_rate": 50,
    }
    match_data = data["official_matches"][0]
    assert match_data["result"] == "win"
    assert match_data["home_sets"] == 3 and match_data["opponent_sets"] == 2
    assert match_data["position"] == "setter"


def test_zero_denominators_return_zero(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1, is_completed=True)
    add_stats(created.rows[0])
    summary = _get_performance(
        client, auth_headers(world.owner_a), created.rows[0].player_id
    ).get_json()["summary"]
    for key in [
        "attack_efficiency", "attack_positive_rate", "reception_positive_rate",
        "defense_positive_rate", "set_positive_rate", "serve_ace_rate", "block_point_rate",
    ]:
        assert summary[key] == 0


def test_performance_contract_has_essential_fields(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1, is_completed=True)
    add_stats(created.rows[0])
    data = _get_performance(
        client, auth_headers(world.owner_a), created.rows[0].player_id
    ).get_json()
    assert {"player", "summary", "totals", "matches", "official_matches", "provisional_matches"} <= set(data)
    assert {"id", "first_name", "last_name", "main_position"} <= set(data["player"])
    assert {"match_id", "match_player_id", "team", "stats", "points_total", "errors_total", "is_completed"} <= set(data["matches"][0])
