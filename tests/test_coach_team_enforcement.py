import io
import re
import uuid
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from src.api.models import (
    Attendance,
    MatchEvent,
    MatchPlayer,
    MatchSession,
    MatchSubstitution,
    Player,
    PlayerMatchStat,
    PlayerPayment,
    Season,
    Team,
    TeamCoachAssignment,
    TeamPlayer,
    Tournament,
    TournamentPlayer,
    TournamentTeam,
    TrainingAuditEvent,
    TrainingPlayer,
    TrainingSession,
    User,
    db,
)
from tests.test_archived_team_activity_guard import (
    CORRECTION_REASON,
    MATCH_MUTATIONS,
    TRAINING_MUTATIONS,
    _match_for_mutation,
    _match_request,
    _send,
    _training,
)


TRAINING_PAYLOAD = {
    "date": "2026-08-10",
    "start_time": "17:00",
    "end_time": "19:00",
    "location": "Cancha principal",
}


@pytest.fixture(autouse=True)
def onboarded_club(world):
    world.club_a.location = "Cancha principal"
    db.session.commit()


def _scope(club):
    club.coach_access_mode = "team_assigned"
    db.session.commit()


def _assign(world, coach=None, team=None, removed_at=None, club=None):
    assignment = TeamCoachAssignment(
        club_id=(club or world.club_a).id,
        team_id=(team or world.team_a).id,
        user_id=(coach or world.coach_a).id,
        assigned_by=world.owner_a.id,
        removed_at=removed_at,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


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


def _coach(world, suffix):
    coach = User(
        id=str(uuid.uuid4()),
        full_name=f"Coach {suffix}",
        email=f"coach-{suffix.lower()}-{uuid.uuid4().hex[:6]}@example.com",
        password="unused",
        role="coach",
        first_login=False,
        is_active=True,
        session_version=0,
        club=world.club_a,
    )
    db.session.add(coach)
    db.session.commit()
    return coach


def _free_player(world, suffix="Libre"):
    player = Player(
        first_name="Nueva",
        last_name=suffix,
        sex="female",
        main_position="setter",
        is_active=True,
        club=world.club_a,
    )
    db.session.add(player)
    db.session.commit()
    return player


def _membership(world, player=None, team=None):
    return TeamPlayer.query.filter_by(
        team_id=(team or world.team_a).id,
        player_id=(player or world.players_a[0]).id,
        left_at=None,
    ).one()


def _tournament(world):
    tournament = Tournament(
        club=world.club_a,
        season=world.season_a,
        name=f"Torneo {uuid.uuid4().hex[:6]}",
        start_date=date(2026, 8, 20),
        status="active",
        created_by=world.owner_a.id,
    )
    db.session.add(tournament)
    db.session.commit()
    return tournament


def _entry(world, team=None):
    entry = TournamentTeam(
        tournament=_tournament(world),
        team=team or world.team_a,
        status="active",
        registration_fee=0,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def _charge(world, entry=None, match=None, payment_type="tournament"):
    charge = PlayerPayment(
        club_id=world.club_a.id,
        player_id=world.players_a[0].id,
        tournament_team_id=entry.id if entry else None,
        match_id=match.id if match else None,
        payment_type=payment_type,
        amount=10,
        currency_code="USD",
        status="pending",
    )
    db.session.add(charge)
    db.session.commit()
    return charge


def _sports_state():
    db.session.expire_all()

    def rows(model, *columns):
        return sorted(
            tuple(str(getattr(row, column)) for column in columns)
            for row in model.query.all()
        )

    return {
        "players": rows(
            Player, "id", "first_name", "last_name", "image_url", "is_active"
        ),
        "memberships": rows(
            TeamPlayer, "id", "player_number", "status", "left_at"
        ),
        "trainings": rows(
            TrainingSession, "id", "status", "date", "location"
        ),
        "training_players": rows(TrainingPlayer, "training_id", "player_id"),
        "attendance": rows(Attendance, "session_id", "player_id", "status"),
        "training_audit": rows(TrainingAuditEvent, "id"),
        "matches": rows(
            MatchSession,
            "id",
            "is_completed",
            "home_sets",
            "opponent_sets",
            "capture_mode",
            "match_step",
        ),
        "match_players": rows(
            MatchPlayer,
            "id",
            "is_called",
            "attendance_status",
            "did_play",
            "is_on_court",
            "position",
        ),
        "events": rows(MatchEvent, "id"),
        "substitutions": rows(MatchSubstitution, "id"),
        "stats": rows(PlayerMatchStat, "id"),
        "tournaments": rows(Tournament, "id", "name", "status"),
        "entries": rows(TournamentTeam, "id", "team_id", "registration_fee"),
        "registrations": rows(TournamentPlayer, "id", "player_id", "status"),
        "charges": rows(PlayerPayment, "id", "status", "amount"),
    }


def _training_request(mutation):
    def build(ctx):
        return TRAINING_MUTATIONS[mutation](_training(ctx.world), ctx.world)

    return build


def _match_mutation_request(mutation):
    def build(ctx):
        created = _match_for_mutation(ctx.world, ctx.match_factory, mutation)
        return _match_request(
            ctx.client, ctx.world, ctx.auth_headers, created, mutation
        )

    return build


def _create_training(ctx):
    return (
        "post",
        "/api/trainings",
        {"team_id": ctx.world.team_a.id, **TRAINING_PAYLOAD},
    )


def _reactivate_training(ctx):
    training = _training(ctx.world, status="cancelled")
    return (
        "post",
        f"/api/trainings/{training.id}/reactivate",
        {"reason": CORRECTION_REASON},
    )


def _correct_metadata(ctx):
    training = _training(ctx.world, status="completed")
    return (
        "post",
        f"/api/trainings/{training.id}/corrections/metadata",
        {
            "reason": CORRECTION_REASON,
            "changes": {"location": "Sede corregida"},
        },
    )


def _correct_attendance(ctx):
    training = _training(ctx.world, status="completed")
    player_id = ctx.world.players_a[0].id
    db.session.add(Attendance(
        session_id=training.id,
        player_id=player_id,
        status="absent",
    ))
    db.session.commit()
    return (
        "post",
        f"/api/trainings/{training.id}/corrections/attendance",
        {
            "reason": CORRECTION_REASON,
            "attendance": [{"player_id": player_id, "status": "present"}],
        },
    )


def _create_match(ctx):
    return (
        "post",
        "/api/matches",
        {
            "team_id": ctx.world.team_a.id,
            "date": "2026-08-11",
            "opponent_name": "Rival",
            "match_type": "official",
        },
    )


def _create_player_with_team(ctx):
    return (
        "post",
        "/api/players",
        {
            "first_name": "Nueva",
            "last_name": "Con equipo",
            "sex": "female",
            "team_id": ctx.world.team_a.id,
            "player_number": 70,
        },
    )


def _add_existing_player(ctx):
    player = _free_player(ctx.world)
    return (
        "post",
        f"/api/teams/{ctx.world.team_a.id}/players/existing",
        {"player_id": player.id, "player_number": 71},
    )


def _remove_player(ctx):
    return (
        "delete",
        f"/api/teams/{ctx.world.team_a.id}/players/{ctx.world.players_a[0].id}",
        None,
    )


def _update_number(ctx):
    player = ctx.world.players_a[0]
    return (
        "put",
        f"/api/players/{player.id}",
        {
            "first_name": player.first_name,
            "last_name": player.last_name,
            "sex": "female",
            "main_position": "setter",
            "team_id": ctx.world.team_a.id,
            "player_number": 72,
        },
    )


def _update_status(ctx):
    return (
        "put",
        f"/api/players/{ctx.world.players_a[0].id}/status",
        {"team_id": ctx.world.team_a.id, "status": "injured"},
    )


def _add_team_to_tournament(ctx):
    return (
        "post",
        f"/api/tournaments/{_tournament(ctx.world).id}/teams",
        {"team_id": ctx.world.team_a.id, "registration_fee": 0},
    )


def _tournament_players(ctx):
    return (
        "put",
        f"/api/tournament-teams/{_entry(ctx.world).id}/players",
        {"player_ids": [ctx.world.players_a[0].id]},
    )


TEAM_BOUND = {
    "training_create": _create_training,
    "training_update": _training_request("update"),
    "training_complete": _training_request("complete"),
    "training_cancel": _training_request("cancel"),
    "training_sync_roster": _training_request("sync_roster"),
    "training_reactivate": _reactivate_training,
    "attendance_save": _training_request("attendance"),
    "correction_metadata": _correct_metadata,
    "correction_attendance": _correct_attendance,
    "match_create": _create_match,
    **{
        f"match_{mutation}": _match_mutation_request(mutation)
        for mutation in MATCH_MUTATIONS
    },
    "player_create_with_team": _create_player_with_team,
    "player_add_existing": _add_existing_player,
    "player_remove": _remove_player,
    "player_update_number": _update_number,
    "player_update_status": _update_status,
    "tournament_add_team": _add_team_to_tournament,
    "tournament_players": _tournament_players,
}


@pytest.fixture
def ctx(client, world, auth_headers, match_factory):
    return SimpleNamespace(
        client=client,
        world=world,
        auth_headers=auth_headers,
        match_factory=match_factory,
    )


def _prepare(ctx, mutation):
    return TEAM_BOUND[mutation](ctx)


# =========================
# Matriz rol / modo / asignación
# =========================


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_assigned_coach_can_mutate_team(ctx, mutation):
    request = _prepare(ctx, mutation)
    _assign(ctx.world)
    _scope(ctx.world.club_a)

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert response.status_code in [200, 201], response.get_json()


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_unassigned_coach_is_rejected_without_side_effects(ctx, mutation):
    request = _prepare(ctx, mutation)
    _assign(ctx.world, team=_team(ctx.world, "Otro equipo"))
    _scope(ctx.world.club_a)
    before = _sports_state()

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert _sports_state() == before


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_removed_assignment_grants_no_mutation(ctx, mutation):
    request = _prepare(ctx, mutation)
    _assign(ctx.world, removed_at=datetime(2026, 7, 1))
    _scope(ctx.world.club_a)
    before = _sports_state()

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert _sports_state() == before


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_club_wide_coach_keeps_legacy_access_without_assignment(ctx, mutation):
    request = _prepare(ctx, mutation)

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert ctx.world.club_a.coach_access_mode == "club_wide"
    assert response.status_code in [200, 201], response.get_json()


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_club_wide_coach_ignores_partial_and_removed_assignments(ctx, mutation):
    request = _prepare(ctx, mutation)
    _assign(ctx.world, removed_at=datetime(2026, 7, 1))
    _assign(ctx.world, team=_team(ctx.world, "Otro equipo"))

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_a), request)

    assert response.status_code in [200, 201], response.get_json()


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_owner_is_not_limited_by_assignments(ctx, mutation):
    request = _prepare(ctx, mutation)
    _scope(ctx.world.club_a)

    response = _send(ctx.client, ctx.auth_headers(ctx.world.owner_a), request)

    assert response.status_code in [200, 201], response.get_json()


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_staff_stays_forbidden_even_with_assignment_row(ctx, mutation):
    request = _prepare(ctx, mutation)
    _assign(ctx.world, coach=ctx.world.staff_a)
    _scope(ctx.world.club_a)
    before = _sports_state()

    response = _send(ctx.client, ctx.auth_headers(ctx.world.staff_a), request)

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"
    assert _sports_state() == before


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_system_admin_gets_no_sports_mutation(ctx, mutation):
    request = _prepare(ctx, mutation)
    before = _sports_state()

    response = _send(
        ctx.client, ctx.auth_headers(ctx.world.system_admin), request
    )

    assert response.status_code in [400, 403, 404]
    assert response.get_json().get("code") != "TEAM_NOT_ASSIGNED"
    assert _sports_state() == before


