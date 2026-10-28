from src.api.sports.base import (
    PositionDefinition,
    SportAdapter,
    SportCapabilities,
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


class VolleyballAdapter(SportAdapter):
    def __init__(self):
        super().__init__(
            code="VOLLEYBALL",
            name="Voleibol",
            capabilities=VOLLEYBALL_CAPABILITIES,
            positions=VOLLEYBALL_POSITIONS,
        )

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
