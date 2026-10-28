"""Add the IANA timezone required by each club.

Revision ID: c1e7b9a4d632
Revises: f4c8b2e6d031
"""

from alembic import op
import sqlalchemy as sa


revision = "c1e7b9a4d632"
down_revision = "f4c8b2e6d031"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "clubs",
        sa.Column("timezone", sa.String(length=120), nullable=True)
    )

    op.execute(sa.text(
        "UPDATE clubs SET timezone = 'America/Caracas' "
        "WHERE country_id = (SELECT id FROM countries WHERE code = 'VE')"
    ))
    op.execute(sa.text(
        "UPDATE clubs SET timezone = 'America/Bogota' "
        "WHERE country_id = (SELECT id FROM countries WHERE code = 'CO')"
    ))

    unresolved = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM clubs WHERE timezone IS NULL")
    ).scalar()

    if unresolved:
        raise RuntimeError(
            "Existen Clubs cuya zona horaria no puede determinarse con certeza."
        )

    with op.batch_alter_table("clubs") as batch_op:
        batch_op.alter_column(
            "timezone",
            existing_type=sa.String(length=120),
            nullable=False
        )


def downgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.drop_column("timezone")
