import calendar
import math
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from src.api.models import db, Player, PlayerPayment
from src.api.time_utils import get_club_today


VALID_PAYMENT_METHODS = [
    "cash",
    "transfer",
    "zelle",
    "mobile_payment",
    "other"
]


def validate_manual_payment_settlement(
    payment_method,
    payment_date,
    as_of
):
    """Valida los datos mínimos de una liquidación manual."""
    if not payment_method:
        return (
            "El método de pago es obligatorio",
            "PAYMENT_METHOD_REQUIRED"
        )

    if payment_method not in VALID_PAYMENT_METHODS:
        return (
            "Método de pago inválido",
            "INVALID_PAYMENT_METHOD"
        )

    if not payment_date:
        return (
            "La fecha de pago es obligatoria",
            "PAYMENT_DATE_REQUIRED"
        )

    if payment_date > as_of:
        return (
            "La fecha de pago no puede estar en el futuro.",
            "INVALID_PAYMENT_DATE"
        )

    return None


def add_months(source_date, months=1):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1

    day = min(
        source_date.day,
        calendar.monthrange(year, month)[1]
    )

    return source_date.replace(
        year=year,
        month=month,
        day=day
    )


def get_first_payment_cycle_on_or_after(
    enrollment_date,
    target_date
):
    """
    Obtiene el primer ciclo mensual que cae en target_date
    o después, manteniendo como ancla la fecha original
    de inscripción.
    """

    months_difference = (
        (target_date.year - enrollment_date.year) * 12
        + target_date.month
        - enrollment_date.month
    )

    months_difference = max(months_difference, 0)

    candidate = add_months(
        enrollment_date,
        months_difference
    )

    if candidate < target_date:
        candidate = add_months(
            enrollment_date,
            months_difference + 1
        )

    return candidate

def get_payment_cycle_containing_date(
    enrollment_date,
    target_date
):
    """
    Obtiene el inicio del ciclo mensual que contiene
    target_date, manteniendo como ancla la fecha original
    de inscripción.

    Ejemplo:
    inscripción: 06/07/2026
    fecha objetivo: 15/08/2026
    resultado: 06/08/2026
    """

    if target_date <= enrollment_date:
        return enrollment_date

    months_difference = (
        (target_date.year - enrollment_date.year) * 12
        + target_date.month
        - enrollment_date.month
    )

    months_difference = max(
        months_difference,
        0
    )

    candidate = add_months(
        enrollment_date,
        months_difference
    )

    # Ejemplo especial:
    # inscripción 31/01
    # target 15/02
    #
    # add_months(31/01, 1) = 28/02,
    # pero el 15/02 todavía pertenece al ciclo
    # iniciado el 31/01.
    if (
        candidate > target_date
        and months_difference > 0
    ):
        candidate = add_months(
            enrollment_date,
            months_difference - 1
        )

    return candidate


def _resolve_as_of(as_of=None, club=None):
    if as_of is not None:
        return as_of

    return get_club_today(club)


def _get_player_name(player):
    return " ".join(
        part
        for part in [player.first_name, player.last_name]
        if part
    )


def get_effective_monthly_fee(player, club):
    return (
        player.monthly_fee
        if player.monthly_fee is not None
        else club.default_monthly_fee
    )


PAYMENT_CONFIGURATION_MESSAGES = {
    "inactive": "La jugadora está inactiva y no genera nuevas mensualidades.",
    "invalid_monthly_fee": "La mensualidad efectiva no es válida.",
    "missing_enrollment_date": "Falta la fecha de inscripción.",
    "missing_payment_control_start_date": (
        "El control mensual todavía no está configurado."
    ),
    "legacy_payment_history_requires_review": (
        "Existe historial anterior y el control mensual requiere revisión."
    ),
    "payment_control_not_started": (
        "El control mensual comienza después de la fecha de referencia."
    ),
}

_MONTHLY_FEE_UNSET = object()


