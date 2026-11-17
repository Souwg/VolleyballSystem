from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.integrity_errors import violates_named_constraint
from src.api.models import (
    Player,
    Season,
    Team,
    TeamCoachAssignment,
    TeamPlayer,
    db,
)


ROOT = Path(__file__).resolve().parents[1]


def _planned_team(world, *, gender="female", name="Futuro"):
    season = Season(
        club=world.club_a,
        name=f"Temporada {name}",
        start_date=date(2027, 1, 1),
        status="planned",
        created_by=world.owner_a.id,
    )
    team = Team(
        club=world.club_a,
        category=world.category_a,
        season=season,
        name=name,
        gender=gender,
        status="active",
    )
    db.session.add_all([season, team])
    db.session.commit()
    return team


def _create_player(client, world, auth_headers, **overrides):
    payload = {
        "first_name": "  Ana  María ",
        "last_name": "  Pérez  ",
        "sex": "female",
        "birth_date": "2012-05-12",
    }
    payload.update(overrides)
    return client.post(
        "/api/players",
        headers=auth_headers(world.owner_a),
        json=payload,
    )


def test_player_without_team_is_valid_and_names_are_normalized(
    client, world, auth_headers
):
    response = _create_player(client, world, auth_headers)
    assert response.status_code == 201
    player = response.get_json()["player"]
    assert player["first_name"] == "Ana María"
    assert player["last_name"] == "Pérez"
    assert player["team_id"] is None


@pytest.mark.parametrize("birth_date", ["2999-01-01", "not-a-date"])
def test_player_birth_date_is_validated(client, world, auth_headers, birth_date):
    response = _create_player(
        client, world, auth_headers, birth_date=birth_date
    )
    assert response.status_code == 400
    assert response.get_json()["code"] in {
        "INVALID_BIRTH_DATE",
        "INVALID_DATE_FORMAT",
    }


