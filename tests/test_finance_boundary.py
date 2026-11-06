import uuid
from datetime import date

import pytest

from src.api import receipt_service
from src.api.finance_access import (
    CLUB_FINANCE_FIELDS,
    PLAYER_FINANCE_FIELDS,
    SPORTS_MONEY_FIELDS,
    can_access_finance,
    can_configure_sports_finance,
    charge_blocks_roster_change,
)
from src.api.models import (
    db,
    MatchPlayer,
    MatchSession,
    PaymentReceipt,
    Player,
    PlayerPayment,
    Tournament,
    TournamentPlayer,
    TournamentTeam,
)
from tests.test_coach_team_enforcement import (
    _assign,
    _entry,
    _scope,
    _team,
    _tournament,
)


FINANCE_KEYS = (
    SPORTS_MONEY_FIELDS
    | set(PLAYER_FINANCE_FIELDS)
    | set(CLUB_FINANCE_FIELDS)
)
COACH_MODES = ["club_wide", "team_assigned"]


@pytest.fixture(autouse=True)
def onboarded_club(world):
    world.club_a.location = "Cancha principal"
    db.session.commit()


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


def _coach_in_mode(world, mode):
    if mode == "team_assigned":
        _scope(world.club_a)
        _assign(world)

    return world.coach_a


def _code(response):
    return response.get_json().get("code")


def _money_scenario(world, match_factory):
    world.club_a.default_enrollment_fee = 11
    world.club_a.default_monthly_fee = 22
    world.players_a[0].monthly_fee = 30
    world.players_a[0].enrollment_fee = 15
    match = match_factory(world).match
    match.referee_fee = 60
    entry = _entry(world)
    entry.registration_fee = 500
    entry.tournament.default_referee_fee = 30
    db.session.add(TournamentPlayer(
        tournament_team_id=entry.id,
        player_id=world.players_a[0].id,
        status="active",
    ))
    tournament_match = MatchSession(
        team=world.team_a,
        tournament_team_id=entry.id,
        date=date(2026, 8, 12),
        opponent_name="Rival torneo",
        match_type="official",
        referee_fee=40,
        created_by=world.owner_a.id,
    )
    db.session.add(tournament_match)
    db.session.commit()
    return match, tournament_match, entry


def _referee_charge(world, match, player=None, status="pending"):
    charge = PlayerPayment(
        club_id=world.club_a.id,
        player_id=(player or world.players_a[0]).id,
        match_id=match.id,
        payment_type="referee",
        amount=10,
        currency_code="USD",
        status=status,
    )
    db.session.add(charge)
    db.session.commit()
    return charge


def _registration_charge(world, entry, player=None, status="pending"):
    charge = PlayerPayment(
        club_id=world.club_a.id,
        player_id=(player or world.players_a[0]).id,
        tournament_team_id=entry.id,
        payment_type="tournament",
        amount=10,
        currency_code="USD",
        status=status,
    )
    db.session.add(charge)
    db.session.commit()
    return charge


def _receipt_for(world, charge):
    receipt = PaymentReceipt(
        payment_id=charge.id,
        club_id=world.club_a.id,
        player_id=charge.player_id,
        receipt_number=f"R-{uuid.uuid4().hex[:8]}",
        currency_code_snapshot="USD",
    )
    db.session.add(receipt)
    db.session.commit()
    return receipt


def _register(world, entry, players):
    for player in players:
        db.session.add(TournamentPlayer(
            tournament_team_id=entry.id,
            player_id=player.id,
            status="active",
        ))

    db.session.commit()


def _finance_state():
    db.session.expire_all()
    return {
        "charges": sorted(
            (
                charge.id,
                charge.player_id,
                float(charge.amount),
                charge.status,
                charge.match_id,
                charge.tournament_team_id,
            )
            for charge in PlayerPayment.query.all()
        ),
        "receipts": sorted(
            (receipt.id, receipt.payment_id)
            for receipt in PaymentReceipt.query.all()
        ),
    }


def _match_roster_state(match):
    db.session.expire_all()
    return sorted(
        (row.player_id, row.is_called, row.attendance_status, row.position)
        for row in MatchPlayer.query.filter_by(match_id=match.id).all()
    ) + [("step", MatchSession.query.get(match.id).match_step)]


def _tournament_roster_state(entry):
    db.session.expire_all()
    return sorted(
        (row.player_id, row.status)
        for row in TournamentPlayer.query.filter_by(
            tournament_team_id=entry.id
        ).all()
    )


def _called_ids(world, without=()):
    return [
        {"player_id": player.id}
        for player in world.players_a
        if player not in without
    ]


# =========================
# Helpers
# =========================


@pytest.mark.parametrize(
    "role, access, configure",
    [
        ("club_owner", True, True),
        ("staff", True, False),
        ("coach", False, False),
        ("system_admin", False, False),
    ],
)
def test_finance_role_policy(role, access, configure):
    class User:
        pass

    user = User()
    user.role = role

    assert can_access_finance(user) is access
    assert can_configure_sports_finance(user) is configure


@pytest.mark.parametrize(
    "status, has_receipt, blocks",
    [
        ("pending", False, True),
        ("overdue", False, True),
        ("paid", False, True),
        ("cancelled", False, False),
        ("cancelled", True, True),
    ],
)
def test_only_an_untouched_cancelled_charge_leaves_the_roster_free(
    status, has_receipt, blocks
):
    class Charge:
        pass

    charge = Charge()
    charge.status = status
    charge.has_receipt_history = has_receipt

    assert charge_blocks_roster_change(charge) is blocks


