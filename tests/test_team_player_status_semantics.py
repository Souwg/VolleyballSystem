import uuid
from datetime import date, datetime, time

import pytest

from src.api.dashboard_service import _get_sports_structure
from src.api.endpoints.matches import sync_match_roster_if_open
from src.api.models import (
    Attendance,
    MatchPlayer,
    MatchSession,
    PlayerPayment,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TournamentPlayer,
    TournamentTeam,
    TrainingPlayer,
    TrainingSession,
    db,
)
from src.api.onboarding_service import get_club_onboarding_progress
from src.api.training_service import sync_training_roster


def _membership(world, index=0, team=None):
    return TeamPlayer.query.filter_by(
        team_id=(team or world.team_a).id,
        player_id=world.players_a[index].id,
        left_at=None,
    ).one()


def _training(world, team=None):
    training = TrainingSession(
        team=team or world.team_a,
        date=date(2026, 8, 10),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha principal",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    db.session.flush()
    return training


def _match(world, team=None):
    match = MatchSession(
        team=team or world.team_a,
        date=date(2026, 8, 11),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(match)
    db.session.flush()
    sync_match_roster_if_open(match)
    return match


def _tournament_entry(world):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name=f"Torneo status {uuid.uuid4().hex[:8]}",
        start_date=date(2026, 8, 20),
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


def _update_status(client, auth_headers, user, world, status, team=None):
    return client.put(
        f"/api/players/{world.players_a[0].id}/status",
        headers=auth_headers(user),
        json={"team_id": (team or world.team_a).id, "status": status},
    )


@pytest.mark.parametrize(
    ("status", "expected_in_training"),
    [("active", True), ("injured", True), ("inactive", False)],
)
def test_training_eligibility_follows_team_availability(
    world, status, expected_in_training
):
    membership = _membership(world)
    membership.status = status
    db.session.commit()
    training = _training(world)

    sync_training_roster(training)
    db.session.flush()

    player_ids = {
        row.player_id
        for row in TrainingPlayer.query.filter_by(training_id=training.id).all()
    }
    assert (membership.player_id in player_ids) is expected_in_training
    assert membership.left_at is None


def test_injured_player_can_receive_training_attendance(
    client, world, auth_headers
):
    membership = _membership(world)
    membership.status = "injured"
    db.session.commit()
    training = _training(world)
    sync_training_roster(training)
    db.session.commit()

    response = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.coach_a),
        json={
            "attendance": [
                {"player_id": membership.player_id, "status": "present"}
            ]
        },
    )

    assert response.status_code == 200
    assert Attendance.query.filter_by(
        session_id=training.id,
        player_id=membership.player_id,
        status="present",
    ).one()


def test_training_sync_preserves_inactive_snapshot_with_attendance(world):
    membership = _membership(world)
    training = _training(world)
    sync_training_roster(training)
    db.session.add(Attendance(
        session_id=training.id,
        player_id=membership.player_id,
        status="present",
    ))
    membership.status = "inactive"
    db.session.commit()

    result = sync_training_roster(training)
    db.session.flush()

    assert result["preserved_with_attendance_count"] == 1
    assert TrainingPlayer.query.filter_by(
        training_id=training.id,
        player_id=membership.player_id,
    ).one()
    assert Attendance.query.filter_by(
        session_id=training.id,
        player_id=membership.player_id,
    ).one()


@pytest.mark.parametrize(
    ("status", "expected_in_match"),
    [("active", True), ("injured", False), ("inactive", False)],
)
def test_match_eligibility_requires_active_team_status(
    world, status, expected_in_match
):
    membership = _membership(world)
    membership.status = status
    db.session.commit()

    match = _match(world)
    player_ids = {
        row.player_id
        for row in MatchPlayer.query.filter_by(match_id=match.id).all()
    }

    assert (membership.player_id in player_ids) is expected_in_match


