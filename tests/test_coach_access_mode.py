import importlib
import uuid
from datetime import date, datetime

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Flask
from flask_jwt_extended import create_access_token

from src.api.admin import (
    ClubAdminView,
    SystemAdminOnly,
    is_flask_admin_enabled,
    setup_admin,
)
from src.api.coach_access import get_coach_access_readiness
from src.api.models import (
    db,
    AdministrativeArea,
    Club,
    Country,
    Player,
    Season,
    Team,
    TeamCoachAssignment,
    TeamPlayer,
    Tournament,
    TournamentTeam,
    User,
)
from src.api.onboarding_service import get_club_onboarding_progress
from tests.test_coach_team_enforcement import _assign, _coach, _team


MODE_URL = "/api/club/coach-access-mode"
DEFAULT_MIGRATION = (
    "migrations.versions.d7a2c9e4f150_default_coach_access_team_assigned"
)
ONBOARDING_MIGRATION = (
    "migrations.versions.e8b3d1f6a274_add_club_onboarding_finished_at"
)


def _set_mode(client, auth_headers, user, mode):
    return client.put(
        MODE_URL,
        headers=auth_headers(user),
        json={"coach_access_mode": mode},
    )


def _create_match(client, auth_headers, user, team):
    return client.post(
        "/api/matches",
        headers=auth_headers(user),
        json={
            "team_id": team.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
        },
    )


def _code(response):
    return response.get_json().get("code")


def _assignments_state():
    db.session.expire_all()
    return sorted(
        (row.id, row.team_id, row.user_id, row.removed_at)
        for row in TeamCoachAssignment.query.all()
    )


def _structure_state():
    db.session.expire_all()
    return {
        "memberships": sorted(
            (row.id, row.left_at, row.status)
            for row in TeamPlayer.query.all()
        ),
        "seasons": sorted(
            (row.id, row.status) for row in Season.query.all()
        ),
        "teams": sorted((row.id, row.status) for row in Team.query.all()),
    }


def _season(world, status):
    season = Season(
        name=f"Temporada {status} {uuid.uuid4().hex[:6]}",
        start_date=date(2027, 1, 1),
        status=status,
        club=world.club_a,
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return season


def _onboarded(world):
    world.club_a.location = "Cancha principal"
    world.club_a.onboarding_finished_at = datetime(2026, 1, 1)
    db.session.commit()


def _status(client, auth_headers, user):
    return client.get(
        "/api/onboarding/status",
        headers=auth_headers(user),
    ).get_json()


# =========================
# Default del modo
# =========================


def test_model_defaults_new_clubs_to_team_assigned(world):
    column = Club.__table__.c.coach_access_mode

    assert column.default.arg == "team_assigned"
    assert column.server_default.arg == "team_assigned"

    club = Club(
        name="Nuevo",
        owner_id=str(uuid.uuid4()),
        sport=world.sport,
        timezone="America/Caracas",
        currency_code="USD",
    )
    db.session.add(club)
    db.session.flush()

    assert club.coach_access_mode == "team_assigned"
    db.session.rollback()


def _create_client(client, world, auth_headers, monkeypatch, **extra):
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
            "full_name": "Owner Nuevo",
            "email": "owner-nuevo@example.com",
            "club_name": "Club Nuevo",
            "sport_id": world.sport.id,
            "country_id": country.id,
            "administrative_area_id": area.id,
            "city": "Caracas",
            "timezone": "America/Caracas",
            "currency_code": "USD",
            **extra,
        },
    )

    assert response.status_code == 201, response.get_json()
    return User.query.filter_by(email="owner-nuevo@example.com").one()


