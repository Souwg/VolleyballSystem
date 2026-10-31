"""Scope team structural identity to its season.

Revision ID: a6c4e2f9b731
Revises: f1d8c3a7b920
"""

from alembic import op
import sqlalchemy as sa


revision = "a6c4e2f9b731"
down_revision = "f1d8c3a7b920"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint(
            "unique_team_gender_per_category",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "unique_team_gender_per_category",
            ["name", "gender", "category_id", "club_id", "season_id"],
        )


def downgrade():
    bind = op.get_bind()
    duplicate = bind.execute(sa.text(
        "SELECT 1 FROM teams "
        "GROUP BY name, gender, category_id, club_id "
        "HAVING COUNT(*) > 1 LIMIT 1"
    )).first()

    if duplicate:
        raise RuntimeError(
            "No se puede revertir la unicidad por temporada: existen equipos "
            "equivalentes en más de una temporada."
        )

    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint(
            "unique_team_gender_per_category",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "unique_team_gender_per_category",
            ["name", "gender", "category_id", "club_id"],
        )