# =========================
# Lecturas de Coach
# =========================


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_reads_contain_no_finance(
    client, world, auth_headers, match_factory, mode
):
    match, tournament_match, entry = _money_scenario(world, match_factory)
    coach = _coach_in_mode(world, mode)
    headers = auth_headers(coach)
    player = world.players_a[0]

    urls = [
        "/api/players",
        f"/api/teams/{world.team_a.id}/players",
        f"/api/teams/{world.team_a.id}/matches",
        f"/api/teams/{world.team_a.id}/tournament-entries",
        f"/api/players/{player.id}/performance",
        "/api/matches",
        f"/api/matches/{match.id}",
        f"/api/matches/{tournament_match.id}",
        f"/api/matches/{tournament_match.id}/roster",
        "/api/tournaments",
        f"/api/tournaments/{entry.tournament_id}",
        f"/api/tournaments/{entry.tournament_id}/teams",
        f"/api/tournament-teams/{entry.id}/players",
        "/api/club/dashboard",
        "/api/onboarding/status",
    ]

    for url in urls:
        response = client.get(url, headers=headers)

        assert response.status_code == 200, url
        assert _keys(response.get_json()) & FINANCE_KEYS == set(), url


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_session_responses_keep_club_context_without_fees(
    client, world, auth_headers, match_factory, app, mode
):
    from src.api.extensions import bcrypt

    _money_scenario(world, match_factory)
    coach = _coach_in_mode(world, mode)
    coach.password = bcrypt.generate_password_hash("Clave1234").decode("utf-8")
    db.session.commit()

    login = client.post(
        "/api/login",
        json={"email": coach.email, "password": "Clave1234"},
    )

    assert login.status_code == 200
    data = login.get_json()
    club = data["user"]["club"]
    assert _keys(data) & FINANCE_KEYS == set()
    assert club["name"] == world.club_a.name
    assert club["currency_code"] == world.club_a.currency_code
    assert club["coach_access_mode"] == mode
    assert club["sport"]["code"] == "VOLLEYBALL"
    assert "timezone" in club

    refresh = client.post(
        "/api/refresh",
        headers={"Authorization": f"Bearer {data['refresh']}"},
    )

    assert refresh.status_code == 200
    assert _keys(refresh.get_json()) & FINANCE_KEYS == set()

    onboarding = client.get(
        "/api/onboarding/status",
        headers=auth_headers(coach),
    ).get_json()
    assert onboarding["status"] == "completed"
    assert onboarding["club"]["currency_code"] == world.club_a.currency_code
    assert _keys(onboarding) & FINANCE_KEYS == set()


def test_coach_set_password_response_contains_no_fees(
    client, world, auth_headers, match_factory
):
    _money_scenario(world, match_factory)
    world.coach_a.first_login = True
    db.session.commit()

    response = client.post(
        "/api/auth/set-password",
        headers=auth_headers(world.coach_a),
        json={"new_password": "ClaveNueva123"},
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["user"]["club"]["name"] == world.club_a.name
    assert _keys(response.get_json()) & FINANCE_KEYS == set()


def test_owner_and_staff_keep_club_fees_in_session(
    client, world, auth_headers, match_factory
):
    _money_scenario(world, match_factory)

    for user in [world.owner_a, world.staff_a]:
        club = client.get(
            "/api/onboarding/status",
            headers=auth_headers(user),
        ).get_json()["club"]

        assert club["default_monthly_fee"] == 22
        assert club["default_enrollment_fee"] == 11


def test_owner_keeps_money_in_sports_reads(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    headers = auth_headers(world.owner_a)

    assert client.get(
        f"/api/matches/{match.id}",
        headers=headers,
    ).get_json()["match"]["referee_fee"] == 60

    tournament = client.get(
        f"/api/tournaments/{entry.tournament_id}",
        headers=headers,
    ).get_json()["tournament"]

    assert tournament["default_referee_fee"] == 30
    assert tournament["teams"][0]["registration_fee"] == 500


def test_club_wide_coach_tournament_responses_contain_no_fee(
    client, world, auth_headers
):
    headers = auth_headers(world.coach_a)

    created = client.post(
        "/api/tournaments",
        headers=headers,
        json={"name": "Copa Coach", "start_date": "2026-09-01"},
    )

    assert created.status_code == 201
    assert _keys(created.get_json()) & FINANCE_KEYS == set()
    tournament_id = created.get_json()["tournament"]["id"]

    updated = client.put(
        f"/api/tournaments/{tournament_id}",
        headers=headers,
        json={"organizer_name": "Liga"},
    )

    assert updated.status_code == 200
    assert _keys(updated.get_json()) & FINANCE_KEYS == set()

    completed = client.put(
        f"/api/tournaments/{tournament_id}/complete",
        headers=headers,
    )

    assert completed.status_code == 200
    assert _keys(completed.get_json()) & FINANCE_KEYS == set()

    repeated = client.put(
        f"/api/tournaments/{tournament_id}/complete",
        headers=headers,
    )

    assert repeated.status_code == 200
    assert _keys(repeated.get_json()) & FINANCE_KEYS == set()


# =========================
# Mutaciones manuales de Coach
# =========================


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("field", PLAYER_FINANCE_FIELDS)
def test_coach_cannot_send_player_finance(
    client, world, auth_headers, mode, field
):
    coach = _coach_in_mode(world, mode)
    player = world.players_a[0]
    value = "2026-01-01" if field.endswith("date") else 5

    created = client.post(
        "/api/players",
        headers=auth_headers(coach),
        json={
            "first_name": "Nueva",
            "last_name": "Jugadora",
            "sex": "female",
            field: value,
        },
    )
    updated = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(coach),
        json={
            "first_name": "Cambio",
            "last_name": "Jugadora",
            "sex": "female",
            field: value,
        },
    )

    assert created.status_code == 403
    assert updated.status_code == 403
    assert _code(created) == "FINANCE_FORBIDDEN"
    assert _code(updated) == "FINANCE_FORBIDDEN"

    db.session.expire_all()
    assert Player.query.filter_by(first_name="Nueva").count() == 0
    assert db.session.get(Player, player.id).first_name != "Cambio"


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_edits_sports_profile_without_finance(
    client, world, auth_headers, mode
):
    coach = _coach_in_mode(world, mode)
    player = world.players_a[0]

    response = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(coach),
        json={
            "first_name": "Cambio",
            "last_name": "Perfil",
            "sex": "female",
            "main_position": player.main_position,
            "representative_name": "Representante",
            "representative_phone": "+58 412 0000000",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["player"]["first_name"] == "Cambio"
    assert _keys(response.get_json()) & FINANCE_KEYS == set()


def test_owner_player_finance_keeps_current_behavior(
    client, world, auth_headers
):
    player = world.players_a[0]

    response = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": player.first_name,
            "last_name": player.last_name,
            "sex": "female",
            "monthly_fee": 99,
        },
    )

    assert response.status_code == 200
    db.session.expire_all()
    assert db.session.get(Player, player.id).monthly_fee is None


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("fee", [100, 0, "25.00"])
def test_coach_cannot_create_match_with_fee(
    client, world, auth_headers, mode, fee
):
    coach = _coach_in_mode(world, mode)

    response = client.post(
        "/api/matches",
        headers=auth_headers(coach),
        json={
            "team_id": world.team_a.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
            "referee_fee": fee,
        },
    )

    assert response.status_code == 403
    assert _code(response) == "FINANCE_FORBIDDEN"
    assert MatchSession.query.count() == 0


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("payload", [{}, {"referee_fee": None}, {"referee_fee": ""}])
def test_coach_creates_match_without_fee(
    client, world, auth_headers, mode, payload
):
    coach = _coach_in_mode(world, mode)

    response = client.post(
        "/api/matches",
        headers=auth_headers(coach),
        json={
            "team_id": world.team_a.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
            **payload,
        },
    )

    assert response.status_code == 201
    assert _keys(response.get_json()) & FINANCE_KEYS == set()
    assert MatchSession.query.one().referee_fee is None


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_tournament_match_inherits_default_fee_without_seeing_it(
    client, world, auth_headers, mode
):
    coach = _coach_in_mode(world, mode)
    entry = _entry(world)
    entry.tournament.default_referee_fee = 30
    db.session.commit()

    response = client.post(
        "/api/matches",
        headers=auth_headers(coach),
        json={
            "team_id": world.team_a.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
            "tournament_team_id": entry.id,
        },
    )

    assert response.status_code == 201
    assert _keys(response.get_json()) & FINANCE_KEYS == set()
    assert float(MatchSession.query.one().referee_fee) == 30


