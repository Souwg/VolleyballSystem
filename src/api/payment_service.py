import calendar
from datetime import datetime, timedelta

from src.api.models import db, Player, PlayerPayment


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


def sync_player_monthly_payments(
    player,
    monthly_fee,
    user_id
):
    if (
        not player.enrollment_date
        or not player.payment_control_start_date
        or monthly_fee <= 0
    ):
        return 0

    today = datetime.utcnow().date()

    if player.payment_control_start_date > today:
        return 0

    enrollment_date = player.enrollment_date
    control_start = player.payment_control_start_date

    months_difference = (
        (control_start.year - enrollment_date.year) * 12
        + control_start.month
        - enrollment_date.month
    )

    months_difference = max(months_difference, 0)

    created_count = 0
    offset = months_difference

    while True:
        period_start = add_months(
            enrollment_date,
            offset
        )

        if period_start < control_start:
            offset += 1
            continue

        if period_start > today:
            break

        period_end = (
            add_months(
                enrollment_date,
                offset + 1
            )
            - timedelta(days=1)
        )

        existing_payment = PlayerPayment.query.filter_by(
            club_id=player.club_id,
            player_id=player.id,
            payment_type="monthly",
            period_start=period_start
        ).first()

        if not existing_payment:
            due_date = period_start + timedelta(days=5)

            status = (
                "overdue"
                if due_date < today
                else "pending"
            )

            payment = PlayerPayment(
                club_id=player.club_id,
                player_id=player.id,
                payment_type="monthly",
                amount=monthly_fee,
                status=status,
                period_start=period_start,
                period_end=period_end,
                due_date=due_date,
                created_by=user_id
            )

            db.session.add(payment)
            created_count += 1

        offset += 1

    return created_count

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

    today = datetime.utcnow().date()

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
            migrated_months += 1

        else:
            status = (
                "overdue"
                if due_date < today
                else "pending"
            )
            settlement_source = None
            unpaid_months += 1

        payment = PlayerPayment(
            club_id=player.club_id,
            player_id=player.id,
            payment_type="monthly",
            amount=monthly_fee,
            status=status,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            settlement_source=settlement_source,
            created_by=user_id
        )

        db.session.add(payment)

        offset += 1

    return {
        "mode": "import_history",
        "payment_control_start_date": player.payment_control_start_date,
        "migrated_months": migrated_months,
        "unpaid_months": unpaid_months
    }

def sync_club_monthly_payments(
    club,
    user_id
):
    """
    Sincroniza las mensualidades de todos los deportistas
    que ya tienen configurado el control de pagos en el club.

    No realiza commit.
    La ruta que invoque esta función controla la transacción.
    """

    players = Player.query.filter(
        Player.club_id == club.id,
        Player.payment_control_start_date.isnot(None)
    ).all()

    created_count = 0

    for player in players:

        monthly_fee = (
            player.monthly_fee
            if player.monthly_fee is not None
            else club.default_monthly_fee
        )

        monthly_fee = float(monthly_fee or 0)

        if monthly_fee <= 0:
            continue

        created_count += sync_player_monthly_payments(
            player=player,
            monthly_fee=monthly_fee,
            user_id=user_id
        )

    return created_count