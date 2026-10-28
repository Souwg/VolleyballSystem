"""Add operational access status to clubs.

Revision ID: b7e31c4a8d62
Revises: a14c7e9d2f01
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e31c4a8d62"
down_revision = "a14c7e9d2f01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "access_status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'active'")
            )
        )
        batch_op.create_check_constraint(
            "ck_clubs_access_status",
            "access_status IN ('active', 'suspended')"
        )


def downgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.drop_constraint(
            "ck_clubs_access_status",
            type_="check"
        )
        batch_op.drop_column("access_status")
