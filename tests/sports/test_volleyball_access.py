import pytest

from tests.sports.helpers import event_payload


def test_owner_cannot_read_other_club_match(client, world, auth_headers, match_factory):
    created = match_factory(world, tenant="b")
    response = client.get(
        f"/api/matches/{created.match.id}", headers=auth_headers(world.owner_a)
    )
    assert (response.status_code, response.get_json()["code"]) == (403, "FORBIDDEN")


def test_owner_cannot_modify_other_club_match(client, world, auth_headers, match_factory):
    created = match_factory(world, tenant="b")
    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=auth_headers(world.owner_a), json={"players": [row.id for row in created.rows[:6]]},
    )
    assert (response.status_code, response.get_json()["code"]) == (403, "FORBIDDEN")


def test_player_from_other_club_cannot_be_used_in_event(
    client, world, auth_headers, match_factory
):
    own = match_factory(world, on_court_count=1)
    other = match_factory(world, tenant="b", on_court_count=1)
    payload = event_payload(own.match, other.rows[0])
    response = client.post(
        "/api/match-events", headers=auth_headers(world.owner_a), json=payload
    )
    assert (response.status_code, response.get_json()["code"]) == (400, "MATCH_PLAYER_INVALID")


def test_other_club_performance_is_hidden(client, world, auth_headers):
    response = client.get(
        f"/api/players/{world.players_b[0].id}/performance",
        headers=auth_headers(world.owner_a),
    )
    assert (response.status_code, response.get_json()["code"]) == (404, "PLAYER_NOT_FOUND")


@pytest.mark.parametrize("role", ["owner", "coach"])
def test_owner_and_coach_can_read_match(client, world, auth_headers, match_factory, role):
    created = match_factory(world)
    user = world.owner_a if role == "owner" else world.coach_a
    assert client.get(f"/api/matches/{created.match.id}", headers=auth_headers(user)).status_code == 200


@pytest.mark.parametrize("role", ["staff", "system_admin"])
def test_staff_and_system_admin_cannot_read_match(
    client, world, auth_headers, match_factory, role
):
    created = match_factory(world)
    user = world.staff_a if role == "staff" else world.system_admin
    response = client.get(f"/api/matches/{created.match.id}", headers=auth_headers(user))
    assert (response.status_code, response.get_json()["code"]) == (403, "FORBIDDEN")


@pytest.mark.parametrize("role", ["owner", "coach"])
def test_owner_and_coach_can_manage_lineup(
    client, world, auth_headers, match_factory, role
):
    created = match_factory(world)
    user = world.owner_a if role == "owner" else world.coach_a
    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=auth_headers(user), json={"players": [row.id for row in created.rows[:6]]},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("role", ["staff", "system_admin"])
def test_staff_and_system_admin_cannot_manage_lineup(
    client, world, auth_headers, match_factory, role
):
    created = match_factory(world)
    user = world.staff_a if role == "staff" else world.system_admin
    response = client.put(
        f"/api/matches/{created.match.id}/starting-lineup",
        headers=auth_headers(user), json={"players": [row.id for row in created.rows[:6]]},
    )
    assert (response.status_code, response.get_json()["code"]) == (403, "FORBIDDEN")


@pytest.mark.parametrize("role", ["owner", "coach"])
def test_owner_and_coach_can_create_events(client, world, auth_headers, match_factory, role):
    created = match_factory(world, on_court_count=1)
    user = world.owner_a if role == "owner" else world.coach_a
    response = client.post(
        "/api/match-events", headers=auth_headers(user),
        json=event_payload(created.match, created.rows[0]),
    )
    assert response.status_code == 201


@pytest.mark.parametrize("role", ["staff", "system_admin"])
def test_staff_and_system_admin_cannot_create_events(
    client, world, auth_headers, match_factory, role
):
    created = match_factory(world, on_court_count=1)
    user = world.staff_a if role == "staff" else world.system_admin
    response = client.post(
        "/api/match-events", headers=auth_headers(user),
        json=event_payload(created.match, created.rows[0]),
    )
    assert (response.status_code, response.get_json()["code"]) == (403, "FORBIDDEN")


@pytest.mark.parametrize("role", ["owner", "coach", "staff"])
def test_club_roles_can_read_performance(client, world, auth_headers, role):
    user = {"owner": world.owner_a, "coach": world.coach_a, "staff": world.staff_a}[role]
    response = client.get(
        f"/api/players/{world.players_a[0].id}/performance", headers=auth_headers(user)
    )
    assert response.status_code == 200


def test_system_admin_has_no_cross_club_performance_access(client, world, auth_headers):
    response = client.get(
        f"/api/players/{world.players_a[0].id}/performance",
        headers=auth_headers(world.system_admin),
    )
    assert (response.status_code, response.get_json()["code"]) == (404, "PLAYER_NOT_FOUND")


def test_match_requires_token(client, world, match_factory):
    created = match_factory(world)
    assert client.get(f"/api/matches/{created.match.id}").status_code == 401