@pytest.mark.parametrize("mutation", sorted(TEAM_BOUND))
def test_cross_tenant_keeps_tenant_response_not_assignment_error(ctx, mutation):
    request = _prepare(ctx, mutation)
    _scope(ctx.world.club_a)
    _scope(ctx.world.club_b)
    _assign(
        ctx.world,
        coach=ctx.world.coach_b,
        team=ctx.world.team_b,
        club=ctx.world.club_b,
    )
    before = _sports_state()

    response = _send(ctx.client, ctx.auth_headers(ctx.world.coach_b), request)

    assert response.status_code in [403, 404]
    assert response.get_json()["code"] != "TEAM_NOT_ASSIGNED"
    assert _sports_state() == before


def test_assignment_removal_takes_effect_on_next_request_with_same_token(
    client, world, auth_headers
):
    _assign(world)
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)
    payload = {"team_id": world.team_a.id, **TRAINING_PAYLOAD}

    assert client.post(
        "/api/trainings", headers=headers, json=payload
    ).status_code == 201
    assert client.delete(
        f"/api/teams/{world.team_a.id}/coaches/{world.coach_a.id}",
        headers=auth_headers(world.owner_a),
    ).status_code == 200

    response = client.post("/api/trainings", headers=headers, json=payload)

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"


