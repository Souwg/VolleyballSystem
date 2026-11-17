from datetime import datetime

from src.api.models import (
    MatchSession,
    Player,
    Season,
    Team,
    TeamCoachAssignment,
    TeamPlayer,
    Tournament,
    TrainingSession,
)
from src.api.team_player_status import VALID_TEAM_PLAYER_STATUSES


INITIAL_SEASON_NAME = "Temporada inicial"


def get_active_season_for_club(club_id):
    if not club_id:
        return None

    return Season.query.filter_by(
        club_id=club_id,
        status="active"
    ).first()


def lock_club_seasons_for_update(club_id):
    """Lock every Season for a Club using one deterministic order.

    Season transition and the preparation writes use this same lock first. A
    preparation request that was waiting for a transition therefore reloads
    the lifecycle before it can write into the former planned Season.
    """
    return Season.query.filter_by(club_id=club_id).order_by(
        Season.id.asc()
    ).populate_existing().with_for_update().all()


def resolve_season_for_read(
    club_id,
    season_id=None,
    default_to_active=True,
):
    """Resolve the active or explicitly requested read-only Season context."""
    if season_id is not None:
        season = Season.query.filter_by(
            id=str(season_id).strip(),
            club_id=club_id,
        ).first()

        if not season:
            return None, (
                "Temporada no encontrada",
                "SEASON_NOT_FOUND",
                404,
            ), True

        return season, None, True

    if not default_to_active:
        return None, None, False

    season = get_active_season_for_club(club_id)

    if not season:
        return None, (
            "El club no tiene una temporada activa",
            "ACTIVE_SEASON_REQUIRED",
            409,
        ), False

    return season, None, False


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


def lock_team_lifecycle(team_id, club_id, exclusive=False):
    """Bloquea Team y luego su Season antes de validar su lifecycle.

    Orden fijo Team -> Season. transition_season toma las Season con FOR
    UPDATE, así que quien crea actividad espera a que termine y vuelve a leer
    el estado; si gana la creación, la transición espera y ve la actividad.
    exclusive=True bloquea el Team con FOR UPDATE (asignaciones de coach).
    populate_existing porque el lock no refresca lo ya cargado en la sesión.
    """
    team = Team.query.filter_by(
        id=team_id,
        club_id=club_id,
    ).populate_existing().with_for_update(read=not exclusive).first()

    if team:
        lock_season_for_operation(team.season_id, club_id)

    return team


def lock_season_for_operation(season_id, club_id):
    return Season.query.filter_by(
        id=season_id,
        club_id=club_id,
    ).populate_existing().with_for_update(read=True).first()


def lock_active_season_for_operation(club_id):
    """Temporada activa resuelta con su lock compartido ya tomado.

    Si una transición termina mientras se espera el lock, la temporada leída
    ya está cerrada: se resuelve otra vez y se usa la nueva activa.
    """
    for _ in range(2):
        season = get_active_season_for_club(club_id)

        if not season:
            return None

        season = lock_season_for_operation(season.id, club_id)

        if season and season.status == "active":
            return season

    return None


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


def _ranges_overlap(first, second):
    first_ends_after_second_starts = (
        first.end_date is None or first.end_date >= second.start_date
    )
    second_ends_after_first_starts = (
        second.end_date is None or second.end_date >= first.start_date
    )
    return first_ends_after_second_starts and second_ends_after_first_starts


