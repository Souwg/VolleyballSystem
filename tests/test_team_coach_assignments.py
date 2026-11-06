import importlib
import uuid
from datetime import date, datetime

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from src.api.coach_access import (
    can_manage_team,
    get_assigned_team_ids,
    get_team_assignment_error,
)
from src.api.endpoints import team_coaches
from src.api.models import (
    Club,
    Country,
    AdministrativeArea,
    Season,
    Team,
    TeamCoachAssignment,
    TrainingSession,
    User,
    db,
)


MIGRATION_MODULE = (
    "migrations.versions.c3e7a1f4b852_add_team_coach_assignments"
)


def _coach(world, suffix="Extra", club=None, is_active=True):
    coach = User(
        id=str(uuid.uuid4()),
        full_name=f"Coach {suffix}",
        email=f"coach-{suffix.lower()}-{uuid.uuid4().hex[:6]}@example.com",
        password="unused",
        role="coach",
        first_login=False,
        is_active=is_active,
        session_version=0,
        club=club or world.club_a,
    )
    db.session.add(coach)
    db.session.commit()
    return coach


def _team(world, name="Sub-18", season=None):
    team = Team(
        name=name,
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=season or world.season_a,
    )
    db.session.add(team)
    db.session.commit()
    return team


def _planned_season(world):
    season = Season(
        club=world.club_a,
        name="Próxima temporada",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return season


def _assignment(world, coach=None, team=None, removed_at=None):
    assignment = TeamCoachAssignment(
        club_id=world.club_a.id,
        team_id=(team or world.team_a).id,
        user_id=(coach or world.coach_a).id,
        assigned_by=world.owner_a.id,
        removed_at=removed_at,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


def _scope_club(world):
    world.club_a.coach_access_mode = "team_assigned"
    db.session.commit()


def _post(client, auth_headers, user, team, coach_id):
    return client.post(
        f"/api/teams/{team.id}/coaches",
        headers=auth_headers(user),
        json={"user_id": coach_id},
    )


def _delete(client, auth_headers, user, team, coach_id):
    return client.delete(
        f"/api/teams/{team.id}/coaches/{coach_id}",
        headers=auth_headers(user),
    )


def _rows(team, coach):
    return TeamCoachAssignment.query.filter_by(
        team_id=team.id,
        user_id=coach.id,
    ).order_by(TeamCoachAssignment.assigned_at.asc()).all()


# =========================
# Club.coach_access_mode
# =========================


def test_legacy_club_keeps_club_wide_and_serializes_mode(world):
    assert world.club_a.coach_access_mode == "club_wide"
    assert world.club_a.serialize()["coach_access_mode"] == "club_wide"


def test_club_rejects_invalid_coach_access_mode(world):
    world.club_a.coach_access_mode = "other"

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_new_club_from_create_client_ignores_mode_in_payload(
    client, world, auth_headers, monkeypatch
):
    country = Country(
        id=str(uuid.uuid4()), code="VE", name="Venezuela", is_active=True
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
            "coach_access_mode": "club_wide",
        },
    )

    assert response.status_code == 201
    owner = User.query.filter_by(email="owner-nuevo@example.com").one()
    assert db.session.get(Club, owner.club_id).coach_access_mode == (
        "team_assigned"
    )


def test_general_club_update_cannot_change_coach_access_mode(
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


# =========================
# Modelo
# =========================


def test_team_can_have_several_coaches_and_coach_several_teams(world):
    second_coach = _coach(world, "Andrea")
    second_team = _team(world)
    _assignment(world)
    _assignment(world, coach=second_coach)
    _assignment(world, team=second_team)

    assert TeamCoachAssignment.query.filter_by(
        team_id=world.team_a.id, removed_at=None
    ).count() == 2
    assert TeamCoachAssignment.query.filter_by(
        user_id=world.coach_a.id, removed_at=None
    ).count() == 2


def test_database_rejects_duplicate_open_assignment(world):
    _assignment(world)

    with pytest.raises(IntegrityError):
        _assignment(world)


def test_database_allows_new_open_assignment_after_closed_one(world):
    closed = _assignment(world, removed_at=datetime(2026, 7, 1))
    current = _assignment(world)

    assert closed.id != current.id
    assert len(_rows(world.team_a, world.coach_a)) == 2


def test_assignment_serialization_is_minimal(world):
    data = _assignment(world).serialize()

    assert set(data) == {
        "id",
        "club_id",
        "team_id",
        "user_id",
        "assigned_at",
        "assigned_by",
        "removed_at",
    }


# =========================
# Migración
# =========================


def _legacy_schema(connection):
    metadata = sa.MetaData()
    sa.Table(
        "clubs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
    )
    sa.Table(
        "teams",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("club_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("club_id", sa.String(36), nullable=True),
    )
    metadata.create_all(connection)


def _insert_assignment(connection, assignment_id, team, user, club, removed=None):
    connection.execute(
        sa.text(
            "INSERT INTO team_coach_assignments "
            "(id, club_id, team_id, user_id, assigned_at, removed_at) "
            "VALUES (:id, :club, :team, :user, '2026-01-01', :removed)"
        ),
        {
            "id": assignment_id,
            "club": club,
            "team": team,
            "user": user,
            "removed": removed,
        },
    )


def test_migration_enforces_tenant_and_open_uniqueness_and_guards_downgrade(
    tmp_path,
):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'assignments.db'}")
    migration = importlib.import_module(MIGRATION_MODULE)
    original_op = migration.op

    with engine.connect() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=ON"))
        _legacy_schema(connection)
        connection.execute(sa.text(
            "INSERT INTO clubs (id) VALUES ('club-a'), ('club-b')"
        ))
        connection.execute(sa.text(
            "INSERT INTO teams (id, club_id) VALUES ('team-a', 'club-a')"
        ))
        connection.execute(sa.text(
            "INSERT INTO users (id, club_id) VALUES "
            "('coach-a', 'club-a'), ('coach-b', 'club-b'), ('admin', NULL)"
        ))
        migration.op = Operations(MigrationContext.configure(connection))

        try:
            migration.upgrade()

            assert {
                row[0]
                for row in connection.execute(sa.text(
                    "SELECT coach_access_mode FROM clubs"
                ))
            } == {"club_wide"}
            assert connection.execute(sa.text(
                "SELECT COUNT(*) FROM team_coach_assignments"
            )).scalar() == 0

            _insert_assignment(connection, "1", "team-a", "coach-a", "club-a")

            with pytest.raises(IntegrityError):
                _insert_assignment(
                    connection, "2", "team-a", "coach-b", "club-a"
                )

            with pytest.raises(IntegrityError):
                _insert_assignment(
                    connection, "3", "team-a", "coach-b", "club-b"
                )

            with pytest.raises(IntegrityError):
                _insert_assignment(
                    connection, "4", "team-a", "coach-a", "club-a"
                )

            with pytest.raises(RuntimeError):
                migration.downgrade()

            connection.execute(sa.text(
                "UPDATE team_coach_assignments "
                "SET removed_at = '2026-02-01' WHERE id = '1'"
            ))
            _insert_assignment(connection, "5", "team-a", "coach-a", "club-a")
            assert connection.execute(sa.text(
                "SELECT COUNT(*) FROM team_coach_assignments"
            )).scalar() == 2

            connection.execute(sa.text("DELETE FROM team_coach_assignments"))
            migration.downgrade()

            inspector = sa.inspect(connection)
            assert "team_coach_assignments" not in inspector.get_table_names()
            assert "coach_access_mode" not in {
                column["name"] for column in inspector.get_columns("clubs")
            }
            assert connection.execute(sa.text(
                "SELECT COUNT(*) FROM users"
            )).scalar() == 3
        finally:
            migration.op = original_op


# =========================
# Helper
# =========================


def test_club_wide_coach_manages_every_team_of_the_club(world):
    other_team = _team(world)

    assert can_manage_team(world.coach_a, world.team_a) is True
    assert can_manage_team(world.coach_a, other_team) is True
    assert get_team_assignment_error(world.coach_a, other_team) is None
    assert get_assigned_team_ids(world.coach_a) is None


def test_partial_assignments_do_not_restrict_club_wide_coach(world):
    other_team = _team(world)
    _assignment(world)

    assert can_manage_team(world.coach_a, other_team) is True
    assert get_assigned_team_ids(world.coach_a) is None


def test_team_assigned_coach_only_manages_open_assignments(world):
    assigned = world.team_a
    unassigned = _team(world)
    removed = _team(world, name="Retirado")
    _assignment(world, team=assigned)
    _assignment(world, team=removed, removed_at=datetime(2026, 7, 1))
    _scope_club(world)

    assert can_manage_team(world.coach_a, assigned) is True
    assert can_manage_team(world.coach_a, unassigned) is False
    assert can_manage_team(world.coach_a, removed) is False
    assert get_team_assignment_error(world.coach_a, assigned) is None
    assert get_team_assignment_error(world.coach_a, unassigned) == (
        "No tienes asignado este equipo",
        "TEAM_NOT_ASSIGNED",
        403,
    )
    assert get_assigned_team_ids(world.coach_a) == {assigned.id}


def test_team_assigned_coach_without_assignments_gets_empty_set(world):
    _scope_club(world)

    assert get_assigned_team_ids(world.coach_a) == set()
    assert can_manage_team(world.coach_a, world.team_a) is False


def test_owner_is_never_limited_by_assignments(world):
    _scope_club(world)

    assert can_manage_team(world.owner_a, world.team_a) is True
    assert get_team_assignment_error(world.owner_a, world.team_a) is None
    assert get_assigned_team_ids(world.owner_a) is None


@pytest.mark.parametrize("scoped", [False, True])
def test_stale_assignment_grants_nothing_after_role_change(world, scoped):
    coach = _coach(world, "Cambio")
    _assignment(world, coach=coach)
    coach.role = "staff"
    db.session.commit()

    if scoped:
        _scope_club(world)

    assert can_manage_team(coach, world.team_a) is False
    assert get_team_assignment_error(coach, world.team_a)[1] == "FORBIDDEN"
    assert get_assigned_team_ids(coach) == set()
    assert _rows(world.team_a, coach)[0].removed_at is None


def test_staff_and_system_admin_get_no_sports_permission(world):
    for user in [world.staff_a, world.system_admin]:
        assert can_manage_team(user, world.team_a) is False
        assert get_team_assignment_error(user, world.team_a)[1] == "FORBIDDEN"
        assert get_assigned_team_ids(user) == set()


@pytest.mark.parametrize("mode", ["club_wide", "team_assigned"])
def test_helper_never_grants_access_across_tenants(world, mode):
    world.club_b.coach_access_mode = mode
    db.session.commit()

    assert can_manage_team(world.coach_b, world.team_a) is False
    assert can_manage_team(world.owner_b, world.team_a) is False
    assert get_team_assignment_error(world.coach_b, world.team_a)[1] == (
        "FORBIDDEN"
    )


def test_assignment_row_of_other_club_does_not_grant_access(world):
    world.club_b.coach_access_mode = "team_assigned"
    db.session.add(TeamCoachAssignment(
        club_id=world.club_a.id,
        team_id=world.team_a.id,
        user_id=world.coach_b.id,
    ))
    db.session.commit()

    assert can_manage_team(world.coach_b, world.team_a) is False
    assert get_assigned_team_ids(world.coach_b) == set()


# =========================
# API: permisos
# =========================


@pytest.mark.parametrize("user_key", ["coach_a", "staff_a", "system_admin"])
def test_only_owner_can_use_assignment_api(
    client, world, auth_headers, user_key
):
    user = getattr(world, user_key)
    headers = auth_headers(user)
    url = f"/api/teams/{world.team_a.id}/coaches"

    responses = [
        client.get(url, headers=headers),
        client.post(url, headers=headers, json={"user_id": world.coach_a.id}),
        client.delete(f"{url}/{world.coach_a.id}", headers=headers),
    ]

    for response in responses:
        assert response.status_code == 403
        assert response.get_json()["code"] == "FORBIDDEN"

    assert TeamCoachAssignment.query.count() == 0


def test_assignment_api_requires_token(client, world):
    url = f"/api/teams/{world.team_a.id}/coaches"

    assert client.get(url).status_code == 401
    assert client.post(url, json={"user_id": world.coach_a.id}).status_code == 401
    assert client.delete(f"{url}/{world.coach_a.id}").status_code == 401


def test_other_club_team_looks_identical_to_missing_team(
    client, world, auth_headers
):
    headers = auth_headers(world.owner_b)
    existing = f"/api/teams/{world.team_a.id}/coaches"
    missing = f"/api/teams/{uuid.uuid4()}/coaches"

    for url in [existing, missing]:
        for response in [
            client.get(url, headers=headers),
            client.post(url, headers=headers, json={"user_id": world.coach_b.id}),
            client.delete(f"{url}/{world.coach_b.id}", headers=headers),
        ]:
            assert response.status_code == 404
            assert response.get_json()["code"] == "TEAM_NOT_FOUND"
            assert response.get_json()["message"] == "Equipo no encontrado"


# =========================
# API: asignar
# =========================


def test_post_creates_assignment_and_keeps_club_mode(
    client, world, auth_headers
):
    response = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert response.status_code == 201
    data = response.get_json()["assignment"]
    assert data["team_id"] == world.team_a.id
    assert data["user_id"] == world.coach_a.id
    assert data["club_id"] == world.club_a.id
    assert data["assigned_by"] == world.owner_a.id
    assert data["removed_at"] is None
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).coach_access_mode == "club_wide"


def test_post_is_idempotent_for_open_assignment(client, world, auth_headers):
    first = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )
    second = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert (
        second.get_json()["assignment"]["id"]
        == first.get_json()["assignment"]["id"]
    )
    assert len(_rows(world.team_a, world.coach_a)) == 1


