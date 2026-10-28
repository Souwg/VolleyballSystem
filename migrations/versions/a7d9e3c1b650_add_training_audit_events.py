"""Add immutable training correction audit events.

Revision ID: a7d9e3c1b650
Revises: f6a2c9d4e815
"""

from alembic import op
import sqlalchemy as sa


revision = "a7d9e3c1b650"
down_revision = "f6a2c9d4e815"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "training_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("training_id", sa.String(length=36), nullable=False),
        sa.Column("club_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action IN ("
            "'training_metadata_corrected', "
            "'training_attendance_corrected', "
            "'training_reactivated'"
            ")",
            name="ck_training_audit_events_action"
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name="fk_training_audit_events_club_id_clubs"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_training_audit_events_created_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["training_id"],
            ["training_sessions.id"],
            name="fk_training_audit_events_training_id_training_sessions"
        ),
        sa.PrimaryKeyConstraint("id")
    )

    op.create_index(
        "ix_training_audit_events_training_created_at",
        "training_audit_events",
        ["training_id", "created_at"],
        unique=False
    )


def downgrade():
    op.drop_index(
        "ix_training_audit_events_training_created_at",
        table_name="training_audit_events"
    )
    op.drop_table("training_audit_events")
