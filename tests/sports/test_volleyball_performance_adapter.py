from dataclasses import replace

from src.api.models import db
from src.api.sports import (
    SportAdapter,
    VolleyballAdapter,
    sport_adapter_registry,
)
from tests.sports.helpers import add_stats, zero_stats


def get_performance(client, auth_headers, world, player_id):
    return client.get(
        f"/api/players/{player_id}/performance",
        headers=auth_headers(world.owner_a),
    )


def use_adapter(monkeypatch, adapter):
    monkeypatch.setitem(
        sport_adapter_registry._adapters,
        "VOLLEYBALL",
        adapter,
    )


def test_volleyball_performance_fields_match_live_and_summary():
    adapter = VolleyballAdapter()

    assert set(adapter.get_performance_stat_fields()) == set(
        adapter.get_summary_stat_fields()
    ) == set(adapter.get_event_stat_fields())


def test_volleyball_performance_metrics_preserve_realistic_formulas():
    stats = zero_stats()
    stats.update({
        "attacks_total": 3,
        "attacks_positive": 2,
        "attacks_errors": 1,
        "receptions_total": 3,
        "receptions_positive": 2,
        "receptions_negative": 1,
        "defenses_total": 3,
        "defenses_positive": 1,
        "defenses_neutral": 1,
        "defenses_negative": 1,
        "sets_total": 6,
        "sets_positive": 1,
        "sets_neutral": 4,
        "sets_errors": 1,
        "serves_total": 6,
        "serves_in": 3,
        "serves_aces": 1,
        "serves_errors": 2,
        "blocks_total": 6,
        "blocks_points": 1,
        "blocks_neutral": 3,
        "blocks_errors": 2,
    })

    assert VolleyballAdapter().calculate_performance_metrics(stats) == {
        "actions_total": 27,
        "points_total": 4,
        "errors_total": 6,
        "attack_efficiency": 33,
        "attack_positive_rate": 67,
        "reception_positive_rate": 67,
        "defense_positive_rate": 33,
        "set_positive_rate": 17,
        "serve_ace_rate": 17,
        "block_point_rate": 17,
    }


def test_volleyball_performance_zero_denominators_are_zero():
    assert VolleyballAdapter().calculate_performance_metrics(
        zero_stats()
    ) == {
        "actions_total": 0,
        "points_total": 0,
        "errors_total": 0,
        "attack_efficiency": 0,
        "attack_positive_rate": 0,
        "reception_positive_rate": 0,
        "defense_positive_rate": 0,
        "set_positive_rate": 0,
        "serve_ace_rate": 0,
        "block_point_rate": 0,
    }


def test_completed_matches_keep_historical_aggregation(
    client,
    world,
    auth_headers,
    match_factory,
):
    first = match_factory(
        world,
        on_court_count=1,
        is_completed=True,
    )
    second = match_factory(
        world,
        on_court_count=1,
        is_completed=True,
    )
    add_stats(
        first.rows[0],
        attacks_total=1,
        attacks_positive=1,
    )
    add_stats(
        second.rows[0],
        serves_total=1,
        serves_aces=1,
    )

    response = get_performance(
        client,
        auth_headers,
        world,
        first.rows[0].player_id,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["matches_played"] == 2
    assert data["summary"]["matches_with_stats"] == 2
    assert data["summary"]["actions_total"] == 2
    assert data["summary"]["points_total"] == 2


def test_endpoint_uses_alternate_adapter_performance_formula(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    class AlternatePerformanceAdapter(VolleyballAdapter):
        def calculate_performance_metrics(self, stats):
            metrics = super().calculate_performance_metrics(stats)
            metrics["points_total"] = (
                stats["attacks_positive"] * 10
            )
            return metrics

    use_adapter(monkeypatch, AlternatePerformanceAdapter())
    created = match_factory(
        world,
        on_court_count=1,
        is_completed=True,
    )
    add_stats(
        created.rows[0],
        attacks_total=2,
        attacks_positive=2,
    )

    response = get_performance(
        client,
        auth_headers,
        world,
        created.rows[0].player_id,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["points_total"] == 20
    assert data["official_matches"][0]["points_total"] == 20


def test_adapter_without_performance_support_fails_explicitly(
    client,
    world,
    auth_headers,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="VOLLEYBALL",
        name="Sin Performance",
        capabilities=replace(
            volleyball.capabilities,
            supports_player_stats=False,
        ),
        positions=volleyball.positions,
        events=volleyball.events,
        summary_stat_groups=volleyball.summary_stat_groups,
    )
    use_adapter(monkeypatch, adapter)

    response = get_performance(
        client,
        auth_headers,
        world,
        world.players_a[0].id,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "PLAYER_PERFORMANCE_NOT_SUPPORTED"
    )


def test_adapter_with_invalid_performance_result_fails_without_mutation(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    class InvalidPerformanceAdapter(VolleyballAdapter):
        def calculate_performance_metrics(self, stats):
            return {"points_total": 1}

    use_adapter(monkeypatch, InvalidPerformanceAdapter())
    created = match_factory(
        world,
        on_court_count=1,
        is_completed=True,
    )
    stat = add_stats(
        created.rows[0],
        attacks_total=1,
        attacks_positive=1,
    )
    before = stat.serialize()

    response = get_performance(
        client,
        auth_headers,
        world,
        created.rows[0].player_id,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "PLAYER_PERFORMANCE_NOT_SUPPORTED"
    )
    db.session.refresh(stat)
    assert stat.serialize() == before


def test_missing_adapter_fails_explicitly(
    client,
    world,
    auth_headers,
    monkeypatch,
):
    monkeypatch.delitem(
        sport_adapter_registry._adapters,
        "VOLLEYBALL",
    )

    response = get_performance(
        client,
        auth_headers,
        world,
        world.players_a[0].id,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "PLAYER_PERFORMANCE_NOT_SUPPORTED"
    )
