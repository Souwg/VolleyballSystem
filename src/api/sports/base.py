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
class SummaryStatGroupDefinition:
    total_field: str
    component_fields: tuple[str, ...]
    error_code: str


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
    summary_stat_groups: tuple[SummaryStatGroupDefinition, ...] = ()

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

    def _get_valid_summary_stat_groups(self):
        if (
            not self.capabilities.supports_summary_stats
            or not self.summary_stat_groups
        ):
            raise NotImplementedError

        used_fields = set()

        for group in self.summary_stat_groups:
            if not isinstance(group, SummaryStatGroupDefinition):
                raise ValueError

            if (
                not isinstance(group.total_field, str)
                or not group.total_field.strip()
                or not isinstance(group.component_fields, tuple)
                or not group.component_fields
                or not isinstance(group.error_code, str)
                or not group.error_code.strip()
            ):
                raise ValueError

            group_fields = (
                group.total_field,
                *group.component_fields,
            )

            if any(
                not isinstance(field, str) or not field.strip()
                for field in group_fields
            ):
                raise ValueError

            if (
                len(set(group_fields)) != len(group_fields)
                or used_fields.intersection(group_fields)
            ):
                raise ValueError

            used_fields.update(group_fields)

        return self.summary_stat_groups

    def get_summary_stat_fields(self):
        fields = []

        for group in self._get_valid_summary_stat_groups():
            fields.append(group.total_field)
            fields.extend(group.component_fields)

        return tuple(fields)

    def validate_summary_stats(self, payload):
        groups = self._get_valid_summary_stat_groups()

        def to_int(value):
            try:
                return max(0, int(value))
            except:
                return 0

        stats = {
            field: to_int(payload.get(field))
            for field in self.get_summary_stat_fields()
        }

        for group in groups:
            if stats[group.total_field] != sum(
                stats[field]
                for field in group.component_fields
            ):
                return None, group.error_code

        return stats, None

    def get_performance_stat_fields(self):
        raise NotImplementedError

    def get_performance_metric_fields(self):
        raise NotImplementedError

    def calculate_performance_metrics(self, stats):
        raise NotImplementedError
