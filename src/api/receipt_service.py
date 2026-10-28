import os
import re
import tempfile
from datetime import datetime
from urllib.parse import urlsplit

from flask import current_app
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from src.api.models import (
    Club,
    db,
    PaymentReceipt,
    PlayerPayment,
    ReceiptCounter,
)
from src.api.currency_registry import format_money
from src.api.payment_service import validate_manual_payment_settlement
from src.api.time_utils import get_club_now, get_club_today


RECEIPT_LINK_MAX_AGE = 7 * 24 * 60 * 60

PAYMENT_TYPE_LABELS = {
    "enrollment": "Inscripción",
    "monthly": "Mensualidad",
    "uniform": "Uniforme",
    "tournament": "Inscripción de torneo",
    "referee": "Arbitraje",
    "extra": "Extra",
}

PAYMENT_METHOD_LABELS = {
    "cash": "Efectivo",
    "transfer": "Transferencia",
    "zelle": "Zelle",
    "mobile_payment": "Pago móvil",
    "other": "Otro",
}

ACTIVE_RECEIPT_CONSTRAINT = "uq_payment_receipts_issued_payment"
RECEIPT_COUNTER_CONSTRAINT = "unique_receipt_counter_per_club_year"
RECEIPT_NUMBER_CONSTRAINTS = {
    "payment_receipts_receipt_number_key",
    "uq_payment_receipts_receipt_number",
}


class PaymentReceiptIssueError(Exception):
    def __init__(self, message, code, status_code):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class PaymentReceiptPdfError(Exception):
    def __init__(self, message, code, status_code):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def classify_receipt_integrity_error(error):
    """Clasifica únicamente constraints conocidas de la emisión."""
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None
    )

    if constraint_name == ACTIVE_RECEIPT_CONSTRAINT:
        return "active_receipt"

    if constraint_name == RECEIPT_COUNTER_CONSTRAINT:
        return "receipt_counter"

    if constraint_name in RECEIPT_NUMBER_CONSTRAINTS:
        return "receipt_number"

    message = str(error.orig).lower()

    if (
        "payment_receipts.payment_id" in message
        and "unique" in message
    ):
        return "active_receipt"

    if (
        "receipt_counters.club_id" in message
        and "receipt_counters.year" in message
        and "unique" in message
    ):
        return "receipt_counter"

    if (
        "payment_receipts.receipt_number" in message
        and "unique" in message
    ):
        return "receipt_number"

    return None


def _begin_sqlite_immediate_transaction():
    """SQLite no soporta FOR UPDATE; serializa su escritura equivalente."""
    connection = db.session.connection()

    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def get_payment_for_update(payment_id, club_id):
    _begin_sqlite_immediate_transaction()

    return (
        PlayerPayment.query
        .filter_by(id=payment_id, club_id=club_id)
        .with_for_update()
        .first()
    )


def _get_receipt_counter_for_update(club_id, year):
    return (
        ReceiptCounter.query
        .filter_by(club_id=club_id, year=year)
        .with_for_update()
        .first()
    )


def get_receipt_link_serializer():
    return URLSafeTimedSerializer(
        current_app.config["JWT_SECRET_KEY"],
        salt="payment-receipt-share-v1"
    )


def get_receipts_folder():
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "../../public/uploads/receipts"
    ))


def get_club_logos_folder():
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "../../public/uploads/clubs"
    ))


def _get_receipt_pdf_location(receipt, require_pdf_url=True):
    receipt_number = str(receipt.receipt_number or "")

    filename = f"{receipt_number}.pdf"
    if not re.fullmatch(r"REC-[A-Za-z0-9-]+\.pdf", filename):
        raise PaymentReceiptPdfError(
            "La ruta del PDF del recibo no es válida.",
            "RECEIPT_PDF_INVALID_PATH",
            409
        )

    pdf_url = f"/uploads/receipts/{filename}"

    if require_pdf_url and receipt.pdf_url != pdf_url:
        raise PaymentReceiptPdfError(
            "La ruta del PDF del recibo no es válida.",
            "RECEIPT_PDF_INVALID_PATH",
            409
        )

    folder = os.path.realpath(get_receipts_folder())
    path = os.path.join(folder, filename)

    if (
        os.path.islink(path)
        or os.path.dirname(os.path.realpath(path)) != folder
    ):
        raise PaymentReceiptPdfError(
            "La ruta del PDF del recibo no es válida.",
            "RECEIPT_PDF_INVALID_PATH",
            409
        )

    return pdf_url, path


