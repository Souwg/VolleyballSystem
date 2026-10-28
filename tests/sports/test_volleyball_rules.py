import pytest

from src.api.models import MatchPlayer, Player, db
from src.api.sports import (
    SportAdapter,
    ValidatedMatchResult,
    VolleyballAdapter,
    get_sport_adapter,
    sport_adapter_registry,
)


VOLLEYBALL_POSITIONS = tuple(
    position.code
    for position in get_sport_adapter("VOLLEYBALL").positions
)
VALID_RESULTS = [(3, 0), (3, 1), (3, 2), (0, 3), (1, 3), (2, 3)]
INVALID_RESULTS = [
    (0, 0), (1, 0), (2, 0), (1, 1), (2, 2), (2, 1), (1, 2), (3, 3),
    (4, 0), (0, 4), (-1, 3), (3, -1), ("x", 3), (None, 3),
    (3, 1.5), (3.0, 1.2), (3, -0.5), (3.7, 1), (3, "1.5"),
    (3, True), (False, 3), (3, []), (3, {}),
]


class TwoPeriodResultAdapter(SportAdapter):
    def validate_match_result(self, home_value, opponent_value):
        valid_scores = {(2, 0), (2, 1), (0, 2), (1, 2)}

        if (home_value, opponent_value) not in valid_scores:
            return None, "Resultado inválido para el deporte de prueba"

        return ValidatedMatchResult(
            home_value=home_value,
            opponent_value=opponent_value,
            result=("win" if home_value > opponent_value else "loss"),
        ), None


def register_result_adapter(monkeypatch, world, adapter):
    monkeypatch.setitem(
        sport_adapter_registry._adapters,
        adapter.code,
        adapter,
    )
    world.sport.code = adapter.code
    db.session.commit()


def test_positions_catalog_is_frozen():
    assert VOLLEYBALL_POSITIONS == (
        "setter", "outside", "middle", "opposite", "libero"
    )


@pytest.mark.parametrize("position", VOLLEYBALL_POSITIONS)
def test_each_position_is_accepted(client, world, auth_headers, match_factory, position):
    created = match_factory(world)
    response = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=auth_headers(world.owner_a),
        json={"players": [{
            "match_player_id": created.rows[0].id,
            "attendance_status": "present",
            "position": position,
        }]},
    )
    assert response.status_code == 200
    assert db.session.get(MatchPlayer, created.rows[0].id).position == position


