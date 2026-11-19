from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Query

from src.api.models import (
    MatchSession,
    Player,
    PlayerPayment,
    Season,
    Team,
    TeamPlayer,
    Tournament,
    TournamentPlayer,
    TournamentTeam,
    db,
)


ROOT = Path(__file__).resolve().parents[1]


def _entry(world, *, status="active"):
    tournament = Tournament(
        club_id=world.club_a.id,
        season_id=world.season_a.id,
        name="Copa 1.0",
        organizer_name="Liga local",
        start_date=date(2026, 9, 1),
        default_referee_fee=25,
        status=status,
        created_by=world.owner_a.id,
    )
    entry = TournamentTeam(
        tournament=tournament,
        team=world.team_a,
        registration_fee=80,
        status="active",
    )
    db.session.add_all([tournament, entry])
    db.session.commit()
    return tournament, entry


def _lock_spy(monkeypatch):
    entities = []
    original = Query.with_for_update

    def spy(query, *args, **kwargs):
        entities.append(query.column_descriptions[0].get("entity"))
        return original(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", spy)
    return entities


def test_tournament_read_models_expose_roster_match_and_season_context(
    client, world, auth_headers
):
    tournament, entry = _entry(world)
    db.session.add_all([
        TournamentPlayer(
            tournament_team_id=entry.id,
            player_id=world.players_a[0].id,
            status="active",
        ),
        TournamentPlayer(
            tournament_team_id=entry.id,
            player_id=world.players_a[1].id,
            status="withdrawn",
        ),
        MatchSession(
            team_id=world.team_a.id,
            tournament_team_id=entry.id,
            date=date(2026, 9, 2),
            opponent_name="Rival abierto",
            is_completed=False,
            created_by=world.owner_a.id,
        ),
        MatchSession(
            team_id=world.team_a.id,
            tournament_team_id=entry.id,
            date=date(2026, 9, 3),
            opponent_name="Rival cerrado",
            is_completed=True,
            home_sets=3,
            opponent_sets=1,
            result="win",
            created_by=world.owner_a.id,
        ),
    ])
    db.session.commit()

    listing = client.get(
        f"/api/tournaments?season_id={world.season_a.id}",
        headers=auth_headers(world.owner_a),
    )
    assert listing.status_code == 200
    row = listing.get_json()["tournaments"][0]
    assert row["season_name"] == world.season_a.name
    assert row["active_roster_count"] == 1
    assert row["total_roster_count"] == 2
    assert row["open_matches_count"] == 1
    assert row["completed_matches_count"] == 1
    assert row["total_matches"] == 2

    detail = client.get(
        f"/api/tournaments/{tournament.id}",
        headers=auth_headers(world.owner_a),
    )
    assert detail.status_code == 200
    payload = detail.get_json()["tournament"]
    assert len(payload["matches"]) == 2
    assert payload["teams"][0]["currently_eligible_players_count"] == 1
    assert payload["teams"][0]["active_roster_count"] == 1
    assert payload["teams"][0]["total_roster_count"] == 2


def test_metadata_update_locks_parent_and_terminal_is_readonly(
    client, world, auth_headers, monkeypatch
):
    tournament, _ = _entry(world)
    locks = _lock_spy(monkeypatch)

    updated = client.put(
        f"/api/tournaments/{tournament.id}",
        headers=auth_headers(world.owner_a),
        json={"name": "Copa segura", "end_date": "2026-09-04"},
    )
    assert updated.status_code == 200
    assert locks[0] is Tournament
    assert updated.get_json()["tournament"]["name"] == "Copa segura"

    tournament = db.session.get(Tournament, tournament.id)
    tournament.status = "completed"
    db.session.commit()
    denied = client.put(
        f"/api/tournaments/{tournament.id}",
        headers=auth_headers(world.owner_a),
        json={"name": "No debe guardarse"},
    )
    assert denied.status_code == 409
    assert denied.get_json()["code"] == "TOURNAMENT_NOT_ACTIVE"
    db.session.expire_all()
    assert db.session.get(Tournament, tournament.id).name == "Copa segura"


def test_cancel_locks_finance_dependencies_and_redacts_coach_count(
    client, world, auth_headers, monkeypatch
):
    tournament, entry = _entry(world)
    db.session.add(PlayerPayment(
        club_id=world.club_a.id,
        player_id=world.players_a[0].id,
        payment_type="tournament",
        tournament_team_id=entry.id,
        amount=80,
        currency_code="USD",
        status="pending",
    ))
    db.session.commit()
    locks = _lock_spy(monkeypatch)

    owner_response = client.put(
        f"/api/tournaments/{tournament.id}/cancel",
        headers=auth_headers(world.owner_a),
    )
    assert owner_response.status_code == 409
    assert owner_response.get_json()["code"] == "TOURNAMENT_HAS_PENDING_CHARGES"
    assert owner_response.get_json()["pending_charges_count"] == 1
    assert locks[0] is Tournament
    assert TournamentTeam in locks
    assert PlayerPayment in locks

    coach_response = client.put(
        f"/api/tournaments/{tournament.id}/cancel",
        headers=auth_headers(world.coach_a),
    )
    assert coach_response.status_code == 409
    assert coach_response.get_json()["code"] == "FINANCE_DEPENDENCY"
    assert "pending_charges_count" not in coach_response.get_json()
    assert "amount" not in coach_response.get_data(as_text=True)


def test_roster_addition_revalidates_under_deterministic_lock_order(
    client, world, auth_headers, monkeypatch
):
    _, entry = _entry(world)
    locks = _lock_spy(monkeypatch)
    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.owner_a),
        json={"player_ids": [world.players_a[0].id]},
    )
    assert response.status_code == 200

    expected = [
        Tournament,
        TournamentTeam,
        Team,
        Season,
        TournamentPlayer,
        Player,
        TeamPlayer,
    ]
    positions = [locks.index(entity) for entity in expected]
    assert positions == sorted(positions)
    assert TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=world.players_a[0].id,
        status="active",
    ).count() == 1


