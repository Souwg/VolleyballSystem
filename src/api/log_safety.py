"""Registro de excepciones sin valores sensibles.

El mensaje de una excepción puede traer datos del usuario: el DETAIL de
PostgreSQL repite la fila rechazada, un ValueError copia el literal recibido y
un proveedor de correo cita al destinatario. Para cualquier registro con
traceback de app.logger se conservan la clase, el contexto SQL sin valores
(SQLSTATE, tabla, columna, constraint y sentencia con placeholders) y los
frames del stack; el mensaje de la excepción se descarta.
"""
import logging
import traceback

from sqlalchemy.exc import StatementError


MAX_STATEMENT_LENGTH = 300


def describe_exception(error):
    parts = [type(error).__name__]

    if isinstance(error, StatementError):
        origin = getattr(error, "orig", None)

        if origin is not None:
            parts.append(f"origen={type(origin).__name__}")

            sqlstate = getattr(origin, "pgcode", None)

            if sqlstate:
                parts.append(f"sqlstate={sqlstate}")

            diagnostic = getattr(origin, "diag", None)

            for attribute, label in (
                ("table_name", "tabla"),
                ("column_name", "columna"),
                ("constraint_name", "constraint"),
            ):
                value = getattr(diagnostic, attribute, None)

                if value:
                    parts.append(f"{label}={value}")

        statement = " ".join(str(error.statement or "").split())

        if statement:
            parts.append(f"sql={statement[:MAX_STATEMENT_LENGTH]}")

    elif error.__cause__ is not None:
        parts.append(f"causa={type(error.__cause__).__name__}")

    return " ".join(parts)


class ExceptionMessageRedactor(logging.Filter):
    def filter(self, record):
        error = record.exc_info[1] if record.exc_info else None

        if error is None:
            return True

        frames = "".join(traceback.format_tb(error.__traceback__)).rstrip()
        record.msg = (
            f"{record.getMessage()} [{describe_exception(error)}]\n{frames}"
        )
        record.args = None
        record.exc_info = None
        record.exc_text = None
        return True
