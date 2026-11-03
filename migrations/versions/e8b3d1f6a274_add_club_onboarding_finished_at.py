"""Persist when a club finished its initial onboarding.

Revision ID: e8b3d1f6a274
Revises: d7a2c9e4f150
"""

from alembic import op
import sqlalchemy as sa


revision = "e8b3d1f6a274"
down_revision = "d7a2c9e4f150"
branch_labels = None
depends_on = None


# En SQLite el batch recrea la tabla y no refleja los CHECK; en PostgreSQL es un ALTER.
CLUB_CHECKS = (
    sa.CheckConstraint(
        "access_status IN ('active', 'suspended')",
        name="ck_clubs_access_status",
    ),
    sa.CheckConstraint(
        "LENGTH(currency_code) = 3 AND currency_code = UPPER(currency_code)",
        name="ck_clubs_currency_code_format",
    ),
    sa.CheckConstraint(
        "coach_access_mode IN ('club_wide', 'team_assigned')",
        name="ck_clubs_coach_access_mode",
    ),
)


def upgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.add_column(
            sa.Column("onboarding_finished_at", sa.DateTime(), nullable=True)
        )

    # No hay registro histórico: se infiere de la evidencia disponible. Una
    # membership en una temporada activa o cerrada implica que el club ya pasó
    # por todos los pasos, aunque hoy haya dejado de cumplirlos (equipo archivado,
    # temporada cerrada). Cubre también a los clubes completos hoy. El resto queda
    # pendiente y puede usar "Omitir por ahora".
    op.execute(sa.text("""
        UPDATE clubs
        SET onboarding_finished_at = CURRENT_TIMESTAMP
        WHERE (
            COALESCE(city, '') <> ''
            OR COALESCE(location, '') <> ''
        )
        AND EXISTS (
            SELECT 1 FROM categories
            WHERE categories.club_id = clubs.id
        )
        AND EXISTS (
            SELECT 1
            FROM team_players
            JOIN teams ON teams.id = team_players.team_id
            JOIN seasons ON seasons.id = teams.season_id
            WHERE teams.club_id = clubs.id
            AND seasons.status IN ('active', 'closed')
        )
    """))


def downgrade():
    with op.batch_alter_table(
        "clubs",
        table_args=CLUB_CHECKS,
    ) as batch_op:
        batch_op.drop_column("onboarding_finished_at")