@pytest.mark.parametrize("status", ["injured", "inactive"])
def test_unavailable_membership_cannot_receive_new_tournament_registration(
    client, world, auth_headers, status
):
    membership = _membership(world)
    membership.status = status
    db.session.commit()
    entry = _tournament_entry(world)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [membership.player_id]},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT"
    assert TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).first() is None


def test_active_membership_can_receive_new_tournament_registration(
    client, world, auth_headers
):
    membership = _membership(world)
    entry = _tournament_entry(world)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [membership.player_id]},
    )

    assert response.status_code == 200
    assert TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
        status="active",
    ).one()


def test_existing_tournament_registration_survives_injury_and_can_withdraw(
    client, world, auth_headers
):
    membership = _membership(world)
    entry = _tournament_entry(world)
    url = f"/api/tournament-teams/{entry.id}/players"
    headers = auth_headers(world.coach_a)

    assert client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    ).status_code == 200
    registration = TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).one()
    registration_id = registration.id
    membership.status = "injured"
    db.session.commit()

    keep_response = client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    )
    assert keep_response.status_code == 200
    assert db.session.get(TournamentPlayer, registration_id).status == "active"

    withdraw_response = client.put(url, headers=headers, json={"player_ids": []})
    assert withdraw_response.status_code == 200
    assert db.session.get(TournamentPlayer, registration_id).status == "withdrawn"
    assert PlayerPayment.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).count() == 0

    reactivate_response = client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    )
    assert reactivate_response.status_code == 409
    assert reactivate_response.get_json()["code"] == (
        "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT"
    )
    assert db.session.get(TournamentPlayer, registration_id).status == "withdrawn"


def test_globally_inactive_player_keeps_membership_but_is_not_newly_eligible(
    client, world, auth_headers
):
    membership = _membership(world)
    membership.player.is_active = False
    db.session.commit()

    training = _training(world)
    sync_training_roster(training)
    db.session.flush()
    match = _match(world)
    entry = _tournament_entry(world)
    tournament_response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [membership.player_id]},
    )

    assert membership.left_at is None
    assert membership.status == "active"
    assert TrainingPlayer.query.filter_by(
        training_id=training.id,
        player_id=membership.player_id,
    ).first() is None
    assert MatchPlayer.query.filter_by(
        match_id=match.id,
        player_id=membership.player_id,
    ).first() is None
    assert tournament_response.status_code == 409


@pytest.mark.parametrize("status", ["injured", "inactive"])
def test_dashboard_and_onboarding_use_open_membership_not_availability(
    world, status
):
    for membership in TeamPlayer.query.filter_by(team_id=world.team_a.id).all():
        membership.status = status
    world.club_a.location = "Cancha principal"
    db.session.commit()

    structure = _get_sports_structure(world.club_a.id, world.season_a.id)
    players_without_team = {
        row["player_id"] for row in structure["players_without_team"]["players"]
    }
    empty_team_ids = {
        row["team_id"] for row in structure["empty_teams"]["teams"]
    }

    assert not ({player.id for player in world.players_a} & players_without_team)
    assert world.team_a.id not in empty_team_ids
    assert get_club_onboarding_progress(world.club_a) == {
        "step": 5,
        "status": "completed",
    }


