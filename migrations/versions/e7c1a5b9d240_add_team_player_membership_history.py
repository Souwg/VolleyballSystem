"""Add historical lifecycle to team player memberships.

Revision ID: e7c1a5b9d240
Revises: c5e1a9f7b204
"""

from alembic import op
import sqlalchemy as sa


revision = "e7c1a5b9d240"
down_revision = "c5e1a9f7b204"
branch_labels = None
depends_on = None


def _duplicate_group_exists(bind, columns):
    team_players = sa.table(
        "team_players",
        sa.column("team_id", sa.String(length=36)),
        sa.column(columns[1], sa.String(length=36) if columns[1] == "player_id" else sa.Integer()),
    )
    grouped = (
        sa.select(sa.literal(1))
        .select_from(team_players)
        .group_by(*(getattr(team_players.c, column) for column in columns))
        .having(sa.func.count() > 1)
        .limit(1)
    )
    return bind.execute(grouped).first() is not None


def upgrade():
    with op.batch_alter_table("team_players") as batch_op:
        batch_op.add_column(
            sa.Column("joined_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("left_at", sa.DateTime(), nullable=True)
        )

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE team_players "
        "SET joined_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
        "WHERE joined_at IS NULL"
    ))

    missing_joined_at = bind.execute(sa.text(
        "SELECT COUNT(*) FROM team_players WHERE joined_at IS NULL"
    )).scalar()

    if missing_joined_at:
        raise RuntimeError(
            "El backfill de TeamPlayer dejó memberships sin joined_at."
        )

    with op.batch_alter_table("team_players") as batch_op:
        batch_op.alter_column(
            "joined_at",
            existing_type=sa.DateTime(),
            nullable=False
        )
        batch_op.drop_constraint(
            "unique_player_per_team",
            type_="unique"
        )
        batch_op.drop_constraint(
            "unique_number_per_team",
            type_="unique"
        )

    op.create_index(
        "uq_team_players_open_player",
        "team_players",
        ["team_id", "player_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
        sqlite_where=sa.text("left_at IS NULL")
    )
    op.create_index(
        "uq_team_players_open_number",
        "team_players",
        ["team_id", "player_number"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
        sqlite_where=sa.text("left_at IS NULL")
    )


def downgrade():
    bind = op.get_bind()

    if _duplicate_group_exists(bind, ("team_id", "player_id")):
        raise RuntimeError(
            "No se puede revertir TeamPlayer: existen múltiples etapas "
            "históricas para la misma jugadora y equipo."
        )

    if _duplicate_group_exists(bind, ("team_id", "player_number")):
        raise RuntimeError(
            "No se puede revertir TeamPlayer: existen números históricos "
            "reutilizados dentro del mismo equipo."
        )

    op.drop_index(
        "uq_team_players_open_number",
        table_name="team_players"
    )
    op.drop_index(
        "uq_team_players_open_player",
        table_name="team_players"
    )

    with op.batch_alter_table("team_players") as batch_op:
        batch_op.create_unique_constraint(
            "unique_player_per_team",
            ["team_id", "player_id"]
        )
        batch_op.create_unique_constraint(
            "unique_number_per_team",
            ["team_id", "player_number"]
        )
        batch_op.drop_column("left_at")
        batch_op.drop_column("joined_at")
