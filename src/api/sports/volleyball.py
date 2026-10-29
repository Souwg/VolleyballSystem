from src.api.sports.base import (
    PositionDefinition,
    SportAdapter,
    SportCapabilities,
    SportEventDefinition,
    SummaryStatGroupDefinition,
    ValidatedMatchResult,
)


VOLLEYBALL_CAPABILITIES = SportCapabilities(
    supports_positions=True,
    supports_lineup=True,
    supports_periods=True,
    supports_live_match=True,
    supports_summary_stats=True,
    supports_player_stats=True,
    lineup_size=6,
    period_label="Set",
    period_min=1,
    period_max=5,
)


VOLLEYBALL_POSITIONS = (
    PositionDefinition(code="setter", label="Armador"),
    PositionDefinition(code="outside", label="Punta"),
    PositionDefinition(code="middle", label="Central"),
    PositionDefinition(code="opposite", label="Opuesto"),
    PositionDefinition(code="libero", label="Líbero"),
)


VOLLEYBALL_EVENTS = (
    SportEventDefinition(
        code="attack",
        allowed_results=("positive", "neutral", "error"),
        stat_updates=(
            ("positive", ("attacks_total", "attacks_positive")),
            ("neutral", ("attacks_total", "attacks_neutral")),
            ("error", ("attacks_total", "attacks_errors")),
        ),
    ),
    SportEventDefinition(
        code="reception",
        allowed_results=("positive", "neutral", "negative"),
        stat_updates=(
            ("positive", ("receptions_total", "receptions_positive")),
            ("neutral", ("receptions_total", "receptions_neutral")),
            ("negative", ("receptions_total", "receptions_negative")),
        ),
    ),
    SportEventDefinition(
        code="defense",
        allowed_results=("positive", "neutral", "negative"),
        stat_updates=(
            ("positive", ("defenses_total", "defenses_positive")),
            ("neutral", ("defenses_total", "defenses_neutral")),
            ("negative", ("defenses_total", "defenses_negative")),
        ),
    ),
    SportEventDefinition(
        code="set",
        allowed_results=("positive", "neutral", "error"),
        stat_updates=(
            ("positive", ("sets_total", "sets_positive")),
            ("neutral", ("sets_total", "sets_neutral")),
            ("error", ("sets_total", "sets_errors")),
        ),
    ),
    SportEventDefinition(
        code="serve",
        allowed_results=("ace", "in", "error"),
        stat_updates=(
            ("ace", ("serves_total", "serves_aces")),
            ("in", ("serves_total", "serves_in")),
            ("error", ("serves_total", "serves_errors")),
        ),
    ),
    SportEventDefinition(
        code="block",
        allowed_results=("point", "neutral", "error"),
        stat_updates=(
            ("point", ("blocks_total", "blocks_points")),
            ("neutral", ("blocks_total", "blocks_neutral")),
            ("error", ("blocks_total", "blocks_errors")),
        ),
    ),
)


VOLLEYBALL_SUMMARY_STAT_GROUPS = (
    SummaryStatGroupDefinition(
        total_field="attacks_total",
        component_fields=(
            "attacks_positive",
            "attacks_neutral",
            "attacks_errors",
        ),
        error_code="INVALID_ATTACK_STATS",
    ),
    SummaryStatGroupDefinition(
        total_field="receptions_total",
        component_fields=(
            "receptions_positive",
            "receptions_neutral",
            "receptions_negative",
        ),
        error_code="INVALID_RECEPTION_STATS",
    ),
    SummaryStatGroupDefinition(
        total_field="defenses_total",
        component_fields=(
            "defenses_positive",
            "defenses_neutral",
            "defenses_negative",
        ),
        error_code="INVALID_DEFENSE_STATS",
    ),
    SummaryStatGroupDefinition(
        total_field="sets_total",
        component_fields=(
            "sets_positive",
            "sets_neutral",
            "sets_errors",
        ),
        error_code="INVALID_SET_STATS",
    ),
    SummaryStatGroupDefinition(
        total_field="serves_total",
        component_fields=(
            "serves_in",
            "serves_aces",
            "serves_errors",
        ),
        error_code="INVALID_SERVE_STATS",
    ),
    SummaryStatGroupDefinition(
        total_field="blocks_total",
        component_fields=(
            "blocks_points",
            "blocks_neutral",
            "blocks_errors",
        ),
        error_code="INVALID_BLOCK_STATS",
    ),
)