def test_status_is_independent_per_team_and_drives_each_team_eligibility(world):
    maria = world.players_a[0]
    sub_18 = Team(
        name="Sub-18",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    sub_18_membership = TeamPlayer(
        team=sub_18,
        player=maria,
        player_number=40,
        status="active",
    )
    sub_16_membership = _membership(world)
    sub_16_membership.status = "injured"
    db.session.add_all([sub_18, sub_18_membership])
    db.session.commit()

    sub_16_training = _training(world)
    sync_training_roster(sub_16_training)
    db.session.flush()
    sub_16_match = _match(world)
    sub_18_match = _match(world, sub_18)

    assert TrainingPlayer.query.filter_by(
        training_id=sub_16_training.id,
        player_id=maria.id,
    ).one()
    assert MatchPlayer.query.filter_by(
        match_id=sub_16_match.id,
        player_id=maria.id,
    ).first() is None
    assert MatchPlayer.query.filter_by(
        match_id=sub_18_match.id,
        player_id=maria.id,
    ).one()
    assert sub_16_membership.status == "injured"
    assert sub_18_membership.status == "active"


@pytest.mark.parametrize(
    ("initial_status", "new_status"),
    [
        ("active", "active"),
        ("active", "injured"),
        ("injured", "active"),
        ("active", "inactive"),
        ("inactive", "active"),
        ("injured", "inactive"),
        ("inactive", "injured"),
        ("injured", "injured"),
        ("inactive", "inactive"),
    ],
)
def test_all_status_transitions_are_allowed_and_do_not_create_memberships(
    client, world, auth_headers, initial_status, new_status
):
    membership = _membership(world)
    membership.status = initial_status
    db.session.commit()
    membership_count = TeamPlayer.query.count()

    response = _update_status(
        client, auth_headers, world.coach_a, world, new_status
    )

    assert response.status_code == 200
    assert db.session.get(TeamPlayer, membership.id).status == new_status
    assert TeamPlayer.query.count() == membership_count


def test_status_permissions_and_closed_membership_guards(
    client, world, auth_headers
):
    assert _update_status(
        client, auth_headers, world.owner_a, world, "injured"
    ).status_code == 200
    assert _update_status(
        client, auth_headers, world.coach_a, world, "active"
    ).status_code == 200

    staff_response = _update_status(
        client, auth_headers, world.staff_a, world, "inactive"
    )
    cross_tenant_response = _update_status(
        client, auth_headers, world.coach_b, world, "inactive"
    )
    assert staff_response.status_code == 403
    assert cross_tenant_response.status_code == 404

    membership = _membership(world)
    membership.left_at = datetime(2026, 7, 1)
    db.session.commit()
    closed_response = _update_status(
        client, auth_headers, world.owner_a, world, "inactive"
    )
    assert closed_response.status_code == 404
    assert db.session.get(TeamPlayer, membership.id).status == "active"


def test_planned_team_status_is_owner_only(client, world, auth_headers):
    planned_season = Season(
        club=world.club_a,
        name="Próxima temporada",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    planned_team = Team(
        name="Team planificado",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned_season,
    )
    membership = TeamPlayer(
        team=planned_team,
        player=world.players_a[0],
        player_number=50,
        status="active",
    )
    db.session.add_all([planned_season, planned_team, membership])
    db.session.commit()

    coach_response = _update_status(
        client,
        auth_headers,
        world.coach_a,
        world,
        "injured",
        team=planned_team,
    )
    owner_response = _update_status(
        client,
        auth_headers,
        world.owner_a,
        world,
        "injured",
        team=planned_team,
    )

    assert coach_response.status_code == 403
    assert owner_response.status_code == 200
    assert db.session.get(TeamPlayer, membership.id).status == "injured"


def test_player_attendance_separates_current_and_historical_memberships(
    client, world, auth_headers
):
    player = world.players_a[0]
    historical = _membership(world)
    historical.left_at = datetime(2026, 6, 30)
    current_team = Team(
        name="Team actual alterno",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    current = TeamPlayer(
        team=current_team,
        player=player,
        player_number=44,
        status="injured",
        joined_at=datetime(2026, 7, 1),
    )
    db.session.add_all([current_team, current])
    db.session.commit()

    response = client.get(
        f"/api/players/{player.id}/attendance",
        headers=auth_headers(world.coach_a),
    )
    data = response.get_json()["player"]

    assert response.status_code == 200
    assert [row["membership_id"] for row in data["teams"]] == [current.id]
    assert data["teams"][0]["status"] == "injured"
    assert data["teams"][0]["season_id"] == world.season_a.id
    assert [row["membership_id"] for row in data["historical_teams"]] == [
        historical.id
    ]
    assert data["historical_teams"][0]["left_at"] is not None


@pytest.mark.parametrize("closure", ["season_closed", "team_archived"])
def test_open_membership_of_non_operational_team_is_not_current_team(
    client, world, auth_headers, closure
):
    membership = _membership(world)

    if closure == "season_closed":
        world.season_a.status = "closed"
    else:
        world.team_a.status = "archived"

    db.session.commit()

    response = client.get(
        f"/api/players/{membership.player_id}/attendance",
        headers=auth_headers(world.owner_a),
    )
    data = response.get_json()["player"]

    assert response.status_code == 200
    assert data["teams"] == []
    assert [row["membership_id"] for row in data["historical_teams"]] == [
        membership.id
    ]
    assert data["historical_teams"][0]["left_at"] is None
    assert db.session.get(TeamPlayer, membership.id).left_at is None


def test_planned_team_membership_is_listed_as_current_with_season_status(
    client, world, auth_headers
):
    planned_season = Season(
        club=world.club_a,
        name="Próxima temporada",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    planned_team = Team(
        name="Team planificado",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned_season,
    )
    planned_membership = TeamPlayer(
        team=planned_team,
        player=world.players_a[0],
        player_number=50,
        status="active",
    )
    db.session.add_all([planned_season, planned_team, planned_membership])
    db.session.commit()

    response = client.get(
        f"/api/players/{world.players_a[0].id}/attendance",
        headers=auth_headers(world.owner_a),
    )
    rows = {
        row["membership_id"]: row
        for row in response.get_json()["player"]["teams"]
    }

    assert set(rows) == {_membership(world).id, planned_membership.id}
    assert rows[planned_membership.id]["season_status"] == "planned"
    assert rows[planned_membership.id]["season_name"] == "Próxima temporada"


@pytest.mark.parametrize(
    ("status", "expected_in_training", "expected_in_match"),
    [
        ("active", True, True),
        ("injured", True, False),
        ("inactive", False, False),
    ],
)
def test_creation_endpoints_apply_status_matrix(
    client, world, auth_headers, status, expected_in_training, expected_in_match
):
    membership = _membership(world)
    membership.status = status
    db.session.commit()
    headers = auth_headers(world.coach_a)

    training_response = client.post(
        "/api/trainings",
        headers=headers,
        json={
            "team_id": world.team_a.id,
            "date": "2026-08-10",
            "start_time": "17:00",
            "end_time": "19:00",
            "location": "Cancha principal",
        },
    )
    match_response = client.post(
        "/api/matches",
        headers=headers,
        json={
            "team_id": world.team_a.id,
            "date": "2026-08-11",
            "opponent_name": "Rival",
            "match_type": "official",
        },
    )

    assert training_response.status_code == 201
    assert match_response.status_code == 201
    training = TrainingSession.query.filter_by(team_id=world.team_a.id).one()
    match = MatchSession.query.filter_by(team_id=world.team_a.id).one()
    assert (
        TrainingPlayer.query.filter_by(
            training_id=training.id,
            player_id=membership.player_id,
        ).first() is not None
    ) is expected_in_training
    assert (
        MatchPlayer.query.filter_by(
            match_id=match.id,
            player_id=membership.player_id,
        ).first() is not None
    ) is expected_in_match


def test_deactivating_player_via_endpoint_keeps_memberships_untouched(
    client, world, auth_headers
):
    membership = _membership(world)
    membership.status = "injured"
    db.session.commit()

    response = client.put(
        f"/api/players/{membership.player_id}/active",
        headers=auth_headers(world.owner_a),
        json={"is_active": False},
    )

    assert response.status_code == 200
    refreshed = db.session.get(TeamPlayer, membership.id)
    assert refreshed.player.is_active is False
    assert refreshed.status == "injured"
    assert refreshed.left_at is None


@pytest.mark.parametrize(
    "make_unavailable",
    ["injured", "inactive", "player_inactive"],
)
def test_withdrawn_registration_cannot_be_reactivated_while_unavailable(
    client, world, auth_headers, make_unavailable
):
    membership = _membership(world)
    entry = _tournament_entry(world)
    url = f"/api/tournament-teams/{entry.id}/players"
    headers = auth_headers(world.coach_a)
    assert client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    ).status_code == 200
    assert client.put(
        url, headers=headers, json={"player_ids": []}
    ).status_code == 200

    if make_unavailable == "player_inactive":
        membership.player.is_active = False
    else:
        membership.status = make_unavailable

    db.session.commit()

    response = client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT"
    assert TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).one().status == "withdrawn"

    if make_unavailable == "player_inactive":
        membership.player.is_active = True
    else:
        membership.status = "active"

    db.session.commit()

    assert client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    ).status_code == 200


def test_rejected_tournament_update_does_not_apply_partial_changes(
    client, world, auth_headers
):
    registered = _membership(world, 0)
    injured = _membership(world, 1)
    injured.status = "injured"
    db.session.commit()
    entry = _tournament_entry(world)
    url = f"/api/tournament-teams/{entry.id}/players"
    headers = auth_headers(world.coach_a)
    assert client.put(
        url, headers=headers, json={"player_ids": [registered.player_id]}
    ).status_code == 200

    response = client.put(
        url, headers=headers, json={"player_ids": [injured.player_id]}
    )

    assert response.status_code == 409
    rows = TournamentPlayer.query.filter_by(tournament_team_id=entry.id).all()
    assert [(row.player_id, row.status) for row in rows] == [
        (registered.player_id, "active")
    ]


def _registered_then_membership_closed(client, world, auth_headers):
    membership = _membership(world, 0)
    teammate = _membership(world, 1)
    entry = _tournament_entry(world)
    url = f"/api/tournament-teams/{entry.id}/players"
    headers = auth_headers(world.coach_a)
    assert client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    ).status_code == 200
    membership.left_at = datetime(2026, 8, 1)
    db.session.commit()
    registration = TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).one()
    return membership, teammate, entry, registration, url, headers