def test_new_club_end_to_end_requires_assignment_to_operate(
    client, world, auth_headers, monkeypatch
):
    owner = _create_client(client, world, auth_headers, monkeypatch)
    owner.first_login = False
    club = db.session.get(Club, owner.club_id)

    assert club.coach_access_mode == "team_assigned"
    assert club.onboarding_finished_at is None
    assert get_club_onboarding_progress(club)["status"] == "pending"

    season = Season.query.filter_by(club_id=club.id, status="active").one()
    category = world.category_a.__class__(name="Sub-16", club=club)
    team = Team(
        name="Sub-16",
        gender="female",
        category=category,
        club=club,
        season=season,
    )
    coach = User(
        id=str(uuid.uuid4()),
        full_name="Coach Nuevo",
        email="coach-nuevo@example.com",
        password="unused",
        role="coach",
        first_login=False,
        is_active=True,
        session_version=0,
        club=club,
    )
    player = Player(
        first_name="Primera",
        last_name="Jugadora",
        sex="female",
        is_active=True,
        club=club,
    )
    db.session.add_all([category, team, coach, player])
    db.session.commit()

    first_member = client.post(
        f"/api/teams/{team.id}/players/existing",
        headers=auth_headers(owner),
        json={"player_id": player.id, "player_number": 1},
    )

    assert first_member.status_code == 201
    assert TeamCoachAssignment.query.count() == 0

    teams = client.get("/api/teams", headers=auth_headers(coach))

    assert teams.status_code == 200
    assert teams.get_json()["teams"][0]["can_manage"] is False

    denied = _create_match(client, auth_headers, coach, team)

    assert denied.status_code == 403
    assert _code(denied) == "TEAM_NOT_ASSIGNED"

    assigned = client.post(
        f"/api/teams/{team.id}/coaches",
        headers=auth_headers(owner),
        json={"user_id": coach.id},
    )

    assert assigned.status_code == 201
    assert _create_match(client, auth_headers, coach, team).status_code == 201


def test_create_client_ignores_mode_in_payload(
    client, world, auth_headers, monkeypatch
):
    owner = _create_client(
        client,
        world,
        auth_headers,
        monkeypatch,
        coach_access_mode="club_wide",
    )

    assert db.session.get(Club, owner.club_id).coach_access_mode == (
        "team_assigned"
    )


# =========================
# API del modo
# =========================


def test_owner_reads_mode_and_readiness(client, world, auth_headers):
    response = client.get(MODE_URL, headers=auth_headers(world.owner_a))

    assert response.status_code == 200
    data = response.get_json()
    assert data["coach_access_mode"] == "club_wide"
    assert data["readiness"] == {
        "active_coaches": 1,
        "coaches_without_team": 1,
        "active_teams_without_coach": 1,
        "planned_teams_without_coach": 0,
    }


def test_owner_switches_mode_both_ways(client, world, auth_headers):
    activated = _set_mode(client, auth_headers, world.owner_a, "team_assigned")

    assert activated.status_code == 200
    assert activated.get_json()["coach_access_mode"] == "team_assigned"
    assert activated.get_json()["club"]["coach_access_mode"] == "team_assigned"
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == (
        "team_assigned"
    )

    restored = _set_mode(client, auth_headers, world.owner_a, "club_wide")

    assert restored.status_code == 200
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == "club_wide"


def test_same_mode_is_idempotent(client, world, auth_headers):
    assignments = _assignments_state()
    structure = _structure_state()

    for _ in range(2):
        response = _set_mode(client, auth_headers, world.owner_a, "club_wide")

        assert response.status_code == 200
        assert response.get_json()["coach_access_mode"] == "club_wide"

    assert _assignments_state() == assignments
    assert _structure_state() == structure


@pytest.mark.parametrize("mode", ["other", "", None, 1, "TEAM_ASSIGNED"])
def test_invalid_mode_is_rejected(client, world, auth_headers, mode):
    response = _set_mode(client, auth_headers, world.owner_a, mode)

    assert response.status_code == 400
    assert _code(response) == "INVALID_COACH_ACCESS_MODE"
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == "club_wide"


def test_missing_mode_is_rejected(client, world, auth_headers):
    response = client.put(
        MODE_URL,
        headers=auth_headers(world.owner_a),
        json={},
    )

    assert response.status_code == 400
    assert _code(response) == "INVALID_COACH_ACCESS_MODE"


