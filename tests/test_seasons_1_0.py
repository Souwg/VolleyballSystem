from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.endpoints import seasons as season_endpoints
from src.api.models import (
    MatchSession,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TrainingSession,
    db,
)
from src.api.season_service import get_active_season_for_club


ROOT = Path(__file__).resolve().parents[1]


def _planned(world, name="Temporada 2027", start=date(2027, 1, 1)):
    season = Season(
        club=world.club_a,
        name=name,
        start_date=start,
        end_date=date(start.year, 12, 31),
        status="planned",
        created_by=world.owner_a.id,
    )
    db.session.add(season)
    db.session.commit()
    return season


def _team(world, season, name="Future"):
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


def _preflight(client, world, season, auth_headers, user=None):
    return client.get(
        f"/api/seasons/{season.id}/preflight",
        headers=auth_headers(user or world.owner_a),
    )


def _activate(client, world, season, auth_headers, source=True, **payload):
    body = {"confirm_activation": True, **payload}
    if source:
        body["source_season_id"] = world.season_a.id
    return client.post(
        f"/api/seasons/{season.id}/transition",
        json=body,
        headers=auth_headers(world.owner_a),
    )


def test_multiple_planned_remain_supported_and_payload_exposes_can_delete(
    client, world, auth_headers
):
    first = _planned(world, "Temporada 2027", date(2027, 1, 1))
    second = _planned(world, "Temporada 2028", date(2028, 1, 1))

    response = client.get("/api/seasons", headers=auth_headers(world.owner_a))
    payload = {season["id"]: season for season in response.get_json()["seasons"]}

    assert response.status_code == 200
    assert payload[first.id]["can_delete"] is True
    assert payload[second.id]["can_delete"] is True


