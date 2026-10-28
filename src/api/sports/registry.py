from src.api.sports.base import SportAdapter
from src.api.sports.volleyball import VolleyballAdapter


class InvalidSportCodeError(ValueError):
    pass


class SportAdapterNotFoundError(LookupError):
    pass


class DuplicateSportAdapterError(ValueError):
    pass


class InvalidClubSportError(ValueError):
    pass


def _normalize_sport_code(code):
    if not isinstance(code, str) or not code.strip():
        raise InvalidSportCodeError(
            "El código del deporte debe ser un texto no vacío."
        )

    return code.strip().upper()


class SportAdapterRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, adapter):
        if not isinstance(adapter, SportAdapter):
            raise TypeError("El adapter debe cumplir el contrato SportAdapter.")

        code = _normalize_sport_code(adapter.code)

        if code in self._adapters:
            raise DuplicateSportAdapterError(
                f"Ya existe un adapter registrado para {code}."
            )

        self._adapters[code] = adapter

    def has(self, code):
        return _normalize_sport_code(code) in self._adapters

    def get(self, code):
        normalized_code = _normalize_sport_code(code)

        try:
            return self._adapters[normalized_code]
        except KeyError as error:
            raise SportAdapterNotFoundError(
                f"No existe un adapter registrado para {normalized_code}."
            ) from error


sport_adapter_registry = SportAdapterRegistry()
sport_adapter_registry.register(VolleyballAdapter())


def get_sport_adapter(code):
    return sport_adapter_registry.get(code)


def get_club_sport_adapter(club):
    if club is None:
        raise InvalidClubSportError("El Club es obligatorio.")

    sport = getattr(club, "sport", None)

    if sport is None:
        raise InvalidClubSportError("El Club no tiene un deporte asociado.")

    code = getattr(sport, "code", None)

    if not isinstance(code, str) or not code.strip():
        raise InvalidClubSportError(
            "El deporte del Club no tiene un código válido."
        )

    return get_sport_adapter(code)
