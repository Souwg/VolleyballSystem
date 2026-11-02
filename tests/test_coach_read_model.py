import re
import uuid
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from src.api.coach_access import (
    PLAYER_FINANCE_FIELDS,
    PLAYER_SENSITIVE_FIELDS,
    SPORTS_MONEY_FIELDS,
    can_manage_team,
    get_team_access_resolver,
)
from src.api.finance_access import CLUB_FINANCE_FIELDS
from src.api.models import (
    MatchEvent,
    MatchPlayer,
    MatchSession,
    Player,
    PlayerPayment,
    Season,
    TeamPlayer,
    TournamentPlayer,
    TournamentTeam,
    TrainingSession,
    db,
)
from src.api.time_utils import get_club_today
from src.api.training_service import sync_training_roster
from tests.test_coach_team_enforcement import (
    TEAM_BOUND,
    _assign,
    _coach,
    _entry,
    _free_player,
    _send,
    _scope,
    _sports_state,
    _team,
    _tournament,
)


PAST = datetime(2026, 7, 1)


@pytest.fixture(autouse=True)
def onboarded_club(world):
    world.club_a.location = "Cancha principal"
    db.session.commit()


@pytest.fixture
def ctx(client, world, auth_headers, match_factory):
    return SimpleNamespace(
        client=client,
        world=world,
        auth_headers=auth_headers,
        match_factory=match_factory,
    )


def _keys(payload):
    if isinstance(payload, dict):
        found = set(payload)

        for value in payload.values():
            found |= _keys(value)

        return found

    if isinstance(payload, list):
        found = set()

        for value in payload:
            found |= _keys(value)

        return found

    return set()


def _season(world, status):
    season = Season(
        club=world.club_a,
        name=f"Temporada {status} {uuid.uuid4().hex[:6]}",
        start_date=date(2027, 1, 1),
        status=status,
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return season


def _team_in_state(world, state):
    if state == "active":
        return _team(world, f"Actual {uuid.uuid4().hex[:6]}")

    if state == "archived":
        team = _team(world, f"Archivado {uuid.uuid4().hex[:6]}")
        team.status = "archived"
        db.session.commit()
        return team

    return _team(
        world,
        f"Equipo {state} {uuid.uuid4().hex[:6]}",
        season=_season(world, state),
    )


def _sensitive_player(world, *teams):
    player = _free_player(world, f"Sensible {uuid.uuid4().hex[:6]}")
    player.birth_date = date(2010, 5, 20)
    player.representative_name = "Representante"
    player.representative_phone = "+58 412 0000000"
    player.enrollment_fee = 15
    player.monthly_fee = 30

    for number, team in enumerate(teams, start=30):
        db.session.add(TeamPlayer(
            team=team,
            player=player,
            player_number=number,
            status="active",
        ))

    db.session.commit()
    return player


def _player_views(client, headers, player, world):
    """Cada respuesta deportiva que serializa a la jugadora."""
    db.session.expire_all()
    views = {}

    rows = client.get("/api/players", headers=headers).get_json()["players"]
    views["list"] = next(row for row in rows if row["id"] == player.id)

    detail = client.get(f"/api/players/{player.id}/attendance", headers=headers)
    views["detail"] = detail.get_json()["player"]

    memberships = TeamPlayer.query.filter_by(player_id=player.id).all()

    for membership in memberships:
        performance = client.get(
            f"/api/players/{player.id}/performance",
            headers=headers,
            query_string={"season_id": membership.team.season_id},
        ).get_json()

        for row in performance["memberships"]:
            views[f"performance:{row['team_id']}"] = row["player"]

        roster = client.get(
            f"/api/teams/{membership.team_id}/players",
            headers=headers,
        ).get_json()["players"]
        views[f"team_roster:{membership.team_id}"] = next(
            row for row in roster if row["id"] == player.id
        )

    return views


def _assert_sensitive(views, visible):
    for name, view in views.items():
        fields = (
            ["birth_date"]
            if name.startswith("team_roster")
            else PLAYER_SENSITIVE_FIELDS
        )

        for field in fields:
            assert (field in view) is visible, (name, field)

    for name, view in views.items():
        if name.startswith("team_roster"):
            continue

        for field in PLAYER_FINANCE_FIELDS:
            assert field not in view, (name, field)


# =========================
# Datos sensibles de Player
# =========================


# (estados de las memberships abiertas, índices asignados, contacto visible)
SENSITIVE_CASES = {
    "assigned_current": (["active"], [0], True),
    "unassigned_current": (["active"], [], False),
    "assigned_planned": (["planned"], [0], True),
    "unassigned_planned": (["planned"], [], False),
    "no_membership": ([], [], True),
    "closed_only": (["closed"], [], True),
    "archived_only": (["archived"], [], True),
    "multi_assigned_and_unassigned": (["active", "active"], [0], True),
    "historical_assigned_current_unassigned": (["closed", "active"], [0], False),
    "archived_assigned_current_unassigned": (["archived", "active"], [0], False),
}


@pytest.mark.parametrize("case", sorted(SENSITIVE_CASES))
def test_scoped_coach_sees_contact_only_under_the_frozen_rule(
    client, world, auth_headers, case
):
    states, assigned, visible = SENSITIVE_CASES[case]
    teams = [_team_in_state(world, state) for state in states]
    player = _sensitive_player(world, *teams)

    for index in assigned:
        _assign(world, team=teams[index])

    _scope(world.club_a)
    views = _player_views(
        client, auth_headers(world.coach_a), player, world
    )

    _assert_sensitive(views, visible)
    assert views["detail"]["can_edit_profile"] is visible
    assert views["list"]["can_edit_profile"] is visible


def test_sports_profile_stays_visible_without_contact(
    client, world, auth_headers
):
    player = _sensitive_player(world, _team_in_state(world, "active"))
    _scope(world.club_a)

    view = _player_views(
        client, auth_headers(world.coach_a), player, world
    )["detail"]

    assert view["first_name"] == player.first_name
    assert view["last_name"] == player.last_name
    assert view["sex"] == player.sex
    assert view["main_position"] == player.main_position
    assert view["is_active"] is True


def test_removed_assignment_stops_contact_on_next_request(
    client, world, auth_headers
):
    team = _team_in_state(world, "active")
    player = _sensitive_player(world, team)
    _assign(world, team=team)
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)

    _assert_sensitive(_player_views(client, headers, player, world), True)

    assert client.delete(
        f"/api/teams/{team.id}/coaches/{world.coach_a.id}",
        headers=auth_headers(world.owner_a),
    ).status_code == 200

    _assert_sensitive(_player_views(client, headers, player, world), False)