def get_receipt_pdf_path(receipt):
    try:
        _, path = _get_receipt_pdf_location(receipt)
    except PaymentReceiptPdfError:
        return None

    return path


def _warn_unsafe_logo(receipt, reason):
    current_app.logger.warning(
        "Logo omitido al generar el recibo %s: %s",
        receipt.id,
        reason
    )


def get_receipt_logo_path(receipt):
    """Resuelve únicamente logos locales dentro de uploads/clubs."""
    logo_reference = str(receipt.logo_url_snapshot or "").strip()

    if not logo_reference:
        return None

    parsed_reference = urlsplit(logo_reference)
    if parsed_reference.scheme or parsed_reference.netloc:
        _warn_unsafe_logo(receipt, "referencia remota no permitida")
        return None

    if "\\" in logo_reference:
        _warn_unsafe_logo(receipt, "separador de ruta no permitido")
        return None

    expected_prefix = "/uploads/clubs/"
    normalized_reference = (
        logo_reference
        if logo_reference.startswith("/")
        else f"/{logo_reference}"
    )

    if not normalized_reference.startswith(expected_prefix):
        _warn_unsafe_logo(receipt, "ruta fuera del directorio permitido")
        return None

    relative_name = normalized_reference[len(expected_prefix):]
    if (
        not relative_name
        or relative_name in {".", ".."}
        or os.path.basename(relative_name) != relative_name
    ):
        _warn_unsafe_logo(receipt, "ruta relativa no válida")
        return None

    allowed_folder = os.path.realpath(get_club_logos_folder())
    candidate = os.path.join(allowed_folder, relative_name)

    if os.path.islink(candidate):
        _warn_unsafe_logo(receipt, "enlace simbólico no permitido")
        return None

    candidate_realpath = os.path.realpath(candidate)

    try:
        is_contained = os.path.commonpath([
            allowed_folder,
            candidate_realpath
        ]) == allowed_folder
    except ValueError:
        is_contained = False

    if not is_contained:
        _warn_unsafe_logo(receipt, "ruta fuera del directorio permitido")
        return None

    if not os.path.isfile(candidate_realpath):
        return None

    return candidate_realpath


