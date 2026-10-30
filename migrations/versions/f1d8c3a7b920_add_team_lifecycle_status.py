"""Add lifecycle status to teams.

Revision ID: f1d8c3a7b920
Revises: e7c1a5b9d240
"""

from alembic import op
import sqlalchemy as sa


revision = "f1d8c3a7b920"
down_revision = "e7c1a5b9d240"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="active",
                nullable=True,
            )
        )

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE teams SET status = 'active' WHERE status IS NULL"
    ))

    missing_status = bind.execute(sa.text(
        "SELECT COUNT(*) FROM teams WHERE status IS NULL"
    )).scalar()

    if missing_status:
        raise RuntimeError(
            "El backfill de Team dejó equipos sin status."
        )

    with op.batch_alter_table("teams") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            nullable=False,
            server_default="active",
        )
        batch_op.create_check_constraint(
            "ck_teams_status",
            "status IN ('active', 'archived')",
        )


def downgrade():
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint(
            "ck_teams_status",
            type_="check",
        )
        batch_op.drop_column("status")