def test_add_team_revalidates_team_and_season_after_tournament_lock(
    client, world, auth_headers, monkeypatch
):
    tournament = Tournament(
        club_id=world.club_a.id,
        season_id=world.season_a.id,
        name="Copa para inscripción segura",
        start_date=date(2026, 9, 5),
        status="active",
        created_by=world.owner_a.id,
    )
    db.session.add(tournament)
    db.session.commit()
    locks = _lock_spy(monkeypatch)

    response = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        headers=auth_headers(world.owner_a),
        json={"team_id": world.team_a.id},
    )

    assert response.status_code == 201
    expected = [Tournament, Team, Season]
    positions = [locks.index(entity) for entity in expected]
    assert positions == sorted(positions)


@pytest.mark.parametrize("membership_status", ["inactive", "injured"])
def test_roster_reactivation_rejects_changed_membership_eligibility(
    client, world, auth_headers, membership_status
):
    _, entry = _entry(world)
    registration = TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=world.players_a[0].id,
        status="withdrawn",
    )
    membership = TeamPlayer.query.filter_by(
        team_id=world.team_a.id,
        player_id=world.players_a[0].id,
        left_at=None,
    ).one()
    membership.status = membership_status
    db.session.add(registration)
    db.session.commit()

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.owner_a),
        json={"player_ids": [world.players_a[0].id]},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT"
    db.session.expire_all()
    assert db.session.get(TournamentPlayer, registration.id).status == "withdrawn"


def test_coach_read_model_redacts_finance_but_keeps_sports_blocker(
    client, world, auth_headers
):
    tournament, entry = _entry(world)
    db.session.add(PlayerPayment(
        club_id=world.club_a.id,
        player_id=world.players_a[0].id,
        payment_type="tournament",
        tournament_team_id=entry.id,
        amount=80,
        currency_code="USD",
        status="pending",
    ))
    db.session.commit()

    response = client.get(
        f"/api/tournaments/{tournament.id}",
        headers=auth_headers(world.coach_a),
    )
    assert response.status_code == 200
    payload = response.get_json()["tournament"]
    assert payload["has_pending_admin_dependencies"] is True
    assert "pending_admin_dependencies_count" not in payload
    assert "default_referee_fee" not in payload
    assert "registration_fee" not in payload["teams"][0]


def test_frontend_tournament_1_0_contracts_are_explicit():
    listing = (ROOT / "src/front/js/pages/tournaments/tournaments.js").read_text()
    detail = (ROOT / "src/front/js/pages/tournaments/tournamentDetail.js").read_text()
    entry = (ROOT / "src/front/js/pages/tournaments/tournamentTeamDetail.js").read_text()
    create_match = (ROOT / "src/front/js/pages/matches/createMatch.js").read_text()
    flux = (ROOT / "src/front/js/store/flux.js").read_text()
    dialog = (ROOT / "src/front/js/component/ui/confirmationDialog.js").read_text()

    assert '"Activos"' in listing and '"Históricos"' in listing
    assert "tournament-card-link" in listing
    assert "tournament-status-filter" in listing
    assert "seasonError" in listing and "reloadSeasons" in listing
    assert "loadRequestId" in listing
    assert "TOURNAMENT_HAS_OPEN_MATCHES" in detail
    assert "pending_admin_dependencies_count" in detail
    assert "const canAddTeam" in detail
    assert "canAddTeam && availableTeams.length > 0" in detail
    assert "ConfirmationDialog" in detail
    assert "window.confirm" not in detail
    assert "Permanecen" in entry and "Se incorporan" in entry and "Se retiran" in entry
    assert "Historial de inscripciones" in entry
    assert "aria-pressed={selected}" in entry
    assert "Actualmente no elegible" in entry
    assert "Crear partido" in entry
    assert "window.confirm" not in entry
    assert "fixedTournamentTeamId" in create_match
    assert "tournament_team" in create_match
    assert "tournamentsRequestId" in flux
    assert "tournamentDetailRequestId" in flux
    assert "tournamentPlayersRequestId" in flux
    assert 'role="dialog"' in dialog
    assert 'aria-modal="true"' in dialog
    assert 'event.key === "Escape"' in dialog


def test_historical_query_context_is_preserved_across_tournament_flow():
    listing = (ROOT / "src/front/js/pages/tournaments/tournaments.js").read_text()
    detail = (ROOT / "src/front/js/pages/tournaments/tournamentDetail.js").read_text()
    entry = (ROOT / "src/front/js/pages/tournaments/tournamentTeamDetail.js").read_text()
    create_match = (ROOT / "src/front/js/pages/matches/createMatch.js").read_text()

    assert "searchParams.toString()" in listing
    assert "location.search" in detail
    assert "location.search" in entry
    assert "new URLSearchParams(searchParams)" in create_match
    assert 'next.delete("tournament_team")' in create_match