def get_player_monthly_configuration_issue(
    player,
    club,
    as_of=None,
    has_existing_base_payment=False,
    include_non_actionable=False,
    monthly_fee_override=_MONTHLY_FEE_UNSET,
):
    """Evalúa la configuración mensual sin crear ni modificar registros."""
    as_of = _resolve_as_of(as_of, club)

    if player.is_active is False:
        reason = "inactive"
    else:
        monthly_fee = (
            monthly_fee_override
            if monthly_fee_override is not _MONTHLY_FEE_UNSET
            else get_effective_monthly_fee(player, club)
        )

        try:
            normalized_monthly_fee = float(monthly_fee or 0)
        except (TypeError, ValueError):
            normalized_monthly_fee = 0

        if (
            not math.isfinite(normalized_monthly_fee)
            or normalized_monthly_fee <= 0
        ):
            reason = "invalid_monthly_fee"
        elif not player.enrollment_date:
            reason = "missing_enrollment_date"
        elif not player.payment_control_start_date:
            reason = (
                "legacy_payment_history_requires_review"
                if has_existing_base_payment
                else "missing_payment_control_start_date"
            )
        elif player.payment_control_start_date > as_of:
            reason = "payment_control_not_started"
        else:
            return None

    if (
        not include_non_actionable
        and reason in ["inactive", "payment_control_not_started"]
    ):
        return None

    return {
        "reason": reason,
        "message": PAYMENT_CONFIGURATION_MESSAGES[reason],
    }


def calculate_player_monthly_payment_plan(
    player,
    monthly_fee,
    as_of=None
):
    """Calcula mensualidades faltantes sin modificar la sesión."""
    as_of = _resolve_as_of(as_of, player.club)

    configuration_issue = get_player_monthly_configuration_issue(
        player=player,
        club=player.club,
        as_of=as_of,
        include_non_actionable=True,
        monthly_fee_override=monthly_fee,
    )

    if configuration_issue:
        reason = configuration_issue["reason"]

        return {
            "skip_reason": reason,
            "payments_to_create": []
        }

    normalized_monthly_fee = float(monthly_fee)

    enrollment_date = player.enrollment_date
    control_start = player.payment_control_start_date

    months_difference = (
        (control_start.year - enrollment_date.year) * 12
        + control_start.month
        - enrollment_date.month
    )
    offset = max(months_difference, 0)

    existing_period_starts = {
        period_start
        for (period_start,) in db.session.query(
            PlayerPayment.period_start
        ).filter(
            PlayerPayment.club_id == player.club_id,
            PlayerPayment.player_id == player.id,
            PlayerPayment.payment_type == "monthly",
            PlayerPayment.period_start.isnot(None)
        ).all()
    }

    payments_to_create = []

    while True:
        period_start = add_months(
            enrollment_date,
            offset
        )

        if period_start < control_start:
            offset += 1
            continue

        if period_start > as_of:
            break

        period_end = (
            add_months(
                enrollment_date,
                offset + 1
            )
            - timedelta(days=1)
        )
        due_date = period_start + timedelta(days=5)

        if period_start not in existing_period_starts:
            payments_to_create.append({
                "club_id": player.club_id,
                "player_id": player.id,
                "player_name": _get_player_name(player),
                "payment_type": "monthly",
                "amount": normalized_monthly_fee,
                "currency_code": player.club.currency_code,
                "status": (
                    "overdue"
                    if due_date < as_of
                    else "pending"
                ),
                "period_start": period_start,
                "period_end": period_end,
                "due_date": due_date
            })

        offset += 1

    return {
        "skip_reason": None,
        "payments_to_create": payments_to_create
    }


