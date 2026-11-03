"""Default new clubs to team assigned coach access.

Revision ID: d7a2c9e4f150
Revises: c3e7a1f4b852
"""

from alembic import op
import sqlalchemy as sa


revision = "d7a2c9e4f150"
down_revision = "c3e7a1f4b852"
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


def _set_default(value):
    # Solo cambia el default: las filas existentes conservan su modo.
    with op.batch_alter_table(
        "clubs",
        table_args=CLUB_CHECKS,
    ) as batch_op:
        batch_op.alter_column(
            "coach_access_mode",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default=value,
        )


def upgrade():
    _set_default("team_assigned")


def downgrade():
    _set_default("club_wide")
