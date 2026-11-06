"""FASE 5.4C1: recibos privados, cabeceras/CORS, torneos, bordes de lifecycle y logs.

Las carreras reales (completar torneo vs inscribir) se validan sobre PostgreSQL;
aquí se fijan las reglas deterministas y el orden de los locks.
"""
import os
import subprocess
import sys
import uuid
from datetime import date, time, timedelta

import pytest
import resend
from sqlalchemy import text
from sqlalchemy.orm import Query

import src.api.endpoints.auth as auth_endpoints
import src.app as app_module
from src.api import receipt_service
from src.api.models import (
    AdministrativeArea,
    Attendance,
    Country,
    PaymentReceipt,
    PlayerPayment,
    Team,
    Tournament,
    TournamentTeam,
    TrainingPlayer,
    TrainingSession,
    db,
)
from src.api.training_service import sync_training_roster


REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))


def _paid_payment(world, player=None):
    payment = PlayerPayment(
        club_id=world.club_a.id,
        player_id=(player or world.players_a[0]).id,
        payment_type="extra",
        amount=10,
        currency_code="USD",
        status="paid",
        payment_method="cash",
        payment_date=date.today() - timedelta(days=1),
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def _issue_receipt(client, auth_headers, world):
    payment = _paid_payment(world)
    response = client.post(
        f"/api/payments/{payment.id}/receipt",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["receipt"]


def _is_pdf(response):
    return response.get_data()[:5] == b"%PDF-"


# =====================================================
# SEC-008 — almacenamiento privado de recibos
# =====================================================

def test_new_receipt_is_stored_outside_public(app, client, world, auth_headers):
    receipt = _issue_receipt(client, auth_headers, world)
    filename = os.path.basename(receipt["pdf_url"])
    private_root = app.config["PRIVATE_RECEIPT_ROOT"]
    public_root = os.path.realpath(os.path.join(REPO_ROOT, "public"))

    assert os.path.isfile(os.path.join(private_root, filename))
    assert os.path.commonpath([private_root, public_root]) != public_root
    assert not os.path.exists(
        os.path.join(receipt_service.get_legacy_receipts_folder(), filename)
    )


@pytest.mark.parametrize("user_key", ["owner_a", "staff_a"])
def test_finance_users_download_receipt_through_api(
    client, world, auth_headers, user_key
):
    receipt = _issue_receipt(client, auth_headers, world)

    response = client.get(
        f"/api/payment-receipts/{receipt['id']}/pdf",
        headers=auth_headers(getattr(world, user_key)),
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert _is_pdf(response)
    assert "no-store" in response.headers["Cache-Control"]


def test_receipt_download_is_denied_to_coach_other_club_and_anonymous(
    client, world, auth_headers
):
    receipt = _issue_receipt(client, auth_headers, world)
    url = f"/api/payment-receipts/{receipt['id']}/pdf"

    coach = client.get(url, headers=auth_headers(world.coach_a))
    other_club = client.get(url, headers=auth_headers(world.owner_b))
    anonymous = client.get(url)

    assert coach.status_code == 403
    assert coach.get_json()["code"] == "FINANCE_FORBIDDEN"
    assert other_club.status_code == 404
    assert other_club.get_json()["code"] == "RECEIPT_NOT_FOUND"
    assert anonymous.status_code == 401
    assert not any(_is_pdf(r) for r in (coach, other_club, anonymous))


def test_public_signed_link_serves_private_receipt(client, world, auth_headers):
    receipt = _issue_receipt(client, auth_headers, world)

    valid = client.get(receipt["share_url"])
    invalid = client.get("/api/payment-receipts/public/token-invalido")

    assert valid.status_code == 200
    assert _is_pdf(valid)
    assert invalid.status_code == 404
    assert invalid.get_json()["code"] == "RECEIPT_NOT_FOUND"


@pytest.fixture
def legacy_receipt(app, client, world, auth_headers, tmp_path, monkeypatch):
    """Recibo emitido antes del almacenamiento privado: su PDF vive en public/."""
    legacy_folder = tmp_path / "legacy_receipts"
    legacy_folder.mkdir()
    monkeypatch.setattr(
        receipt_service,
        "get_legacy_receipts_folder",
        lambda: str(legacy_folder),
    )
    receipt = _issue_receipt(client, auth_headers, world)
    filename = os.path.basename(receipt["pdf_url"])
    private_file = os.path.join(app.config["PRIVATE_RECEIPT_ROOT"], filename)
    legacy_file = legacy_folder / filename
    legacy_file.write_bytes(open(private_file, "rb").read())
    os.remove(private_file)
    return receipt, private_file, legacy_file


def test_legacy_receipt_is_served_only_through_endpoints(
    client, world, auth_headers, legacy_receipt
):
    receipt, private_file, legacy_file = legacy_receipt

    download = client.get(
        f"/api/payment-receipts/{receipt['id']}/pdf",
        headers=auth_headers(world.owner_a),
    )
    public = client.get(receipt["share_url"])

    assert download.status_code == 200 and _is_pdf(download)
    assert public.status_code == 200 and _is_pdf(public)
    # El legacy no se regenera ni se mueve al almacenamiento privado.
    assert legacy_file.exists()
    assert not os.path.exists(private_file)


def test_missing_pdf_is_rebuilt_in_private_storage_on_download(
    app, client, world, auth_headers
):
    receipt = _issue_receipt(client, auth_headers, world)
    private_file = os.path.join(
        app.config["PRIVATE_RECEIPT_ROOT"],
        os.path.basename(receipt["pdf_url"]),
    )
    os.remove(private_file)

    response = client.get(
        f"/api/payment-receipts/{receipt['id']}/pdf",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert os.path.isfile(private_file)
    assert PaymentReceipt.query.count() == 1


STATIC_RECEIPT_VARIANTS = [
    "/uploads/receipts/{f}",
    "/UPLOADS/receipts/{f}",
    "/uploads/RECEIPTS/{f}",
    "/Uploads/Receipts/{F}",
    "/uploads//receipts/{f}",
    "/uploads/./receipts/{f}",
    "/./uploads/receipts/{f}",
    "/uploads/x/../receipts/{f}",
    "/uploads%2freceipts/{f}",
    "/uploads%2Freceipts%2F{f}",
    "/uploads/%72eceipts/{f}",
    "/uploads/receipts/{f}?download=1",
    "/uploads/receipts",
    "/uploads/receipts/",
]


@pytest.mark.parametrize("variant", STATIC_RECEIPT_VARIANTS)
def test_static_receipt_path_variants_are_blocked(
    client, tmp_path, monkeypatch, variant
):
    receipts = tmp_path / "uploads" / "receipts"
    receipts.mkdir(parents=True)
    filename = "REC-2026-ABCD1234-00001.pdf"
    (receipts / filename).write_bytes(b"%PDF-1.4 recibo legacy")
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setattr(app_module, "static_file_dir", str(tmp_path))

    response = client.get(variant.format(f=filename, F=filename.upper()))

    assert not _is_pdf(response)


def test_private_upload_check_covers_case_and_identity(tmp_path, monkeypatch):
    receipts = tmp_path / "uploads" / "receipts"
    receipts.mkdir(parents=True)
    alias = tmp_path / "uploads" / "alias"
    alias.symlink_to(receipts)
    monkeypatch.setattr(app_module, "static_file_dir", str(tmp_path))

    assert app_module.is_private_upload_path("UPLOADS/Receipts/x.pdf")
    assert app_module.is_private_upload_path("uploads/alias/x.pdf")
    assert not app_module.is_private_upload_path("uploads/players/x.png")


def test_private_receipt_root_inside_public_refuses_to_start(tmp_path):
    env = {
        **os.environ,
        "APP_ENV": "development",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'guard.db'}",
        "TOKEN_SECRET": "sportflow-pytest-secret-123456789",
        "PRIVATE_RECEIPT_ROOT": os.path.join(REPO_ROOT, "public", "recibos"),
    }

    result = subprocess.run(
        [sys.executable, "-c", "import src.app"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "PRIVATE_RECEIPT_ROOT no puede estar dentro de public/" in result.stderr


# =====================================================
# SEC-010 — cabeceras y CORS
# =====================================================

@pytest.mark.parametrize(
    "path",
    ["/api/no-existe", "/api/teams", "/uploads/receipts/x.pdf"],
)
def test_security_headers_on_every_response(client, path):
    response = client.get(path)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers["Content-Security-Policy"] == (
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    assert "Strict-Transport-Security" not in response.headers


def test_security_headers_on_receipt_pdf(client, world, auth_headers):
    receipt = _issue_receipt(client, auth_headers, world)

    response = client.get(receipt["share_url"])

    assert _is_pdf(response)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in (
        response.headers["Content-Security-Policy"]
    )


@pytest.mark.parametrize("path", ["/api/teams", "/api/login"])
def test_cors_only_allows_configured_origins(client, path):
    allowed = client.open(
        path,
        method="OPTIONS",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    rejected = client.open(
        path,
        method="OPTIONS",
        headers={
            "Origin": "https://evil.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    rejected_get = client.get(path, headers={"Origin": "https://evil.test"})

    assert allowed.headers["Access-Control-Allow-Origin"] == (
        "http://localhost:3000"
    )
    assert "Access-Control-Allow-Credentials" not in allowed.headers
    assert "Access-Control-Allow-Origin" not in rejected.headers
    assert "Access-Control-Allow-Origin" not in rejected_get.headers


def test_allowed_origins_parser_keeps_only_explicit_origins():
    assert app_module.parse_allowed_origins(
        " https://App.Example.test/ruta?x=1 , *, null, ftp://x.test,"
        "https://user:pw@evil.test, http://localhost:3000"
    ) == ["https://app.example.test", "http://localhost:3000"]
    assert app_module.parse_allowed_origins(None) == []


# =====================================================
# SEC-012 — completar/cancelar torneo vs inscribir equipo
# =====================================================

def _tournament(world, status="active"):
    tournament = Tournament(
        club_id=world.club_a.id,
        season_id=world.season_a.id,
        name="Copa",
        start_date=date(2026, 11, 1),
        default_referee_fee=0,
        status=status,
        created_by=world.owner_a.id,
    )
    db.session.add(tournament)
    db.session.commit()
    return tournament


def _lock_spy(monkeypatch):
    locks = []
    real_with_for_update = Query.with_for_update

    def spy(query, *args, **kwargs):
        locks.append((
            query.column_descriptions[0]["entity"],
            kwargs.get("key_share", False),
        ))
        return real_with_for_update(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", spy)
    return locks


def test_registration_locks_tournament_before_reading_status(
    client, world, auth_headers, monkeypatch
):
    tournament = _tournament(world)
    locks = _lock_spy(monkeypatch)

    response = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        headers=auth_headers(world.owner_a),
        json={"team_id": world.team_a.id},
    )

    assert response.status_code == 201
    assert locks == [(Tournament, True)]


@pytest.mark.parametrize("action", ["complete", "cancel"])
def test_transition_locks_tournament_first(
    client, world, auth_headers, monkeypatch, action
):
    tournament = _tournament(world)
    locks = _lock_spy(monkeypatch)

    response = client.put(
        f"/api/tournaments/{tournament.id}/{action}",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert locks[0] == (Tournament, True)


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_registration_after_transition_is_rejected(
    client, world, auth_headers, status
):
    tournament = _tournament(world, status=status)

    response = client.post(
        f"/api/tournaments/{tournament.id}/teams",
        headers=auth_headers(world.owner_a),
        json={"team_id": world.team_a.id},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TOURNAMENT_NOT_ACTIVE"
    assert TournamentTeam.query.count() == 0


# =====================================================
# SEC-013 — bordes de lifecycle
# =====================================================

def test_archived_team_cannot_be_renamed(client, world, auth_headers):
    world.team_a.status = "archived"
    db.session.commit()

    response = client.put(
        f"/api/teams/{world.team_a.id}",
        headers=auth_headers(world.owner_a),
        json={"name": "Renombrado", "gender": "female"},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TEAM_ARCHIVED"
    db.session.expire_all()
    assert db.session.get(Team, world.team_a.id).name == "Team A"


def test_active_team_rename_keeps_working(client, world, auth_headers):
    response = client.put(
        f"/api/teams/{world.team_a.id}",
        headers=auth_headers(world.owner_a),
        json={"name": "Renombrado", "gender": "female"},
    )

    assert response.status_code == 200
    assert response.get_json()["team"]["name"] == "Renombrado"


def _training(world, status="scheduled"):
    training = TrainingSession(
        team_id=world.team_a.id,
        date=date(2026, 11, 20),
        start_time=time(10, 0),
        end_time=time(11, 0),
        location="Cancha",
        status=status,
        created_by=world.owner_a.id,
    )
    db.session.add(training)
    db.session.flush()
    sync_training_roster(training)
    db.session.commit()
    return training


def _deactivate(world, player):
    player.is_active = False
    db.session.commit()


def test_historical_correction_keeps_snapshot_player_after_inactive(
    client, world, auth_headers
):
    # Corrección histórica permitida: la jugadora estaba en el snapshot del
    # entrenamiento ya completado. Comportamiento esperado, no un bug.
    player = world.players_a[0]
    training = _training(world)
    training.status = "completed"
    db.session.commit()
    _deactivate(world, player)

    response = client.post(
        f"/api/trainings/{training.id}/corrections/attendance",
        headers=auth_headers(world.owner_a),
        json={
            "reason": "corrección de planilla",
            "attendance": [{"player_id": player.id, "status": "present"}],
        },
    )

    assert response.status_code == 200
    assert Attendance.query.filter_by(
        session_id=training.id,
        player_id=player.id,
        status="present",
    ).one()


def test_new_training_after_inactive_excludes_player(
    client, world, auth_headers
):
    player = world.players_a[0]
    _deactivate(world, player)
    training = _training(world)

    response = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.owner_a),
        json={"attendance": [{"player_id": player.id, "status": "present"}]},
    )

    assert TrainingPlayer.query.filter_by(
        training_id=training.id,
        player_id=player.id,
    ).count() == 0
    assert response.status_code == 403
    assert response.get_json()["code"] == "PLAYER_NOT_IN_TRAINING"
    assert Attendance.query.count() == 0


def test_scheduled_training_snapshot_is_kept_until_explicit_sync(
    client, world, auth_headers
):
    # El roster de un entrenamiento es un snapshot: desactivar a una jugadora
    # no la quita sola; la sincronización explícita sí, si no tiene asistencia.
    player = world.players_a[0]
    training = _training(world)
    _deactivate(world, player)

    attendance = client.post(
        f"/api/trainings/{training.id}/attendance",
        headers=auth_headers(world.owner_a),
        json={"attendance": [{"player_id": player.id, "status": "present"}]},
    )
    other_training = _training(world)
    sync = client.put(
        f"/api/trainings/{other_training.id}/sync-roster",
        headers=auth_headers(world.owner_a),
    )

    assert attendance.status_code == 200
    assert sync.status_code == 200
    assert TrainingPlayer.query.filter_by(
        training_id=other_training.id,
        player_id=player.id,
    ).count() == 0


def _tournament_with_charges(world, statuses):
    tournament = _tournament(world)
    entry = TournamentTeam(
        tournament_id=tournament.id,
        team_id=world.team_a.id,
        registration_fee=30,
        status="active",
    )
    db.session.add(entry)
    db.session.flush()

    for index, status in enumerate(statuses):
        db.session.add(PlayerPayment(
            club_id=world.club_a.id,
            player_id=world.players_a[index].id,
            payment_type="tournament",
            tournament_team_id=entry.id,
            amount=10,
            currency_code="USD",
            status=status,
            payment_method="cash" if status == "paid" else None,
            payment_date=date.today() if status == "paid" else None,
        ))

    db.session.commit()
    return tournament, entry


def _charge_statuses(entry):
    return sorted(
        payment.status
        for payment in PlayerPayment.query.filter_by(
            tournament_team_id=entry.id
        ).all()
    )


@pytest.mark.parametrize("pending_status", ["pending", "overdue"])
def test_cancel_with_pending_charges_is_blocked_for_owner(
    client, world, auth_headers, pending_status
):
    tournament, entry = _tournament_with_charges(world, [pending_status, "paid"])

    response = client.put(
        f"/api/tournaments/{tournament.id}/cancel",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "TOURNAMENT_HAS_PENDING_CHARGES"
    db.session.expire_all()
    assert db.session.get(Tournament, tournament.id).status == "active"
    assert _charge_statuses(entry) == sorted([pending_status, "paid"])


def test_cancel_with_pending_charges_gives_coach_no_finance_detail(
    client, world, auth_headers
):
    tournament, _ = _tournament_with_charges(world, ["pending"])

    response = client.put(
        f"/api/tournaments/{tournament.id}/cancel",
        headers=auth_headers(world.coach_a),
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "FINANCE_DEPENDENCY"
    assert "amount" not in response.get_data(as_text=True)


def test_cancel_after_resolving_keeps_paid_and_cancelled_charges(
    client, world, auth_headers
):
    tournament, entry = _tournament_with_charges(world, ["paid", "cancelled"])

    response = client.put(
        f"/api/tournaments/{tournament.id}/cancel",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert response.get_json()["tournament"]["status"] == "cancelled"
    assert _charge_statuses(entry) == ["cancelled", "paid"]


def test_completing_with_pending_charges_is_not_blocked(
    client, world, auth_headers
):
    tournament, entry = _tournament_with_charges(world, ["pending"])

    response = client.put(
        f"/api/tournaments/{tournament.id}/complete",
        headers=auth_headers(world.owner_a),
    )

    assert response.status_code == 200
    assert _charge_statuses(entry) == ["pending"]


# =====================================================
# SEC-014 — logs sin datos personales ni valores SQL
# =====================================================

@pytest.fixture
def failing_email(monkeypatch):
    sent = {}
    monkeypatch.setenv("RESEND_API_KEY", "re_test_dummy")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "no-reply@example.com")

    def fail(params):
        sent.update(params)
        raise RuntimeError(f"Resend rechazó {params['to'][0]}: {params['html']}")

    monkeypatch.setattr(resend.Emails, "send", fail)
    return sent


def _logged(caplog):
    return "\n".join(record.getMessage() for record in caplog.records)


def test_welcome_email_failure_logs_no_personal_data(
    client, world, auth_headers, failing_email, caplog, monkeypatch
):
    import src.api.endpoints.admin as admin_endpoints

    created = {}
    real_send = admin_endpoints.send_welcome_email

    def capture(**kwargs):
        created.update(kwargs)
        return real_send(**kwargs)

    monkeypatch.setattr(admin_endpoints, "send_welcome_email", capture)
    country = Country(code="VE", name="Venezuela", is_active=True)
    db.session.add(country)
    db.session.flush()
    area = AdministrativeArea(
        country_id=country.id,
        code="DC",
        name="Distrito Capital",
        is_active=True,
    )
    db.session.add(area)
    db.session.commit()

    response = client.post(
        "/api/admin/create-client",
        headers=auth_headers(world.system_admin),
        json={
            "full_name": "Cliente Privado",
            "email": "cliente.privado@example.com",
            "club_name": "Club Log",
            "sport_id": world.sport.id,
            "country_id": country.id,
            "administrative_area_id": area.id,
            "city": "Caracas",
            "timezone": "America/Caracas",
            "currency_code": "USD",
        },
    )

    assert response.status_code == 201, response.get_json()
    log = _logged(caplog)
    assert response.get_json()["email_sent"] is False
    assert "cliente.privado@example.com" not in log
    assert created["temporary_password"] not in log
    assert "RuntimeError" in log


def test_password_reset_email_failure_logs_no_email_or_token(
    client, world, failing_email, caplog
):
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": world.coach_a.email},
    )

    log = _logged(caplog)
    token = failing_email["html"].split("token=")[1].split('"')[0]
    assert response.status_code == 200
    assert token and token not in log
    assert world.coach_a.email not in log
    assert "RuntimeError" in log


def test_sql_error_logs_context_without_parameter_values(
    client, world, caplog, monkeypatch
):
    def failing_insert(user, password):
        db.session.execute(
            text("INSERT INTO users (id, email, password) VALUES (:i, :e, :p)"),
            {"i": str(uuid.uuid4()), "e": "pii.sql@example.com", "p": "Secreto-SQL-9876"},
        )
        return False

    monkeypatch.setattr(auth_endpoints, "password_matches", failing_insert)

    response = client.post(
        "/api/login",
        json={"email": "nadie@example.com", "password": "otra-clave-123"},
    )

    log = _logged(caplog)
    assert response.status_code == 500
    assert "pii.sql@example.com" not in log
    assert "Secreto-SQL-9876" not in log
    assert "IntegrityError" in log
    assert "sql=INSERT INTO users" in log
    assert db.engine.hide_parameters is True


def test_unexpected_exception_logs_no_request_secrets(
    client, caplog, monkeypatch
):
    def boom(user, password):
        raise RuntimeError(f"fallo inesperado con {password}")

    monkeypatch.setattr(auth_endpoints, "password_matches", boom)

    response = client.post(
        "/api/login",
        headers={"Authorization": "Bearer tok-secreto-abc123"},
        json={
            "email": "secreto.inesperado@example.com",
            "password": "ClaveInesperada-55",
        },
    )

    log = _logged(caplog)
    assert response.status_code == 500
    assert response.get_json()["code"] == "INTERNAL_ERROR"
    for secret in (
        "ClaveInesperada-55",
        "secreto.inesperado@example.com",
        "tok-secreto-abc123",
    ):
        assert secret not in log
    assert "RuntimeError" in log
    assert "POST /api/login" in log
    assert "auth.py" in log
