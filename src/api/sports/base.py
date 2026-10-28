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
class SportEventDefinition:
    code: str
    allowed_results: tuple[str, ...]
    stat_updates: tuple[tuple[str, tuple[str, ...]], ...] = ()


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
    events: tuple[SportEventDefinition, ...] = ()

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

    def get_event_definition(self, code):
        return next(
            (
                event
                for event in self.events
                if event.code == code
            ),
            None
        )

    def validate_event(self, code, result):
        if not self.events:
            raise NotImplementedError

        event = self.get_event_definition(code)

        if event is None:
            return False, False

        return True, result in event.allowed_results

    def get_event_stat_updates(self, code, result):
        event = self.get_event_definition(code)

        if event is None or result not in event.allowed_results:
            raise LookupError

        updates = next(
            (
                fields
                for mapped_result, fields in event.stat_updates
                if mapped_result == result
            ),
            None
        )

        if not updates:
            raise NotImplementedError

        return updates

    def get_event_stat_fields(self):
        if not self.events:
            raise NotImplementedError

        fields = []

        for event in self.events:
            for result in event.allowed_results:
                for field in self.get_event_stat_updates(
                    event.code,
                    result,
                ):
                    if field not in fields:
                        fields.append(field)

        return tuple(fields)
