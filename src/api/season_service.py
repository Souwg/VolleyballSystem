from datetime import datetime

from src.api.models import MatchSession, Season, Team, Tournament, TrainingSession


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


def get_team_membership_operation_error(team):
    if team.status == "archived":
        return (
            "El equipo está archivado y no admite cambios en su roster",
            "TEAM_ARCHIVED",
            409,
        )

    return get_season_structure_operation_error(team.season)


def get_season_structure_operation_error(season):
    if season and season.status in ["active", "planned"]:
        return None

    return get_season_operation_error(season)


def get_season_open_activities(season):
    team_ids = [
        row[0]
        for row in Team.query.with_entities(Team.id).filter_by(
            club_id=season.club_id,
            season_id=season.id,
        ).all()
    ]

    scheduled_trainings = 0
    open_matches = 0

    if team_ids:
        scheduled_trainings = TrainingSession.query.filter(
            TrainingSession.team_id.in_(team_ids),
            TrainingSession.status == "scheduled",
        ).count()
        open_matches = MatchSession.query.filter(
            MatchSession.team_id.in_(team_ids),
            MatchSession.is_completed.is_(False),
        ).count()

    active_tournaments = Tournament.query.filter_by(
        club_id=season.club_id,
        season_id=season.id,
        status="active",
    ).count()

    return {
        "scheduled_trainings": scheduled_trainings,
        "open_matches": open_matches,
        "active_tournaments": active_tournaments,
    }


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
