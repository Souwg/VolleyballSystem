"""Add lifecycle status to training sessions.

Revision ID: d4f8a21c6b90
Revises: b7e31c4a8d62
"""

from alembic import op
import sqlalchemy as sa


revision = "d4f8a21c6b90"
down_revision = "b7e31c4a8d62"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("training_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'scheduled'")
            )
        )
        batch_op.create_check_constraint(
            "ck_training_sessions_status",
            "status IN ('scheduled', 'completed', 'cancelled')"
        )

    # Attendance is the only existing objective evidence that a past
    # training took place. Past sessions without attendance remain
    # scheduled rather than inventing historical completion/cancellation.
    op.execute(
        sa.text(
            """
            UPDATE training_sessions
            SET status = 'completed'
            WHERE date < CURRENT_DATE
              AND EXISTS (
                  SELECT 1
                  FROM attendance
                  WHERE attendance.session_id = training_sessions.id
              )
            """
        )
    )


def downgrade():
    with op.batch_alter_table("training_sessions") as batch_op:
        batch_op.drop_constraint(
            "ck_training_sessions_status",
            type_="check"
        )
        batch_op.drop_column("status")