def test_multi_team_contact_follows_each_coach(client, world, auth_headers):
    sub_16 = _team_in_state(world, "active")
    sub_18 = _team_in_state(world, "active")
    maria = _sensitive_player(world, sub_16, sub_18)
    pedro = _coach(world, "Pedro")
    andrea = _coach(world, "Andrea")
    carlos = _coach(world, "Carlos")
    _assign(world, coach=pedro, team=sub_16)
    _assign(world, coach=andrea, team=sub_18)
    _scope(world.club_a)

    for coach, visible in [(pedro, True), (andrea, True), (carlos, False)]:
        views = _player_views(client, auth_headers(coach), maria, world)
        _assert_sensitive(views, visible)
        assert views["detail"]["first_name"] == maria.first_name


def test_memberships_are_marked_per_team_for_multi_team_player(
    client, world, auth_headers
):
    assigned = _team_in_state(world, "active")
    other = _team_in_state(world, "active")
    closed = _team_in_state(world, "closed")
    player = _sensitive_player(world, assigned, other, closed)
    _assign(world, team=assigned)
    _scope(world.club_a)

    detail = client.get(
        f"/api/players/{player.id}/attendance",
        headers=auth_headers(world.coach_a),
    ).get_json()["player"]
    current = {row["id"]: row for row in detail["teams"]}
    historical = {row["id"]: row for row in detail["historical_teams"]}

    assert set(current) == {assigned.id, other.id}
    assert set(historical) == {closed.id}
    assert current[assigned.id]["is_assigned"] is True
    assert current[assigned.id]["can_manage"] is True
    assert current[assigned.id]["is_current"] is True
    assert current[other.id]["is_assigned"] is False
    assert current[other.id]["can_manage"] is False
    assert historical[closed.id]["is_current"] is False
    assert historical[closed.id]["season_status"] == "closed"
    assert historical[closed.id]["team_status"] == "active"


def test_legacy_scalar_team_id_does_not_decide_permissions(
    client, world, auth_headers
):
    unassigned = _team_in_state(world, "active")
    assigned = _team_in_state(world, "active")
    player = _sensitive_player(world, unassigned, assigned)
    memberships = {
        row.team_id: row
        for row in TeamPlayer.query.filter_by(player_id=player.id).all()
    }
    memberships[unassigned.id].joined_at = datetime(2026, 1, 1)
    memberships[assigned.id].joined_at = datetime(2026, 2, 1)
    db.session.commit()
    _assign(world, team=assigned)
    _scope(world.club_a)

    rows = client.get(
        "/api/players",
        headers=auth_headers(world.coach_a),
    ).get_json()["players"]
    row = next(item for item in rows if item["id"] == player.id)

    assert row["team_id"] == unassigned.id
    assert row["can_edit_profile"] is True
    assert "birth_date" in row
    teams = {team["id"]: team for team in row["teams"]}
    assert teams[assigned.id]["is_assigned"] is True
    assert teams[unassigned.id]["is_assigned"] is False


def test_club_wide_coach_keeps_contact_but_no_player_finance(
    client, world, auth_headers
):
    player = _sensitive_player(world, _team_in_state(world, "active"))

    views = _player_views(
        client, auth_headers(world.coach_a), player, world
    )

    _assert_sensitive(views, True)
    assert views["list"]["birth_date"] == "2010-05-20"
    assert views["detail"]["representative_phone"] == "+58 412 0000000"


def test_owner_keeps_full_player_data_in_every_mode(
    client, world, auth_headers
):
    player = _sensitive_player(world, _team_in_state(world, "active"))
    _scope(world.club_a)

    view = _player_views(
        client, auth_headers(world.owner_a), player, world
    )["detail"]

    assert view["monthly_fee"] == 30
    assert view["enrollment_fee"] == 15
    assert view["birth_date"] == "2010-05-20"
    assert view["representative_name"] == "Representante"


def test_staff_keeps_administrative_player_data_in_every_mode(
    client, world, auth_headers
):
    player = _sensitive_player(world, _team_in_state(world, "active"))
    _scope(world.club_a)

    rows = client.get(
        "/api/players",
        headers=auth_headers(world.staff_a),
    ).get_json()["players"]
    row = next(item for item in rows if item["id"] == player.id)

    assert row["monthly_fee"] == 30
    assert row["enrollment_fee"] == 15
    assert row["birth_date"] == "2010-05-20"
    assert row["representative_phone"] == "+58 412 0000000"


def test_tournament_roster_applies_player_policy(client, world, auth_headers):
    team = _team_in_state(world, "active")
    player = _sensitive_player(world, team)
    entry = _entry(world, team=team)
    db.session.add(TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=player.id,
        status="active",
    ))
    db.session.commit()
    _scope(world.club_a)
    url = f"/api/tournament-teams/{entry.id}/players"

    unassigned = client.get(url, headers=auth_headers(world.coach_a)).get_json()
    assert not _keys(unassigned) & set(PLAYER_SENSITIVE_FIELDS)
    assert not _keys(unassigned) & set(PLAYER_FINANCE_FIELDS)

    _assign(world, team=team)

    assigned = client.get(url, headers=auth_headers(world.coach_a)).get_json()
    row = next(
        item for item in assigned["players"]
        if item["player_id"] == player.id
    )
    assert row["player"]["representative_name"] == "Representante"
    assert not _keys(assigned) & set(PLAYER_FINANCE_FIELDS)


