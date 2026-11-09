from pathlib import Path

from src.api.models import TeamPlayer, db


ROOT = Path(__file__).resolve().parents[1]


def _owner_dashboard(client, auth_headers, world):
    response = client.get(
        "/api/club/dashboard",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 200
    return response.get_json()


def _remove_current_team(world):
    TeamPlayer.query.filter_by(team_id=world.team_a.id).delete(
        synchronize_session=False,
    )
    db.session.delete(world.team_a)
    db.session.flush()


def test_empty_club_dashboard_continues_with_category(
    client, world, auth_headers
):
    _remove_current_team(world)
    db.session.delete(world.category_a)
    db.session.commit()

    setup = _owner_dashboard(client, auth_headers, world)["sections"][
        "setup_continuation"
    ]

    assert setup["step"] == "category"
    assert setup["action_label"] == "Crear categoría"
    assert setup["action_path"] == "/categories"


def test_category_without_team_continues_with_team(
    client, world, auth_headers
):
    category_id = world.category_a.id
    _remove_current_team(world)
    db.session.commit()

    setup = _owner_dashboard(client, auth_headers, world)["sections"][
        "setup_continuation"
    ]

    assert setup["step"] == "team"
    assert setup["action_label"] == "Crear equipo"
    assert setup["action_path"] == f"/categories/{category_id}"


def test_team_without_players_continues_with_roster(
    client, world, auth_headers
):
    TeamPlayer.query.filter_by(team_id=world.team_a.id).delete(
        synchronize_session=False,
    )
    db.session.commit()

    setup = _owner_dashboard(client, auth_headers, world)["sections"][
        "setup_continuation"
    ]

    assert setup["step"] == "player"
    assert setup["action_label"] == "Agregar deportistas"
    assert setup["action_path"] == f"/teams/{world.team_a.id}"


def test_operational_club_has_no_setup_continuation(
    client, world, auth_headers
):
    sections = _owner_dashboard(client, auth_headers, world)["sections"]

    assert sections["setup_continuation"] is None


def test_staff_dashboard_remains_financial_and_season_independent(
    client, world, auth_headers
):
    world.season_a.status = "closed"
    db.session.commit()

    response = client.get(
        "/api/club/dashboard",
        headers=auth_headers(world.staff_a),
    )
    sections = response.get_json()["sections"]

    assert response.status_code == 200
    assert "finance" in sections
    assert "agenda" not in sections
    assert "operations" not in sections
    assert "setup_continuation" not in sections


def test_dashboard_frontend_contract_for_role_flows_and_copy():
    source = (
        ROOT / "src/front/js/pages/dashboard/dashboard.js"
    ).read_text(encoding="utf-8")
    components = (
        ROOT / "src/front/js/pages/dashboard/dashboardComponents.js"
    ).read_text(encoding="utf-8")

    owner = source[
        source.index("const OwnerDashboard") : source.index(
            "const CoachDashboard"
        )
    ]
    coach = source[
        source.index("const CoachDashboard") : source.index(
            "const StaffDashboard"
        )
    ]
    staff = source[
        source.index("const StaffDashboard") : source.index(
            "const DashboardErrorState"
        )
    ]

    assert owner.index("<SetupContinuation") < owner.index(
        'title="Requiere atención"'
    )
    assert owner.index('title="Requiere atención"') < owner.index(
        'title="Agenda de hoy"'
    )
    assert coach.index('title="Agenda de hoy"') < coach.index(
        'title="Requiere atención"'
    )
    assert staff.index('title="Requiere atención"') < staff.index(
        'title="Hoy"'
    )

    assert "Partido preparado para registro en vivo" in source
    assert "Abrir registro en vivo" in source
    assert "Partido en curso" not in source
    assert "Continuar LiveMatch" not in source
    assert "Consultar equipos del club" in source
    assert "Gestionar temporadas" in source
    assert "Revisar pagos vencidos" in source
    assert "Registrar asistencia" in source
    assert "Pagos sin recibo" in source
    assert "Recibos aún no compartidos desde SportFlow" in source
    assert "jugadoras" not in source
    assert "convocadas" not in source
    assert "role=\"status\"" not in components


def test_dashboard_money_uses_shared_formatter_without_currency_symbol():
    source = (
        ROOT / "src/front/js/pages/dashboard/dashboard.js"
    ).read_text(encoding="utf-8")
    components = (
        ROOT / "src/front/js/pages/dashboard/dashboardComponents.js"
    ).read_text(encoding="utf-8")

    assert "formatMoney" in source
    assert "formatMoney" in components
    assert '"$"' not in source
    assert '"$"' not in components
