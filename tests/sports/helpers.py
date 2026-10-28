from dataclasses import replace

from src.api.models import PlayerMatchStat, db
from src.api.sports import (
    SportAdapter,
    VolleyballAdapter,
    sport_adapter_registry,
)


STAT_FIELDS = [
    "attacks_total", "attacks_positive", "attacks_neutral", "attacks_errors",
    "receptions_total", "receptions_positive", "receptions_neutral", "receptions_negative",
    "defenses_total", "defenses_positive", "defenses_neutral", "defenses_negative",
    "sets_total", "sets_positive", "sets_neutral", "sets_errors",
    "serves_total", "serves_in", "serves_aces", "serves_errors",
    "blocks_total", "blocks_points", "blocks_neutral", "blocks_errors",
]


def event_payload(match, row, action="attack", result="positive", set_number=1):
    return {
        "match_id": match.id,
        "match_player_id": row.id,
        "action_type": action,
        "result": result,
        "set_number": set_number,
    }


def register_test_period_adapter(
    monkeypatch,
    world,
    *,
    period_min,
    period_max,
    supports_periods=True,
):
    code = "TEST_PERIODS"
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code=code,
        name="Deporte de prueba",
        capabilities=replace(
            volleyball.capabilities,
            supports_periods=supports_periods,
            period_min=period_min,
            period_max=period_max,
        ),
        positions=volleyball.positions,
        events=volleyball.events,
    )

    monkeypatch.setitem(
        sport_adapter_registry._adapters,
        code,
        adapter,
    )
    world.sport.code = code
    db.session.commit()

    return adapter


def zero_stats():
    return {field: 0 for field in STAT_FIELDS}


def add_stats(row, **values):
    stat = PlayerMatchStat(match_player_id=row.id)
    for field in STAT_FIELDS:
        setattr(stat, field, values.get(field, 0))
    db.session.add(stat)
    db.session.commit()
    return stat
