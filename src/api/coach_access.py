from src.api.models import Season, Team, TeamCoachAssignment, TeamPlayer, db


COACH_ACCESS_CLUB_WIDE = "club_wide"
COACH_ACCESS_TEAM_ASSIGNED = "team_assigned"


def _is_scoped_coach(user):
    return (
        user.role == "coach"
        and user.club is not None
        and user.club.coach_access_mode == COACH_ACCESS_TEAM_ASSIGNED
    )


def _open_assignments(user):
    return TeamCoachAssignment.query.filter(
        TeamCoachAssignment.user_id == user.id,
        TeamCoachAssignment.club_id == user.club_id,
        TeamCoachAssignment.removed_at.is_(None),
    )


def can_manage_team(user, team):
    if not user.club_id or team.club_id != user.club_id:
        return False

    if user.role == "club_owner":
        return True

    if user.role != "coach":
        return False

    if not _is_scoped_coach(user):
        return True

    return _open_assignments(user).filter(
        TeamCoachAssignment.team_id == team.id
    ).first() is not None


def get_team_assignment_error(user, team):
    if can_manage_team(user, team):
        return None

    if user.role == "coach" and user.club_id == team.club_id:
        return (
            "No tienes asignado este equipo",
            "TEAM_NOT_ASSIGNED",
            403,
        )

    return (
        "No tienes permisos para operar este equipo",
        "FORBIDDEN",
        403,
    )


def can_edit_player_profile(user, player):
    if not user.club_id or player.club_id != user.club_id:
        return False

    if user.role == "club_owner":
        return True

    if user.role != "coach":
        return False

    assigned_team_ids = get_assigned_team_ids(user)

    if assigned_team_ids is None:
        return True

    # Cerrar una temporada o archivar un equipo no cierra la membership, pero
    # esa relación ya es histórica y no decide quién edita el perfil global.
    current_team_ids = {
        team_id
        for (team_id,) in db.session.query(TeamPlayer.team_id).join(
            Team,
            Team.id == TeamPlayer.team_id,
        ).join(
            Season,
            Season.id == Team.season_id,
        ).filter(
            TeamPlayer.player_id == player.id,
            TeamPlayer.left_at.is_(None),
            Team.status == "active",
            Season.status.in_(["active", "planned"]),
        ).all()
    }

    return not current_team_ids or bool(current_team_ids & assigned_team_ids)


def get_player_profile_error(user, player):
    if can_edit_player_profile(user, player):
        return None

    if user.role == "coach" and user.club_id == player.club_id:
        return (
            "No tienes asignado ningún equipo actual de esta jugadora",
            "TEAM_NOT_ASSIGNED",
            403,
        )

    return (
        "No tienes permisos para modificar esta jugadora",
        "FORBIDDEN",
        403,
    )


def can_manage_club_sports_entity(user):
    if user.role == "club_owner":
        return True

    return user.role == "coach" and not _is_scoped_coach(user)


def get_club_sports_entity_error(user):
    if can_manage_club_sports_entity(user):
        return None

    return (
        "Solo el dueño del club puede gestionar esta entidad deportiva",
        "FORBIDDEN",
        403,
    )


def get_assigned_team_ids(user):
    """None significa sin restricción por asignación; solo Owner y Coach club_wide."""
    if user.role == "club_owner":
        return None

    if user.role != "coach":
        return set()

    if not _is_scoped_coach(user):
        return None

    return {
        assignment.team_id
        for assignment in _open_assignments(user).all()
    }
