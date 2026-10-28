from dataclasses import dataclass


@dataclass(frozen=True)
class SportCapabilities:
    supports_positions: bool
    supports_lineup: bool
    supports_periods: bool
    supports_live_match: bool
    supports_summary_stats: bool
    supports_player_stats: bool
    lineup_size: int
    period_label: str
    period_min: int
    period_max: int


@dataclass(frozen=True)
class PositionDefinition:
    code: str
    label: str


@dataclass(frozen=True)
class ValidatedMatchResult:
    home_value: int
    opponent_value: int
    result: str


@dataclass(frozen=True)
class SportAdapter:
    code: str
    name: str
    capabilities: SportCapabilities
    positions: tuple[PositionDefinition, ...]

    def has_position(self, code):
        return self.get_position(code) is not None

    def get_position(self, code):
        return next(
            (
                position
                for position in self.positions
                if position.code == code
            ),
            None
        )

    def validate_match_result(self, home_value, opponent_value):
        raise NotImplementedError
