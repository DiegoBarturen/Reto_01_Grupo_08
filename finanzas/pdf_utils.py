from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _draw_brand(pdf, page_width, page_height, subtitle):
    pdf.setFillColor(colors.HexColor("#ff7a1a"))
    pdf.roundRect(22 * mm, page_height - 32 * mm, 18 * mm, 18 * mm, 4 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(31 * mm, page_height - 20.6 * mm, "FB")

    pdf.setFillColor(colors.HexColor("#132033"))
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(46 * mm, page_height - 20 * mm, "FairBet Lab")
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#56657a"))
    pdf.drawString(46 * mm, page_height - 25.4 * mm, subtitle)


def _draw_footer(pdf, page_width):
    pdf.setStrokeColor(colors.HexColor("#dde4ee"))
    pdf.line(20 * mm, 15 * mm, page_width - 20 * mm, 15 * mm)
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(colors.HexColor("#6f7d90"))
    pdf.drawString(20 * mm, 10.5 * mm, "Plataforma educativa con moneda virtual. No constituye una casa de apuestas.")


def _split_text(text, length):
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= length:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_detail_card(pdf, transaccion, billetera, page_width, page_height, y_start, title):
    left = 20 * mm
    width = page_width - (40 * mm)
    pdf.setFillColor(colors.HexColor("#f7f9fc"))
    pdf.roundRect(left, y_start - 82 * mm, width, 74 * mm, 6 * mm, fill=1, stroke=0)

    pdf.setFillColor(colors.HexColor("#132033"))
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left + 8 * mm, y_start - 16 * mm, title)
    pdf.setFont("Helvetica", 10.5)
    pdf.setFillColor(colors.HexColor("#56657a"))
    pdf.drawString(left + 8 * mm, y_start - 22 * mm, f"Movimiento #{transaccion.id}")

    rows = [
        ("Operacion", transaccion.get_tipo_display()),
        ("Metodo", transaccion.get_metodo_display()),
        ("Monto", f"S/ {transaccion.monto}"),
        ("Fecha", transaccion.creado_en.strftime("%d/%m/%Y %H:%M")),
        ("Saldo actual", f"S/ {billetera.saldo}"),
    ]
    label_x = left + 8 * mm
    value_x = left + 52 * mm
    base_y = y_start - 34 * mm

    for index, (label, value) in enumerate(rows):
        current_y = base_y - (index * 8 * mm)
        pdf.setFont("Helvetica-Bold", 10.5)
        pdf.setFillColor(colors.HexColor("#394a5f"))
        pdf.drawString(label_x, current_y, label)
        pdf.setFont("Helvetica", 10.5)
        pdf.setFillColor(colors.HexColor("#132033"))
        pdf.drawString(value_x, current_y, value)

    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.setFillColor(colors.HexColor("#394a5f"))
    pdf.drawString(label_x, y_start - 74 * mm, "Descripcion")
    pdf.setFont("Helvetica", 10.2)
    pdf.setFillColor(colors.HexColor("#132033"))
    text = pdf.beginText()
    text.setTextOrigin(value_x, y_start - 74 * mm)
    text.setLeading(14)
    for line in _split_text(transaccion.descripcion or "Sin descripcion adicional.", 68):
        text.textLine(line)
    pdf.drawText(text)


def generar_pdf_movimiento(transaccion, billetera):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    _draw_brand(pdf, page_width, page_height, "Comprobante de movimiento")
    _draw_detail_card(pdf, transaccion, billetera, page_width, page_height, page_height - 38 * mm, "Detalle del movimiento")
    _draw_footer(pdf, page_width)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def generar_pdf_movimientos(transacciones, billetera):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    for index, transaccion in enumerate(transacciones, start=1):
        _draw_brand(pdf, page_width, page_height, "Resumen de movimientos")
        _draw_detail_card(
            pdf,
            transaccion,
            billetera,
            page_width,
            page_height,
            page_height - 38 * mm,
            f"Movimiento {index} de {len(transacciones)}",
        )
        _draw_footer(pdf, page_width)
        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer
