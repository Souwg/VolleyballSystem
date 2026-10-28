import os

from flask import jsonify, request, send_file, url_for
from flask_jwt_extended import jwt_required
from itsdangerous import BadSignature, SignatureExpired

from src.api.api_blueprint import api
from src.api.models import db, PaymentReceipt, PaymentReceiptShareEvent
from src.api.receipt_service import (
    RECEIPT_LINK_MAX_AGE,
    PaymentReceiptIssueError,
    PaymentReceiptPdfError,
    ensure_receipt_pdf,
    get_receipt_link_serializer,
    get_receipt_pdf_path,
    issue_payment_receipt,
)
from src.api.utils import error_response, get_current_user


def _get_receipt_sharing_user():
    user = get_current_user()

    if user.role not in ["club_owner", "staff"]:
        return None, error_response(
            "No tienes permisos para compartir recibos",
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


def _get_receipt_for_club(receipt_id, club_id):
    return PaymentReceipt.query.filter_by(
        id=receipt_id,
        club_id=club_id
    ).first()


def _create_receipt_share_event(receipt, user, channel, destination):
    if receipt.status != "issued":
        return None, error_response(
            "El recibo fue invalidado y no puede compartirse nuevamente",
            "RECEIPT_INVALIDATED",
            409
        )

    if channel != "whatsapp":
        return None, error_response(
            "Canal de envío inválido",
            "INVALID_RECEIPT_CHANNEL",
            400
        )

    normalized_destination = (
        str(destination).strip()
        if destination is not None
        else ""
    )

    if not normalized_destination or len(normalized_destination) > 120:
        return None, error_response(
            "El destino de WhatsApp es inválido",
            "INVALID_RECEIPT_DESTINATION",
            400
        )

    try:
        ensure_receipt_pdf(receipt)
    except PaymentReceiptPdfError as error:
        db.session.rollback()
        return None, error_response(
            error.message,
            error.code,
            error.status_code
        )

    share_event = PaymentReceiptShareEvent(
        receipt_id=receipt.id,
        club_id=receipt.club_id,
        channel="whatsapp",
        destination=normalized_destination,
        event_type="share_initiated",
        source="application",
        created_by=user.id
    )

    db.session.add(share_event)
    db.session.commit()

    return share_event, None


@api.route("/payments/<string:payment_id>/receipt", methods=["POST"])
@jwt_required()
def create_payment_receipt(payment_id):
    user = get_current_user()

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para generar recibos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    receipt_serializer = get_receipt_link_serializer()

    try:
        payment, receipt, created = issue_payment_receipt(
            payment_id=payment_id,
            club_id=user.club_id
        )
    except PaymentReceiptIssueError as error:
        db.session.rollback()
        return error_response(
            error.message,
            error.code,
            error.status_code
        )

    return jsonify({
        "message": (
            "Recibo generado correctamente"
            if created
            else "El recibo ya existe"
        ),
        "receipt": {
            **receipt.serialize(),
            "share_url": url_for(
                "api.get_public_payment_receipt",
                token=receipt_serializer.dumps(receipt.id)
            )
        },
        "payment": payment.serialize()
    }), 200


@api.route(
    "/payment-receipts/<string:receipt_id>/repair-pdf",
    methods=["POST"]
)
@jwt_required()
def repair_payment_receipt_pdf(receipt_id):
    user = get_current_user()

    if user.role not in ["club_owner", "staff"]:
        return error_response(
            "No tienes permisos para reparar recibos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    receipt = PaymentReceipt.query.filter_by(
        id=receipt_id,
        club_id=user.club_id
    ).first()

    if not receipt:
        return error_response(
            "Recibo no encontrado",
            "RECEIPT_NOT_FOUND",
            404
        )

    try:
        repaired = ensure_receipt_pdf(receipt)
    except PaymentReceiptPdfError as error:
        db.session.rollback()
        return error_response(
            error.message,
            error.code,
            error.status_code
        )

    return jsonify({
        "message": (
            "PDF del recibo reparado correctamente"
            if repaired
            else "El PDF del recibo ya está disponible"
        ),
        "repaired": repaired,
        "receipt": receipt.serialize()
    }), 200


@api.route("/payment-receipts/public/<string:token>", methods=["GET"])
def get_public_payment_receipt(token):
    try:
        receipt_id = get_receipt_link_serializer().loads(
            token,
            max_age=RECEIPT_LINK_MAX_AGE
        )
    except (SignatureExpired, BadSignature):
        return error_response("Recibo no encontrado", "RECEIPT_NOT_FOUND", 404)

    if not isinstance(receipt_id, str):
        return error_response("Recibo no encontrado", "RECEIPT_NOT_FOUND", 404)

    receipt = PaymentReceipt.query.get(receipt_id)

    if not receipt or receipt.status != "issued":
        return error_response("Recibo no encontrado", "RECEIPT_NOT_FOUND", 404)

    receipt_pdf_path = get_receipt_pdf_path(receipt) if receipt else None

    if not receipt_pdf_path or not os.path.isfile(receipt_pdf_path):
        return error_response("Recibo no encontrado", "RECEIPT_NOT_FOUND", 404)

    try:
        response = send_file(receipt_pdf_path, mimetype="application/pdf")
    except FileNotFoundError:
        return error_response("Recibo no encontrado", "RECEIPT_NOT_FOUND", 404)

    response.cache_control.no_store = True
    return response


@api.route(
    "/payment-receipts/<string:receipt_id>/share-events",
    methods=["POST"]
)
@jwt_required()
def create_payment_receipt_share_event(receipt_id):
    user, user_error = _get_receipt_sharing_user()

    if user_error:
        return user_error

    receipt = _get_receipt_for_club(receipt_id, user.club_id)

    if not receipt:
        return error_response(
            "Recibo no encontrado",
            "RECEIPT_NOT_FOUND",
            404
        )

    body = request.get_json() or {}
    channel = str(body.get("channel") or "").strip().lower()
    destination = body.get("destination")

    share_event, share_error = _create_receipt_share_event(
        receipt,
        user,
        channel,
        destination
    )

    if share_error:
        return share_error

    return jsonify({
        "message": "Acción de compartir registrada",
        "share_event": share_event.serialize()
    }), 201


@api.route(
    "/payment-receipts/<string:receipt_id>/share-events",
    methods=["GET"]
)
@jwt_required()
def get_payment_receipt_share_events(receipt_id):
    user, user_error = _get_receipt_sharing_user()

    if user_error:
        return user_error

    receipt = _get_receipt_for_club(receipt_id, user.club_id)

    if not receipt:
        return error_response(
            "Recibo no encontrado",
            "RECEIPT_NOT_FOUND",
            404
        )

    share_events = PaymentReceiptShareEvent.query.filter_by(
        receipt_id=receipt.id,
        club_id=user.club_id
    ).order_by(
        PaymentReceiptShareEvent.created_at.desc(),
        PaymentReceiptShareEvent.id.desc()
    ).all()

    return jsonify({
        "receipt_id": receipt.id,
        "share_events": [
            share_event.serialize()
            for share_event in share_events
        ]
    }), 200


@api.route("/payment-receipts/<string:receipt_id>/share", methods=["PUT"])
@jwt_required()
def record_legacy_payment_receipt_share_event(receipt_id):
    """Compatibilidad: registra un evento sin modificar campos sent_* legacy."""
    user, user_error = _get_receipt_sharing_user()

    if user_error:
        return user_error

    receipt = _get_receipt_for_club(receipt_id, user.club_id)

    if not receipt:
        return error_response(
            "Recibo no encontrado",
            "RECEIPT_NOT_FOUND",
            404
        )

    body = request.get_json() or {}
    channel = str(body.get("sent_channel") or "").strip().lower()
    destination = body.get("sent_to")

    share_event, share_error = _create_receipt_share_event(
        receipt,
        user,
        channel,
        destination
    )

    if share_error:
        return share_error

    return jsonify({
        "message": "Acción de compartir registrada",
        "share_event": share_event.serialize(),
        "deprecated_endpoint": True
    }), 201
