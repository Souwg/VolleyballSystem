"""Add seasons to teams and tournaments.

Revision ID: c5e1a9f7b204
Revises: a2e8c6f4d913
"""

from datetime import date, datetime
import uuid

from alembic import op
import sqlalchemy as sa


revision = "c5e1a9f7b204"
down_revision = "a2e8c6f4d913"
branch_labels = None
depends_on = None


INITIAL_SEASON_NAME = "Temporada inicial"
SEASON_UUID_NAMESPACE = uuid.UUID("6fb7bc75-a833-4bb8-b09e-f12f8cd9d945")


def _as_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return None


def _minimum_date(bind, statement):
    return _as_date(bind.execute(statement).scalar())


def _resolve_initial_start_date(
    bind,
    *,
    club_id,
    club_created_at,
    owner_id,
    users,
    teams,
    tournaments,
    training_sessions,
    match_sessions,
):
    candidates = [_as_date(club_created_at)]

    if owner_id:
        candidates.append(
            _minimum_date(
                bind,
                sa.select(sa.func.min(users.c.created_at)).where(
                    users.c.id == owner_id
                )
            )
        )

    candidates.extend([
        _minimum_date(
            bind,
            sa.select(sa.func.min(teams.c.created_at)).where(
                teams.c.club_id == club_id
            )
        ),
        _minimum_date(
            bind,
            sa.select(sa.func.min(tournaments.c.start_date)).where(
                tournaments.c.club_id == club_id
            )
        ),
        _minimum_date(
            bind,
            sa.select(sa.func.min(training_sessions.c.date))
            .select_from(
                training_sessions.join(
                    teams,
                    training_sessions.c.team_id == teams.c.id
                )
            )
            .where(teams.c.club_id == club_id)
        ),
        _minimum_date(
            bind,
            sa.select(sa.func.min(match_sessions.c.date))
            .select_from(
                match_sessions.join(
                    teams,
                    match_sessions.c.team_id == teams.c.id
                )
            )
            .where(teams.c.club_id == club_id)
        ),
    ])

    resolved = [candidate for candidate in candidates if candidate]

    if not resolved:
        raise RuntimeError(
            "No se pudo determinar una fecha inicial para el Club "
            f"{club_id}."
        )

    return min(resolved)


def upgrade():
    op.create_table(
        "seasons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("club_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False
        ),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'closed')",
            name="ck_seasons_status"
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_seasons_date_range"
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name="fk_seasons_club_id_clubs"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_seasons_created_by_users"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "club_id",
            name="uq_seasons_id_club_id"
        )
    )
    op.create_index(
        "uq_seasons_active_per_club",
        "seasons",
        ["club_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'")
    )

    op.add_column(
        "teams",
        sa.Column("season_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "tournaments",
        sa.Column("season_id", sa.String(length=36), nullable=True)
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(
        bind=bind,
        only=[
            "clubs",
            "users",
            "teams",
            "tournaments",
            "training_sessions",
            "match_sessions",
            "seasons",
        ]
    )

    clubs = metadata.tables["clubs"]
    users = metadata.tables["users"]
    teams = metadata.tables["teams"]
    tournaments = metadata.tables["tournaments"]
    training_sessions = metadata.tables["training_sessions"]
    match_sessions = metadata.tables["match_sessions"]
    seasons = metadata.tables["seasons"]

    user_ids = set(bind.execute(sa.select(users.c.id)).scalars())
    club_rows = bind.execute(
        sa.select(
            clubs.c.id,
            clubs.c.owner_id,
            clubs.c.created_at
        ).order_by(clubs.c.id)
    ).all()

    for club in club_rows:
        season_id = str(
            uuid.uuid5(
                SEASON_UUID_NAMESPACE,
                f"sportflow:initial-season:{club.id}"
            )
        )
        start_date = _resolve_initial_start_date(
            bind,
            club_id=club.id,
            club_created_at=club.created_at,
            owner_id=club.owner_id,
            users=users,
            teams=teams,
            tournaments=tournaments,
            training_sessions=training_sessions,
            match_sessions=match_sessions,
        )
        creator_id = (
            club.owner_id
            if club.owner_id in user_ids
            else None
        )

        bind.execute(
            seasons.insert().values(
                id=season_id,
                club_id=club.id,
                name=INITIAL_SEASON_NAME,
                start_date=start_date,
                end_date=None,
                status="active",
                created_by=creator_id,
                created_at=datetime.utcnow(),
            )
        )
        bind.execute(
            teams.update()
            .where(teams.c.club_id == club.id)
            .values(season_id=season_id)
        )
        bind.execute(
            tournaments.update()
            .where(tournaments.c.club_id == club.id)
            .values(season_id=season_id)
        )

    teams_without_season = bind.execute(
        sa.select(sa.func.count())
        .select_from(teams)
        .where(teams.c.season_id.is_(None))
    ).scalar()
    tournaments_without_season = bind.execute(
        sa.select(sa.func.count())
        .select_from(tournaments)
        .where(tournaments.c.season_id.is_(None))
    ).scalar()

    if teams_without_season or tournaments_without_season:
        raise RuntimeError(
            "El backfill de Season dejó Teams o Tournaments sin asociar."
        )

    with op.batch_alter_table("teams") as batch_op:
        batch_op.alter_column(
            "season_id",
            existing_type=sa.String(length=36),
            nullable=False
        )
        batch_op.create_foreign_key(
            "fk_teams_season_club",
            "seasons",
            ["season_id", "club_id"],
            ["id", "club_id"]
        )

    with op.batch_alter_table("tournaments") as batch_op:
        batch_op.alter_column(
            "season_id",
            existing_type=sa.String(length=36),
            nullable=False
        )
        batch_op.create_foreign_key(
            "fk_tournaments_season_club",
            "seasons",
            ["season_id", "club_id"],
            ["id", "club_id"]
        )


def downgrade():
    with op.batch_alter_table("tournaments") as batch_op:
        batch_op.drop_constraint(
            "fk_tournaments_season_club",
            type_="foreignkey"
        )
        batch_op.drop_column("season_id")

    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint(
            "fk_teams_season_club",
            type_="foreignkey"
        )
        batch_op.drop_column("season_id")

    op.drop_index(
        "uq_seasons_active_per_club",
        table_name="seasons"
    )
    op.drop_table("seasons")
