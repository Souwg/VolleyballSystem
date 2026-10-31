import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.models import (
    MatchSession,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TrainingSession,
    db,
)


def _planned(world, name="Temporada 2027"):
    season = Season(
        club=world.club_a,
        name=name,
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
        status="planned",
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return season


def _target_team(world, season, name="Team A"):
    team = Team(
        name=name,
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=season,
        status="active",
    )
    db.session.add(team)
    db.session.commit()
    return team


def _create_planned(client, world, auth_headers, user=None, **overrides):
    payload = {
        "name": "Temporada 2027",
        "start_date": "2027-01-01",
        "end_date": "2027-12-31",
    }
    payload.update(overrides)
    return client.post(
        "/api/seasons",
        json=payload,
        headers=auth_headers(user or world.owner_a),
    )


def _transition(client, world, target, auth_headers, source=None, user=None):
    return client.post(
        f"/api/seasons/{target.id}/transition",
        json={"source_season_id": (source or world.season_a).id},
        headers=auth_headers(user or world.owner_a),
    )


def test_owner_creates_planned_season(client, world, auth_headers):
    response = _create_planned(client, world, auth_headers)
    assert response.status_code == 201
    assert response.get_json()["season"]["status"] == "planned"


@pytest.mark.parametrize("role", ["coach_a", "staff_a"])
def test_non_owner_cannot_create_planned_season(
    client, world, auth_headers, role
):
    response = _create_planned(
        client, world, auth_headers, user=getattr(world, role)
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"name": ""}, "SEASON_NAME_REQUIRED"),
        ({"start_date": "bad"}, "INVALID_DATE_FORMAT"),
        (
            {"start_date": "2027-03-01", "end_date": "2027-02-01"},
            "INVALID_SEASON_DATE_RANGE",
        ),
    ],
)
def test_planned_season_validates_input(
    client, world, auth_headers, overrides, code
):
    response = _create_planned(client, world, auth_headers, **overrides)
    assert response.status_code == 400
    assert response.get_json()["code"] == code


def test_creating_planned_does_not_change_active(client, world, auth_headers):
    _create_planned(client, world, auth_headers)
    db.session.refresh(world.season_a)
    assert world.season_a.status == "active"


@pytest.mark.parametrize("role", ["owner_a", "coach_a", "staff_a"])
def test_club_roles_can_list_seasons(client, world, auth_headers, role):
    _planned(world)
    response = client.get(
        "/api/seasons", headers=auth_headers(getattr(world, role))
    )
    assert response.status_code == 200
    assert len(response.get_json()["seasons"]) == 2


def test_season_detail_is_tenant_scoped(client, world, auth_headers):
    response = client.get(
        f"/api/seasons/{world.season_b.id}",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 404


def test_owner_creates_team_in_planned(client, world, auth_headers):
    planned = _planned(world)
    response = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "Future", "gender": "female", "season_id": planned.id},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 201
    assert response.get_json()["team"]["season_id"] == planned.id


def test_team_creation_without_season_uses_active(client, world, auth_headers):
    response = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "Current", "gender": "female"},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 201
    assert response.get_json()["team"]["season_id"] == world.season_a.id


@pytest.mark.parametrize("status", ["active", "closed"])
def test_explicit_future_team_requires_planned(
    client, world, auth_headers, status
):
    season = world.season_a
    if status == "closed":
        season = Season(
            club=world.club_a,
            name="Closed",
            start_date=date(2025, 1, 1),
            status="closed",
        )
        db.session.add(season)
        db.session.commit()
    response = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={"name": "Future", "gender": "female", "season_id": season.id},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_NOT_PLANNED"


