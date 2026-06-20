"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
import re
import uuid
import calendar
import secrets
import hashlib
from src.api.email_service import send_password_reset_email
from datetime import datetime, timedelta
from flask import (
    Flask,
    request,
    jsonify,
    url_for,
    Blueprint,
    current_app
)
from werkzeug.utils import secure_filename
from sqlalchemy import func
from src.api.models import (
    db,
    User,
    Club,
    Category,
    Player,
    Team,
    TeamPlayer,
    Attendance,
    TrainingSession,
    TrainingPlayer,
    TokenBlockedList,
    MatchSession,
    MatchPlayer,
    MatchSubstitution,
    MatchEvent,
    PlayerPayment,
    ReceiptCounter,
    PaymentReceipt,
    PlayerMatchStat,
    RefreshToken,
    PasswordResetToken
)
from src.api.stats_validator import validate_match_stats
from flask_cors import CORS
from src.api.extensions import bcrypt
from src.api.utils import (
    generate_sitemap,
    APIException,
    get_current_user,
    error_response,
    generate_temp_password
)
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token
)

api = Blueprint('api', __name__)


CORS(api)

VALID_MATCH_STATUSES = ["present", "late", "absent", "injured"]
PLAYABLE_MATCH_STATUSES = ["present", "late"]
VALID_MATCH_STEPS = [0, 1, 2, 3, 4]
VALID_MATCH_TYPES = ["official", "friendly", "scrimmage"]
ALLOWED_POSITIONS = ["setter", "outside", "middle", "opposite", "libero"]
VALID_PAYMENT_STATUSES = ["pending", "paid", "overdue", "cancelled"]
VALID_PAYMENT_METHODS = ["cash", "transfer", "zelle", "mobile_payment", "other"]
VALID_PAYMENT_TYPES = ["enrollment", "monthly", "uniform", "tournament", "extra"]

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_CLUB_IMAGE_SIZE = 2 * 1024 * 1024  
MAX_PLAYER_IMAGE_SIZE = 8 * 1024 * 1024  


def allowed_image_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )

def sync_match_roster_if_open(match):
    """
    Sincroniza jugadoras nuevas del equipo al partido SOLO si el partido
    todavía no tiene convocatoria guardada.

    No elimina jugadoras viejas del snapshot.
    Solo agrega las que faltan.
    """

    if not match:
        return 0

    # Si ya avanzó de convocatoria, no tocamos el snapshot
    if match.match_step != 0:
        return 0

    if match.is_completed:
        return 0

    existing_player_ids = {
        row.player_id
        for row in MatchPlayer.query.filter_by(match_id=match.id).all()
    }

    current_roster = TeamPlayer.query.filter_by(
        team_id=match.team_id
    ).all()

    added_count = 0

    for member in current_roster:
        if member.player_id in existing_player_ids:
            continue

        snapshot = MatchPlayer(
            match_id=match.id,
            player_id=member.player_id,
            player_number=member.player_number,
            is_called=False,
            attendance_status=None,
            did_play=False
        )

        db.session.add(snapshot)
        added_count += 1

    if added_count > 0:
        db.session.commit()

    return added_count

def recalculate_player_match_stats(match_player_id):
    row = MatchPlayer.query.get(match_player_id)

    if not row:
        return

    stat = PlayerMatchStat.query.filter_by(
        match_player_id=match_player_id
    ).first()

    if not stat:
        stat = PlayerMatchStat(match_player_id=match_player_id)
        db.session.add(stat)


    events = MatchEvent.query.filter_by(
        match_player_id=match_player_id
    ).all()

    # Reset stats
    stat.attacks_total = 0
    stat.attacks_positive = 0
    stat.attacks_neutral = 0
    stat.attacks_errors = 0

    stat.receptions_total = 0
    stat.receptions_positive = 0
    stat.receptions_neutral = 0
    stat.receptions_negative = 0

    stat.defenses_total = 0
    stat.defenses_positive = 0
    stat.defenses_neutral = 0
    stat.defenses_negative = 0

    stat.sets_total = 0
    stat.sets_positive = 0
    stat.sets_neutral = 0
    stat.sets_errors = 0

    stat.serves_total = 0
    stat.serves_in = 0
    stat.serves_aces = 0
    stat.serves_errors = 0

    stat.blocks_total = 0
    stat.blocks_points = 0
    stat.blocks_neutral = 0
    stat.blocks_errors = 0


    for event in events:
        action = event.action_type
        result = event.result

        if action == "attack":
            stat.attacks_total += 1

            if result == "positive":
                stat.attacks_positive += 1
            elif result == "neutral":
                stat.attacks_neutral += 1
            elif result == "error":
                stat.attacks_errors += 1

        elif action == "reception":
            stat.receptions_total += 1

            if result == "positive":
                stat.receptions_positive += 1
            elif result == "neutral":
                stat.receptions_neutral += 1
            elif result == "negative":
                stat.receptions_negative += 1

        elif action == "defense":
            stat.defenses_total += 1

            if result == "positive":
                stat.defenses_positive += 1
            elif result == "neutral":
                stat.defenses_neutral += 1
            elif result == "negative":
                stat.defenses_negative += 1

        elif action == "set":
            stat.sets_total += 1

            if result == "positive":
                stat.sets_positive += 1
            elif result == "neutral":
                stat.sets_neutral += 1
            elif result == "error":
                stat.sets_errors += 1

        elif action == "serve":
            stat.serves_total += 1

            if result == "ace":
                stat.serves_aces += 1
            elif result == "in":
                stat.serves_in += 1
            elif result == "error":
                stat.serves_errors += 1

        elif action == "block":
            stat.blocks_total += 1

            if result == "point":
                stat.blocks_points += 1
            elif result == "neutral":
                stat.blocks_neutral += 1
            elif result == "error":
                stat.blocks_errors += 1

def add_months(source_date, months=1):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1

    day = min(
        source_date.day,
        calendar.monthrange(year, month)[1]
    )

    return source_date.replace(year=year, month=month, day=day)

def generate_receipt_number(club_id):
    year = datetime.utcnow().year

    counter = ReceiptCounter.query.filter_by(
        club_id=club_id,
        year=year
    ).with_for_update().first()

    if not counter:
        counter = ReceiptCounter(
            club_id=club_id,
            year=year,
            next_sequence=1
        )
        db.session.add(counter)
        db.session.flush()

    sequence = counter.next_sequence
    counter.next_sequence += 1

    club_code = club_id.split("-")[0].upper()

    return f"REC-{year}-{club_code}-{str(sequence).zfill(5)}"

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

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

def generate_payment_receipt_pdf(receipt, payment):
    receipts_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../public/uploads/receipts"
        )
    )

    os.makedirs(receipts_folder, exist_ok=True)

    filename = f"{receipt.receipt_number}.pdf"
    file_path = os.path.join(receipts_folder, filename)

    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    club = payment.club
    player = payment.player

    club_name = club.name if club else "Club"
    club_location = " · ".join(
        value for value in [
            club.location if club else None,
            club.state if club else None
        ]
        if value
    )

    player_name = (
        f"{player.first_name} {player.last_name}"
        if player else "Deportista"
    )

    primary_color = (
        club.primary_color
        if club and club.primary_color
        else "#1e3a8a"
    )

    dark_color = "#0f172a"
    muted_color = "#64748b"
    light_text = "#94a3b8"
    border_color = "#dbe3ef"
    soft_surface = "#f8fafc"
    accent_color = "#bbcbe1"
    success_color = "#15803d"

    payment_type_labels = {
        "enrollment": "Inscripción",
        "monthly": "Mensualidad",
        "uniform": "Uniforme",
        "tournament": "Torneo",
        "extra": "Extra",
    }

    payment_method_labels = {
        "cash": "Efectivo",
        "transfer": "Transferencia",
        "zelle": "Zelle",
        "mobile_payment": "Pago móvil",
        "other": "Otro",
    }

    concept = payment_type_labels.get(payment.payment_type, "Pago")
    payment_method = payment_method_labels.get(
        payment.payment_method,
        payment.payment_method or "No registrado"
    )

    payment_date = (
        payment.payment_date.strftime("%d/%m/%Y")
        if payment.payment_date else "No registrada"
    )

    generated_date = (
        receipt.generated_at.strftime("%d/%m/%Y")
        if receipt.generated_at else ""
    )

    amount_text = f"${payment.amount:,.2f}"

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

    if club and club.image_url:
        try:
            image_relative_path = club.image_url.lstrip("/")
            image_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "../../public",
                    image_relative_path
                )
            )

            if os.path.exists(image_path):
                logo = ImageReader(image_path)

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
        ("Referencia", payment.reference or "Sin referencia"),
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

    return f"/uploads/receipts/{filename}"

def hash_reset_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

######################### SYSTEM ###############################

@api.route('/hello', methods=['POST', 'GET'])
def handle_hello():

    response_body = {
        "message": "Hello Sousan! I'm a message that came from the backend, check the network tab on the google inspector and you will see the GET requestttttt"
    }

    return jsonify(response_body), 200

############################# AUTHENTICATION ##################################

@api.route('/login', methods=['POST'])
def login():
    body = request.get_json() or {}

    email = body.get("email")
    password = body.get("password")

    if email:
        email = str(email).strip().lower()

    if password:
        password = str(password)

    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error_response(
            "Email inválido",
            "INVALID_EMAIL",
            400
        )

    if not password:
        return error_response(
            "Contraseña es obligatoria",
            "PASSWORD_REQUIRED",
            400
        )

    user = User.query.filter_by(email=email).first()

    if not user:
        return error_response(
            "Email o contraseña incorrectos",
            "INVALID_CREDENTIALS",
            401
        )

    if not user.is_active:
        return error_response(
            "Tu cuenta está desactivada. Contacta al administrador.",
            "ACCOUNT_DISABLED",
            403
        )

    if not bcrypt.check_password_hash(user.password, password):
        return error_response(
            "Email o contraseña incorrectos",
            "INVALID_CREDENTIALS",
            401
        )

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    decoded_refresh = decode_token(refresh_token)
    refresh_jti = decoded_refresh["jti"]

    refresh_entry = RefreshToken(
        user_id=user.id,
        jti=refresh_jti,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(refresh_entry)
    db.session.commit()

    return jsonify({
        "message": "Login exitoso",
        "token": access_token,
        "refresh": refresh_token,
        "first_login": user.first_login,
        "user": user.serialize()
    }), 200

@api.route("/auth/forgot-password", methods=["POST"])
def forgot_password():
    body = request.get_json() or {}

    email = body.get("email")

    if email:
        email = str(email).strip().lower()

    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error_response(
            "Email inválido",
            "INVALID_EMAIL",
            400
        )

    user = User.query.filter_by(email=email).first()

    generic_response = {
        "message": (
            "Si el email existe, enviaremos instrucciones "
            "para recuperar el acceso."
        )
    }

    if not user or not user.is_active:
        return jsonify(generic_response), 200

    PasswordResetToken.query.filter_by(
        user_id=user.id,
        used_at=None
    ).update({
        "used_at": datetime.utcnow()
    })

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )

    db.session.add(reset_token)
    db.session.commit()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_url}/reset-password?token={raw_token}"

    try:
        send_password_reset_email(
            recipient_email=user.email,
            recipient_name=user.full_name,
            reset_url=reset_url
        )

    except Exception as error:
        db.session.delete(reset_token)
        db.session.commit()

        current_app.logger.exception(
            "No se pudo enviar el correo de recuperación",
            exc_info=error
        )

        return error_response(
            "No pudimos enviar el correo de recuperación",
            "PASSWORD_RESET_EMAIL_FAILED",
            500
        )

    return jsonify(generic_response), 200

