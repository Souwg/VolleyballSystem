from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


COUNTRY_TIMEZONE_SUGGESTIONS = {
    "VE": "America/Caracas",
    "CO": "America/Bogota",
}


class ClubTimezoneError(ValueError):
    pass


def normalize_iana_timezone(value):
    timezone_name = str(value or "").strip()

    if not timezone_name:
        return None

    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return None

    return timezone_name


def get_suggested_timezone(country_code):
    return COUNTRY_TIMEZONE_SUGGESTIONS.get(
        str(country_code or "").strip().upper()
    )


def get_club_timezone(club):
    timezone_name = getattr(club, "timezone", None)

    if not timezone_name:
        raise ClubTimezoneError(
            "El club no tiene una zona horaria configurada."
        )

    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ClubTimezoneError(
            "La zona horaria configurada para el club no es válida."
        ) from error


def get_club_now(club, utc_now=None):
    instant = utc_now or datetime.now(datetime_timezone.utc)

    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=datetime_timezone.utc)
    else:
        instant = instant.astimezone(datetime_timezone.utc)

    return instant.astimezone(get_club_timezone(club))


def get_club_today(club, utc_now=None):
    return get_club_now(club, utc_now=utc_now).date()
