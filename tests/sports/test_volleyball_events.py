import pytest

from src.api.models import MatchEvent, PlayerMatchStat, db
from src.api.sports import (
    SportAdapter,
    SportEventDefinition,
    VolleyballAdapter,
    sport_adapter_registry,
)
from tests.sports.helpers import (
    STAT_FIELDS,
    event_payload,
    register_test_period_adapter,
)


EVENT_CASES = [
    ("attack", "positive", "attacks_total", "attacks_positive"),
    ("attack", "neutral", "attacks_total", "attacks_neutral"),
    ("attack", "error", "attacks_total", "attacks_errors"),
    ("reception", "positive", "receptions_total", "receptions_positive"),
    ("reception", "neutral", "receptions_total", "receptions_neutral"),
    ("reception", "negative", "receptions_total", "receptions_negative"),
    ("defense", "positive", "defenses_total", "defenses_positive"),
    ("defense", "neutral", "defenses_total", "defenses_neutral"),
    ("defense", "negative", "defenses_total", "defenses_negative"),
    ("set", "positive", "sets_total", "sets_positive"),
    ("set", "neutral", "sets_total", "sets_neutral"),
    ("set", "error", "sets_total", "sets_errors"),
    ("serve", "ace", "serves_total", "serves_aces"),
    ("serve", "in", "serves_total", "serves_in"),
    ("serve", "error", "serves_total", "serves_errors"),
    ("block", "point", "blocks_total", "blocks_points"),
    ("block", "neutral", "blocks_total", "blocks_neutral"),
    ("block", "error", "blocks_total", "blocks_errors"),
]


def register_event_adapter(monkeypatch, world, adapter):
    monkeypatch.setitem(
        sport_adapter_registry._adapters,
        adapter.code,
        adapter,
    )
    world.sport.code = adapter.code
    db.session.commit()


def test_volleyball_event_catalog_is_frozen():
    adapter = VolleyballAdapter()

    assert tuple(
        (event.code, event.allowed_results)
        for event in adapter.events
    ) == (
        ("attack", ("positive", "neutral", "error")),
        ("reception", ("positive", "neutral", "negative")),
        ("defense", ("positive", "neutral", "negative")),
        ("set", ("positive", "neutral", "error")),
        ("serve", ("ace", "in", "error")),
        ("block", ("point", "neutral", "error")),
    )


@pytest.mark.parametrize("action,result,total_field,result_field", EVENT_CASES)
def test_each_event_updates_exact_counters(
    client, world, auth_headers, match_factory, action, result, total_field, result_field
):
    created = match_factory(world, on_court_count=1)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0], action, result),
    )
    assert response.status_code == 201
    event = response.get_json()["event"]
    assert {"id", "match_id", "match_player_id", "action_type", "result", "set_number", "created_at"} <= set(event)
    stat = PlayerMatchStat.query.filter_by(match_player_id=created.rows[0].id).one()
    nonzero = {field: getattr(stat, field) for field in STAT_FIELDS if getattr(stat, field)}
    assert nonzero == {total_field: 1, result_field: 1}


@pytest.mark.parametrize(
    "payload_change,expected_code",
    [
        ({"action_type": "dig"}, "INVALID_EVENT_ACTION"),
        ({"result": "ace"}, "INVALID_EVENT_RESULT"),
        ({"set_number": 0}, "INVALID_SET_NUMBER"),
        ({"set_number": 6}, "INVALID_SET_NUMBER"),
    ],
)
def test_invalid_event_payload_is_rejected(
    client, world, auth_headers, match_factory, payload_change, expected_code
):
    created = match_factory(world, on_court_count=1)
    payload = event_payload(created.match, created.rows[0])
    payload.update(payload_change)
    response = client.post("/api/match-events", headers=auth_headers(world.owner_a), json=payload)
    assert response.status_code == 400
    assert response.get_json()["code"] == expected_code


@pytest.mark.parametrize("set_number", [1, 5])
def test_event_accepts_boundary_sets(
    client, world, auth_headers, match_factory, set_number
):
    created = match_factory(world, on_court_count=1)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(
            created.match, created.rows[0], "serve", "in", set_number
        ),
    )
    assert response.status_code == 201
    assert response.get_json()["event"]["set_number"] == set_number


@pytest.mark.parametrize(
    "set_number,expected_status",
    [(1, 400), (2, 201), (4, 201), (5, 400)],
)
def test_event_uses_adapter_period_range(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
    set_number,
    expected_status,
):
    adapter = register_test_period_adapter(
        monkeypatch,
        world,
        period_min=2,
        period_max=4,
    )
    created = match_factory(world, on_court_count=1)

    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(
            created.match,
            created.rows[0],
            "serve",
            "in",
            set_number,
        ),
    )

    assert adapter.capabilities.period_min == 2
    assert adapter.capabilities.period_max == 4
    assert response.status_code == expected_status

    if expected_status == 400:
        assert response.get_json()["code"] == "INVALID_SET_NUMBER"
    else:
        assert response.get_json()["event"]["set_number"] == set_number


