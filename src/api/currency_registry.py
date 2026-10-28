from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


@dataclass(frozen=True)
class CurrencyDefinition:
    code: str
    name: str

    def serialize(self):
        return {
            "code": self.code,
            "name": self.name
        }


# Orden canónico y determinista por código.
SUPPORTED_CURRENCIES = (
    CurrencyDefinition(code="COP", name="Peso colombiano"),
    CurrencyDefinition(code="USD", name="Dólar estadounidense"),
    CurrencyDefinition(code="VES", name="Bolívar venezolano"),
)

_SUPPORTED_CURRENCIES_BY_CODE = {
    currency.code: currency
    for currency in SUPPORTED_CURRENCIES
}


def normalize_currency_code(value):
    """Devuelve el código canónico si SportFlow soporta la moneda."""
    if not isinstance(value, str):
        return None

    normalized_code = value.strip().upper()

    if normalized_code not in _SUPPORTED_CURRENCIES_BY_CODE:
        return None

    return normalized_code


def is_supported_currency(value):
    return normalize_currency_code(value) is not None


def get_currency_definition(value):
    normalized_code = normalize_currency_code(value)

    if not normalized_code:
        return None

    return _SUPPORTED_CURRENCIES_BY_CODE[normalized_code]


def serialize_supported_currencies():
    return [
        currency.serialize()
        for currency in SUPPORTED_CURRENCIES
    ]


def format_money(amount, currency_code):
    """Formatea un importe identificando siempre la moneda por su código."""
    if amount is None:
        return "No registrado"

    definition = get_currency_definition(currency_code)
    display_code = (
        definition.code
        if definition
        else str(currency_code or "").strip().upper()
    )

    try:
        normalized_amount = Decimal(str(amount)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, TypeError, ValueError):
        return "No registrado"

    if not normalized_amount.is_finite() or not display_code:
        return "No registrado"

    return f"{display_code} {normalized_amount:,.2f}"
