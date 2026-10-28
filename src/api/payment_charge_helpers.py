from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from src.api.models import db, PlayerPayment
from src.api.utils import error_response


def parse_money(value, field_name="Monto"):
    try:
        amount = Decimal(str(value))

        if not amount.is_finite():
            return None, error_response(
                f"{field_name} debe ser un número válido",
                "INVALID_AMOUNT",
                400
            )

        amount = amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, TypeError, ValueError):
        return None, error_response(
            f"{field_name} debe ser un número válido",
            "INVALID_AMOUNT",
            400
        )

    if amount < 0:
        return None, error_response(
            f"{field_name} no puede ser negativo",
            "INVALID_AMOUNT",
            400
        )

    return amount, None


def split_money_exactly(total_amount, total_people):
    """
    Divide un monto conservando exactamente todos los centavos.

    Ejemplo:
    10.00 entre 3 personas
    -> 3.34, 3.33, 3.33
    """

    if total_people <= 0:
        return []

    total_amount = Decimal(str(total_amount)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    total_cents = int(total_amount * 100)

    base_cents = total_cents // total_people
    remaining_cents = total_cents % total_people

    amounts = []

    for index in range(total_people):
        cents = base_cents

        if index < remaining_cents:
            cents += 1

        amounts.append(
            Decimal(cents) / Decimal("100")
        )

    return amounts


def add_charge_if_absent(
    charge,
    identity_filters,
    constraint_name
):
    """
    Inserta un cargo protegido por un índice único parcial.

    El savepoint limita el rollback al cargo que perdió una carrera
    concurrente y conserva los demás cargos válidos de la operación.
    """

    existing_charge = PlayerPayment.query.filter_by(
        **identity_filters
    ).first()

    if existing_charge:
        return existing_charge

    savepoint = db.session.begin_nested()

    try:
        with savepoint:
            db.session.add(charge)
            db.session.flush()
    except IntegrityError as error:
        conflicting_constraint = getattr(
            getattr(error.orig, "diag", None),
            "constraint_name",
            None
        )

        if (
            conflicting_constraint
            and conflicting_constraint != constraint_name
        ):
            raise

        existing_charge = PlayerPayment.query.filter_by(
            **identity_filters
        ).first()

        if existing_charge is None:
            raise

        return existing_charge

    return charge
