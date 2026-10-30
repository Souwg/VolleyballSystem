from datetime import datetime

from src.api.models import Season


INITIAL_SEASON_NAME = "Temporada inicial"


def get_active_season_for_club(club_id):
    if not club_id:
        return None

    return Season.query.filter_by(
        club_id=club_id,
        status="active"
    ).first()


def build_initial_season(club, created_by=None):
    start_date = (
        club.created_at.date()
        if club.created_at
        else datetime.utcnow().date()
    )

    return Season(
        club_id=club.id,
        name=INITIAL_SEASON_NAME,
        start_date=start_date,
        end_date=None,
        status="active",
        created_by=created_by
    )
