"""Prevent duplicate monthly payments for the same player and period.

Revision ID: c6a493b25d7e
Revises: 007be904e222
"""

from alembic import op
import sqlalchemy as sa


revision = "c6a493b25d7e"
down_revision = "007be904e222"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_player_payments_monthly_cycle",
        "player_payments",
        ["club_id", "player_id", "period_start"],
        unique=True,
        postgresql_where=sa.text("payment_type = 'monthly'"),
        sqlite_where=sa.text("payment_type = 'monthly'")
    )


def downgrade():
    op.drop_index(
        "uq_player_payments_monthly_cycle",
        table_name="player_payments"
    )
