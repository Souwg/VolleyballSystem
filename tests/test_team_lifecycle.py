import importlib
import uuid
from datetime import date, datetime, time

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from src.api.dashboard_service import _get_sports_structure
from src.api.models import (
    MatchSession,
    Player,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TournamentTeam,
    TrainingSession,
    db,
)
from src.api.onboarding_service import get_club_onboarding_progress


MIGRATION_MODULE = (
    "migrations.versions.f1d8c3a7b920_add_team_lifecycle_status"
)


def _new_player(world, suffix="Lifecycle"):
    player = Player(
        first_name="Nueva",
        last_name=suffix,
        sex="female",
        main_position="setter",
        is_active=True,
        club=world.club_a,
    )
    db.session.add(player)
    db.session.commit()
    return player


def _training_payload(team):
    return {
        "team_id": team.id,
        "date": "2026-08-10",
        "start_time": "17:00",
        "end_time": "19:00",
        "location": "Cancha principal",
    }


def _match_payload(team):
    return {
        "team_id": team.id,
        "date": "2026-08-11",
        "opponent_name": "Rival",
        "match_type": "official",
    }


def _tournament(world, suffix="Lifecycle"):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name=f"Torneo {suffix} {uuid.uuid4().hex[:6]}",
        start_date=date(2026, 8, 20),
        status="active",
        created_by=world.owner_a.id,
    )
    db.session.add(tournament)
    db.session.commit()
    return tournament


def _archive(client, world, auth_headers, team=None, user=None):
    return client.put(
        f"/api/teams/{(team or world.team_a).id}/archive",
        headers=auth_headers(user or world.owner_a),
    )


def test_new_team_defaults_to_active_and_serializes(world):
    assert world.team_a.status == "active"
    assert world.team_a.serialize()["status"] == "active"


def test_team_rejects_invalid_lifecycle_status(world):
    world.team_a.status = "deleted"
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_owner_can_archive_team(client, world, auth_headers):
    response = _archive(client, world, auth_headers)

    assert response.status_code == 200
    assert response.get_json()["team"]["status"] == "archived"
    assert db.session.get(Team, world.team_a.id).status == "archived"


def test_archived_team_and_roster_remain_readable(client, world, auth_headers):
    _archive(client, world, auth_headers)

    detail = client.get(
        f"/api/teams/{world.team_a.id}",
        headers=auth_headers(world.owner_a),
    )
    roster = client.get(
        f"/api/teams/{world.team_a.id}/players",
        headers=auth_headers(world.coach_a),
    )

    assert detail.status_code == 200
    assert detail.get_json()["team"]["status"] == "archived"
    assert roster.status_code == 200
    assert roster.get_json()["total_players"] == len(world.players_a)


def test_archived_team_is_absent_from_operational_lists(
    client, world, auth_headers
):
    _archive(client, world, auth_headers)

    teams = client.get("/api/teams", headers=auth_headers(world.owner_a))
    category = client.get(
        f"/api/categories/{world.category_a.id}",
        headers=auth_headers(world.owner_a),
    )

    assert world.team_a.id not in {
        row["id"] for row in teams.get_json()["teams"]
    }
    assert world.team_a.id not in {
        row["id"] for row in category.get_json()["teams"]
    }