def test_team_roster_row_keeps_sports_fields_without_birth_date(
    client, world, auth_headers
):
    team = _team_in_state(world, "active")
    player = _sensitive_player(world, team)
    _scope(world.club_a)

    data = client.get(
        f"/api/teams/{team.id}/players",
        headers=auth_headers(world.coach_a),
    ).get_json()
    row = next(item for item in data["players"] if item["id"] == player.id)

    assert "birth_date" not in row
    assert row["first_name"] == player.first_name
    assert row["sex"] == player.sex
    assert row["main_position"] == player.main_position
    assert row["player_number"] == 30
    assert row["status"] == "active"


# =========================
# Finance en respuestas deportivas
# =========================


def _finance_scenario(world, match_factory):
    team = world.team_a
    created = match_factory(world)
    created.match.referee_fee = 25
    entry = _entry(world, team=team)
    entry.registration_fee = 500
    entry.tournament.default_referee_fee = 30
    db.session.add(TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=world.players_a[0].id,
        status="active",
    ))
    tournament_match = MatchSession(
        team=team,
        tournament_team_id=entry.id,
        date=date(2026, 8, 12),
        opponent_name="Rival torneo",
        match_type="official",
        referee_fee=40,
        created_by=world.owner_a.id,
    )
    db.session.add(tournament_match)
    db.session.commit()
    return team, created.match, tournament_match, entry


def _sports_read_urls(team, match, tournament_match, entry, player_id):
    return [
        "/api/matches",
        f"/api/matches/{match.id}",
        f"/api/matches/{tournament_match.id}",
        f"/api/matches/{match.id}/roster",
        f"/api/teams/{team.id}/matches",
        "/api/tournaments",
        f"/api/tournaments/{entry.tournament_id}",
        f"/api/tournaments/{entry.tournament_id}/teams",
        f"/api/tournament-teams/{entry.id}/players",
        f"/api/teams/{team.id}/tournament-entries",
        "/api/players",
        f"/api/players/{player_id}/attendance",
        f"/api/players/{player_id}/performance",
        f"/api/teams/{team.id}/players",
        "/api/club/dashboard",
    ]


@pytest.mark.parametrize("assigned", [False, True])
def test_scoped_coach_receives_no_money_in_sports_responses(
    client, world, auth_headers, match_factory, assigned
):
    urls = _sports_read_urls(
        *_finance_scenario(world, match_factory),
        world.players_a[0].id,
    )

    if assigned:
        _assign(world)

    _scope(world.club_a)
    headers = auth_headers(world.coach_a)

    for url in urls:
        response = client.get(url, headers=headers)
        assert response.status_code == 200, url
        leaked = _keys(response.get_json()) & (
            SPORTS_MONEY_FIELDS | set(PLAYER_FINANCE_FIELDS)
        )
        assert leaked == set(), url


def test_club_wide_coach_receives_no_money_in_sports_reads(
    client, world, auth_headers, match_factory
):
    team, match, tournament_match, entry = _finance_scenario(
        world, match_factory
    )
    headers = auth_headers(world.coach_a)

    for url in _sports_read_urls(
        team, match, tournament_match, entry, world.players_a[0].id
    ):
        leaked = _keys(client.get(url, headers=headers).get_json()) & (
            SPORTS_MONEY_FIELDS | set(PLAYER_FINANCE_FIELDS)
        )
        assert leaked == set(), url


def test_owner_keeps_money_in_sports_responses(
    client, world, auth_headers, match_factory
):
    team, match, tournament_match, entry = _finance_scenario(
        world, match_factory
    )
    _scope(world.club_a)
    headers = auth_headers(world.owner_a)

    assert client.get(
        f"/api/matches/{match.id}", headers=headers
    ).get_json()["match"]["referee_fee"] == 25
    data = client.get(
        f"/api/tournaments/{entry.tournament_id}", headers=headers
    ).get_json()["tournament"]
    assert data["default_referee_fee"] == 30
    assert data["teams"][0]["registration_fee"] == 500


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_mutation_responses_do_not_leak_finance_to_scoped_coach(ctx, mutation):
    request = TEAM_BOUND[mutation](ctx)
    _assign(ctx.world)
    _scope(ctx.world.club_a)

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert response.status_code in [200, 201], response.get_json()
    leaked = _keys(response.get_json()) & (
        SPORTS_MONEY_FIELDS | set(PLAYER_FINANCE_FIELDS)
    )
    assert leaked == set()


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_mutation_responses_do_not_leak_finance_to_club_wide_coach(
    ctx, mutation
):
    request = TEAM_BOUND[mutation](ctx)

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert response.status_code in [200, 201], response.get_json()
    assert _keys(response.get_json()) & (
        SPORTS_MONEY_FIELDS | set(PLAYER_FINANCE_FIELDS)
    ) == set()


def test_starting_lineup_response_applies_player_policy(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    world.players_a[0].monthly_fee = 30
    world.players_a[0].birth_date = date(2010, 5, 20)
    db.session.commit()

    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=auth_headers(world.coach_a),
        json={"players": [row.id for row in created.rows[:6]]},
    )

    assert response.status_code == 200
    assert _keys(response.get_json()) & set(PLAYER_FINANCE_FIELDS) == set()
    assert any(
        row["player"].get("birth_date") == "2010-05-20"
        for row in response.get_json()["players"]
    )


# =========================
# is_assigned / can_manage
# =========================


TEAM_ACCESS_CASES = {
    "owner": ("owner_a", "team_assigned", None, False, True),
    "club_wide_unassigned": ("coach_a", "club_wide", None, False, True),
    "club_wide_assigned": ("coach_a", "club_wide", "open", True, True),
    "scoped_assigned": ("coach_a", "team_assigned", "open", True, True),
    "scoped_unassigned": ("coach_a", "team_assigned", None, False, False),
    "scoped_removed": ("coach_a", "team_assigned", "removed", False, False),
    "staff": ("staff_a", "team_assigned", None, False, False),
}


def _apply_team_access_case(world, case):
    user_key, mode, assignment, is_assigned, can_manage = (
        TEAM_ACCESS_CASES[case]
    )

    if assignment == "open":
        _assign(world)
    elif assignment == "removed":
        _assign(world, removed_at=PAST)

    world.club_a.coach_access_mode = mode
    db.session.commit()
    return getattr(world, user_key), is_assigned, can_manage


