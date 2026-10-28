from src.api.sports.base import (
    PositionDefinition,
    SportAdapter,
    SportCapabilities,
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