def calculate_monthly_sync_preview(
    club,
    player=None,
    as_of=None
):
    """Construye el plan de sincronización mensual sin escribir en la DB."""
    as_of = _resolve_as_of(as_of, club)

    if player is not None:
        players = [player]
        payments_query = PlayerPayment.query.filter_by(
            club_id=club.id,
            player_id=player.id
        )
    else:
        players = Player.query.filter_by(
            club_id=club.id
        ).order_by(
            Player.created_at.asc()
        ).all()
        payments_query = PlayerPayment.query.filter_by(
            club_id=club.id
        )

    existing_payments = payments_query.all()
    existing_base_payment_player_ids = {
        payment.player_id
        for payment in existing_payments
        if payment.payment_type in ["enrollment", "monthly"]
    }

    payments_to_create = []
    skipped_players = []
    warnings = []
    skipped_inactive = 0
    skipped_unconfigured = 0
    skipped_not_started = 0

    for current_player in players:
        monthly_fee = get_effective_monthly_fee(
            current_player,
            club
        )
        player_plan = calculate_player_monthly_payment_plan(
            player=current_player,
            monthly_fee=monthly_fee,
            as_of=as_of
        )
        skip_reason = player_plan["skip_reason"]

        if skip_reason:
            if skip_reason == "inactive":
                skipped_inactive += 1
            elif skip_reason == "payment_control_not_started":
                skipped_not_started += 1
            else:
                skipped_unconfigured += 1

            public_reason = skip_reason
            message = PAYMENT_CONFIGURATION_MESSAGES[skip_reason]

            if (
                skip_reason == "missing_payment_control_start_date"
                and current_player.id in existing_base_payment_player_ids
            ):
                public_reason = "legacy_payment_history_requires_review"
                message = PAYMENT_CONFIGURATION_MESSAGES[public_reason]

            skipped_player = {
                "player_id": current_player.id,
                "player_name": _get_player_name(current_player),
                "reason": public_reason,
                "message": message
            }
            skipped_players.append(skipped_player)

            if public_reason not in ["inactive", "payment_control_not_started"]:
                warnings.append(skipped_player.copy())

            continue

        payments_to_create.extend(
            player_plan["payments_to_create"]
        )

    payments_to_mark_overdue = []

    for payment in existing_payments:
        if (
            payment.status == "pending"
            and payment.due_date
            and payment.due_date < as_of
        ):
            payments_to_mark_overdue.append({
                "payment_id": payment.id,
                "club_id": payment.club_id,
                "payment_type": payment.payment_type,
                "player_id": payment.player_id,
                "player_name": (
                    _get_player_name(payment.player)
                    if payment.player
                    else ""
                ),
                "period_start": payment.period_start,
                "period_end": payment.period_end,
                "due_date": payment.due_date,
                "current_status": payment.status,
                "projected_status": "overdue"
            })

    return {
        "as_of": as_of,
        "summary": {
            "payments_to_create": len(payments_to_create),
            "payments_to_mark_overdue": len(
                payments_to_mark_overdue
            ),
            "existing_payments": len(existing_payments),
            "players_evaluated": len(players),
            "players_skipped_inactive": skipped_inactive,
            "players_skipped_unconfigured": skipped_unconfigured,
            "players_skipped_not_started": skipped_not_started
        },
        "payments_to_create": payments_to_create,
        "payments_to_mark_overdue": payments_to_mark_overdue,
        "skipped_players": skipped_players,
        "warnings": warnings
    }


def serialize_monthly_sync_preview(preview):
    serialized = {
        **preview,
        "as_of": preview["as_of"].isoformat(),
        "payments_to_create": [],
        "payments_to_mark_overdue": []
    }

    for payment in preview["payments_to_create"]:
        serialized["payments_to_create"].append({
            **payment,
            "period_start": payment["period_start"].isoformat(),
            "period_end": payment["period_end"].isoformat(),
            "due_date": payment["due_date"].isoformat()
        })

    for payment in preview["payments_to_mark_overdue"]:
        serialized["payments_to_mark_overdue"].append({
            **payment,
            "period_start": (
                payment["period_start"].isoformat()
                if payment["period_start"]
                else None
            ),
            "period_end": (
                payment["period_end"].isoformat()
                if payment["period_end"]
                else None
            ),
            "due_date": payment["due_date"].isoformat()
        })

    return serialized


def apply_monthly_sync(plan, user_id=None):
    """
    Aplica un plan calculado por calculate_monthly_sync_preview().

    No realiza commit. El llamador controla la unidad transaccional.
    """
    payments_created = []
    payments_marked_overdue = []

    for candidate in plan["payments_to_create"]:
        payment = PlayerPayment(
            club_id=candidate["club_id"],
            player_id=candidate["player_id"],
            payment_type="monthly",
            amount=candidate["amount"],
            currency_code=candidate["currency_code"],
            status=candidate["status"],
            period_start=candidate["period_start"],
            period_end=candidate["period_end"],
            due_date=candidate["due_date"],
            created_by=user_id
        )

        if add_monthly_payment_if_absent(payment):
            payments_created.append(candidate)

    for transition in plan["payments_to_mark_overdue"]:
        payment = PlayerPayment.query.filter_by(
            id=transition["payment_id"],
            club_id=transition["club_id"]
        ).first()

        if (
            payment
            and payment.status == transition["current_status"]
            and transition["projected_status"] == "overdue"
        ):
            payment.status = "overdue"
            payments_marked_overdue.append(transition)

    return {
        "as_of": plan["as_of"],
        "summary": {
            "payments_planned_to_create": len(
                plan["payments_to_create"]
            ),
            "payments_created": len(payments_created),
            "payments_not_created": (
                len(plan["payments_to_create"])
                - len(payments_created)
            ),
            "payments_planned_to_mark_overdue": len(
                plan["payments_to_mark_overdue"]
            ),
            "payments_marked_overdue": len(
                payments_marked_overdue
            ),
            "overdue_transitions_not_applied": (
                len(plan["payments_to_mark_overdue"])
                - len(payments_marked_overdue)
            )
        },
        "payments_created": payments_created,
        "payments_marked_overdue": payments_marked_overdue
    }