@pytest.mark.parametrize("user_key", ["coach_a", "staff_a", "system_admin"])
def test_only_owner_controls_mode(client, world, auth_headers, user_key):
    user = getattr(world, user_key)

    write = _set_mode(client, auth_headers, user, "team_assigned")
    read = client.get(MODE_URL, headers=auth_headers(user))

    assert write.status_code == 403
    assert read.status_code == 403
    assert _code(write) == "FORBIDDEN"
    assert _code(read) == "FORBIDDEN"
    assert "readiness" not in read.get_json()
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == "club_wide"


def test_mode_is_scoped_to_the_owner_club(client, world, auth_headers):
    _assign(world)

    response = _set_mode(client, auth_headers, world.owner_b, "team_assigned")

    assert response.status_code == 200
    assert response.get_json()["club"]["id"] == world.club_b.id
    assert response.get_json()["readiness"]["active_coaches"] == 1
    assert response.get_json()["readiness"]["coaches_without_team"] == 1
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == "club_wide"
    assert db.session.get(Club, world.club_b.id).coach_access_mode == (
        "team_assigned"
    )


def test_general_club_update_still_cannot_change_mode(
    client, world, auth_headers
):
    response = client.put(
        "/api/club",
        headers=auth_headers(world.owner_a),
        json={"coach_access_mode": "team_assigned"},
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == "club_wide"


@pytest.mark.parametrize(
    "target", ["team_assigned", "club_wide"]
)
def test_switching_mode_never_touches_assignments_or_structure(
    client, world, auth_headers, target
):
    other = _team(world, "Otro")
    _assign(world)
    _assign(world, coach=_coach(world, "Dos"), team=other)
    world.club_a.coach_access_mode = (
        "club_wide" if target == "team_assigned" else "team_assigned"
    )
    db.session.commit()
    assignments = _assignments_state()
    structure = _structure_state()

    response = _set_mode(client, auth_headers, world.owner_a, target)

    assert response.status_code == 200
    assert _assignments_state() == assignments
    assert _structure_state() == structure


def test_activation_creates_no_assignments(client, world, auth_headers):
    _team(world, "Otro")
    assert TeamCoachAssignment.query.count() == 0

    response = _set_mode(client, auth_headers, world.owner_a, "team_assigned")

    assert response.status_code == 200
    assert TeamCoachAssignment.query.count() == 0


def test_readiness_ignores_archived_and_closed(world):
    archived = _team(world, "Archivado")
    archived.status = "archived"
    closed = _team(world, "Cerrado", season=_season(world, "closed"))
    planned = _team(world, "Planificado", season=_season(world, "planned"))
    _assign(world, team=archived)
    other_coach = _coach(world, "Dos")
    _assign(world, coach=other_coach, team=planned)
    inactive = _coach(world, "Inactivo")
    inactive.is_active = False
    db.session.commit()

    assert closed.status == "active"
    assert get_coach_access_readiness(world.club_a.id) == {
        "active_coaches": 2,
        "coaches_without_team": 1,
        "active_teams_without_coach": 1,
        "planned_teams_without_coach": 0,
    }


# =========================
# Efecto inmediato sin nuevo login
# =========================


def test_legacy_club_lifecycle_without_new_login(client, world, auth_headers):
    world.club_a.location = "Cancha"
    db.session.commit()
    coach = world.coach_a
    team = world.team_a

    assert world.club_a.coach_access_mode == "club_wide"
    assert _create_match(client, auth_headers, coach, team).status_code == 201

    token_headers = auth_headers(coach)

    assert _set_mode(
        client, auth_headers, world.owner_a, "team_assigned"
    ).status_code == 200

    denied = client.post(
        "/api/matches",
        headers=token_headers,
        json={
            "team_id": team.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
        },
    )

    assert denied.status_code == 403
    assert _code(denied) == "TEAM_NOT_ASSIGNED"

    assign = client.post(
        f"/api/teams/{team.id}/coaches",
        headers=auth_headers(world.owner_a),
        json={"user_id": coach.id},
    )

    assert assign.status_code == 201

    allowed = client.post(
        "/api/matches",
        headers=token_headers,
        json={
            "team_id": team.id,
            "date": "2026-11-21",
            "opponent_name": "Rival",
        },
    )

    assert allowed.status_code == 201

    removed = client.delete(
        f"/api/teams/{team.id}/coaches/{coach.id}",
        headers=auth_headers(world.owner_a),
    )

    assert removed.status_code == 200
    denied_again = _create_match(client, auth_headers, coach, team)
    assert denied_again.status_code == 403

    assign_again = client.post(
        f"/api/teams/{team.id}/coaches",
        headers=auth_headers(world.owner_a),
        json={"user_id": coach.id},
    )

    assert assign_again.status_code == 201
    kept = _assignments_state()

    assert _set_mode(
        client, auth_headers, world.owner_a, "club_wide"
    ).status_code == 200
    assert _assignments_state() == kept

    other = _team(world, "Sin asignar")

    assert _create_match(client, auth_headers, coach, other).status_code == 201

    assert _set_mode(
        client, auth_headers, world.owner_a, "team_assigned"
    ).status_code == 200
    assert _create_match(client, auth_headers, coach, team).status_code == 201
    assert _create_match(client, auth_headers, coach, other).status_code == 403


@pytest.mark.parametrize("mode", ["club_wide", "team_assigned"])
def test_mode_does_not_override_lifecycle(client, world, auth_headers, mode):
    world.club_a.coach_access_mode = mode
    archived = _team(world, "Archivado")
    archived.status = "archived"
    closed = _team(world, "Cerrado", season=_season(world, "closed"))
    planned = _team(world, "Planificado", season=_season(world, "planned"))
    db.session.commit()

    for team in [archived, closed, planned]:
        _assign(world, team=team)

    for team, code in [
        (archived, "TEAM_ARCHIVED"),
        (closed, "SEASON_CLOSED"),
        (planned, "ACTIVE_SEASON_REQUIRED"),
    ]:
        response = _create_match(client, auth_headers, world.coach_a, team)

        assert response.status_code == 409, team.name
        assert _code(response) == code, team.name


# =========================
# Onboarding
# =========================


def test_club_that_never_finished_stays_pending(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    db.session.commit()
    assert _status(client, auth_headers, world.owner_a)["status"] == "pending"

    world.club_a.location = "Cancha"
    world.team_a.status = "archived"
    db.session.commit()
    data = _status(client, auth_headers, world.owner_a)

    assert data["status"] == "pending"
    assert data["step"] == 3
    assert world.club_a.onboarding_finished_at is None


def test_completing_location_last_persists_finish(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    db.session.commit()
    response = client.put(
        "/api/club",
        headers=auth_headers(world.owner_a),
        json={"city": "Caracas"},
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at


def test_incomplete_update_does_not_persist_finish(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    world.team_a.status = "archived"
    db.session.commit()

    response = client.put(
        "/api/club",
        headers=auth_headers(world.owner_a),
        json={"city": "Caracas"},
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at is None


def test_first_new_player_persists_finish(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    world.club_a.location = "Cancha"
    empty = _team(world, "Primer equipo")
    TeamPlayer.query.filter_by(team_id=world.team_a.id).delete()
    db.session.commit()

    response = client.post(
        "/api/players",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": "Nueva",
            "last_name": "Jugadora",
            "sex": "female",
            "team_id": empty.id,
            "player_number": 7,
        },
    )

    assert response.status_code == 201
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at


def test_first_existing_player_persists_finish(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    world.club_a.location = "Cancha"
    player = world.players_a[0]
    TeamPlayer.query.filter_by(team_id=world.team_a.id).delete()
    db.session.commit()

    response = client.post(
        f"/api/teams/{world.team_a.id}/players/existing",
        headers=auth_headers(world.owner_a),
        json={"player_id": player.id, "player_number": 9},
    )

    assert response.status_code == 201
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at


def test_reactivating_team_can_finish(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    world.club_a.location = "Cancha"
    world.team_a.status = "archived"
    db.session.commit()

    response = client.put(
        f"/api/teams/{world.team_a.id}/reactivate",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at


def test_finished_club_survives_archiving_last_team(
    client, world, auth_headers
):
    _onboarded(world)

    response = client.put(
        f"/api/teams/{world.team_a.id}/archive",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert _status(client, auth_headers, world.owner_a)["status"] == "completed"
    assert _status(client, auth_headers, world.coach_a)["status"] == "completed"
    assert _status(client, auth_headers, world.staff_a)["status"] == "completed"


def test_finished_club_survives_removing_last_memberships(
    client, world, auth_headers
):
    _onboarded(world)

    for player in world.players_a:
        response = client.delete(
            f"/api/teams/{world.team_a.id}/players/{player.id}",
            headers=auth_headers(world.owner_a),
        )

        assert response.status_code == 200

    assert TeamPlayer.query.filter_by(left_at=None, team_id=world.team_a.id).count() == 0
    assert _status(client, auth_headers, world.owner_a)["status"] == "completed"


def test_finished_club_survives_season_transition(
    client, world, auth_headers
):
    _onboarded(world)
    target = _season(world, "planned")
    _team(world, "Sin deportistas", season=target)

    response = client.post(
        f"/api/seasons/{target.id}/transition",
        headers=auth_headers(world.owner_a),
        json={"source_season_id": world.season_a.id},
    )

    assert response.status_code == 200, response.get_json()
    db.session.expire_all()
    assert db.session.get(Season, world.season_a.id).status == "closed"
    assert _status(client, auth_headers, world.owner_a)["status"] == "completed"


def test_finished_club_keeps_coach_player_creation(
    client, world, auth_headers
):
    _onboarded(world)
    world.team_a.status = "archived"
    db.session.commit()

    response = client.post(
        "/api/players",
        headers=auth_headers(world.coach_a),
        json={
            "first_name": "Nueva",
            "last_name": "Jugadora",
            "sex": "female",
        },
    )

    assert response.status_code == 201


def test_skip_persists_and_is_idempotent(client, world, auth_headers):
    world.club_a.onboarding_finished_at = None
    world.club_b.onboarding_finished_at = None
    db.session.commit()
    assert _status(client, auth_headers, world.owner_a)["status"] == "pending"

    first = client.post(
        "/api/onboarding/finish",
        headers=auth_headers(world.owner_a),
    )

    assert first.status_code == 200
    assert first.get_json()["status"] == "completed"
    assert first.get_json()["step"] == 5
    assert "default_monthly_fee" in first.get_json()["club"]
    db.session.expire_all()
    finished_at = db.session.get(Club, world.club_a.id).onboarding_finished_at
    assert finished_at

    second = client.post(
        "/api/onboarding/finish",
        headers=auth_headers(world.owner_a),
    )

    assert second.status_code == 200
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at == (
        finished_at
    )
    assert _status(client, auth_headers, world.coach_a)["status"] == "completed"
    assert db.session.get(Club, world.club_b.id).onboarding_finished_at is None


@pytest.mark.parametrize("user_key", ["coach_a", "staff_a", "system_admin"])
def test_only_owner_can_skip_onboarding(client, world, auth_headers, user_key):
    world.club_a.onboarding_finished_at = None
    db.session.commit()
    response = client.post(
        "/api/onboarding/finish",
        headers=auth_headers(getattr(world, user_key)),
    )

    assert response.status_code == 403
    assert _code(response) == "FORBIDDEN"
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at is None


def test_club_serialization_stays_minimal(world):
    assert "onboarding_finished_at" not in world.club_a.serialize()


# =========================
# Torneo: el estado se relee bajo bloqueo
# =========================


def _active_entry(world):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name=f"Copa {uuid.uuid4().hex[:6]}",
        start_date=date(2026, 12, 1),
        status="active",
        created_by=world.owner_a.id,
    )
    entry = TournamentTeam(
        tournament=tournament,
        team=world.team_a,
        status="active",
        registration_fee=100,
    )
    db.session.add_all([tournament, entry])
    db.session.commit()
    return entry


@pytest.mark.parametrize("action", ["complete", "cancel"])
def test_finished_tournament_rejects_generation(
    client, world, auth_headers, action
):
    entry = _active_entry(world)
    headers = auth_headers(world.owner_a)

    transition = client.put(
        f"/api/tournaments/{entry.tournament_id}/{action}",
        headers=headers,
    )
    generated = client.post(
        f"/api/tournament-teams/{entry.id}/registration-charges",
        headers=headers,
    )
    fee = client.put(
        f"/api/tournament-teams/{entry.id}/registration-fee",
        headers=headers,
        json={"registration_fee": 5},
    )
    roster = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=headers,
        json={"player_ids": []},
    )

    assert transition.status_code == 200
    assert generated.status_code == 409
    assert fee.status_code == 409
    assert roster.status_code == 409
    assert _code(generated) == "TOURNAMENT_NOT_ACTIVE"
    assert _code(fee) == "TOURNAMENT_NOT_ACTIVE"
    assert _code(roster) == "TOURNAMENT_NOT_ACTIVE"


# =========================
# Flask-Admin
# =========================


@pytest.mark.parametrize(
    "path", ["/admin", "/admin/", "/admin/club/", "/admin/user/edit/"]
)
def test_admin_routes_are_not_found_by_default(client, path):
    assert client.get(path).status_code == 404


def test_platform_admin_screen_still_loads(client):
    assert client.get("/admin/clients").status_code == 200


def test_flask_admin_blueprint_is_not_registered_by_default(app):
    assert "admin" not in app.blueprints


@pytest.mark.parametrize(
    "env, flag, enabled",
    [
        (None, None, False),
        ("production", None, False),
        ("production", "1", False),
        ("development", None, False),
        ("development", "0", False),
        ("development", "true", False),
        ("Development", "1", True),
        ("development", "1", True),
    ],
)
def test_flask_admin_requires_explicit_opt_in(monkeypatch, env, flag, enabled):
    for name, value in [("APP_ENV", env), ("ENABLE_FLASK_ADMIN", flag)]:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    assert is_flask_admin_enabled() is enabled


def test_flask_admin_views_require_system_admin(app, world):
    tokens = {
        "system_admin": create_access_token(identity=world.system_admin.id),
        "owner": create_access_token(identity=world.owner_a.id),
    }

    with app.test_request_context():
        assert SystemAdminOnly().is_accessible() is False

    for role, expected in [("system_admin", True), ("owner", False)]:
        with app.test_request_context(
            headers={"Authorization": f"Bearer {tokens[role]}"}
        ):
            assert SystemAdminOnly().is_accessible() is expected, role


def test_opt_in_flask_admin_stays_closed_and_hides_mode():
    admin_app = Flask("admin-opt-in")
    admin_app.config["SECRET_KEY"] = "test"
    setup_admin(admin_app)

    assert "coach_access_mode" in ClubAdminView.form_excluded_columns

    with admin_app.test_client() as admin_client:
        for path in ["/admin/", "/admin/club/", "/admin/club/edit/"]:
            response = admin_client.get(path)

            assert response.status_code == 302, path
            assert response.headers["Location"].rstrip("/").endswith("localhost") or (
                response.headers["Location"] == "/"
            )


# =========================
# Migraciones
# =========================


def _run(module_name, connection, action):
    migration = importlib.import_module(module_name)
    original = migration.op
    migration.op = Operations(MigrationContext.configure(connection))

    try:
        getattr(migration, action)()
    finally:
        migration.op = original


def _legacy_schema(connection):
    for statement in [
        """CREATE TABLE clubs (
            id VARCHAR(36) PRIMARY KEY,
            city VARCHAR(120),
            location VARCHAR(120),
            access_status VARCHAR(20) NOT NULL DEFAULT 'active',
            currency_code VARCHAR(3) NOT NULL DEFAULT 'USD',
            coach_access_mode VARCHAR(20) NOT NULL DEFAULT 'club_wide'
                CONSTRAINT ck_clubs_coach_access_mode
                CHECK (coach_access_mode IN ('club_wide', 'team_assigned'))
        )""",
        "CREATE TABLE categories (id VARCHAR(36) PRIMARY KEY, club_id VARCHAR(36))",
        """CREATE TABLE seasons (
            id VARCHAR(36) PRIMARY KEY, club_id VARCHAR(36), status VARCHAR(20)
        )""",
        """CREATE TABLE teams (
            id VARCHAR(36) PRIMARY KEY,
            club_id VARCHAR(36),
            season_id VARCHAR(36),
            status VARCHAR(20)
        )""",
        """CREATE TABLE team_players (
            id VARCHAR(36) PRIMARY KEY,
            team_id VARCHAR(36),
            left_at DATETIME
        )""",
    ]:
        connection.execute(sa.text(statement))


def _seed_club(
    connection,
    club_id,
    city="Caracas",
    category=True,
    season_status="active",
    team_status="active",
    left_at=None,
):
    connection.execute(
        sa.text("INSERT INTO clubs (id, city) VALUES (:id, :city)"),
        {"id": club_id, "city": city},
    )

    if category:
        connection.execute(
            sa.text("INSERT INTO categories VALUES (:id, :club)"),
            {"id": f"cat-{club_id}", "club": club_id},
        )

    if season_status:
        connection.execute(
            sa.text("INSERT INTO seasons VALUES (:id, :club, :status)"),
            {"id": f"sea-{club_id}", "club": club_id, "status": season_status},
        )
        connection.execute(
            sa.text("INSERT INTO teams VALUES (:id, :club, :season, :status)"),
            {
                "id": f"team-{club_id}",
                "club": club_id,
                "season": f"sea-{club_id}",
                "status": team_status,
            },
        )
        connection.execute(
            sa.text("INSERT INTO team_players VALUES (:id, :team, :left_at)"),
            {
                "id": f"tp-{club_id}",
                "team": f"team-{club_id}",
                "left_at": left_at,
            },
        )


def test_onboarding_backfill_uses_evidence_not_a_blanket_update(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'onboarding.db'}")

    with engine.begin() as connection:
        _legacy_schema(connection)
        _seed_club(connection, "completo")
        _seed_club(connection, "archivado", team_status="archived")
        _seed_club(connection, "sin-miembros", left_at="2026-01-01")
        _seed_club(connection, "cerrado", season_status="closed")
        _seed_club(connection, "planificado", season_status="planned")
        _seed_club(connection, "sin-ciudad", city=None)
        _seed_club(connection, "sin-categoria", category=False)
        _seed_club(connection, "vacio", season_status=None)

        _run(ONBOARDING_MIGRATION, connection, "upgrade")

        finished = {
            row[0]
            for row in connection.execute(sa.text(
                "SELECT id FROM clubs WHERE onboarding_finished_at IS NOT NULL"
            ))
        }

        assert finished == {"completo", "archivado", "sin-miembros", "cerrado"}

        _run(ONBOARDING_MIGRATION, connection, "downgrade")

        assert "onboarding_finished_at" not in {
            column["name"]
            for column in sa.inspect(connection).get_columns("clubs")
        }

        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.execute(sa.text(
                    "INSERT INTO clubs (id, coach_access_mode) "
                    "VALUES ('mal', 'other')"
                ))


def test_default_migration_changes_only_the_default(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'default.db'}")

    with engine.begin() as connection:
        _legacy_schema(connection)
        connection.execute(sa.text(
            "INSERT INTO clubs (id, coach_access_mode) "
            "VALUES ('legacy', 'club_wide'), ('scoped', 'team_assigned')"
        ))

        _run(DEFAULT_MIGRATION, connection, "upgrade")
        connection.execute(sa.text("INSERT INTO clubs (id) VALUES ('nuevo')"))

        modes = dict(connection.execute(sa.text(
            "SELECT id, coach_access_mode FROM clubs"
        )).fetchall())

        assert modes == {
            "legacy": "club_wide",
            "scoped": "team_assigned",
            "nuevo": "team_assigned",
        }

        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.execute(sa.text(
                    "INSERT INTO clubs (id, coach_access_mode) "
                    "VALUES ('mal', 'other')"
                ))

        _run(DEFAULT_MIGRATION, connection, "downgrade")
        connection.execute(sa.text("INSERT INTO clubs (id) VALUES ('viejo')"))

        modes = dict(connection.execute(sa.text(
            "SELECT id, coach_access_mode FROM clubs"
        )).fetchall())

        assert modes["viejo"] == "club_wide"
        assert modes["legacy"] == "club_wide"
        assert modes["nuevo"] == "team_assigned"