def test_archived_team_rejects_existing_player_membership(
    client, world, auth_headers
):
    player = _new_player(world)
    _archive(client, world, auth_headers)

    response = client.post(
        f"/api/teams/{world.team_a.id}/players/existing",
        json={"player_id": player.id, "player_number": 30},
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    assert TeamPlayer.query.filter_by(player_id=player.id).count() == 0


def test_archived_team_rejects_new_player_membership(
    client, world, auth_headers
):
    _archive(client, world, auth_headers)

    response = client.post(
        "/api/players",
        json={
            "first_name": "No",
            "last_name": "Creada",
            "sex": "female",
            "main_position": "setter",
            "team_id": world.team_a.id,
            "player_number": 31,
        },
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    assert Player.query.filter_by(last_name="Creada").count() == 0


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/trainings", _training_payload),
        ("/api/matches", _match_payload),
    ],
)
def test_archived_team_rejects_new_sports_activity(
    client, world, auth_headers, path, payload
):
    _archive(client, world, auth_headers)

    response = client.post(
        path,
        json=payload(world.team_a),
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"


def test_archived_team_cannot_join_tournament(client, world, auth_headers):
    tournament = _tournament(world)
    _archive(client, world, auth_headers)

    response = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        json={"team_id": world.team_a.id, "registration_fee": 0},
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"


def test_archived_team_cannot_receive_tournament_players(
    client, world, auth_headers
):
    tournament = _tournament(world)
    entry = TournamentTeam(
        tournament=tournament,
        team=world.team_a,
        status="active",
        registration_fee=0,
    )
    db.session.add(entry)
    db.session.commit()
    _archive(client, world, auth_headers)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        json={"player_ids": [world.players_a[0].id]},
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"


def test_archive_preserves_memberships_and_sports_history(
    client, world, auth_headers
):
    membership = TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[0].id,
    ).one()
    joined_at = membership.joined_at
    training = TrainingSession(
        team=world.team_a,
        date=date(2026, 7, 1),
        start_time=time(17),
        end_time=time(19),
        location="Histórica",
        status="completed",
        created_by=world.owner_a.id,
    )
    match = MatchSession(
        team=world.team_a,
        date=date(2026, 7, 2),
        opponent_name="Histórico",
        match_type="official",
        is_completed=True,
        created_by=world.owner_a.id,
    )
    db.session.add_all([training, match])
    db.session.commit()

    _archive(client, world, auth_headers)

    db.session.refresh(membership)
    assert membership.joined_at == joined_at
    assert membership.left_at is None
    assert TeamPlayer.query.filter_by(team_id=world.team_a.id).count() == 8
    assert db.session.get(TrainingSession, training.id) is not None
    assert db.session.get(MatchSession, match.id) is not None
    assert client.get(
        f"/api/trainings/{training.id}",
        headers=auth_headers(world.owner_a),
    ).status_code == 200
    assert client.get(
        f"/api/matches/{match.id}",
        headers=auth_headers(world.owner_a),
    ).status_code == 200


