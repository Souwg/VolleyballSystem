import importlib
import uuid
from datetime import date, datetime, time

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from src.api.dashboard_service import _get_sports_structure
from src.api.endpoints.matches import sync_match_roster_if_open
from src.api.models import (
    MatchPlayer,
    MatchSession,
    Player,
    TeamPlayer,
    Tournament,
    TournamentTeam,
    TrainingPlayer,
    TrainingSession,
    db,
)
from src.api.onboarding_service import get_club_onboarding_progress
from src.api.training_service import sync_training_roster


MIGRATION_MODULE = (
    "migrations.versions."
    "e7c1a5b9d240_add_team_player_membership_history"
)


def _membership(world, index=0):
    return TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[index].id,
        left_at=None,
    ).one()


def _close_membership(world, index=0, left_at=None):
    membership = _membership(world, index)
    membership.left_at = left_at or datetime(2026, 6, 30, 12, 0)
    db.session.commit()
    return membership


def _new_player(world, suffix="Nueva"):
    player = Player(
        first_name=suffix,
        last_name="Histórica",
        sex="female",
        main_position="setter",
        is_active=True,
        club=world.club_a,
    )
    db.session.add(player)
    db.session.commit()
    return player


def _create_tournament_entry(world):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name=f"Torneo {uuid.uuid4().hex[:8]}",
        start_date=date(2026, 8, 1),
        status="active",
        created_by=world.owner_a.id,
    )
    entry = TournamentTeam(
        tournament=tournament,
        team=world.team_a,
        status="active",
        registration_fee=0,
    )
    db.session.add_all([tournament, entry])
    db.session.commit()
    return entry


def _legacy_team_players_schema(connection):
    metadata = sa.MetaData()
    table = sa.Table(
        "team_players",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("player_id", sa.String(36), nullable=False),
        sa.Column("player_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "team_id",
            "player_id",
            name="unique_player_per_team",
        ),
        sa.UniqueConstraint(
            "team_id",
            "player_number",
            name="unique_number_per_team",
        ),
    )
    metadata.create_all(connection)
    return table


def _run_migration(connection, action):
    migration = importlib.import_module(MIGRATION_MODULE)
    original_op = migration.op
    migration.op = Operations(MigrationContext.configure(connection))

    try:
        getattr(migration, action)()
    finally:
        migration.op = original_op


def test_new_membership_is_open_and_serializes_lifecycle(world):
    membership = _membership(world)

    assert membership.joined_at is not None
    assert membership.left_at is None
    assert membership.serialize()["joined_at"] == membership.joined_at.isoformat()
    assert membership.serialize()["left_at"] is None


def test_remove_closes_membership_without_deleting_it(
    client,
    world,
    auth_headers,
):
    membership = _membership(world)
    membership_id = membership.id

    response = client.delete(
        f"/api/teams/{world.team_a.id}/players/{world.players_a[0].id}",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 200
    persisted = TeamPlayer.query.get(membership_id)
    assert persisted is not None
    assert persisted.left_at is not None


def test_remove_rejects_cross_tenant_team(client, world, auth_headers):
    response = client.delete(
        f"/api/teams/{world.team_a.id}/players/{world.players_a[0].id}",
        headers=auth_headers(world.coach_b),
    )

    assert response.status_code == 404
    assert _membership(world).left_at is None


def test_reentry_creates_new_membership_and_preserves_closed_stage(
    client,
    world,
    auth_headers,
):
    original = _close_membership(world)
    original_id = original.id
    original_left_at = original.left_at

    response = client.post(
        f"/api/teams/{world.team_a.id}/players/existing",
        headers=auth_headers(world.owner_a),
        json={"player_id": world.players_a[0].id, "player_number": 40},
    )

    assert response.status_code == 201
    stages = TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[0].id,
    ).order_by(TeamPlayer.joined_at, TeamPlayer.id).all()
    assert len(stages) == 2
    assert TeamPlayer.query.get(original_id).left_at == original_left_at
    assert sum(stage.left_at is None for stage in stages) == 1
    assert next(stage for stage in stages if stage.left_at is None).id != original_id

    players_response = client.get(
        "/api/players",
        headers=auth_headers(world.owner_a),
    )
    player_row = next(
        player
        for player in players_response.get_json()["players"]
        if player["id"] == world.players_a[0].id
    )
    assert player_row["team_id"] == world.team_a.id
    assert player_row["player_number"] == 40


