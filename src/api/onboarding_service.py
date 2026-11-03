from datetime import datetime

from src.api.models import Category, Team, TeamPlayer
from src.api.season_service import get_active_season_for_club


def get_club_onboarding_progress(club):
    # El onboarding es un proceso inicial: una vez terminado, los cambios
    # operativos posteriores no lo reabren.
    if club.onboarding_finished_at is not None:
        return {
            "step": 5,
            "status": "completed"
        }

    if not (club.city or club.location):
        return {
            "step": 1,
            "status": "pending"
        }

    categories_count = Category.query.filter_by(
        club_id=club.id
    ).count()

    if categories_count == 0:
        return {
            "step": 2,
            "status": "pending"
        }

    active_season = get_active_season_for_club(club.id)
    active_season_id = active_season.id if active_season else None

    teams_count = Team.query.filter_by(
        club_id=club.id,
        season_id=active_season_id,
        status="active"
    ).count()

    if teams_count == 0:
        return {
            "step": 3,
            "status": "pending"
        }

    players_count = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id,
        Team.season_id == active_season_id,
        Team.status == "active",
        TeamPlayer.left_at.is_(None)
    ).count()

    if players_count == 0:
        return {
            "step": 4,
            "status": "pending"
        }

    return {
        "step": 5,
        "status": "completed"
    }


def is_club_onboarding_complete(club):
    return get_club_onboarding_progress(club)["status"] == "completed"


def finish_club_onboarding(club):
    if club.onboarding_finished_at is None:
        club.onboarding_finished_at = datetime.utcnow()


def finish_club_onboarding_if_complete(club):
    """Llamar antes del commit en toda mutación que pueda completar los requisitos."""
    if is_club_onboarding_complete(club):
        finish_club_onboarding(club)