VOLLEYBALL_PERFORMANCE_METRIC_FIELDS = (
    "actions_total",
    "points_total",
    "errors_total",
    "attack_efficiency",
    "attack_positive_rate",
    "reception_positive_rate",
    "defense_positive_rate",
    "set_positive_rate",
    "serve_ace_rate",
    "block_point_rate",
)


class VolleyballAdapter(SportAdapter):
    def __init__(self):
        super().__init__(
            code="VOLLEYBALL",
            name="Voleibol",
            capabilities=VOLLEYBALL_CAPABILITIES,
            positions=VOLLEYBALL_POSITIONS,
            events=VOLLEYBALL_EVENTS,
            summary_stat_groups=VOLLEYBALL_SUMMARY_STAT_GROUPS,
        )

    def get_performance_stat_fields(self):
        return self.get_summary_stat_fields()

    def get_performance_metric_fields(self):
        return VOLLEYBALL_PERFORMANCE_METRIC_FIELDS

    def calculate_performance_metrics(self, stats):
        if not isinstance(stats, dict):
            raise TypeError

        stat_fields = self.get_performance_stat_fields()

        if any(field not in stats for field in stat_fields):
            raise ValueError

        def percentage(value, total):
            if total <= 0:
                return 0

            return round((value / total) * 100)

        points_total = (
            stats["attacks_positive"]
            + stats["serves_aces"]
            + stats["blocks_points"]
        )

        errors_total = (
            stats["attacks_errors"]
            + stats["sets_errors"]
            + stats["serves_errors"]
            + stats["blocks_errors"]
        )

        actions_total = sum(
            stats[group.total_field]
            for group in self._get_valid_summary_stat_groups()
        )

        attack_efficiency = 0

        if stats["attacks_total"] > 0:
            attack_efficiency = round(
                (
                    (
                        stats["attacks_positive"]
                        - stats["attacks_errors"]
                    )
                    / stats["attacks_total"]
                )
                * 100
            )

        return {
            "actions_total": actions_total,
            "points_total": points_total,
            "errors_total": errors_total,
            "attack_efficiency": attack_efficiency,
            "attack_positive_rate": percentage(
                stats["attacks_positive"],
                stats["attacks_total"],
            ),
            "reception_positive_rate": percentage(
                stats["receptions_positive"],
                stats["receptions_total"],
            ),
            "defense_positive_rate": percentage(
                stats["defenses_positive"],
                stats["defenses_total"],
            ),
            "set_positive_rate": percentage(
                stats["sets_positive"],
                stats["sets_total"],
            ),
            "serve_ace_rate": percentage(
                stats["serves_aces"],
                stats["serves_total"],
            ),
            "block_point_rate": percentage(
                stats["blocks_points"],
                stats["blocks_total"],
            ),
        }

    def validate_match_result(self, home_value, opponent_value):
        def parse_integer_set(value):
            if isinstance(value, bool):
                raise ValueError

            if isinstance(value, int):
                return value

            if isinstance(value, float):
                if not value.is_integer():
                    raise ValueError

                return int(value)

            if isinstance(value, str):
                return int(value)

            raise TypeError

        try:
            home_sets = parse_integer_set(home_value)
            opponent_sets = parse_integer_set(opponent_value)
        except (TypeError, ValueError):
            return None, "Los sets deben ser números enteros"

        if home_sets < 0 or opponent_sets < 0:
            return None, "Los sets no pueden ser negativos"

        if home_sets > 3 or opponent_sets > 3:
            return None, "Ningún equipo puede superar 3 sets"

        if home_sets == opponent_sets:
            return None, "No puede haber empate en sets"

        if max(home_sets, opponent_sets) != 3:
            return None, "Uno de los equipos debe ganar 3 sets"

        if min(home_sets, opponent_sets) > 2:
            return None, "El equipo perdedor no puede superar 2 sets"

        return ValidatedMatchResult(
            home_value=home_sets,
            opponent_value=opponent_sets,
            result=("win" if home_sets > opponent_sets else "loss"),
        ), None
