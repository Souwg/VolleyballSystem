"""FASE 5.4B: errores HTTP, validación de entrada, stats, uploads, emails y login.

La validación contra PostgreSQL real y el fuzz de rutas se ejecutan aparte;
aquí se fijan las reglas deterministas.
"""
import io
import os
import re
from datetime import date
from decimal import Decimal

import pytest
import resend
from PIL import Image
from werkzeug.datastructures import FileStorage

import src.api.endpoints.club as club_endpoints
import src.app as app_module
from src.api.email_service import (
    send_password_reset_email,
    send_welcome_email,
)
from src.api.extensions import bcrypt
from src.api.models import (
    Club,
    MatchSession,
    PasswordResetToken,
    Player,
    PlayerMatchStat,
    PlayerPayment,
    db,
)
from src.api.payment_charge_helpers import MAX_MONEY_AMOUNT, parse_money
from src.api.rate_limit import LOGIN_RULE, rate_limiter
from src.api.upload_utils import MAX_UPLOAD_REQUEST_SIZE


PASSWORD = "Correcta-123"


def _png_bytes(size=(2, 2), image_format="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format=image_format)
    return buffer.getvalue()


def _image(data, filename):
    return {
        "data": {"image": (io.BytesIO(data), filename)},
        "content_type": "multipart/form-data",
    }


@pytest.fixture
def saved_files(monkeypatch):
    saved = []
    monkeypatch.setattr(
        FileStorage,
        "save",
        lambda self, destination, *args, **kwargs: saved.append(destination),
    )
    return saved


@pytest.fixture
def rate_limit_on(app, monkeypatch):
    monkeypatch.setitem(app.config, "RATE_LIMIT_ENABLED", True)
    rate_limiter.clear()
    yield
    rate_limiter.clear()


def _with_password(user, password=PASSWORD):
    user.password = bcrypt.generate_password_hash(password).decode("utf-8")
    db.session.commit()
    return user


def _login(client, email, password):
    return client.post(
        "/api/login",
        json={"email": email, "password": password},
    )


# =====================================================
# SEC-004 — errores HTTP con su estado y contrato JSON
# =====================================================

@pytest.mark.parametrize(
    "raw",
    ["{bad", ""],
)
def test_malformed_json_is_400_not_500(client, world, auth_headers, raw):
    response = client.post(
        "/api/categories",
        headers={**auth_headers(world.owner_a), "Content-Type": "application/json"},
        data=raw,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_JSON_BODY"


def test_unknown_api_route_is_json_404(client, world, auth_headers):
    response = client.get("/api/no-existe", headers=auth_headers(world.owner_a))

    assert response.status_code == 404
    assert response.get_json()["code"] == "NOT_FOUND"


def test_unsafe_static_path_is_404_not_500(client):
    response = client.get("/../.env")

    assert response.status_code == 404
    assert response.get_json()["code"] == "NOT_FOUND"


def test_method_not_allowed_keeps_405_and_allow_header(
    client, world, auth_headers
):
    response = client.delete("/api/club", headers=auth_headers(world.owner_a))

    assert response.status_code == 405
    assert response.get_json() == {
        "error": True,
        "code": "METHOD_NOT_ALLOWED",
        "message": "Método no permitido para este recurso.",
    }
    assert "PUT" in response.headers["Allow"]


def test_non_json_content_type_is_415(client, world, auth_headers):
    response = client.post(
        "/api/categories",
        headers={**auth_headers(world.owner_a), "Content-Type": "text/plain"},
        data='{"name": "x"}',
    )

    assert response.status_code == 415
    assert response.get_json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_request_over_global_limit_is_413(client, world, auth_headers):
    response = client.post(
        "/api/categories",
        headers={**auth_headers(world.owner_a), "Content-Type": "application/json"},
        data='{"name": "' + "x" * MAX_UPLOAD_REQUEST_SIZE + '"}',
    )

    assert response.status_code == 413
    assert response.get_json()["code"] == "PAYLOAD_TOO_LARGE"


# =====================================================
# SEC-005 — cuerpos, tipos, longitudes y montos
# =====================================================

@pytest.mark.parametrize("raw", ["[]", '"x"', "1", "true", "null"])
def test_json_body_must_be_an_object(client, world, auth_headers, raw):
    response = client.put(
        "/api/club",
        headers={**auth_headers(world.owner_a), "Content-Type": "application/json"},
        data=raw,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_JSON_BODY"


@pytest.mark.parametrize(
    "value",
    [5, True, ["x"], {"id": "x"}],
)
def test_identifiers_must_be_text(client, world, auth_headers, value):
    response = client.post(
        "/api/matches",
        headers=auth_headers(world.owner_a),
        json={
            "team_id": value,
            "date": "2027-03-01",
            "opponent_name": "Rival",
            "match_type": "friendly",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_FIELD_TYPE"
    assert response.get_json()["field"] == "team_id"
    assert MatchSession.query.count() == 0


def test_nested_identifiers_and_id_lists_are_checked(
    client, world, auth_headers
):
    response = client.put(
        f"/api/matches/{'x'}/roster/status",
        headers=auth_headers(world.owner_a),
        json={"players": [{"match_player_id": 7}]},
    )
    id_list = client.post(
        "/api/seasons/x/transition",
        headers=auth_headers(world.owner_a),
        json={"source_season_id": "x", "team_ids": [1, 2]},
    )

    assert response.status_code == 400
    assert response.get_json()["field"] == "match_player_id"
    assert id_list.status_code == 400
    assert id_list.get_json()["field"] == "team_ids"


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/categories", {"name": 5}),
        ("/api/categories", {"name": "Sub 18", "description": ["x"]}),
        ("/api/club/users", {"full_name": "A", "email": 5, "role": "coach"}),
    ],
)
def test_text_fields_reject_other_types(client, world, auth_headers, path, body):
    response = client.post(path, headers=auth_headers(world.owner_a), json=body)

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_FIELD_TYPE"


def test_player_update_wrong_types_are_400_without_changes(
    client, world, auth_headers
):
    player = world.players_a[0]
    url = f"/api/players/{player.id}"
    headers = auth_headers(world.owner_a)
    base = {"first_name": "Ana", "last_name": "Pérez", "sex": "female"}

    responses = [
        client.put(url, headers=headers, json={**base, "birth_date": 5}),
        client.put(url, headers=headers, json={**base, "first_name": [{"a": 1}]}),
        client.put(url, headers=headers, json={**base, "main_position": 3}),
        client.put(
            f"{url}/status",
            headers=headers,
            json={"status": {}, "team_id": world.team_a.id},
        ),
    ]

    assert [response.status_code for response in responses] == [400] * 4
    db.session.expire_all()
    assert db.session.get(Player, player.id).first_name == "Player A1"


def test_lineup_and_roster_lists_reject_wrong_shapes(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, on_court_count=0)
    headers = auth_headers(world.owner_a)
    match_id = created.match.id

    lineup = client.put(
        f"/api/matches/{match_id}/starting-lineup",
        headers=headers,
        json={"players": [{}] * 6},
    )
    lineup_int = client.put(
        f"/api/matches/{match_id}/starting-lineup",
        headers=headers,
        json={"players": 6},
    )
    roster = client.put(
        f"/api/matches/{match_id}/roster/status",
        headers=headers,
        json={"players": [1]},
    )

    assert lineup.status_code == 400
    assert lineup.get_json()["code"] == "INVALID_STARTING_LINEUP"
    assert lineup_int.status_code == 400
    assert roster.status_code == 400
    assert roster.get_json()["code"] == "INVALID_MATCH_STATUS"


@pytest.mark.parametrize(
    "field,limit",
    [("name", 120), ("primary_color", 20), ("secondary_color", 20)],
)
def test_club_text_longer_than_column_is_rejected(
    client, world, auth_headers, field, limit
):
    response = client.put(
        "/api/club",
        headers=auth_headers(world.owner_a),
        json={field: "n" * (limit + 1)},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "FIELD_TOO_LONG"
    assert response.get_json()["field"] == field
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).name == "Club A"


def test_text_at_column_limit_is_accepted(client, world, auth_headers):
    response = client.put(
        "/api/club",
        headers=auth_headers(world.owner_a),
        json={"name": "n" * 120},
    )

    assert response.status_code == 200


def test_match_opponent_name_longer_than_column_is_rejected(
    client, world, auth_headers
):
    response = client.post(
        "/api/matches",
        headers=auth_headers(world.owner_a),
        json={
            "team_id": world.team_a.id,
            "date": "2027-03-01",
            "opponent_name": "o" * 5000,
            "match_type": "friendly",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "FIELD_TOO_LONG"
    assert MatchSession.query.count() == 0


def _pending_payment(world):
    payment = PlayerPayment(
        club_id=world.club_a.id,
        player_id=world.players_a[0].id,
        payment_type="extra",
        amount=10,
        currency_code="USD",
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()
    return payment


@pytest.mark.parametrize(
    "body,code",
    [
        ({"amount": 1e12}, "INVALID_PAYMENT_AMOUNT"),
        ({"amount": 1e15}, "INVALID_PAYMENT_AMOUNT"),
        ({"amount": "9" * 400}, "INVALID_PAYMENT_AMOUNT"),
        ({"amount": "NaN"}, "INVALID_PAYMENT_AMOUNT"),
        ({"amount": "Infinity"}, "INVALID_PAYMENT_AMOUNT"),
        ({"amount": "-Infinity"}, "INVALID_PAYMENT_AMOUNT"),
        ({"reference": "r" * 121}, "FIELD_TOO_LONG"),
    ],
)
def test_payment_out_of_range_values_are_400_without_persisting(
    client, world, auth_headers, body, code
):
    payment = _pending_payment(world)

    response = client.put(
        f"/api/payments/{payment.id}",
        headers=auth_headers(world.owner_a),
        json=body,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == code
    db.session.expire_all()
    stored = db.session.get(PlayerPayment, payment.id)
    assert stored.amount == Decimal("10.00")
    assert stored.reference is None


@pytest.mark.parametrize(
    "field,code",
    [
        ("default_monthly_fee", "INVALID_DEFAULT_MONTHLY_FEE"),
        ("default_enrollment_fee", "INVALID_DEFAULT_ENROLLMENT_FEE"),
    ],
)
def test_club_default_fee_above_charge_limit_is_rejected(
    client, world, auth_headers, field, code
):
    response = client.put(
        "/api/club",
        headers=auth_headers(world.owner_a),
        json={field: 1e15},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == code
    db.session.expire_all()
    assert getattr(db.session.get(Club, world.club_a.id), field) is None


def test_money_limit_comes_from_charge_column():
    assert MAX_MONEY_AMOUNT == Decimal("99999999.99")
    assert parse_money("99999999.99")[0] == MAX_MONEY_AMOUNT
    assert parse_money("99999999.995")[1] is not None
    assert parse_money(1e15)[1] is not None
    assert parse_money("-0.001")[0] == Decimal("0.00")


def test_integer_column_overflow_is_400(client, world, auth_headers):
    response = client.post(
        "/api/players",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": "Ana",
            "last_name": "Pérez",
            "sex": "female",
            "team_id": world.team_a.id,
            "player_number": 10 ** 12,
        },
    )

    assert response.status_code == 400
    assert Player.query.filter_by(first_name="Ana").count() == 0


# =====================================================
# SEC-006 — stats resumen inválidas
# =====================================================

@pytest.mark.parametrize(
    "value",
    [-5, "x", "-5", True, 1.5, 2.0, None, 2 ** 40],
)
def test_invalid_summary_stats_are_rejected_without_overwriting(
    client, world, auth_headers, match_factory, value
):
    created = match_factory(world, capture_mode="summary", did_play=True)
    row = created.rows[0]
    db.session.add(PlayerMatchStat(
        match_player_id=row.id,
        attacks_total=2,
        attacks_positive=2,
    ))
    db.session.commit()

    response = client.post(
        f"/api/match-players/{row.id}/stats",
        headers=auth_headers(world.owner_a),
        json={"attacks_total": value, "attacks_positive": 0},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_SUMMARY_STAT_VALUE"
    db.session.expire_all()
    stat = PlayerMatchStat.query.filter_by(match_player_id=row.id).one()
    assert (stat.attacks_total, stat.attacks_positive) == (2, 2)


def test_valid_summary_stats_still_save(
    client, world, auth_headers, match_factory
):
    created = match_factory(world, capture_mode="summary", did_play=True)
    row = created.rows[0]

    response = client.post(
        f"/api/match-players/{row.id}/stats",
        headers=auth_headers(world.owner_a),
        json={"attacks_total": 3, "attacks_positive": "2", "attacks_errors": 1},
    )

    assert response.status_code == 200
    stat = PlayerMatchStat.query.filter_by(match_player_id=row.id).one()
    assert (stat.attacks_total, stat.attacks_positive) == (3, 2)


# =====================================================
# SEC-007 — uploads
# =====================================================

def _upload_player(client, auth_headers, world, data, filename):
    return client.post(
        f"/api/players/{world.players_a[0].id}/upload-image",
        headers=auth_headers(world.owner_a),
        **_image(data, filename),
    )


@pytest.mark.parametrize(
    "data,filename",
    [
        (b"<html><script>alert(1)</script></html>", "foto.png"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "corrupta.png"),
        (_png_bytes(), "foto.jpg"),
        (_png_bytes(), "foto.gif"),
        (_png_bytes(), "sin-extension"),
    ],
)
def test_invalid_image_content_is_rejected(
    client, world, auth_headers, saved_files, data, filename
):
    response = _upload_player(client, auth_headers, world, data, filename)

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_IMAGE_FORMAT"
    assert saved_files == []
    db.session.expire_all()
    assert db.session.get(Player, world.players_a[0].id).image_url is None


def test_declared_content_type_must_match_image(
    client, world, auth_headers, saved_files
):
    response = client.post(
        f"/api/players/{world.players_a[0].id}/upload-image",
        headers=auth_headers(world.owner_a),
        data={"image": (io.BytesIO(_png_bytes()), "foto.png", "text/html")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert saved_files == []


@pytest.mark.parametrize(
    "filename,image_format,extension",
    [
        ("foto.png", "PNG", "png"),
        ("foto.JPEG", "JPEG", "jpeg"),
        ("foto.webp", "WEBP", "webp"),
        (".png", "PNG", "png"),
        ("../../evil.png", "PNG", "png"),
        ("a.php.png", "PNG", "png"),
        ("ñ‮.png", "PNG", "png"),
    ],
)
def test_valid_image_is_saved_under_uuid_name(
    client, world, auth_headers, saved_files, filename, image_format, extension
):
    response = _upload_player(
        client,
        auth_headers,
        world,
        _png_bytes(image_format=image_format),
        filename,
    )

    assert response.status_code == 201
    player_id = world.players_a[0].id
    uploads = os.path.realpath(
        os.path.join(os.path.dirname(app_module.__file__), "../public/uploads/players")
    )
    destination = os.path.realpath(saved_files[0])
    assert os.path.dirname(destination) == uploads
    assert re.fullmatch(
        rf"{player_id}-[0-9a-f]{{32}}\.{extension}",
        os.path.basename(destination),
    )
    assert response.get_json()["image_url"] == (
        f"/uploads/players/{os.path.basename(destination)}"
    )


def test_image_over_request_limit_is_413(
    client, world, auth_headers, saved_files
):
    response = _upload_player(
        client,
        auth_headers,
        world,
        b"\x89PNG" + b"\x00" * MAX_UPLOAD_REQUEST_SIZE,
        "grande.png",
    )

    assert response.status_code == 413
    assert response.get_json()["code"] == "IMAGE_TOO_LARGE"
    assert saved_files == []


def test_club_logo_keeps_its_own_smaller_limit(
    client, world, auth_headers, saved_files
):
    response = client.post(
        "/api/club/upload-image",
        headers=auth_headers(world.owner_a),
        **_image(b"\x89PNG" + b"\x00" * (3 * 1024 * 1024), "logo.png"),
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "IMAGE_TOO_LARGE"
    assert saved_files == []


def test_club_logo_upload_is_linked_to_the_club(
    client, world, auth_headers, saved_files
):
    response = client.post(
        "/api/club/upload-image",
        headers=auth_headers(world.owner_a),
        **_image(_png_bytes(), "logo.png"),
    )

    assert response.status_code == 201
    image_url = response.get_json()["image_url"]
    assert image_url.startswith(f"/uploads/clubs/{world.club_a.id}-")
    db.session.expire_all()
    assert db.session.get(Club, world.club_a.id).image_url == image_url
    assert len(saved_files) == 1


def test_club_logo_file_is_discarded_if_linking_fails(
    client, world, auth_headers, saved_files, monkeypatch
):
    discarded = []
    monkeypatch.setattr(
        club_endpoints,
        "discard_uploaded_image",
        discarded.append,
    )

    def failing_commit():
        raise RuntimeError("commit falló")

    monkeypatch.setattr(db.session, "commit", failing_commit)

    response = client.post(
        "/api/club/upload-image",
        headers=auth_headers(world.owner_a),
        **_image(_png_bytes(), "logo.png"),
    )

    assert response.status_code == 500
    assert discarded == saved_files


def test_uploaded_files_are_served_with_nosniff(client, tmp_path, monkeypatch):
    players_dir = tmp_path / "uploads" / "players"
    players_dir.mkdir(parents=True)
    (players_dir / "foto.png").write_bytes(_png_bytes())
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setattr(app_module, "static_file_dir", str(tmp_path))

    upload = client.get("/uploads/players/foto.png")
    page = client.get("/index.html")

    assert upload.status_code == 200
    assert upload.headers["Content-Type"] == "image/png"
    assert upload.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Content-Type-Options" not in page.headers


# =====================================================
# SEC-009 — HTML y asunto de los correos
# =====================================================

INJECTED_NAME = (
    '<a href="https://evil.test">click</a>'
    "<img src=x onerror=alert(1)><b>Nombre</b>"
)


@pytest.fixture
def sent_emails(monkeypatch):
    sent = []
    monkeypatch.setenv("RESEND_API_KEY", "re_test_dummy")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.setattr(resend.Emails, "send", lambda params: sent.append(params))
    return sent


def test_email_html_escapes_user_values(sent_emails):
    send_password_reset_email(
        "ana@example.com",
        INJECTED_NAME,
        "https://app.test/reset-password?token=abc&x=1",
    )
    send_welcome_email(
        "ana@example.com",
        INJECTED_NAME,
        "<b>Club</b>",
        "Tmp12345",
        "https://app.test/login",
    )

    for email in sent_emails:
        html = email["html"]
        assert "<a href=\"https://evil.test\">" not in html
        assert "<img src=x" not in html
        assert "<b>Nombre</b>" not in html
        assert "&lt;a href=&quot;https://evil.test&quot;&gt;click&lt;/a&gt;" in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html

    assert "token=abc&amp;x=1" in sent_emails[0]["html"]
    assert "&lt;b&gt;Club&lt;/b&gt;" in sent_emails[1]["html"]


def test_email_subject_and_sender_are_single_line(sent_emails, monkeypatch):
    monkeypatch.setenv("MAIL_FROM_NAME", "SportFlow\r\nBcc: x@evil.test")

    send_welcome_email(
        "ana@example.com",
        "Ana",
        "Club\r\nBcc: victim@evil.test\n\tX Y",
        "Tmp12345",
        "https://app.test/login",
    )

    email = sent_emails[0]
    assert email["subject"] == (
        "Bienvenido a SportFlow — Club Bcc: victim@evil.test X Y"
    )
    assert email["from"] == "SportFlow Bcc: x@evil.test <no-reply@example.com>"
    for header in (email["subject"], email["from"]):
        assert "\r" not in header and "\n" not in header


# =====================================================
# SEC-011 — enumeración y límite de intentos
# =====================================================

@pytest.mark.parametrize("state", ["inactive", "suspended", "missing"])
def test_wrong_password_never_reveals_account_state(client, world, state):
    user = _with_password(world.coach_a)
    email = user.email

    if state == "inactive":
        user.is_active = False
    elif state == "suspended":
        world.club_a.access_status = "suspended"
    else:
        email = "nadie@example.com"
    db.session.commit()

    response = _login(client, email, "incorrecta-123")

    assert response.status_code == 401
    assert response.get_json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.parametrize(
    "state,code",
    [("inactive", "ACCOUNT_DISABLED"), ("suspended", "CLUB_SUSPENDED")],
)
def test_account_state_only_after_correct_password(client, world, state, code):
    user = _with_password(world.coach_a)

    if state == "inactive":
        user.is_active = False
    else:
        world.club_a.access_status = "suspended"
    db.session.commit()

    response = _login(client, user.email, PASSWORD)

    assert response.status_code == 403
    assert response.get_json()["code"] == code


def test_password_longer_than_bcrypt_limit_is_not_500(client, world):
    user = _with_password(world.coach_a, "p" * 72)

    longer = _login(client, user.email, "p" * 80)
    reset = client.post(
        "/api/auth/reset-password",
        json={"token": "x", "new_password": "ñ" * 37},
    )

    # Igual que las versiones anteriores de bcrypt: solo cuentan 72 bytes.
    assert longer.status_code == 200
    assert reset.status_code == 400
    assert reset.get_json()["code"] == "PASSWORD_TOO_LONG"


def test_forgot_password_response_does_not_reveal_accounts(
    client, world, monkeypatch
):
    monkeypatch.setenv("RESEND_API_KEY", "")
    inactive = world.staff_a
    inactive.is_active = False
    db.session.commit()

    responses = [
        client.post("/api/auth/forgot-password", json={"email": email})
        for email in (
            world.coach_a.email,
            "nadie@example.com",
            inactive.email,
        )
    ]

    assert {response.status_code for response in responses} == {200}
    assert len({response.get_data() for response in responses}) == 1
    # El envío falló: no queda un token utilizable.
    assert PasswordResetToken.query.count() == 0


def test_login_is_rate_limited_per_ip_and_email(client, world, rate_limit_on):
    user = _with_password(world.coach_a)
    other = _with_password(world.staff_a)

    failures = [
        _login(client, user.email, f"mala-{attempt}").status_code
        for attempt in range(LOGIN_RULE.limit)
    ]
    limited = _login(client, user.email, PASSWORD)
    other_account = _login(client, other.email, PASSWORD)

    assert failures == [401] * LOGIN_RULE.limit
    assert limited.status_code == 429
    assert limited.get_json() == {
        "error": True,
        "code": "RATE_LIMITED",
        "message": (
            "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
        ),
    }
    assert 0 < int(limited.headers["Retry-After"]) <= LOGIN_RULE.window_seconds
    assert other_account.status_code == 200


def test_rate_limit_is_identical_for_unknown_accounts(client, rate_limit_on):
    statuses = [
        _login(client, "nadie@example.com", "mala").status_code
        for _ in range(LOGIN_RULE.limit + 1)
    ]

    assert statuses == [401] * LOGIN_RULE.limit + [429]


def test_rate_limit_expires_and_can_be_reset(
    client, world, rate_limit_on, monkeypatch
):
    user = _with_password(world.coach_a)
    now = [1000.0]
    monkeypatch.setattr(rate_limiter, "_clock", lambda: now[0])

    for _ in range(LOGIN_RULE.limit):
        _login(client, user.email, "mala")

    assert _login(client, user.email, PASSWORD).status_code == 429

    now[0] += LOGIN_RULE.window_seconds + 1
    assert _login(client, user.email, PASSWORD).status_code == 200

    for _ in range(LOGIN_RULE.limit):
        _login(client, user.email, "mala")

    rate_limiter.clear()
    assert _login(client, user.email, PASSWORD).status_code == 200


def test_successful_login_resets_failed_attempts(
    client, world, rate_limit_on
):
    user = _with_password(world.coach_a)

    for _ in range(LOGIN_RULE.limit - 1):
        _login(client, user.email, "mala")

    assert _login(client, user.email, PASSWORD).status_code == 200
    assert _login(client, user.email, "mala").status_code == 401


def test_forgot_reset_and_public_receipt_are_rate_limited(
    client, rate_limit_on
):
    forgot = [
        client.post(
            "/api/auth/forgot-password",
            json={"email": "nadie@example.com"},
        ).status_code
        for _ in range(6)
    ]
    reset = [
        client.post(
            "/api/auth/reset-password",
            json={"token": f"t{attempt}", "new_password": "Nueva-12345"},
        ).status_code
        for attempt in range(21)
    ]
    receipts = [
        client.get(f"/api/payment-receipts/public/token-{attempt}").status_code
        for attempt in range(61)
    ]

    assert forgot == [200] * 5 + [429]
    assert reset == [400] * 20 + [429]
    assert receipts == [404] * 60 + [429]


def test_rate_limit_is_off_only_by_explicit_config(app, client):
    assert app.config["RATE_LIMIT_ENABLED"] is False

    statuses = [
        _login(client, "nadie@example.com", "mala").status_code
        for _ in range(LOGIN_RULE.limit + 1)
    ]

    assert statuses == [401] * (LOGIN_RULE.limit + 1)