@api.route("/auth/reset-password", methods=["POST"])
def reset_password():
    body = request.get_json() or {}

    token = body.get("token")
    new_password = body.get("new_password")

    if not token:
        return error_response(
            "Token requerido",
            "RESET_TOKEN_REQUIRED",
            400
        )

    if not new_password:
        return error_response(
            "Nueva contraseña requerida",
            "PASSWORD_REQUIRED",
            400
        )

    if len(str(new_password)) < 8:
        return error_response(
            "Debe tener al menos 8 caracteres",
            "PASSWORD_TOO_SHORT",
            400
        )

    token_hash = hash_reset_token(str(token))

    reset_token = PasswordResetToken.query.filter_by(
        token_hash=token_hash,
        used_at=None
    ).first()

    if not reset_token:
        return error_response(
            "El enlace no es válido o ya fue usado",
            "RESET_TOKEN_INVALID",
            400
        )

    if reset_token.expires_at < datetime.utcnow():
        return error_response(
            "El enlace expiró. Solicita uno nuevo.",
            "RESET_TOKEN_EXPIRED",
            400
        )

    user = User.query.get(reset_token.user_id)

    if not user or not user.is_active:
        return error_response(
            "El usuario no está disponible",
            "USER_NOT_FOUND",
            404
        )

    user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.first_login = False

    reset_token.used_at = datetime.utcnow()

    RefreshToken.query.filter_by(
        user_id=user.id,
        revoked=False
    ).update({
        "revoked": True
    })

    db.session.commit()

    return jsonify({
        "message": "Contraseña actualizada correctamente"
    }), 200

@api.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():

    jwt_data = get_jwt()
    user_id = get_jwt_identity()
    jti = jwt_data["jti"]

    stored_token = RefreshToken.query.filter_by(jti=jti).first()

    
    if not stored_token:
        return error_response(
            "La sesión ya no es válida. Inicia sesión nuevamente",
            "REFRESH_NOT_FOUND",
            401
        )

    if stored_token.revoked:
        return error_response(
            "La sesión fue cerrada previamente",
            "REFRESH_REVOKED",
            401
        )

   
    stored_token.revoked = True

  
    new_access = create_access_token(identity=user_id)
    new_refresh = create_refresh_token(identity=user_id)

    decoded_new = decode_token(new_refresh)

    new_entry = RefreshToken(
        user_id=user_id,
        jti=decoded_new["jti"],
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({
        "token": new_access,
        "refresh": new_refresh
    }), 200

@api.route('/auth/set-password', methods=['POST'])
@jwt_required()
def set_password():

    user = get_current_user()

    body = request.get_json() or {}

    new_password = body.get("new_password")

    if not new_password:
        return error_response(
            "Nueva contraseña requerida",
            "PASSWORD_REQUIRED",
            400
        )

    if len(new_password) < 8:
        return error_response(
            "Debe tener al menos 8 caracteres",
            "PASSWORD_TOO_SHORT",
            400
        )

    user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.first_login = False  

    db.session.commit()

    return jsonify({
        "message": "Contraseña actualizada correctamente"
    }), 200

@api.route("/logout", methods=["POST"])
@jwt_required()
def logout():

    jwt_data = get_jwt()
    jti = jwt_data["jti"]

    blocked_token = TokenBlockedList(jti=jti)
    db.session.add(blocked_token)

    user = get_current_user()

    RefreshToken.query.filter_by(user_id=user.id, revoked=False).update({
        "revoked": True
    })

    db.session.commit()

    return jsonify({"message": "Logout exitoso"}), 200


######################################### ADMIN ############################################################
@api.route('/admin/create-client', methods=['POST'])
@jwt_required()
def create_client():

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para crear clientes",
            "FORBIDDEN",
            403
        )
    
    body = request.get_json() or {}

    full_name = body.get("full_name")
    email = body.get("email")
    club_name = body.get("club_name")
    club_state = body.get("state")

    if full_name:
        full_name = " ".join(str(full_name).strip().split())

    if email:
        email = email.strip().lower()

    if club_name:
        club_name = " ".join(str(club_name).strip().split())

    if club_state:
        club_state = " ".join(str(club_state).strip().split())

    if not full_name or not str(full_name).strip():
        return error_response(
            "Nombre completo es obligatorio",
            "FULL_NAME_REQUIRED",
            400
        )
    
    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error_response(
            "Email inválido",
            "INVALID_EMAIL",
            400
        )
    
    if not club_name or not str(club_name).strip():
        return error_response(
            "Nombre del club es obligatorio",
            "CLUB_NAME_REQUIRED",
            400
        )
    
    if not club_state or not str(club_state).strip():
        return error_response(
            "El estado es obligatorio",
            "STATE_REQUIRED",
            400
        )
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return error_response(
            "Ya existe un cliente con ese email",
            "CLIENT_ALREADY_EXISTS",
            409
        )


    temp_password = generate_temp_password(10)
    hashed_password = bcrypt.generate_password_hash(temp_password).decode("utf-8")

    new_user = User(
        full_name=full_name.strip(),
        email=email,
        password=hashed_password,
        first_login=True,
        role="club_owner"
    )

    db.session.add(new_user)
    db.session.flush()

    club = Club(
        name=club_name.strip(),
        location=None,
        state=club_state.strip(),
        owner_id=new_user.id
    )

    db.session.add(club)
    db.session.flush()

    new_user.club_id = club.id

    db.session.commit()

    return jsonify({
    "message": "Cliente creado exitosamente",
    "credentials": {
        "email": email,
        "temporary_password": temp_password
    },
    "user": new_user.serialize()
}), 201

@api.route('/admin/clients', methods=['GET'])
@jwt_required()
def list_clients():

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para acceder a esta información",
            "FORBIDDEN",
            403
        )

    clients = User.query.filter_by(role="club_owner") \
        .order_by(User.created_at.desc()) \
        .all()

    return jsonify({
        "total": len(clients),
        "clients": [c.serialize() for c in clients]
    }), 200

@api.route('/admin/clients/<string:user_id>/deactivate', methods=['PUT'])
@jwt_required()
def deactivate_client(user_id):

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para gestionar clientes",
            "FORBIDDEN",
            403
        )

    client = User.query.get(user_id)

    if not client:
        return error_response(
            "El cliente solicitado no existe",
            "CLIENT_NOT_FOUND",
            404
        )

    if client.role != "club_owner":
        return error_response(
            "Solo los clientes pueden ser desactivados",
            "INVALID_CLIENT",
            400
        )

    client.is_active = False
    db.session.commit()

    return jsonify({
        "message": "Cliente desactivado correctamente",
        "client": client.serialize()
    }), 200

@api.route('/admin/clients/<string:user_id>/activate', methods=['PUT'])
@jwt_required()
def activate_client(user_id):

    user = get_current_user()

    if user.role != "system_admin":
        return error_response(
            "No tienes permisos para gestionar clientes",
            "FORBIDDEN",
            403
        )

    client = User.query.get(user_id)

    if not client:
        return error_response(
            "El cliente solicitado no existe",
            "CLIENT_NOT_FOUND",
            404
        )

    if client.role != "club_owner":
        return error_response(
            "Solo los clientes pueden ser reactivados",
            "INVALID_CLIENT",
            400
        )

    client.is_active = True
    db.session.commit()

    return jsonify({
        "message": "Cliente reactivado correctamente",
        "client": client.serialize()
    }), 200

################################### CLUB #############################################

@api.route("/club/users", methods=["POST"])
@jwt_required()
def create_club_user():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear usuarios",
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

    body = request.get_json() or {}

    full_name = body.get("full_name")
    email = body.get("email")

    if email:
        email = email.strip().lower()
    role = body.get("role")

    if not full_name:
        return error_response(
            "Nombre completo requerido",
            "FULL_NAME_REQUIRED",
            400
        )

    if not email:
        return error_response(
            "Email requerido",
            "EMAIL_REQUIRED",
            400
        )

    if role not in ["coach", "staff"]:
        return error_response(
            "Rol inválido",
            "INVALID_ROLE",
            400
        )

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return error_response(
            "Ya existe un usuario con ese email",
            "EMAIL_ALREADY_EXISTS",
            409
        )

    temp_password = generate_temp_password()

    hashed_password = bcrypt.generate_password_hash(temp_password).decode("utf-8")

    new_user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        role=role,
        first_login=True,
        club_id=club.id
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "Usuario del club creado",
        "temporary_password": temp_password,
        "user": new_user.serialize()
    }), 201

@api.route("/club/upload-image", methods=["POST"])
@jwt_required()
def upload_club_image():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede actualizar la imagen",
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

    if "image" not in request.files:
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    image = request.files["image"]

    if image.filename == "":
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    if not allowed_image_file(image.filename):
        return error_response(
            "Formato inválido. Usa PNG, JPG o WEBP",
            "INVALID_IMAGE_FORMAT",
            400
        )

    image.seek(0, os.SEEK_END)
    image_size = image.tell()
    image.seek(0)

    if image_size > MAX_CLUB_IMAGE_SIZE:
        return error_response(
            "La imagen no puede pesar más de 2MB",
            "IMAGE_TOO_LARGE",
            400
        )
    
    original_filename = secure_filename(image.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    filename = f"{club.id}-{uuid.uuid4().hex}.{extension}"

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../public/uploads/clubs"
        )
    )

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)
    image.save(file_path)

    image_url = f"/uploads/clubs/{filename}"

    return jsonify({
        "image_url": image_url
    }), 201

@api.route("/club", methods=["PUT"])
@jwt_required()
def update_club():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede actualizar la información",
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

    body = request.get_json() or {}

    name = body.get("name")
    location = body.get("location")
    state = body.get("state")
    image_url = body.get("image_url")
    primary_color = body.get("primary_color")
    secondary_color = body.get("secondary_color")
    default_enrollment_fee = body.get("default_enrollment_fee")
    default_monthly_fee = body.get("default_monthly_fee")

    if name is not None:
        name = str(name).strip()

        if not name:
            return error_response(
                "El nombre del club es obligatorio",
                "CLUB_NAME_REQUIRED",
                400
            )

        club.name = name

    if state is not None:
        state = str(state).strip()

        if not state:
            return error_response(
                "El estado es obligatorio",
                "STATE_REQUIRED",
                400
            )

        club.state = state

    if location is not None:
        location = str(location).strip()

        if not location:
            return error_response(
                "La ubicación es obligatoria",
                "LOCATION_REQUIRED",
                400
            )

        club.location = location

    if image_url is not None:
        image_url = str(image_url).strip()

        club.image_url = image_url or None

    if primary_color is not None:
        primary_color = str(primary_color).strip()
        club.primary_color = primary_color or None

    if secondary_color is not None:
        secondary_color = str(secondary_color).strip()
        club.secondary_color = secondary_color or None

    # ✅ MONTO DE INSCRIPCIÓN POR DEFECTO
    if default_enrollment_fee is not None:
        try:
            default_enrollment_fee = float(default_enrollment_fee or 0)
        except (TypeError, ValueError):
            return error_response(
                "El monto de inscripción debe ser numérico",
                "INVALID_DEFAULT_ENROLLMENT_FEE",
                400
            )

        if default_enrollment_fee < 0:
            return error_response(
                "El monto de inscripción no puede ser negativo",
                "INVALID_DEFAULT_ENROLLMENT_FEE",
                400
            )

        club.default_enrollment_fee = default_enrollment_fee


    if default_monthly_fee is not None:
        try:
            default_monthly_fee = float(default_monthly_fee or 0)
        except (TypeError, ValueError):
            return error_response(
                "El monto de mensualidad debe ser numérico",
                "INVALID_DEFAULT_MONTHLY_FEE",
                400
            )

        if default_monthly_fee < 0:
            return error_response(
                "El monto de mensualidad no puede ser negativo",
                "INVALID_DEFAULT_MONTHLY_FEE",
                400
            )

        club.default_monthly_fee = default_monthly_fee

    db.session.commit()

    return jsonify({
        "message": "Información del club actualizada",
        "club": club.serialize()
    }), 200

