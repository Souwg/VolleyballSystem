"""FASE 5.4A: inscripción única, transición de temporada y rotación de refresh.

Las carreras reales se validan sobre PostgreSQL; aquí se fijan las reglas
deterministas que las sostienen.
"""
from datetime import date, datetime, timedelta

import pytest
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from sqlalchemy.exc import IntegrityError

import src.api.endpoints.auth as auth_endpoints
import src.api.endpoints.payments as payment_endpoints
from src.api import season_service
from src.api.models import (
    PlayerPayment,
    RefreshToken,
    Season,
    Team,
    TokenBlockedList,
    User,
    db,
)
from src.api.time_utils import get_club_today


def _settings_body(world, mode):
    today = get_club_today(world.club_a)
    bodies = {
        "pending": {
            "enrollment_date": (today + timedelta(days=20)).isoformat(),
            "initial_payment_mode": "start_now",
            "initial_enrollment_status": "pending",
        },
        "overdue": {
            "enrollment_date": (today - timedelta(days=10)).isoformat(),
            "initial_payment_mode": "start_now",
            "initial_enrollment_status": "pending",
        },
        "migrated": {
            "enrollment_date": (today + timedelta(days=25)).isoformat(),
            "initial_payment_mode": "start_now",
            "initial_enrollment_status": "paid_before_sportflow",
        },
        "history": {
            "enrollment_date": (today - timedelta(days=70)).isoformat(),
            "initial_payment_mode": "import_history",
            "initial_enrollment_status": "paid_before_sportflow",
            "last_paid_month": (today - timedelta(days=35)).strftime("%Y-%m"),
        },
    }
    return {**bodies[mode], "enrollment_fee": 15, "monthly_fee": 30}


def _payment_rows(player_id):
    return sorted(
        (payment.payment_type, payment.status, payment.period_start)
        for payment in PlayerPayment.query.filter_by(player_id=player_id).all()
    )


# =====================================================
# SEC-001 — una sola inscripción por jugadora
# =====================================================

@pytest.mark.parametrize("mode", ["pending", "overdue", "migrated", "history"])
def test_payment_settings_retry_keeps_one_enrollment(
    client, world, auth_headers, mode
):
    player = world.players_a[0]
    body = _settings_body(world, mode)
    url = f"/api/players/{player.id}/payment-settings"

    first = client.put(url, headers=auth_headers(world.staff_a), json=body)
    after_first = _payment_rows(player.id)
    retry = client.put(url, headers=auth_headers(world.owner_a), json=body)

    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.get_json()["message"] == (
        "Configuración de pagos actualizada correctamente"
    )
    assert _payment_rows(player.id) == after_first
    assert PlayerPayment.query.filter_by(
        player_id=player.id,
        payment_type="enrollment",
    ).count() == 1


