"""Validación de entrada compartida por toda la API.

- El cuerpo JSON de una escritura debe ser un objeto.
- Los identificadores (`id`, `*_id`) son UUID en texto y las listas `*_ids`
  solo contienen textos, en cualquier nivel del cuerpo.
- Antes de cada flush se comprueban los valores contra los límites declarados
  en las columnas (longitud de textos, rango de enteros y de Numeric), para que
  un dato inválido termine en un 400 y no en un error de PostgreSQL.
"""
import math
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import sqlalchemy as sa
from flask import Request, request
from sqlalchemy import event, inspect

from src.api.utils import APIException


JSON_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

INVALID_JSON_BODY_MESSAGE = (
    "El cuerpo de la solicitud debe ser un objeto JSON válido."
)

INTEGER_LIMITS = (
    (sa.SmallInteger, 2 ** 15 - 1),
    (sa.BigInteger, 2 ** 63 - 1),
    (sa.Integer, 2 ** 31 - 1),
)


class InputValidationError(APIException):
    def __init__(self, message, code, field=None):
        payload = {"error": True, "code": code}

        if field:
            payload["field"] = field

        super().__init__(message, status_code=400, payload=payload)


class ApiRequest(Request):
    def on_json_loading_failed(self, e):
        # Sin `e` el Content-Type no era JSON: Werkzeug responde 415.
        if e is None:
            return super().on_json_loading_failed(e)

        raise InputValidationError(
            INVALID_JSON_BODY_MESSAGE,
            "INVALID_JSON_BODY"
        )


def validate_json_body():
    if (
        request.method not in JSON_BODY_METHODS
        or not request.path.startswith("/api/")
        or not request.is_json
        or not request.get_data(cache=True)
    ):
        return None

    try:
        body = request.get_json()
    except RecursionError:
        body = None

    if not isinstance(body, dict):
        raise InputValidationError(
            INVALID_JSON_BODY_MESSAGE,
            "INVALID_JSON_BODY"
        )

    _validate_identifiers(body)
    return None


def _validate_identifiers(body):
    pending = [body]

    while pending:
        value = pending.pop()

        if isinstance(value, list):
            pending.extend(value)
            continue

        if not isinstance(value, dict):
            continue

        for key, item in value.items():
            if key == "id" or key.endswith("_id"):
                valid = item is None or isinstance(item, str)
            elif key.endswith("_ids"):
                valid = item is None or (
                    isinstance(item, list)
                    and all(isinstance(entry, str) for entry in item)
                )
            else:
                valid = True

            if not valid:
                raise InputValidationError(
                    "Uno de los identificadores enviados no es válido.",
                    "INVALID_FIELD_TYPE",
                    key
                )

            pending.append(item)


def text_field(body, field):
    """Devuelve el texto de `field` o None; rechaza cualquier otro tipo."""
    value = body.get(field)

    if value is None or isinstance(value, str):
        return value

    raise InputValidationError(
        "Uno de los campos enviados tiene un formato inválido.",
        "INVALID_FIELD_TYPE",
        field
    )


def _is_finite(value):
    if isinstance(value, Decimal):
        return value.is_finite()

    return math.isfinite(value)


def _out_of_range(field):
    return InputValidationError(
        "Uno de los valores numéricos está fuera del rango permitido.",
        "NUMBER_OUT_OF_RANGE",
        field
    )


def _check_column_value(column, field, value):
    column_type = column.type

    if value is None or isinstance(value, bool):
        return

    if isinstance(column_type, sa.String):
        if (
            isinstance(value, str)
            and column_type.length
            and len(value) > column_type.length
        ):
            raise InputValidationError(
                (
                    "Uno de los textos supera la longitud máxima permitida "
                    f"({column_type.length} caracteres)."
                ),
                "FIELD_TOO_LONG",
                field
            )
        return

    if isinstance(column_type, sa.Float):
        if isinstance(value, (float, Decimal)) and not _is_finite(value):
            raise _out_of_range(field)
        return

    if isinstance(column_type, sa.Numeric):
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise InputValidationError(
                "Uno de los campos enviados tiene un formato inválido.",
                "INVALID_FIELD_TYPE",
                field
            )

        if not number.is_finite():
            raise _out_of_range(field)

        if column_type.precision is None:
            return

        scale = column_type.scale or 0
        integer_digits = column_type.precision - scale

        if (
            number != 0
            and (
                number.adjusted() >= integer_digits
                or abs(number.quantize(
                    Decimal(1).scaleb(-scale),
                    rounding=ROUND_HALF_UP
                )) >= Decimal(10) ** integer_digits
            )
        ):
            raise _out_of_range(field)
        return

    if isinstance(column_type, sa.Integer) and isinstance(
        value,
        (int, float, Decimal)
    ):
        limit = next(
            maximum
            for integer_type, maximum in INTEGER_LIMITS
            if isinstance(column_type, integer_type)
        )

        if not _is_finite(value) or abs(value) > limit:
            raise _out_of_range(field)


def _validate_pending_values(session, flush_context, instances):
    for obj in session.new:
        state = inspect(obj)

        for attr in state.mapper.column_attrs:
            column = attr.columns[0]

            if attr.key in state.dict and isinstance(column, sa.Column):
                _check_column_value(column, attr.key, state.dict[attr.key])

    for obj in session.dirty:
        state = inspect(obj)

        for attr in state.mapper.column_attrs:
            column = attr.columns[0]

            if not isinstance(column, sa.Column):
                continue

            for value in state.attrs[attr.key].history.added or ():
                _check_column_value(column, attr.key, value)


def register_column_limit_guard(session):
    if not event.contains(session, "before_flush", _validate_pending_values):
        event.listen(session, "before_flush", _validate_pending_values)