def _registration_charge(world, entry, player_id, status):
    charge = PlayerPayment(
        club_id=world.club_a.id,
        player_id=player_id,
        tournament_team_id=entry.id,
        payment_type="tournament",
        amount=10,
        currency_code="USD",
        status=status,
    )
    db.session.add(charge)
    db.session.commit()
    return charge


def test_registration_with_closed_membership_stays_in_roster_read_model(
    client, world, auth_headers
):
    membership, _, _, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )

    data = client.get(url, headers=headers).get_json()
    rows = {row["player_id"]: row for row in data["players"]}

    assert data["registered_count"] == 1
    assert rows[membership.player_id]["is_registered"] is True
    assert rows[membership.player_id]["registration_status"] == "active"
    assert rows[membership.player_id]["membership_open"] is False
    assert rows[membership.player_id]["team_status"] is None
    assert rows[membership.player_id]["player_number"] == (
        membership.player_number
    )
    assert db.session.get(TournamentPlayer, registration.id).status == "active"


def test_saving_roster_from_read_model_keeps_registration_with_closed_membership(
    client, world, auth_headers
):
    membership, teammate, entry, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )
    memberships_before = TeamPlayer.query.count()

    registered_ids = [
        row["player_id"]
        for row in client.get(url, headers=headers).get_json()["players"]
        if row["is_registered"]
    ]
    response = client.put(
        url,
        headers=headers,
        json={"player_ids": registered_ids + [teammate.player_id]},
    )

    assert response.status_code == 200
    assert db.session.get(TournamentPlayer, registration.id).status == "active"
    assert TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=teammate.player_id,
        status="active",
    ).one()
    assert TeamPlayer.query.count() == memberships_before
    assert db.session.get(TeamPlayer, membership.id).left_at is not None