def test_owner_can_reactivate_team_in_active_season(
    client, world, auth_headers
):
    _archive(client, world, auth_headers)

    response = client.put(
        f"/api/teams/{world.team_a.id}/reactivate",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert response.get_json()["team"]["status"] == "active"


def test_team_cannot_be_reactivated_in_closed_season(
    client, world, auth_headers
):
    _archive(client, world, auth_headers)
    world.season_a.status = "closed"
    db.session.commit()

    response = client.put(
        f"/api/teams/{world.team_a.id}/reactivate",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"
    assert db.session.get(Team, world.team_a.id).status == "archived"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/trainings", _training_payload),
        ("/api/matches", _match_payload),
    ],
)
def test_closed_season_rejects_new_sports_activity(
    client, world, auth_headers, path, payload
):
    world.season_a.status = "closed"
    db.session.commit()

    response = client.post(
        path,
        json=payload(world.team_a),
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"


def test_closed_season_rejects_membership(client, world, auth_headers):
    player = _new_player(world, "Closed")
    world.season_a.status = "closed"
    db.session.commit()

    response = client.post(
        f"/api/teams/{world.team_a.id}/players/existing",
        json={"player_id": player.id, "player_number": 32},
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"


def test_closed_season_rejects_new_tournament_team(
    client, world, auth_headers
):
    tournament = _tournament(world, "Closed")
    world.season_a.status = "closed"
    db.session.commit()

    response = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        json={"team_id": world.team_a.id, "registration_fee": 0},
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/categories/{category_id}/teams",
            {"name": "Equipo cerrado", "gender": "female"},
        ),
        (
            "/api/tournaments",
            {
                "name": "Torneo cerrado",
                "start_date": "2026-09-01",
                "default_referee_fee": 0,
            },
        ),
    ],
)
def test_closed_season_rejects_new_structure(
    client, world, auth_headers, path, payload
):
    world.season_a.status = "closed"
    db.session.commit()

    response = client.post(
        path.format(category_id=world.category_a.id),
        json=payload,
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"


def test_closed_season_historical_team_remains_readable(
    client, world, auth_headers
):
    world.season_a.status = "closed"
    db.session.commit()

    response = client.get(
        f"/api/teams/{world.team_a.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200


def test_planned_season_team_is_readable_and_accepts_owner_roster_preparation(
    client, world, auth_headers
):
    planned = Season(
        club=world.club_a,
        name="Temporada 2027",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    future_team = Team(
        name="Equipo futuro",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned,
    )
    player = _new_player(world, "Future")
    db.session.add_all([planned, future_team])
    db.session.commit()

    detail = client.get(
        f"/api/teams/{future_team.id}",
        headers=auth_headers(world.owner_a),
    )
    membership = client.post(
        f"/api/teams/{future_team.id}/players/existing",
        json={"player_id": player.id, "player_number": 33},
        headers=auth_headers(world.owner_a),
    )

    assert detail.status_code == 200
    assert membership.status_code == 201
    assert membership.get_json()["player"]["team_id"] == future_team.id


def test_dashboard_and_onboarding_ignore_archived_team(
    client, world, auth_headers
):
    world.club_a.location = "Cancha"
    _archive(client, world, auth_headers)

    structure = _get_sports_structure(world.club_a.id, world.season_a.id)
    progress = get_club_onboarding_progress(world.club_a)

    assert world.team_a.id not in {
        row["team_id"] for row in structure["empty_teams"]["teams"]
    }
    assert progress == {"step": 3, "status": "pending"}


@pytest.mark.parametrize("action", ["archive", "reactivate"])
def test_cross_tenant_team_lifecycle_is_rejected(
    client, world, auth_headers, action
):
    response = client.put(
        f"/api/teams/{world.team_b.id}/{action}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 404
    assert db.session.get(Team, world.team_b.id).status == "active"


@pytest.mark.parametrize("role", ["coach_a", "staff_a"])
@pytest.mark.parametrize("action", ["archive", "reactivate"])
def test_only_owner_can_change_team_lifecycle(
    client, world, auth_headers, role, action
):
    response = client.put(
        f"/api/teams/{world.team_a.id}/{action}",
        headers=auth_headers(getattr(world, role)),
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"


def test_safe_physical_delete_behavior_is_unchanged(
    client, world, auth_headers
):
    empty = Team(
        name="Temporal",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    db.session.add(empty)
    db.session.commit()

    response = client.delete(
        f"/api/teams/{empty.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert db.session.get(Team, empty.id) is None


def test_team_status_migration_backfills_constraints_and_downgrades(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'team-status.db'}")
    metadata = sa.MetaData()
    teams = sa.Table(
        "teams",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(teams.insert(), {
            "id": str(uuid.uuid4()),
            "name": "Existente",
        })
        migration = importlib.import_module(MIGRATION_MODULE)
        original_op = migration.op
        migration.op = Operations(MigrationContext.configure(connection))

        try:
            migration.upgrade()
            upgraded = sa.MetaData()
            upgraded.reflect(bind=connection)
            row = connection.execute(
                sa.select(upgraded.tables["teams"])
            ).one()
            assert row.status == "active"
            assert not next(
                column
                for column in sa.inspect(connection).get_columns("teams")
                if column["name"] == "status"
            )["nullable"]

            with pytest.raises(IntegrityError):
                connection.execute(sa.text(
                    "UPDATE teams SET status = 'invalid'"
                ))

            migration.downgrade()
            assert "status" not in {
                column["name"]
                for column in sa.inspect(connection).get_columns("teams")
            }
        finally:
            migration.op = original_op
