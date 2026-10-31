from src.api.models import TeamCoachAssignment


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
