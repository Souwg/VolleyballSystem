from dataclasses import replace

import pytest

from src.api.models import PlayerMatchStat, db
from src.api.sports import (
    SportAdapter,
    SummaryStatGroupDefinition,
    VolleyballAdapter,
    sport_adapter_registry,
)
from tests.sports.helpers import STAT_FIELDS, zero_stats


INVALID_GROUP_CASES = (
    ("attacks_total", "INVALID_ATTACK_STATS"),
    ("receptions_total", "INVALID_RECEPTION_STATS"),
    ("defenses_total", "INVALID_DEFENSE_STATS"),
    ("sets_total", "INVALID_SET_STATS"),
    ("serves_total", "INVALID_SERVE_STATS"),
    ("blocks_total", "INVALID_BLOCK_STATS"),
)


def register_summary_adapter(monkeypatch, world, adapter):
    monkeypatch.setitem(
        sport_adapter_registry._adapters,
        adapter.code,
        adapter,
    )
    world.sport.code = adapter.code
    db.session.commit()


def post_summary_stats(client, auth_headers, world, row, payload):
    return client.post(
        f"/api/match-players/{row.id}/stats",
        headers=auth_headers(world.owner_a),
        json=payload,
    )


def test_volleyball_summary_groups_are_frozen():
    adapter = VolleyballAdapter()

    assert tuple(
        (
            group.total_field,
            group.component_fields,
            group.error_code,
        )
        for group in adapter.summary_stat_groups
    ) == (
        (
            "attacks_total",
            ("attacks_positive", "attacks_neutral", "attacks_errors"),
            "INVALID_ATTACK_STATS",
        ),
        (
            "receptions_total",
            (
                "receptions_positive",
                "receptions_neutral",
                "receptions_negative",
            ),
            "INVALID_RECEPTION_STATS",
        ),
        (
            "defenses_total",
            ("defenses_positive", "defenses_neutral", "defenses_negative"),
            "INVALID_DEFENSE_STATS",
        ),
        (
            "sets_total",
            ("sets_positive", "sets_neutral", "sets_errors"),
            "INVALID_SET_STATS",
        ),
        (
            "serves_total",
            ("serves_in", "serves_aces", "serves_errors"),
            "INVALID_SERVE_STATS",
        ),
        (
            "blocks_total",
            ("blocks_points", "blocks_neutral", "blocks_errors"),
            "INVALID_BLOCK_STATS",
        ),
    )


def test_volleyball_live_and_summary_stat_fields_are_consistent():
    adapter = VolleyballAdapter()

    assert set(adapter.get_event_stat_fields()) == set(
        adapter.get_summary_stat_fields()
    ) == set(STAT_FIELDS)


@pytest.mark.parametrize("total_field,error_code", INVALID_GROUP_CASES)
def test_each_summary_group_inconsistency_is_rejected_without_partial_write(
    client,
    world,
    auth_headers,
    match_factory,
    total_field,
    error_code,
):
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )
    existing = PlayerMatchStat(
        match_player_id=created.rows[0].id,
        attacks_total=2,
        attacks_positive=2,
    )
    db.session.add(existing)
    db.session.commit()
    payload = zero_stats()
    payload[total_field] = 1

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        payload,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == error_code
    db.session.refresh(existing)
    assert existing.attacks_total == 2
    assert existing.attacks_positive == 2


def test_summary_validation_preserves_first_error_order(
    client, world, auth_headers, match_factory
):
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )
    payload = zero_stats()
    payload["attacks_total"] = 1
    payload["receptions_total"] = 1

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        payload,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_ATTACK_STATS"
    assert PlayerMatchStat.query.count() == 0


def test_empty_summary_payload_normalizes_to_all_zeroes():
    stats, error = VolleyballAdapter().validate_summary_stats({})

    assert error is None
    assert stats == {
        field: 0
        for field in STAT_FIELDS
    }


