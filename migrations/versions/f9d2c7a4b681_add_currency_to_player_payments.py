"""Freeze the operating currency on each payment obligation.

Revision ID: f9d2c7a4b681
Revises: e3b7c4a9d215
"""

from alembic import op
import sqlalchemy as sa


revision = "f9d2c7a4b681"
down_revision = "e3b7c4a9d215"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "player_payments",
        sa.Column("currency_code", sa.String(length=3), nullable=True)
    )

    clubs = sa.table(
        "clubs",
        sa.column("id", sa.String(length=36)),
        sa.column("currency_code", sa.String(length=3)),
    )
    payments = sa.table(
        "player_payments",
        sa.column("club_id", sa.String(length=36)),
        sa.column("currency_code", sa.String(length=3)),
    )
    bind = op.get_bind()

    valid_club_currency = (
        sa.select(clubs.c.currency_code)
        .where(
            clubs.c.id == payments.c.club_id,
            sa.func.length(clubs.c.currency_code) == 3,
            clubs.c.currency_code == sa.func.upper(clubs.c.currency_code),
        )
        .scalar_subquery()
    )
    bind.execute(
        payments.update().values(currency_code=valid_club_currency)
    )

    unresolved = bind.execute(
        sa.select(sa.func.count())
        .select_from(payments)
        .where(payments.c.currency_code.is_(None))
    ).scalar()

    if unresolved:
        raise RuntimeError(
            "Existen obligaciones cuya moneda no puede resolverse desde su Club."
        )

    with op.batch_alter_table("player_payments") as batch_op:
        batch_op.alter_column(
            "currency_code",
            existing_type=sa.String(length=3),
            nullable=False
        )
        batch_op.create_check_constraint(
            "ck_player_payments_currency_code_format",
            "LENGTH(currency_code) = 3 "
            "AND currency_code = UPPER(currency_code)"
        )


def downgrade():
    with op.batch_alter_table("player_payments") as batch_op:
        batch_op.drop_constraint(
            "ck_player_payments_currency_code_format",
            type_="check"
        )
        batch_op.drop_column("currency_code")