def generate_receipt_number(club_id, utc_now=None):
    club = Club.query.get(club_id)

    if not club:
        raise PaymentReceiptIssueError(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    year = get_club_now(club, utc_now=utc_now).year

    counter = _get_receipt_counter_for_update(club_id, year)

    if not counter:
        savepoint = db.session.begin_nested()

        try:
            with savepoint:
                counter = ReceiptCounter(
                    club_id=club_id,
                    year=year,
                    next_sequence=1
                )
                db.session.add(counter)
                db.session.flush()
        except IntegrityError as error:
            if classify_receipt_integrity_error(error) != "receipt_counter":
                raise

            counter = _get_receipt_counter_for_update(club_id, year)

            if counter is None:
                raise

    sequence = counter.next_sequence
    counter.next_sequence += 1

    club_code = club_id.split("-")[0].upper()

    return f"REC-{year}-{club_code}-{str(sequence).zfill(5)}"


def build_payment_receipt_snapshot(payment):
    """Captura una sola vez los datos documentales de un pago."""
    player = payment.player
    club = payment.club

    player_name = None
    if player:
        player_name = " ".join(
            value
            for value in [player.first_name, player.last_name]
            if value
        ) or None

    return {
        "status": "issued",
        "snapshot_source": "issued",
        "amount_snapshot": payment.amount,
        "currency_code_snapshot": payment.currency_code,
        "payment_type_snapshot": payment.payment_type,
        "concept_snapshot": PAYMENT_TYPE_LABELS.get(
            payment.payment_type,
            "Pago"
        ),
        "period_start_snapshot": payment.period_start,
        "period_end_snapshot": payment.period_end,
        "payment_date_snapshot": payment.payment_date,
        "payment_method_snapshot": payment.payment_method,
        "reference_snapshot": payment.reference,
        "player_name_snapshot": player_name,
        "club_name_snapshot": club.name if club else None,
        "club_location_snapshot": (
            (club.city or club.location)
            if club
            else None
        ),
        "club_state_snapshot": (
            (
                club.administrative_area.name
                if club.administrative_area
                else club.state
            )
            if club
            else None
        ),
        "primary_color_snapshot": (
            club.primary_color if club else None
        ),
        "secondary_color_snapshot": (
            club.secondary_color if club else None
        ),
        "logo_url_snapshot": club.image_url if club else None,
    }


def _remove_created_receipt_pdf(file_path):
    if not file_path:
        return

    try:
        if os.path.islink(file_path):
            current_app.logger.error(
                "No se eliminó el PDF compensatorio porque es un symlink"
            )
            return

        if os.path.isfile(file_path):
            os.unlink(file_path)
    except OSError:
        current_app.logger.exception(
            "No se pudo eliminar un PDF tras revertir su emisión"
        )


def write_receipt_pdf_atomic(receipt, allow_replace=False):
    """Genera el PDF en el directorio final y lo publica con os.replace."""
    pdf_url, final_path = _get_receipt_pdf_location(
        receipt,
        require_pdf_url=False
    )
    receipts_folder = os.path.dirname(final_path)
    os.makedirs(receipts_folder, exist_ok=True)

    if os.path.lexists(final_path):
        if os.path.islink(final_path) or not os.path.isfile(final_path):
            raise PaymentReceiptPdfError(
                "La ruta del PDF del recibo no es válida.",
                "RECEIPT_PDF_INVALID_PATH",
                409
            )

        if not allow_replace:
            raise PaymentReceiptPdfError(
                "Ya existe un archivo para este número de recibo.",
                "RECEIPT_PDF_INVALID_PATH",
                409
            )

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".receipt-",
        suffix=".tmp",
        dir=receipts_folder
    )
    os.close(descriptor)

    try:
        _render_payment_receipt_pdf(receipt, temporary_path)

        if not os.path.isfile(temporary_path):
            raise OSError("El generador no creó el archivo temporal")

        with open(temporary_path, "rb") as temporary_file:
            if temporary_file.read(5) != b"%PDF-":
                raise OSError("El archivo temporal no contiene un PDF válido")

        os.chmod(temporary_path, 0o640)

        if os.path.islink(final_path):
            raise PaymentReceiptPdfError(
                "La ruta del PDF del recibo no es válida.",
                "RECEIPT_PDF_INVALID_PATH",
                409
            )

        if not allow_replace and os.path.lexists(final_path):
            raise PaymentReceiptPdfError(
                "Ya existe un archivo para este número de recibo.",
                "RECEIPT_PDF_INVALID_PATH",
                409
            )

        os.replace(temporary_path, final_path)
        temporary_path = None

        return pdf_url, final_path

    except PaymentReceiptPdfError:
        raise
    except Exception as error:
        current_app.logger.exception(
            "No se pudo generar atómicamente el PDF del recibo %s",
            receipt.id
        )
        raise PaymentReceiptPdfError(
            "No se pudo generar el PDF del recibo.",
            "RECEIPT_PDF_GENERATION_FAILED",
            500
        ) from error
    finally:
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.unlink(temporary_path)
            except OSError:
                current_app.logger.exception(
                    "No se pudo limpiar un PDF temporal del recibo %s",
                    receipt.id
                )