def test_summary_normalization_preserves_historical_contract():
    large_value = 999999
    stats, error = VolleyballAdapter().validate_summary_stats({
        "attacks_total": "2",
        "attacks_positive": "2",
        "receptions_total": "not-a-number",
        "defenses_total": -4,
        "sets_total": large_value,
        "sets_positive": large_value,
        "unknown_field": 17,
    })

    assert error is None
    assert stats["attacks_total"] == 2
    assert stats["attacks_positive"] == 2
    assert stats["attacks_neutral"] == 0
    assert stats["receptions_total"] == 0
    assert stats["defenses_total"] == 0
    assert stats["sets_total"] == large_value
    assert stats["sets_positive"] == large_value
    assert "unknown_field" not in stats


def test_summary_endpoint_uses_alternate_adapter_metadata(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_SUMMARY",
        name="Deporte Summary de prueba",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
        summary_stat_groups=(
            SummaryStatGroupDefinition(
                total_field="attacks_total",
                component_fields=(
                    "attacks_positive",
                    "attacks_errors",
                ),
                error_code="INVALID_TEST_SUMMARY_STATS",
            ),
        ),
    )
    register_summary_adapter(monkeypatch, world, adapter)
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        {
            "attacks_total": 2,
            "attacks_positive": 1,
            "attacks_errors": 1,
            "attacks_neutral": 99,
        },
    )

    assert response.status_code == 200
    stat = PlayerMatchStat.query.filter_by(
        match_player_id=created.rows[0].id
    ).one()
    assert stat.attacks_total == 2
    assert stat.attacks_positive == 1
    assert stat.attacks_errors == 1
    assert stat.attacks_neutral == 0


def test_adapter_without_summary_support_fails_before_write(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_NO_SUMMARY",
        name="Deporte sin Summary",
        capabilities=replace(
            volleyball.capabilities,
            supports_summary_stats=False,
        ),
        positions=volleyball.positions,
        summary_stat_groups=volleyball.summary_stat_groups,
    )
    register_summary_adapter(monkeypatch, world, adapter)
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        zero_stats(),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "MATCH_SUMMARY_STATS_NOT_SUPPORTED"
    )
    assert PlayerMatchStat.query.count() == 0


def test_adapter_without_summary_metadata_fails_before_write(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_EMPTY_SUMMARY",
        name="Deporte sin metadata Summary",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
    )
    register_summary_adapter(monkeypatch, world, adapter)
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        zero_stats(),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "MATCH_SUMMARY_STATS_NOT_SUPPORTED"
    )
    assert PlayerMatchStat.query.count() == 0


def test_invalid_summary_metadata_fails_before_write(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_INVALID_SUMMARY",
        name="Deporte con metadata Summary inválida",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
        summary_stat_groups=(
            SummaryStatGroupDefinition(
                total_field="attacks_total",
                component_fields=(
                    "attacks_total",
                    "attacks_positive",
                ),
                error_code="INVALID_TEST_SUMMARY_STATS",
            ),
        ),
    )
    register_summary_adapter(monkeypatch, world, adapter)
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        zero_stats(),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "MATCH_SUMMARY_STATS_NOT_SUPPORTED"
    )
    assert PlayerMatchStat.query.count() == 0


def test_unknown_summary_model_field_fails_before_write(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_UNKNOWN_FIELD",
        name="Deporte con campo Summary desconocido",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
        summary_stat_groups=(
            SummaryStatGroupDefinition(
                total_field="unknown_total",
                component_fields=("attacks_positive",),
                error_code="INVALID_TEST_SUMMARY_STATS",
            ),
        ),
    )
    register_summary_adapter(monkeypatch, world, adapter)
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        zero_stats(),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "MATCH_SUMMARY_STATS_NOT_SUPPORTED"
    )
    assert PlayerMatchStat.query.count() == 0


def test_missing_sport_adapter_fails_before_write(
    client,
    world,
    auth_headers,
    match_factory,
):
    world.sport.code = "UNREGISTERED_SUMMARY"
    db.session.commit()
    created = match_factory(
        world,
        capture_mode="summary",
        did_play=True,
    )

    response = post_summary_stats(
        client,
        auth_headers,
        world,
        created.rows[0],
        zero_stats(),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == (
        "MATCH_SUMMARY_STATS_NOT_SUPPORTED"
    )
    assert PlayerMatchStat.query.count() == 0
