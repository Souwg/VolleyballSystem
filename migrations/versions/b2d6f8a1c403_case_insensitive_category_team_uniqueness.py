"""Add case-insensitive uniqueness for categories and teams.

Revision ID: b2d6f8a1c403
Revises: a1f4c7e9b352
"""

from alembic import op
import sqlalchemy as sa


revision = "b2d6f8a1c403"
down_revision = "a1f4c7e9b352"
branch_labels = None
depends_on = None


def _duplicate_group_count(query):
    return op.get_bind().execute(sa.text(query)).scalar()


def _non_normalized_name_ids(table_name):
    rows = op.get_bind().execute(
        sa.text(f"SELECT id, name FROM {table_name}")
    )
    return [
        row.id
        for row in rows
        if " ".join(row.name.strip().split()) != row.name
    ]


def upgrade():
    category_duplicates = _duplicate_group_count(
        """
        SELECT COUNT(*) FROM (
            SELECT club_id, lower(trim(name))
            FROM categories
            GROUP BY club_id, lower(trim(name))
            HAVING COUNT(*) > 1
        ) duplicated
        """
    )
    team_duplicates = _duplicate_group_count(
        """
        SELECT COUNT(*) FROM (
            SELECT club_id, season_id, category_id, gender,
                   lower(trim(name))
            FROM teams
            GROUP BY club_id, season_id, category_id, gender,
                     lower(trim(name))
            HAVING COUNT(*) > 1
        ) duplicated
        """
    )

    if category_duplicates or team_duplicates:
        raise RuntimeError(
            "Hay colisiones case-insensitive en Categories o Teams. "
            "Requieren conciliación manual antes de aplicar esta migración; "
            "no se modificó ningún registro. "
            f"Categories: {category_duplicates}; Teams: {team_duplicates}."
        )

    category_names = _non_normalized_name_ids("categories")
    team_names = _non_normalized_name_ids("teams")

    if category_names or team_names:
        raise RuntimeError(
            "Hay nombres sin la normalización de espacios esperada. "
            "Requieren revisión manual antes de aplicar esta migración; "
            "no se modificó ningún registro. "
            f"Category IDs: {category_names}; Team IDs: {team_names}."
        )

    op.create_index(
        "uq_categories_club_lower_name",
        "categories",
        ["club_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "uq_teams_scope_lower_name",
        "teams",
        [
            "club_id",
            "season_id",
            "category_id",
            "gender",
            sa.text("lower(name)"),
        ],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "uq_teams_scope_lower_name",
        table_name="teams",
    )
    op.drop_index(
        "uq_categories_club_lower_name",
        table_name="categories",
    )