def test_future_team_rejects_other_tenant_season(client, world, auth_headers):
    response = client.post(
        f"/api/categories/{world.category_a.id}/teams",
        json={
            "name": "Future",
            "gender": "female",
            "season_id": world.season_b.id,
        },
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 404


def test_same_team_structure_can_exist_in_two_seasons(world):
    planned = _planned(world)
    duplicate = _target_team(world, planned)
    assert duplicate.id != world.team_a.id


def test_same_team_structure_stays_unique_inside_season(world):
    duplicate = Team(
        name=world.team_a.name,
        gender=world.team_a.gender,
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    db.session.add(duplicate)
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_planned_team_is_absent_from_operational_team_list(
    client, world, auth_headers
):
    planned = _planned(world)
    future = _target_team(world, planned, "Future")
    response = client.get("/api/teams", headers=auth_headers(world.owner_a))
    assert future.id not in {team["id"] for team in response.get_json()["teams"]}


def test_owner_adds_existing_player_to_planned_team(
    client, world, auth_headers
):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    response = client.post(
        f"/api/teams/{target.id}/players/existing",
        json={"player_id": world.players_a[0].id, "player_number": 20},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 201


def test_planned_membership_does_not_close_active_membership(
    client, world, auth_headers
):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    source_membership = TeamPlayer.query.filter_by(
        team_id=world.team_a.id, player_id=world.players_a[0].id
    ).one()
    client.post(
        f"/api/teams/{target.id}/players/existing",
        json={"player_id": world.players_a[0].id, "player_number": 20},
        headers=auth_headers(world.owner_a),
    )
    assert source_membership.left_at is None


@pytest.mark.parametrize("role", ["coach_a", "staff_a"])
def test_non_owner_cannot_prepare_planned_membership(
    client, world, auth_headers, role
):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    response = client.post(
        f"/api/teams/{target.id}/players/existing",
        json={"player_id": world.players_a[0].id, "player_number": 20},
        headers=auth_headers(getattr(world, role)),
    )
    assert response.status_code == 403


def test_duplicate_selected_team_copies_only_structure(
    client, world, auth_headers
):
    planned = _planned(world)
    response = client.post(
        f"/api/seasons/{planned.id}/teams/duplicate",
        json={
            "source_season_id": world.season_a.id,
            "team_ids": [world.team_a.id],
        },
        headers=auth_headers(world.owner_a),
    )
    copied = response.get_json()["teams"][0]
    assert response.status_code == 201
    assert (copied["name"], copied["category_id"], copied["gender"]) == (
        world.team_a.name,
        world.team_a.category_id,
        world.team_a.gender,
    )
    assert copied["id"] != world.team_a.id


def test_structure_copy_does_not_copy_roster_or_activities(
    client, world, auth_headers
):
    planned = _planned(world)
    response = client.post(
        f"/api/seasons/{planned.id}/teams/duplicate",
        json={"source_season_id": world.season_a.id, "team_ids": [world.team_a.id]},
        headers=auth_headers(world.owner_a),
    )
    target_id = response.get_json()["teams"][0]["id"]
    assert TeamPlayer.query.filter_by(team_id=target_id).count() == 0
    assert TrainingSession.query.filter_by(team_id=target_id).count() == 0
    assert MatchSession.query.filter_by(team_id=target_id).count() == 0


def test_repeated_structure_copy_returns_conflict(client, world, auth_headers):
    planned = _planned(world)
    payload = {"source_season_id": world.season_a.id, "team_ids": [world.team_a.id]}
    url = f"/api/seasons/{planned.id}/teams/duplicate"
    assert client.post(url, json=payload, headers=auth_headers(world.owner_a)).status_code == 201
    second = client.post(url, json=payload, headers=auth_headers(world.owner_a))
    assert second.status_code == 409
    assert Team.query.filter_by(season_id=planned.id).count() == 1


def test_structure_copy_rejects_non_planned_target(client, world, auth_headers):
    response = client.post(
        f"/api/seasons/{world.season_a.id}/teams/duplicate",
        json={"source_season_id": world.season_a.id, "team_ids": [world.team_a.id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409


def test_structure_copy_rejects_cross_tenant_target(client, world, auth_headers):
    response = client.post(
        f"/api/seasons/{world.season_b.id}/teams/duplicate",
        json={"source_season_id": world.season_a.id, "team_ids": [world.team_a.id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 404


def test_structure_copy_rejects_team_outside_source(client, world, auth_headers):
    planned = _planned(world)
    response = client.post(
        f"/api/seasons/{planned.id}/teams/duplicate",
        json={"source_season_id": world.season_a.id, "team_ids": [world.team_b.id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 404


def test_copy_roster_creates_new_active_memberships(client, world, auth_headers):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    selected = world.players_a[:2]
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [p.id for p in selected]},
        headers=auth_headers(world.owner_a),
    )
    rows = TeamPlayer.query.filter_by(team_id=target.id).all()
    assert response.status_code == 201
    assert {row.player_id for row in rows} == {player.id for player in selected}
    assert {row.status for row in rows} == {"active"}


def test_copy_roster_preserves_source_history(client, world, auth_headers):
    planned = _planned(world)
    target = _target_team(world, planned, "Sub-16")
    source = TeamPlayer.query.filter_by(team_id=world.team_a.id).first()
    joined_at = source.joined_at
    client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [source.player_id]},
        headers=auth_headers(world.owner_a),
    )
    assert source.left_at is None
    assert source.joined_at == joined_at


def test_roster_copy_supports_promotion_to_different_team_name(
    client, world, auth_headers
):
    planned = _planned(world)
    target = _target_team(world, planned, "Sub-16")
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [world.players_a[0].id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 201


def test_roster_copy_rejects_occupied_number(client, world, auth_headers):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    db.session.add(TeamPlayer(team=target, player=world.players_a[2], player_number=1))
    db.session.commit()
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [world.players_a[0].id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NUMBER_DUPLICATED"


def test_roster_copy_rejects_existing_player(client, world, auth_headers):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    db.session.add(TeamPlayer(team=target, player=world.players_a[0], player_number=20))
    db.session.commit()
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [world.players_a[0].id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_ALREADY_IN_TEAM"


def test_roster_copy_rejects_cross_tenant_source(client, world, auth_headers):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_b.id, "player_ids": [world.players_b[0].id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 404


def test_roster_copy_requires_planned_target(client, world, auth_headers):
    response = client.post(
        f"/api/teams/{world.team_a.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [world.players_a[0].id]},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_NOT_PLANNED"


def test_transition_closes_source_and_activates_target(client, world, auth_headers):
    planned = _planned(world)
    target_team = _target_team(world, planned, "Future")
    response = _transition(client, world, planned, auth_headers)
    assert response.status_code == 200
    assert db.session.get(Season, world.season_a.id).status == "closed"
    assert db.session.get(Season, planned.id).status == "active"
    assert db.session.get(Team, target_team.id).status == "active"


def test_transition_requires_target_team(client, world, auth_headers):
    planned = _planned(world)
    response = _transition(client, world, planned, auth_headers)
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_TEAM_REQUIRED"
    assert world.season_a.status == "active"


@pytest.mark.parametrize("activity", ["training", "match", "tournament"])
def test_transition_blocks_open_activities(
    client, world, auth_headers, activity
):
    planned = _planned(world)
    _target_team(world, planned, "Future")
    if activity == "training":
        db.session.add(TrainingSession(
            team=world.team_a, date=date(2026, 12, 1), status="scheduled"
        ))
    elif activity == "match":
        db.session.add(MatchSession(
            team=world.team_a,
            date=date(2026, 12, 1),
            opponent_name="Rival",
            match_type="official",
            is_completed=False,
        ))
    else:
        db.session.add(Tournament(
            club=world.club_a,
            season=world.season_a,
            name=f"Open {uuid.uuid4().hex}",
            start_date=date(2026, 12, 1),
            status="active",
            created_by=world.owner_a.id,
        ))
    db.session.commit()
    response = _transition(client, world, planned, auth_headers)
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_HAS_OPEN_ACTIVITIES"
    assert db.session.get(Season, world.season_a.id).status == "active"
    assert db.session.get(Season, planned.id).status == "planned"


@pytest.mark.parametrize("role", ["coach_a", "staff_a"])
def test_non_owner_cannot_transition(client, world, auth_headers, role):
    planned = _planned(world)
    _target_team(world, planned, "Future")
    response = _transition(
        client, world, planned, auth_headers, user=getattr(world, role)
    )
    assert response.status_code == 403


def test_transition_rejects_other_tenant_target(client, world, auth_headers):
    response = _transition(client, world, world.season_b, auth_headers)
    assert response.status_code == 404


def test_transition_rejects_non_active_source(client, world, auth_headers):
    planned = _planned(world)
    _target_team(world, planned, "Future")
    closed = Season(
        club=world.club_a,
        name="Closed",
        start_date=date(2025, 1, 1),
        status="closed",
    )
    db.session.add(closed)
    db.session.commit()
    response = _transition(client, world, planned, auth_headers, source=closed)
    assert response.status_code == 409


def test_transition_rolls_back_both_seasons_on_integrity_conflict(
    client, world, auth_headers, monkeypatch
):
    planned = _planned(world)
    _target_team(world, planned, "Future")

    def fail_commit():
        raise IntegrityError("transition", {}, Exception("conflict"))

    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = _transition(client, world, planned, auth_headers)

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_TRANSITION_CONFLICT"
    assert db.session.get(Season, world.season_a.id).status == "active"
    assert db.session.get(Season, planned.id).status == "planned"


def test_transition_preserves_team_status_and_membership_dates(
    client, world, auth_headers
):
    planned = _planned(world)
    _target_team(world, planned, "Future")
    source_membership = TeamPlayer.query.filter_by(team_id=world.team_a.id).first()
    source_team_status = world.team_a.status
    _transition(client, world, planned, auth_headers)
    assert world.team_a.status == source_team_status
    assert source_membership.left_at is None


def test_closed_season_remains_readable_after_transition(
    client, world, auth_headers
):
    planned = _planned(world)
    _target_team(world, planned, "Future")
    _transition(client, world, planned, auth_headers)
    response = client.get(
        f"/api/seasons/{world.season_a.id}",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200
    assert response.get_json()["season"]["status"] == "closed"


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("put", "/api/teams/{team_id}", {"name": "Edited", "gender": "female"}),
        ("put", "/api/teams/{team_id}/archive", None),
        ("delete", "/api/teams/{team_id}", None),
    ],
)
def test_closed_season_blocks_team_structure_mutations(
    client, world, auth_headers, method, path, payload
):
    planned = _planned(world)
    _target_team(world, planned, "Future")
    _transition(client, world, planned, auth_headers)
    response = getattr(client, method)(
        path.format(team_id=world.team_a.id),
        json=payload,
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"


def test_operation_switches_to_new_season_teams(client, world, auth_headers):
    planned = _planned(world)
    target = _target_team(world, planned, "Future")
    _transition(client, world, planned, auth_headers)
    response = client.get("/api/teams", headers=auth_headers(world.owner_a))
    ids = {team["id"] for team in response.get_json()["teams"]}
    assert target.id in ids
    assert world.team_a.id not in ids


def test_end_to_end_owner_prepares_and_transitions_season(
    client, world, auth_headers
):
    world.team_a.name = "Sub-14"
    source_sub16 = Team(
        name="Sub-16",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=world.season_a,
    )
    db.session.add(source_sub16)
    db.session.flush()
    db.session.add(TeamPlayer(
        team=source_sub16,
        player=world.players_a[2],
        player_number=3,
        status="active",
    ))
    db.session.commit()

    created = _create_planned(client, world, auth_headers)
    target_season = db.session.get(Season, created.get_json()["season"]["id"])
    duplicated = client.post(
        f"/api/seasons/{target_season.id}/teams/duplicate",
        json={
            "source_season_id": world.season_a.id,
            "team_ids": [world.team_a.id, source_sub16.id],
        },
        headers=auth_headers(world.owner_a),
    )
    targets = {team["name"]: team["id"] for team in duplicated.get_json()["teams"]}

    ana = world.players_a[0]
    maria = world.players_a[1]
    laura = world.players_a[2]
    assert client.post(
        f"/api/teams/{targets['Sub-14']}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [ana.id]},
        headers=auth_headers(world.owner_a),
    ).status_code == 201
    assert client.post(
        f"/api/teams/{targets['Sub-16']}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [maria.id]},
        headers=auth_headers(world.owner_a),
    ).status_code == 201
    assert client.post(
        f"/api/teams/{targets['Sub-16']}/roster/copy",
        json={"source_team_id": source_sub16.id, "player_ids": [laura.id]},
        headers=auth_headers(world.owner_a),
    ).status_code == 201

    before = client.get("/api/teams", headers=auth_headers(world.owner_a))
    assert world.team_a.id in {team["id"] for team in before.get_json()["teams"]}
    assert target_season.status == "planned"

    transitioned = _transition(client, world, target_season, auth_headers)
    assert transitioned.status_code == 200
    assert db.session.get(Season, world.season_a.id).status == "closed"
    assert db.session.get(Season, target_season.id).status == "active"
    assert TeamPlayer.query.filter_by(team_id=world.team_a.id).count() == len(world.players_a)
    assert TeamPlayer.query.filter(
        TeamPlayer.team_id.in_(targets.values()),
        TeamPlayer.left_at.is_(None),
    ).count() == 3

    after = client.get("/api/teams", headers=auth_headers(world.owner_a))
    assert {team["id"] for team in after.get_json()["teams"]} == set(targets.values())

    dashboard = client.get(
        "/api/club/dashboard", headers=auth_headers(world.owner_a)
    )
    assert dashboard.status_code == 200
    assert dashboard.get_json()["stats"]["total_teams"] == 2