def ensure_receipt_pdf(receipt):
    """Restaura desde el snapshot un PDF ausente sin modificar el Receipt."""
    _, final_path = _get_receipt_pdf_location(receipt)

    if os.path.isfile(final_path):
        return False

    if os.path.lexists(final_path):
        raise PaymentReceiptPdfError(
            "La ruta del PDF del recibo no es válida.",
            "RECEIPT_PDF_INVALID_PATH",
            409
        )

    try:
        write_receipt_pdf_atomic(receipt, allow_replace=True)
    except PaymentReceiptPdfError as error:
        if error.code == "RECEIPT_PDF_INVALID_PATH":
            raise

        raise PaymentReceiptPdfError(
            "No se pudo reparar el PDF del recibo.",
            "RECEIPT_PDF_REPAIR_FAILED",
            500
        ) from error

    current_app.logger.info(
        "PDF del recibo %s reconstruido desde snapshot",
        receipt.id
    )
    return True


def issue_payment_receipt(payment_id, club_id, as_of=None):
    """Emite o recupera idempotentemente el recibo vigente de un pago."""
    payment = get_payment_for_update(payment_id, club_id)

    if not payment:
        raise PaymentReceiptIssueError(
            "Pago no encontrado",
            "PAYMENT_NOT_FOUND",
            404
        )

    if payment.status != "paid":
        raise PaymentReceiptIssueError(
            "Solo puedes generar recibos de pagos registrados",
            "PAYMENT_NOT_PAID",
            400
        )

    if payment.settlement_source == "migration":
        raise PaymentReceiptIssueError(
            "Los pagos anteriores a SportFlow no generan recibo",
            "MIGRATED_PAYMENT_RECEIPT_NOT_ALLOWED",
            400
        )

    existing_receipt = PaymentReceipt.query.filter_by(
        payment_id=payment.id,
        status="issued"
    ).first()

    if existing_receipt:
        try:
            ensure_receipt_pdf(existing_receipt)
        except PaymentReceiptPdfError as error:
            raise PaymentReceiptIssueError(
                error.message,
                error.code,
                error.status_code
            ) from error

        db.session.commit()
        return payment, existing_receipt, False

    as_of = as_of or get_club_today(payment.club)
    settlement_error = validate_manual_payment_settlement(
        payment.payment_method,
        payment.payment_date,
        as_of
    )

    if settlement_error:
        message, code = settlement_error
        raise PaymentReceiptIssueError(message, code, 400)

    snapshot = build_payment_receipt_snapshot(payment)
    savepoint = db.session.begin_nested()
    created_pdf_path = None

    try:
        with savepoint:
            receipt = PaymentReceipt(
                payment_id=payment.id,
                club_id=payment.club_id,
                player_id=payment.player_id,
                receipt_number=generate_receipt_number(payment.club_id),
                pdf_url=None,
                **snapshot
            )

            db.session.add(receipt)
            db.session.flush()

            receipt.pdf_url, created_pdf_path = write_receipt_pdf_atomic(
                receipt
            )

    except IntegrityError as error:
        _remove_created_receipt_pdf(created_pdf_path)
        conflict = classify_receipt_integrity_error(error)

        if conflict == "active_receipt":
            existing_receipt = PaymentReceipt.query.filter_by(
                payment_id=payment.id,
                status="issued"
            ).first()

            if existing_receipt is None:
                raise

            try:
                ensure_receipt_pdf(existing_receipt)
            except PaymentReceiptPdfError as pdf_error:
                raise PaymentReceiptIssueError(
                    pdf_error.message,
                    pdf_error.code,
                    pdf_error.status_code
                ) from pdf_error

            db.session.commit()
            return payment, existing_receipt, False

        if conflict == "receipt_number":
            raise PaymentReceiptIssueError(
                "No se pudo asignar un número único al recibo.",
                "RECEIPT_NUMBER_CONFLICT",
                409
            ) from error

        raise
    except PaymentReceiptPdfError as error:
        _remove_created_receipt_pdf(created_pdf_path)
        raise PaymentReceiptIssueError(
            error.message,
            error.code,
            error.status_code
        ) from error
    except Exception:
        _remove_created_receipt_pdf(created_pdf_path)
        raise

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        _remove_created_receipt_pdf(created_pdf_path)
        raise

    return payment, receipt, True


