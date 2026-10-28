from src.api.models import (
    Attendance,
    TournamentPlayer,
    TrainingPlayer,
    TrainingSession,
    db,
)


def test_training_roster_attendance_and_completion(
    client, world, auth_headers
):
    headers = auth_headers(world.coach_a)
    response = client.post(
        "/api/trainings",
        headers=headers,
        json={
            "team_id": world.team_a.id,
            "date": "2026-10-27",
            "start_time": "17:00",
            "end_time": "19:00",
            "location": "Cancha principal",
        },
    )
    assert response.status_code == 201
    training_id = response.get_json()["training"]["id"]
    roster = TrainingPlayer.query.filter_by(training_id=training_id).all()
    assert len(roster) == 8
    response = client.post(
        f"/api/trainings/{training_id}/attendance",
        headers=headers,
        json={"attendance": [
            {"player_id": row.player_id, "status": "present"} for row in roster
        ]},
    )
    assert response.status_code == 200
    assert Attendance.query.filter_by(session_id=training_id).count() == 8
    response = client.put(f"/api/trainings/{training_id}/complete", headers=headers)
    assert response.status_code == 200
    assert db.session.get(TrainingSession, training_id).status == "completed"
    assert Attendance.query.filter_by(session_id=training_id).count() == 8


def test_basic_tournament_team_and_player_registration(
    client, world, auth_headers
):
    headers = auth_headers(world.owner_a)
    response = client.post(
        "/api/tournaments",
        headers=headers,
        json={
            "name": "Copa de regresión",
            "organizer_name": "SportFlow",
            "start_date": "2026-11-01",
            "end_date": "2026-11-02",
            "default_referee_fee": "20.00",
        },
    )
    assert response.status_code == 201
    tournament = response.get_json()["tournament"]
    response = client.post(
        f"/api/tournaments/{tournament['id']}/teams",
        headers=headers,
        json={"team_id": world.team_a.id, "registration_fee": "100.00"},
    )
    assert response.status_code == 201
    entry = response.get_json()["tournament_team"]
    selected = [player.id for player in world.players_a[:6]]
    response = client.put(
        f"/api/tournament-teams/{entry['id']}/players",
        headers=headers,
        json={"player_ids": selected},
    )
    assert response.status_code == 200
    assert response.get_json()["total_players"] == 6
    registrations = TournamentPlayer.query.filter_by(
        tournament_team_id=entry["id"], status="active"
    ).all()
    assert {row.player_id for row in registrations} == set(selected)
