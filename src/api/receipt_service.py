import os
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from src.api.models import db, ReceiptCounter


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
        "tournament": "Inscripción de torneo",
        "referee": "Arbitraje",
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