def truncate_pdf_text(c, text, font_name, font_size, max_width):
    if not text:
        return ""

    if c.stringWidth(text, font_name, font_size) <= max_width:
        return text

    ellipsis = "..."

    while text and c.stringWidth(text + ellipsis, font_name, font_size) > max_width:
        text = text[:-1]

    return text.strip() + ellipsis

def wrap_pdf_text(c, text, font_name, font_size, max_width, max_lines=2):
    if not text:
        return [""]

    words = str(text).split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()

        if c.stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)

            current_line = word

            if len(lines) == max_lines - 1:
                break

    if current_line and len(lines) < max_lines:
        remaining_words = words[
            len(" ".join(lines + [current_line]).split()):
        ]

        if remaining_words:
            current_line = f"{current_line} {' '.join(remaining_words)}"

        lines.append(current_line)

    return lines[:max_lines]

def _render_payment_receipt_pdf(receipt, file_path):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    club_name = receipt.club_name_snapshot or "Club"
    club_location = " · ".join(
        value for value in [
            receipt.club_location_snapshot,
            receipt.club_state_snapshot
        ]
        if value
    )

    player_name = receipt.player_name_snapshot or "Deportista"

    primary_color = (
        receipt.primary_color_snapshot
        if receipt.primary_color_snapshot
        else "#1e3a8a"
    )

    dark_color = "#0f172a"
    muted_color = "#64748b"
    light_text = "#94a3b8"
    border_color = "#dbe3ef"
    soft_surface = "#f8fafc"
    accent_color = "#bbcbe1"
    success_color = "#15803d"

    concept = receipt.concept_snapshot or "Pago"
    payment_method = PAYMENT_METHOD_LABELS.get(
        receipt.payment_method_snapshot,
        receipt.payment_method_snapshot or "No registrado"
    )

    payment_date = (
        receipt.payment_date_snapshot.strftime("%d/%m/%Y")
        if receipt.payment_date_snapshot else "No registrada"
    )

    generated_date = (
        receipt.generated_at.strftime("%d/%m/%Y")
        if receipt.generated_at else ""
    )

    amount_text = format_money(
        receipt.amount_snapshot,
        receipt.currency_code_snapshot
    )

    c.setTitle(f"Recibo {receipt.receipt_number}")

    # =========================
    # Background
    # =========================
    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # Thin top bar
    c.setFillColor(colors.HexColor(primary_color))
    c.rect(0, height - 6, width, 6, fill=True, stroke=False)

    # =========================
    # Header
    # =========================
    header_x = 50
    header_y = height - 118

    logo_size = 70
    logo_drawn = False

    logo_path = get_receipt_logo_path(receipt)

    if logo_path:
        try:
            logo = ImageReader(logo_path)

            c.drawImage(
                logo,
                header_x,
                header_y + 2,
                width=logo_size,
                height=logo_size,
                preserveAspectRatio=True,
                mask="auto"
            )

            logo_drawn = True
        except Exception:
            current_app.logger.warning(
                "No se pudo dibujar el logo del recibo %s",
                receipt.id
            )
            logo_drawn = False

    club_text_x = header_x + 92 if logo_drawn else header_x

    # Receipt box
    receipt_box_w = 160
    receipt_box_h = 66
    receipt_box_x = width - 50 - receipt_box_w
    receipt_box_y = header_y + 5

    c.setStrokeColor(colors.HexColor(primary_color))
    c.setLineWidth(1)
    c.roundRect(
        receipt_box_x,
        receipt_box_y,
        receipt_box_w,
        receipt_box_h,
        6,
        fill=False,
        stroke=True
    )

    c.setFillColor(colors.HexColor(primary_color))
    c.rect(
        receipt_box_x,
        receipt_box_y + receipt_box_h - 28,
        receipt_box_w,
        28,
        fill=True,
        stroke=False
    )

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(
        receipt_box_x + receipt_box_w / 2,
        receipt_box_y + receipt_box_h - 18,
        "RECIBO DE PAGO"
    )

    c.setFillColor(colors.HexColor(dark_color))
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(
        receipt_box_x + receipt_box_w / 2,
        receipt_box_y + 19,
        receipt.receipt_number
    )

    # Club name, máximo 2 líneas
    available_club_name_width = receipt_box_x - club_text_x - 35
    club_font_size = 18

    club_lines = wrap_pdf_text(
        c,
        club_name,
        "Helvetica-Bold",
        club_font_size,
        available_club_name_width,
        max_lines=2
    )

    c.setFillColor(colors.HexColor(dark_color))
    c.setFont("Helvetica-Bold", club_font_size)

    club_name_y = header_y + 58

    for index, line in enumerate(club_lines):
        c.drawString(
            club_text_x,
            club_name_y - (index * 20),
            line
        )

    location_y = club_name_y - (len(club_lines) * 20) - 4

    c.setFillColor(colors.HexColor(muted_color))
    c.setFont("Helvetica", 11)
    c.drawString(
        club_text_x,
        location_y,
        club_location or "Club deportivo"
    )

    # Header divider
    c.setStrokeColor(colors.HexColor(border_color))
    c.setLineWidth(1)
    c.line(50, height - 145, width - 50, height - 145)

    # =========================
    # Main title
    # =========================
    title_text = "Comprobante de pago"
    title_y = height - 205

    c.setFillColor(colors.HexColor(dark_color))
    c.setFont("Helvetica-Bold", 28)
    title_width = c.stringWidth(title_text, "Helvetica-Bold", 28)
    c.drawCentredString(width / 2, title_y, title_text)

    c.setStrokeColor(colors.HexColor(accent_color))
    c.setLineWidth(3)
    c.line(
        (width - title_width) / 2,
        title_y - 12,
        (width + title_width) / 2,
        title_y - 12
    )

    c.setFillColor(colors.HexColor(muted_color))
    c.setFont("Helvetica", 11)
    c.drawCentredString(
        width / 2,
        title_y - 42,
        f"Generado el {generated_date}"
    )

    # =========================
    # Amount card
    # =========================
    amount_card_w = 420
    amount_card_h = 88
    amount_card_x = (width - amount_card_w) / 2
    amount_card_y = height - 345

    c.setFillColor(colors.HexColor(soft_surface))
    c.roundRect(
        amount_card_x,
        amount_card_y,
        amount_card_w,
        amount_card_h,
        8,
        fill=True,
        stroke=False
    )

    c.setStrokeColor(colors.HexColor(border_color))
    c.setLineWidth(1)
    c.roundRect(
        amount_card_x,
        amount_card_y,
        amount_card_w,
        amount_card_h,
        8,
        fill=False,
        stroke=True
    )

    c.setFillColor(colors.HexColor(muted_color))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(
        amount_card_x + amount_card_w / 2,
        amount_card_y + 64,
        "MONTO PAGADO"
    )

    c.setFillColor(colors.HexColor(primary_color))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(
        amount_card_x + amount_card_w / 2,
        amount_card_y + 32,
        amount_text
    )

    # =========================
    # Details table
    # =========================
    table_x = 70
    table_y = height - 565
    table_w = width - 140
    row_h = 48
    rows = [
        ("Concepto", concept),
        ("Deportista", player_name),
        ("Fecha de pago", payment_date),
        ("Método de pago", payment_method),
        ("Referencia", receipt.reference_snapshot or "Sin referencia"),
    ]

    table_h = row_h * len(rows)

    c.setFillColor(colors.white)
    c.roundRect(
        table_x,
        table_y,
        table_w,
        table_h,
        8,
        fill=True,
        stroke=False
    )

    c.setStrokeColor(colors.HexColor(border_color))
    c.setLineWidth(1)
    c.roundRect(
        table_x,
        table_y,
        table_w,
        table_h,
        8,
        fill=False,
        stroke=True
    )

    label_w = 215
    value_x = table_x + label_w + 28

    # Vertical separator
    c.setStrokeColor(colors.HexColor(border_color))
    c.line(
        table_x + label_w,
        table_y,
        table_x + label_w,
        table_y + table_h
    )

    current_y = table_y + table_h - row_h

    for index, (label, value) in enumerate(rows):
        if index > 0:
            c.setStrokeColor(colors.HexColor(border_color))
            c.line(
                table_x,
                current_y + row_h,
                table_x + table_w,
                current_y + row_h
            )

        icon_x = table_x + 34
        icon_y = current_y + 24

        c.setFillColor(colors.HexColor("#eef2f7"))
        c.circle(icon_x, icon_y, 13, fill=True, stroke=False)

        c.setFillColor(colors.HexColor(primary_color))
        c.setFont("Helvetica-Bold", 10)

        icon_text = "#"
        if label == "Concepto":
            icon_text = "C"
        elif label == "Deportista":
            icon_text = "D"
        elif label == "Fecha de pago":
            icon_text = "F"
        elif label == "Método de pago":
            icon_text = "M"

        c.drawCentredString(icon_x, icon_y - 4, icon_text)

        c.setFillColor(colors.HexColor(dark_color))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(table_x + 64, current_y + 19, label)

        value_lines = wrap_pdf_text(
            c,
            str(value),
            "Helvetica",
            12,
            table_w - label_w - 48,
            max_lines=2
        )

        c.setFillColor(colors.HexColor(dark_color))
        c.setFont("Helvetica", 12)

        value_start_y = current_y + 24

        if len(value_lines) == 1:
            c.drawString(value_x, current_y + 19, value_lines[0])
        else:
            for line_index, line in enumerate(value_lines):
                c.drawString(
                    value_x,
                    value_start_y - (line_index * 14),
                    line
                )

        current_y -= row_h

    # =========================
    # Confirmation
    # =========================
    confirm_x = 70
    confirm_y = 118
    confirm_w = width - 140
    confirm_h = 58

    c.setFillColor(colors.HexColor("#f8fafc"))
    c.roundRect(
        confirm_x,
        confirm_y,
        confirm_w,
        confirm_h,
        8,
        fill=True,
        stroke=False
    )

    c.setStrokeColor(colors.HexColor(border_color))
    c.roundRect(
        confirm_x,
        confirm_y,
        confirm_w,
        confirm_h,
        8,
        fill=False,
        stroke=True
    )

    c.setFillColor(colors.HexColor(primary_color))
    c.circle(confirm_x + 32, confirm_y + 29, 17, fill=True, stroke=False)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(confirm_x + 32, confirm_y + 22, "✓")

    c.setFillColor(colors.HexColor(dark_color))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(
        confirm_x + 64,
        confirm_y + 33,
        "Pago registrado correctamente"
    )

    c.setFillColor(colors.HexColor(muted_color))
    c.setFont("Helvetica", 10)
    c.drawString(
        confirm_x + 64,
        confirm_y + 17,
        "Este documento confirma que el pago fue registrado correctamente."
    )

    # =========================
    # Footer
    # =========================
    c.setStrokeColor(colors.HexColor(border_color))
    c.line(50, 78, width - 50, 78)

    c.setFillColor(colors.HexColor(primary_color))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2 - 22, 50, "SportFlow")

    c.setFillColor(colors.HexColor(muted_color))
    c.setFont("Helvetica", 9)
    c.drawCentredString(
        width / 2,
        34,
        "Generado automáticamente por SportFlow"
    )

    c.save()


def generate_payment_receipt_pdf(receipt):
    """Compatibilidad: genera y publica el PDF de forma atómica."""
    pdf_url, _ = write_receipt_pdf_atomic(receipt)
    return pdf_url