def execute_monthly_sync(
    club,
    player=None,
    as_of=None,
    user_id=None
):
    """
    Recalcula y aplica una sincronización mensual en la sesión actual.

    No realiza commit. El llamador conserva el control de la transacción.
    """
    as_of = _resolve_as_of(as_of, club)
    connection = db.session.connection()

    # pysqlite difiere BEGIN hasta la primera escritura. Si esa escritura
    # ocurre dentro de un savepoint, RELEASE puede escapar al rollback de la
    # unidad exterior. Iniciamos explícitamente la transacción en desarrollo.
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    plan = calculate_monthly_sync_preview(
        club=club,
        player=player,
        as_of=as_of
    )
    result = apply_monthly_sync(
        plan,
        user_id=user_id
    )

    return plan, result


def add_monthly_payment_if_absent(payment):
    """Inserta una mensualidad sin invalidar la transacción si otro proceso gana la carrera."""
    existing_payment = PlayerPayment.query.filter_by(
        club_id=payment.club_id,
        player_id=payment.player_id,
        payment_type="monthly",
        period_start=payment.period_start
    ).first()

    if existing_payment:
        return False

    # begin_nested hace flush de cambios anteriores antes de abrir el savepoint.
    # Solo el INSERT de esta mensualidad queda dentro del savepoint.
    savepoint = db.session.begin_nested()

    try:
        with savepoint:
            db.session.add(payment)
            db.session.flush()
    except IntegrityError as error:
        # La sesión exterior sigue utilizable tras el rollback del savepoint.
        # Propagamos errores de integridad que no sean esta misma mensualidad.
        constraint_name = getattr(
            getattr(error.orig, "diag", None),
            "constraint_name",
            None
        )

        if constraint_name and constraint_name != "uq_player_payments_monthly_cycle":
            raise

        if PlayerPayment.query.filter_by(
            club_id=payment.club_id,
            player_id=payment.player_id,
            payment_type="monthly",
            period_start=payment.period_start
        ).first() is None:
            raise

        return False

    return True


def sync_player_monthly_payments(
    player,
    monthly_fee,
    user_id,
    as_of=None
):
    as_of = _resolve_as_of(as_of, player.club)
    plan = calculate_player_monthly_payment_plan(
        player=player,
        monthly_fee=monthly_fee,
        as_of=as_of
    )
    result = apply_monthly_sync(
        {
            "as_of": as_of,
            "payments_to_create": plan["payments_to_create"],
            "payments_to_mark_overdue": []
        },
        user_id=user_id
    )

    return result["summary"]["payments_created"]