@pytest.mark.parametrize("case", sorted(TEAM_ACCESS_CASES))
def test_team_list_and_detail_expose_access_metadata(
    client, world, auth_headers, case
):
    user, is_assigned, can_manage = _apply_team_access_case(world, case)
    headers = auth_headers(user)

    listed = next(
        team
        for team in client.get("/api/teams", headers=headers).get_json()["teams"]
        if team["id"] == world.team_a.id
    )
    detail = client.get(
        f"/api/teams/{world.team_a.id}", headers=headers
    ).get_json()["team"]
    category = client.get(
        f"/api/categories/{world.team_a.category_id}", headers=headers
    ).get_json()["teams"][0]
    category_teams = client.get(
        f"/api/categories/{world.team_a.category_id}/teams", headers=headers
    ).get_json()["teams"][0]

    for view in [listed, detail, category, category_teams]:
        assert view["is_assigned"] is is_assigned
        assert view["can_manage"] is can_manage

    assert detail["season_status"] == "active"
    assert can_manage_team(user, world.team_a) is can_manage


@pytest.mark.parametrize(
    "case",
    [case for case in sorted(TEAM_ACCESS_CASES) if case != "staff"],
)
def test_activity_reads_expose_can_manage(
    client, world, auth_headers, match_factory, case
):
    training = TrainingSession(
        team=world.team_a,
        date=date(2026, 8, 10),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    match = match_factory(world).match
    entry = _entry(world)
    db.session.commit()
    user, is_assigned, can_manage = _apply_team_access_case(world, case)
    headers = auth_headers(user)
    team_id = world.team_a.id

    def get(url):
        response = client.get(url, headers=headers)
        assert response.status_code == 200, url
        return response.get_json()

    assert get(f"/api/trainings/{training.id}")["training"]["can_manage"] is can_manage
    assert get("/api/trainings")["trainings"][0]["can_manage"] is can_manage
    team_trainings = get(f"/api/teams/{team_id}/trainings")
    assert team_trainings["trainings"][0]["can_manage"] is can_manage
    assert team_trainings["team"]["is_assigned"] is is_assigned
    assert get(f"/api/matches/{match.id}")["match"]["can_manage"] is can_manage
    assert get("/api/matches")["matches"][0]["can_manage"] is can_manage
    team_matches = get(f"/api/teams/{team_id}/matches")
    assert team_matches["matches"][0]["can_manage"] is can_manage
    assert team_matches["team"]["can_manage"] is can_manage
    assert get(f"/api/teams/{team_id}/players")["team"]["is_assigned"] is is_assigned

    tournament_id = entry.tournament_id

    for view in [
        get("/api/tournaments")["tournaments"][0]["teams"][0],
        get(f"/api/tournaments/{tournament_id}")["tournament"]["teams"][0],
        get(f"/api/tournaments/{tournament_id}/teams")["teams"][0],
        get(f"/api/tournament-teams/{entry.id}/players")["tournament_team"],
        get(f"/api/teams/{team_id}/tournament-entries")["tournament_entries"][0],
    ]:
        assert view["is_assigned"] is is_assigned
        assert view["can_manage"] is can_manage


def test_tournament_entity_metadata_reflects_owner_only_rule(
    client, world, auth_headers
):
    tournament = _tournament(world)
    _assign(world)
    url = f"/api/tournaments/{tournament.id}"

    assert client.get(
        url, headers=auth_headers(world.coach_a)
    ).get_json()["tournament"]["can_manage"] is True

    _scope(world.club_a)

    assert client.get(
        url, headers=auth_headers(world.coach_a)
    ).get_json()["tournament"]["can_manage"] is False
    assert client.get(
        url, headers=auth_headers(world.owner_a)
    ).get_json()["tournament"]["can_manage"] is True


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        ("archived", "TEAM_ARCHIVED"),
        ("closed", "SEASON_CLOSED"),
        ("planned", "ACTIVE_SEASON_REQUIRED"),
    ],
)
def test_can_manage_is_scoping_not_lifecycle(
    client, world, auth_headers, state, expected_code
):
    team = _team_in_state(world, state)
    _assign(world, team=team)
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)

    detail = client.get(f"/api/teams/{team.id}", headers=headers)
    mutation = client.post(
        "/api/trainings",
        headers=headers,
        json={
            "team_id": team.id,
            "date": "2026-08-10",
            "start_time": "17:00",
            "end_time": "19:00",
            "location": "Cancha",
        },
    )

    assert detail.status_code == 200
    assert detail.get_json()["team"]["is_assigned"] is True
    assert detail.get_json()["team"]["can_manage"] is True
    assert mutation.status_code == 409
    assert mutation.get_json()["code"] == expected_code


def test_access_resolver_matches_enforcement_helper(world):
    assigned = _team_in_state(world, "active")
    other = _team_in_state(world, "active")
    _assign(world, team=assigned)
    users = [
        world.owner_a,
        world.coach_a,
        world.staff_a,
        world.system_admin,
        world.coach_b,
        world.owner_b,
    ]

    for mode in ["club_wide", "team_assigned"]:
        world.club_a.coach_access_mode = mode
        db.session.commit()

        for user in users:
            resolve = get_team_access_resolver(user)

            for team in [assigned, other, world.team_b]:
                assert resolve(team)["can_manage"] is can_manage_team(
                    user, team
                )


# =========================
# Lecturas históricas y tenant
# =========================


