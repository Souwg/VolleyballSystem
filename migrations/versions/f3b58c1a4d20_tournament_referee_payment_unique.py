"""Prevent duplicate tournament and referee charges.

Revision ID: f3b58c1a4d20
Revises: c6a493b25d7e
"""

from alembic import op
import sqlalchemy as sa


revision = "f3b58c1a4d20"
down_revision = "c6a493b25d7e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_player_payments_tournament_charge",
        "player_payments",
        ["club_id", "player_id", "tournament_team_id"],
        unique=True,
        postgresql_where=sa.text("payment_type = 'tournament'"),
        sqlite_where=sa.text("payment_type = 'tournament'")
    )

    op.create_index(
        "uq_player_payments_referee_charge",
        "player_payments",
        ["club_id", "player_id", "match_id"],
        unique=True,
        postgresql_where=sa.text("payment_type = 'referee'"),
        sqlite_where=sa.text("payment_type = 'referee'")
    )


def downgrade():
    op.drop_index(
        "uq_player_payments_referee_charge",
        table_name="player_payments"
    )
    op.drop_index(
        "uq_player_payments_tournament_charge",
        table_name="player_payments"
    )
