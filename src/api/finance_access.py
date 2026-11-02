FINANCE_ACCESS_ROLES = ("club_owner", "staff")
SPORTS_FINANCE_ROLES = ("club_owner",)

CLUB_FINANCE_FIELDS = (
    "default_enrollment_fee",
    "default_monthly_fee",
)
PLAYER_FINANCE_FIELDS = (
    "enrollment_date",
    "enrollment_fee",
    "monthly_fee",
    "payment_cycle_day",
    "payment_control_start_date",
)
SPORTS_MONEY_FIELDS = frozenset({
    "default_referee_fee",
    "referee_fee",
    "registration_fee",
})

FINANCE_FORBIDDEN_ERROR = (
    "No tienes permisos para acceder a la información financiera",
    "FINANCE_FORBIDDEN",
    403,
)
FINANCE_DEPENDENCY_ERROR = (
    (
        "Este registro tiene cargos asociados. El dueño debe resolverlos "
        "antes de modificar esta información."
    ),
    "FINANCE_DEPENDENCY",
    409,
)


def can_access_finance(user):
    """Cargos existentes, pagos y recibos."""
    return user.role in FINANCE_ACCESS_ROLES


def can_configure_sports_finance(user):
    """Montos de la actividad deportiva y generación de sus cargos."""
    return user.role in SPORTS_FINANCE_ROLES


def get_finance_access_error(user):
    return None if can_access_finance(user) else FINANCE_FORBIDDEN_ERROR


def get_sports_finance_error(user):
    return None if can_configure_sports_finance(user) else FINANCE_FORBIDDEN_ERROR


def get_finance_payload_error(user, body, fields):
    """Rechaza montos enviados por quien no los configura; omitirlos es válido."""
    if can_configure_sports_finance(user):
        return None

    if any(body.get(field) not in (None, "") for field in fields):
        return FINANCE_FORBIDDEN_ERROR

    return None


def charge_blocks_roster_change(charge):
    """Un cargo cancelado sin recibo no se toca al cambiar el roster."""
    return charge.status != "cancelled" or charge.has_receipt_history


def serialize_club_for_user(club, user):
    data = club.serialize()

    if not can_access_finance(user):
        for field in CLUB_FINANCE_FIELDS:
            data.pop(field, None)

    return data


def serialize_user_for_viewer(target, viewer):
    return {
        **target.serialize(),
        "club": (
            serialize_club_for_user(target.club, viewer)
            if target.club
            else None
        ),
    }