def test_scoped_unassigned_coach_reads_closed_season_history(
    client, world, auth_headers
):
    closed = _season(world, "closed")
    team = _team(world, "Histórico", season=closed)
    training = TrainingSession(
        team=team,
        date=date(2025, 3, 1),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha",
        status="completed",
        created_by=world.owner_a.id,
    )
    match = MatchSession(
        team=team,
        date=date(2025, 3, 2),
        opponent_name="Rival",
        match_type="official",
        is_completed=True,
        created_by=world.owner_a.id,
    )
    db.session.add_all([training, match])
    db.session.commit()
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)
    params = {"season_id": closed.id}

    teams = client.get("/api/teams", headers=headers, query_string=params)
    trainings = client.get("/api/trainings", headers=headers, query_string=params)
    matches = client.get("/api/matches", headers=headers, query_string=params)

    assert [row["id"] for row in teams.get_json()["teams"]] == [team.id]
    assert [row["id"] for row in trainings.get_json()["trainings"]] == [training.id]
    assert [row["id"] for row in matches.get_json()["matches"]] == [match.id]
    assert client.get(
        f"/api/trainings/{training.id}", headers=headers
    ).status_code == 200
    assert client.get(
        f"/api/matches/{match.id}", headers=headers
    ).status_code == 200