def test_paid_charge_does_not_block_saving_roster_with_closed_membership(
    client, world, auth_headers
):
    membership, teammate, entry, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )
    charge = _registration_charge(world, entry, membership.player_id, "paid")
    roster = [membership.player_id, teammate.player_id]

    # Añadir cambia el reparto: el Coach no puede; el Owner conserva su flujo.
    rejected = client.put(url, headers=headers, json={"player_ids": roster})

    assert rejected.status_code == 409
    assert rejected.get_json()["code"] == "FINANCE_DEPENDENCY"

    response = client.put(
        url,
        headers=auth_headers(world.owner_a),
        json={"player_ids": roster},
    )

    assert response.status_code == 200
    assert db.session.get(TournamentPlayer, registration.id).status == "active"
    assert db.session.get(PlayerPayment, charge.id).status == "paid"


def test_explicit_withdrawal_with_closed_membership_keeps_financial_rules(
    client, world, auth_headers
):
    membership, _, entry, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )
    paid = _registration_charge(world, entry, membership.player_id, "paid")

    # El Coach no recibe el detalle financiero; el Owner, sí.
    for user, code in [
        (world.coach_a, "FINANCE_DEPENDENCY"),
        (world.owner_a, "TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED"),
    ]:
        response = client.put(
            url,
            headers=auth_headers(user),
            json={"player_ids": []},
        )

        assert response.status_code == 409
        assert response.get_json()["code"] == code
        assert (
            db.session.get(TournamentPlayer, registration.id).status == "active"
        )
        assert db.session.get(PlayerPayment, paid.id).status == "paid"


