"""Add the primary sport to clubs.

Revision ID: d2a6f9c3e841
Revises: b4f10c2d9a71
"""

from alembic import op
import sqlalchemy as sa


revision = "d2a6f9c3e841"
down_revision = "b4f10c2d9a71"
branch_labels = None
depends_on = None

VOLLEYBALL_ID = "00000000-0000-4000-8000-000000000001"


def upgrade():
    op.add_column(
        "clubs",
        sa.Column("sport_id", sa.String(length=36), nullable=True)
    )

    op.execute(
        sa.text(
            "UPDATE clubs "
            f"SET sport_id = '{VOLLEYBALL_ID}' "
            "WHERE sport_id IS NULL"
        )
    )

    with op.batch_alter_table("clubs") as batch_op:
        batch_op.create_foreign_key(
            "fk_clubs_sport_id_sports",
            "sports",
            ["sport_id"],
            ["id"]
        )
        batch_op.alter_column(
            "sport_id",
            existing_type=sa.String(length=36),
            nullable=False
        )


def downgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.drop_constraint(
            "fk_clubs_sport_id_sports",
            type_="foreignkey"
        )
        batch_op.drop_column("sport_id")