def test_club_wide_coach_cannot_send_tournament_default_fee(
    client, world, auth_headers
):
    headers = auth_headers(world.coach_a)
    tournament = _tournament(world)
    tournament.default_referee_fee = 30
    db.session.commit()

    created = client.post(
        "/api/tournaments",
        headers=headers,
        json={
            "name": "Copa",
            "start_date": "2026-09-01",
            "default_referee_fee": 10,
        },
    )
    updated = client.put(
        f"/api/tournaments/{tournament.id}",
        headers=headers,
        json={"default_referee_fee": 10},
    )

    assert created.status_code == 403
    assert updated.status_code == 403
    assert _code(created) == "FINANCE_FORBIDDEN"
    assert _code(updated) == "FINANCE_FORBIDDEN"
    db.session.expire_all()
    assert Tournament.query.count() == 1
    assert float(Tournament.query.one().default_referee_fee) == 30


def test_scoped_coach_tournament_stays_owner_only(
    client, world, auth_headers
):
    coach = _coach_in_mode(world, "team_assigned")

    response = client.post(
        "/api/tournaments",
        headers=auth_headers(coach),
        json={"name": "Copa", "start_date": "2026-09-01"},
    )

    assert response.status_code == 403
    assert _code(response) == "FORBIDDEN"


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_enrolls_team_only_without_registration_fee(
    client, world, auth_headers, mode
):
    coach = _coach_in_mode(world, mode)
    tournament = _tournament(world)

    rejected = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        headers=auth_headers(coach),
        json={"team_id": world.team_a.id, "registration_fee": 50},
    )

    assert rejected.status_code == 403
    assert _code(rejected) == "FINANCE_FORBIDDEN"
    assert TournamentTeam.query.count() == 0

    enrolled = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        headers=auth_headers(coach),
        json={"team_id": world.team_a.id},
    )

    assert enrolled.status_code == 201
    assert _keys(enrolled.get_json()) & FINANCE_KEYS == set()
    assert float(TournamentTeam.query.one().registration_fee) == 0