def initialize_player_payment_history(
    player,
    enrollment_fee,
    monthly_fee,
    enrollment_status,
    initial_payment_mode,
    last_paid_month,
    user_id
):
    """
    Inicializa por primera vez el estado de pagos de un deportista.

    enrollment_status:
    - pending
    - paid_before_sportflow
    - not_applicable

    initial_payment_mode:
    - import_history
    - start_now

    last_paid_month:
    - "YYYY-MM" si se trae historial
    - None si no existe ninguna mensualidad histórica pagada
    """

    today = get_club_today(player.club)

    # =====================================================
    # 1. INSCRIPCIÓN
    # =====================================================

    if enrollment_status != "not_applicable" and enrollment_fee > 0:

        if enrollment_status == "paid_before_sportflow":
            enrollment_payment = PlayerPayment(
                club_id=player.club_id,
                player_id=player.id,
                payment_type="enrollment",
                amount=enrollment_fee,
                currency_code=player.club.currency_code,
                status="paid",
                due_date=player.enrollment_date,
                settlement_source="migration",
                created_by=user_id
            )

        else:
            enrollment_status_value = (
                "overdue"
                if player.enrollment_date < today
                else "pending"
            )

            enrollment_payment = PlayerPayment(
                club_id=player.club_id,
                player_id=player.id,
                payment_type="enrollment",
                amount=enrollment_fee,
                currency_code=player.club.currency_code,
                status=enrollment_status_value,
                due_date=player.enrollment_date,
                settlement_source=None,
                created_by=user_id
            )

        db.session.add(enrollment_payment)

    # =====================================================
    # 2. EMPEZAR DESDE AHORA
    # =====================================================

    if initial_payment_mode == "start_now":

        # El control comienza en el ciclo que está vigente hoy.
        #
        # Ejemplo:
        # inscripción: 06/07
        # hoy: 15/08
        #
        # ciclo anterior:
        # 06/07 -> 05/08   (se ignora)
        #
        # ciclo actual:
        # 06/08 -> 05/09   (entra en SportFlow)
        control_start = get_payment_cycle_containing_date(
            player.enrollment_date,
            today
        )

        player.payment_control_start_date = control_start

        created_monthly_payments = (
            sync_player_monthly_payments(
                player=player,
                monthly_fee=monthly_fee,
                user_id=user_id
            )
        )

        return {
            "mode": "start_now",
            "payment_control_start_date": control_start,
            "migrated_months": 0,
            "unpaid_months": created_monthly_payments
        }

    # =====================================================
    # 3. TRAER HISTORIAL ANTERIOR
    # =====================================================

    player.payment_control_start_date = player.enrollment_date

    last_paid_year_month = None

    if last_paid_month:
        parsed_last_paid_month = datetime.strptime(
            last_paid_month,
            "%Y-%m"
        )

        last_paid_year_month = (
            parsed_last_paid_month.year,
            parsed_last_paid_month.month
        )

    migrated_months = 0
    unpaid_months = 0
    offset = 0

    while True:
        period_start = add_months(
            player.enrollment_date,
            offset
        )

        if period_start > today:
            break

        period_end = (
            add_months(
                player.enrollment_date,
                offset + 1
            )
            - timedelta(days=1)
        )

        due_date = period_start + timedelta(days=5)

        period_year_month = (
            period_start.year,
            period_start.month
        )

        was_paid_before_sportflow = (
            last_paid_year_month is not None
            and period_year_month <= last_paid_year_month
        )

        if was_paid_before_sportflow:
            status = "paid"
            settlement_source = "migration"

        else:
            status = (
                "overdue"
                if due_date < today
                else "pending"
            )
            settlement_source = None

        payment = PlayerPayment(
            club_id=player.club_id,
            player_id=player.id,
            payment_type="monthly",
            amount=monthly_fee,
            currency_code=player.club.currency_code,
            status=status,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            settlement_source=settlement_source,
            created_by=user_id
        )

        if add_monthly_payment_if_absent(payment):
            if was_paid_before_sportflow:
                migrated_months += 1
            else:
                unpaid_months += 1

        offset += 1

    return {
        "mode": "import_history",
        "payment_control_start_date": player.payment_control_start_date,
        "migrated_months": migrated_months,
        "unpaid_months": unpaid_months
    }

def sync_club_monthly_payments(
    club,
    user_id,
    as_of=None
):
    """
    Sincroniza las mensualidades de todos los deportistas
    que ya tienen configurado el control de pagos en el club.

    No realiza commit.
    La ruta que invoque esta función controla la transacción.
    """
    as_of = _resolve_as_of(as_of, club)

    players = Player.query.filter(
        Player.club_id == club.id,
        Player.is_active.is_(True),
        Player.payment_control_start_date.isnot(None)
    ).all()

    created_count = 0

    for player in players:

        monthly_fee = get_effective_monthly_fee(player, club)

        monthly_fee = float(monthly_fee or 0)

        if not math.isfinite(monthly_fee) or monthly_fee <= 0:
            continue

        created_count += sync_player_monthly_payments(
            player=player,
            monthly_fee=monthly_fee,
            user_id=user_id,
            as_of=as_of
        )

    return created_count