def test_keeping_registration_with_closed_membership_keeps_pending_charge(
    client, world, auth_headers
):
    membership, _, entry, _, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )
    pending = _registration_charge(world, entry, membership.player_id, "pending")

    response = client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    )

    assert response.status_code == 200
    assert db.session.get(PlayerPayment, pending.id).status == "pending"


def test_registration_with_closed_membership_can_be_withdrawn_explicitly(
    client, world, auth_headers
):
    membership, _, entry, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )

    response = client.put(url, headers=headers, json={"player_ids": []})

    assert response.status_code == 200
    assert db.session.get(TournamentPlayer, registration.id).status == "withdrawn"
    assert db.session.get(TeamPlayer, membership.id).left_at is not None

    row = next(
        row
        for row in client.get(url, headers=headers).get_json()["players"]
        if row["player_id"] == membership.player_id
    )
    assert row["is_registered"] is False
    assert row["registration_status"] == "withdrawn"


def test_withdrawn_registration_with_closed_membership_cannot_be_reactivated(
    client, world, auth_headers
):
    membership, _, _, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )
    memberships_before = TeamPlayer.query.count()
    assert client.put(
        url, headers=headers, json={"player_ids": []}
    ).status_code == 200

    response = client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT"
    assert db.session.get(TournamentPlayer, registration.id).status == "withdrawn"
    assert TeamPlayer.query.count() == memberships_before


def test_closed_membership_without_registration_cannot_be_newly_registered(
    client, world, auth_headers
):
    membership = _membership(world)
    membership.left_at = datetime(2026, 8, 1)
    db.session.commit()
    entry = _tournament_entry(world)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [membership.player_id]},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "PLAYER_NOT_IN_TEAM"
    assert TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).first() is None


def test_rejoining_team_uses_open_membership_in_tournament_read_model(
    client, world, auth_headers
):
    membership, _, _, registration, url, headers = (
        _registered_then_membership_closed(client, world, auth_headers)
    )
    reopened = TeamPlayer(
        team_id=membership.team_id,
        player_id=membership.player_id,
        player_number=77,
        status="injured",
    )
    db.session.add(reopened)
    db.session.commit()

    rows = [
        row
        for row in client.get(url, headers=headers).get_json()["players"]
        if row["player_id"] == membership.player_id
    ]

    assert len(rows) == 1
    assert rows[0]["membership_open"] is True
    assert rows[0]["team_status"] == "injured"
    assert rows[0]["player_number"] == 77
    assert db.session.get(TournamentPlayer, registration.id).status == "active"


