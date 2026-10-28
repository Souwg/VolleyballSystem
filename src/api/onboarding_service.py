from src.api.models import Category, Team, TeamPlayer


def get_club_onboarding_progress(club):
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

    teams_count = Team.query.filter_by(
        club_id=club.id
    ).count()

    if teams_count == 0:
        return {
            "step": 3,
            "status": "pending"
        }

    players_count = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id
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
