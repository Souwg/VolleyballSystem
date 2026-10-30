from datetime import date, datetime
import importlib
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.api.models import (
    AdministrativeArea,
    Club,
    Country,
    Season,
    Team,
    Tournament,
    User,
    db,
)


MIGRATION_MODULE = (
    "migrations.versions."
    "c5e1a9f7b204_add_seasons_to_teams_and_tournaments"
)


def test_season_belongs_to_club_and_serializes(world):
    season = world.season_a

    assert season.club_id == world.club_a.id
    assert season.club == world.club_a
    assert season.serialize()["club_id"] == world.club_a.id
    assert season.serialize()["start_date"] == "2026-01-01"


@pytest.mark.parametrize("status", ["planned", "active", "closed"])
def test_season_accepts_valid_statuses(world, status):
    if status == "active":
        assert world.season_a.status == status
        return

    season = Season(
        club=world.club_a,
        name=f"Season {status}",
        start_date=date(2027, 1, 1),
        status=status,
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()

    assert season.status == status


def test_season_rejects_invalid_status(world):
    db.session.add(Season(
        club=world.club_a,
        name="Invalid",
        start_date=date(2027, 1, 1),
        status="archived",
        created_by=world.owner_a.id,
    ))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_season_rejects_end_before_start(world):
    db.session.add(Season(
        club=world.club_a,
        name="Invalid range",
        start_date=date(2027, 2, 1),
        end_date=date(2027, 1, 31),
        status="planned",
        created_by=world.owner_a.id,
    ))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_only_one_active_season_per_club(world):
    db.session.add(Season(
        club=world.club_a,
        name="Second active",
        start_date=date(2027, 1, 1),
        status="active",
        created_by=world.owner_a.id,
    ))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_different_clubs_can_each_have_an_active_season(world):
    assert world.season_a.status == "active"
    assert world.season_b.status == "active"
    assert world.season_a.club_id != world.season_b.club_id


def test_team_and_tournament_belong_to_same_club_season(world):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name="Season tournament",
        start_date=date(2026, 11, 1),
        status="active",
        created_by=world.owner_a.id,
    )
    db.session.add(tournament)
    db.session.commit()

    assert world.team_a.season_id == world.season_a.id
    assert tournament.season_id == world.season_a.id
    assert tournament.club_id == world.season_a.club_id


def _enable_sqlite_foreign_keys():
    db.session.execute(sa.text("PRAGMA foreign_keys = ON"))


def test_cross_tenant_season_is_rejected_for_team(world):
    _enable_sqlite_foreign_keys()
    db.session.add(Team(
        name="Cross tenant Team",
        gender="female",
        category_id=world.category_a.id,
        club_id=world.club_a.id,
        season_id=world.season_b.id,
    ))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_cross_tenant_season_is_rejected_for_tournament(world):
    _enable_sqlite_foreign_keys()
    db.session.add(Tournament(
        club_id=world.club_a.id,
        season_id=world.season_b.id,
        name="Cross tenant Tournament",
        start_date=date(2026, 12, 1),
        status="active",
        created_by=world.owner_a.id,
    ))

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_existing_team_creation_uses_active_season(
    client,
    world,
    auth_headers,
):
    response = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        headers=auth_headers(world.owner_a),
        json={"name": "Team new", "gender": "female"},
    )

    assert response.status_code == 201
    assert response.get_json()["team"]["season_id"] == world.season_a.id


