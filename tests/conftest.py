import os
import tempfile
import uuid
from datetime import date
from types import SimpleNamespace

import pytest


TEST_DB_PATH = os.path.join(
    tempfile.gettempdir(),
    f"sportflow_pytest_{uuid.uuid4().hex}.db",
)
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["TOKEN_SECRET"] = "sportflow-pytest-secret-123456789"

from flask_jwt_extended import create_access_token

from src.app import app as flask_app
from src.api.models import (
    Category,
    Club,
    MatchPlayer,
    MatchSession,
    Player,
    Sport,
    Team,
    TeamPlayer,
    User,
    db,
)


POSITIONS = [
    "setter",
    "outside",
    "middle",
    "opposite",
    "libero",
    "outside",
    "middle",
    "setter",
]


@pytest.fixture(scope="session")
def app():
    flask_app.config.update(TESTING=True)

    with flask_app.app_context():
        assert db.engine.url.get_backend_name() == "sqlite"
        assert db.engine.url.database == TEST_DB_PATH
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()

    try:
        os.remove(TEST_DB_PATH)
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def isolated_database(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _new_user(role, club, suffix):
    return User(
        id=str(uuid.uuid4()),
        full_name=f"{role} {suffix}",
        email=f"{role}-{suffix.lower()}@example.com",
        password="unused",
        role=role,
        first_login=False,
        is_active=True,
        session_version=0,
        club=club,
    )


def _new_club(sport, suffix):
    owner_id = str(uuid.uuid4())
    club = Club(
        id=str(uuid.uuid4()),
        name=f"Club {suffix}",
        owner_id=owner_id,
        sport=sport,
        timezone="America/Caracas",
        currency_code="USD",
        access_status="active",
    )
    owner = User(
        id=owner_id,
        full_name=f"Owner {suffix}",
        email=f"owner-{suffix.lower()}@example.com",
        password="unused",
        role="club_owner",
        first_login=False,
        is_active=True,
        session_version=0,
        club=club,
    )
    return club, owner


@pytest.fixture
def world(app):
    sport = Sport(
        id=str(uuid.uuid4()),
        code="VOLLEYBALL",
        name="Voleibol",
        is_active=True,
    )
    club_a, owner_a = _new_club(sport, "A")
    club_b, owner_b = _new_club(sport, "B")
    coach_a = _new_user("coach", club_a, "A")
    coach_b = _new_user("coach", club_b, "B")
    staff_a = _new_user("staff", club_a, "A")
    system_admin = _new_user("system_admin", None, "System")

    category_a = Category(name="Adulto A", club=club_a)
    category_b = Category(name="Adulto B", club=club_b)
    team_a = Team(name="Team A", gender="female", category=category_a, club=club_a)
    team_b = Team(name="Team B", gender="female", category=category_b, club=club_b)

    players_a = []
    players_b = []
    memberships = []

    for index, position in enumerate(POSITIONS, start=1):
        player_a = Player(
            first_name=f"Player A{index}",
            last_name="Volleyball",
            sex="female",
            main_position=position,
            is_active=True,
            club=club_a,
        )
        player_b = Player(
            first_name=f"Player B{index}",
            last_name="Volleyball",
            sex="female",
            main_position=position,
            is_active=True,
            club=club_b,
        )
        players_a.append(player_a)
        players_b.append(player_b)
        memberships.extend([
            TeamPlayer(
                team=team_a,
                player=player_a,
                player_number=index,
                status="active",
            ),
            TeamPlayer(
                team=team_b,
                player=player_b,
                player_number=index,
                status="active",
            ),
        ])

    db.session.add_all([
        sport,
        club_a,
        club_b,
        owner_a,
        owner_b,
        coach_a,
        coach_b,
        staff_a,
        system_admin,
        category_a,
        category_b,
        team_a,
        team_b,
        *players_a,
        *players_b,
        *memberships,
    ])
    db.session.commit()

    return SimpleNamespace(
        sport=sport,
        club_a=club_a,
        club_b=club_b,
        owner_a=owner_a,
        owner_b=owner_b,
        coach_a=coach_a,
        coach_b=coach_b,
        staff_a=staff_a,
        system_admin=system_admin,
        category_a=category_a,
        category_b=category_b,
        team_a=team_a,
        team_b=team_b,
        players_a=players_a,
        players_b=players_b,
    )


@pytest.fixture
def auth_headers(app):
    def build(user):
        token = create_access_token(
            identity=user.id,
            additional_claims={"session_version": user.session_version},
        )
        return {"Authorization": f"Bearer {token}"}

    return build


@pytest.fixture
def match_factory():
    def build(
        world,
        *,
        tenant="a",
        capture_mode="live",
        is_completed=False,
        called=True,
        attendance_status="present",
        on_court_count=0,
        did_play=False,
    ):
        team = world.team_a if tenant == "a" else world.team_b
        players = world.players_a if tenant == "a" else world.players_b
        match = MatchSession(
            team=team,
            date=date(2026, 10, 26),
            opponent_name="Rival",
            match_type="official",
            capture_mode=capture_mode,
            is_completed=is_completed,
            created_by=(world.owner_a.id if tenant == "a" else world.owner_b.id),
        )
        db.session.add(match)
        db.session.flush()

        rows = []
        for index, player in enumerate(players):
            row = MatchPlayer(
                match=match,
                player=player,
                player_number=index + 1,
                is_called=called,
                attendance_status=attendance_status if called else None,
                did_play=did_play or index < on_court_count,
                is_on_court=index < on_court_count,
                position=player.main_position if called else None,
            )
            rows.append(row)
            db.session.add(row)

        db.session.commit()
        return SimpleNamespace(match=match, rows=rows)

    return build