def test_owner_edits_only_planned_season(client, world, auth_headers):
    planned = _planned(world)
    response = client.patch(
        f"/api/seasons/{planned.id}",
        json={
            "name": "  Temporada 2027 revisada  ",
            "start_date": "2027-02-01",
            "end_date": None,
        },
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert response.get_json()["season"]["name"] == "Temporada 2027 revisada"
    assert response.get_json()["season"]["end_date"] is None


@pytest.mark.parametrize("status", ["active", "closed"])
def test_active_and_closed_seasons_cannot_be_edited(
    client, world, auth_headers, status
):
    season = world.season_a
    if status == "closed":
        season = Season(
            club=world.club_a,
            name="Histórica",
            start_date=date(2025, 1, 1),
            status="closed",
        )
        db.session.add(season)
        db.session.commit()

    response = client.patch(
        f"/api/seasons/{season.id}",
        json={"name": "No", "start_date": "2025-01-01"},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_NOT_PLANNED"


def test_planned_edit_validates_dates_and_owner(client, world, auth_headers):
    planned = _planned(world)
    invalid = client.patch(
        f"/api/seasons/{planned.id}",
        json={"start_date": "2027-04-01", "end_date": "2027-03-31"},
        headers=auth_headers(world.owner_a),
    )
    forbidden = client.patch(
        f"/api/seasons/{planned.id}",
        json={"name": "Coach edit"},
        headers=auth_headers(world.coach_a),
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["code"] == "INVALID_SEASON_DATE_RANGE"
    assert forbidden.status_code == 403


def test_owner_deletes_empty_planned_season(client, world, auth_headers):
    planned = _planned(world)
    response = client.delete(
        f"/api/seasons/{planned.id}", headers=auth_headers(world.owner_a)
    )
    assert response.status_code == 200
    assert db.session.get(Season, planned.id) is None


@pytest.mark.parametrize("dependency", ["team", "tournament"])
def test_delete_planned_with_dependency_is_denied(
    client, world, auth_headers, dependency
):
    planned = _planned(world)
    if dependency == "team":
        _team(world, planned)
    else:
        db.session.add(Tournament(
            club=world.club_a,
            season=planned,
            name="Preparado por datos legacy",
            start_date=date(2027, 5, 1),
            status="active",
            created_by=world.owner_a.id,
        ))
        db.session.commit()

    response = client.delete(
        f"/api/seasons/{planned.id}", headers=auth_headers(world.owner_a)
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_HAS_DEPENDENCIES"


@pytest.mark.parametrize("status", ["active", "closed"])
def test_active_and_closed_seasons_cannot_be_deleted(
    client, world, auth_headers, status
):
    season = world.season_a
    if status == "closed":
        season = Season(
            club=world.club_a,
            name="Histórica",
            start_date=date(2025, 1, 1),
            status="closed",
        )
        db.session.add(season)
        db.session.commit()
    response = client.delete(
        f"/api/seasons/{season.id}", headers=auth_headers(world.owner_a)
    )
    assert response.status_code == 409
    assert db.session.get(Season, season.id) is not None


def test_preflight_normal_mode_reports_warnings_without_blocking(
    client, world, auth_headers
):
    planned = _planned(world, name=world.season_a.name)
    _team(world, planned)
    response = _preflight(client, world, planned, auth_headers)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["mode"] == "transition"
    assert payload["source"]["id"] == world.season_a.id
    assert payload["can_activate"] is True
    assert {warning["code"] for warning in payload["warnings"]} >= {
        "TEAMS_WITHOUT_PLAYERS",
        "TEAMS_WITHOUT_COACH",
        "DUPLICATE_SEASON_NAME",
        "SEASON_DATES_OVERLAP",
    }


def test_preflight_teamless_target_is_blocked(client, world, auth_headers):
    planned = _planned(world)
    payload = _preflight(client, world, planned, auth_headers).get_json()
    assert payload["can_activate"] is False
    assert payload["blockers"][0]["code"] == "SEASON_TEAM_REQUIRED"


def test_preflight_reports_each_open_activity(client, world, auth_headers):
    planned = _planned(world)
    _team(world, planned)
    db.session.add_all([
        TrainingSession(
            team=world.team_a,
            date=date(2026, 12, 1),
            status="scheduled",
        ),
        MatchSession(
            team=world.team_a,
            date=date(2026, 12, 2),
            opponent_name="Rival",
            match_type="official",
            is_completed=False,
        ),
        Tournament(
            club=world.club_a,
            season=world.season_a,
            name="Abierto",
            start_date=date(2026, 12, 3),
            status="active",
            created_by=world.owner_a.id,
        ),
    ])
    db.session.commit()

    payload = _preflight(client, world, planned, auth_headers).get_json()
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert codes >= {"SCHEDULED_TRAININGS", "OPEN_MATCHES", "ACTIVE_TOURNAMENTS"}
    assert payload["summary"]["scheduled_trainings"] == 1
    assert payload["summary"]["open_matches"] == 1
    assert payload["summary"]["active_tournaments"] == 1


@pytest.mark.parametrize("invalid_kind", ["inactive", "gender", "status", "number"])
def test_preflight_blocks_invalid_target_roster(
    client, world, auth_headers, invalid_kind
):
    planned = _planned(world)
    target = _team(world, planned)
    player = world.players_a[0]
    membership = TeamPlayer(
        team=target,
        player=player,
        player_number=20,
        status="active",
    )
    if invalid_kind == "inactive":
        player.is_active = False
    elif invalid_kind == "gender":
        player.sex = "male"
    elif invalid_kind == "status":
        membership.status = "unknown"
    else:
        membership.player_number = 0
    db.session.add(membership)
    db.session.commit()

    payload = _preflight(client, world, planned, auth_headers).get_json()
    assert payload["can_activate"] is False
    assert "TARGET_ROSTER_INVALID" in {
        blocker["code"] for blocker in payload["blockers"]
    }


@pytest.mark.parametrize("role", ["coach_a", "staff_a"])
def test_preflight_is_owner_only(client, world, auth_headers, role):
    planned = _planned(world)
    response = _preflight(
        client, world, planned, auth_headers, user=getattr(world, role)
    )
    assert response.status_code == 403


def test_transition_requires_explicit_confirmation(client, world, auth_headers):
    planned = _planned(world)
    _team(world, planned)
    response = client.post(
        f"/api/seasons/{planned.id}/transition",
        json={"source_season_id": world.season_a.id},
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "SEASON_ACTIVATION_CONFIRMATION_REQUIRED"


def test_zero_active_recovery_preflight_and_activation(
    client, world, auth_headers
):
    world.season_a.status = "closed"
    planned = _planned(world)
    _team(world, planned)

    preflight = _preflight(client, world, planned, auth_headers).get_json()
    assert preflight["mode"] == "recovery"
    assert preflight["source"] is None
    assert preflight["can_activate"] is True

    response = _activate(
        client,
        world,
        planned,
        auth_headers,
        source=False,
    )
    assert response.status_code == 200
    assert response.get_json()["mode"] == "recovery"
    assert db.session.get(Season, world.season_a.id).status == "closed"
    assert get_active_season_for_club(world.club_a.id).id == planned.id
    assert Season.query.filter_by(club_id=world.club_a.id, status="active").count() == 1
    dashboard = client.get(
        "/api/club/dashboard", headers=auth_headers(world.owner_a)
    )
    assert dashboard.status_code == 200


def test_recovery_rejects_stale_source(client, world, auth_headers):
    world.season_a.status = "closed"
    planned = _planned(world)
    _team(world, planned)
    response = _activate(
        client,
        world,
        planned,
        auth_headers,
        source=False,
        source_season_id=world.season_a.id,
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_TRANSITION_CONFLICT"


def test_recovery_loses_with_conflict_if_an_active_season_appears(
    client, world, auth_headers
):
    world.season_a.status = "closed"
    planned = _planned(world)
    _team(world, planned)

    preflight = _preflight(client, world, planned, auth_headers).get_json()
    assert preflight["mode"] == "recovery"

    competing = Season(
        club=world.club_a,
        name="Temporada activada por otra petición",
        start_date=date(2026, 6, 1),
        status="active",
        created_by=world.owner_a.id,
    )
    db.session.add(competing)
    db.session.commit()

    response = _activate(
        client,
        world,
        planned,
        auth_headers,
        source=False,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SEASON_TRANSITION_CONFLICT"
    assert db.session.get(Season, planned.id).status == "planned"
    assert db.session.get(Season, competing.id).status == "active"
    assert Season.query.filter_by(
        club_id=world.club_a.id,
        status="active",
    ).count() == 1


def test_stale_preparation_writes_are_revalidated(client, world, auth_headers):
    planned = _planned(world)
    target = _team(world, planned)
    world.season_a.status = "closed"
    db.session.flush()
    planned.status = "active"
    db.session.commit()

    duplicate = client.post(
        f"/api/seasons/{planned.id}/teams/duplicate",
        json={"source_season_id": world.season_a.id, "team_ids": [world.team_a.id]},
        headers=auth_headers(world.owner_a),
    )
    roster = client.post(
        f"/api/teams/{target.id}/roster/copy",
        json={"source_team_id": world.team_a.id, "player_ids": [world.players_a[0].id]},
        headers=auth_headers(world.owner_a),
    )
    assert duplicate.status_code == 409
    assert roster.status_code == 409
    assert TeamPlayer.query.filter_by(team_id=target.id).count() == 0


def test_unknown_transition_integrity_error_is_not_mapped_to_conflict(
    client, world, auth_headers, monkeypatch
):
    planned = _planned(world)
    _team(world, planned)

    def fail_commit():
        raise IntegrityError("transition", {}, Exception("unknown database failure"))

    monkeypatch.setattr(season_endpoints.db.session, "commit", fail_commit)
    response = _activate(client, world, planned, auth_headers)
    assert response.status_code == 500
    assert response.get_json()["code"] == "INTERNAL_ERROR"


@pytest.mark.parametrize(
    "signature,expected_status",
    [
        (
            "UNIQUE constraint failed: teams.name, teams.gender, "
            "teams.category_id, teams.club_id, teams.season_id",
            409,
        ),
        ("unknown database failure", 500),
    ],
)
def test_structure_copy_classifies_only_expected_integrity_errors(
    client, world, auth_headers, monkeypatch, signature, expected_status
):
    planned = _planned(world)

    def fail_commit():
        raise IntegrityError("insert", {}, Exception(signature))

    monkeypatch.setattr(season_endpoints.db.session, "commit", fail_commit)
    response = client.post(
        f"/api/seasons/{planned.id}/teams/duplicate",
        json={
            "source_season_id": world.season_a.id,
            "team_ids": [world.team_a.id],
        },
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == expected_status
    if expected_status == 409:
        assert response.get_json()["code"] == "TEAM_ALREADY_COPIED"
    else:
        assert response.get_json()["code"] == "INTERNAL_ERROR"


def test_frontend_seasons_1_0_contract():
    seasons = (ROOT / "src/front/js/pages/seasons/seasons.js").read_text(
        encoding="utf-8"
    )
    selector = (ROOT / "src/front/js/component/seasonSelector.js").read_text(
        encoding="utf-8"
    )
    category = (ROOT / "src/front/js/pages/categories/categoryDetail.js").read_text(
        encoding="utf-8"
    )
    styles = (ROOT / "src/front/styles/seasons.css").read_text(encoding="utf-8")

    for heading in (
        "Ciclo de temporadas",
        "Temporada actual",
        "Temporadas en preparación",
        "Temporadas anteriores",
        "Revisar antes de activar",
    ):
        assert heading in seasons
    assert "planned.length === 1" in seasons
    assert "Activar de todas formas" in seasons
    assert 'role="dialog"' in seasons
    assert 'aria-modal="true"' in seasons
    assert "confirm_activation: true" in seasons
    assert '"SEASON_HAS_OPEN_ACTIVITIES"' in seasons
    assert '"TARGET_ROSTER_INVALID"' in seasons
    assert "await loadDetail(targetId)" in seasons
    assert "Volver a intentar" in seasons
    assert 'active: "Actual"' in selector
    assert 'planned: "En preparación"' in selector
    assert "preparación por el administrador del club" in category
    assert "@media (max-width: 480px)" in styles


def test_preparation_operations_share_deterministic_season_lock():
    source = (ROOT / "src/api/endpoints/seasons.py").read_text(encoding="utf-8")
    service = (ROOT / "src/api/season_service.py").read_text(encoding="utf-8")
    assert source.count("lock_club_seasons_for_update(user.club_id)") >= 5
    assert "Season.id.asc()" in service
