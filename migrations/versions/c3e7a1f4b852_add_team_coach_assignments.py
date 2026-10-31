"""Add team coach assignments and club coach access mode.

Revision ID: c3e7a1f4b852
Revises: a6c4e2f9b731
"""

from alembic import op
import sqlalchemy as sa


revision = "c3e7a1f4b852"
down_revision = "a6c4e2f9b731"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("clubs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "coach_access_mode",
                sa.String(length=20),
                nullable=False,
                server_default="club_wide",
            )
        )
        batch_op.create_check_constraint(
            "ck_clubs_coach_access_mode",
            "coach_access_mode IN ('club_wide', 'team_assigned')",
        )

    with op.batch_alter_table("teams") as batch_op:
        batch_op.create_unique_constraint(
            "uq_teams_id_club_id",
            ["id", "club_id"],
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint(
            "uq_users_id_club_id",
            ["id", "club_id"],
        )

    op.create_table(
        "team_coach_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("club_id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("assigned_by", sa.String(length=36), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["team_id", "club_id"],
            ["teams.id", "teams.club_id"],
            name="fk_team_coach_assignments_team_club",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "club_id"],
            ["users.id", "users.club_id"],
            name="fk_team_coach_assignments_user_club",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_team_coach_assignments_open",
        "team_coach_assignments",
        ["team_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("removed_at IS NULL"),
        sqlite_where=sa.text("removed_at IS NULL"),
    )
    op.create_index(
        "ix_team_coach_assignments_user_id",
        "team_coach_assignments",
        ["user_id"],
    )


def downgrade():
    bind = op.get_bind()
    has_assignments = bind.execute(sa.text(
        "SELECT 1 FROM team_coach_assignments LIMIT 1"
    )).first()
    has_scoped_club = bind.execute(sa.text(
        "SELECT 1 FROM clubs WHERE coach_access_mode <> 'club_wide' LIMIT 1"
    )).first()

    if has_assignments or has_scoped_club:
        raise RuntimeError(
            "No se puede revertir: existen asignaciones de entrenadores o "
            "clubes con acceso por equipo, y se perderían al revertir."
        )

    op.drop_index(
        "ix_team_coach_assignments_user_id",
        table_name="team_coach_assignments",
    )
    op.drop_index(
        "uq_team_coach_assignments_open",
        table_name="team_coach_assignments",
    )
    op.drop_table("team_coach_assignments")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_id_club_id", type_="unique")

    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint("uq_teams_id_club_id", type_="unique")

    with op.batch_alter_table("clubs") as batch_op:
        batch_op.drop_constraint("ck_clubs_coach_access_mode", type_="check")
        batch_op.drop_column("coach_access_mode")