def build_season_activation_preflight(target, source=None):
    """Build the canonical readiness result used by preflight and transition."""
    active_teams = Team.query.filter_by(
        club_id=target.club_id,
        season_id=target.id,
        status="active",
    ).order_by(Team.name.asc()).all()
    team_ids = [team.id for team in active_teams]

    memberships = []
    if team_ids:
        memberships = TeamPlayer.query.join(Player).filter(
            TeamPlayer.team_id.in_(team_ids),
            TeamPlayer.left_at.is_(None),
        ).all()

    memberships_by_team = {team_id: [] for team_id in team_ids}
    invalid_memberships = []
    seen_players = set()
    seen_numbers = set()

    for membership in memberships:
        memberships_by_team[membership.team_id].append(membership)
        team = membership.team
        player = membership.player
        player_key = (membership.team_id, membership.player_id)
        number_key = (membership.team_id, membership.player_number)
        reasons = []

        if not player or player.club_id != target.club_id or not player.is_active:
            reasons.append("PLAYER_INACTIVE")
        if (
            player
            and team.gender != "mixed"
            and player.sex != team.gender
        ):
            reasons.append("PLAYER_GENDER_MISMATCH")
        if membership.status not in VALID_TEAM_PLAYER_STATUSES:
            reasons.append("INVALID_PLAYER_STATUS")
        if (
            not isinstance(membership.player_number, int)
            or membership.player_number < 1
            or membership.player_number > 99
        ):
            reasons.append("INVALID_PLAYER_NUMBER")
        if player_key in seen_players:
            reasons.append("PLAYER_ALREADY_IN_TEAM")
        if number_key in seen_numbers:
            reasons.append("PLAYER_NUMBER_DUPLICATED")

        seen_players.add(player_key)
        seen_numbers.add(number_key)

        if reasons:
            invalid_memberships.append({
                "membership_id": membership.id,
                "team_id": membership.team_id,
                "player_id": membership.player_id,
                "reasons": reasons,
            })

    coached_team_ids = set()
    if team_ids:
        coached_team_ids = {
            row[0]
            for row in TeamCoachAssignment.query.with_entities(
                TeamCoachAssignment.team_id
            ).filter(
                TeamCoachAssignment.club_id == target.club_id,
                TeamCoachAssignment.team_id.in_(team_ids),
                TeamCoachAssignment.removed_at.is_(None),
            ).distinct().all()
        }

    teams_without_players = sum(
        not memberships_by_team.get(team.id) for team in active_teams
    )
    teams_without_coach = sum(
        team.id not in coached_team_ids for team in active_teams
    )
    activities = (
        get_season_open_activities(source)
        if source
        else {
            "scheduled_trainings": 0,
            "open_matches": 0,
            "active_tournaments": 0,
        }
    )

    blockers = []
    if not active_teams:
        blockers.append({
            "code": "SEASON_TEAM_REQUIRED",
            "message": "Agrega al menos un equipo antes de activar esta temporada.",
            "count": 0,
            "action": {
                "label": "Preparar equipos",
                "href": f"/categories?season={target.id}",
            },
        })

    activity_blockers = (
        (
            "SCHEDULED_TRAININGS",
            "Entrenamientos programados pendientes",
            "scheduled_trainings",
            "Ver entrenamientos pendientes",
            "/trainings",
        ),
        (
            "OPEN_MATCHES",
            "Partidos abiertos pendientes",
            "open_matches",
            "Ver partidos pendientes",
            "/matches",
        ),
        (
            "ACTIVE_TOURNAMENTS",
            "Torneos activos pendientes",
            "active_tournaments",
            "Ver torneos pendientes",
            "/tournaments",
        ),
    )
    if source:
        for code, message, key, label, path in activity_blockers:
            count = activities[key]
            if count:
                blockers.append({
                    "code": code,
                    "message": message,
                    "count": count,
                    "action": {
                        "label": label,
                        "href": f"{path}?season={source.id}",
                    },
                })

    if invalid_memberships:
        blockers.append({
            "code": "TARGET_ROSTER_INVALID",
            "message": "El roster preparado contiene datos que deben corregirse.",
            "count": len(invalid_memberships),
            "details": invalid_memberships,
            "action": {
                "label": "Revisar equipos",
                "href": f"/categories?season={target.id}",
            },
        })

    warnings = []
    if teams_without_players:
        warnings.append({
            "code": "TEAMS_WITHOUT_PLAYERS",
            "message": "Hay equipos sin deportistas asignados.",
            "count": teams_without_players,
        })
    if teams_without_coach:
        warnings.append({
            "code": "TEAMS_WITHOUT_COACH",
            "message": "Hay equipos sin entrenador asignado.",
            "count": teams_without_coach,
            "action": {
                "label": "Asignar entrenadores",
                "href": f"/categories?season={target.id}",
            },
        })

    other_seasons = Season.query.filter(
        Season.club_id == target.club_id,
        Season.id != target.id,
    ).all()
    if any(season.name.lower() == target.name.lower() for season in other_seasons):
        warnings.append({
            "code": "DUPLICATE_SEASON_NAME",
            "message": "Ya existe otra temporada con este nombre.",
            "count": 1,
        })
    if any(_ranges_overlap(target, season) for season in other_seasons):
        warnings.append({
            "code": "SEASON_DATES_OVERLAP",
            "message": "Las fechas se solapan con otra temporada.",
            "count": 1,
        })

    return {
        "mode": "transition" if source else "recovery",
        "source": source.serialize() if source else None,
        "target": target.serialize(),
        "can_activate": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "total_teams": len(active_teams),
            "total_players": len(memberships),
            "teams_without_players": teams_without_players,
            "teams_without_coach": teams_without_coach,
            **activities,
        },
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
