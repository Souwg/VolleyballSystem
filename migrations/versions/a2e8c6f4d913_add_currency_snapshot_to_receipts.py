"""Freeze the payment currency on each receipt snapshot.

Revision ID: a2e8c6f4d913
Revises: f9d2c7a4b681
"""

from alembic import op
import sqlalchemy as sa


revision = "a2e8c6f4d913"
down_revision = "f9d2c7a4b681"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = (
    "ck_payment_receipts_currency_code_snapshot_format"
)


def upgrade():
    op.add_column(
        "payment_receipts",
        sa.Column(
            "currency_code_snapshot",
            sa.String(length=3),
            nullable=True
        )
    )

    metadata = sa.MetaData()
    receipts = sa.Table(
        "payment_receipts",
        metadata,
        autoload_with=op.get_bind()
    )
    payments = sa.Table(
        "player_payments",
        metadata,
        autoload_with=op.get_bind()
    )

    valid_payment_currency = (
        sa.select(payments.c.currency_code)
        .where(
            payments.c.id == receipts.c.payment_id,
            sa.func.length(payments.c.currency_code) == 3,
            payments.c.currency_code
            == sa.func.upper(payments.c.currency_code),
        )
        .scalar_subquery()
    )

    bind = op.get_bind()
    bind.execute(
        receipts.update().values(
            currency_code_snapshot=valid_payment_currency
        )
    )

    unresolved = bind.execute(
        sa.select(sa.func.count())
        .select_from(receipts)
        .where(receipts.c.currency_code_snapshot.is_(None))
    ).scalar()

    if unresolved:
        raise RuntimeError(
            "Existen recibos cuya moneda no puede resolverse "
            "desde su obligación de pago."
        )

    with op.batch_alter_table("payment_receipts") as batch_op:
        batch_op.alter_column(
            "currency_code_snapshot",
            existing_type=sa.String(length=3),
            nullable=False
        )
        batch_op.create_check_constraint(
            CONSTRAINT_NAME,
            "LENGTH(currency_code_snapshot) = 3 "
            "AND currency_code_snapshot = UPPER(currency_code_snapshot)"
        )


def downgrade():
    with op.batch_alter_table("payment_receipts") as batch_op:
        batch_op.drop_constraint(
            CONSTRAINT_NAME,
            type_="check"
        )
        batch_op.drop_column("currency_code_snapshot")
