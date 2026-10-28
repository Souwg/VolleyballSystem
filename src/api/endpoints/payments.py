import math
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import current_app, jsonify, request
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import db, Club, Player, PlayerPayment
from src.api.payment_service import (
    VALID_PAYMENT_METHODS,
    add_months,
    calculate_monthly_sync_preview,
    execute_monthly_sync,
    initialize_player_payment_history,
    serialize_monthly_sync_preview,
    sync_player_monthly_payments,
    validate_manual_payment_settlement,
)
from src.api.receipt_service import get_payment_for_update
from src.api.time_utils import get_club_today
from src.api.utils import error_response, get_current_user


VALID_PAYMENT_STATUSES = ["pending", "paid", "overdue", "cancelled"]
VALID_INITIAL_PAYMENT_MODES = [
    "import_history",
    "start_now"
]
VALID_INITIAL_ENROLLMENT_STATUSES = [
    "pending",
    "paid_before_sportflow",
    "not_applicable"
]
VALID_PAYMENT_TYPES = [
    "enrollment",
    "monthly",
    "uniform",
    "tournament",
    "referee",
    "extra"
]


def _get_payments_user():
    user = get_current_user()

    if user.role not in ["club_owner", "staff"]:
        return None, error_response(
            "No tienes permisos para ver pagos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return None, error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    return user, None


def _serialize_monthly_sync_execution(plan, result):
    return {
        "as_of": plan["as_of"].isoformat(),
        "planned": {
            "payments_to_create": plan["summary"][
                "payments_to_create"
            ],
            "payments_to_mark_overdue": plan["summary"][
                "payments_to_mark_overdue"
            ]
        },
        "applied": {
            "payments_created": result["summary"][
                "payments_created"
            ],
            "payments_marked_overdue": result["summary"][
                "payments_marked_overdue"
            ],
            "payments_not_created": result["summary"][
                "payments_not_created"
            ],
            "overdue_transitions_not_applied": result["summary"][
                "overdue_transitions_not_applied"
            ]
        },
        "skipped": {
            "players_inactive": plan["summary"][
                "players_skipped_inactive"
            ],
            "players_unconfigured": plan["summary"][
                "players_skipped_unconfigured"
            ],
            "players_not_started": plan["summary"][
                "players_skipped_not_started"
            ],
            "players": plan["skipped_players"]
        },
        "warnings": plan["warnings"]
    }


def _run_monthly_sync(club, player=None):
    as_of = get_club_today(club)

    try:
        plan, result = execute_monthly_sync(
            club=club,
            player=player,
            as_of=as_of,
            user_id=None
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "No se pudo completar la sincronización mensual del club %s",
            club.id
        )
        return None, error_response(
            "No pudimos sincronizar los pagos. Intenta nuevamente.",
            "PAYMENT_SYNC_FAILED",
            500
        )

    return _serialize_monthly_sync_execution(plan, result), None


@api.route("/players/<string:player_id>/payment-settings", methods=["PUT"])
@jwt_required()
def update_player_payment_settings(player_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para configurar pagos",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    enrollment_date = body.get("enrollment_date")
    custom_enrollment_fee = body.get("enrollment_fee")
    custom_monthly_fee = body.get("monthly_fee")

    initial_payment_mode = body.get("initial_payment_mode")
    initial_enrollment_status = body.get(
        "initial_enrollment_status"
    )

    last_paid_month = body.get("last_paid_month")

    if last_paid_month == "":
        last_paid_month = None

    # =====================================================
    # 1. FECHA DE INSCRIPCIÓN
    # =====================================================

    if not enrollment_date:
        return error_response(
            "La fecha de inscripción es obligatoria",
            "ENROLLMENT_DATE_REQUIRED",
            400
        )

    try:
        parsed_enrollment_date = datetime.strptime(
            enrollment_date,
            "%Y-%m-%d"
        ).date()

    except (TypeError, ValueError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_ENROLLMENT_DATE_FORMAT",
            400
        )

    payment_cycle_day = parsed_enrollment_date.day
    today = get_club_today(club)

    # =====================================================
    # 2. SABER SI ES CONFIGURACIÓN INICIAL
    # =====================================================

    # Puede existir información creada por la versión anterior
    # del módulo de pagos sin payment_control_start_date.
    #
    # Solo revisamos inscripción y mensualidades:
    # un cargo de torneo, arbitraje o extra NO significa que
    # el cobro mensual ya haya sido configurado.
    existing_base_payment = PlayerPayment.query.filter(
        PlayerPayment.club_id == user.club_id,
        PlayerPayment.player_id == player.id,
        PlayerPayment.payment_type.in_(
            ["enrollment", "monthly"]
        )
    ).first()

    has_legacy_payment_history = (
        player.payment_control_start_date is None
        and existing_base_payment is not None
    )

    if has_legacy_payment_history:
        return error_response(
            (
                "Este deportista tiene un historial de pagos anterior "
                "que debe revisarse antes de iniciar la nueva configuración"
            ),
            "LEGACY_PAYMENT_HISTORY_REQUIRES_REVIEW",
            409
        )

    is_initial_setup = (
        player.payment_control_start_date is None
    )
    # Una vez inicializado el historial, la fecha de inscripción
    # no se cambia silenciosamente porque afectaría los ciclos
    # ya creados.
    if (
        not is_initial_setup
        and player.enrollment_date
        and parsed_enrollment_date != player.enrollment_date
    ):
        return error_response(
            (
                "La fecha de inscripción no puede modificarse "
                "después de iniciar el control de pagos"
            ),
            "ENROLLMENT_DATE_LOCKED",
            409
        )

    # =====================================================
    # 3. VALIDAR ESTADO INICIAL
    # =====================================================

    if is_initial_setup:

        if initial_payment_mode not in VALID_INITIAL_PAYMENT_MODES:
            return error_response(
                "Debes indicar cómo iniciar el historial de mensualidades",
                "INITIAL_PAYMENT_MODE_REQUIRED",
                400
            )

        if (
            initial_enrollment_status
            not in VALID_INITIAL_ENROLLMENT_STATUSES
        ):
            return error_response(
                "Debes indicar el estado inicial de la inscripción",
                "INITIAL_ENROLLMENT_STATUS_REQUIRED",
                400
            )

        # Traer historial solo tiene sentido para una inscripción
        # que ya ocurrió.
        if (
            initial_payment_mode == "import_history"
            and parsed_enrollment_date > today
        ):
            return error_response(
                (
                    "No puedes traer historial de mensualidades "
                    "para una inscripción futura"
                ),
                "INVALID_HISTORY_ENROLLMENT_DATE",
                400
            )

    # =====================================================
    # 4. VALIDAR ÚLTIMO MES PAGADO
    # =====================================================

    if (
        is_initial_setup
        and initial_payment_mode == "import_history"
        and last_paid_month
    ):
        try:
            parsed_last_paid_month = datetime.strptime(
                last_paid_month,
                "%Y-%m"
            )

        except (TypeError, ValueError):
            return error_response(
                "El último mes pagado debe usar el formato YYYY-MM",
                "INVALID_LAST_PAID_MONTH_FORMAT",
                400
            )

        months_difference = (
            (
                parsed_last_paid_month.year
                - parsed_enrollment_date.year
            ) * 12
            + parsed_last_paid_month.month
            - parsed_enrollment_date.month
        )

        if months_difference < 0:
            return error_response(
                (
                    "El último mes pagado no puede ser anterior "
                    "a la inscripción"
                ),
                "LAST_PAID_MONTH_BEFORE_ENROLLMENT",
                400
            )

        selected_cycle = add_months(
            parsed_enrollment_date,
            months_difference
        )

        if selected_cycle > today:
            return error_response(
                (
                    "El último mes pagado corresponde a un ciclo "
                    "que todavía no ha comenzado"
                ),
                "LAST_PAID_MONTH_NOT_REACHED",
                400
            )

    # En start_now no necesitamos historial anterior.
    if initial_payment_mode == "start_now":
        last_paid_month = None

    # =====================================================
    # 5. MONTOS PERSONALIZADOS / MONTOS DEL CLUB
    # =====================================================

    has_custom_enrollment_fee = (
        custom_enrollment_fee is not None
        and custom_enrollment_fee != ""
    )

    has_custom_monthly_fee = (
        custom_monthly_fee is not None
        and custom_monthly_fee != ""
    )

    enrollment_fee = (
        custom_enrollment_fee
        if has_custom_enrollment_fee
        else club.default_enrollment_fee
    )

    monthly_fee = (
        custom_monthly_fee
        if has_custom_monthly_fee
        else club.default_monthly_fee
    )

    try:
        enrollment_fee = float(enrollment_fee or 0)
        monthly_fee = float(monthly_fee or 0)

    except (TypeError, ValueError):
        return error_response(
            "Los montos deben ser numéricos",
            "INVALID_PAYMENT_AMOUNT",
            400
        )

    if not (
        math.isfinite(enrollment_fee)
        and math.isfinite(monthly_fee)
    ):
        return error_response(
            "Los montos deben ser numéricos",
            "INVALID_PAYMENT_AMOUNT",
            400
        )

    if enrollment_fee < 0:
        return error_response(
            "El monto de inscripción no puede ser negativo",
            "INVALID_ENROLLMENT_FEE",
            400
        )

    if monthly_fee <= 0:
        return error_response(
            "Debes configurar una mensualidad válida",
            "INVALID_MONTHLY_FEE",
            400
        )

    # Si la inscripción sí aplica, necesitamos un monto válido.
    if (
        is_initial_setup
        and initial_enrollment_status != "not_applicable"
        and enrollment_fee <= 0
    ):
        return error_response(
            "Debes configurar un monto de inscripción válido",
            "INVALID_ENROLLMENT_FEE",
            400
        )

    # =====================================================
    # 6. GUARDAR CONFIGURACIÓN DEL JUGADOR
    # =====================================================

    player.enrollment_date = parsed_enrollment_date

    player.enrollment_fee = (
        enrollment_fee
        if has_custom_enrollment_fee
        else None
    )

    player.monthly_fee = (
        monthly_fee
        if has_custom_monthly_fee
        else None
    )

    player.payment_cycle_day = payment_cycle_day

    # =====================================================
    # 7. CONFIGURACIÓN INICIAL
    # =====================================================

    if is_initial_setup:

        initialization = initialize_player_payment_history(
            player=player,
            enrollment_fee=enrollment_fee,
            monthly_fee=monthly_fee,
            enrollment_status=initial_enrollment_status,
            initial_payment_mode=initial_payment_mode,
            last_paid_month=last_paid_month,
            user_id=user.id
        )

        db.session.commit()

        return jsonify({
            "message": "Configuración de pagos creada correctamente",
            "player": player.serialize(),
            "initialization": {
                "mode": initialization["mode"],
                "payment_control_start_date": (
                    initialization[
                        "payment_control_start_date"
                    ].isoformat()
                    if initialization[
                        "payment_control_start_date"
                    ]
                    else None
                ),
                "migrated_months": initialization[
                    "migrated_months"
                ],
                "unpaid_months": initialization[
                    "unpaid_months"
                ]
            }
        }), 200

    # =====================================================
    # 8. EDICIÓN POSTERIOR
    # =====================================================

    # La configuración inicial ya no se vuelve a ejecutar.
    # Si la inscripción todavía está pendiente, permitimos
    # actualizar su monto.
    enrollment_payment = PlayerPayment.query.filter_by(
        club_id=user.club_id,
        player_id=player.id,
        payment_type="enrollment"
    ).first()

    if (
        enrollment_payment
        and enrollment_payment.status in ["pending", "overdue"]
        and enrollment_fee > 0
    ):
        enrollment_payment.amount = enrollment_fee

    # Crea cualquier mensualidad que deba existir y aún falte.
    # Las mensualidades históricas existentes NO se destruyen.
    sync_player_monthly_payments(
        player=player,
        monthly_fee=monthly_fee,
        user_id=user.id
    )

    db.session.commit()

    return jsonify({
        "message": "Configuración de pagos actualizada correctamente",
        "player": player.serialize()
    }), 200


@api.route("/payments/sync-preview", methods=["GET"])
@jwt_required()
def preview_payments_sync():
    user, authorization_error = _get_payments_user()

    if authorization_error is not None:
        return authorization_error

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    as_of = get_club_today(club)

    with db.session.no_autoflush:
        preview = calculate_monthly_sync_preview(
            club=club,
            as_of=as_of
        )

    return jsonify(
        serialize_monthly_sync_preview(preview)
    ), 200


@api.route("/payments/sync", methods=["POST"])
@jwt_required()
def sync_payments():
    user, authorization_error = _get_payments_user()

    if authorization_error is not None:
        return authorization_error

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    execution, execution_error = _run_monthly_sync(club)

    if execution_error is not None:
        return execution_error

    return jsonify({
        "message": "Sincronización de pagos completada",
        **execution
    }), 200


@api.route("/payments", methods=["GET"])
@jwt_required()
def get_payments():
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para ver pagos",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    status_filter = request.args.get("status")
    payment_type_filter = request.args.get("payment_type")

    if status_filter and status_filter not in VALID_PAYMENT_STATUSES:
        return error_response(
            "Estado de pago inválido",
            "INVALID_PAYMENT_STATUS",
            400
        )

    if payment_type_filter and payment_type_filter not in VALID_PAYMENT_TYPES:
        return error_response(
            "Tipo de pago inválido",
            "INVALID_PAYMENT_TYPE",
            400
        )

    summary_query = PlayerPayment.query.filter_by(
        club_id=user.club_id
    ).join(Player)

    list_query = PlayerPayment.query.filter_by(
        club_id=user.club_id
    ).join(Player)

    if payment_type_filter:
        list_query = list_query.filter(
            PlayerPayment.payment_type == payment_type_filter
        )

    all_payments = summary_query.all()

    payments = list_query.all()

    # ==================================================
    # ORDEN OPERATIVO DE COBROS
    # ==================================================
    # 1. Atrasados: los más antiguos primero
    # 2. Pendientes: los próximos a vencer primero
    # 3. Pagados: los más recientes primero
    # 4. Cancelados: al final

    def payment_order_key(payment):

        status_priority = {
            "overdue": 0,
            "pending": 1,
            "paid": 2,
            "cancelled": 3
        }

        priority = status_priority.get(
            payment.status,
            4
        )

        # Deudas:
        # queremos primero la fecha de vencimiento
        # más antigua / más próxima.
        if payment.status in ["overdue", "pending"]:

            date_order = (
                payment.due_date.toordinal()
                if payment.due_date
                else datetime.max.date().toordinal()
            )

        # Historial:
        # queremos primero los pagos más recientes.
        else:

            reference_date = (
                payment.payment_date
                or payment.due_date
            )

            date_order = (
                -reference_date.toordinal()
                if reference_date
                else 0
            )

        player_name = ""

        if payment.player:
            player_name = (
                f"{payment.player.first_name or ''} "
                f"{payment.player.last_name or ''}"
            ).strip().lower()

        return (
            priority,
            date_order,
            player_name
        )


    payments.sort(
        key=payment_order_key
    )

    summary = {
        "total": len(all_payments),

        "pending": 0,
        "paid": 0,
        "overdue": 0,
        "cancelled": 0,

        "pending_amount": 0,
        "paid_amount": 0,
        "overdue_amount": 0,
        "cancelled_amount": 0,

        # Pagos realmente registrados dentro de SportFlow.
        "registered_paid": 0,
        "registered_paid_amount": 0,

        # Pagos que ya estaban saldados antes de usar SportFlow.
        "migrated_paid": 0,
        "migrated_paid_amount": 0,

        "expected_amount": 0,
        "total_amount": 0
    }

    for payment in all_payments:
        amount = payment.amount or 0

        # ==================================================
        # ESTADO GENERAL DE LA OBLIGACIÓN
        # ==================================================

        if payment.status in [
            "pending",
            "paid",
            "overdue",
            "cancelled"
        ]:
            summary[payment.status] += 1
            summary[f"{payment.status}_amount"] += amount

        # ==================================================
        # PAGOS SALDADOS
        # ==================================================

        if payment.status == "paid":

            if payment.settlement_source == "migration":
                summary["migrated_paid"] += 1
                summary["migrated_paid_amount"] += amount

            else:
                # manual es el valor normal.
                # También dejamos pasar None defensivamente
                # por si existiera algún pago antiguo.
                summary["registered_paid"] += 1
                summary["registered_paid_amount"] += amount

        # ==================================================
        # DEUDA ACTUAL
        # ==================================================

        if payment.status in ["pending", "overdue"]:
            summary["expected_amount"] += amount

        # Total histórico de obligaciones, incluyendo
        # pagadas antes de SportFlow.
        if payment.status in ["pending", "paid", "overdue"]:
            summary["total_amount"] += amount

    if status_filter:
        payments = [
            payment for payment in payments
            if payment.status == status_filter
        ]

    return jsonify({
        "summary": summary,
        "payments": [payment.serialize() for payment in payments]
    }), 200


@api.route("/payments/<string:payment_id>", methods=["PUT"])
@jwt_required()
def update_payment(payment_id):
    user = get_current_user()

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para actualizar pagos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    payment = get_payment_for_update(payment_id, user.club_id)

    if not payment:
        return error_response(
            "Pago no encontrado",
            "PAYMENT_NOT_FOUND",
            404
        )

    # Los registros migrados representan historia anterior
    # a SportFlow y no se modifican como pagos normales.
    if payment.settlement_source == "migration":
        return error_response(
            "Los pagos anteriores a SportFlow no pueden modificarse como pagos normales",
            "MIGRATED_PAYMENT_LOCKED",
            409
        )

    body = request.get_json() or {}

    status = body.get("status")
    amount = body.get("amount")
    payment_method = body.get("payment_method")
    reference = body.get("reference")
    notes = body.get("notes")
    payment_date = body.get("payment_date")
    due_date = body.get("due_date")
    active_receipt = payment.active_receipt
    as_of = get_club_today(payment.club)
    is_transition_to_paid = (
        status == "paid"
        and payment.status != "paid"
    )

    if status is not None:
        if status not in VALID_PAYMENT_STATUSES:
            return error_response(
                "Estado de pago inválido",
                "INVALID_PAYMENT_STATUS",
                400
            )

    parsed_amount = None

    if amount is not None:
        try:
            parsed_amount = float(amount)
        except (TypeError, ValueError):
            return error_response(
                "Monto inválido",
                "INVALID_PAYMENT_AMOUNT",
                400
            )

        if not math.isfinite(parsed_amount):
            return error_response(
                "Monto inválido",
                "INVALID_PAYMENT_AMOUNT",
                400
            )

        if parsed_amount < 0:
            return error_response(
                "El monto no puede ser negativo",
                "INVALID_PAYMENT_AMOUNT",
                400
            )

    normalized_payment_method = None

    if payment_method is not None:
        normalized_payment_method = (
            str(payment_method).strip() or None
        )

        if (
            normalized_payment_method
            and normalized_payment_method not in VALID_PAYMENT_METHODS
        ):
            return error_response(
                "Método de pago inválido",
                "INVALID_PAYMENT_METHOD",
                400
            )

    normalized_reference = None

    if reference is not None:
        normalized_reference = str(reference).strip() or None

    normalized_notes = None

    if notes is not None:
        normalized_notes = str(notes).strip() or None

    parsed_payment_date = None

    if payment_date is not None and payment_date:
        try:
            parsed_payment_date = datetime.strptime(
                payment_date,
                "%Y-%m-%d"
            ).date()
        except (TypeError, ValueError):
            return error_response(
                "Formato de fecha inválido. Usa YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400
            )

        if parsed_payment_date > as_of:
            return error_response(
                "La fecha de pago no puede estar en el futuro.",
                "INVALID_PAYMENT_DATE",
                400
            )

    parsed_due_date = None

    if due_date is not None and due_date:
        try:
            parsed_due_date = datetime.strptime(
                due_date,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            return error_response(
                "Formato de fecha límite inválido. Usa YYYY-MM-DD",
                "INVALID_DUE_DATE_FORMAT",
                400
            )

    should_validate_paid_details = (
        is_transition_to_paid
        or (
            payment.status == "paid"
            and (
                payment_method is not None
                or payment_date is not None
            )
        )
    )

    if should_validate_paid_details:
        effective_payment_method = (
            normalized_payment_method
            if payment_method is not None
            else payment.payment_method
        )
        effective_payment_date = (
            parsed_payment_date
            if payment_date is not None
            else payment.payment_date
        )
        settlement_error = validate_manual_payment_settlement(
            effective_payment_method,
            effective_payment_date,
            as_of
        )

        if settlement_error:
            message, code = settlement_error
            return error_response(message, code, 400)

    receipt_will_be_invalidated = (
        active_receipt is not None
        and status is not None
        and status != "paid"
    )

    if active_receipt and not receipt_will_be_invalidated:
        protected_data_changed = False

        if amount is not None:
            try:
                current_amount = Decimal(
                    str(payment.amount)
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )
                requested_amount = Decimal(
                    str(amount)
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )
                protected_data_changed = (
                    current_amount != requested_amount
                )
            except (InvalidOperation, TypeError, ValueError):
                protected_data_changed = True

        if (
            payment_method is not None
            and payment.payment_method != normalized_payment_method
        ):
            protected_data_changed = True

        if (
            reference is not None
            and (payment.reference or None) != normalized_reference
        ):
            protected_data_changed = True

        if (
            payment_date is not None
            and payment.payment_date != parsed_payment_date
        ):
            protected_data_changed = True

        if protected_data_changed:
            return error_response(
                (
                    "No puedes modificar los datos de un pago que ya "
                    "tiene un recibo emitido."
                ),
                "PAYMENT_RECEIPT_LOCKED",
                409
            )

    if status is not None:
        payment.status = status

        if is_transition_to_paid:
            payment.paid_by = user.id
            payment.settlement_source = "manual"

        elif status != "paid":
            if active_receipt:
                active_receipt.status = "invalidated"
                active_receipt.invalidated_at = datetime.utcnow()
                active_receipt.invalidated_by = user.id
                active_receipt.invalidation_reason = (
                    "payment_status_changed"
                )

            payment.payment_date = None
            payment.payment_method = None
            payment.reference = None
            payment.settlement_source = None

    if amount is not None:
        payment.amount = parsed_amount

    if payment_method is not None:
        payment.payment_method = normalized_payment_method

    if reference is not None:
        payment.reference = normalized_reference

    if notes is not None:
        payment.notes = normalized_notes

    if payment_date is not None:
        payment.payment_date = parsed_payment_date

    if due_date is not None:
        payment.due_date = parsed_due_date

    db.session.commit()

    return jsonify({
        "message": "Pago actualizado correctamente",
        "payment": payment.serialize()
    }), 200


@api.route(
    "/players/<string:player_id>/payments/sync-preview",
    methods=["GET"]
)
@jwt_required()
def preview_player_payments_sync(player_id):
    user, authorization_error = _get_payments_user()

    if authorization_error is not None:
        return authorization_error

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    as_of = get_club_today(club)

    with db.session.no_autoflush:
        preview = calculate_monthly_sync_preview(
            club=club,
            player=player,
            as_of=as_of
        )

    return jsonify(
        serialize_monthly_sync_preview(preview)
    ), 200


@api.route(
    "/players/<string:player_id>/payments/sync",
    methods=["POST"]
)
@jwt_required()
def sync_player_payments(player_id):
    user, authorization_error = _get_payments_user()

    if authorization_error is not None:
        return authorization_error

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    execution, execution_error = _run_monthly_sync(
        club=club,
        player=player
    )

    if execution_error is not None:
        return execution_error

    return jsonify({
        "message": "Sincronización de pagos completada",
        **execution
    }), 200


@api.route("/players/<string:player_id>/payments", methods=["GET"])
@jwt_required()
def get_player_payments(player_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para ver pagos",
            "FORBIDDEN",
            403
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    payments = PlayerPayment.query.filter_by(
        player_id=player.id,
        club_id=user.club_id
    ).order_by(
        PlayerPayment.due_date.desc().nullslast(),
        PlayerPayment.created_at.desc()
    ).all()

    return jsonify({
        "player": player.serialize(),
        "payments": [payment.serialize() for payment in payments]
    }), 200