def test_database_rejects_second_enrollment_charge(world):
    player = world.players_a[0]

    for _ in range(2):
        db.session.add(PlayerPayment(
            club_id=world.club_a.id,
            player_id=player.id,
            payment_type="enrollment",
            amount=15,
            currency_code="USD",
            status="pending",
        ))

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_enrollment_conflict_is_controlled_and_rolled_back(
    client, world, auth_headers, monkeypatch
):
    player = world.players_a[0]
    original = payment_endpoints.initialize_player_payment_history

    def with_concurrent_enrollment(*args, **kwargs):
        db.session.add(PlayerPayment(
            club_id=world.club_a.id,
            player_id=player.id,
            payment_type="enrollment",
            amount=15,
            currency_code="USD",
            status="pending",
        ))
        db.session.flush()
        return original(*args, **kwargs)

    monkeypatch.setattr(
        payment_endpoints,
        "initialize_player_payment_history",
        with_concurrent_enrollment,
    )

    response = client.put(
        f"/api/players/{player.id}/payment-settings",
        headers=auth_headers(world.staff_a),
        json=_settings_body(world, "pending"),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "PAYMENT_SETTINGS_CONFLICT"
    db.session.expire_all()
    assert PlayerPayment.query.filter_by(player_id=player.id).count() == 0
    assert db.session.get(
        type(player),
        player.id,
    ).payment_control_start_date is None


def test_payment_settings_other_club_player_is_not_found(
    client, world, auth_headers
):
    player = world.players_a[0]

    response = client.put(
        f"/api/players/{player.id}/payment-settings",
        headers=auth_headers(world.owner_b),
        json=_settings_body(world, "pending"),
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "PLAYER_NOT_FOUND"
    assert PlayerPayment.query.filter_by(player_id=player.id).count() == 0


def test_payment_settings_edit_keeps_monthly_history(
    client, world, auth_headers
):
    player = world.players_a[0]
    url = f"/api/players/{player.id}/payment-settings"
    body = _settings_body(world, "history")

    assert client.put(
        url,
        headers=auth_headers(world.staff_a),
        json=body,
    ).status_code == 200
    before = _payment_rows(player.id)

    response = client.put(
        url,
        headers=auth_headers(world.staff_a),
        json={**body, "monthly_fee": 45},
    )

    assert response.status_code == 200
    assert _payment_rows(player.id) == before


# =====================================================
# SEC-002 — temporada activa resuelta bajo lock
# =====================================================

def test_active_season_lock_resolves_again_after_transition(
    world, monkeypatch
):
    closed = world.season_a
    closed.status = "closed"
    successor = Season(
        name="Temporada siguiente",
        start_date=date(2027, 1, 1),
        status="active",
        club=world.club_a,
        created_by=world.owner_a.id,
    )
    db.session.add(successor)
    db.session.commit()

    lookups = []
    resolve = season_service.get_active_season_for_club

    def stale_then_fresh(club_id):
        lookups.append(club_id)
        return closed if len(lookups) == 1 else resolve(club_id)

    monkeypatch.setattr(
        season_service,
        "get_active_season_for_club",
        stale_then_fresh,
    )

    season = season_service.lock_active_season_for_operation(world.club_a.id)

    assert season.id == successor.id
    assert len(lookups) == 2


def test_team_lifecycle_lock_rereads_season(world):
    team_id = world.team_a.id
    db.session.execute(
        Season.__table__.update()
        .where(Season.id == world.season_a.id)
        .values(status="closed")
    )

    team = season_service.lock_team_lifecycle(team_id, world.club_a.id)

    assert team.id == team_id
    assert team.season.status == "closed"
    assert season_service.lock_team_lifecycle(
        team_id,
        world.club_b.id,
    ) is None


def test_tournament_after_transition_uses_new_active_season(
    client, world, auth_headers
):
    planned = Season(
        name="Temporada siguiente",
        start_date=date(2027, 1, 1),
        status="planned",
        club=world.club_a,
        created_by=world.owner_a.id,
    )
    db.session.add(planned)
    db.session.add(Team(
        name="Team A 2027",
        gender="female",
        category=world.category_a,
        club=world.club_a,
        season=planned,
    ))
    db.session.commit()

    transition = client.post(
        f"/api/seasons/{planned.id}/transition",
        headers=auth_headers(world.owner_a),
        json={"source_season_id": world.season_a.id},
    )
    created = client.post(
        "/api/tournaments",
        headers=auth_headers(world.owner_a),
        json={
            "name": "Copa",
            "start_date": "2027-02-01",
            "end_date": "2027-02-03",
        },
    )

    assert transition.status_code == 200
    assert created.status_code == 201
    assert created.get_json()["tournament"]["season_id"] == planned.id


# =====================================================
# SEC-003 — refresh de un solo uso y logout robusto
# =====================================================

def _issue_session(user):
    claims = {"session_version": user.session_version}
    access = create_access_token(identity=user.id, additional_claims=claims)
    refresh = create_refresh_token(identity=user.id, additional_claims=claims)
    db.session.add(RefreshToken(
        user_id=user.id,
        jti=decode_token(refresh)["jti"],
        expires_at=datetime.utcnow() + timedelta(days=7),
    ))
    db.session.commit()
    return access, refresh


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_refresh_token_is_single_use(client, world):
    _, refresh = _issue_session(world.coach_a)

    first = client.post("/api/refresh", headers=_bearer(refresh))
    reuse = client.post("/api/refresh", headers=_bearer(refresh))

    assert first.status_code == 200
    assert reuse.status_code == 401
    assert reuse.get_json()["code"] == "REFRESH_REVOKED"
    assert RefreshToken.query.filter_by(
        user_id=world.coach_a.id,
        revoked=False,
    ).count() == 1


def test_refresh_that_loses_consumption_issues_nothing(
    client, world, monkeypatch
):
    _, refresh = _issue_session(world.coach_a)
    jti = decode_token(refresh)["jti"]
    original = auth_endpoints.ensure_club_access

    def consumed_meanwhile(user):
        # Otra request consumió el mismo refresh entre la verificación del JWT
        # y el UPDATE condicional.
        RefreshToken.query.filter_by(jti=jti).update({"revoked": True})
        return original(user)

    monkeypatch.setattr(
        auth_endpoints,
        "ensure_club_access",
        consumed_meanwhile,
    )

    response = client.post("/api/refresh", headers=_bearer(refresh))

    assert response.status_code == 401
    assert response.get_json()["code"] == "REFRESH_REVOKED"
    assert "token" not in response.get_json()
    assert RefreshToken.query.filter_by(user_id=world.coach_a.id).count() == 1


def test_logout_closes_every_session_immediately(client, world):
    user_id = world.coach_a.id
    access_a, refresh_a = _issue_session(world.coach_a)
    access_b, refresh_b = _issue_session(world.coach_a)

    response = client.post("/api/logout", headers=_bearer(access_a))

    assert response.status_code == 200
    assert db.session.get(User, user_id).session_version == 1
    assert TokenBlockedList.query.count() == 1
    assert client.get("/api/teams", headers=_bearer(access_b)).status_code == 401
    assert client.post("/api/refresh", headers=_bearer(refresh_a)).status_code == 401
    assert client.post("/api/refresh", headers=_bearer(refresh_b)).status_code == 401


def test_tokens_minted_before_logout_do_not_survive_it(client, world):
    access, refresh = _issue_session(world.coach_a)
    rotated = client.post("/api/refresh", headers=_bearer(refresh)).get_json()

    assert client.post("/api/logout", headers=_bearer(access)).status_code == 200
    assert client.get(
        "/api/teams",
        headers=_bearer(rotated["token"]),
    ).status_code == 401
    assert client.post(
        "/api/refresh",
        headers=_bearer(rotated["refresh"]),
    ).status_code == 401
