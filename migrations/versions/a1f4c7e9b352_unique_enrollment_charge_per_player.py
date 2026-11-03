"""Allow at most one enrollment charge per player.

Revision ID: a1f4c7e9b352
Revises: e8b3d1f6a274
"""

from alembic import op
import sqlalchemy as sa


revision = "a1f4c7e9b352"
down_revision = "e8b3d1f6a274"
branch_labels = None
depends_on = None


def upgrade():
    # Un duplicado puede estar pagado o tener recibo: elegir cuál conservar es
    # una conciliación del club, no una decisión de la migración.
    duplicated_groups = op.get_bind().execute(sa.text(
        """
        SELECT COUNT(*) FROM (
            SELECT club_id, player_id
            FROM player_payments
            WHERE payment_type = 'enrollment'
            GROUP BY club_id, player_id
            HAVING COUNT(*) > 1
        ) duplicated
        """
    )).scalar()

    if duplicated_groups:
        raise RuntimeError(
            f"Hay {duplicated_groups} deportista(s) con más de un cargo de "
            "inscripción. Requieren conciliación manual antes de aplicar esta "
            "migración; no se modificó ningún registro."
        )

    op.create_index(
        "uq_player_payments_enrollment_charge",
        "player_payments",
        ["club_id", "player_id"],
        unique=True,
        postgresql_where=sa.text("payment_type = 'enrollment'"),
        sqlite_where=sa.text("payment_type = 'enrollment'")
    )


def downgrade():
    op.drop_index(
        "uq_player_payments_enrollment_charge",
        table_name="player_payments"
    )
