"""Add explicit statistics capture mode to matches.

Revision ID: e8c41f7a9d30
Revises: d4f8a21c6b90
"""

from alembic import op
import sqlalchemy as sa


revision = "e8c41f7a9d30"
down_revision = "d4f8a21c6b90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("match_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "capture_mode",
                sa.String(length=20),
                nullable=True
            )
        )
        batch_op.create_check_constraint(
            "ck_match_sessions_capture_mode",
            "capture_mode IS NULL OR capture_mode IN ('live', 'summary')"
        )

    # Existing matches intentionally remain NULL. Events and summarized
    # statistics may have been mixed before this field existed, so their
    # original source cannot be inferred safely.


def downgrade():
    with op.batch_alter_table("match_sessions") as batch_op:
        batch_op.drop_constraint(
            "ck_match_sessions_capture_mode",
            type_="check"
        )
        batch_op.drop_column("capture_mode")
