"""Add session version to users.

Revision ID: a14c7e9d2f01
Revises: f3b58c1a4d20
"""

from alembic import op
import sqlalchemy as sa


revision = "a14c7e9d2f01"
down_revision = "f3b58c1a4d20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "session_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0")
        )
    )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("session_version")
