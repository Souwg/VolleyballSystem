"""Add the required operating currency to each club.

Revision ID: e3b7c4a9d215
Revises: c1e7b9a4d632
"""

from alembic import op
import sqlalchemy as sa


revision = "e3b7c4a9d215"
down_revision = "c1e7b9a4d632"
branch_labels = None
depends_on = None


# Product explicitly confirmed these historical club identities as USD.
# Country and club name are deliberately not used to infer currency.
HISTORICAL_CLUB_CURRENCIES = {
    "3d4d3687-98ee-4e13-b4e3-fb1771abdb9f": "USD",
    "b736dda2-4372-42c5-8176-7bc5678c9ae9": "USD",
}


def upgrade():
    op.add_column(
        "clubs",
        sa.Column("currency_code", sa.String(length=3), nullable=True)
    )

    clubs = sa.table(
        "clubs",
        sa.column("id", sa.String(length=36)),
        sa.column("currency_code", sa.String(length=3)),
    )
    bind = op.get_bind()

    for club_id, currency_code in HISTORICAL_CLUB_CURRENCIES.items():
        bind.execute(
            clubs.update()
            .where(clubs.c.id == club_id)
            .values(currency_code=currency_code)
        )

    unresolved = bind.execute(
        sa.select(sa.func.count())
        .select_from(clubs)
        .where(clubs.c.currency_code.is_(None))
    ).scalar()

    if unresolved:
        raise RuntimeError(
            "Existen Clubs históricos sin una decisión explícita de moneda."
        )

    with op.batch_alter_table("clubs") as batch_op:
        batch_op.alter_column(
            "currency_code",
            existing_type=sa.String(length=3),
            nullable=False
        )
        batch_op.create_check_constraint(
            "ck_clubs_currency_code_format",
            "LENGTH(currency_code) = 3 "
            "AND currency_code = UPPER(currency_code)"
        )


def downgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.drop_constraint(
            "ck_clubs_currency_code_format",
            type_="check"
        )
        batch_op.drop_column("currency_code")
