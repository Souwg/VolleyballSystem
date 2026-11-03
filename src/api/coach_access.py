from src.api.finance_access import (
    PLAYER_FINANCE_FIELDS,
    SPORTS_MONEY_FIELDS,
    can_access_finance,
)
from src.api.models import Season, Team, TeamCoachAssignment, TeamPlayer, User, db


COACH_ACCESS_CLUB_WIDE = "club_wide"
COACH_ACCESS_TEAM_ASSIGNED = "team_assigned"
COACH_ACCESS_MODES = (COACH_ACCESS_CLUB_WIDE, COACH_ACCESS_TEAM_ASSIGNED)

CURRENT_SEASON_STATUSES = ("active", "planned")

PLAYER_SENSITIVE_FIELDS = (
    "birth_date",
    "representative_name",
    "representative_phone",
)


def is_scoped_coach(user):
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

    if not is_scoped_coach(user):
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


def get_team_access_resolver(user):
    """Metadata de lectura de un equipo para el usuario.

    is_assigned: existe una asignación abierta entre el Coach y el equipo.
    can_manage: permiso por scoping, igual que can_manage_team. No incluye el
    lifecycle: un equipo archivado o de una temporada cerrada puede dar True y
    sus mutaciones siguen rechazándose con TEAM_ARCHIVED o SEASON_CLOSED.
    """
    assigned_team_ids = (
        {assignment.team_id for assignment in _open_assignments(user).all()}
        if user.role == "coach" and user.club_id
        else set()
    )
    scoped = is_scoped_coach(user)

    def resolve(team):
        same_club = bool(user.club_id) and team.club_id == user.club_id
        is_assigned = same_club and team.id in assigned_team_ids

        if not same_club:
            can_manage = False
        elif user.role == "club_owner":
            can_manage = True
        elif user.role == "coach":
            can_manage = is_assigned if scoped else True
        else:
            can_manage = False

        return {"is_assigned": is_assigned, "can_manage": can_manage}

    return resolve


def is_current_membership(membership):
    """Python de la misma regla que _current_team_ids_by_player."""
    return (
        membership.left_at is None
        and membership.team.status == "active"
        and membership.team.season is not None
        and membership.team.season.status in CURRENT_SEASON_STATUSES
    )


def _current_team_ids_by_player(player_ids):
    # Cerrar una temporada o archivar un equipo no cierra la membership, pero
    # esa relación ya es histórica y no da acceso al perfil global ni al contacto.
    current_team_ids = {}

    if not player_ids:
        return current_team_ids

    rows = db.session.query(TeamPlayer.player_id, TeamPlayer.team_id).join(
        Team,
        Team.id == TeamPlayer.team_id,
    ).join(
        Season,
        Season.id == Team.season_id,
    ).filter(
        TeamPlayer.player_id.in_(player_ids),
        TeamPlayer.left_at.is_(None),
        Team.status == "active",
        Season.status.in_(CURRENT_SEASON_STATUSES),
    ).all()

    for player_id, team_id in rows:
        current_team_ids.setdefault(player_id, set()).add(team_id)

    return current_team_ids


def get_player_profile_access_resolver(user, players):
    """Quién puede editar el perfil global y ver el contacto de cada Player."""
    if not user.club_id or user.role not in ["club_owner", "coach"]:
        return lambda player: False

    assigned_team_ids = get_assigned_team_ids(user)

    if assigned_team_ids is None:
        return lambda player: player.club_id == user.club_id

    current_team_ids = _current_team_ids_by_player([
        player.id
        for player in players
    ])

    def resolve(player):
        if player.club_id != user.club_id:
            return False

        player_team_ids = current_team_ids.get(player.id)
        return (
            not player_team_ids
            or bool(player_team_ids & assigned_team_ids)
        )

    return resolve


def can_edit_player_profile(user, player):
    return get_player_profile_access_resolver(user, [player])(player)


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


def get_player_serializer(user, players):
    """Serializa Players para el usuario. Evita una consulta por jugadora.

    Owner y Staff reciben Player.serialize() sin cambios. Ningún Coach recibe
    datos de cobro; el Coach team_assigned tampoco recibe el contacto ni la
    fecha de nacimiento de quien no entrena.
    """
    if user.role != "coach":
        return lambda player: player.serialize()

    can_view_contact = get_player_profile_access_resolver(user, players)

    def serialize(player):
        data = player.serialize()

        for field in PLAYER_FINANCE_FIELDS:
            data.pop(field, None)

        if not can_view_contact(player):
            for field in PLAYER_SENSITIVE_FIELDS:
                data.pop(field, None)

        return data

    return serialize


def serialize_player_for_user(player, user):
    return get_player_serializer(user, [player])(player)


def serialize_with_player_for_user(row, user, player_serializer=None):
    """Para serializers de modelos que anidan la Player completa."""
    serialize_player = (
        player_serializer
        or get_player_serializer(user, [row.player])
    )

    return {
        **row.serialize(),
        "player": serialize_player(row.player) if row.player else None,
    }


def redact_sports_money_for_user(user, payload):
    """Quita montos de una respuesta deportiva para quien no accede a Finance."""
    if can_access_finance(user):
        return payload

    def redact(value):
        if isinstance(value, dict):
            return {
                key: redact(item)
                for key, item in value.items()
                if key not in SPORTS_MONEY_FIELDS
            }

        if isinstance(value, list):
            return [redact(item) for item in value]

        return value

    return redact(payload)


def can_manage_club_sports_entity(user):
    if user.role == "club_owner":
        return True

    return user.role == "coach" and not is_scoped_coach(user)


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

    if not is_scoped_coach(user):
        return None

    return {
        assignment.team_id
        for assignment in _open_assignments(user).all()
    }


def get_coach_access_readiness(club_id):
    """Conteos informativos para activar el acceso por equipos; no son requisito.

    Los equipos archivados y las temporadas cerradas no son operación pendiente.
    """
    teams = db.session.query(Team.id, Season.status).join(
        Season,
        Season.id == Team.season_id,
    ).filter(
        Team.club_id == club_id,
        Team.status == "active",
        Season.status.in_(CURRENT_SEASON_STATUSES),
    ).all()
    assignments = db.session.query(
        TeamCoachAssignment.team_id,
        TeamCoachAssignment.user_id,
    ).filter(
        TeamCoachAssignment.club_id == club_id,
        TeamCoachAssignment.removed_at.is_(None),
    ).all()
    coach_ids = {
        user_id
        for (user_id,) in db.session.query(User.id).filter(
            User.club_id == club_id,
            User.role == "coach",
            User.is_active.is_(True),
        ).all()
    }
    current_team_ids = {team_id for team_id, _ in teams}
    staffed_team_ids = {
        team_id
        for team_id, user_id in assignments
        if user_id in coach_ids
    }
    assigned_coach_ids = {
        user_id
        for team_id, user_id in assignments
        if team_id in current_team_ids
    }

    return {
        "active_coaches": len(coach_ids),
        "coaches_without_team": len(coach_ids - assigned_coach_ids),
        "active_teams_without_coach": sum(
            1
            for team_id, season_status in teams
            if season_status == "active" and team_id not in staffed_team_ids
        ),
        "planned_teams_without_coach": sum(
            1
            for team_id, season_status in teams
            if season_status == "planned" and team_id not in staffed_team_ids
        ),
    }