def test_scoped_coach_finance_does_not_depend_on_assignment(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    _scope(world.club_a)
    _assign(world)
    headers = auth_headers(world.coach_a)

    for method, url, body in [
        ("get", f"/api/matches/{match.id}/referee-charges/preview", None),
        ("post", f"/api/matches/{match.id}/referee-charges", {}),
        ("put", f"/api/matches/{match.id}/referee-fee", {"referee_fee": 5}),
        (
            "get",
            f"/api/tournament-teams/{entry.id}/registration-charges/preview",
            None,
        ),
        ("post", f"/api/tournament-teams/{entry.id}/registration-charges", {}),
        (
            "put",
            f"/api/tournament-teams/{entry.id}/registration-fee",
            {"registration_fee": 5},
        ),
    ]:
        response = getattr(client, method)(url, headers=headers, json=body)

        assert response.status_code == 403, url
        assert _code(response) == "FINANCE_FORBIDDEN", url


def test_unassigned_team_stays_read_only_for_scoped_coach(
    client, world, auth_headers
):
    _scope(world.club_a)
    other = _team(world, "Otro")
    _assign(world, team=other)

    response = client.post(
        "/api/matches",
        headers=auth_headers(world.coach_a),
        json={
            "team_id": world.team_a.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
        },
    )

    assert response.status_code == 403
    assert _code(response) == "TEAM_NOT_ASSIGNED"


# =========================
# Cargos: Owner only
# =========================


@pytest.mark.parametrize("user_key", ["coach_a", "staff_a"])
def test_charge_generation_is_owner_only(
    client, world, auth_headers, match_factory, user_key
):
    match, _, entry = _money_scenario(world, match_factory)
    headers = auth_headers(getattr(world, user_key))
    before = _finance_state()

    for method, url in [
        ("get", f"/api/matches/{match.id}/referee-charges/preview"),
        ("post", f"/api/matches/{match.id}/referee-charges"),
        ("get", f"/api/tournament-teams/{entry.id}/registration-charges/preview"),
        ("post", f"/api/tournament-teams/{entry.id}/registration-charges"),
    ]:
        response = getattr(client, method)(url, headers=headers)

        assert response.status_code == 403, url
        assert _code(response) == "FINANCE_FORBIDDEN", url

    assert _finance_state() == before


def test_owner_generates_charges(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    headers = auth_headers(world.owner_a)

    preview = client.get(
        f"/api/matches/{match.id}/referee-charges/preview",
        headers=headers,
    )
    generated = client.post(
        f"/api/matches/{match.id}/referee-charges",
        headers=headers,
    )
    registration_preview = client.get(
        f"/api/tournament-teams/{entry.id}/registration-charges/preview",
        headers=headers,
    )
    registration = client.post(
        f"/api/tournament-teams/{entry.id}/registration-charges",
        headers=headers,
    )

    assert preview.status_code == 200
    assert generated.status_code == 201
    assert generated.get_json()["total_charges"] == len(world.players_a)
    assert registration_preview.status_code == 200
    assert registration.status_code == 201
    assert registration.get_json()["total_charges"] == 1


def test_staff_keeps_payments_and_charge_contexts(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    _referee_charge(world, match)
    headers = auth_headers(world.staff_a)

    payments = client.get("/api/payments", headers=headers)
    player_payments = client.get(
        f"/api/players/{world.players_a[0].id}/payments",
        headers=headers,
    )
    contexts = client.get(
        "/api/tournament-registration-charges",
        headers=headers,
    )
    sync_preview = client.get("/api/payments/sync-preview", headers=headers)

    assert payments.status_code == 200
    assert len(payments.get_json()["payments"]) == 1
    assert player_payments.status_code == 200
    assert contexts.status_code == 200
    assert contexts.get_json()["entries"][0]["tournament_team"]["registration_fee"] == 500
    assert sync_preview.status_code == 200


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_cannot_reach_payments_or_receipts(
    client, world, auth_headers, match_factory, mode
):
    match, _, entry = _money_scenario(world, match_factory)
    charge = _referee_charge(world, match)
    receipt = _receipt_for(world, charge)
    coach = _coach_in_mode(world, mode)
    headers = auth_headers(coach)
    player_id = world.players_a[0].id
    before = _finance_state()

    for method, url in [
        ("get", "/api/payments"),
        ("get", "/api/payments/sync-preview"),
        ("post", "/api/payments/sync"),
        ("put", f"/api/payments/{charge.id}"),
        ("get", f"/api/players/{player_id}/payments"),
        ("get", f"/api/players/{player_id}/payments/sync-preview"),
        ("post", f"/api/players/{player_id}/payments/sync"),
        ("put", f"/api/players/{player_id}/payment-settings"),
        ("post", f"/api/payments/{charge.id}/receipt"),
        ("post", f"/api/payment-receipts/{receipt.id}/repair-pdf"),
        ("post", f"/api/payment-receipts/{receipt.id}/share-events"),
        ("get", f"/api/payment-receipts/{receipt.id}/share-events"),
        ("put", f"/api/payment-receipts/{receipt.id}/share"),
        ("get", "/api/tournament-registration-charges"),
    ]:
        response = getattr(client, method)(url, headers=headers, json={})

        assert response.status_code == 403, url
        assert _code(response) == "FINANCE_FORBIDDEN", url

    assert _finance_state() == before


@pytest.mark.parametrize("user_key", ["owner_a", "staff_a"])
def test_owner_and_staff_keep_receipts(
    client, world, auth_headers, match_factory, monkeypatch, user_key
):
    # El recibo real genera un PDF: aquí no se genera el archivo.
    monkeypatch.setattr(
        receipt_service,
        "write_receipt_pdf_atomic",
        lambda receipt, allow_replace=False: (
            f"/uploads/receipts/{receipt.id}.pdf",
            f"/tmp/{receipt.id}.pdf",
        ),
    )
    match, _, _ = _money_scenario(world, match_factory)
    charge = _referee_charge(world, match, status="paid")
    charge.payment_date = date(2026, 11, 1)
    charge.payment_method = "cash"
    db.session.commit()
    headers = auth_headers(getattr(world, user_key))

    created = client.post(
        f"/api/payments/{charge.id}/receipt",
        headers=headers,
    )

    assert created.status_code == 200, created.get_json()
    receipt_id = created.get_json()["receipt"]["id"]
    assert created.get_json()["payment"]["id"] == charge.id

    events = client.get(
        f"/api/payment-receipts/{receipt_id}/share-events",
        headers=headers,
    )

    assert events.status_code == 200


def test_private_receipt_files_are_not_served_directly(client, world):
    response = client.get("/uploads/receipts/recibo.pdf")

    assert response.status_code == 404
    assert _code(response) == "RECEIPT_NOT_FOUND"


def test_public_receipt_link_stays_public_and_signed(client, world):
    response = client.get("/api/payment-receipts/public/token-falso")

    assert response.status_code == 404
    assert _code(response) == "RECEIPT_NOT_FOUND"


@pytest.mark.parametrize("action", ["suspend", "activate"])
def test_system_admin_club_responses_contain_no_fees(
    client, world, auth_headers, match_factory, action
):
    _money_scenario(world, match_factory)

    response = client.put(
        f"/api/admin/clubs/{world.club_a.id}/{action}",
        headers=auth_headers(world.system_admin),
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["club"]["name"] == world.club_a.name
    assert _keys(response.get_json()) & FINANCE_KEYS == set()


def test_system_admin_client_responses_contain_no_fees(
    client, world, auth_headers, match_factory
):
    _money_scenario(world, match_factory)
    headers = auth_headers(world.system_admin)

    listed = client.get("/api/admin/clients", headers=headers)

    assert listed.status_code == 200
    assert _keys(listed.get_json()) & FINANCE_KEYS == set()
    assert world.club_a.name in {
        row["club"]["name"] for row in listed.get_json()["clients"]
    }

    for action in ["deactivate", "activate"]:
        response = client.put(
            f"/api/admin/clients/{world.owner_a.id}/{action}",
            headers=headers,
        )

        assert response.status_code == 200, response.get_json()
        assert _keys(response.get_json()) & FINANCE_KEYS == set()


def test_system_admin_has_no_club_finance(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    headers = auth_headers(world.system_admin)

    payments = client.get("/api/payments", headers=headers)

    assert payments.status_code == 400
    assert _code(payments) == "CLUB_REQUIRED"

    for method, url, code in [
        ("get", f"/api/matches/{match.id}/referee-charges/preview", 404),
        ("put", f"/api/matches/{match.id}/referee-fee", 404),
        ("put", f"/api/tournament-teams/{entry.id}/registration-fee", 404),
        ("post", f"/api/tournament-teams/{entry.id}/registration-charges", 404),
    ]:
        response = getattr(client, method)(url, headers=headers, json={})

        assert response.status_code == code, url


# =========================
# Editores Owner
# =========================


def test_owner_sets_referee_fee_on_coach_match(
    client, world, auth_headers
):
    created = client.post(
        "/api/matches",
        headers=auth_headers(world.coach_a),
        json={
            "team_id": world.team_a.id,
            "date": "2026-11-20",
            "opponent_name": "Rival",
        },
    )
    match_id = created.get_json()["match"]["id"]

    response = client.put(
        f"/api/matches/{match_id}/referee-fee",
        headers=auth_headers(world.owner_a),
        json={"referee_fee": "60.50"},
    )

    assert response.status_code == 200
    assert response.get_json()["match"]["referee_fee"] == 60.5
    db.session.expire_all()
    assert float(MatchSession.query.get(match_id).referee_fee) == 60.5


@pytest.mark.parametrize(
    "fee, code",
    [
        (None, "INVALID_REFEREE_FEE"),
        ("", "INVALID_REFEREE_FEE"),
        (0, "INVALID_REFEREE_FEE"),
        (-1, "INVALID_AMOUNT"),
        ("abc", "INVALID_AMOUNT"),
        ("NaN", "INVALID_AMOUNT"),
    ],
)
def test_referee_fee_editor_validates_amount(
    client, world, auth_headers, match_factory, fee, code
):
    match = match_factory(world).match

    response = client.put(
        f"/api/matches/{match.id}/referee-fee",
        headers=auth_headers(world.owner_a),
        json={"referee_fee": fee},
    )

    assert response.status_code == 400
    assert _code(response) == code


def test_referee_fee_change_leaves_pending_charges_until_regenerated(
    client, world, auth_headers, match_factory
):
    match, _, _ = _money_scenario(world, match_factory)
    _referee_charge(world, match)
    before = _finance_state()

    response = client.put(
        f"/api/matches/{match.id}/referee-fee",
        headers=auth_headers(world.owner_a),
        json={"referee_fee": 90},
    )

    assert response.status_code == 200
    assert _finance_state() == before


@pytest.mark.parametrize("use_receipt", [False, True])
def test_referee_fee_is_locked_by_paid_or_receipt_charges(
    client, world, auth_headers, match_factory, use_receipt
):
    match, _, _ = _money_scenario(world, match_factory)
    charge = _referee_charge(
        world,
        match,
        status="pending" if use_receipt else "paid",
    )

    if use_receipt:
        _receipt_for(world, charge)

    before = _finance_state()

    response = client.put(
        f"/api/matches/{match.id}/referee-fee",
        headers=auth_headers(world.owner_a),
        json={"referee_fee": 90},
    )

    assert response.status_code == 409
    assert _code(response) == "REFEREE_CHARGES_LOCKED"
    assert _finance_state() == before
    db.session.expire_all()
    assert float(MatchSession.query.get(match.id).referee_fee) == 60


def test_owner_edits_tournament_default_fee(
    client, world, auth_headers
):
    tournament = _tournament(world)

    response = client.put(
        f"/api/tournaments/{tournament.id}",
        headers=auth_headers(world.owner_a),
        json={"default_referee_fee": 45},
    )

    assert response.status_code == 200
    assert response.get_json()["tournament"]["default_referee_fee"] == 45


def test_owner_sets_registration_fee_then_generates(
    client, world, auth_headers
):
    entry = _entry(world)
    _register(world, entry, world.players_a[:2])
    headers = auth_headers(world.owner_a)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/registration-fee",
        headers=headers,
        json={"registration_fee": 100},
    )

    assert response.status_code == 200
    assert response.get_json()["tournament_team"]["registration_fee"] == 100

    generated = client.post(
        f"/api/tournament-teams/{entry.id}/registration-charges",
        headers=headers,
    )

    assert generated.status_code == 201
    assert sorted(
        charge["amount"] for charge in generated.get_json()["charges"]
    ) == [50, 50]


@pytest.mark.parametrize(
    "fee, code",
    [
        (None, "INVALID_TOURNAMENT_REGISTRATION_FEE"),
        (0, "INVALID_TOURNAMENT_REGISTRATION_FEE"),
        (-1, "INVALID_AMOUNT"),
    ],
)
def test_registration_fee_editor_validates_amount(
    client, world, auth_headers, fee, code
):
    entry = _entry(world)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/registration-fee",
        headers=auth_headers(world.owner_a),
        json={"registration_fee": fee},
    )

    assert response.status_code == 400
    assert _code(response) == code


def test_registration_fee_is_locked_by_paid_charges(
    client, world, auth_headers
):
    entry = _entry(world)
    _registration_charge(world, entry, status="paid")
    before = _finance_state()

    response = client.put(
        f"/api/tournament-teams/{entry.id}/registration-fee",
        headers=auth_headers(world.owner_a),
        json={"registration_fee": 100},
    )

    assert response.status_code == 409
    assert _code(response) == "TOURNAMENT_REGISTRATION_CHARGES_LOCKED"
    assert _finance_state() == before


@pytest.mark.parametrize("target", ["tournament", "entry"])
def test_registration_fee_requires_active_participation(
    client, world, auth_headers, target
):
    entry = _entry(world)

    if target == "tournament":
        entry.tournament.status = "completed"
    else:
        entry.status = "withdrawn"

    db.session.commit()

    response = client.put(
        f"/api/tournament-teams/{entry.id}/registration-fee",
        headers=auth_headers(world.owner_a),
        json={"registration_fee": 100},
    )

    assert response.status_code == 409


def test_staff_cannot_edit_source_fees(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    headers = auth_headers(world.staff_a)

    for url, body in [
        (f"/api/matches/{match.id}/referee-fee", {"referee_fee": 5}),
        (
            f"/api/tournament-teams/{entry.id}/registration-fee",
            {"registration_fee": 5},
        ),
    ]:
        response = client.put(url, headers=headers, json=body)

        assert response.status_code == 403
        assert _code(response) == "FINANCE_FORBIDDEN"

    staff_tournament = client.put(
        f"/api/tournaments/{entry.tournament_id}",
        headers=headers,
        json={"default_referee_fee": 5},
    )

    assert staff_tournament.status_code == 403

    db.session.expire_all()
    assert float(MatchSession.query.get(match.id).referee_fee) == 60
    assert float(TournamentTeam.query.get(entry.id).registration_fee) == 500


# =========================
# Roster de partido y cargos
# =========================


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("status", ["pending", "overdue", "paid"])
def test_coach_roster_removal_is_blocked_by_referee_charge(
    client, world, auth_headers, match_factory, mode, status
):
    match, _, _ = _money_scenario(world, match_factory)
    _referee_charge(world, match, status=status)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _match_roster_state(match)

    response = client.post(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(coach),
        json={"players": _called_ids(world, without=[world.players_a[0]])},
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    message = response.get_json()["message"]
    assert "player_payment" not in message.lower()
    assert _finance_state() == finance_before
    assert _match_roster_state(match) == sports_before


def test_coach_roster_removal_is_blocked_by_receipt_history(
    client, world, auth_headers, match_factory
):
    match, _, _ = _money_scenario(world, match_factory)
    charge = _referee_charge(world, match, status="cancelled")
    _receipt_for(world, charge)
    before = _finance_state()

    response = client.post(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(world.coach_a),
        json={"players": _called_ids(world, without=[world.players_a[0]])},
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == before


def _rostered_match(world, match_factory, called=5):
    """Cinco convocadas y el resto disponible para entrar."""
    created = match_factory(world)
    created.match.referee_fee = 60
    created.match.match_step = 1

    for row in created.rows[called:]:
        row.is_called = False
        row.attendance_status = None
        row.position = None

    db.session.commit()
    return created.match


def _changed_roster(world, change, size=5):
    current = [player.id for player in world.players_a[:size]]
    spare = world.players_a[size].id

    # La primera tiene el cargo; quien entra o sale es siempre otra persona.
    return {
        "add": [*current, spare],
        "remove_uncharged": current[:-1],
        "swap": [*current[:-1], spare],
    }[change]


def _save_match_roster(client, auth_headers, user, match, player_ids):
    return client.post(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(user),
        json={"players": [{"player_id": pid} for pid in player_ids]},
    )


def _called_set(match):
    db.session.expire_all()
    return {
        row.player_id
        for row in MatchPlayer.query.filter_by(
            match_id=match.id,
            is_called=True
        ).all()
    }


ROSTER_CHANGES = ["add", "remove_uncharged", "swap"]
BLOCKING_STATUSES = ["pending", "overdue", "paid"]


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
def test_coach_match_roster_change_without_charges_works(
    client, world, auth_headers, match_factory, mode, change
):
    match = _rostered_match(world, match_factory)
    coach = _coach_in_mode(world, mode)
    target = _changed_roster(world, change)

    response = _save_match_roster(client, auth_headers, coach, match, target)

    assert response.status_code == 200
    assert _called_set(match) == set(target)


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
@pytest.mark.parametrize("status", BLOCKING_STATUSES)
def test_coach_match_roster_change_is_blocked_by_any_charge(
    client, world, auth_headers, match_factory, mode, change, status
):
    match = _rostered_match(world, match_factory)
    _referee_charge(world, match, status=status)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _match_roster_state(match)

    response = _save_match_roster(
        client,
        auth_headers,
        coach,
        match,
        _changed_roster(world, change),
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before
    assert _match_roster_state(match) == sports_before


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
def test_coach_match_roster_is_free_with_only_cancelled_charge(
    client, world, auth_headers, match_factory, mode, change
):
    match = _rostered_match(world, match_factory)
    _referee_charge(world, match, status="cancelled")
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    target = _changed_roster(world, change)

    response = _save_match_roster(client, auth_headers, coach, match, target)

    assert response.status_code == 200
    assert _called_set(match) == set(target)
    assert _finance_state() == finance_before


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
def test_coach_match_roster_is_blocked_by_cancelled_charge_with_receipt(
    client, world, auth_headers, match_factory, mode, change
):
    match = _rostered_match(world, match_factory)
    charge = _referee_charge(world, match, status="cancelled")
    _receipt_for(world, charge)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _match_roster_state(match)

    response = _save_match_roster(
        client,
        auth_headers,
        coach,
        match,
        _changed_roster(world, change),
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before
    assert _match_roster_state(match) == sports_before


def test_coach_match_cancelled_charge_does_not_hide_other_blocking_charge(
    client, world, auth_headers, match_factory
):
    match = _rostered_match(world, match_factory)
    _referee_charge(world, match, status="cancelled")
    _referee_charge(world, match, player=world.players_a[1])
    finance_before = _finance_state()

    response = _save_match_roster(
        client,
        auth_headers,
        world.coach_a,
        match,
        _changed_roster(world, "add"),
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_saving_same_match_roster_is_not_blocked_by_charges(
    client, world, auth_headers, match_factory, mode
):
    match = _rostered_match(world, match_factory)
    _referee_charge(world, match, status="paid")
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    called = [player.id for player in world.players_a[:5]]

    response = _save_match_roster(client, auth_headers, coach, match, called)

    assert response.status_code == 200
    assert _called_set(match) == set(called)
    assert _finance_state() == finance_before


def test_completed_match_keeps_sports_error_for_coach(
    client, world, auth_headers, match_factory
):
    match = _rostered_match(world, match_factory)
    match.is_completed = True
    db.session.commit()
    _referee_charge(world, match)

    response = _save_match_roster(
        client,
        auth_headers,
        world.coach_a,
        match,
        _changed_roster(world, "add"),
    )

    assert response.status_code == 409
    assert _code(response) == "MATCH_COMPLETED"


@pytest.mark.parametrize("change", ROSTER_CHANGES)
@pytest.mark.parametrize("status", BLOCKING_STATUSES)
def test_owner_match_roster_change_keeps_current_flow(
    client, world, auth_headers, match_factory, change, status
):
    match = _rostered_match(world, match_factory)
    charge = _referee_charge(world, match, status=status)
    target = _changed_roster(world, change)
    finance_before = _finance_state()

    response = _save_match_roster(
        client,
        auth_headers,
        world.owner_a,
        match,
        target,
    )

    assert response.status_code == 200
    assert _called_set(match) == set(target)
    assert _finance_state() == finance_before
    assert db.session.get(PlayerPayment, charge.id).status == status


def test_coach_roster_removal_leaves_cancelled_charge_untouched(
    client, world, auth_headers, match_factory
):
    match, _, _ = _money_scenario(world, match_factory)
    _referee_charge(world, match, status="cancelled")
    before = _finance_state()

    response = client.post(
        f"/api/matches/{match.id}/roster",
        headers=auth_headers(world.coach_a),
        json={"players": _called_ids(world, without=[world.players_a[0]])},
    )

    assert response.status_code == 200
    assert _finance_state() == before


def test_owner_roster_removal_keeps_current_finance_flow(
    client, world, auth_headers, match_factory
):
    match, _, _ = _money_scenario(world, match_factory)
    _referee_charge(world, match, player=world.players_a[0])
    paid = _referee_charge(
        world,
        match,
        player=world.players_a[1],
        status="paid",
    )
    headers = auth_headers(world.owner_a)

    locked = client.post(
        f"/api/matches/{match.id}/roster",
        headers=headers,
        json={"players": _called_ids(world, without=[world.players_a[1]])},
    )

    assert locked.status_code == 409
    assert _code(locked) == "MATCH_ROSTER_FINANCIALLY_LOCKED"

    removed = client.post(
        f"/api/matches/{match.id}/roster",
        headers=headers,
        json={"players": _called_ids(world, without=[world.players_a[0]])},
    )

    assert removed.status_code == 200
    db.session.expire_all()
    remaining = PlayerPayment.query.filter_by(match_id=match.id).all()
    assert [charge.id for charge in remaining] == [paid.id]


def test_owner_cannot_regenerate_over_paid_referee_charge(
    client, world, auth_headers, match_factory
):
    match, _, _ = _money_scenario(world, match_factory)
    charge = _referee_charge(world, match, status="paid")
    receipt = _receipt_for(world, charge)
    before = _finance_state()

    response = client.post(
        f"/api/matches/{match.id}/referee-charges",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert _code(response) == "REFEREE_CHARGES_LOCKED"
    assert _finance_state() == before
    db.session.expire_all()
    assert PaymentReceipt.query.get(receipt.id).payment_id == charge.id


# =========================
# Roster de torneo y cargos
# =========================


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("status", ["pending", "overdue", "paid"])
def test_coach_tournament_removal_is_blocked_by_registration_charge(
    client, world, auth_headers, mode, status
):
    entry = _entry(world)
    _register(world, entry, world.players_a[:2])
    _registration_charge(world, entry, status=status)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _tournament_roster_state(entry)

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(coach),
        json={"player_ids": [world.players_a[1].id]},
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before
    assert _tournament_roster_state(entry) == sports_before


def _rostered_entry(world):
    """Cinco inscritas y el resto del equipo disponible para entrar."""
    entry = _entry(world)
    entry.registration_fee = 600
    _register(world, entry, world.players_a[:5])
    return entry


def _save_entry_roster(client, auth_headers, user, entry, player_ids):
    return client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(user),
        json={"player_ids": player_ids},
    )


def _active_set(entry):
    db.session.expire_all()
    return {
        row.player_id
        for row in TournamentPlayer.query.filter_by(
            tournament_team_id=entry.id,
            status="active"
        ).all()
    }


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
def test_coach_tournament_roster_change_without_charges_works(
    client, world, auth_headers, mode, change
):
    entry = _rostered_entry(world)
    coach = _coach_in_mode(world, mode)
    target = _changed_roster(world, change)

    response = _save_entry_roster(client, auth_headers, coach, entry, target)

    assert response.status_code == 200
    assert _keys(response.get_json()) & FINANCE_KEYS == set()
    assert _active_set(entry) == set(target)


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
@pytest.mark.parametrize("status", BLOCKING_STATUSES)
def test_coach_tournament_roster_change_is_blocked_by_any_charge(
    client, world, auth_headers, mode, change, status
):
    entry = _rostered_entry(world)
    _registration_charge(world, entry, status=status)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _tournament_roster_state(entry)

    response = _save_entry_roster(
        client,
        auth_headers,
        coach,
        entry,
        _changed_roster(world, change),
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before
    assert _tournament_roster_state(entry) == sports_before


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_cannot_reactivate_withdrawn_registration_after_charges(
    client, world, auth_headers, mode
):
    entry = _rostered_entry(world)
    TournamentPlayer.query.filter_by(
        tournament_team_id=entry.id,
        player_id=world.players_a[4].id,
    ).one().status = "withdrawn"
    db.session.commit()
    _registration_charge(world, entry)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _tournament_roster_state(entry)

    response = _save_entry_roster(
        client,
        auth_headers,
        coach,
        entry,
        [player.id for player in world.players_a[:5]],
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before
    assert _tournament_roster_state(entry) == sports_before


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
def test_coach_tournament_roster_is_free_with_only_cancelled_charge(
    client, world, auth_headers, mode, change
):
    entry = _rostered_entry(world)
    _registration_charge(world, entry, status="cancelled")
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    target = _changed_roster(world, change)

    response = _save_entry_roster(client, auth_headers, coach, entry, target)

    assert response.status_code == 200
    assert _active_set(entry) == set(target)
    assert _finance_state() == finance_before


@pytest.mark.parametrize("mode", COACH_MODES)
@pytest.mark.parametrize("change", ROSTER_CHANGES)
def test_coach_tournament_roster_is_blocked_by_cancelled_charge_with_receipt(
    client, world, auth_headers, mode, change
):
    entry = _rostered_entry(world)
    charge = _registration_charge(world, entry, status="cancelled")
    _receipt_for(world, charge)
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    sports_before = _tournament_roster_state(entry)

    response = _save_entry_roster(
        client,
        auth_headers,
        coach,
        entry,
        _changed_roster(world, change),
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before
    assert _tournament_roster_state(entry) == sports_before


def test_coach_tournament_cancelled_charge_does_not_hide_other_blocking_charge(
    client, world, auth_headers
):
    entry = _rostered_entry(world)
    _registration_charge(world, entry, status="cancelled")
    _registration_charge(world, entry, player=world.players_a[1])
    finance_before = _finance_state()

    response = _save_entry_roster(
        client,
        auth_headers,
        world.coach_a,
        entry,
        _changed_roster(world, "add"),
    )

    assert response.status_code == 409
    assert _code(response) == "FINANCE_DEPENDENCY"
    assert _finance_state() == finance_before


@pytest.mark.parametrize("mode", COACH_MODES)
def test_coach_saving_same_tournament_roster_is_not_blocked_by_charges(
    client, world, auth_headers, mode
):
    entry = _rostered_entry(world)
    _registration_charge(world, entry, status="paid")
    coach = _coach_in_mode(world, mode)
    finance_before = _finance_state()
    current = [player.id for player in world.players_a[:5]]

    response = _save_entry_roster(client, auth_headers, coach, entry, current)

    assert response.status_code == 200
    assert _active_set(entry) == set(current)
    assert _finance_state() == finance_before


@pytest.mark.parametrize("change", ROSTER_CHANGES)
@pytest.mark.parametrize("status", BLOCKING_STATUSES)
def test_owner_tournament_roster_change_keeps_current_flow(
    client, world, auth_headers, change, status
):
    entry = _rostered_entry(world)
    charge = _registration_charge(world, entry, status=status)
    target = _changed_roster(world, change)
    finance_before = _finance_state()

    response = _save_entry_roster(
        client,
        auth_headers,
        world.owner_a,
        entry,
        target,
    )

    assert response.status_code == 200
    assert _active_set(entry) == set(target)
    assert _finance_state() == finance_before
    assert db.session.get(PlayerPayment, charge.id).status == status


def test_coach_tournament_removal_leaves_cancelled_charge_untouched(
    client, world, auth_headers
):
    entry = _entry(world)
    _register(world, entry, world.players_a[:2])
    _registration_charge(world, entry, status="cancelled")
    before = _finance_state()

    response = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=auth_headers(world.coach_a),
        json={"player_ids": [world.players_a[1].id]},
    )

    assert response.status_code == 200
    assert _finance_state() == before


def test_owner_tournament_removal_keeps_current_finance_flow(
    client, world, auth_headers
):
    entry = _entry(world)
    _register(world, entry, world.players_a[:2])
    _registration_charge(world, entry, player=world.players_a[0])
    paid = _registration_charge(
        world,
        entry,
        player=world.players_a[1],
        status="paid",
    )
    headers = auth_headers(world.owner_a)

    locked = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=headers,
        json={"player_ids": [world.players_a[0].id]},
    )

    assert locked.status_code == 409
    assert _code(locked) == "TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED"

    removed = client.put(
        f"/api/tournament-teams/{entry.id}/players",
        headers=headers,
        json={"player_ids": [world.players_a[1].id]},
    )

    assert removed.status_code == 200
    db.session.expire_all()
    remaining = PlayerPayment.query.filter_by(tournament_team_id=entry.id).all()
    assert [charge.id for charge in remaining] == [paid.id]


# =========================
# Tenant primero
# =========================


def test_cross_tenant_reveals_no_finance_or_dependency(
    client, world, auth_headers, match_factory
):
    match, _, entry = _money_scenario(world, match_factory)
    _referee_charge(world, match)
    _registration_charge(world, entry)
    before = _finance_state()

    for user in [world.coach_b, world.owner_b]:
        headers = auth_headers(user)

        for method, url, body in [
            ("put", f"/api/matches/{match.id}/referee-fee", {"referee_fee": 5}),
            ("get", f"/api/matches/{match.id}/referee-charges/preview", None),
            ("post", f"/api/matches/{match.id}/referee-charges", {}),
            (
                "put",
                f"/api/tournament-teams/{entry.id}/registration-fee",
                {"registration_fee": 5},
            ),
            (
                "get",
                f"/api/tournament-teams/{entry.id}/registration-charges/preview",
                None,
            ),
            ("post", f"/api/tournament-teams/{entry.id}/registration-charges", {}),
        ]:
            response = getattr(client, method)(url, headers=headers, json=body)

            assert response.status_code == 404, url
            assert _keys(response.get_json()) & FINANCE_KEYS == set(), url

        roster = client.post(
            f"/api/matches/{match.id}/roster",
            headers=headers,
            json={"players": []},
        )
        tournament_roster = client.put(
            f"/api/tournament-teams/{entry.id}/players",
            headers=headers,
            json={"player_ids": []},
        )

        assert roster.status_code == 403
        assert _code(roster) == "FORBIDDEN"
        assert tournament_roster.status_code == 403
        assert _code(tournament_roster) == "FORBIDDEN"

    assert _finance_state() == before