def test_existing_tournament_creation_uses_active_season(
    client,
    world,
    auth_headers,
):
    response = client.post(
        "/api/tournaments",
        headers=auth_headers(world.owner_a),
        json={
            "name": "New Tournament",
            "start_date": "2026-11-15",
            "default_referee_fee": "0",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["tournament"]["season_id"] == world.season_a.id


def test_new_club_provisioning_creates_initial_season(
    client,
    world,
    auth_headers,
    monkeypatch,
):
    country = Country(
        id=str(uuid.uuid4()),
        code="VE",
        name="Venezuela",
        is_active=True,
    )
    area = AdministrativeArea(
        id=str(uuid.uuid4()),
        country=country,
        code="VE-A",
        name="Distrito Capital",
        is_active=True,
    )
    db.session.add_all([country, area])
    db.session.commit()

    monkeypatch.setattr(
        "src.api.endpoints.admin.send_welcome_email",
        lambda **kwargs: None,
    )

    response = client.post(
        "/api/admin/create-client",
        headers=auth_headers(world.system_admin),
        json={
            "full_name": "Owner Season",
            "email": "owner-season@example.com",
            "club_name": "Club Season",
            "sport_id": world.sport.id,
            "country_id": country.id,
            "administrative_area_id": area.id,
            "city": "Caracas",
            "timezone": "America/Caracas",
            "currency_code": "USD",
        },
    )

    assert response.status_code == 201
    owner = User.query.filter_by(
        email="owner-season@example.com"
    ).one()
    season = Season.query.filter_by(
        club_id=owner.club_id,
        status="active"
    ).one()
    assert season.name == "Temporada inicial"
    assert season.created_by == owner.id


def _create_legacy_schema(connection):
    metadata = sa.MetaData()
    sa.Table(
        "clubs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    sa.Table(
        "teams",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("club_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    sa.Table(
        "tournaments",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("club_id", sa.String(36), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
    )
    sa.Table(
        "training_sessions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
    )
    sa.Table(
        "match_sessions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
    )
    metadata.create_all(connection)
    return metadata


def test_migration_backfills_club_team_and_tournament_and_downgrades(
    tmp_path,
):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'season.db'}")
    migration = importlib.import_module(MIGRATION_MODULE)

    with engine.begin() as connection:
        metadata = _create_legacy_schema(connection)
        club_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        team_id = str(uuid.uuid4())
        tournament_id = str(uuid.uuid4())

        connection.execute(metadata.tables["users"].insert(), {
            "id": owner_id,
            "created_at": datetime(2025, 12, 15),
        })
        connection.execute(metadata.tables["clubs"].insert(), {
            "id": club_id,
            "owner_id": owner_id,
            "created_at": datetime(2026, 1, 10),
        })
        connection.execute(metadata.tables["teams"].insert(), {
            "id": team_id,
            "club_id": club_id,
            "created_at": datetime(2026, 1, 5),
        })
        connection.execute(metadata.tables["tournaments"].insert(), {
            "id": tournament_id,
            "club_id": club_id,
            "start_date": date(2026, 2, 1),
        })

        context = MigrationContext.configure(connection)
        operations = Operations(context)
        original_op = migration.op
        migration.op = operations

        try:
            migration.upgrade()

            upgraded = sa.MetaData()
            upgraded.reflect(bind=connection)
            seasons = upgraded.tables["seasons"]
            teams = upgraded.tables["teams"]
            tournaments = upgraded.tables["tournaments"]

            season = connection.execute(
                sa.select(seasons)
            ).one()
            team = connection.execute(sa.select(teams)).one()
            tournament = connection.execute(
                sa.select(tournaments)
            ).one()

            assert season.club_id == club_id
            assert season.name == "Temporada inicial"
            assert season.status == "active"
            assert season.start_date == date(2025, 12, 15)
            assert team.season_id == season.id
            assert tournament.season_id == season.id

            migration.downgrade()

            downgraded = sa.inspect(connection)
            assert "seasons" not in downgraded.get_table_names()
            assert "season_id" not in {
                column["name"]
                for column in downgraded.get_columns("teams")
            }
            assert "season_id" not in {
                column["name"]
                for column in downgraded.get_columns("tournaments")
            }
        finally:
            migration.op = original_op


def test_migration_handles_empty_legacy_database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'empty-season.db'}")
    migration = importlib.import_module(MIGRATION_MODULE)

    with engine.begin() as connection:
        _create_legacy_schema(connection)
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        original_op = migration.op
        migration.op = operations

        try:
            migration.upgrade()
            assert connection.execute(
                sa.text("SELECT COUNT(*) FROM seasons")
            ).scalar() == 0
        finally:
            migration.op = original_op
