from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest

from src.api.models import (
    MatchSession,
    Player,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TrainingSession,
    db,
)
from src.api.time_utils import get_club_today


def _build_two_season_scenario(world):
    world.season_a.name = "Temporada 2027"
    world.season_a.start_date = date(2027, 1, 1)

    closed_season = Season(
        club=world.club_a,
        name="Temporada 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="closed",
        created_by=world.owner_a.id,
    )
    planned_season = Season(
        club=world.club_a,
        name="Temporada 2028",
        start_date=date(2028, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    closed_team = Team(
        name="Team 2026",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=closed_season,
    )
    planned_team = Team(
        name="Team 2028",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned_season,
    )

    today = get_club_today(world.club_a)
    active_training = TrainingSession(
        team=world.team_a,
        date=today + timedelta(days=2),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha actual",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    closed_training = TrainingSession(
        team=closed_team,
        date=today + timedelta(days=1),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha histórica",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    active_match = MatchSession(
        team=world.team_a,
        date=today + timedelta(days=2),
        opponent_name="Rival actual",
        match_type="official",
        created_by=world.owner_a.id,
    )
    closed_match = MatchSession(
        team=closed_team,
        date=today + timedelta(days=1),
        opponent_name="Rival histórico",
        match_type="official",
        created_by=world.owner_a.id,
    )
    active_tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name="Torneo 2027",
        start_date=today + timedelta(days=5),
        status="active",
        created_by=world.owner_a.id,
    )
    closed_tournament = Tournament(
        club=world.club_a,
        season=closed_season,
        name="Torneo 2026",
        start_date=today - timedelta(days=30),
        status="completed",
        created_by=world.owner_a.id,
    )
    planned_tournament = Tournament(
        club=world.club_a,
        season=planned_season,
        name="Torneo 2028",
        start_date=today + timedelta(days=60),
        status="active",
        created_by=world.owner_a.id,
    )
    historical_player = Player(
        first_name="Player",
        last_name="Histórica",
        sex="female",
        main_position="setter",
        is_active=True,
        club=world.club_a,
    )
    historical_membership = TeamPlayer(
        team=closed_team,
        player=historical_player,
        player_number=40,
        status="active",
    )

    db.session.add_all([
        closed_season,
        planned_season,
        closed_team,
        planned_team,
        active_training,
        closed_training,
        active_match,
        closed_match,
        active_tournament,
        closed_tournament,
        planned_tournament,
        historical_player,
        historical_membership,
    ])
    db.session.commit()

    return SimpleNamespace(
        closed_season=closed_season,
        planned_season=planned_season,
        closed_team=closed_team,
        planned_team=planned_team,
        active_training=active_training,
        closed_training=closed_training,
        active_match=active_match,
        closed_match=closed_match,
        active_tournament=active_tournament,
        closed_tournament=closed_tournament,
        planned_tournament=planned_tournament,
        historical_player=historical_player,
    )


def _ids(rows):
    return {row["id"] for row in rows}


def test_team_list_uses_only_active_season(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    response = client.get(
        "/api/teams",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    team_ids = _ids(response.get_json()["teams"])
    assert world.team_a.id in team_ids
    assert scenario.closed_team.id not in team_ids
    assert scenario.planned_team.id not in team_ids


def test_historical_team_remains_accessible_by_id(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    response = client.get(
        f"/api/teams/{scenario.closed_team.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert response.get_json()["team"]["id"] == scenario.closed_team.id


def test_tournament_list_uses_only_active_season_and_preserves_detail(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    list_response = client.get(
        "/api/tournaments",
        headers=auth_headers(world.owner_a),
    )
    detail_response = client.get(
        f"/api/tournaments/{scenario.closed_tournament.id}",
        headers=auth_headers(world.owner_a),
    )

    assert list_response.status_code == 200
    tournament_ids = _ids(list_response.get_json()["tournaments"])
    assert scenario.active_tournament.id in tournament_ids
    assert scenario.closed_tournament.id not in tournament_ids
    assert scenario.planned_tournament.id not in tournament_ids
    assert detail_response.status_code == 200
    assert (
        detail_response.get_json()["tournament"]["id"]
        == scenario.closed_tournament.id
    )


def test_training_list_uses_active_season_and_preserves_historical_detail(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    list_response = client.get(
        "/api/trainings",
        headers=auth_headers(world.owner_a),
    )
    detail_response = client.get(
        f"/api/trainings/{scenario.closed_training.id}",
        headers=auth_headers(world.owner_a),
    )

    assert list_response.status_code == 200
    training_ids = _ids(list_response.get_json()["trainings"])
    assert scenario.active_training.id in training_ids
    assert scenario.closed_training.id not in training_ids
    assert detail_response.status_code == 200
    assert (
        detail_response.get_json()["training"]["id"]
        == scenario.closed_training.id
    )


def test_match_list_uses_active_season_and_preserves_historical_detail(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    list_response = client.get(
        "/api/matches",
        headers=auth_headers(world.owner_a),
    )
    detail_response = client.get(
        f"/api/matches/{scenario.closed_match.id}",
        headers=auth_headers(world.owner_a),
    )

    assert list_response.status_code == 200
    match_ids = _ids(list_response.get_json()["matches"])
    assert scenario.active_match.id in match_ids
    assert scenario.closed_match.id not in match_ids
    assert detail_response.status_code == 200
    assert detail_response.get_json()["match"]["id"] == scenario.closed_match.id


def test_categories_are_global_but_nested_teams_use_active_season(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    list_response = client.get(
        "/api/categories",
        headers=auth_headers(world.owner_a),
    )
    detail_response = client.get(
        f"/api/categories/{world.category_a.id}",
        headers=auth_headers(world.owner_a),
    )
    teams_response = client.get(
        f"/api/categories/{world.category_a.id}/teams",
        headers=auth_headers(world.owner_a),
    )

    assert list_response.status_code == 200
    category = next(
        row
        for row in list_response.get_json()["categories"]
        if row["id"] == world.category_a.id
    )
    assert category["total_teams"] == 1
    assert detail_response.status_code == 200
    team_ids = _ids(detail_response.get_json()["teams"])
    assert world.team_a.id in team_ids
    assert scenario.closed_team.id not in team_ids
    assert scenario.planned_team.id not in team_ids
    assert teams_response.status_code == 200
    assert _ids(teams_response.get_json()["teams"]) == {world.team_a.id}


def test_player_remains_global_without_treating_historical_team_as_current(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    response = client.get(
        "/api/players",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    player = next(
        row
        for row in response.get_json()["players"]
        if row["id"] == scenario.historical_player.id
    )
    assert player["team_id"] is None
    assert player["teams"] == []


def test_global_categories_and_players_do_not_require_active_season(
    client,
    world,
    auth_headers,
):
    world.season_a.status = "closed"
    db.session.commit()

    categories_response = client.get(
        "/api/categories",
        headers=auth_headers(world.owner_a),
    )
    players_response = client.get(
        "/api/players",
        headers=auth_headers(world.owner_a),
    )

    assert categories_response.status_code == 200
    assert categories_response.get_json()["categories"]
    assert players_response.status_code == 200
    assert players_response.get_json()["players"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/teams",
        "/api/tournaments",
        "/api/trainings",
        "/api/matches",
    ],
)
def test_operational_lists_require_an_active_season(
    client,
    world,
    auth_headers,
    endpoint,
):
    world.season_a.status = "closed"
    db.session.commit()

    response = client.get(
        endpoint,
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"


def test_planned_and_closed_seasons_are_not_fallbacks(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)
    world.season_a.status = "closed"
    db.session.commit()

    response = client.get(
        "/api/teams",
        headers=auth_headers(world.owner_a),
    )

    assert scenario.closed_season.status == "closed"
    assert scenario.planned_season.status == "planned"
    assert response.status_code == 409
    assert response.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"


def test_clubs_resolve_active_seasons_independently(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    response_a = client.get(
        "/api/teams",
        headers=auth_headers(world.owner_a),
    )
    response_b = client.get(
        "/api/teams",
        headers=auth_headers(world.owner_b),
    )

    assert _ids(response_a.get_json()["teams"]) == {world.team_a.id}
    assert _ids(response_b.get_json()["teams"]) == {world.team_b.id}
    assert scenario.closed_team.id not in _ids(response_a.get_json()["teams"])


def test_historical_resource_remains_cross_tenant_protected(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    response = client.get(
        f"/api/teams/{scenario.closed_team.id}",
        headers=auth_headers(world.owner_b),
    )

    assert response.status_code == 403


def test_dashboard_uses_active_season_for_current_sports_sections(
    client,
    world,
    auth_headers,
):
    scenario = _build_two_season_scenario(world)

    response = client.get(
        "/api/club/dashboard",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    payload = response.get_json()
    operations = payload["sections"]["operations"]
    assert payload["stats"]["total_teams"] == 1
    assert payload["stats"]["total_trainings"] == 2
    assert _ids(operations["upcoming_trainings"]) == {
        scenario.active_training.id
    }
    assert _ids(operations["upcoming_matches"]) == {
        scenario.active_match.id
    }
    assert {
        row["tournament_id"]
        for row in payload["sections"]["active_tournaments"]
    } == {scenario.active_tournament.id}
    assert payload["next_match"]["id"] == scenario.active_match.id


def test_owner_dashboard_requires_active_season_but_staff_finance_does_not(
    client,
    world,
    auth_headers,
):
    world.season_a.status = "closed"
    db.session.commit()

    owner_response = client.get(
        "/api/club/dashboard",
        headers=auth_headers(world.owner_a),
    )
    staff_response = client.get(
        "/api/club/dashboard",
        headers=auth_headers(world.staff_a),
    )

    assert owner_response.status_code == 409
    assert owner_response.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"
    assert staff_response.status_code == 200