def test_invalid_position_is_rejected(client, world, auth_headers, match_factory):
    created = match_factory(world)
    response = client.put(
        f"/api/matches/{created.match.id}/roster/status",
        headers=auth_headers(world.owner_a),
        json={"players": [{
            "match_player_id": created.rows[0].id,
            "attendance_status": "present",
            "position": "goalkeeper",
        }]},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_POSITION"


@pytest.mark.parametrize("position", VOLLEYBALL_POSITIONS)
def test_player_create_accepts_each_position(
    client, world, auth_headers, position
):
    response = client.post(
        "/api/players",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": "Nueva",
            "last_name": "Jugadora",
            "sex": "female",
            "main_position": position,
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert set(payload) == {"message", "player"}
    assert payload["message"] == "Jugador registrado correctamente"
    assert payload["player"]["main_position"] == position


@pytest.mark.parametrize("position", VOLLEYBALL_POSITIONS)
def test_player_update_accepts_each_position(
    client, world, auth_headers, position
):
    player = world.players_a[0]
    response = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": player.first_name,
            "last_name": player.last_name,
            "sex": player.sex,
            "main_position": position,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"message", "player"}
    assert payload["message"] == "Jugador actualizado correctamente"
    assert payload["player"]["main_position"] == position


def test_player_create_rejects_invalid_position(
    client, world, auth_headers
):
    response = client.post(
        "/api/players",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": "Nueva",
            "last_name": "Jugadora",
            "sex": "female",
            "main_position": "goalkeeper",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": True,
        "message": "Posición inválida",
        "code": "INVALID_POSITION",
    }
    assert Player.query.filter_by(first_name="Nueva").first() is None


def test_player_update_rejects_invalid_position_without_mutation(
    client, world, auth_headers
):
    player = world.players_a[0]
    original_position = player.main_position
    response = client.put(
        f"/api/players/{player.id}",
        headers=auth_headers(world.owner_a),
        json={
            "first_name": player.first_name,
            "last_name": player.last_name,
            "sex": player.sex,
            "main_position": "goalkeeper",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": True,
        "message": "Posición inválida",
        "code": "INVALID_POSITION",
    }
    assert db.session.get(Player, player.id).main_position == original_position


@pytest.mark.parametrize("home_sets,opponent_sets", VALID_RESULTS)
def test_valid_volleyball_results(home_sets, opponent_sets):
    result, error = VolleyballAdapter().validate_match_result(
        home_sets,
        opponent_sets,
    )
    assert (result.home_value, result.opponent_value) == (
        home_sets,
        opponent_sets,
    )
    assert result.result == ("win" if home_sets > opponent_sets else "loss")
    assert error is None


@pytest.mark.parametrize("home_sets,opponent_sets", INVALID_RESULTS)
def test_invalid_volleyball_results(home_sets, opponent_sets):
    result, error = VolleyballAdapter().validate_match_result(
        home_sets,
        opponent_sets,
    )
    assert result is None
    assert error


def test_decimal_set_result_is_rejected():
    result, error = VolleyballAdapter().validate_match_result(3, 1.5)
    assert result is None
    assert error


@pytest.mark.parametrize(
    "home_sets,opponent_sets",
    [(3.0, 1.0), ("3", "1")],
)
def test_semantically_integer_values_remain_compatible(home_sets, opponent_sets):
    result, error = VolleyballAdapter().validate_match_result(
        home_sets,
        opponent_sets,
    )
    assert (result.home_value, result.opponent_value) == (3, 1)
    assert result.result == "win"
    assert error is None


@pytest.mark.parametrize(
    "home_sets,opponent_sets,expected",
    [(3, 0, "win"), (2, 3, "loss")],
)
def test_result_endpoint_derives_win_loss(
    client, world, auth_headers, match_factory, home_sets, opponent_sets, expected
):
    created = match_factory(world)
    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=auth_headers(world.coach_a),
        json={"home_sets": home_sets, "opponent_sets": opponent_sets},
    )
    assert response.status_code == 200
    assert response.get_json()["match"]["result"] == expected


def test_match_cannot_finalize_without_valid_result(client, world, auth_headers, match_factory):
    created = match_factory(world)
    response = client.put(
        f"/api/matches/{created.match.id}/finalize",
        headers=auth_headers(world.owner_a),
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_RESULT_INCOMPLETE"


def test_decimal_result_endpoint_rejects_without_mutating_match(
    client, world, auth_headers, match_factory
):
    created = match_factory(world)
    headers = auth_headers(world.owner_a)

    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 1.5},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_MATCH_RESULT"

    db.session.refresh(created.match)
    assert created.match.home_sets == 0
    assert created.match.opponent_sets == 0
    assert created.match.result is None
    assert created.match.match_step == 0

    finalize_response = client.put(
        f"/api/matches/{created.match.id}/finalize",
        headers=headers,
    )
    assert finalize_response.status_code == 409
    assert finalize_response.get_json()["code"] == "MATCH_RESULT_INCOMPLETE"


def test_result_then_finalize_contract(client, world, auth_headers, match_factory):
    created = match_factory(world)
    headers = auth_headers(world.owner_a)
    client.put(
        f"/api/matches/{created.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 1},
    )
    response = client.put(f"/api/matches/{created.match.id}/finalize", headers=headers)
    assert response.status_code == 200
    match = response.get_json()["match"]
    assert match["is_completed"] is True
    assert match["result"] == "win"
    assert {"id", "team_id", "date", "home_sets", "opponent_sets", "match_step", "capture_mode"} <= set(match)


def test_result_endpoint_uses_club_sport_adapter(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = TwoPeriodResultAdapter(
        code="TEST_RESULT",
        name="Deporte de prueba",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
    )
    register_result_adapter(monkeypatch, world, adapter)
    created = match_factory(world)
    headers = auth_headers(world.owner_a)

    for score in [(2, 0), (2, 1)]:
        response = client.put(
            f"/api/matches/{created.match.id}/result",
            headers=headers,
            json={"home_sets": score[0], "opponent_sets": score[1]},
        )
        assert response.status_code == 200
        assert response.get_json()["match"]["result"] == "win"

    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=headers,
        json={"home_sets": 3, "opponent_sets": 0},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_MATCH_RESULT"
    db.session.refresh(created.match)
    assert (created.match.home_sets, created.match.opponent_sets) == (2, 1)

    finalize_response = client.put(
        f"/api/matches/{created.match.id}/finalize",
        headers=headers,
    )
    assert finalize_response.status_code == 200
    assert finalize_response.get_json()["match"]["is_completed"] is True


def test_result_endpoint_rejects_adapter_without_result_contract(
    client,
    world,
    auth_headers,
    match_factory,
    monkeypatch,
):
    volleyball = VolleyballAdapter()
    adapter = SportAdapter(
        code="TEST_NO_RESULT",
        name="Deporte sin resultado",
        capabilities=volleyball.capabilities,
        positions=volleyball.positions,
    )
    register_result_adapter(monkeypatch, world, adapter)
    created = match_factory(world)

    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=auth_headers(world.owner_a),
        json={"home_sets": 3, "opponent_sets": 0},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_RESULT_NOT_SUPPORTED"
    db.session.refresh(created.match)
    assert (created.match.home_sets, created.match.opponent_sets) == (0, 0)
    assert created.match.result is None


def test_completed_match_keeps_result_lock(
    client,
    world,
    auth_headers,
    match_factory,
):
    created = match_factory(world)
    created.match.is_completed = True
    db.session.commit()

    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=auth_headers(world.owner_a),
        json={"home_sets": 3, "opponent_sets": 0},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "MATCH_FINALIZED"


def test_result_endpoint_preserves_cross_tenant_protection(
    client,
    world,
    auth_headers,
    match_factory,
):
    created = match_factory(world, tenant="b")

    response = client.put(
        f"/api/matches/{created.match.id}/result",
        headers=auth_headers(world.owner_a),
        json={"home_sets": 3, "opponent_sets": 0},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"
