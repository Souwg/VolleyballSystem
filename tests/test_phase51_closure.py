from datetime import date, time, timedelta

from src.api.models import Season, Team, TeamPlayer, TrainingSession, db
from src.api.time_utils import get_club_today


def test_operational_player_memberships_do_not_mix_seasons(
    client, world, auth_headers
):
    closed = Season(
        club=world.club_a,
        name="Temporada cerrada",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="closed",
        created_by=world.owner_a.id,
    )
    planned = Season(
        club=world.club_a,
        name="Temporada planificada",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    closed_team = Team(
        name="Histórico",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=closed,
    )
    planned_team = Team(
        name="Preparación",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned,
    )
    player = world.players_a[0]
    db.session.add_all([
        closed,
        planned,
        closed_team,
        planned_team,
        TeamPlayer(
            team=closed_team,
            player=player,
            player_number=30,
            status="active",
        ),
        TeamPlayer(
            team=planned_team,
            player=player,
            player_number=31,
            status="active",
        ),
    ])
    db.session.commit()

    response = client.get(
        "/api/players",
        headers=auth_headers(world.owner_a),
    )
    row = next(
        item for item in response.get_json()["players"]
        if item["id"] == player.id
    )

    assert response.status_code == 200
    assert response.get_json()["season"]["id"] == world.season_a.id
    assert {team["id"] for team in row["teams"]} == {world.team_a.id}
    assert row["team_id"] == world.team_a.id

    historical = client.get(
        f"/api/players?season_id={closed.id}",
        headers=auth_headers(world.owner_a),
    )
    historical_row = next(
        item for item in historical.get_json()["players"]
        if item["id"] == player.id
    )
    assert {team["id"] for team in historical_row["teams"]} == {
        closed_team.id
    }


def test_closed_season_training_cannot_be_reactivated(
    client, world, auth_headers
):
    training = TrainingSession(
        team=world.team_a,
        date=get_club_today(world.club_a) - timedelta(days=1),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha principal",
        status="cancelled",
        created_by=world.owner_a.id,
    )
    target = Season(
        club=world.club_a,
        name="Temporada siguiente",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    target_team = Team(
        name="Team siguiente",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=target,
    )
    db.session.add_all([training, target, target_team])
    db.session.commit()

    transitioned = client.post(
        f"/api/seasons/{target.id}/transition",
        headers=auth_headers(world.owner_a),
        json={"source_season_id": world.season_a.id},
    )
    assert transitioned.status_code == 200

    response = client.post(
        f"/api/trainings/{training.id}/reactivate",
        headers=auth_headers(world.owner_a),
        json={"reason": "Corrección solicitada"},
    )

    db.session.refresh(training)
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"
    assert training.status == "cancelled"