def test_post_race_lost_on_unique_index_returns_existing_assignment(
    client, world, auth_headers, monkeypatch
):
    existing = _assignment(world)
    existing_id = existing.id
    real_open_assignment = team_coaches._open_assignment
    calls = {"count": 0}

    class EmptyQuery:
        def first(self):
            return None

    def losing_race(team_id, user_id):
        calls["count"] += 1

        if calls["count"] == 1:
            return EmptyQuery()

        return real_open_assignment(team_id, user_id)

    monkeypatch.setattr(team_coaches, "_open_assignment", losing_race)

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert response.status_code == 200
    assert response.get_json()["assignment"]["id"] == existing_id
    assert len(_rows(world.team_a, world.coach_a)) == 1


@pytest.mark.parametrize(
    ("statement", "expected_code"),
    [
        ("UPDATE teams SET status = 'archived'", "TEAM_ARCHIVED"),
        ("UPDATE seasons SET status = 'closed'", "SEASON_CLOSED"),
    ],
)
def test_post_revalidates_lifecycle_committed_before_taking_the_lock(
    client, world, auth_headers, monkeypatch, statement, expected_code
):
    real_lock = team_coaches._lock_team_lifecycle

    def lifecycle_changes_first(team_id, club_id):
        db.session.execute(sa.text(statement))
        return real_lock(team_id, club_id)

    monkeypatch.setattr(
        team_coaches,
        "_lock_team_lifecycle",
        lifecycle_changes_first,
    )

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == expected_code
    assert TeamCoachAssignment.query.count() == 0


