from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from src.api.models import Category, Season, Team, db


def _constraint_error(name):
    original = Exception(f'duplicate key violates constraint "{name}"')
    original.diag = SimpleNamespace(constraint_name=name)
    return IntegrityError("insert or update", {}, original)


def _postgres_index_sql(model, name):
    index = next(item for item in model.__table__.indexes if item.name == name)
    return " ".join(
        str(CreateIndex(index).compile(dialect=postgresql.dialect())).split()
    ).lower()


def test_postgresql_schema_has_case_insensitive_scoped_indexes():
    category_sql = _postgres_index_sql(
        Category,
        "uq_categories_club_lower_name",
    )
    team_sql = _postgres_index_sql(
        Team,
        "uq_teams_scope_lower_name",
    )

    assert category_sql == (
        "create unique index uq_categories_club_lower_name "
        "on categories (club_id, lower(name))"
    )
    assert team_sql == (
        "create unique index uq_teams_scope_lower_name on teams "
        "(club_id, season_id, category_id, gender, lower(name))"
    )


def test_database_rejects_case_only_category_duplicate(world):
    db.session.add(Category(name="Infantil", club=world.club_a))
    db.session.commit()

    db.session.add(Category(name="INFANTIL", club=world.club_a))

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()
    assert Category.query.filter_by(club_id=world.club_a.id).filter(
        db.func.lower(Category.name) == "infantil"
    ).count() == 1


def test_database_rejects_case_only_team_duplicate_in_same_scope(world):
    db.session.add(
        Team(
            name="Primera",
            gender="female",
            category=world.category_a,
            club=world.club_a,
            season=world.season_a,
        )
    )
    db.session.commit()
    db.session.add(
        Team(
            name="PRIMERA",
            gender="female",
            category=world.category_a,
            club=world.club_a,
            season=world.season_a,
        )
    )

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()
    assert Team.query.filter_by(
        club_id=world.club_a.id,
        season_id=world.season_a.id,
        category_id=world.category_a.id,
        gender="female",
    ).filter(db.func.lower(Team.name) == "primera").count() == 1


def test_category_create_update_and_tenant_scope(
    client,
    world,
    auth_headers,
):
    owner_a = auth_headers(world.owner_a)
    owner_b = auth_headers(world.owner_b)

    created = client.post(
        "/api/categories",
        json={"name": "  Infantil  "},
        headers=owner_a,
    )
    duplicate = client.post(
        "/api/categories",
        json={"name": "INFANTIL"},
        headers=owner_a,
    )
    other_club = client.post(
        "/api/categories",
        json={"name": "infantil"},
        headers=owner_b,
    )
    juvenile = client.post(
        "/api/categories",
        json={"name": "Juvenil"},
        headers=owner_a,
    )
    rename = client.put(
        f"/api/categories/{juvenile.get_json()['category']['id']}",
        json={"name": "infantil"},
        headers=owner_a,
    )

    assert created.status_code == 201
    assert created.get_json()["category"]["name"] == "Infantil"
    assert duplicate.status_code == 409
    assert duplicate.get_json()["code"] == "CATEGORY_ALREADY_EXISTS"
    assert other_club.status_code == 201
    assert juvenile.status_code == 201
    assert rename.status_code == 409
    assert rename.get_json()["code"] == "CATEGORY_ALREADY_EXISTS"


def test_team_create_update_and_valid_scopes(client, world, auth_headers):
    owner_a = auth_headers(world.owner_a)
    owner_b = auth_headers(world.owner_b)
    category = Category(name="Juvenil", club=world.club_a)
    planned = Season(
        club=world.club_a,
        name="Temporada 2027",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
        status="planned",
        created_by=world.owner_a.id,
    )
    db.session.add_all([category, planned])
    db.session.commit()

    first = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "A", "gender": "female"},
        headers=owner_a,
    )
    duplicate = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "a", "gender": "female"},
        headers=owner_a,
    )
    second = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "B", "gender": "female"},
        headers=owner_a,
    )
    rename = client.put(
        f"/api/teams/{second.get_json()['team']['id']}",
        json={"name": "a", "gender": "female"},
        headers=owner_a,
    )
    other_gender = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "a", "gender": "male"},
        headers=owner_a,
    )
    other_category = client.post(
        f"/api/categories/{category.id}/teams",
        json={"name": "a", "gender": "female"},
        headers=owner_a,
    )
    other_season = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={
            "name": "a",
            "gender": "female",
            "season_id": planned.id,
        },
        headers=owner_a,
    )
    other_club = client.post(
        f"/api/categories/{world.category_b.id}/teams",
        json={"name": "a", "gender": "female"},
        headers=owner_b,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.get_json()["code"] == "TEAM_ALREADY_EXISTS"
    assert second.status_code == 201
    assert rename.status_code == 409
    assert rename.get_json()["code"] == "TEAM_ALREADY_EXISTS"
    assert other_gender.status_code == 201
    assert other_category.status_code == 201
    assert other_season.status_code == 201
    assert other_club.status_code == 201


@pytest.mark.parametrize(
    ("method", "path", "payload", "constraint", "error_code"),
    [
        (
            "post",
            "/api/categories",
            {"name": "Infantil"},
            "uq_categories_club_lower_name",
            "CATEGORY_ALREADY_EXISTS",
        ),
        (
            "put",
            "/api/categories/{category_id}",
            {"name": "Infantil"},
            "uq_categories_club_lower_name",
            "CATEGORY_ALREADY_EXISTS",
        ),
        (
            "post",
            "/api/categories/{category_id}/teams",
            {"name": "A", "gender": "female"},
            "uq_teams_scope_lower_name",
            "TEAM_ALREADY_EXISTS",
        ),
        (
            "put",
            "/api/teams/{team_id}",
            {"name": "Renombrado", "gender": "female"},
            "uq_teams_scope_lower_name",
            "TEAM_ALREADY_EXISTS",
        ),
    ],
)
def test_concurrent_uniqueness_violation_is_translated_to_409(
    client,
    world,
    auth_headers,
    monkeypatch,
    method,
    path,
    payload,
    constraint,
    error_code,
):
    path = path.format(
        category_id=world.category_a.id,
        team_id=world.team_a.id,
    )

    def fail_commit():
        raise _constraint_error(constraint)

    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = getattr(client, method)(
        path,
        json=payload,
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == error_code
