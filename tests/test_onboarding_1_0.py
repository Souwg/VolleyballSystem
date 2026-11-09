from pathlib import Path

import pytest

from src.api.extensions import bcrypt
from src.api.models import Club, TeamPlayer, db


ROOT = Path(__file__).resolve().parents[1]


def _code(response):
    return response.get_json().get("code")


@pytest.mark.parametrize("user_key", ["coach_a", "staff_a"])
def test_pending_coach_and_staff_only_keep_setup_access(
    client, world, auth_headers, user_key
):
    world.club_a.onboarding_finished_at = None
    db.session.commit()
    user = getattr(world, user_key)

    status = client.get(
        "/api/onboarding/status",
        headers=auth_headers(user),
    )
    operational = client.get(
        "/api/categories",
        headers=auth_headers(user),
    )

    assert status.status_code == 200
    assert status.get_json()["status"] == "pending"
    assert operational.status_code == 403
    assert _code(operational) == "CLUB_SETUP_PENDING"


@pytest.mark.parametrize("user_key", ["coach_a", "staff_a"])
def test_pending_coach_and_staff_can_login_refresh_and_logout(
    client, world, user_key
):
    world.club_a.onboarding_finished_at = None
    user = getattr(world, user_key)
    user.password = bcrypt.generate_password_hash("Clave1234").decode("utf-8")
    db.session.commit()

    login = client.post(
        "/api/login",
        json={"email": user.email, "password": "Clave1234"},
    )
    assert login.status_code == 200

    refresh = client.post(
        "/api/refresh",
        headers={"Authorization": f"Bearer {login.get_json()['refresh']}"},
    )
    assert refresh.status_code == 200

    logout = client.post(
        "/api/logout",
        headers={"Authorization": f"Bearer {refresh.get_json()['token']}"},
    )
    assert logout.status_code == 200


def test_finishing_unlocks_coach_and_staff_and_does_not_affect_admin(
    client, world, auth_headers
):
    world.club_a.onboarding_finished_at = None
    db.session.commit()

    admin = client.get(
        "/api/admin/sports",
        headers=auth_headers(world.system_admin),
    )
    owner = client.get(
        "/api/categories",
        headers=auth_headers(world.owner_a),
    )
    finish = client.post(
        "/api/onboarding/finish",
        headers=auth_headers(world.owner_a),
    )

    assert admin.status_code == 200
    assert owner.status_code == 200
    assert finish.status_code == 200

    for user in (world.coach_a, world.staff_a):
        response = client.get(
            "/api/categories",
            headers=auth_headers(user),
        )
        assert response.status_code == 200


def test_player_is_not_required_for_persistent_finish(
    client, world, auth_headers
):
    world.club_a.onboarding_finished_at = None
    world.club_a.city = "Caracas"
    TeamPlayer.query.filter_by(team_id=world.team_a.id).delete()
    db.session.commit()

    before = client.get(
        "/api/onboarding/status",
        headers=auth_headers(world.owner_a),
    )
    finish = client.post(
        "/api/onboarding/finish",
        headers=auth_headers(world.owner_a),
    )
    after = client.get(
        "/api/onboarding/status",
        headers=auth_headers(world.owner_a),
    )

    assert before.get_json()["step"] == 4
    assert before.get_json()["status"] == "pending"
    assert finish.status_code == 200
    assert finish.get_json()["status"] == "completed"
    assert after.get_json()["status"] == "completed"
    assert db.session.get(Club, world.club_a.id).onboarding_finished_at


def test_onboarding_frontend_contract_for_three_tasks_and_finish_screen():
    source = (
        ROOT / "src/front/js/pages/onboarding/onboarding.js"
    ).read_text(encoding="utf-8")
    stepper = (
        ROOT / "src/front/js/component/ui/stepIndicator.js"
    ).read_text(encoding="utf-8")
    route = (
        ROOT / "src/front/js/component/onboardingRoute.js"
    ).read_text(encoding="utf-8")

    assert '["Categoría", "Equipo", "Deportista"]' in source
    assert "Paso 2 de 5" not in source
    assert "Season" not in source
    assert "Crear categoría" in source
    assert "Crear equipo" in source
    assert "Agregar deportista" in source
    assert "Recomendado · puedes hacerlo después" in source
    assert "Lo agregaré después" in source
    assert "Ir al panel y configurar después" in source
    assert "Tienes cambios sin guardar" in source
    assert "Tu primer equipo está listo" in source
    assert "Ir al panel" in source
    assert "window.confirm" not in source
    assert "window.scrollTo(0, 0)" in source
    assert 'aria-current={step === index + 1 ? "step" : undefined}' in stepper
    assert "onboardingJustFinished" in route