def test_cross_tenant_reads_expose_no_metadata_or_contact(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    entry = _entry(world)
    player = world.players_a[0]
    player.birth_date = date(2010, 5, 20)
    db.session.commit()
    _scope(world.club_b)
    headers = auth_headers(world.coach_b)

    for url in [
        f"/api/teams/{world.team_a.id}",
        f"/api/teams/{world.team_a.id}/players",
        f"/api/teams/{world.team_a.id}/matches",
        f"/api/teams/{world.team_a.id}/trainings",
        f"/api/matches/{created.match.id}",
        f"/api/matches/{created.match.id}/roster",
        f"/api/tournaments/{entry.tournament_id}",
        f"/api/tournament-teams/{entry.id}/players",
        f"/api/players/{player.id}/attendance",
        f"/api/players/{player.id}/performance",
    ]:
        response = client.get(url, headers=headers)
        assert response.status_code in [403, 404], url
        assert not _keys(response.get_json()) & {
            "is_assigned",
            "can_manage",
            "birth_date",
            "representative_name",
        }, url

    listed = client.get("/api/players", headers=headers).get_json()["players"]
    assert player.id not in {row["id"] for row in listed}


# =========================
# GET read-only
# =========================


@pytest.fixture
def sql_writes(app):
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if re.match(r"\s*(INSERT|UPDATE|DELETE)\b", statement, re.I):
            statements.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", record)
    yield statements
    event.remove(engine, "before_cursor_execute", record)


def _read_world(world, match_factory):
    team = world.team_a
    player = world.players_a[0]
    training = TrainingSession(
        team=team,
        date=date(2026, 8, 10),
        start_time=time(17, 0),
        end_time=time(19, 0),
        location="Cancha",
        status="scheduled",
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    db.session.flush()
    sync_training_roster(training)
    created = match_factory(world)
    open_match = MatchSession(
        team=team,
        date=date(2026, 8, 11),
        opponent_name="Sin snapshot",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(open_match)
    entry = _entry(world)
    payment = PlayerPayment(
        club_id=world.club_a.id,
        player_id=player.id,
        payment_type="monthly",
        amount=10,
        currency_code="USD",
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()
    return {
        "team_id": team.id,
        "target_team_id": team.id,
        "player_id": player.id,
        "training_id": training.id,
        "match_id": open_match.id,
        "match_player_id": created.rows[0].id,
        "tournament_id": entry.tournament_id,
        "tournament_team_id": entry.id,
        "category_id": team.category_id,
        "season_id": world.season_a.id,
        "target_season_id": world.season_a.id,
        "user_id": world.coach_a.id,
        "payment_id": payment.id,
        "country_id": str(uuid.uuid4()),
        "receipt_id": str(uuid.uuid4()),
        "token": uuid.uuid4().hex,
    }


def _get_routes(app):
    return sorted(
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/")
        and "GET" in rule.methods
        and rule.endpoint != "api_not_found"
    )


@pytest.mark.parametrize(
    "user_key",
    ["owner_a", "coach_scoped", "coach_assigned", "coach_a", "staff_a"],
)
def test_no_get_route_of_the_api_writes_to_the_database(
    client, world, auth_headers, match_factory, app, sql_writes, user_key
):
    identifiers = _read_world(world, match_factory)
    routes = _get_routes(app)
    assert len(routes) > 30

    if user_key in ["coach_scoped", "coach_assigned"]:
        _scope(world.club_a)

    if user_key == "coach_assigned":
        _assign(world)

    user = getattr(world, "coach_a" if "coach" in user_key else user_key)
    headers = auth_headers(user)
    forbidden = set()

    if "coach" in user_key:
        forbidden |= (
            set(PLAYER_FINANCE_FIELDS)
            | SPORTS_MONEY_FIELDS
            | set(CLUB_FINANCE_FIELDS)
        )

    # Todas las jugadoras de este mundo están en un Team que no le asignamos.
    if user_key == "coach_scoped":
        forbidden |= set(PLAYER_SENSITIVE_FIELDS)

    before = _sports_state()
    sql_writes.clear()

    for rule in routes:
        names = re.findall(r"<(?:[^:>]+:)?([^>]+)>", rule)
        missing = [name for name in names if name not in identifiers]
        # Una ruta GET nueva debe añadir su identificador en _read_world.
        assert missing == [], rule
        url = re.sub(
            r"<(?:[^:>]+:)?([^>]+)>",
            lambda found: identifiers[found.group(1)],
            rule,
        )

        response = client.get(url, headers=headers)

        assert response.status_code < 500, url
        assert sql_writes == [], url
        assert _keys(response.get_json(silent=True)) & forbidden == set(), url

    assert _sports_state() == before


# =========================
# GET roster
# =========================


def _match_without_snapshot(world, **fields):
    match = MatchSession(
        team=world.team_a,
        date=date(2026, 8, 11),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
        **fields,
    )
    db.session.add(match)
    db.session.commit()
    return match


def _roster(client, auth_headers, user, match):
    response = client.get(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(user),
    )
    assert response.status_code == 200
    return response.get_json()


def _new_member(world, number=70, status="active"):
    player = _free_player(world, f"Nueva {uuid.uuid4().hex[:6]}")
    db.session.add(TeamPlayer(
        team=world.team_a,
        player=player,
        player_number=number,
        status=status,
    ))
    db.session.commit()
    return player


def test_roster_without_snapshot_is_derived_and_not_persisted(
    client, world, auth_headers
):
    match = _match_without_snapshot(world)

    data = _roster(client, auth_headers, world.owner_a, match)

    assert data["roster_source"] == "derived"
    assert data["synced_count"] == 0
    assert {row["player_id"] for row in data["players"]} == {
        player.id for player in world.players_a
    }
    assert all(row["match_player_id"] is None for row in data["players"])
    assert all(row["is_called"] is False for row in data["players"])
    assert [row["player_number"] for row in data["players"]] == sorted(
        row["player_number"] for row in data["players"]
    )
    db.session.expire_all()
    assert MatchPlayer.query.filter_by(match_id=match.id).count() == 0


def test_roster_with_saved_callup_uses_frozen_snapshot(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    created.match.match_step = 1
    db.session.commit()
    newcomer = _new_member(world)

    data = _roster(client, auth_headers, world.owner_a, created.match)

    assert data["roster_source"] == "snapshot"
    assert {row["match_player_id"] for row in data["players"]} == {
        row.id for row in created.rows
    }
    assert newcomer.id not in {row["player_id"] for row in data["players"]}


def test_finalized_match_is_never_rebuilt_from_current_roster(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, is_completed=True, called=True)
    original_ids = {row.id for row in created.rows}
    newcomer = _new_member(world)
    left = TeamPlayer.query.filter_by(
        player_id=world.players_a[0].id,
        team_id=world.team_a.id,
    ).one()
    left.left_at = PAST
    db.session.commit()

    data = _roster(client, auth_headers, world.owner_a, created.match)

    assert data["roster_source"] == "snapshot"
    assert {row["match_player_id"] for row in data["players"]} == original_ids
    assert newcomer.id not in {row["player_id"] for row in data["players"]}
    assert world.players_a[0].id in {
        row["player_id"] for row in data["players"]
    }


def test_finalized_match_without_snapshot_shows_no_current_roster(
    client, world, auth_headers
):
    match = _match_without_snapshot(world, is_completed=True)

    data = _roster(client, auth_headers, world.owner_a, match)

    assert data["roster_source"] == "snapshot"
    assert data["players"] == []


@pytest.mark.parametrize("state", ["archived", "closed"])
def test_non_operational_match_only_shows_persisted_snapshot(
    client, world, auth_headers, match_factory, state
):
    created = match_factory(world, called=False)
    original_ids = {row.id for row in created.rows}
    newcomer = _new_member(world)

    if state == "archived":
        world.team_a.status = "archived"
    else:
        world.season_a.status = "closed"

    db.session.commit()

    data = _roster(client, auth_headers, world.owner_a, created.match)

    assert data["roster_source"] == "snapshot"
    assert {row["match_player_id"] for row in data["players"]} == original_ids
    assert newcomer.id not in {row["player_id"] for row in data["players"]}


def test_open_roster_shows_what_saving_would_reconcile_without_writing(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, called=False)
    rows = {row.player_id: row for row in created.rows}
    newcomer = _new_member(world)
    injured = TeamPlayer.query.filter_by(
        player_id=world.players_a[0].id,
        team_id=world.team_a.id,
    ).one()
    injured.status = "injured"
    renumbered = TeamPlayer.query.filter_by(
        player_id=world.players_a[1].id,
        team_id=world.team_a.id,
    ).one()
    renumbered.player_number = 88
    db.session.commit()
    before = _sports_state()

    data = _roster(client, auth_headers, world.owner_a, created.match)
    view = {row["player_id"]: row for row in data["players"]}

    assert data["roster_source"] == "derived"
    assert world.players_a[0].id not in view
    assert view[world.players_a[1].id]["player_number"] == 88
    assert (
        view[world.players_a[1].id]["match_player_id"]
        == rows[world.players_a[1].id].id
    )
    assert view[newcomer.id]["match_player_id"] is None
    assert _sports_state() == before


def test_open_roster_keeps_row_with_history_of_ineligible_player(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    injured = TeamPlayer.query.filter_by(
        player_id=world.players_a[0].id,
        team_id=world.team_a.id,
    ).one()
    injured.status = "injured"
    db.session.commit()

    data = _roster(client, auth_headers, world.owner_a, created.match)

    assert world.players_a[0].id in {
        row["player_id"] for row in data["players"]
    }


def test_tournament_match_derives_only_registered_players(
    client, world, auth_headers
):
    entry = _entry(world)
    db.session.add(TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=world.players_a[0].id,
        status="active",
    ))
    db.session.commit()
    match = _match_without_snapshot(world, tournament_team_id=entry.id)

    data = _roster(client, auth_headers, world.owner_a, match)

    assert [row["player_id"] for row in data["players"]] == [
        world.players_a[0].id
    ]


def test_roster_view_is_the_same_for_scoped_coach_without_assignment(
    client, world, auth_headers
):
    match = _match_without_snapshot(world)
    owner_view = _roster(client, auth_headers, world.owner_a, match)
    _scope(world.club_a)

    coach_view = _roster(client, auth_headers, world.coach_a, match)

    assert coach_view == owner_view
    assert MatchPlayer.query.filter_by(match_id=match.id).count() == 0


# =========================
# POST roster reconcilia
# =========================


def _post_roster(client, auth_headers, user, match, player_ids):
    return client.post(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(user),
        json={"players": [{"player_id": pid} for pid in player_ids]},
    )


def test_post_roster_persists_players_seen_only_in_derived_view(
    client, world, auth_headers
):
    match = _match_without_snapshot(world)
    player_ids = [
        row["player_id"]
        for row in _roster(
            client, auth_headers, world.owner_a, match
        )["players"]
    ][:6]

    response = _post_roster(
        client, auth_headers, world.coach_a, match, player_ids
    )

    assert response.status_code == 200
    db.session.expire_all()
    rows = MatchPlayer.query.filter_by(match_id=match.id).all()
    assert len(rows) == len(world.players_a)
    assert {row.player_id for row in rows if row.is_called} == set(player_ids)
    assert db.session.get(MatchSession, match.id).match_step == 1

    data = _roster(client, auth_headers, world.owner_a, match)
    assert data["roster_source"] == "snapshot"
    assert all(row["match_player_id"] for row in data["players"])


def test_post_roster_adds_newcomer_and_reconciles_open_snapshot(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, called=False)
    newcomer = _new_member(world, number=71)
    injured = TeamPlayer.query.filter_by(
        player_id=world.players_a[0].id,
        team_id=world.team_a.id,
    ).one()
    injured.status = "injured"
    db.session.commit()

    response = _post_roster(
        client, auth_headers, world.owner_a, created.match, [newcomer.id]
    )

    assert response.status_code == 200
    db.session.expire_all()
    rows = {
        row.player_id: row
        for row in MatchPlayer.query.filter_by(match_id=created.match.id).all()
    }
    assert rows[newcomer.id].is_called is True
    assert rows[newcomer.id].player_number == 71
    assert world.players_a[0].id not in rows


def test_rejected_post_roster_does_not_persist_reconciliation(
    client, world, auth_headers
):
    match = _match_without_snapshot(world)
    before = _sports_state()

    response = _post_roster(
        client, auth_headers, world.owner_a, match, [str(uuid.uuid4())]
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_MATCH_ROSTER"
    assert _sports_state() == before


def test_post_roster_history_lock_rolls_back_reconciliation(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, on_court_count=1)
    newcomer = _new_member(world, number=72)
    db.session.add(MatchEvent(
        match_id=created.match.id,
        match_player_id=created.rows[0].id,
        action_type="attack",
        result="positive",
        set_number=1,
    ))
    db.session.commit()
    before = _sports_state()

    response = _post_roster(
        client,
        auth_headers,
        world.owner_a,
        created.match,
        [created.rows[1].player_id],
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_HISTORY_LOCKED"
    assert _sports_state() == before
    assert MatchPlayer.query.filter_by(
        match_id=created.match.id,
        player_id=newcomer.id,
    ).first() is None


def test_post_roster_does_not_touch_frozen_snapshot(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    created.match.match_step = 1
    db.session.commit()
    newcomer = _new_member(world, number=73)

    response = _post_roster(
        client, auth_headers, world.owner_a, created.match, [newcomer.id]
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_MATCH_ROSTER"
    assert MatchPlayer.query.filter_by(
        match_id=created.match.id,
        player_id=newcomer.id,
    ).first() is None


# =========================
# Dashboard
# =========================


@pytest.fixture
def dashboard_world(world):
    today = get_club_today(world.club_a)
    future = today + timedelta(days=3)
    other_team = _team(world, "Otro equipo")
    other_player = _free_player(world, "De otro equipo")
    shared_team = _team(world, "Segundo asignable")
    db.session.add(TeamPlayer(
        team=other_team,
        player=other_player,
        player_number=1,
        status="active",
    ))
    db.session.add(TeamPlayer(
        team=shared_team,
        player=world.players_a[0],
        player_number=50,
        status="active",
    ))

    def training(team, when):
        row = TrainingSession(
            team=team,
            date=when,
            start_time=time(17, 0),
            end_time=time(19, 0),
            location="Cancha",
            status="scheduled",
            created_by=world.owner_a.id,
        )
        db.session.add(row)
        db.session.flush()
        sync_training_roster(row)
        return row

    def match(team, when):
        row = MatchSession(
            team=team,
            date=when,
            opponent_name=f"Rival {team.name}",
            match_type="official",
            created_by=world.owner_a.id,
        )
        db.session.add(row)
        db.session.flush()
        return row

    own_training = training(world.team_a, today)
    own_future_training = training(world.team_a, future)
    other_training = training(other_team, today)
    own_match = match(world.team_a, future)
    other_match = match(other_team, today)
    finished = match(other_team, today - timedelta(days=5))
    finished.is_completed = True
    own_entry = TournamentTeam(
        tournament=_tournament(world),
        team=world.team_a,
        status="active",
        registration_fee=0,
    )
    other_entry = TournamentTeam(
        tournament=_tournament(world),
        team=other_team,
        status="active",
        registration_fee=0,
    )
    db.session.add_all([own_entry, other_entry])
    db.session.commit()

    return SimpleNamespace(
        today=today,
        other_team=other_team,
        other_player=other_player,
        shared_team=shared_team,
        own_training=own_training,
        own_future_training=own_future_training,
        other_training=other_training,
        own_match=own_match,
        other_match=other_match,
        finished=finished,
        own_tournament_id=own_entry.tournament_id,
        other_tournament_id=other_entry.tournament_id,
    )


def _dashboard(client, auth_headers, user):
    response = client.get("/api/club/dashboard", headers=auth_headers(user))
    assert response.status_code == 200
    return response.get_json()


def _agenda_ids(data, key):
    return {row["id"] for row in data["sections"]["agenda"][key]}


def test_scoped_coach_dashboard_only_counts_assigned_teams(
    client, world, auth_headers, dashboard_world
):
    scenario = dashboard_world
    _assign(world)
    _scope(world.club_a)

    data = _dashboard(client, auth_headers, world.coach_a)
    sections = data["sections"]

    assert data["has_team_assignments"] is True
    assert _agenda_ids(data, "upcoming_trainings") == {
        scenario.own_training.id,
        scenario.own_future_training.id,
    }
    assert _agenda_ids(data, "upcoming_matches") == {scenario.own_match.id}
    assert _agenda_ids(data, "open_matches") == set()
    assert sections["today"]["trainings_today_count"] == 1
    assert sections["today"]["matches_today_count"] == 0
    assert sections["today"]["open_matches_count"] == 0
    assert sections["players_without_team"]["count"] == 0
    assert sections["players_without_team"]["players"] == []
    assert sections["empty_teams"]["count"] == 0
    assert {row["tournament_id"] for row in sections["active_tournaments"]} == {
        scenario.own_tournament_id
    }
    assert sections["last_official_match"] is None
    assert data["stats"]["total_teams"] == 1
    assert data["stats"]["total_players"] == len(world.players_a)
    assert data["stats"]["total_trainings"] == 2
    assert data["next_match"]["id"] == scenario.own_match.id


def test_scoped_dashboard_counts_shared_player_once_across_assigned_teams(
    client, world, auth_headers, dashboard_world
):
    _assign(world)
    _assign(world, team=dashboard_world.shared_team)
    _scope(world.club_a)

    data = _dashboard(client, auth_headers, world.coach_a)

    assert data["stats"]["total_teams"] == 2
    assert data["stats"]["total_players"] == len(world.players_a)
    assert data["stats"]["total_categories"] == 1


def test_scoped_dashboard_lists_empty_assigned_team_only(
    client, world, auth_headers, dashboard_world
):
    empty_assigned = _team(world, "Vacío asignado")
    _team(world, "Vacío ajeno")
    _assign(world, team=empty_assigned)
    _scope(world.club_a)

    sections = _dashboard(client, auth_headers, world.coach_a)["sections"]

    assert [row["team_id"] for row in sections["empty_teams"]["teams"]] == [
        empty_assigned.id
    ]


def test_scoped_coach_without_assignments_gets_valid_empty_dashboard(
    client, world, auth_headers, dashboard_world
):
    _scope(world.club_a)

    data = _dashboard(client, auth_headers, world.coach_a)
    sections = data["sections"]
    agenda = sections["agenda"]

    assert data["has_team_assignments"] is False
    assert agenda["upcoming_trainings"] == []
    assert agenda["upcoming_matches"] == []
    assert agenda["open_matches"] == []
    assert agenda["live_match"] is None
    assert agenda["pending_attendance"] == {"count": 0, "trainings": []}
    assert sections["today"] == {
        "trainings_today_count": 0,
        "matches_today_count": 0,
        "pending_attendance_count": 0,
        "open_matches_count": 0,
    }
    assert sections["players_without_team"]["count"] == 0
    assert sections["empty_teams"]["count"] == 0
    assert sections["active_tournaments"] == []
    assert sections["last_official_match"] is None
    assert data["next_match"] is None
    assert data["stats"]["total_teams"] == 0
    assert data["stats"]["total_players"] == 0
    assert data["stats"]["total_categories"] == 0
    assert data["stats"]["total_trainings"] == 0
    assert data["stats"]["active_players_percentage"] == 0


def test_removed_assignment_leaves_next_dashboard_without_login(
    client, world, auth_headers, dashboard_world
):
    _assign(world)
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)

    first = client.get("/api/club/dashboard", headers=headers).get_json()
    assert first["stats"]["total_teams"] == 1

    assert client.delete(
        f"/api/teams/{world.team_a.id}/coaches/{world.coach_a.id}",
        headers=auth_headers(world.owner_a),
    ).status_code == 200

    second = client.get("/api/club/dashboard", headers=headers).get_json()
    assert second["has_team_assignments"] is False
    assert second["stats"]["total_teams"] == 0
    assert second["sections"]["agenda"]["upcoming_trainings"] == []


@pytest.mark.parametrize("state", ["archived", "closed", "planned"])
def test_non_operational_assignment_does_not_enter_dashboard(
    client, world, auth_headers, dashboard_world, state
):
    team = _team_in_state(world, state)
    _assign(world, team=team)
    _scope(world.club_a)

    data = _dashboard(client, auth_headers, world.coach_a)

    assert data["has_team_assignments"] is False
    assert data["stats"]["total_teams"] == 0
    assert data["sections"]["empty_teams"]["count"] == 0


def test_club_wide_coach_dashboard_stays_global_without_flag(
    client, world, auth_headers, dashboard_world
):
    scenario = dashboard_world
    _assign(world, team=scenario.other_team, removed_at=PAST)

    data = _dashboard(client, auth_headers, world.coach_a)

    assert "has_team_assignments" not in data
    assert scenario.other_training.id in _agenda_ids(data, "upcoming_trainings")
    assert scenario.other_match.id in _agenda_ids(data, "upcoming_matches")
    assert data["stats"]["total_teams"] == 3
    assert data["stats"]["total_players"] == Player.query.filter_by(
        club_id=world.club_a.id
    ).count()
    assert data["sections"]["last_official_match"]["match_id"] == (
        scenario.finished.id
    )


def test_owner_dashboard_is_global_and_unaffected_by_mode(
    client, world, auth_headers, dashboard_world
):
    club_wide = _dashboard(client, auth_headers, world.owner_a)
    _assign(world)
    _scope(world.club_a)
    scoped = _dashboard(client, auth_headers, world.owner_a)

    for data in [club_wide, scoped]:
        data.pop("as_of")
        data["club"].pop("coach_access_mode")

    assert "has_team_assignments" not in scoped
    assert scoped == club_wide
    assert scoped["stats"]["total_teams"] == 3
    assert "finance" in scoped["sections"]


def test_staff_dashboard_is_unaffected_by_mode_or_assignment_row(
    client, world, auth_headers, dashboard_world
):
    club_wide = _dashboard(client, auth_headers, world.staff_a)
    _assign(world, coach=world.staff_a)
    _scope(world.club_a)
    scoped = _dashboard(client, auth_headers, world.staff_a)

    for data in [club_wide, scoped]:
        data.pop("as_of")
        data["club"].pop("coach_access_mode")

    assert "has_team_assignments" not in scoped
    assert scoped == club_wide
    assert "finance" in scoped["sections"]
    assert "agenda" not in scoped["sections"]


def test_scoped_dashboard_exposes_no_finance(
    client, world, auth_headers, dashboard_world
):
    dashboard_world.own_match.referee_fee = 25
    db.session.commit()
    _assign(world)
    _scope(world.club_a)

    data = _dashboard(client, auth_headers, world.coach_a)

    assert "finance" not in data["sections"]
    assert "recent_payments" not in data["sections"]
    assert not _keys(data) & (
        SPORTS_MONEY_FIELDS
        | set(PLAYER_FINANCE_FIELDS)
        | {
            "default_enrollment_fee",
            "default_monthly_fee",
            "paid_today_amount",
        }
    )