def test_globally_inactive_registered_player_is_kept_and_can_withdraw(
    client, world, auth_headers
):
    membership = _membership(world)
    entry = _tournament_entry(world)
    url = f"/api/tournament-teams/{entry.id}/players"
    headers = auth_headers(world.coach_a)
    assert client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    ).status_code == 200
    membership.player.is_active = False
    db.session.commit()

    assert client.put(
        url, headers=headers, json={"player_ids": [membership.player_id]}
    ).status_code == 200
    registration = TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).one()
    assert registration.status == "active"

    assert client.put(
        url, headers=headers, json={"player_ids": []}
    ).status_code == 200
    assert db.session.get(TournamentPlayer, registration.id).status == "withdrawn"


def test_registered_player_injured_is_excluded_from_tournament_match(world):
    membership = _membership(world)
    entry = _tournament_entry(world)
    db.session.add(TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
        status="active",
    ))
    membership.status = "injured"
    db.session.commit()

    match = MatchSession(
        team=world.team_a,
        tournament_team_id=entry.id,
        date=date(2026, 8, 21),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(match)
    db.session.flush()
    sync_match_roster_if_open(match)

    assert MatchPlayer.query.filter_by(match_id=match.id).count() == 0
    assert db.session.get(TournamentPlayer, TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=membership.player_id,
    ).one().id).status == "active"


def test_match_sync_preserves_snapshot_with_history_after_injury(world):
    called = _membership(world, 0)
    uncalled = _membership(world, 1)
    match = _match(world)
    called_row = MatchPlayer.query.filter_by(
        match_id=match.id,
        player_id=called.player_id,
    ).one()
    called_row.is_called = True
    called.status = "injured"
    uncalled.status = "injured"
    db.session.commit()

    sync_match_roster_if_open(match)

    assert MatchPlayer.query.filter_by(
        match_id=match.id,
        player_id=called.player_id,
    ).one().is_called is True
    assert MatchPlayer.query.filter_by(
        match_id=match.id,
        player_id=uncalled.player_id,
    ).first() is None


def test_status_change_is_scoped_to_one_membership_via_endpoint(
    client, world, auth_headers
):
    sub_18 = Team(
        name="Sub-18",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    sub_18_membership = TeamPlayer(
        team=sub_18,
        player=world.players_a[0],
        player_number=40,
        status="active",
    )
    db.session.add_all([sub_18, sub_18_membership])
    db.session.commit()

    response = _update_status(
        client, auth_headers, world.owner_a, world, "injured"
    )

    assert response.status_code == 200
    assert _membership(world).status == "injured"
    assert db.session.get(TeamPlayer, sub_18_membership.id).status == "active"


@pytest.mark.parametrize("user_key", ["owner_a", "coach_a"])
@pytest.mark.parametrize(
    ("closure", "expected_code"),
    [("season_closed", "SEASON_CLOSED"), ("team_archived", "TEAM_ARCHIVED")],
)
def test_status_cannot_change_on_non_operational_team(
    client, world, auth_headers, user_key, closure, expected_code
):
    membership = _membership(world)

    if closure == "season_closed":
        world.season_a.status = "closed"
    else:
        world.team_a.status = "archived"

    db.session.commit()

    response = _update_status(
        client, auth_headers, getattr(world, user_key), world, "injured"
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == expected_code
    assert db.session.get(TeamPlayer, membership.id).status == "active"


def test_status_endpoint_rejects_missing_token_invalid_value_and_foreign_team(
    client, world, auth_headers
):
    membership = _membership(world)
    url = f"/api/players/{membership.player_id}/status"

    no_token = client.put(
        url, json={"team_id": world.team_a.id, "status": "injured"}
    )
    invalid_value = client.put(
        url,
        headers=auth_headers(world.owner_a),
        json={"team_id": world.team_a.id, "status": "suspended"},
    )
    foreign_team = client.put(
        url,
        headers=auth_headers(world.owner_a),
        json={"team_id": world.team_b.id, "status": "injured"},
    )

    assert no_token.status_code == 401
    assert invalid_value.status_code == 400
    assert invalid_value.get_json()["code"] == "INVALID_PLAYER_STATUS"
    assert foreign_team.status_code == 404
    assert db.session.get(TeamPlayer, membership.id).status == "active"
