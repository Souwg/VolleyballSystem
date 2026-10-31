from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest

from src.api.models import (
    MatchPlayer,
    MatchSession,
    PlayerMatchStat,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TournamentTeam,
    TrainingSession,
    db,
)
from src.api.season_service import get_active_season_for_club
from src.api.time_utils import get_club_today


def _build_history(world):
    world.season_a.name = "Temporada 2027"

    closed = Season(
        club=world.club_a,
        name="Temporada 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="closed",
        created_by=world.owner_a.id,
    )
    planned = Season(
        club=world.club_a,
        name="Temporada 2028",
        start_date=date(2028, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    archived_team = Team(
        name="Sub-16 2026",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=closed,
        status="archived",
    )
    planned_team = Team(
        name="Sub-18 2028",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned,
    )
    historical_membership = TeamPlayer(
        team=archived_team,
        player=world.players_a[0],
        player_number=20,
        status="active",
    )
    planned_membership = TeamPlayer(
        team=planned_team,
        player=world.players_a[1],
        player_number=21,
        status="active",
    )

    today = get_club_today(world.club_a)
    closed_training = TrainingSession(
        team=archived_team,
        date=today - timedelta(days=30),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha histórica",
        status="completed",
        created_by=world.owner_a.id,
    )
    active_training = TrainingSession(
        team=world.team_a,
        date=today,
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha actual",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    closed_tournament = Tournament(
        club=world.club_a,
        season=closed,
        name="Copa 2026",
        start_date=today - timedelta(days=40),
        status="completed",
        created_by=world.owner_a.id,
    )
    active_tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name="Copa 2027",
        start_date=today + timedelta(days=10),
        status="active",
        created_by=world.owner_a.id,
    )
    tournament_entry = TournamentTeam(
        tournament=closed_tournament,
        team=archived_team,
        status="completed",
    )
    friendly = MatchSession(
        team=archived_team,
        date=today - timedelta(days=25),
        opponent_name="Rival amistoso",
        match_type="friendly",
        is_completed=True,
        result="win",
        created_by=world.owner_a.id,
    )
    tournament_match = MatchSession(
        team=archived_team,
        tournament_team=tournament_entry,
        date=today - timedelta(days=20),
        opponent_name="Rival torneo",
        match_type="official",
        is_completed=True,
        result="win",
        created_by=world.owner_a.id,
    )
    active_match = MatchSession(
        team=world.team_a,
        date=today,
        opponent_name="Rival actual",
        match_type="official",
        is_completed=True,
        result="win",
        created_by=world.owner_a.id,
    )
    dashboard_match = MatchSession(
        team=world.team_a,
        date=today + timedelta(days=1),
        opponent_name="Próximo rival",
        match_type="friendly",
        is_completed=False,
        created_by=world.owner_a.id,
    )

    db.session.add_all([
        closed,
        planned,
        archived_team,
        planned_team,
        historical_membership,
        planned_membership,
        closed_training,
        active_training,
        closed_tournament,
        active_tournament,
        tournament_entry,
        friendly,
        tournament_match,
        active_match,
        dashboard_match,
    ])
    db.session.flush()

    closed_row = MatchPlayer(
        match=tournament_match,
        player=world.players_a[0],
        player_number=20,
        is_called=True,
        attendance_status="present",
        did_play=True,
        position="setter",
    )
    active_row = MatchPlayer(
        match=active_match,
        player=world.players_a[0],
        player_number=1,
        is_called=True,
        attendance_status="present",
        did_play=True,
        position="setter",
    )
    db.session.add_all([closed_row, active_row])
    db.session.flush()
    db.session.add_all([
        PlayerMatchStat(
            match_player=closed_row,
            attacks_total=3,
            attacks_positive=2,
        ),
        PlayerMatchStat(
            match_player=active_row,
            attacks_total=4,
            attacks_positive=1,
        ),
    ])
    db.session.commit()

    return SimpleNamespace(
        closed=closed,
        planned=planned,
        archived_team=archived_team,
        planned_team=planned_team,
        closed_training=closed_training,
        active_training=active_training,
        closed_tournament=closed_tournament,
        active_tournament=active_tournament,
        friendly=friendly,
        tournament_match=tournament_match,
        active_match=active_match,
        dashboard_match=dashboard_match,
    )


def _ids(payload, key):
    return {row["id"] for row in payload[key]}


def test_operational_and_historical_lists_are_separated(
    client, world, auth_headers
):
    history = _build_history(world)
    headers = auth_headers(world.owner_a)

    cases = [
        ("/api/teams", "teams", world.team_a.id, history.archived_team.id),
        (
            "/api/trainings",
            "trainings",
            history.active_training.id,
            history.closed_training.id,
        ),
        (
            "/api/tournaments",
            "tournaments",
            history.active_tournament.id,
            history.closed_tournament.id,
        ),
        (
            "/api/matches",
            "matches",
            history.active_match.id,
            history.tournament_match.id,
        ),
    ]

    for endpoint, key, active_id, closed_id in cases:
        operational = client.get(endpoint, headers=headers)
        historical = client.get(
            f"{endpoint}?season_id={history.closed.id}",
            headers=headers,
        )

        assert operational.status_code == 200
        assert historical.status_code == 200
        assert active_id in _ids(operational.get_json(), key)
        assert closed_id not in _ids(operational.get_json(), key)
        assert closed_id in _ids(historical.get_json(), key)
        assert active_id not in _ids(historical.get_json(), key)
        assert historical.get_json()["season"]["status"] == "closed"


def test_historical_matches_include_friendly_and_tournament_matches(
    client, world, auth_headers
):
    history = _build_history(world)
    response = client.get(
        f"/api/matches?season_id={history.closed.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    ids = _ids(response.get_json(), "matches")
    assert history.friendly.id in ids
    assert history.tournament_match.id in ids


def test_explicit_season_includes_archived_and_planned_teams(
    client, world, auth_headers
):
    history = _build_history(world)
    headers = auth_headers(world.owner_a)

    closed_response = client.get(
        f"/api/teams?season_id={history.closed.id}", headers=headers
    )
    planned_response = client.get(
        f"/api/teams?season_id={history.planned.id}", headers=headers
    )

    archived = next(
        row for row in closed_response.get_json()["teams"]
        if row["id"] == history.archived_team.id
    )
    assert archived["status"] == "archived"
    assert _ids(planned_response.get_json(), "teams") == {
        history.planned_team.id
    }
    assert planned_response.get_json()["season"]["status"] == "planned"

    for endpoint, key in [
        ("/api/trainings", "trainings"),
        ("/api/tournaments", "tournaments"),
        ("/api/matches", "matches"),
    ]:
        response = client.get(
            f"{endpoint}?season_id={history.planned.id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.get_json()[key] == []
        assert response.get_json()["season"]["status"] == "planned"


def test_categories_remain_global_and_use_selected_season_counts(
    client, world, auth_headers
):
    history = _build_history(world)
    response = client.get(
        f"/api/categories?season_id={history.closed.id}",
        headers=auth_headers(world.owner_a),
    )
    detail = client.get(
        f"/api/categories/{world.category_a.id}?season_id={history.closed.id}",
        headers=auth_headers(world.owner_a),
    )

    category = next(
        row for row in response.get_json()["categories"]
        if row["id"] == world.category_a.id
    )
    assert category["total_teams"] == 1
    assert category["total_players"] == 1
    assert _ids(detail.get_json(), "teams") == {history.archived_team.id}


def test_player_is_global_and_memberships_are_segmented_by_team_season(
    client, world, auth_headers
):
    history = _build_history(world)
    response = client.get(
        f"/api/players?season_id={history.closed.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert len(response.get_json()["players"]) == len(world.players_a)
    player = next(
        row for row in response.get_json()["players"]
        if row["id"] == world.players_a[0].id
    )
    assert {team["id"] for team in player["teams"]} == {
        history.archived_team.id
    }
    assert player["teams"][0]["season_id"] == history.closed.id


def test_performance_keeps_total_history_and_accepts_explicit_season_filter(
    client, world, auth_headers
):
    history = _build_history(world)
    endpoint = f"/api/players/{world.players_a[0].id}/performance"
    headers = auth_headers(world.staff_a)

    total = client.get(endpoint, headers=headers)
    historical = client.get(
        f"{endpoint}?season_id={history.closed.id}", headers=headers
    )

    assert total.status_code == 200
    assert historical.status_code == 200
    assert total.get_json()["summary"]["matches_played"] == 2
    assert total.get_json()["totals"]["attacks_total"] == 7
    assert historical.get_json()["summary"]["matches_played"] == 1
    assert historical.get_json()["totals"]["attacks_total"] == 3
    assert historical.get_json()["summary"]["points_total"] == 2
    assert historical.get_json()["season"]["id"] == history.closed.id
    assert historical.get_json()["memberships"][0]["team"]["id"] == (
        history.archived_team.id
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/teams",
        "/api/trainings",
        "/api/tournaments",
        "/api/matches",
        "/api/players",
        "/api/categories",
    ],
)
def test_cross_tenant_season_filter_is_rejected(
    client, world, auth_headers, endpoint
):
    response = client.get(
        f"{endpoint}?season_id={world.season_b.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "SEASON_NOT_FOUND"


def test_cross_tenant_performance_season_filter_is_rejected(
    client, world, auth_headers
):
    response = client.get(
        (
            f"/api/players/{world.players_a[0].id}/performance"
            f"?season_id={world.season_b.id}"
        ),
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "SEASON_NOT_FOUND"


def test_historical_reads_do_not_change_season_status_or_active_context(
    client, world, auth_headers
):
    history = _build_history(world)
    headers = auth_headers(world.owner_a)

    for endpoint in ["teams", "trainings", "tournaments", "matches"]:
        response = client.get(
            f"/api/{endpoint}?season_id={history.closed.id}",
            headers=headers,
        )
        assert response.status_code == 200

    db.session.refresh(history.closed)
    db.session.refresh(world.season_a)
    assert history.closed.status == "closed"
    assert world.season_a.status == "active"
    assert get_active_season_for_club(world.club_a.id).id == world.season_a.id


def test_dashboard_ignores_historical_query_and_remains_operational(
    client, world, auth_headers
):
    history = _build_history(world)
    response = client.get(
        f"/api/club/dashboard?season_id={history.closed.id}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    payload = response.get_json()
    operations = payload["sections"]["operations"]
    assert {row["id"] for row in operations["upcoming_matches"]} == {
        history.dashboard_match.id
    }
    assert {
        row["tournament_id"]
        for row in payload["sections"]["active_tournaments"]
    } == {history.active_tournament.id}
    assert payload["next_match"]["id"] == history.dashboard_match.id


def test_season_query_parameter_never_redirects_training_creation(
    client, world, auth_headers
):
    history = _build_history(world)
    response = client.post(
        f"/api/trainings?season_id={history.closed.id}",
        headers=auth_headers(world.owner_a),
        json={
            "team_id": world.team_a.id,
            "date": get_club_today(world.club_a).isoformat(),
            "start_time": "08:00",
            "end_time": "10:00",
            "location": "Cancha activa",
        },
    )

    assert response.status_code == 201
    created = db.session.get(
        TrainingSession,
        response.get_json()["training"]["id"],
    )
    assert created.team.season_id == world.season_a.id
    assert history.closed.status == "closed"


def test_closed_team_mutation_remains_blocked_with_any_query_context(
    client, world, auth_headers
):
    history = _build_history(world)
    response = client.post(
        f"/api/trainings?season_id={world.season_a.id}",
        headers=auth_headers(world.owner_a),
        json={
            "team_id": history.archived_team.id,
            "date": get_club_today(world.club_a).isoformat(),
            "start_time": "08:00",
            "end_time": "10:00",
            "location": "Cancha histórica",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"


def test_direct_historical_resources_remain_available(
    client, world, auth_headers
):
    history = _build_history(world)
    headers = auth_headers(world.owner_a)
    endpoints = [
        f"/api/teams/{history.archived_team.id}",
        f"/api/trainings/{history.closed_training.id}",
        f"/api/tournaments/{history.closed_tournament.id}",
        f"/api/matches/{history.tournament_match.id}",
    ]

    for endpoint in endpoints:
        assert client.get(endpoint, headers=headers).status_code == 200