def test_only_one_open_membership_per_player_and_team(world):
    duplicate = TeamPlayer(
        team=world.team_a,
        player=world.players_a[0],
        player_number=40,
        status="active",
    )
    db.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_multiple_closed_memberships_for_same_player_and_team_are_allowed(world):
    first = _close_membership(world)
    second = TeamPlayer(
        team=world.team_a,
        player=world.players_a[0],
        player_number=41,
        status="active",
        joined_at=datetime(2026, 9, 1),
        left_at=datetime(2026, 12, 1),
    )
    db.session.add(second)
    db.session.commit()

    assert first.left_at is not None
    assert TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[0].id,
    ).count() == 2


def test_closed_number_can_be_reused_by_an_open_membership(world):
    _close_membership(world)
    player = _new_player(world, "Número reutilizado")
    replacement = TeamPlayer(
        team=world.team_a,
        player=player,
        player_number=1,
        status="active",
    )
    db.session.add(replacement)
    db.session.commit()

    assert replacement.left_at is None


def test_duplicate_number_between_open_memberships_is_rejected(world):
    player = _new_player(world, "Número duplicado")
    duplicate = TeamPlayer(
        team=world.team_a,
        player=player,
        player_number=1,
        status="active",
    )
    db.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db.session.commit()


@pytest.mark.parametrize("status", ["injured", "inactive"])
def test_non_active_status_is_still_an_open_membership(
    client,
    world,
    auth_headers,
    status,
):
    membership = _membership(world)
    membership.status = status
    db.session.commit()

    response = client.get(
        f"/api/teams/{world.team_a.id}/players",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 200
    row = next(
        player
        for player in response.get_json()["players"]
        if player["id"] == world.players_a[0].id
    )
    assert row["status"] == status


def test_closed_active_membership_is_not_in_current_team_roster(
    client,
    world,
    auth_headers,
):
    membership = _close_membership(world)
    assert membership.status == "active"

    response = client.get(
        f"/api/teams/{world.team_a.id}/players",
        headers=auth_headers(world.coach_a),
    )

    ids = {player["id"] for player in response.get_json()["players"]}
    assert world.players_a[0].id not in ids


def test_closed_membership_is_not_added_to_new_match_snapshot(world):
    closed = _close_membership(world)
    match = MatchSession(
        team=world.team_a,
        date=date(2026, 8, 5),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(match)
    db.session.flush()

    sync_match_roster_if_open(match)

    snapshot_ids = {
        row.player_id
        for row in MatchPlayer.query.filter_by(match_id=match.id).all()
    }
    assert closed.player_id not in snapshot_ids
    assert world.players_a[1].id in snapshot_ids


def test_closed_membership_is_not_added_to_new_training_snapshot(world):
    closed = _close_membership(world)
    training = TrainingSession(
        team=world.team_a,
        date=date(2026, 8, 6),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    db.session.flush()

    sync_training_roster(training)
    db.session.flush()

    snapshot_ids = {
        row.player_id
        for row in TrainingPlayer.query.filter_by(training_id=training.id).all()
    }
    assert closed.player_id not in snapshot_ids
    assert world.players_a[1].id in snapshot_ids


def test_tournament_roster_and_registration_reject_closed_membership(
    client,
    world,
    auth_headers,
):
    closed = _close_membership(world)
    entry = _create_tournament_entry(world)

    roster_response = client.get(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
    )
    registration_response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [closed.player_id]},
    )

    roster_ids = {
        player["player_id"]
        for player in roster_response.get_json()["players"]
    }
    assert roster_response.status_code == 200
    assert closed.player_id not in roster_ids
    assert registration_response.status_code == 400
    assert registration_response.get_json()["code"] == "PLAYER_NOT_IN_TEAM"


def test_player_list_never_selects_closed_membership_as_current_team(
    client,
    world,
    auth_headers,
):
    closed = _close_membership(world)

    response = client.get(
        "/api/players",
        headers=auth_headers(world.owner_a),
    )

    row = next(
        player
        for player in response.get_json()["players"]
        if player["id"] == closed.player_id
    )
    assert row["team_id"] is None
    assert row["teams"] == []


def test_current_team_counts_ignore_closed_memberships(
    client,
    world,
    auth_headers,
):
    _close_membership(world)

    team_response = client.get(
        f"/api/teams/{world.team_a.id}",
        headers=auth_headers(world.owner_a),
    )
    category_response = client.get(
        f"/api/categories/{world.category_a.id}",
        headers=auth_headers(world.owner_a),
    )

    team_row = category_response.get_json()["teams"][0]
    assert team_response.get_json()["stats"]["total_players"] == 7
    assert team_row["total_players"] == 7


def test_dashboard_treats_closed_membership_as_no_current_team(
    world,
):
    closed = _close_membership(world)

    result = _get_sports_structure(world.club_a.id, world.season_a.id)

    player_ids = {
        player["player_id"]
        for player in result["players_without_team"]["players"]
    }
    assert closed.player_id in player_ids


def test_onboarding_counts_only_open_memberships(world):
    world.club_a.location = "Cancha principal"
    for membership in TeamPlayer.query.filter_by(team_id=world.team_a.id).all():
        membership.left_at = datetime(2026, 6, 30)
    db.session.commit()

    progress = get_club_onboarding_progress(world.club_a)

    assert progress == {"step": 4, "status": "pending"}


def test_real_history_scenario_keeps_two_stages_and_one_current_roster_row(
    client,
    world,
    auth_headers,
):
    maria = _new_player(world, "María")
    first = TeamPlayer(
        team=world.team_a,
        player=maria,
        player_number=30,
        status="active",
        joined_at=datetime(2026, 1, 10),
        left_at=datetime(2026, 6, 30),
    )
    second = TeamPlayer(
        team=world.team_a,
        player=maria,
        player_number=31,
        status="active",
        joined_at=datetime(2026, 9, 1),
    )
    db.session.add_all([first, second])
    db.session.commit()

    response = client.get(
        f"/api/teams/{world.team_a.id}/players",
        headers=auth_headers(world.coach_a),
    )

    stages = TeamPlayer.query.filter_by(player_id=maria.id).all()
    roster_rows = [
        player
        for player in response.get_json()["players"]
        if player["id"] == maria.id
    ]
    assert len(stages) == 2
    assert first.left_at == datetime(2026, 6, 30)
    assert second.left_at is None
    assert len(roster_rows) == 1
    assert roster_rows[0]["player_number"] == 31


def test_migration_backfills_created_at_and_downgrades_immediately(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'membership.db'}")
    created_at = datetime(2025, 12, 15, 9, 30)

    with engine.begin() as connection:
        table = _legacy_team_players_schema(connection)
        connection.execute(table.insert(), {
            "id": str(uuid.uuid4()),
            "team_id": "team-a",
            "player_id": "player-a",
            "player_number": 7,
            "status": "active",
            "created_at": created_at,
        })

        _run_migration(connection, "upgrade")
        row = connection.execute(sa.text(
            "SELECT joined_at, left_at FROM team_players"
        )).one()
        assert datetime.fromisoformat(row.joined_at) == created_at
        assert row.left_at is None
        assert {
            index["name"]
            for index in sa.inspect(connection).get_indexes("team_players")
        } == {
            "uq_team_players_open_player",
            "uq_team_players_open_number",
        }

        _run_migration(connection, "downgrade")
        columns = {
            column["name"]
            for column in sa.inspect(connection).get_columns("team_players")
        }
        assert "joined_at" not in columns
        assert "left_at" not in columns


def test_migration_falls_back_when_legacy_created_at_is_null(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'fallback.db'}")

    with engine.begin() as connection:
        table = _legacy_team_players_schema(connection)
        connection.execute(table.insert(), {
            "id": str(uuid.uuid4()),
            "team_id": "team-a",
            "player_id": "player-a",
            "player_number": 7,
            "status": "active",
            "created_at": None,
        })

        _run_migration(connection, "upgrade")

        assert connection.execute(sa.text(
            "SELECT joined_at FROM team_players"
        )).scalar() is not None


def test_migration_downgrade_refuses_to_destroy_new_history(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'history.db'}")

    with engine.begin() as connection:
        table = _legacy_team_players_schema(connection)
        connection.execute(table.insert(), {
            "id": "stage-1",
            "team_id": "team-a",
            "player_id": "player-a",
            "player_number": 7,
            "status": "active",
            "created_at": datetime(2026, 1, 10),
        })
        _run_migration(connection, "upgrade")
        connection.execute(sa.text(
            "UPDATE team_players SET left_at = '2026-06-30' "
            "WHERE id = 'stage-1'"
        ))
        connection.execute(sa.text(
            "INSERT INTO team_players "
            "(id, team_id, player_id, player_number, status, created_at, "
            "joined_at, left_at) VALUES "
            "('stage-2', 'team-a', 'player-a', 8, 'active', "
            "'2026-09-01', '2026-09-01', NULL)"
        ))

        with pytest.raises(RuntimeError, match="múltiples etapas históricas"):
            _run_migration(connection, "downgrade")