def test_coach_changed_to_staff_loses_access_but_keeps_assignment(
    client, world, auth_headers
):
    coach = _coach(world, "Cambio")
    assignment = _assign(world, coach=coach)
    _scope(world.club_a)
    coach.role = "staff"
    db.session.commit()

    response = client.post(
        "/api/trainings",
        headers=auth_headers(coach),
        json={"team_id": world.team_a.id, **TRAINING_PAYLOAD},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None


def test_deactivated_assigned_coach_is_blocked_by_auth(
    client, world, auth_headers
):
    coach = _coach(world, "Inactivo")
    assignment = _assign(world, coach=coach)
    _scope(world.club_a)
    headers = auth_headers(coach)
    coach.is_active = False
    db.session.commit()

    response = client.post(
        "/api/trainings",
        headers=headers,
        json={"team_id": world.team_a.id, **TRAINING_PAYLOAD},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "ACCOUNT_DISABLED"
    assert db.session.get(TeamCoachAssignment, assignment.id).removed_at is None


# =========================
# Player global
# =========================


def _profile_payload(player, **extra):
    return {
        "first_name": "Editada",
        "last_name": player.last_name,
        "sex": "female",
        "main_position": "setter",
        **extra,
    }


def _put_profile(client, auth_headers, user, player, **extra):
    return client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(user),
        json=_profile_payload(player, **extra),
    )


def test_scoped_coach_can_create_player_without_team(
    client, world, auth_headers
):
    _scope(world.club_a)

    response = client.post(
        "/api/players",
        headers=auth_headers(world.coach_a),
        json={
            "first_name": "Sin",
            "last_name": "Equipo",
            "sex": "female",
        },
    )

    assert response.status_code == 201
    created = db.session.get(Player, response.get_json()["player"]["id"])
    assert TeamPlayer.query.filter_by(player_id=created.id).count() == 0


def test_rejected_player_creation_with_team_creates_no_player(
    client, world, auth_headers
):
    _scope(world.club_a)
    players_before = Player.query.count()

    response = client.post(
        "/api/players",
        headers=auth_headers(world.coach_a),
        json={
            "first_name": "Nueva",
            "last_name": "Rechazada",
            "sex": "female",
            "team_id": world.team_a.id,
            "player_number": 80,
        },
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert Player.query.count() == players_before


def test_profile_edit_allowed_with_assigned_open_membership(
    client, world, auth_headers
):
    _assign(world)
    _scope(world.club_a)

    response = _put_profile(
        client, auth_headers, world.coach_a, world.players_a[0]
    )

    assert response.status_code == 200
    assert db.session.get(Player, world.players_a[0].id).first_name == "Editada"


def test_profile_edit_allowed_for_player_without_open_membership(
    client, world, auth_headers
):
    _scope(world.club_a)
    free = _free_player(world)
    closed = _membership(world, player=world.players_a[1])
    closed.left_at = datetime(2026, 7, 1)
    db.session.commit()

    for player in [free, world.players_a[1]]:
        response = _put_profile(client, auth_headers, world.coach_a, player)
        assert response.status_code == 200


def test_profile_edit_rejected_when_only_unassigned_open_memberships(
    client, world, auth_headers
):
    _assign(world, team=_team(world, "Otro equipo"))
    _scope(world.club_a)
    before = _sports_state()

    response = _put_profile(
        client, auth_headers, world.coach_a, world.players_a[0]
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert _sports_state() == before


def test_profile_edit_rejected_after_assignment_removed(
    client, world, auth_headers
):
    _assign(world, removed_at=datetime(2026, 7, 1))
    _scope(world.club_a)

    response = _put_profile(
        client, auth_headers, world.coach_a, world.players_a[0]
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"


def test_club_wide_coach_and_owner_edit_any_profile(
    client, world, auth_headers
):
    assert _put_profile(
        client, auth_headers, world.coach_a, world.players_a[0]
    ).status_code == 200

    _scope(world.club_a)

    assert _put_profile(
        client, auth_headers, world.owner_a, world.players_a[1]
    ).status_code == 200


def test_profile_edit_cross_tenant_stays_not_found(
    client, world, auth_headers
):
    _scope(world.club_b)

    response = _put_profile(
        client, auth_headers, world.coach_b, world.players_a[0]
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "PLAYER_NOT_FOUND"


@pytest.fixture
def saved_files(monkeypatch):
    saved = []
    monkeypatch.setattr(
        FileStorage,
        "save",
        lambda self, destination, *args, **kwargs: saved.append(destination),
    )
    return saved


def _upload(client, auth_headers, user, player):
    return client.post(
        f"/api/players/{player.id}/upload-image",
        headers=auth_headers(user),
        data={"image": (io.BytesIO(b"imagen"), "foto.png")},
        content_type="multipart/form-data",
    )


@pytest.mark.parametrize(
    ("setup", "expected_status"),
    [
        ("assigned", 201),
        ("no_membership", 201),
        ("unassigned", 403),
        ("removed", 403),
    ],
)
def test_scoped_image_upload_follows_profile_rule(
    client, world, auth_headers, saved_files, setup, expected_status
):
    player = world.players_a[0]

    if setup == "assigned":
        _assign(world)
    elif setup == "no_membership":
        player = _free_player(world)
    elif setup == "removed":
        _assign(world, removed_at=datetime(2026, 7, 1))

    _scope(world.club_a)
    image_before = player.image_url

    response = _upload(client, auth_headers, world.coach_a, player)

    assert response.status_code == expected_status

    if expected_status == 403:
        assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
        assert saved_files == []
        assert db.session.get(Player, player.id).image_url == image_before
    else:
        assert len(saved_files) == 1


def test_image_upload_unchanged_for_club_wide_coach_and_owner(
    client, world, auth_headers, saved_files
):
    assert _upload(
        client, auth_headers, world.coach_a, world.players_a[0]
    ).status_code == 201

    _scope(world.club_a)

    assert _upload(
        client, auth_headers, world.owner_a, world.players_a[0]
    ).status_code == 201


# =========================
# Membership relevante para el perfil global
# =========================


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


def _player_in(world, *teams):
    player = _free_player(world, f"Vínculo {uuid.uuid4().hex[:6]}")

    for number, team in enumerate(teams, start=30):
        db.session.add(TeamPlayer(
            team=team,
            player=player,
            player_number=number,
            status="active",
        ))

    db.session.commit()
    return player


# (estados de las memberships abiertas, índices asignados al Coach, permitido)
PROFILE_RELEVANCE_CASES = {
    "closed_only": (["closed"], [], True),
    "archived_only": (["archived"], [], True),
    "closed_only_with_historical_assignment": (["closed"], [0], True),
    "archived_only_with_historical_assignment": (["archived"], [0], True),
    "active_assigned": (["active"], [0], True),
    "active_unassigned": (["active"], [], False),
    "planned_assigned": (["planned"], [0], True),
    "planned_unassigned": (["planned"], [], False),
    "closed_plus_current_assigned": (["closed", "active"], [1], True),
    "historical_assigned_plus_current_unassigned": (
        ["closed", "active"],
        [0],
        False,
    ),
    "archived_assigned_plus_current_unassigned": (
        ["archived", "active"],
        [0],
        False,
    ),
    "historical_assigned_plus_planned_unassigned": (
        ["closed", "planned"],
        [0],
        False,
    ),
}


@pytest.mark.parametrize("channel", ["profile", "image"])
@pytest.mark.parametrize("case", sorted(PROFILE_RELEVANCE_CASES))
def test_only_current_or_future_membership_decides_global_profile_access(
    client, world, auth_headers, saved_files, case, channel
):
    states, assigned_indexes, allowed = PROFILE_RELEVANCE_CASES[case]
    teams = [_team_in_state(world, state) for state in states]
    player = _player_in(world, *teams)

    for index in assigned_indexes:
        _assign(world, team=teams[index])

    _scope(world.club_a)
    memberships_before = sorted(
        (row.id, str(row.left_at))
        for row in TeamPlayer.query.filter_by(player_id=player.id).all()
    )

    if channel == "profile":
        response = _put_profile(client, auth_headers, world.coach_a, player)
    else:
        response = _upload(client, auth_headers, world.coach_a, player)

    if allowed:
        assert response.status_code in [200, 201], response.get_json()
    else:
        assert response.status_code == 403
        assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
        assert saved_files == []

    db.session.expire_all()
    assert sorted(
        (row.id, str(row.left_at))
        for row in TeamPlayer.query.filter_by(player_id=player.id).all()
    ) == memberships_before


def test_assigned_coach_of_planned_team_edits_profile_but_cannot_operate(
    client, world, auth_headers
):
    team = _team_in_state(world, "planned")
    player = _player_in(world, team)
    _assign(world, team=team)
    _scope(world.club_a)

    profile = _put_profile(client, auth_headers, world.coach_a, player)
    training = _post_training(client, auth_headers, world.coach_a, team)
    status = _status(
        client, auth_headers, world.coach_a, player, team, "injured"
    )

    assert profile.status_code == 200
    assert training.status_code == 409
    assert training.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"
    assert status.status_code == 403
    assert status.get_json()["code"] == "FORBIDDEN"


def test_relevant_membership_rule_keeps_removed_assignment_rejected(
    client, world, auth_headers
):
    team = _team_in_state(world, "active")
    player = _player_in(world, team)
    _assign(world, team=team, removed_at=datetime(2026, 7, 1))
    _scope(world.club_a)

    response = _put_profile(client, auth_headers, world.coach_a, player)

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"


# =========================
# Multi-Team
# =========================


@pytest.fixture
def maria(world):
    sub_18 = _team(world, "Sub-18")
    player = world.players_a[0]
    sub_18_membership = TeamPlayer(
        team=sub_18,
        player=player,
        player_number=40,
        status="active",
    )
    db.session.add(sub_18_membership)
    db.session.commit()
    pedro = _coach(world, "Pedro")
    andrea = _coach(world, "Andrea")
    _assign(world, coach=pedro, team=world.team_a)
    _assign(world, coach=andrea, team=sub_18)
    _scope(world.club_a)
    return SimpleNamespace(
        player=player,
        sub_16=world.team_a,
        sub_18=sub_18,
        pedro=pedro,
        andrea=andrea,
    )


def _status(client, auth_headers, user, player, team, status):
    return client.put(
        f"/api/players/{player.id}/status",
        headers=auth_headers(user),
        json={"team_id": team.id, "status": status},
    )


def test_multi_team_status_only_changes_membership_of_assigned_team(
    client, world, auth_headers, maria
):
    own = _status(
        client, auth_headers, maria.pedro, maria.player, maria.sub_16, "injured"
    )
    other = _status(
        client, auth_headers, maria.pedro, maria.player, maria.sub_18, "inactive"
    )
    andrea_own = _status(
        client, auth_headers, maria.andrea, maria.player, maria.sub_18, "inactive"
    )
    andrea_other = _status(
        client, auth_headers, maria.andrea, maria.player, maria.sub_16, "active"
    )

    assert own.status_code == 200
    assert other.status_code == 403
    assert other.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert andrea_own.status_code == 200
    assert andrea_other.status_code == 403
    assert _membership(world, team=maria.sub_16).status == "injured"
    assert _membership(world, team=maria.sub_18).status == "inactive"


@pytest.mark.parametrize("coach_key", ["pedro", "andrea"])
def test_multi_team_activities_follow_each_coach_assignment(
    client, world, auth_headers, match_factory, maria, coach_key
):
    coach = getattr(maria, coach_key)
    own, other = (
        (maria.sub_16, maria.sub_18)
        if coach_key == "pedro"
        else (maria.sub_18, maria.sub_16)
    )
    headers = auth_headers(coach)

    def create_training(team):
        return client.post(
            "/api/trainings",
            headers=headers,
            json={"team_id": team.id, **TRAINING_PAYLOAD},
        )

    def create_match(team):
        return client.post(
            "/api/matches",
            headers=headers,
            json={
                "team_id": team.id,
                "date": "2026-08-11",
                "opponent_name": "Rival",
                "match_type": "official",
            },
        )

    assert create_training(own).status_code == 201
    assert create_match(own).status_code == 201

    for response in [create_training(other), create_match(other)]:
        assert response.status_code == 403
        assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"


@pytest.mark.parametrize("coach_key", ["pedro", "andrea"])
def test_one_assigned_membership_is_enough_to_edit_global_profile(
    client, auth_headers, maria, coach_key
):
    response = _put_profile(
        client, auth_headers, getattr(maria, coach_key), maria.player
    )

    assert response.status_code == 200


def test_multi_team_number_change_requires_that_team_assignment(
    client, world, auth_headers, maria
):
    before = _sports_state()

    other_team = _put_profile(
        client,
        auth_headers,
        maria.pedro,
        maria.player,
        team_id=maria.sub_18.id,
        player_number=55,
    )

    assert other_team.status_code == 403
    assert other_team.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert _sports_state() == before

    own_team = _put_profile(
        client,
        auth_headers,
        maria.pedro,
        maria.player,
        team_id=maria.sub_16.id,
        player_number=55,
    )

    assert own_team.status_code == 200
    assert _membership(world, team=maria.sub_16).player_number == 55
    assert _membership(world, team=maria.sub_18).player_number == 40


# =========================
# GET roster
# =========================


def _open_match(world):
    match = MatchSession(
        team=world.team_a,
        date=date(2026, 8, 11),
        opponent_name="Rival",
        match_type="official",
        created_by=world.owner_a.id,
    )
    db.session.add(match)
    db.session.commit()
    return match


def _get_roster(client, auth_headers, user, match):
    return client.get(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(user),
    )


@pytest.mark.parametrize("assignment", ["none", "removed"])
def test_unassigned_coach_get_roster_reads_without_writing(
    client, world, auth_headers, assignment
):
    match = _open_match(world)

    if assignment == "removed":
        _assign(world, removed_at=datetime(2026, 7, 1))

    _scope(world.club_a)

    response = _get_roster(client, auth_headers, world.coach_a, match)

    assert response.status_code == 200
    assert response.get_json()["synced_count"] == 0
    db.session.expire_all()
    assert MatchPlayer.query.filter_by(match_id=match.id).count() == 0


@pytest.mark.parametrize("case", ["assigned", "club_wide", "owner"])
def test_get_roster_keeps_sync_for_who_can_manage_team(
    client, world, auth_headers, case
):
    match = _open_match(world)
    user = world.coach_a

    if case == "assigned":
        _assign(world)
        _scope(world.club_a)
    elif case == "owner":
        _scope(world.club_a)
        user = world.owner_a

    response = _get_roster(client, auth_headers, user, match)

    assert response.status_code == 200
    assert MatchPlayer.query.filter_by(match_id=match.id).count() == len(
        world.players_a
    )


# =========================
# Tournament
# =========================


def _tournament_entity_requests(world):
    tournament = _tournament(world)
    base = f"/api/tournaments/{tournament.id}"
    return {
        "create": (
            "post",
            "/api/tournaments",
            {"name": f"Nuevo {uuid.uuid4().hex[:6]}", "start_date": "2026-09-01"},
        ),
        "update": (
            "put",
            base,
            {"name": f"Editado {uuid.uuid4().hex[:6]}", "start_date": "2026-09-01"},
        ),
        "complete": ("put", f"{base}/complete", None),
        "cancel": ("put", f"{base}/cancel", None),
    }


TOURNAMENT_ENTITY_ACTIONS = ["create", "update", "complete", "cancel"]


@pytest.mark.parametrize("assigned", [False, True])
@pytest.mark.parametrize("action", TOURNAMENT_ENTITY_ACTIONS)
def test_scoped_coach_cannot_mutate_tournament_entity(
    client, world, auth_headers, action, assigned
):
    request = _tournament_entity_requests(world)[action]

    if assigned:
        _assign(world)

    _scope(world.club_a)
    before = _sports_state()

    response = _send(client, auth_headers(world.coach_a), request)

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"
    assert _sports_state() == before


@pytest.mark.parametrize("action", TOURNAMENT_ENTITY_ACTIONS)
def test_owner_and_club_wide_coach_keep_tournament_entity_access(
    client, world, auth_headers, action
):
    club_wide = _send(
        client,
        auth_headers(world.coach_a),
        _tournament_entity_requests(world)[action],
    )
    _scope(world.club_a)
    owner = _send(
        client,
        auth_headers(world.owner_a),
        _tournament_entity_requests(world)[action],
    )

    assert club_wide.status_code in [200, 201], club_wide.get_json()
    assert owner.status_code in [200, 201], owner.get_json()


def test_scoped_tournament_entity_cross_tenant_stays_forbidden(
    client, world, auth_headers
):
    request = _tournament_entity_requests(world)["cancel"]
    _scope(world.club_b)

    response = _send(client, auth_headers(world.coach_b), request)

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"


def test_assigned_coach_keeps_tournament_player_availability_rules(
    client, world, auth_headers
):
    entry = _entry(world)
    injured = _membership(world, player=world.players_a[1])
    injured.status = "injured"
    db.session.commit()
    _assign(world)
    _scope(world.club_a)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [world.players_a[1].id]},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT"


# =========================
# Finance: el guard actúa antes de los efectos financieros
# =========================


def test_unassigned_coach_cannot_delete_tournament_charge_by_withdrawing(
    client, world, auth_headers
):
    entry = _entry(world)
    db.session.add(TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=world.players_a[0].id,
        status="active",
    ))
    charge = _charge(world, entry=entry)
    charge_id = charge.id
    _scope(world.club_a)
    before = _sports_state()

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": []},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert db.session.get(PlayerPayment, charge_id) is not None
    assert _sports_state() == before


def test_unassigned_coach_cannot_delete_referee_charge_by_changing_roster(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    charge = _charge(world, match=created.match, payment_type="referee")
    charge_id = charge.id
    _scope(world.club_a)
    before = _sports_state()

    response = client.post(
        f"/api/matches/{created.match.id}/roster",
        headers=auth_headers(world.coach_a),
        json={"players": [{"player_id": created.rows[1].player_id}]},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
    assert db.session.get(PlayerPayment, charge_id) is not None
    assert _sports_state() == before


# =========================
# Lecturas sin filtrar
# =========================


def test_unassigned_coach_keeps_general_sports_reads(
    client, world, auth_headers, match_factory
):
    training = _training(world)
    created = match_factory(world)
    entry = _entry(world)
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)
    player_id = world.players_a[0].id

    for url in [
        "/api/teams",
        f"/api/teams/{world.team_a.id}",
        f"/api/teams/{world.team_a.id}/players",
        "/api/players",
        f"/api/players/{player_id}/attendance",
        f"/api/players/{player_id}/performance",
        "/api/categories",
        "/api/seasons",
        "/api/trainings",
        f"/api/trainings/{training.id}",
        f"/api/trainings/{training.id}/attendance",
        "/api/matches",
        f"/api/matches/{created.match.id}",
        "/api/tournaments",
        f"/api/tournament-teams/{entry.id}/players",
        "/api/club/dashboard",
    ]:
        assert client.get(url, headers=headers).status_code == 200, url


# =========================
# Lifecycle y precedencia
# =========================


def _planned_team(world):
    season = Season(
        club=world.club_a,
        name="Próxima temporada",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return _team(world, "Planificado", season=season)


def _post_training(client, auth_headers, user, team):
    return client.post(
        "/api/trainings",
        headers=auth_headers(user),
        json={"team_id": team.id, **TRAINING_PAYLOAD},
    )


def test_precedence_unassigned_active_team(client, world, auth_headers):
    _scope(world.club_a)

    response = _post_training(
        client, auth_headers, world.coach_a, world.team_a
    )

    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"


def test_precedence_assigned_archived_team(client, world, auth_headers):
    _assign(world)
    _scope(world.club_a)
    world.team_a.status = "archived"
    db.session.commit()

    response = _post_training(
        client, auth_headers, world.coach_a, world.team_a
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"


def test_precedence_assigned_closed_season(client, world, auth_headers):
    _assign(world)
    _scope(world.club_a)
    world.season_a.status = "closed"
    db.session.commit()

    response = _post_training(
        client, auth_headers, world.coach_a, world.team_a
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_CLOSED"


def test_precedence_assigned_planned_season(client, world, auth_headers):
    team = _planned_team(world)
    _assign(world, team=team)
    _scope(world.club_a)

    response = _post_training(client, auth_headers, world.coach_a, team)

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACTIVE_SEASON_REQUIRED"


@pytest.mark.parametrize("state", ["archived", "closed", "planned"])
def test_precedence_unassigned_wins_over_lifecycle(
    client, world, auth_headers, state
):
    team = world.team_a

    if state == "archived":
        team.status = "archived"
    elif state == "closed":
        world.season_a.status = "closed"
    else:
        team = _planned_team(world)

    _scope(world.club_a)
    db.session.commit()

    response = _post_training(client, auth_headers, world.coach_a, team)

    assert response.status_code == 403
    assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"


def test_precedence_assigned_coach_on_planned_roster_keeps_owner_only_rule(
    client, world, auth_headers
):
    team = _planned_team(world)
    player = _free_player(world)
    _assign(world, team=team)
    _scope(world.club_a)

    response = client.post(
        f"/api/teams/{team.id}/players/existing",
        headers=auth_headers(world.coach_a),
        json={"player_id": player.id, "player_number": 9},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"


def test_precedence_assigned_match_mutation_on_archived_and_closed(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    _assign(world)
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)
    url = f"/api/matches/{created.match.id}/result"
    payload = {"home_sets": 3, "opponent_sets": 1}

    world.team_a.status = "archived"
    db.session.commit()
    archived = client.put(url, headers=headers, json=payload)

    world.team_a.status = "active"
    world.season_a.status = "closed"
    db.session.commit()
    closed = client.put(url, headers=headers, json=payload)

    assert archived.get_json()["code"] == "TEAM_ARCHIVED"
    assert closed.get_json()["code"] == "SEASON_CLOSED"


@pytest.mark.parametrize("closure", ["team_archived", "season_closed"])
@pytest.mark.parametrize(
    ("case", "expected_status"),
    [
        ("assigned", 200),
        ("unassigned", 403),
        ("removed", 403),
        ("owner", 200),
    ],
)
def test_historical_corrections_require_open_assignment(
    client, world, auth_headers, closure, case, expected_status
):
    training = _training(world, status="completed")
    user = world.coach_a

    if case == "assigned":
        _assign(world)
    elif case == "removed":
        _assign(world, removed_at=datetime(2026, 7, 1))
    elif case == "owner":
        user = world.owner_a

    _scope(world.club_a)

    if closure == "team_archived":
        world.team_a.status = "archived"
    else:
        world.season_a.status = "closed"

    db.session.commit()
    audit_before = TrainingAuditEvent.query.count()

    response = client.post(
        f"/api/trainings/{training.id}/corrections/metadata",
        headers=auth_headers(user),
        json={
            "reason": CORRECTION_REASON,
            "changes": {"location": "Sede corregida"},
        },
    )

    assert response.status_code == expected_status

    if expected_status == 403:
        assert response.get_json()["code"] == "TEAM_NOT_ASSIGNED"
        assert TrainingAuditEvent.query.count() == audit_before
    else:
        assert TrainingAuditEvent.query.count() == audit_before + 1


# =========================
# Inventario de mutaciones
# =========================


COACH_TEAM_BOUND_ROUTES = {
    ("POST", "/api/trainings"),
    ("PUT", "/api/trainings/<string:training_id>"),
    ("PUT", "/api/trainings/<string:training_id>/complete"),
    ("PUT", "/api/trainings/<string:training_id>/cancel"),
    ("POST", "/api/trainings/<string:training_id>/reactivate"),
    ("PUT", "/api/trainings/<string:training_id>/sync-roster"),
    ("POST", "/api/trainings/<string:training_id>/attendance"),
    ("POST", "/api/trainings/<string:training_id>/corrections/metadata"),
    ("POST", "/api/trainings/<string:training_id>/corrections/attendance"),
    ("POST", "/api/matches"),
    ("POST", "/api/matches/<string:match_id>/roster"),
    ("PUT", "/api/matches/<string:match_id>/roster/status"),
    ("PUT", "/api/matches/<string:match_id>/roster/participation"),
    ("PUT", "/api/matches/<string:match_id>/capture-mode"),
    ("PUT", "/api/matches/<string:match_id>/starting-lineup"),
    ("POST", "/api/matches/<string:match_id>/substitutions"),
    ("PUT", "/api/matches/<string:match_id>/result"),
    ("PUT", "/api/matches/<string:match_id>/finalize"),
    ("POST", "/api/match-events"),
    ("DELETE", "/api/match-events/<string:event_id>"),
    ("POST", "/api/match-players/<string:match_player_id>/stats"),
    ("POST", "/api/players"),
    ("PUT", "/api/players/<string:player_id>"),
    ("PUT", "/api/players/<string:player_id>/status"),
    ("POST", "/api/players/<string:player_id>/upload-image"),
    ("POST", "/api/teams/<string:team_id>/players/existing"),
    ("DELETE", "/api/teams/<string:team_id>/players/<string:player_id>"),
    ("POST", "/api/tournaments/<string:tournament_id>/teams"),
    ("PUT", "/api/tournament-teams/<string:tournament_team_id>/players"),
}

COACH_ENTITY_ROUTES = {
    ("POST", "/api/tournaments"),
    ("PUT", "/api/tournaments/<string:tournament_id>"),
    ("PUT", "/api/tournaments/<string:tournament_id>/complete"),
    ("PUT", "/api/tournaments/<string:tournament_id>/cancel"),
}

ACCOUNT_ROUTES = {
    ("POST", "/api/login"),
    ("POST", "/api/logout"),
    ("POST", "/api/refresh"),
    ("POST", "/api/auth/forgot-password"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/set-password"),
}


def _mutating_routes(app):
    routes = set()

    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/") or rule.endpoint == "api_not_found":
            continue

        for method in rule.methods - {"GET", "HEAD", "OPTIONS"}:
            routes.add((method, rule.rule))

    return routes


def test_every_coach_route_is_classified_and_the_rest_reject_coach(
    client, world, auth_headers, match_factory, app
):
    routes = _mutating_routes(app)
    classified = COACH_TEAM_BOUND_ROUTES | COACH_ENTITY_ROUTES

    assert classified <= routes
    # Esta ruta busca el partido antes de comprobar el rol.
    match_id = match_factory(world).match.id
    _scope(world.club_a)
    headers = auth_headers(world.coach_a)
    accepted = []

    for method, rule in sorted(routes - classified - ACCOUNT_ROUTES):
        path_id = match_id if rule.endswith("/referee-charges") and "/matches/" in rule else str(uuid.uuid4())
        url = re.sub(r"<[^>]+>", path_id, rule)
        response = getattr(client, method.lower())(url, headers=headers, json={})

        if response.status_code != 403:
            accepted.append((method, rule, response.status_code))

    # Una ruta mutante nueva que admita Coach debe clasificarse arriba y
    # cubrirse con el guard de asignación.
    assert accepted == []