@api.route("/club/dashboard", methods=["GET"])
@jwt_required()
def club_dashboard():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver el dashboard",
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
    
    total_categories = Category.query.filter_by(club_id=club.id).count()

    total_teams = Team.query.filter_by(club_id=club.id).count()

    total_players = Player.query.filter_by(
        club_id=club.id
    ).count()

    active_players = Player.query.filter_by(
        club_id=club.id,
        is_active=True
    ).count()

    injured_players = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id,
        TeamPlayer.status == "injured"
    ).count()

    inactive_players = Player.query.filter_by(
        club_id=club.id,
        is_active=False
    ).count()

    total_trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    today = datetime.utcnow().date()

    
    next_match = MatchSession.query.join(Team).filter(
        Team.club_id == club.id,
        MatchSession.is_completed == False,
        MatchSession.date >= today
    ).order_by(MatchSession.date.asc()).first()

   
    if not next_match:
        next_match = MatchSession.query.join(Team).filter(
            Team.club_id == club.id,
            MatchSession.is_completed == False,
            MatchSession.date < today
        ).order_by(MatchSession.date.desc()).first()

    return jsonify({
        "club": club.serialize(),
        "stats": {
            "total_categories": total_categories,
            "total_teams": total_teams,
            "total_players": total_players,
            "active_players": active_players,
            "injured_players": injured_players,
            "inactive_players": inactive_players,
            "total_trainings": total_trainings
        },
        "next_match": {
            **next_match.serialize(),
            "team_name": next_match.team.name
        } if next_match else None
    }), 200

@api.route("/teams/<string:team_id>/players/<string:player_id>", methods=["DELETE"])
@jwt_required()
def remove_player_from_team(team_id, player_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response("No tienes permisos", "FORBIDDEN", 403)

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response("Equipo no encontrado", "TEAM_NOT_FOUND", 404)

    membership = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_id=player_id
    ).first()

    if not membership:
        return error_response(
            "El jugador no pertenece a este equipo",
            "PLAYER_MEMBERSHIP_NOT_FOUND",
            404
        )

    db.session.delete(membership)
    db.session.commit()

    return jsonify({
        "message": "Jugador removido del equipo"
    }), 200

############################################## CATEGORIES #############################################

@api.route("/categories", methods=["POST"])
@jwt_required()
def create_category():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear categorías",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    body = request.get_json() or {}

    name = body.get("name")
    description = body.get("description")

    if name:
        name = " ".join(name.strip().split())

    if description:
        description = " ".join(description.strip().split())

    if not name:
        return error_response(
            "Nombre de la categoría requerido",
            "CATEGORY_NAME_REQUIRED",
            400
        )

    existing_category = Category.query.filter(
        Category.club_id == user.club_id,
        func.lower(Category.name) == name.lower()
    ).first()

    if existing_category:
        return error_response(
            "Ya existe una categoría con ese nombre",
            "CATEGORY_ALREADY_EXISTS",
            409
        )

    category = Category(
        name=name,
        description=description or None,
        club_id=user.club_id
    )

    db.session.add(category)
    db.session.commit()

    return jsonify({
        "message": "Categoría creada correctamente",
        "category": category.serialize()
    }), 201


@api.route("/categories", methods=["GET"])
@jwt_required()
def get_categories():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    categories = Category.query.filter_by(
        club_id=user.club_id
    ).order_by(Category.name).all()

    result = []

    for category in categories:
        teams = Team.query.filter_by(
            category_id=category.id,
            club_id=user.club_id
        ).all()

        team_ids = [team.id for team in teams]

        total_players = 0

        if team_ids:
            total_players = TeamPlayer.query.filter(
                TeamPlayer.team_id.in_(team_ids)
            ).count()

        result.append({
            **category.serialize(),
            "total_teams": len(teams),
            "total_players": total_players
        })

    return jsonify({
        "categories": result
    }), 200


@api.route("/categories/<string:category_id>", methods=["GET"])
@jwt_required()
def get_category_detail(category_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    teams = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id
    ).order_by(Team.name).all()

    serialized_teams = []

    for team in teams:
        total_players = TeamPlayer.query.filter_by(team_id=team.id).count()

        serialized_teams.append({
            **team.serialize(),
            "total_players": total_players
        })

    return jsonify({
        "category": category.serialize(),
        "total_teams": len(serialized_teams),
        "teams": serialized_teams
    }), 200

