from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from src.api.sports import (
    DuplicateSportAdapterError,
    InvalidClubSportError,
    InvalidSportCodeError,
    PositionDefinition,
    SportAdapter,
    SportAdapterNotFoundError,
    SportAdapterRegistry,
    SportCapabilities,
    VolleyballAdapter,
    get_club_sport_adapter,
    get_sport_adapter,
    sport_adapter_registry,
)


EXPECTED_POSITIONS = (
    ("setter", "Armador"),
    ("outside", "Punta"),
    ("middle", "Central"),
    ("opposite", "Opuesto"),
    ("libero", "Líbero"),
)


def test_volleyball_adapter_contract_and_metadata():
    adapter = VolleyballAdapter()

    assert isinstance(adapter, SportAdapter)
    assert adapter.code == "VOLLEYBALL"
    assert adapter.name == "Voleibol"
    assert isinstance(adapter.capabilities, SportCapabilities)
    assert all(
        isinstance(position, PositionDefinition)
        for position in adapter.positions
    )


def test_volleyball_capabilities_are_correct():
    capabilities = VolleyballAdapter().capabilities

    assert capabilities.supports_positions is True
    assert capabilities.supports_lineup is True
    assert capabilities.supports_periods is True
    assert capabilities.supports_live_match is True
    assert capabilities.supports_summary_stats is True
    assert capabilities.supports_player_stats is True
    assert capabilities.lineup_size == 6
    assert capabilities.period_label == "Set"
    assert capabilities.period_min == 1
    assert capabilities.period_max == 5


def test_volleyball_positions_have_exact_codes_labels_and_order():
    adapter = VolleyballAdapter()

    assert tuple(
        (position.code, position.label)
        for position in adapter.positions
    ) == EXPECTED_POSITIONS


def test_volleyball_position_definitions_are_immutable():
    position = VolleyballAdapter().positions[0]

    with pytest.raises(FrozenInstanceError):
        position.label = "Otro"


@pytest.mark.parametrize("code,_label", EXPECTED_POSITIONS)
def test_volleyball_adapter_recognizes_each_position(code, _label):
    adapter = VolleyballAdapter()

    assert adapter.has_position(code) is True
    assert adapter.get_position(code).code == code


def test_volleyball_adapter_rejects_unknown_position():
    adapter = VolleyballAdapter()

    assert adapter.has_position("goalkeeper") is False
    assert adapter.get_position("goalkeeper") is None


def test_volleyball_resolves_from_registry():
    adapter = get_sport_adapter("VOLLEYBALL")

    assert isinstance(adapter, VolleyballAdapter)
    assert sport_adapter_registry.has("VOLLEYBALL") is True


def test_two_volleyball_clubs_resolve_stateless_adapter(world):
    first = get_club_sport_adapter(world.club_a)
    second = get_club_sport_adapter(world.club_b)

    assert first is second
    assert isinstance(first, VolleyballAdapter)
    assert set(first.__dict__) == {
        "code",
        "name",
        "capabilities",
        "positions",
        "events",
        "summary_stat_groups",
    }


@pytest.mark.parametrize("code", ["FOOTBALL", "BASEBALL", "UNKNOWN"])
def test_unregistered_sports_fail_without_volleyball_fallback(code):
    assert sport_adapter_registry.has(code) is False

    with pytest.raises(SportAdapterNotFoundError):
        get_sport_adapter(code)


@pytest.mark.parametrize("code", [None, "", "   "])
def test_empty_or_missing_sport_code_fails(code):
    with pytest.raises(InvalidSportCodeError):
        get_sport_adapter(code)


def test_duplicate_registration_fails_explicitly():
    registry = SportAdapterRegistry()
    registry.register(VolleyballAdapter())

    with pytest.raises(DuplicateSportAdapterError):
        registry.register(VolleyballAdapter())


@pytest.mark.parametrize(
    "club",
    [
        None,
        SimpleNamespace(sport=None),
        SimpleNamespace(sport=SimpleNamespace(code=None)),
        SimpleNamespace(sport=SimpleNamespace(code="")),
    ],
)
def test_invalid_club_sport_relationship_fails_clearly(club):
    with pytest.raises(InvalidClubSportError):
        get_club_sport_adapter(club)
