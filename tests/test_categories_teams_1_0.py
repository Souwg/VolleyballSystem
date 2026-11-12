from datetime import date
from pathlib import Path

from src.api.models import Category, Season, Team, db


ROOT = Path(__file__).resolve().parents[1]


def _season(world, *, name, status, year):
    season = Season(
        club=world.club_a,
        name=name,
        start_date=date(year, 1, 1),
        end_date=date(year, 12, 31),
        status=status,
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return season


def test_category_is_global_and_keeps_description_in_planned_context(
    client, world, auth_headers
):
    planned = _season(
        world,
        name="Temporada 2027",
        status="planned",
        year=2027,
    )
    category = Category(
        name="Infantil",
        description="Formación inicial",
        club=world.club_a,
    )
    db.session.add(category)
    db.session.commit()

    response = client.get(
        f"/api/categories?season_id={planned.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert response.get_json()["season"]["name"] == "Temporada 2027"
    row = next(
        item
        for item in response.get_json()["categories"]
        if item["id"] == category.id
    )
    assert row["description"] == "Formación inicial"
    assert row["total_teams"] == 0
    assert row["can_delete"] is True


def test_owner_edits_global_category_while_other_seasons_exist(
    client, world, auth_headers
):
    _season(world, name="Temporada 2025", status="closed", year=2025)
    _season(world, name="Temporada 2027", status="planned", year=2027)

    response = client.put(
        f"/api/categories/{world.category_a.id}",
        json={"name": "Infantil", "description": "Base del club"},
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert response.get_json()["category"]["name"] == "Infantil"
    assert response.get_json()["category"]["description"] == "Base del club"


def test_empty_category_can_be_deleted_but_used_category_cannot(
    client, world, auth_headers
):
    empty = Category(name="Descartable", club=world.club_a)
    db.session.add(empty)
    db.session.commit()

    deleted = client.delete(
        f"/api/categories/{empty.id}",
        headers=auth_headers(world.owner_a),
    )
    blocked = client.delete(
        f"/api/categories/{world.category_a.id}",
        headers=auth_headers(world.owner_a),
    )

    assert deleted.status_code == 200
    assert db.session.get(Category, empty.id) is None
    assert blocked.status_code == 409
    assert blocked.get_json()["code"] == "CATEGORY_HAS_TEAMS"


def test_category_reports_historical_usage_for_rename_warning(
    client, world, auth_headers
):
    closed = _season(
        world,
        name="Temporada 2025",
        status="closed",
        year=2025,
    )
    db.session.add(
        Team(
            name="Histórico",
            gender="female",
            category=world.category_a,
            club=world.club_a,
            season=closed,
        )
    )
    db.session.commit()

    response = client.get(
        "/api/categories",
        headers=auth_headers(world.owner_a),
    )
    row = next(
        item
        for item in response.get_json()["categories"]
        if item["id"] == world.category_a.id
    )

    assert row["has_historical_teams"] is True
    assert row["total_teams_all_seasons"] == 2
    assert row["can_delete"] is False


def test_owner_creates_team_in_active_season(client, world, auth_headers):
    response = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "A", "gender": "female"},
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 201
    assert response.get_json()["team"]["season_id"] == world.season_a.id


def test_planned_team_can_be_created_edited_and_stays_isolated(
    client, world, auth_headers
):
    planned = _season(
        world,
        name="Temporada 2027",
        status="planned",
        year=2027,
    )
    created = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "A", "gender": "female", "season_id": planned.id},
        headers=auth_headers(world.owner_a),
    )
    team_id = created.get_json()["team"]["id"]
    updated = client.put(
        f"/api/teams/{team_id}",
        json={"name": "B", "gender": "mixed"},
        headers=auth_headers(world.owner_a),
    )
    planned_view = client.get(
        f"/api/categories/{world.category_a.id}?season_id={planned.id}",
        headers=auth_headers(world.owner_a),
    )
    active_view = client.get(
        f"/api/categories/{world.category_a.id}",
        headers=auth_headers(world.owner_a),
    )

    assert created.status_code == 201
    assert updated.status_code == 200
    assert updated.get_json()["team"]["name"] == "B"
    assert {team["id"] for team in planned_view.get_json()["teams"]} == {
        team_id
    }
    assert team_id not in {
        team["id"] for team in active_view.get_json()["teams"]
    }
    assert db.session.get(Season, planned.id).status == "planned"


def test_closed_team_cannot_be_edited(client, world, auth_headers):
    closed = _season(
        world,
        name="Temporada 2025",
        status="closed",
        year=2025,
    )
    team = Team(
        name="Histórico",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=closed,
    )
    db.session.add(team)
    db.session.commit()

    response = client.put(
        f"/api/teams/{team.id}",
        json={"name": "Mutado", "gender": "mixed"},
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"
    db.session.refresh(team)
    assert team.name == "Histórico"


def test_team_read_model_includes_context_archive_and_player_active_state(
    client, world, auth_headers
):
    world.team_a.status = "archived"
    world.players_a[0].is_active = False
    db.session.commit()

    detail = client.get(
        f"/api/teams/{world.team_a.id}",
        headers=auth_headers(world.owner_a),
    )
    roster = client.get(
        f"/api/teams/{world.team_a.id}/players",
        headers=auth_headers(world.owner_a),
    )

    team = detail.get_json()["team"]
    player = next(
        row
        for row in roster.get_json()["players"]
        if row["id"] == world.players_a[0].id
    )
    assert team["category"]["name"] == world.category_a.name
    assert team["season"]["name"] == world.season_a.name
    assert team["season_status"] == "active"
    assert team["status"] == "archived"
    assert player["is_active"] is False


def test_categories_teams_frontend_contract_for_flow_copy_and_accessibility():
    categories = (
        ROOT / "src/front/js/pages/categories/categories.js"
    ).read_text(encoding="utf-8")
    category_detail = (
        ROOT / "src/front/js/pages/categories/categoryDetail.js"
    ).read_text(encoding="utf-8")
    team_detail = (
        ROOT / "src/front/js/pages/teams/teamDetail.js"
    ).read_text(encoding="utf-8")
    styles = (ROOT / "src/front/styles/teams.css").read_text(encoding="utf-8")

    assert "Las categorías organizan permanentemente" in categories
    assert "Mostrando equipos y deportistas de:" in categories
    assert "Este nombre también se mostrará en temporadas anteriores." in categories
    assert "Eliminar categoría" in categories
    assert "category.description" in categories
    assert "<Link" in categories

    assert '{ season_id: contextSeason.id }' in category_detail
    assert 'label="Rama"' in category_detail
    assert "Planificada. Puedes crear y editar equipos" in category_detail
    assert "No hubo equipos de esta categoría en esta temporada." in category_detail
    assert "breadcrumbs" in category_detail

    assert "Deportistas del equipo" in team_detail
    assert "Número en el equipo" in team_detail
    assert "Agregar también a este equipo" in team_detail
    assert "Inactivo en el club" in team_detail
    assert "Equipo archivado. Conserva su histórico" in team_detail
    assert "lifecycleError" in team_detail
    assert "seasonQuery" in team_detail
    assert 'type="button"' in team_detail

    assert "grid-template-columns: repeat(2" in styles
    assert ":focus-visible" in styles
    assert "width: 44px" in styles