@api.route("/categories/<string:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede editar categorías",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes permisos para editar esta categoría",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    name = body.get("name")
    description = body.get("description")

    if name:
        name = " ".join(str(name).strip().split())

    if description is not None:
        description = " ".join(str(description).strip().split())

    if not name:
        return error_response(
            "Nombre de la categoría requerido",
            "CATEGORY_NAME_REQUIRED",
            400
        )

    existing_category = Category.query.filter(
        Category.club_id == user.club_id,
        func.lower(Category.name) == name.lower(),
        Category.id != category.id
    ).first()

    if existing_category:
        return error_response(
            "Ya existe una categoría con ese nombre",
            "CATEGORY_ALREADY_EXISTS",
            409
        )

    category.name = name
    category.description = description or None

    db.session.commit()

    return jsonify({
        "message": "Categoría actualizada correctamente",
        "category": category.serialize()
    }), 200


@api.route("/categories/<string:category_id>/teams", methods=["GET"])
@jwt_required()
def get_category_teams(category_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    teams = Team.query.filter_by(
        category_id=category.id,
        club_id=user.club_id
    ).order_by(Team.name).all()

    serialized_teams = []

    for team in teams:
        total_players = TeamPlayer.query.filter_by(team_id=team.id).count()

        serialized_teams.append({
            **team.serialize(),
            "total_players": total_players
        })

    return jsonify({
        "category": category.serialize(),
        "teams": serialized_teams
    }), 200


@api.route("/categories/<string:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede eliminar categorías",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes permisos para eliminar esta categoría",
            "FORBIDDEN",
            403
        )

    teams_count = Team.query.filter_by(category_id=category.id).count()

    if teams_count > 0:
        return error_response(
            "No puedes eliminar una categoría que tiene equipos",
            "CATEGORY_HAS_TEAMS",
            409
        )

    db.session.delete(category)
    db.session.commit()

    return jsonify({
        "message": "Categoría eliminada correctamente"
    }), 200

############################################## TEAMS #############################################
@api.route("/categories/<string:category_id>/teams", methods=["POST"])
@jwt_required()
def create_team(category_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear equipos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    category = Category.query.get(category_id)

    if not category:
        return error_response(
            "Categoría no encontrada",
            "CATEGORY_NOT_FOUND",
            404
        )

    if category.club_id != user.club_id:
        return error_response(
            "No tienes permisos para crear equipos en esta categoría",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    name = body.get("name")
    gender = body.get("gender")

    if name:
        name = " ".join(name.strip().split())

    if not name:
        return error_response(
            "Nombre del equipo requerido",
            "TEAM_NAME_REQUIRED",
            400
        )

    allowed_gender = ["female", "male", "mixed"]

    if gender not in allowed_gender:
        return error_response(
            "La rama es inválida",
            "INVALID_TEAM_GENDER",
            400
        )

    existing_team = Team.query.filter(
        Team.club_id == user.club_id,
        Team.category_id == category.id,
        Team.gender == gender,
        func.lower(Team.name) == name.lower()
    ).first()

    if existing_team:
        return error_response(
            "Ya existe este equipo en esa categoría y rama",
            "TEAM_ALREADY_EXISTS",
            409
        )

    team = Team(
        name=name,
        gender=gender,
        category_id=category.id,
        club_id=user.club_id
    )

    db.session.add(team)
    db.session.commit()

    return jsonify({
        "message": "Equipo creado correctamente",
        "team": team.serialize()
    }), 201

@api.route("/teams", methods=["GET"])
@jwt_required()
def get_teams():

    user = get_current_user()
    
    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    teams = Team.query.filter_by(club_id=user.club_id)\
        .order_by(Team.name)\
        .all()

    return jsonify({
        "teams": [t.serialize() for t in teams]
    }), 200

@api.route("/teams/<string:team_id>", methods=["GET"])
@jwt_required()
def get_team_detail(team_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    total_players = TeamPlayer.query.filter_by(team_id=team.id).count()

    return jsonify({
        "team": team.serialize(),
        "stats": {
            "total_players": total_players
        }
    }), 200

@api.route("/teams/<string:team_id>", methods=["PUT"])
@jwt_required()
def update_team(team_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede editar equipos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para editar este equipo",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    name = body.get("name")
    gender = body.get("gender")

    if name:
        name = " ".join(str(name).strip().split())

    if not name:
        return error_response(
            "Nombre del equipo requerido",
            "TEAM_NAME_REQUIRED",
            400
        )

    allowed_gender = ["female", "male", "mixed"]

    if gender not in allowed_gender:
        return error_response(
            "La rama es inválida",
            "INVALID_TEAM_GENDER",
            400
        )

    existing_team = Team.query.filter(
        Team.club_id == user.club_id,
        Team.category_id == team.category_id,
        Team.gender == gender,
        func.lower(Team.name) == name.lower(),
        Team.id != team.id
    ).first()

    if existing_team:
        return error_response(
            "Ya existe este equipo en esa categoría y rama",
            "TEAM_ALREADY_EXISTS",
            409
        )

    if gender != team.gender and gender != "mixed":
        incompatible_player = TeamPlayer.query.join(Player).filter(
            TeamPlayer.team_id == team.id,
            Player.sex != gender
        ).first()

        if incompatible_player:
            return error_response(
                "No puedes cambiar la rama porque hay deportistas incompatibles en este equipo",
                "TEAM_GENDER_HAS_PLAYERS",
                409
            )

    team.name = name
    team.gender = gender

    db.session.commit()

    return jsonify({
        "message": "Equipo actualizado correctamente",
        "team": team.serialize()
    }), 200

@api.route("/teams/<string:team_id>", methods=["DELETE"])
@jwt_required()
def delete_team(team_id):

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede eliminar equipos",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para eliminar este equipo",
            "FORBIDDEN",
            403
        )

    players_count = TeamPlayer.query.filter_by(team_id=team.id).count()

    if players_count > 0:
        return error_response(
            "No puedes eliminar este equipo porque tiene jugadores registrados",
            "TEAM_HAS_PLAYERS",
            409
        )

    trainings_count = TrainingSession.query.filter_by(team_id=team.id).count()

    if trainings_count > 0:
        return error_response(
            "No puedes eliminar este equipo porque tiene entrenamientos históricos",
            "TEAM_HAS_TRAININGS",
            409
        )

    db.session.delete(team)
    db.session.commit()

    return jsonify({
        "message": "Equipo eliminado correctamente"
    }), 200

################################################ PLAYERS #############################################
@api.route("/players", methods=["POST"])
@jwt_required()
def create_player():

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "Solo el dueño del club o un entrenador pueden registrar jugadores",
            "FORBIDDEN",
            403
        )
    
    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    body = request.get_json() or {}
    
    first_name = body.get("first_name")
    last_name = body.get("last_name")
    player_number = body.get("player_number")
    sex = body.get("sex")
    birth_date = body.get("birth_date")
    status = body.get("status", "active")
    team_id = body.get("team_id")
    representative_name = body.get("representative_name")
    representative_phone = body.get("representative_phone")

    if representative_name:
        representative_name = " ".join(str(representative_name).strip().split())

    if representative_phone:
        representative_phone = str(representative_phone).strip()

    main_position = (body.get("main_position") or "").strip().lower() or None

    if main_position and main_position not in ALLOWED_POSITIONS:
        return error_response(
            "Posición inválida",
            "INVALID_POSITION",
            400
        )

    allowed_sex = ["male", "female"]

    if not sex:
        return error_response(
            "El sexo es obligatorio",
            "SEX_REQUIRED",
            400
        )

    if sex not in allowed_sex:
        return error_response(
            "Sexo inválido",
            "INVALID_SEX",
            400
        )

    allowed_status = ["active", "injured", "inactive"]

    if status not in allowed_status:
        return error_response(
            "Estado del jugador inválido",
            "INVALID_PLAYER_STATUS",
            400
        )

    if not first_name:
        return error_response(
            "Nombre del jugador requerido",
            "FIRST_NAME_REQUIRED",
            400
        )

    if not last_name:
        return error_response(
            "Apellido del jugador requerido",
            "LAST_NAME_REQUIRED",
            400
        )

    team = None

    if team_id:
        if player_number is None:
            return error_response(
                "El número del jugador es obligatorio",
                "PLAYER_NUMBER_REQUIRED",
                400
            )

        try:
            player_number = int(player_number)
        except (TypeError, ValueError):
            return error_response(
                "El número del jugador debe ser numérico",
                "INVALID_PLAYER_NUMBER",
                400
            )

        if player_number <= 0:
            return error_response(
                "El número del jugador debe ser mayor que cero",
                "INVALID_PLAYER_NUMBER",
                400
            )

        team = Team.query.get(team_id)

        if not team:
            return error_response(
                "Equipo no encontrado",
                "TEAM_NOT_FOUND",
                404
            )

        if team.club_id != user.club_id:
            return error_response(
                "No tienes permisos para registrar jugadores en este equipo",
                "FORBIDDEN",
                403
            )

        if team.gender != "mixed" and team.gender != sex:
            return error_response(
                "El sexo del jugador no coincide con la rama del equipo",
                "PLAYER_GENDER_MISMATCH",
                400
            )

        existing_membership = TeamPlayer.query.filter_by(
            team_id=team.id,
            player_number=player_number
        ).first()

        if existing_membership:
            return error_response(
                "Ya existe un jugador con ese número en este equipo",
                "PLAYER_NUMBER_DUPLICATED",
                409
            )
    
    parsed_birth_date = None

    if birth_date:
        try:
            parsed_birth_date = datetime.strptime(
                birth_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            return error_response(
                "Formato de fecha inválido. Usa YYYY-MM-DD",
                "INVALID_DATE_FORMAT",
                400
            )

    player = Player(
        first_name=first_name,
        last_name=last_name,
        sex=sex,
        birth_date=parsed_birth_date,
        main_position=main_position,
        representative_name=representative_name or None,
        representative_phone=representative_phone or None,
        club_id=user.club_id
    )

    db.session.add(player)
    db.session.flush()

    membership = None

    if team:
        membership = TeamPlayer(
            team_id=team.id,
            player_id=player.id,
            player_number=player_number,
            status=status
        )
        db.session.add(membership)
    db.session.commit()

    return jsonify({
        "message": "Jugador registrado correctamente",
        "player": {
            **player.serialize(),
            "team_id": membership.team_id if membership else None,
            "player_number": membership.player_number if membership else None,
            "status": membership.status if membership else "active"
        }
    }), 201

@api.route("/players/<string:player_id>/upload-image", methods=["POST"])
@jwt_required()
def upload_player_image(player_id):

    user = get_current_user()

    player = Player.query.get(player_id)

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    if player.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if "image" not in request.files:
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    image = request.files["image"]

    if image.filename == "":
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    if not allowed_image_file(image.filename):
        return error_response(
            "Formato inválido. Usa PNG, JPG o WEBP",
            "INVALID_IMAGE_FORMAT",
            400
        )

    image.seek(0, os.SEEK_END)
    image_size = image.tell()
    image.seek(0)

    if image_size > MAX_PLAYER_IMAGE_SIZE:
        return error_response(
            "La imagen no puede pesar más de 5MB",
            "IMAGE_TOO_LARGE",
            400
        )

    original_filename = secure_filename(image.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    filename = f"{player.id}-{uuid.uuid4().hex}.{extension}"

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../public/uploads/players"
        )
    )

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)
    image.save(file_path)

    image_url = f"/uploads/players/{filename}"

    player.image_url = image_url
    db.session.commit()

    return jsonify({
        "image_url": image_url,
        "player": player.serialize()
    }), 201

@api.route("/players/<string:player_id>/active", methods=["PUT"])
@jwt_required()
def update_player_active_status(player_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar jugadores",
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

    body = request.get_json() or {}
    is_active = body.get("is_active")

    if not isinstance(is_active, bool):
        return error_response(
            "Estado inválido",
            "INVALID_PLAYER_ACTIVE_STATUS",
            400
        )

    player.is_active = is_active

    db.session.commit()

    return jsonify({
        "message": "Estado del jugador actualizado correctamente",
        "player": player.serialize()
    }), 200

@api.route("/teams/<string:team_id>/players", methods=["GET"])
@jwt_required()
def get_team_players(team_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver jugadores",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    memberships = TeamPlayer.query.filter_by(team_id=team.id)\
        .order_by(TeamPlayer.player_number)\
        .all()

    players = [
        {
            "id": m.player.id,
            "first_name": m.player.first_name,
            "last_name": m.player.last_name,
            "sex": m.player.sex,
            "birth_date": m.player.birth_date.isoformat() if m.player.birth_date else None,
            "main_position": m.player.main_position,
            "team_id": m.team_id,
            "player_number": m.player_number,
            "status": m.status
        }
        for m in memberships
    ]

    return jsonify({
        "team": team.serialize(),
        "total_players": len(players),
        "players": players
    }), 200

@api.route("/players", methods=["GET"])
@jwt_required()
def get_players():
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    players = Player.query.filter_by(
        club_id=user.club_id
    ).order_by(Player.created_at.desc()).all()

    serialized_players = []

    for player in players:
        membership = player.team_memberships[0] if player.team_memberships else None

        serialized_players.append({
            **player.serialize(),
            "team_id": membership.team_id if membership else None,
            "player_number": membership.player_number if membership else None,
            "status": membership.status if membership else "active",
            "teams": [
                {
                    "id": m.team.id,
                    "name": m.team.name,
                    "gender": m.team.gender,
                    "category_id": m.team.category_id,
                    "category_name": m.team.category.name if m.team.category else None,
                    "player_number": m.player_number,
                    "status": m.status
                }
                for m in player.team_memberships
            ]
        })

    return jsonify({
        "total_players": len(serialized_players),
        "players": serialized_players
    }), 200

@api.route("/teams/<string:team_id>/players/existing", methods=["POST"])
@jwt_required()
def add_existing_player_to_team(team_id):
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    player_id = body.get("player_id")
    player_number = body.get("player_number")

    if not player_id:
        return error_response(
            "Jugador requerido",
            "PLAYER_REQUIRED",
            400
        )

    if player_number is None:
        return error_response(
            "Número requerido",
            "PLAYER_NUMBER_REQUIRED",
            400
        )
    
    try:
        player_number = int(player_number)
    except (TypeError, ValueError):
        return error_response(
            "El número del jugador debe ser numérico",
            "INVALID_PLAYER_NUMBER",
            400
        )

    if player_number < 1 or player_number > 99:
        return error_response(
            "El número del jugador debe estar entre 1 y 99",
            "INVALID_PLAYER_NUMBER",
            400
        )

    player = Player.query.get(player_id)

    if not player or player.club_id != user.club_id:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    if not player.is_active:
        return error_response(
            "No puedes asignar una jugadora desactivada",
            "PLAYER_INACTIVE",
            400
        )
    
    if team.gender != "mixed" and team.gender != player.sex:
        return error_response(
            "El jugador no coincide con la rama de la categoría",
            "PLAYER_GENDER_MISMATCH",
            400
        )

    existing = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_id=player.id
    ).first()

    if existing:
        return error_response(
            "El jugador ya pertenece al equipo",
            "PLAYER_ALREADY_IN_TEAM",
            409
        )

    duplicated_number = TeamPlayer.query.filter_by(
        team_id=team.id,
        player_number=player_number
    ).first()

    if duplicated_number:
        return error_response(
            "Número duplicado",
            "PLAYER_NUMBER_DUPLICATED",
            409
        )

    membership = TeamPlayer(
        team_id=team.id,
        player_id=player.id,
        player_number=player_number,
        status="active"
    )

    db.session.add(membership)
    db.session.commit()

    return jsonify({
        "message": "Jugador agregado al equipo",
        "player": membership.serialize()
    }), 201

@api.route("/players/<string:player_id>", methods=["PUT"])
@jwt_required()
def update_player(player_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar jugadores",
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

    body = request.get_json() or {}

    first_name = body.get("first_name")
    last_name = body.get("last_name")
    sex = body.get("sex")
    birth_date = body.get("birth_date")
    team_id = body.get("team_id")
    representative_name = body.get("representative_name")
    representative_phone = body.get("representative_phone")

    main_position = (body.get("main_position") or "").strip().lower() or None

    if main_position and main_position not in ALLOWED_POSITIONS:
        return error_response(
            "Posición inválida",
            "INVALID_POSITION",
            400
        )
    
    player_number = body.get("player_number")

    if not first_name:
        return error_response(
            "Nombre del jugador requerido",
            "FIRST_NAME_REQUIRED",
            400
        )

    if not last_name:
        return error_response(
            "Apellido del jugador requerido",
            "LAST_NAME_REQUIRED",
            400
        )

    allowed_sex = ["male", "female"]

    if sex not in allowed_sex:
        return error_response(
            "Sexo inválido",
            "INVALID_SEX",
            400
        )

    # ✅ validar cambio global de sexo contra TODAS sus categorías
    memberships = TeamPlayer.query.filter_by(
        player_id=player.id
    ).all()

    for membership in memberships:
        team = Team.query.get(membership.team_id)

        if not team:
            continue

        if team.gender != "mixed" and team.gender != sex:
            return error_response(
                "No puedes cambiar el sexo porque la jugadora pertenece a categorías incompatibles",
                "PLAYER_GENDER_MISMATCH",
                409
            )

    # ✅ actualizar perfil global
    player.first_name = first_name
    player.last_name = last_name
    player.sex = sex

    if representative_name is not None:
        representative_name = " ".join(str(representative_name).strip().split())
        player.representative_name = representative_name or None

    if representative_phone is not None:
        representative_phone = str(representative_phone).strip()
        player.representative_phone = representative_phone or None

    # ✅ fecha opcional
    if birth_date:
        try:
            player.birth_date = datetime.strptime(
                birth_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            return error_response(
                "Formato de fecha inválido",
                "INVALID_DATE_FORMAT",
                400
            )

    # ✅ actualizar número SOLO en membership específica
    if team_id and player_number is not None:
        membership = TeamPlayer.query.filter_by(
            player_id=player.id,
            team_id=team_id
        ).first()

        if not membership:
            return error_response(
                "El jugador no pertenece a esta categoría",
                "PLAYER_MEMBERSHIP_NOT_FOUND",
                404
            )
        
        try:
            player_number = int(player_number)
        except (TypeError, ValueError):
            return error_response(
                "El número del jugador debe ser numérico",
                "INVALID_PLAYER_NUMBER",
                400
            )

        if player_number < 1 or player_number > 99:
            return error_response(
                "El número del jugador debe estar entre 1 y 99",
                "INVALID_PLAYER_NUMBER",
                400
            )

        duplicated_number = TeamPlayer.query.filter(
            TeamPlayer.team_id == team_id,
            TeamPlayer.player_number == player_number,
            TeamPlayer.player_id != player.id
        ).first()

        if duplicated_number:
            return error_response(
                "Ya existe un jugador con ese número",
                "PLAYER_NUMBER_DUPLICATED",
                409
            )

        membership.player_number = int(player_number)

    player.main_position = main_position

    db.session.commit()

    return jsonify({
        "message": "Jugador actualizado correctamente",
        "player": player.serialize()
    }), 200

@api.route("/players/<string:player_id>/status", methods=["PUT"])
@jwt_required()
def update_player_status(player_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para modificar jugadores",
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

    body = request.get_json() or {}
    status = body.get("status")
    team_id = body.get("team_id")

    if not team_id:
        return error_response(
            "La categoría es obligatoria",
            "TEAM_ID_REQUIRED",
            400
        )

    allowed_status = ["active", "injured", "inactive"]

    if status not in allowed_status:
        return error_response(
            "Estado del jugador inválido",
            "INVALID_PLAYER_STATUS",
            400
        )

    membership = TeamPlayer.query.filter_by(
        player_id=player.id,
        team_id=team_id
    ).first()

    if not membership:
        return error_response(
            "El jugador no pertenece a esta categoría",
            "PLAYER_MEMBERSHIP_NOT_FOUND",
            404
        )

    team = Team.query.get(team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes permisos para modificar este jugador",
            "FORBIDDEN",
            403
        )

    membership.status = status
    db.session.commit()

    return jsonify({
        "message": "Estado del jugador actualizado correctamente",
        "player": {
            **player.serialize(),
            "team_id": membership.team_id,
            "player_number": membership.player_number,
            "status": membership.status
        }
    }), 200

@api.route("/players/<string:player_id>", methods=["DELETE"])
@jwt_required()
def delete_player(player_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para eliminar jugadores",
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

    memberships = TeamPlayer.query.filter_by(
        player_id=player.id
    ).all()

    # 🚨 protección histórica
    attendance_exists = Attendance.query.filter_by(
        player_id=player.id
    ).first()

    match_exists = MatchPlayer.query.filter_by(
        player_id=player.id
    ).first()

    if attendance_exists or match_exists:
        return error_response(
            "No puedes eliminar una jugadora con historial registrado",
            "PLAYER_HAS_HISTORY",
            409
        )

    for membership in memberships:
        db.session.delete(membership)

    db.session.delete(player)
    db.session.commit()

    return jsonify({
        "message": "Jugador eliminado correctamente"
    }), 200

########################################### PAYMENTS #############################################

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

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para configurar pagos",
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

    body = request.get_json() or {}

    enrollment_date = body.get("enrollment_date")
    custom_enrollment_fee = body.get("enrollment_fee")
    custom_monthly_fee = body.get("monthly_fee")

    # Validar fecha de inscripción
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

    # Detectar si la jugadora tiene montos personalizados
    has_custom_enrollment_fee = (
        custom_enrollment_fee is not None and custom_enrollment_fee != ""
    )

    has_custom_monthly_fee = (
        custom_monthly_fee is not None and custom_monthly_fee != ""
    )

    # Montos efectivos:
    # Si viene personalizado, usa personalizado.
    # Si no viene personalizado, usa el monto del club.
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

    if enrollment_fee <= 0:
        return error_response(
            "Debes configurar un monto de inscripción válido",
            "INVALID_ENROLLMENT_FEE",
            400
        )

    if monthly_fee <= 0:
        return error_response(
            "Debes configurar una mensualidad válida",
            "INVALID_MONTHLY_FEE",
            400
        )

    # Guardar configuración del jugador
    player.enrollment_date = parsed_enrollment_date

    # Importante:
    # Si NO son montos personalizados, dejamos null en el jugador.
    # Así el frontend sabe que debe mostrar el checkbox desmarcado.
    player.enrollment_fee = enrollment_fee if has_custom_enrollment_fee else None
    player.monthly_fee = monthly_fee if has_custom_monthly_fee else None

    player.payment_cycle_day = payment_cycle_day

    # Limpiar mensualidades NO pagadas para regenerarlas desde la nueva fecha.
    # No tocamos pagos pagados para no borrar historial real.
    old_unpaid_monthly_payments = PlayerPayment.query.filter(
        PlayerPayment.club_id == user.club_id,
        PlayerPayment.player_id == player.id,
        PlayerPayment.payment_type == "monthly",
        PlayerPayment.status.in_(["pending", "overdue"])
    ).all()

    for payment in old_unpaid_monthly_payments:
        db.session.delete(payment)

    # Crear o actualizar cargo de inscripción
    if enrollment_fee > 0:
        existing_enrollment_payment = PlayerPayment.query.filter_by(
            club_id=user.club_id,
            player_id=player.id,
            payment_type="enrollment"
        ).first()

        if existing_enrollment_payment:
            # Si todavía no fue pagada, sí podemos corregir fecha y monto.
            if existing_enrollment_payment.status in ["pending", "overdue"]:
                existing_enrollment_payment.amount = enrollment_fee
                existing_enrollment_payment.due_date = parsed_enrollment_date
                existing_enrollment_payment.status = "pending"
        else:
            enrollment_payment = PlayerPayment(
                club_id=user.club_id,
                player_id=player.id,
                payment_type="enrollment",
                amount=enrollment_fee,
                status="pending",
                due_date=parsed_enrollment_date,
                created_by=user.id
            )

            db.session.add(enrollment_payment)

    # Crear mensualidades desde la fecha de inscripción hasta el ciclo actual
    if monthly_fee > 0:
        today = datetime.utcnow().date()

        period_start = parsed_enrollment_date
        safety_counter = 0

        while period_start <= today and safety_counter < 36:
            period_end = add_months(period_start, 1)

            existing_monthly_payment = PlayerPayment.query.filter_by(
                club_id=user.club_id,
                player_id=player.id,
                payment_type="monthly",
                period_start=period_start
            ).first()

            if not existing_monthly_payment:
                monthly_payment = PlayerPayment(
                    club_id=user.club_id,
                    player_id=player.id,
                    payment_type="monthly",
                    amount=monthly_fee,
                    status="pending",
                    period_start=period_start,
                    period_end=period_end,
                    due_date=period_start + timedelta(days=5),
                    created_by=user.id
                )

                db.session.add(monthly_payment)

            period_start = period_end
            safety_counter += 1

    db.session.commit()

    return jsonify({
        "message": "Configuración de pagos actualizada correctamente",
        "player": player.serialize()
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

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para ver pagos",
            "FORBIDDEN",
            403
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

    all_payments = summary_query.order_by(
        PlayerPayment.due_date.asc().nullslast(),
        Player.first_name.asc(),
        Player.last_name.asc()
    ).all()

    payments = list_query.order_by(
        PlayerPayment.due_date.asc().nullslast(),
        Player.first_name.asc(),
        Player.last_name.asc()
    ).all()

    today = datetime.utcnow().date()
    status_changed = False

    for payment in all_payments:
        if (
            payment.status == "pending"
            and payment.due_date
            and payment.due_date < today
        ):
            payment.status = "overdue"
            status_changed = True

    if status_changed:
        db.session.commit()

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

        "expected_amount": 0,
        "total_amount": 0
    }

    for payment in all_payments:
        amount = payment.amount or 0

        if payment.status in ["pending", "paid", "overdue", "cancelled"]:
            summary[payment.status] += 1
            summary[f"{payment.status}_amount"] += amount

        if payment.status in ["pending", "overdue"]:
            summary["expected_amount"] += amount

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

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para actualizar pagos",
            "FORBIDDEN",
            403
        )

    payment = PlayerPayment.query.get(payment_id)

    if not payment or payment.club_id != user.club_id:
        return error_response(
            "Pago no encontrado",
            "PAYMENT_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    status = body.get("status")
    amount = body.get("amount")
    payment_method = body.get("payment_method")
    reference = body.get("reference")
    notes = body.get("notes")
    payment_date = body.get("payment_date")
    due_date = body.get("due_date")

    if status is not None:
        if status not in VALID_PAYMENT_STATUSES:
            return error_response(
                "Estado de pago inválido",
                "INVALID_PAYMENT_STATUS",
                400
            )

        payment.status = status

        if status == "paid":
            payment.paid_by = user.id

            if not payment.payment_date:
                payment.payment_date = datetime.utcnow().date()

        else:
            if payment.receipt:
                db.session.delete(payment.receipt)

            payment.paid_by = None
            payment.payment_date = None
            payment.payment_method = None
            payment.reference = None

    if amount is not None:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return error_response(
                "Monto inválido",
                "INVALID_PAYMENT_AMOUNT",
                400
            )

        if amount < 0:
            return error_response(
                "El monto no puede ser negativo",
                "INVALID_PAYMENT_AMOUNT",
                400
            )

        payment.amount = amount

    if payment_method is not None:
        payment_method = str(payment_method).strip() or None

        if payment_method and payment_method not in VALID_PAYMENT_METHODS:
            return error_response(
                "Método de pago inválido",
                "INVALID_PAYMENT_METHOD",
                400
            )

        payment.payment_method = payment_method

    if reference is not None:
        payment.reference = str(reference).strip() or None

    if notes is not None:
        payment.notes = str(notes).strip() or None

    if payment_date is not None:
        if payment_date:
            try:
                payment.payment_date = datetime.strptime(
                    payment_date, "%Y-%m-%d"
                ).date()
            except ValueError:
                return error_response(
                    "Formato de fecha inválido. Usa YYYY-MM-DD",
                    "INVALID_DATE_FORMAT",
                    400
                )
        else:
            payment.payment_date = None

    if due_date is not None:
        if due_date:
            try:
                payment.due_date = datetime.strptime(
                    due_date, "%Y-%m-%d"
                ).date()
            except ValueError:
                return error_response(
                    "Formato de fecha límite inválido. Usa YYYY-MM-DD",
                    "INVALID_DUE_DATE_FORMAT",
                    400
                )
        else:
            payment.due_date = None

    db.session.commit()

    return jsonify({
        "message": "Pago actualizado correctamente",
        "payment": payment.serialize()
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

    if user.role not in ["club_owner", "coach", "staff"]:
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

    payments = PlayerPayment.query.filter_by(
        player_id=player.id,
        club_id=user.club_id
    ).order_by(
        PlayerPayment.due_date.desc().nullslast(),
        PlayerPayment.created_at.desc()
    ).all()

    today = datetime.utcnow().date()
    status_changed = False

    for payment in payments:
        if (
            payment.status == "pending"
            and payment.due_date
            and payment.due_date < today
        ):
            payment.status = "overdue"
            status_changed = True

    if status_changed:
        db.session.commit()

    return jsonify({
        "player": player.serialize(),
        "payments": [payment.serialize() for payment in payments]
    }), 200

@api.route("/payments/<string:payment_id>/receipt", methods=["POST"])
@jwt_required()
def create_payment_receipt(payment_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para generar recibos",
            "FORBIDDEN",
            403
        )

    payment = PlayerPayment.query.get(payment_id)

    if not payment or payment.club_id != user.club_id:
        return error_response(
            "Pago no encontrado",
            "PAYMENT_NOT_FOUND",
            404
        )

    if payment.status != "paid":
        return error_response(
            "Solo puedes generar recibos de pagos registrados",
            "PAYMENT_NOT_PAID",
            400
        )

    existing_receipt = PaymentReceipt.query.filter_by(
        payment_id=payment.id
    ).first()

    if existing_receipt:
        if not existing_receipt.pdf_url:
            existing_receipt.pdf_url = generate_payment_receipt_pdf(
                existing_receipt,
                payment
            )
            db.session.commit()

        return jsonify({
            "message": "El recibo ya existe",
            "receipt": existing_receipt.serialize(),
            "payment": payment.serialize()
        }), 200

    receipt = PaymentReceipt(
        payment_id=payment.id,
        club_id=payment.club_id,
        player_id=payment.player_id,
        receipt_number=generate_receipt_number(payment.club_id),
        pdf_url=None
    )

    db.session.add(receipt)
    db.session.flush()

    receipt.pdf_url = generate_payment_receipt_pdf(receipt, payment)

    db.session.commit()

    return jsonify({
        "message": "Recibo generado correctamente",
        "receipt": receipt.serialize(),
        "payment": payment.serialize()
    }), 201

@api.route("/payment-receipts/<string:receipt_id>/share", methods=["PUT"])
@jwt_required()
def mark_payment_receipt_shared(receipt_id):
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    receipt = PaymentReceipt.query.get(receipt_id)

    if not receipt or receipt.club_id != user.club_id:
        return error_response(
            "Recibo no encontrado",
            "RECEIPT_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    sent_channel = body.get("sent_channel")
    sent_to = body.get("sent_to")

    if sent_channel not in ["whatsapp", "email", "manual"]:
        return error_response(
            "Canal de envío inválido",
            "INVALID_RECEIPT_CHANNEL",
            400
        )

    receipt.sent_channel = sent_channel
    receipt.sent_to = str(sent_to).strip() if sent_to else None
    receipt.sent_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "message": "Recibo marcado como compartido",
        "receipt": receipt.serialize()
    }), 200

########################################### ATTENDANCE #############################################
@api.route("/trainings/<string:training_id>/attendance", methods=["POST"])
@jwt_required()
def save_attendance(training_id):

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para registrar asistencia",
            "FORBIDDEN",
            403
        )

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este entrenamiento",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    attendance_list = body.get("attendance")

    if not attendance_list:
        return error_response(
            "Lista de asistencia requerida",
            "ATTENDANCE_REQUIRED",
            400
        )

    Attendance.query.filter_by(session_id=training.id).delete()

    allowed_status = ["present", "late", "absent"]

    for item in attendance_list:

        player_id = item.get("player_id")
        status = item.get("status", "present")

        if status not in allowed_status:
            return error_response(
                "Estado de asistencia inválido",
                "INVALID_ATTENDANCE_STATUS",
                400
            )

        attendance = Attendance(
            session_id=training.id,
            player_id=player_id,
            status=status
        )

        db.session.add(attendance)

    db.session.commit()

    return jsonify({
        "message": "Asistencia guardada correctamente"
    }), 200

@api.route("/trainings/<string:training_id>/attendance", methods=["GET"])
@jwt_required()
def get_attendance(training_id):

    user = get_current_user()

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    attendance = Attendance.query.filter_by(
        session_id=training.id
    ).all()

    return jsonify({
        "attendance": [a.serialize() for a in attendance]
    }), 200

@api.route("/trainings/<string:training_id>/players", methods=["GET"])
@jwt_required()
def get_training_players(training_id):
    user = get_current_user()

    training = TrainingSession.query.get(training_id)

    if not training:
        return error_response(
            "Entrenamiento no encontrado",
            "TRAINING_NOT_FOUND",
            404
        )

    team = Team.query.get(training.team_id)

    if not team or team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    snapshot = TrainingPlayer.query.filter_by(
        training_id=training.id
    ).order_by(TrainingPlayer.player_number).all()

    players = []

    for row in snapshot:
        if not row.player:
            continue

        players.append({
            "id": row.player.id,
            "first_name": row.player.first_name,
            "last_name": row.player.last_name,
            "player_number": row.player_number,
            "sex": row.player.sex
        })

    return jsonify({
        "players": players
    }), 200

@api.route("/players/<string:player_id>/attendance", methods=["GET"])
@jwt_required()
def get_player_attendance(player_id):

    user = get_current_user()

    player = Player.query.get(player_id)

    if not player:
        return error_response(
            "Jugador no encontrado",
            "PLAYER_NOT_FOUND",
            404
        )

    memberships = TeamPlayer.query.filter_by(
        player_id=player.id
    ).all()

    if player.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )


    for membership in memberships:
        team = Team.query.get(membership.team_id)

        if not team or team.club_id != user.club_id:
            return error_response(
                "No tienes acceso",
                "FORBIDDEN",
                403
            )
        
    attendance_records = Attendance.query.join(TrainingSession).filter(
        Attendance.player_id == player.id
    ).order_by(TrainingSession.date.desc()).all()

    history = []
    present = 0
    late = 0
    absent = 0

    for record in attendance_records:
        if record.status == "present":
            present += 1
        elif record.status == "late":
            late += 1
        elif record.status == "absent":
            absent += 1

        history.append({
            "training_id": record.session_id,
            "date": record.session.date.isoformat(),
            "location": record.session.location,
            "status": record.status
        })

    total = present + late + absent
    attendance_rate = round((present / total) * 100) if total > 0 else 0

    return jsonify({
        "player": {
            **player.serialize(),
            "teams": [
                {
                    "id": m.team.id,
                    "name": m.team.name,
                    "gender": m.team.gender,
                    "category_id": m.team.category_id,
                    "category_name": m.team.category.name if m.team.category else None,
                    "player_number": m.player_number,
                    "status": m.status
                }
                for m in memberships
            ]
        },
        "summary": {
            "present": present,
            "late": late,
            "absent": absent,
            "total_sessions": total,
            "attendance_rate": attendance_rate
        },
        "history": history
    }), 200

############################################ TRAININGS ##############################################
@api.route("/trainings", methods=["POST"])
@jwt_required()
def create_training():

    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    team_id = body.get("team_id")
    date = body.get("date")
    location = body.get("location")

    # ✅ VALIDACIONES VAN AQUÍ
    if not team_id:
        return error_response(
            "La categoría es obligatoria",
            "TEAM_ID_REQUIRED",
            400
        )

    if not date:
        return error_response(
            "La fecha del entrenamiento es obligatoria",
            "TRAINING_DATE_REQUIRED",
            400
        )

    if not location or not str(location).strip():
        return error_response(
            "La ubicación del entrenamiento es obligatoria",
            "TRAINING_LOCATION_REQUIRED",
            400
        )

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )

    location = location.strip()

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    training = TrainingSession(
        team_id=team.id,
        date=parsed_date,
        location=location,
        created_by=user.id
    )

    db.session.add(training)
    db.session.flush()

    current_roster = TeamPlayer.query.filter_by(
        team_id=team.id
    ).all()

    for member in current_roster:
        snapshot = TrainingPlayer(
            training_id=training.id,
            player_id=member.player_id,
            player_number=member.player_number
        )
        db.session.add(snapshot)

    db.session.commit()

    return jsonify({
        "message": "Entrenamiento creado",
        "training": training.serialize()
    }), 201

@api.route("/teams/<string:team_id>/trainings", methods=["GET"])
@jwt_required()
def get_team_trainings(team_id):

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
            "FORBIDDEN",
            403
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    # Seguridad multi-tenant
    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este equipo",
            "FORBIDDEN",
            403
        )

    trainings = TrainingSession.query.filter_by(team_id=team.id)\
        .order_by(TrainingSession.date.desc())\
        .all()

    return jsonify({
        "team": team.serialize(),
        "total_trainings": len(trainings),
        "trainings": [t.serialize() for t in trainings]
    }), 200

@api.route("/trainings", methods=["GET"])
@jwt_required()
def get_all_trainings():

    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver entrenamientos",
            "FORBIDDEN",
            403
        )

    trainings = TrainingSession.query.join(Team).filter(
        Team.club_id == user.club_id
    ).order_by(TrainingSession.date.desc()).all()

    return jsonify({
        "total_trainings": len(trainings),
        "trainings": [
        {
            **t.serialize(),
            "team_name": t.team.name
        }
        for t in trainings
    ]
    }), 200
############################################ ONBOARDING #############################################
@api.route("/onboarding/status", methods=["GET"])
@jwt_required()
def onboarding_status():
    print("ONBOARDING STATUS HIT")

    user = get_current_user()

    if user.role == "system_admin":
        return jsonify({
            "step": 5,
            "status": "completed",
            "club": None
        }), 200

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    # STEP 1 — configurar ciudad del club
    if not club.location:
        return jsonify({
            "step": 1,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 2 — crear primera categoría
    categories_count = Category.query.filter_by(
        club_id=club.id
    ).count()

    if categories_count == 0:
        return jsonify({
            "step": 2,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 3 — crear primer equipo dentro de una categoría
    teams_count = Team.query.filter_by(
        club_id=club.id
    ).count()

    if teams_count == 0:
        return jsonify({
            "step": 3,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 4 — registrar primer deportista en un equipo
    players_count = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    if players_count == 0:
        return jsonify({
            "step": 4,
            "status": "pending",
            "club": club.serialize()
        }), 200

    # STEP 5 — onboarding completo
    return jsonify({
        "step": 5,
        "status": "completed",
        "club": club.serialize()
    }), 200

@api.route("/onboarding/complete", methods=["POST"])
@jwt_required()
def complete_onboarding():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede completar el onboarding",
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

    categories_count = Category.query.filter_by(
        club_id=club.id
    ).count()

    if categories_count == 0:
        return error_response(
            "Debes crear al menos una categoría antes de activar el sistema",
            "ONBOARDING_REQUIRES_CATEGORY",
            400
        )

    teams_count = Team.query.filter_by(
        club_id=club.id
    ).count()

    if teams_count == 0:
        return error_response(
            "Debes crear al menos un equipo antes de activar el sistema",
            "ONBOARDING_REQUIRES_TEAM",
            400
        )

    players_count = TeamPlayer.query.join(Team).filter(
        Team.club_id == club.id
    ).count()

    if players_count == 0:
        return error_response(
            "Debes registrar al menos un deportista antes de activar el sistema",
            "ONBOARDING_REQUIRES_PLAYERS",
            400
        )

    user.first_login = False
    db.session.commit()

    return jsonify({
        "message": "Sistema activado correctamente"
    }), 200

############################################# MATCHES #############################################

@api.route("/matches", methods=["POST"])
@jwt_required()
def create_match():
    user = get_current_user()

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para crear partidos",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    team_id = body.get("team_id")
    date = body.get("date")
    opponent_name = body.get("opponent_name")
    match_type = body.get("match_type", "official")
    location = body.get("location")
    notes = body.get("notes")

    if opponent_name:
        opponent_name = opponent_name.strip()
    
    if not team_id:
        return error_response(
            "La categoría es obligatoria",
            "TEAM_ID_REQUIRED",
            400
        )
    
    if match_type not in VALID_MATCH_TYPES:
        return error_response(
            "Tipo de partido inválido",
            "INVALID_MATCH_TYPE",
            400
        )

    if not date:
        return error_response(
            "La fecha es obligatoria",
            "MATCH_DATE_REQUIRED",
            400
        )

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return error_response(
            "Formato de fecha inválido. Usa YYYY-MM-DD",
            "INVALID_DATE_FORMAT",
            400
        )
    
    if not opponent_name:
        return error_response(
            "El rival es obligatorio",
            "OPPONENT_NAME_REQUIRED",
            400
        )

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría}",
            "FORBIDDEN",
            403
        )

    match = MatchSession(
        team_id=team.id,
        date=parsed_date,
        opponent_name=opponent_name,
        match_type=match_type,
        location=location,
        notes=notes,
        created_by=user.id
    )

    db.session.add(match)
        
    db.session.flush()

    current_roster = TeamPlayer.query.filter_by(
        team_id=team.id
    ).all()

    for member in current_roster:
        snapshot = MatchPlayer(
            match_id=match.id,
            player_id=member.player_id,
            player_number=member.player_number,
            is_called=False,
            attendance_status=None,
            did_play=False
        )
        db.session.add(snapshot)

    db.session.commit()

    return jsonify({
        "message": "Partido creado correctamente",
        "match": match.serialize()
    }), 201

@api.route("/teams/<string:team_id>/matches", methods=["GET"])
@jwt_required()
def get_team_matches(team_id):
    user = get_current_user()

    team = Team.query.get(team_id)

    if not team:
        return error_response(
            "Equipo no encontrado",
            "TEAM_NOT_FOUND",
            404
        )

    if team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a esta categoría",
            "FORBIDDEN",
            403
        )

    matches = MatchSession.query.filter_by(team_id=team.id)\
        .order_by(MatchSession.date.desc())\
        .all()

    return jsonify({
        "team": team.serialize(),
        "total_matches": len(matches),
        "matches": [m.serialize() for m in matches]
    }), 200

@api.route("/matches/<string:match_id>/roster", methods=["POST"])
@jwt_required()
def save_match_roster(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso a este partido",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response(
            "Debes seleccionar al menos una jugadora",
            "MATCH_ROSTER_REQUIRED",
            400
        )

    selected_ids = {
        item.get("player_id")
        for item in players
        if item.get("player_id")
    }

    rows = MatchPlayer.query.filter_by(match_id=match.id).all()

    for row in rows:
        was_called = row.player_id in selected_ids
        row.is_called = was_called

        if not was_called:
            row.attendance_status = None
            row.did_play = False
            row.is_on_court = False
            row.position = None

    match.match_step = max(match.match_step, 1)

    db.session.commit()

    return jsonify({
        "message": "Convocatoria guardada correctamente"
    }), 200

@api.route("/matches/<string:match_id>/roster/status", methods=["PUT"])
@jwt_required()
def update_match_status(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response("Partido no encontrado", "MATCH_NOT_FOUND", 404)

    if match.team.club_id != user.club_id:
        return error_response("No tienes acceso", "FORBIDDEN", 403)

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response("Lista requerida", "MATCH_STATUS_REQUIRED", 400)

    for item in players:
        match_player_id = item.get("match_player_id")
        status = item.get("attendance_status")
        position = (item.get("position") or "").strip().lower()

        if not match_player_id:
            return error_response(
                "Registro del partido requerido",
                "MATCH_PLAYER_ID_REQUIRED",
                400
            )

        row = MatchPlayer.query.get(match_player_id)

        if not row:
            return error_response(
                "Registro del partido no encontrado",
                "MATCH_PLAYER_NOT_FOUND",
                404
            )

        if row.match_id != match.id:
            return error_response(
                "La jugadora no pertenece a este partido",
                "MATCH_PLAYER_INVALID",
                400
            )

        if not row.is_called:
            return error_response(
                "La jugadora no está convocada para este partido",
                "PLAYER_NOT_CALLED",
                400
            )

        if status not in VALID_MATCH_STATUSES:
            return error_response(
                "Estado inválido",
                "INVALID_MATCH_STATUS",
                400
            )

        if status in PLAYABLE_MATCH_STATUSES:
            if not position:
                position = row.player.main_position

            if not position:
                return error_response(
                    "La posición es obligatoria para jugadoras presentes o tarde",
                    "POSITION_REQUIRED",
                    400
                )

            if position not in ALLOWED_POSITIONS:
                return error_response(
                    "Posición inválida",
                    "INVALID_POSITION",
                    400
                )

            row.position = position
        else:
            row.position = None
            row.did_play = False
            row.is_on_court = False

        row.attendance_status = status

    match.match_step = max(match.match_step, 2)

    db.session.commit()

    return jsonify({
        "message": "Estado del día actualizado"
    }), 200

@api.route("/matches", methods=["GET"])
@jwt_required()
def get_club_matches():
    user = get_current_user()

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    if user.role not in ["club_owner", "coach"]:
        return error_response(
            "No tienes permisos para ver partidos",
            "FORBIDDEN",
            403
        )

    matches = MatchSession.query.join(Team).filter(
        Team.club_id == user.club_id
    ).order_by(
        MatchSession.date.desc()
    ).all()

    result = []

    for match in matches:
        team = match.team
        category = team.category if team else None

        result.append({
            **match.serialize(),
            "team_id": team.id if team else None,
            "team_name": team.name if team else None,
            "category_id": category.id if category else None,
            "category_name": category.name if category else None,
        })

    return jsonify({
        "matches": result
    }), 200

@api.route("/matches/<string:match_id>", methods=["GET"])
@jwt_required()
def get_match_detail(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    return jsonify({
        "match": match.serialize()
    }), 200

@api.route("/matches/<string:match_id>/roster", methods=["GET"])
@jwt_required()
def get_match_roster(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    synced_count = sync_match_roster_if_open(match)

    roster = MatchPlayer.query.filter_by(
        match_id=match.id
    ).order_by(MatchPlayer.player_number).all()

    players = []

    for row in roster:
        if not row.player:
            continue

        players.append({
            "match_player_id": row.id,
            "player_id": row.player.id,
            "first_name": row.player.first_name,
            "last_name": row.player.last_name,
            "player_number": row.player_number,
            "attendance_status": row.attendance_status,
            "did_play": row.did_play,
            "is_called": row.is_called,
            "is_on_court": row.is_on_court,
            "main_position": row.player.main_position,
            "position": row.position or row.player.main_position,
        })

    return jsonify({
        "players": players,
        "synced_count": synced_count
    }), 200

@api.route("/matches/<string:match_id>/starting-lineup", methods=["PUT"])
@jwt_required()
def save_starting_lineup(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response(
            "Debes seleccionar las jugadoras iniciales",
            "STARTING_LINEUP_REQUIRED",
            400
        )

    if len(players) != 6:
        return error_response(
            "Debes seleccionar exactamente 6 jugadoras en cancha",
            "STARTING_LINEUP_MUST_HAVE_6",
            400
        )

    selected_ids = set(players)

    rows = MatchPlayer.query.filter_by(match_id=match.id).all()

    valid_rows = []

    for row in rows:
        if row.id in selected_ids:
            valid_rows.append(row)

    if len(valid_rows) != 6:
        return error_response(
            "Una o más jugadoras no pertenecen a este partido",
            "INVALID_STARTING_LINEUP",
            400
        )

    for row in valid_rows:
        if not row.is_called:
            return error_response(
                "Todas las jugadoras iniciales deben estar convocadas",
                "PLAYER_NOT_CALLED",
                400
            )

        if row.attendance_status not in PLAYABLE_MATCH_STATUSES:
            return error_response(
                "Todas las jugadoras iniciales deben estar presentes o tarde",
                "PLAYER_NOT_ELIGIBLE_FOR_LINEUP",
                400
            )

    for row in rows:
        row.is_on_court = row.id in selected_ids

        if row.is_on_court:
            row.did_play = True
            row.position = row.position or row.player.main_position

    match.match_step = max(match.match_step, 3)

    db.session.commit()

    return jsonify({
        "message": "Alineación inicial guardada correctamente",
        "players": [row.serialize() for row in rows]
    }), 200

@api.route("/matches/<string:match_id>/substitutions", methods=["POST"])
@jwt_required()
def create_match_substitution(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}

    player_out_id = body.get("player_out_id")
    player_in_id = body.get("player_in_id")

    try:
        set_number = int(body.get("set_number", 1))
    except (TypeError, ValueError):
        return error_response(
            "Set inválido",
            "INVALID_SET_NUMBER",
            400
        )

    if set_number < 1 or set_number > 5:
        return error_response(
            "El set debe estar entre 1 y 5",
            "INVALID_SET_NUMBER",
            400
        )

    if not player_out_id or not player_in_id:
        return error_response(
            "Debes indicar quién sale y quién entra",
            "SUBSTITUTION_PLAYERS_REQUIRED",
            400
        )

    if player_out_id == player_in_id:
        return error_response(
            "La jugadora que entra no puede ser la misma que sale",
            "INVALID_SUBSTITUTION",
            400
        )

    player_out = MatchPlayer.query.get(player_out_id)
    player_in = MatchPlayer.query.get(player_in_id)

    if not player_out or not player_in:
        return error_response(
            "Jugadora no encontrada en el partido",
            "MATCH_PLAYER_NOT_FOUND",
            404
        )

    if player_out.match_id != match.id or player_in.match_id != match.id:
        return error_response(
            "Las jugadoras no pertenecen a este partido",
            "MATCH_PLAYER_INVALID",
            400
        )

    if not player_out.is_called or not player_in.is_called:
        return error_response(
            "Ambas jugadoras deben estar convocadas",
            "PLAYER_NOT_CALLED",
            400
        )

    if player_out.attendance_status not in PLAYABLE_MATCH_STATUSES:
        return error_response(
            "La jugadora que sale no está disponible para jugar",
            "PLAYER_OUT_NOT_ELIGIBLE",
            400
        )

    if not player_out.is_on_court:
        return error_response(
            "La jugadora que sale debe estar en cancha",
            "PLAYER_OUT_NOT_ON_COURT",
            400
        )

    if player_in.is_on_court:
        return error_response(
            "La jugadora que entra ya está en cancha",
            "PLAYER_IN_ALREADY_ON_COURT",
            400
        )

    if not player_in.is_called:
        return error_response(
            "La jugadora que entra debe estar convocada",
            "PLAYER_NOT_CALLED",
            400
        )

    if player_in.attendance_status not in PLAYABLE_MATCH_STATUSES:
        return error_response(
            "La jugadora que entra debe estar presente o haber llegado tarde",
            "PLAYER_NOT_ELIGIBLE_FOR_SUBSTITUTION",
            400
        )

    substitution = MatchSubstitution(
        match_id=match.id,
        set_number=set_number,
        player_out_id=player_out.id,
        player_in_id=player_in.id
    )

    player_out.is_on_court = False
    player_in.is_on_court = True
    player_in.did_play = True

    match.match_step = max(match.match_step, 3)
    
    db.session.add(substitution)
    db.session.commit()

    return jsonify({
        "message": "Cambio registrado correctamente",
        "substitution": substitution.serialize()
    }), 201

@api.route("/matches/<string:match_id>/roster/participation", methods=["PUT"])
@jwt_required()
def update_match_participation(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    body = request.get_json() or {}
    players = body.get("players")

    if not players:
        return error_response(
            "Lista requerida",
            "MATCH_PARTICIPATION_REQUIRED",
            400
        )

    for item in players:
        match_player_id = item.get("match_player_id")

        if not match_player_id:
            return error_response(
                "Registro del partido requerido",
                "MATCH_PLAYER_ID_REQUIRED",
                400
            )

        row = MatchPlayer.query.get(match_player_id)

        if not row:
            return error_response(
                "Registro del partido no encontrado",
                "MATCH_PLAYER_NOT_FOUND",
                404
            )

        if row.match_id != match.id:
            return error_response(
                "La jugadora no pertenece a este partido",
                "MATCH_PLAYER_INVALID",
                400
            )

        if not row.is_called:
            return error_response(
                "La jugadora no está convocada para este partido",
                "PLAYER_NOT_CALLED",
                400
            )

        if row.attendance_status not in PLAYABLE_MATCH_STATUSES:
            return error_response(
                "La jugadora no puede marcar participación con ese estado",
                "PLAYER_NOT_ELIGIBLE_FOR_PARTICIPATION",
                400
            )

        did_play = bool(item.get("did_play", False))
        position = (item.get("position") or row.player.main_position or "").strip().lower()

        if did_play and not position:
            return error_response(
                "La posición es obligatoria si la jugadora participó",
                "POSITION_REQUIRED",
                400
            )

        if position and position not in ALLOWED_POSITIONS:
            return error_response(
                "Posición inválida",
                "INVALID_POSITION",
                400
            )

        row.did_play = did_play
        row.position = position if did_play else None

    match.match_step = max(match.match_step, 3)

    db.session.commit()

    return jsonify({
        "message": "Participación guardada"
    }), 200

@api.route("/match-players/<string:match_player_id>/stats", methods=["POST"])
@jwt_required()
def save_match_stats(match_player_id):
    user = get_current_user()

    row = MatchPlayer.query.get(match_player_id)

    if not row:
        return error_response(
            "Registro del partido no encontrado",
            "MATCH_PLAYER_NOT_FOUND",
            404
        )

    if row.match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    if (
        not row.is_called or
        row.attendance_status not in PLAYABLE_MATCH_STATUSES or
        not row.did_play
    ):
        return error_response(
            "La jugadora no puede registrar stats",
            "PLAYER_NOT_ELIGIBLE_FOR_STATS",
            400
        )

    body = request.get_json() or {}

    validated_stats, error = validate_match_stats(body)

    if error:
        return error_response(
            "Datos inválidos en estadísticas",
            error,
            400
        )

    stat = PlayerMatchStat.query.filter_by(
        match_player_id=row.id
    ).first()

    if not stat:
        stat = PlayerMatchStat(match_player_id=row.id)
        db.session.add(stat)

    new_position = validated_stats.get("position")

    if new_position:
        row.position = new_position
    elif not row.position:
        row.position = row.player.main_position

    stat.attacks_total = validated_stats.get("attacks_total")
    stat.attacks_positive = validated_stats.get("attacks_positive")
    stat.attacks_neutral = validated_stats.get("attacks_neutral")
    stat.attacks_errors = validated_stats.get("attacks_errors")

    stat.receptions_total = validated_stats.get("receptions_total")
    stat.receptions_positive = validated_stats.get("receptions_positive")
    stat.receptions_neutral = validated_stats.get("receptions_neutral")
    stat.receptions_negative = validated_stats.get("receptions_negative")

    stat.defenses_total = validated_stats.get("defenses_total")
    stat.defenses_positive = validated_stats.get("defenses_positive")
    stat.defenses_neutral = validated_stats.get("defenses_neutral")
    stat.defenses_negative = validated_stats.get("defenses_negative")

    stat.sets_total = validated_stats.get("sets_total")
    stat.sets_positive = validated_stats.get("sets_positive")
    stat.sets_neutral = validated_stats.get("sets_neutral")
    stat.sets_errors = validated_stats.get("sets_errors")

    stat.serves_total = validated_stats.get("serves_total")
    stat.serves_in = validated_stats.get("serves_in")
    stat.serves_aces = validated_stats.get("serves_aces")
    stat.serves_errors = validated_stats.get("serves_errors")

    stat.blocks_total = validated_stats.get("blocks_total")
    stat.blocks_points = validated_stats.get("blocks_points")
    stat.blocks_neutral = validated_stats.get("blocks_neutral")
    stat.blocks_errors = validated_stats.get("blocks_errors")
    

    row.match.match_step = max(row.match.match_step, 4)
   

    db.session.commit()

    return jsonify({
        "message": "Stats guardadas correctamente",
        "stats": stat.serialize()
    }), 200

@api.route("/match-players/<string:match_player_id>/stats", methods=["GET"])
@jwt_required()
def get_match_stats(match_player_id):
    user = get_current_user()

    row = MatchPlayer.query.get(match_player_id)

    if not row:
        return error_response(
            "Registro del partido no encontrado",
            "MATCH_PLAYER_NOT_FOUND",
            404
        )

    if row.match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    stats = PlayerMatchStat.query.filter_by(
        match_player_id=row.id
    ).first()

    team = row.match.team
    player = row.player
    match = row.match

    return jsonify({
        "context": {
            "player": {
                "id": player.id,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "player_number": row.player_number,
                "sex": player.sex,
                "main_position": player.main_position,
            },
            "team": {
                "id": team.id,
                "name": team.name,
                "gender": team.gender
            },
            "match": {
                "id": match.id,
                "date": match.date.isoformat() if match.date else None,
                "opponent_name": match.opponent_name,
                "match_type": match.match_type,
                "location": match.location,
                "home_sets": match.home_sets,
                "opponent_sets": match.opponent_sets,
                "result": match.result,
                "is_completed": match.is_completed
            },
            "match_player": {
                "id": row.id,
                "is_called": row.is_called,
                "attendance_status": row.attendance_status,
                "did_play": row.did_play,
                "position": row.position or player.main_position
                
            }
        },
        "stats": stats.serialize() if stats else None
    }), 200

@api.route("/matches/<string:match_id>/result", methods=["PUT"])
@jwt_required()
def update_match_result(match_id):
    user = get_current_user()

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response("No tienes acceso", "FORBIDDEN", 403)

    body = request.get_json() or {}

    try:
        home_sets = int(body.get("home_sets", 0))
        opponent_sets = int(body.get("opponent_sets", 0))
    except (TypeError, ValueError):
        return error_response(
            "Los sets deben ser números enteros",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ VALIDACIÓN DE NEGATIVOS
    if home_sets < 0 or opponent_sets < 0:
        return error_response(
            "Los sets no pueden ser negativos",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ NADIE PUEDE PASAR DE 3
    if home_sets > 3 or opponent_sets > 3:
        return error_response(
            "Ningún equipo puede superar 3 sets",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ NO HAY EMPATE
    if home_sets == opponent_sets:
        return error_response(
            "No puede haber empate en sets",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ EL GANADOR DEBE TENER 3
    if max(home_sets, opponent_sets) != 3:
        return error_response(
            "Uno de los equipos debe ganar 3 sets",
            "INVALID_MATCH_RESULT",
            400
        )

    # ✅ EL PERDEDOR SOLO PUEDE TENER 0,1,2
    if min(home_sets, opponent_sets) > 2:
        return error_response(
            "El equipo perdedor no puede superar 2 sets",
            "INVALID_MATCH_RESULT",
            400
        )

    match.home_sets = home_sets
    match.opponent_sets = opponent_sets
    match.result = "win" if home_sets > opponent_sets else "loss"

    if max(home_sets, opponent_sets) == 3:
        match.is_completed = True

    db.session.commit()

    return jsonify({
        "message": "Resultado guardado",
        "match": match.serialize()
    }), 200

############################################ MATCH EVENTS #############################################


VALID_EVENT_ACTIONS = [
    "attack", "reception", "serve",
    "block", "set", "defense"
]

VALID_EVENT_RESULTS_BY_ACTION = {
    "attack": ["positive", "neutral", "error"],
    "reception": ["positive", "neutral", "negative"],
    "defense": ["positive", "neutral", "negative"],
    "set": ["positive", "neutral", "error"],
    "serve": ["in", "ace", "error"],
    "block": ["point", "neutral", "error"],
}


@api.route("/match-events", methods=["POST"])
@jwt_required()
def create_match_event():
    user = get_current_user()
    body = request.get_json() or {}

    match_id = body.get("match_id")
    match_player_id = body.get("match_player_id")
    action = body.get("action_type")
    result = body.get("result")

    try:
        set_number = int(body.get("set_number", 1))
    except (TypeError, ValueError):
        return error_response(
            "Set inválido",
            "INVALID_SET_NUMBER",
            400
        )

    if set_number < 1 or set_number > 5:
        return error_response(
            "El set debe estar entre 1 y 5",
            "INVALID_SET_NUMBER",
            400
        )

    
    if not match_id or not match_player_id:
        return error_response(
            "Datos incompletos",
            "MATCH_EVENT_REQUIRED",
            400
        )

    if action not in VALID_EVENT_ACTIONS:
        return error_response(
            "Acción inválida",
            "INVALID_EVENT_ACTION",
            400
        )

    allowed_results = VALID_EVENT_RESULTS_BY_ACTION.get(action, [])

    if result not in allowed_results:
        return error_response(
            "Resultado inválido para esta acción",
            "INVALID_EVENT_RESULT",
            400
        )

    match = MatchSession.query.get(match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    # 🔒 Validar que el match_player pertenece a ese match
    match_player = MatchPlayer.query.get(match_player_id)

    if not match_player or match_player.match_id != match.id:
        return error_response(
            "Registro inválido",
            "MATCH_PLAYER_INVALID",
            400
        )

    if (
        not match_player.is_called or
        match_player.attendance_status not in PLAYABLE_MATCH_STATUSES or
        not match_player.is_on_court
    ):
        return error_response(
            "Solo puedes registrar acciones a jugadoras en cancha",
            "PLAYER_NOT_ON_COURT",
            400
        )
    
    match_player.did_play = True
    match_player.position = match_player.position or match_player.player.main_position
    
    event = MatchEvent(
        match_id=match_id,
        match_player_id=match_player_id,
        action_type=action,
        result=result,
        set_number=set_number
    )

    db.session.add(event)
    db.session.flush()

    recalculate_player_match_stats(match_player_id)

    db.session.commit()

    return jsonify({
        "message": "Evento registrado correctamente",
        "event": event.serialize()
    }), 201

@api.route("/match-events/<string:event_id>", methods=["DELETE"])
@jwt_required()
def delete_match_event(event_id):
    user = get_current_user()

    event = MatchEvent.query.get(event_id)

    if not event:
        return error_response(
            "Evento no encontrado",
            "MATCH_EVENT_NOT_FOUND",
            404
        )

    match = MatchSession.query.get(event.match_id)

    if not match:
        return error_response(
            "Partido no encontrado",
            "MATCH_NOT_FOUND",
            404
        )

    if match.team.club_id != user.club_id:
        return error_response(
            "No tienes acceso",
            "FORBIDDEN",
            403
        )

    match_player_id = event.match_player_id

    db.session.delete(event)
    db.session.flush()

    recalculate_player_match_stats(match_player_id)

    db.session.commit()

    return jsonify({
        "message": "Evento eliminado correctamente"
    }), 200