@pytest.mark.parametrize("number", [0, 100])
def test_create_dorsal_is_always_1_to_99(
    client, world, auth_headers, number
):
    response = _create_player(
        client,
        world,
        auth_headers,
        team_id=world.team_a.id,
        player_number=number,
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_PLAYER_NUMBER"


def test_dedicated_detail_includes_current_and_historical_memberships(
    client, world, auth_headers
):
    player = world.players_a[0]
    historical = TeamPlayer(
        team=world.team_a,
        player=player,
        player_number=90,
        status="inactive",
        joined_at=datetime(2025, 1, 1),
        left_at=datetime(2025, 6, 1),
    )
    db.session.add(historical)
    db.session.commit()

    response = client.get(
        f"/api/players/{player.id}",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200
    payload = response.get_json()["player"]
    assert len(payload["current_memberships"]) == 1
    assert len(payload["historical_memberships"]) == 1
    assert payload["current_memberships"][0]["season_name"]
    assert payload["historical_memberships"][0]["left_at"]
    assert payload["can_delete"] is False


def test_closed_season_membership_is_historical_even_without_left_at(
    client, world, auth_headers
):
    world.season_a.status = "closed"
    db.session.commit()
    response = client.get(
        f"/api/players/{world.players_a[0].id}",
        headers=auth_headers(world.owner_a),
    )
    payload = response.get_json()["player"]
    assert payload["current_memberships"] == []
    assert len(payload["historical_memberships"]) == 1


def test_global_directory_includes_active_and_planned_memberships(
    client, world, auth_headers
):
    planned = _planned_team(world)
    db.session.add(TeamPlayer(
        team=planned,
        player=world.players_a[0],
        player_number=77,
        status="injured",
    ))
    db.session.commit()

    response = client.get("/api/players", headers=auth_headers(world.owner_a))
    row = next(
        item
        for item in response.get_json()["players"]
        if item["id"] == world.players_a[0].id
    )

    assert {team["id"] for team in row["teams"]} == {
        world.team_a.id,
        planned.id,
    }
    assert any(team["season_status"] == "planned" for team in row["teams"])


def test_staff_reads_same_detail_as_read_only(client, world, auth_headers):
    response = client.get(
        f"/api/players/{world.players_a[0].id}",
        headers=auth_headers(world.staff_a),
    )
    assert response.status_code == 200
    payload = response.get_json()["player"]
    assert payload["read_only"] is True
    assert payload["current_memberships"]
    assert "representative_name" in payload


def test_detail_is_tenant_scoped(client, world, auth_headers):
    response = client.get(
        f"/api/players/{world.players_b[0].id}",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 404


def test_detail_never_exposes_cross_tenant_membership_if_data_is_corrupt(
    client, world, auth_headers
):
    db.session.add(TeamPlayer(
        team=world.team_b,
        player=world.players_a[0],
        player_number=88,
        status="active",
    ))
    db.session.commit()

    response = client.get(
        f"/api/players/{world.players_a[0].id}",
        headers=auth_headers(world.owner_a),
    )
    payload = response.get_json()["player"]
    memberships = (
        payload["current_memberships"]
        + payload["historical_memberships"]
    )

    assert response.status_code == 200
    assert world.team_b.id not in {row["team_id"] for row in memberships}

    other_roster = client.get(
        f"/api/teams/{world.team_b.id}/players",
        headers=auth_headers(world.owner_b),
    )
    assert world.players_a[0].id not in {
        row["id"] for row in other_roster.get_json()["players"]
    }


def test_hard_delete_allows_only_empty_profile(client, world, auth_headers):
    created = _create_player(client, world, auth_headers).get_json()["player"]
    detail = client.get(
        f"/api/players/{created['id']}",
        headers=auth_headers(world.owner_a),
    )
    assert detail.get_json()["player"]["can_delete"] is True
    deleted = client.delete(
        f"/api/players/{created['id']}",
        headers=auth_headers(world.owner_a),
    )
    assert deleted.status_code == 200


@pytest.mark.parametrize("closed", [False, True])
def test_hard_delete_blocks_any_team_membership(
    client, world, auth_headers, closed
):
    membership = TeamPlayer.query.filter_by(
        player_id=world.players_a[0].id,
        team_id=world.team_a.id,
    ).one()
    if closed:
        membership.left_at = datetime.utcnow()
        db.session.commit()
    response = client.delete(
        f"/api/players/{world.players_a[0].id}",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_HAS_HISTORY"


def test_duplicate_candidates_are_same_club_and_rank_birth_and_sex(
    client, world, auth_headers
):
    local = Player(
        first_name="María",
        last_name="Pérez",
        birth_date=date(2012, 5, 12),
        sex="female",
        club=world.club_a,
    )
    other = Player(
        first_name="María",
        last_name="Pérez",
        birth_date=date(2012, 5, 12),
        sex="female",
        club=world.club_b,
    )
    db.session.add_all([local, other])
    db.session.commit()
    response = client.get(
        "/api/players/candidates?first_name=Mar%C3%ADa&last_name=P%C3%A9rez&birth_date=2012-05-12&sex=female",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200
    candidates = response.get_json()["candidates"]
    assert [candidate["id"] for candidate in candidates] == [local.id]
    assert candidates[0]["match"] == {"birth_date": True, "sex": True}


def test_duplicate_name_never_blocks_create_anyway(client, world, auth_headers):
    first = _create_player(client, world, auth_headers)
    second = _create_player(client, world, auth_headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["player"]["id"] != second.get_json()["player"]["id"]


def test_club_wide_coach_edits_only_main_position(client, world, auth_headers):
    player = world.players_a[0]
    allowed = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(world.coach_a),
        json={"main_position": "libero"},
    )
    denied = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(world.coach_a),
        json={
            "first_name": "Cambio",
            "last_name": player.last_name,
            "sex": player.sex,
            "main_position": "setter",
        },
    )
    assert allowed.status_code == 200
    assert denied.status_code == 403
    db.session.refresh(player)
    assert player.first_name != "Cambio"


def test_coach_cannot_set_representative_when_creating_player(
    client, world, auth_headers
):
    response = client.post(
        "/api/players",
        headers=auth_headers(world.coach_a),
        json={
            "first_name": "Ana",
            "last_name": "Nueva",
            "sex": "female",
            "representative_name": "Dato administrativo",
        },
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"
    assert Player.query.filter_by(first_name="Ana", last_name="Nueva").first() is None


def test_scoped_coach_cannot_create_orphan_or_edit_global_profile(
    client, world, auth_headers
):
    world.club_a.coach_access_mode = "team_assigned"
    db.session.add(TeamCoachAssignment(
        team_id=world.team_a.id,
        user_id=world.coach_a.id,
        club_id=world.club_a.id,
        assigned_by=world.owner_a.id,
    ))
    db.session.commit()
    orphan = client.post(
        "/api/players",
        headers=auth_headers(world.coach_a),
        json={"first_name": "Nueva", "last_name": "Persona", "sex": "female"},
    )
    in_team = client.post(
        "/api/players",
        headers=auth_headers(world.coach_a),
        json={
            "first_name": "Nueva",
            "last_name": "Persona",
            "sex": "female",
            "team_id": world.team_a.id,
            "player_number": 90,
        },
    )
    edit = client.put(
        f"/api/players/{world.players_a[0].id}",
        headers=auth_headers(world.coach_a),
        json={"main_position": "libero"},
    )
    assert orphan.status_code == 403
    assert orphan.get_json()["code"] == "TEAM_REQUIRED_FOR_SCOPED_COACH"
    assert in_team.status_code == 201
    assert edit.status_code == 403


def test_roster_copy_preserves_explicit_injured_status(
    client, world, auth_headers
):
    target = _planned_team(world)
    source = TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[0].id,
    ).one()
    source.status = "injured"
    db.session.commit()
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        headers=auth_headers(world.owner_a),
        json={
            "source_team_id": world.team_a.id,
            "players": [{
                "player_id": source.player_id,
                "player_number": 22,
                "status": "injured",
            }],
        },
    )
    assert response.status_code == 201
    copied = TeamPlayer.query.filter_by(team_id=target.id).one()
    assert copied.player_number == 22
    assert copied.status == "injured"


def test_roster_copy_blocks_global_inactive_and_incompatible_branch(
    client, world, auth_headers
):
    target = _planned_team(world)
    player = world.players_a[0]
    player.is_active = False
    db.session.commit()
    inactive = client.post(
        f"/api/teams/{target.id}/roster/copy",
        headers=auth_headers(world.owner_a),
        json={"source_team_id": world.team_a.id, "player_ids": [player.id]},
    )
    player.is_active = True
    player.sex = "male"
    db.session.commit()
    incompatible = client.post(
        f"/api/teams/{target.id}/roster/copy",
        headers=auth_headers(world.owner_a),
        json={"source_team_id": world.team_a.id, "player_ids": [player.id]},
    )
    assert inactive.status_code == 409
    assert inactive.get_json()["code"] == "PLAYER_INACTIVE"
    assert incompatible.status_code == 409
    assert incompatible.get_json()["code"] == "PLAYER_GENDER_MISMATCH"


def test_roster_copy_rejects_cross_tenant_player_even_if_membership_is_corrupt(
    client, world, auth_headers
):
    target = _planned_team(world)
    db.session.add(TeamPlayer(
        team=world.team_a,
        player=world.players_b[0],
        player_number=88,
        status="active",
    ))
    db.session.commit()

    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        headers=auth_headers(world.owner_a),
        json={
            "source_team_id": world.team_a.id,
            "players": [{
                "player_id": world.players_b[0].id,
                "player_number": 88,
                "status": "active",
            }],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "PLAYER_NOT_IN_TEAM"
    assert TeamPlayer.query.filter_by(
        team_id=target.id,
        player_id=world.players_b[0].id,
    ).first() is None


def test_roster_copy_requires_review_for_source_inactive(
    client, world, auth_headers
):
    target = _planned_team(world)
    source = TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[0].id,
    ).one()
    source.status = "inactive"
    db.session.commit()
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        headers=auth_headers(world.owner_a),
        json={"source_team_id": world.team_a.id, "player_ids": [source.player_id]},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_STATUS_REVIEW_REQUIRED"


def test_roster_copy_detects_target_dorsal_conflict(
    client, world, auth_headers
):
    target = _planned_team(world)
    db.session.add(TeamPlayer(
        team=target,
        player=world.players_a[1],
        player_number=55,
    ))
    db.session.commit()
    response = client.post(
        f"/api/teams/{target.id}/roster/copy",
        headers=auth_headers(world.owner_a),
        json={
            "source_team_id": world.team_a.id,
            "players": [{
                "player_id": world.players_a[0].id,
                "player_number": 55,
                "status": "active",
            }],
        },
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NUMBER_DUPLICATED"


def test_players_frontend_contract_for_directory_access_and_copy():
    directory = (ROOT / "src/front/js/pages/players/players.js").read_text(
        encoding="utf-8"
    )
    detail = (ROOT / "src/front/js/pages/players/playerDetail.js").read_text(
        encoding="utf-8"
    )
    team = (ROOT / "src/front/js/pages/teams/teamDetail.js").read_text(
        encoding="utf-8"
    )
    seasons = (ROOT / "src/front/js/pages/seasons/seasons.js").read_text(
        encoding="utf-8"
    )

    assert 'title="Deportistas del club"' in directory
    assert 'className="player-profile-link"' in directory
    assert "player-header-clickable" not in directory
    assert "Estado en el club" in directory
    assert "Encontramos posibles coincidencias" in directory
    assert "Registra deportistas en el club" in directory
    assert "Activo en el club" in detail
    assert "current_memberships" in detail
    assert "Ver equipo" in detail
    assert "player.can_delete" in detail or "canDeletePlayer" in detail
    assert "Solo lectura" in detail
    assert "Agregar deportista existente del club" in team
    assert "Seguirá perteneciendo a sus otros equipos" in team
    assert "Preparar vista previa" in seasons
    assert "Dorsal destino" in seasons


@pytest.mark.parametrize(
    "signature",
    [
        "team_players.team_id, team_players.player_id",
        "team_players.team_id, team_players.player_number",
    ],
)
def test_sqlite_team_player_race_signatures_are_classified(signature):
    error = IntegrityError(
        "insert",
        {},
        Exception(f"UNIQUE constraint failed: {signature}"),
    )
    assert violates_named_constraint(error, (signature,))