@pytest.mark.parametrize(
    ("statement", "expected_code"),
    [
        ("UPDATE users SET role = 'staff' WHERE id = :id", "USER_NOT_COACH"),
        ("UPDATE users SET is_active = false WHERE id = :id", "COACH_INACTIVE"),
    ],
)
def test_post_revalidates_coach_changed_before_taking_the_lock(
    client, world, auth_headers, monkeypatch, statement, expected_code
):
    coach_id = world.coach_a.id
    real_lock = team_coaches._lock_coach

    def user_changes_first(user_id, club_id):
        db.session.execute(sa.text(statement), {"id": coach_id})
        return real_lock(user_id, club_id)

    monkeypatch.setattr(team_coaches, "_lock_coach", user_changes_first)

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, coach_id
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == expected_code
    assert TeamCoachAssignment.query.count() == 0


def test_post_locks_team_season_and_coach_before_creating_assignment(
    client, world, auth_headers, monkeypatch
):
    locks = []
    real_with_for_update = Query.with_for_update

    def spy(query, *args, **kwargs):
        locks.append((
            query.column_descriptions[0]["entity"],
            kwargs.get("read", False),
        ))
        return real_with_for_update(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", spy)

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert response.status_code == 201
    assert locks == [(Team, False), (Season, True), (User, True)]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "COACH_ID_REQUIRED"),
        ({"user_id": ""}, "COACH_ID_REQUIRED"),
        # La validación central de entrada responde antes que la ruta.
        ({"user_id": 5}, "INVALID_FIELD_TYPE"),
        ([], "INVALID_JSON_BODY"),
    ],
)
def test_post_requires_valid_user_id(client, world, auth_headers, body, code):
    response = client.post(
        f"/api/teams/{world.team_a.id}/coaches",
        headers=auth_headers(world.owner_a),
        json=body,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == code
    assert TeamCoachAssignment.query.count() == 0


def test_post_hides_users_of_other_clubs_and_system_admin(
    client, world, auth_headers
):
    for coach_id in [
        world.coach_b.id,
        world.owner_b.id,
        world.system_admin.id,
        str(uuid.uuid4()),
    ]:
        response = _post(
            client, auth_headers, world.owner_a, world.team_a, coach_id
        )

        assert response.status_code == 404
        assert response.get_json()["code"] == "COACH_NOT_FOUND"

    assert TeamCoachAssignment.query.count() == 0


@pytest.mark.parametrize("user_key", ["staff_a", "owner_a"])
def test_post_rejects_non_coach_of_same_club(
    client, world, auth_headers, user_key
):
    response = _post(
        client,
        auth_headers,
        world.owner_a,
        world.team_a,
        getattr(world, user_key).id,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "USER_NOT_COACH"
    assert TeamCoachAssignment.query.count() == 0


def test_post_rejects_inactive_coach(client, world, auth_headers):
    coach = _coach(world, "Inactivo", is_active=False)

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, coach.id
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "COACH_INACTIVE"
    assert TeamCoachAssignment.query.count() == 0


def test_post_rejects_archived_team(client, world, auth_headers):
    world.team_a.status = "archived"
    db.session.commit()

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    assert TeamCoachAssignment.query.count() == 0


def test_post_rejects_closed_season(client, world, auth_headers):
    world.season_a.status = "closed"
    db.session.commit()

    response = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"
    assert TeamCoachAssignment.query.count() == 0


def test_post_allows_planned_season_without_enabling_operation(
    client, world, auth_headers
):
    planned_team = _team(world, season=_planned_season(world))

    response = _post(
        client, auth_headers, world.owner_a, planned_team, world.coach_a.id
    )
    training_response = client.post(
        "/api/trainings",
        headers=auth_headers(world.coach_a),
        json={
            "team_id": planned_team.id,
            "date": "2027-02-10",
            "start_time": "17:00",
            "end_time": "19:00",
            "location": "Cancha principal",
        },
    )

    assert response.status_code == 201
    assert training_response.status_code == 409
    assert training_response.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"


# =========================
# API: listar
# =========================


def test_get_lists_only_open_assignments_without_sensitive_fields(
    client, world, auth_headers
):
    second_coach = _coach(world, "Andrea")
    open_assignment = _assignment(world)
    _assignment(world, coach=second_coach, removed_at=datetime(2026, 7, 1))

    response = client.get(
        f"/api/teams/{world.team_a.id}/coaches",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["team"]["id"] == world.team_a.id
    assert [row["assignment_id"] for row in data["coaches"]] == [
        open_assignment.id
    ]
    row = data["coaches"][0]
    assert row["user_id"] == world.coach_a.id
    assert row["full_name"] == world.coach_a.full_name
    assert row["email"] == world.coach_a.email
    assert row["is_active"] is True
    assert row["removed_at"] is None
    assert "password" not in row
    assert "session_version" not in row


# =========================
# API: quitar y reasignar
# =========================


def test_delete_closes_row_and_is_idempotent(client, world, auth_headers):
    assignment = _assignment(world)

    first = _delete(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )
    db.session.expire_all()
    removed_at = db.session.get(TeamCoachAssignment, assignment.id).removed_at
    second = _delete(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert first.status_code == 200
    assert first.get_json()["removed"] is True
    assert removed_at is not None
    assert second.status_code == 200
    assert second.get_json()["removed"] is False
    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at == (
        removed_at
    )
    assert TeamCoachAssignment.query.count() == 1


def test_delete_only_closes_the_requested_relation(client, world, auth_headers):
    second_coach = _coach(world, "Andrea")
    second_team = _team(world)
    target = _assignment(world)
    other_coach = _assignment(world, coach=second_coach)
    other_team = _assignment(world, team=second_team)

    _delete(client, auth_headers, world.owner_a, world.team_a, world.coach_a.id)

    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, target.id).removed_at is not None
    assert db.session.get(TeamCoachAssignment, other_coach.id).removed_at is None
    assert db.session.get(TeamCoachAssignment, other_team.id).removed_at is None


@pytest.mark.parametrize(
    "scenario",
    ["team_archived", "season_closed", "coach_inactive", "role_changed"],
)
def test_delete_is_allowed_in_any_administrative_state(
    client, world, auth_headers, scenario
):
    coach = _coach(world, "Admin")
    assignment = _assignment(world, coach=coach)

    if scenario == "team_archived":
        world.team_a.status = "archived"
    elif scenario == "season_closed":
        world.season_a.status = "closed"
    elif scenario == "coach_inactive":
        coach.is_active = False
    else:
        coach.role = "staff"

    db.session.commit()

    response = _delete(
        client, auth_headers, world.owner_a, world.team_a, coach.id
    )

    assert response.status_code == 200
    assert response.get_json()["removed"] is True
    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at


def test_reassign_creates_new_row_and_keeps_history(
    client, world, auth_headers
):
    first = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    ).get_json()["assignment"]
    _delete(client, auth_headers, world.owner_a, world.team_a, world.coach_a.id)
    second = _post(
        client, auth_headers, world.owner_a, world.team_a, world.coach_a.id
    )

    assert second.status_code == 201
    assert second.get_json()["assignment"]["id"] != first["id"]
    db.session.expire_all()
    rows = {
        row.id: row
        for row in _rows(world.team_a, world.coach_a)
    }
    assert len(rows) == 2
    assert rows[first["id"]].removed_at is not None
    assert rows[second.get_json()["assignment"]["id"]].removed_at is None


# =========================
# Lifecycle de la relación
# =========================


def test_deactivating_coach_keeps_assignment(client, world, auth_headers):
    coach = _coach(world, "Pausa")
    assignment = _assignment(world, coach=coach)

    deactivate = client.put(
        f"/api/club/users/{coach.id}/deactivate",
        headers=auth_headers(world.owner_a),
    )
    activate = client.put(
        f"/api/club/users/{coach.id}/activate",
        headers=auth_headers(world.owner_a),
    )

    assert deactivate.status_code == 200
    assert activate.status_code == 200
    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None


def test_role_change_keeps_assignment(client, world, auth_headers):
    coach = _coach(world, "Rol")
    assignment = _assignment(world, coach=coach)

    response = client.put(
        f"/api/club/users/{coach.id}",
        headers=auth_headers(world.owner_a),
        json={"role": "staff"},
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None
    changed_user = db.session.get(User, coach.id)
    assert changed_user.role == "staff"
    assert can_manage_team(changed_user, world.team_a) is False
    assert get_assigned_team_ids(changed_user) == set()


def test_archiving_and_reactivating_team_keeps_assignment(
    client, world, auth_headers
):
    assignment = _assignment(world)
    headers = auth_headers(world.owner_a)

    assert client.put(
        f"/api/teams/{world.team_a.id}/archive", headers=headers
    ).status_code == 200
    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None

    assert client.put(
        f"/api/teams/{world.team_a.id}/reactivate", headers=headers
    ).status_code == 200
    db.session.expire_all()
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None


def test_season_transition_keeps_assignments_and_does_not_copy_them(
    client, world, auth_headers
):
    assignment = _assignment(world)
    headers = auth_headers(world.owner_a)
    planned = _planned_season(world)

    duplicate = client.post(
        f"/api/seasons/{planned.id}/teams/duplicate",
        headers=headers,
        json={
            "source_season_id": world.season_a.id,
            "team_ids": [world.team_a.id],
        },
    )
    transition = client.post(
        f"/api/seasons/{planned.id}/transition",
        headers=headers,
        json={"source_season_id": world.season_a.id},
    )

    assert duplicate.status_code == 201
    assert transition.status_code == 200
    copied_id = duplicate.get_json()["teams"][0]["id"]
    db.session.expire_all()
    assert TeamCoachAssignment.query.filter_by(team_id=copied_id).count() == 0
    assert TeamCoachAssignment.query.count() == 1
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None
    assert db.session.get(Season, world.season_a.id).status == "closed"


def test_team_with_assignment_history_cannot_be_physically_deleted(
    client, world, auth_headers
):
    empty = _team(world, name="Vacío")
    assignment = _assignment(
        world, team=empty, removed_at=datetime(2026, 7, 1)
    )

    response = client.delete(
        f"/api/teams/{empty.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_HAS_HISTORY"
    assert db.session.get(Team, empty.id) is not None
    assert db.session.get(TeamCoachAssignment, assignment.id) is not None


# =========================
# Sin enforcement deportivo
# =========================


def test_club_wide_coach_keeps_operating_unassigned_team(
    client, world, auth_headers
):
    other_coach = _coach(world, "Otro")
    _assignment(world, coach=other_coach)

    response = client.post(
        "/api/trainings",
        headers=auth_headers(world.coach_a),
        json={
            "team_id": world.team_a.id,
            "date": "2026-08-10",
            "start_time": "17:00",
            "end_time": "19:00",
            "location": "Cancha principal",
        },
    )

    assert response.status_code == 201
    assert TrainingSession.query.filter_by(team_id=world.team_a.id).count() == 1


def test_team_assigned_mode_is_enforced_on_sports_endpoints(
    client, world, auth_headers
):
    _scope_club(world)
    assert can_manage_team(world.coach_a, world.team_a) is False

    response = client.post(
        "/api/trainings",
        headers=auth_headers(world.coach_a),
        json={
            "team_id": world.team_a.id,
            "date": "2026-08-10",
            "start_time": "17:00",
            "end_time": "19:00",
            "location": "Cancha principal",
        },
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