def test_event_defaults_to_adapter_period_min(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    register_test_period_adapter(
        monkeypatch,
        world,
        period_min=2,
        period_max=4,
    )
    created = match_factory(world, on_court_count=1)
    payload = event_payload(created.match, created.rows[0])
    payload.pop("set_number")

    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=payload,
    )

    assert response.status_code == 201
    assert response.get_json()["event"]["set_number"] == 2


def test_event_missing_adapter_does_not_fallback_to_volleyball_events(
    client,
    world,
    auth_headers,
    match_factory,
):
    world.sport.code = "UNREGISTERED"
    db.session.commit()
    created = match_factory(world, on_court_count=1)

    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_EVENT_RULES_NOT_SUPPORTED"


def test_adapter_without_event_support_fails_explicitly(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_NO_EVENTS",
        name="Deporte sin eventos",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
    )
    register_event_adapter(monkeypatch, world, adapter)
    created = match_factory(world, on_court_count=1)

    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_EVENT_RULES_NOT_SUPPORTED"
    assert MatchEvent.query.count() == 0


def test_event_endpoint_uses_club_sport_adapter_catalog(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_EVENTS",
        name="Deporte de prueba",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
        events=(
            SportEventDefinition(
                code="goal",
                allowed_results=("scored", "missed"),
            ),
        ),
    )
    register_event_adapter(monkeypatch, world, adapter)
    created = match_factory(world, on_court_count=1)
    headers = auth_headers(world.owner_a)

    for result in ["scored", "missed"]:
        response = client.post(
            "/api/match-events",
            headers=headers,
            json=event_payload(
                created.match,
                created.rows[0],
                "goal",
                result,
            ),
        )
        assert response.status_code == 201
        assert response.get_json()["event"]["result"] == result

    invalid_action = client.post(
        "/api/match-events",
        headers=headers,
        json=event_payload(
            created.match,
            created.rows[0],
            "attack",
            "positive",
        ),
    )
    assert invalid_action.status_code == 400
    assert invalid_action.get_json()["code"] == "INVALID_EVENT_ACTION"

    invalid_result = client.post(
        "/api/match-events",
        headers=headers,
        json=event_payload(
            created.match,
            created.rows[0],
            "goal",
            "blocked",
        ),
    )
    assert invalid_result.status_code == 400
    assert invalid_result.get_json()["code"] == "INVALID_EVENT_RESULT"
    assert MatchEvent.query.count() == 2


@pytest.mark.parametrize(
    "supports_periods,period_min,period_max",
    [(False, 1, 5), (True, 5, 1), (True, True, 5)],
)
def test_invalid_period_capabilities_fail_explicitly(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
    supports_periods,
    period_min,
    period_max,
):
    register_test_period_adapter(
        monkeypatch,
        world,
        supports_periods=supports_periods,
        period_min=period_min,
        period_max=period_max,
    )
    created = match_factory(world, on_court_count=1)

    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_PERIODS_NOT_SUPPORTED"


def test_event_for_bench_player_is_rejected(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[1]),
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "PLAYER_NOT_ON_COURT"


def test_completed_match_rejects_new_event(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1, is_completed=True)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_COMPLETED"


def test_cross_tenant_event_is_rejected(client, world, auth_headers, match_factory):
    created = match_factory(world, tenant="b", on_court_count=1)
    response = client.post(
        "/api/match-events",
        headers=auth_headers(world.owner_a),
        json=event_payload(created.match, created.rows[0]),
    )
    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"


def test_deleting_event_recalculates_without_stale_counters(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, on_court_count=1)
    headers = auth_headers(world.owner_a)
    first = client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0], "attack", "positive"),
    ).get_json()["event"]
    client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0], "serve", "ace"),
    )
    response = client.delete(f"/api/match-events/{first['id']}", headers=headers)
    assert response.status_code == 200
    assert MatchEvent.query.count() == 1
    stat = PlayerMatchStat.query.filter_by(match_player_id=created.rows[0].id).one()
    assert stat.attacks_total == stat.attacks_positive == 0
    assert stat.serves_total == stat.serves_aces == 1


def test_live_undo_updates_provisional_performance(client, world, auth_headers, match_factory):
    created = match_factory(world, on_court_count=1)
    headers = auth_headers(world.owner_a)
    first = client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0], "attack", "positive"),
    ).get_json()["event"]
    client.post(
        "/api/match-events", headers=headers,
        json=event_payload(created.match, created.rows[0], "block", "point"),
    )
    client.delete(f"/api/match-events/{first['id']}", headers=headers)
    response = client.get(
        f"/api/players/{created.rows[0].player_id}/performance", headers=headers
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["points_total"] == 0
    assert data["provisional_matches"][0]["points_total"] == 1
    assert data["provisional_matches"][0]["stats"]["attacks_total"] == 0
    assert data["provisional_matches"][0]["stats"]["blocks_points"] == 1
