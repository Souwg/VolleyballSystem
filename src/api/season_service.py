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


def get_season_operation_error(season):
    if season and season.status == "active":
        return None

    if season and season.status == "closed":
        return (
            "La temporada está cerrada y no admite nuevas operaciones deportivas",
            "SEASON_CLOSED",
            409,
        )

    return (
        "La operación requiere una temporada activa",
        "ACTIVE_SEASON_REQUIRED",
        409,
    )


def get_team_operation_error(team):
    if team.status == "archived":
        return (
            "El equipo está archivado y no admite nuevas operaciones deportivas",
            "TEAM_ARCHIVED",
            409,
        )

    return get_season_operation_error(team.season)


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
