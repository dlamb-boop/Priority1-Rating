"""Customer PDF branded from the EasyPost sales deck. Sell prices only."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from freight.customer import customer_pdf_filename, prepared_by_line

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "easypost-logo.png"
FONTS = ROOT / "assets" / "fonts"

NAVY = HexColor("#061242")
BLUE = HexColor("#164DFF")
WASH = HexColor("#E8EDFF")
BAND = HexColor("#D0DAFE")
MINT = HexColor("#CBF9EE")
INK = HexColor("#061242")
MUTED = HexColor("#3C4A78")
LINE = HexColor("#D0DAFE")

# Baseline-to-baseline lead before a section title, matching the air between
# the shipment summary and the line-item table.
SECTION_LEAD = 28
# Extra room between a card's last charge and its transit line.
TIMING_GAP = 8

_FONTS_READY = False


def _fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    pdfmetrics.registerFont(TTFont("Poppins", str(FONTS / "Poppins-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Poppins-Medium", str(FONTS / "Poppins-Medium.ttf")))
    pdfmetrics.registerFont(TTFont("Poppins-SemiBold", str(FONTS / "Poppins-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont("Poppins-Bold", str(FONTS / "Poppins-Bold.ttf")))
    _FONTS_READY = True


def _long_date_safe(value: str | None) -> str:
    if not value or len(value) < 10:
        return "—"
    from datetime import datetime

    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return value
    return f"{parsed.strftime('%a')}, {parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def _money(amount: float, currency: str = "USD") -> str:
    symbol = "$" if currency in {"USD", ""} else f"{currency} "
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def _transit(days: int | None) -> str:
    if days is None:
        return "—"
    return "1 day" if days == 1 else f"{days} days"


def render_customer_pdf(document: dict) -> bytes:
    _fonts()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    _draw_document(pdf, document, width, height)
    pdf.save()
    return _rewrite_metadata(buffer.getvalue(), document)


def _rewrite_metadata(raw: bytes, document: dict) -> bytes:
    name = (document.get("preparer_name") or "").strip()
    author = f"{name}, EasyPost" if name else "EasyPost"
    reader = PdfReader(BytesIO(raw))
    writer = PdfWriter()
    writer.append(reader)
    writer.add_metadata(
        {
            "/Title": "EasyPost Freight Quote",
            "/Author": author,
            "/Subject": "Customer freight quote",
            "/Keywords": "EasyPost, freight quote",
            "/Creator": "EasyPost Freight Quotes",
            "/Producer": "EasyPost",
        }
    )
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _header(pdf: canvas.Canvas, document: dict, width: float, height: float, continued: bool) -> None:
    band_h = 64 if continued else 86
    pdf.setFillColor(WASH)
    pdf.rect(0, height - band_h, width, band_h, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.rect(0, height - band_h - 4, width, 4, fill=1, stroke=0)
    logo_w = 132
    logo_h = logo_w * 370 / 1600
    pdf.drawImage(ImageReader(str(LOGO)), 40, height - 18 - logo_h, logo_w, logo_h, mask="auto", preserveAspectRatio=True)
    pdf.setFillColor(NAVY)
    pdf.setFont("Poppins-Bold", 13 if continued else 18)
    pdf.drawRightString(width - 40, height - (30 if continued else 38), "Freight quote")
    pdf.setFont("Poppins", 8)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(width - 40, height - (46 if continued else 56), document["reference"])
    if not continued:
        pdf.drawRightString(width - 40, height - 70, f"Valid through {_long_date_safe(document['valid_through'])}")


def _wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if pdfmetrics.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _footer(pdf: canvas.Canvas, document: dict, width: float) -> None:
    prepared = document.get("prepared_by") or prepared_by_line()
    prepared_lines = _wrap(prepared, "Poppins", 7.5, width - 80)
    note = "Estimate only. This is not a tender. The rate can change if the shipment differs from the details above."
    if document.get("mention_capacity_partner"):
        note += " Capacity sourced through Priority1."
    note_lines = _wrap(note, "Poppins", 7, width - 80)
    rule_y = 16 + len(note_lines) * 10 + 4 + len(prepared_lines) * 11 + 14
    pdf.setFillColor(BLUE)
    pdf.rect(40, rule_y, width - 80, 2, fill=1, stroke=0)
    pdf.setFillColor(NAVY)
    pdf.setFont("Poppins", 7.5)
    cursor = rule_y - 14
    for line in prepared_lines:
        pdf.drawString(40, cursor, line)
        cursor -= 11
    pdf.setFillColor(MUTED)
    pdf.setFont("Poppins", 7)
    cursor -= 4
    for line in note_lines:
        pdf.drawString(40, cursor, line)
        cursor -= 10


def _draw_document(pdf: canvas.Canvas, document: dict, width: float, height: float) -> None:
    def new_page(continued: bool) -> float:
        if continued:
            pdf.showPage()
        _header(pdf, document, width, height, continued)
        _footer(pdf, document, width)
        return height - (108 if continued else 118)

    y = new_page(False)
    prepared = [document.get("customer_name"), document.get("company")]
    prepared = [part for part in prepared if part]
    pdf.setFillColor(BLUE)
    pdf.setFont("Poppins-SemiBold", 8)
    pdf.drawString(40, y, "PREPARED FOR")
    pdf.setFillColor(NAVY)
    pdf.setFont("Poppins-Bold", 13)
    if not prepared:
        pdf.drawString(40, y - 18, "Prospective customer")
        y -= 18
    else:
        pdf.drawString(40, y - 18, prepared[0])
        y -= 18
        if len(prepared) > 1:
            pdf.setFont("Poppins", 11)
            pdf.drawString(40, y - 16, prepared[1])
            y -= 16

    y = _section(pdf, "Shipment", y)
    box_top = y
    pdf.setFillColor(WASH)
    pdf.roundRect(40, box_top - 72, width - 80, 72, 8, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.setFont("Poppins-SemiBold", 7)
    pdf.drawString(54, box_top - 16, "ORIGIN")
    pdf.drawString(310, box_top - 16, "DESTINATION")
    pdf.setFillColor(NAVY)
    pdf.setFont("Poppins-SemiBold", 11)
    pdf.drawString(54, box_top - 34, document["shipment"]["origin_label"])
    pdf.drawString(310, box_top - 34, document["shipment"]["destination_label"])
    facts = [f"Pickup {_long_date_safe(document['shipment']['pickup_date'])}"]
    if document["shipment"].get("total_weight") is not None:
        facts.append(f"{document['shipment']['total_weight']:,.0f} lb")
    if document["shipment"].get("distance_miles") is not None:
        facts.append(f"{document['shipment']['distance_miles']:,.0f} miles")
    pdf.setFillColor(MUTED)
    pdf.setFont("Poppins", 8)
    pdf.drawString(54, box_top - 56, "   ·   ".join(facts))
    y = box_top - 88

    items = document["shipment"]["items"]
    if items:
        y = _table_header(pdf, y, width)
        for index, item in enumerate(items):
            if y < 130:
                y = new_page(True)
                y = _table_header(pdf, y, width)
            if index % 2 == 0:
                pdf.setFillColor(HexColor("#F7F8FF"))
                pdf.rect(40, y - 16, width - 80, 20, fill=1, stroke=0)
            notes = [item.get("description"), "Hazmat" if item.get("is_hazardous") else None, "Stackable" if item.get("is_stackable") else None]
            dims = "—"
            if item["length"] and item["width"] and item["height"]:
                dims = f"{_num(item['length'])} × {_num(item['width'])} × {_num(item['height'])} in"
            cells = [
                (item["freight_class"], 48),
                (item["packaging_type"], 100),
                (str(item["units"]), 190),
                (f"{item['total_weight']:,.0f} lb", 240),
                (dims, 310),
                (", ".join(part for part in notes if part) or "—", 430),
            ]
            pdf.setFillColor(NAVY)
            pdf.setFont("Poppins", 8)
            for text, x in cells:
                pdf.drawString(x, y - 10, str(text)[:28])
            y -= 20
        y -= 8

    if document["shipment"]["accessorials"]:
        pdf.setFillColor(MUTED)
        pdf.setFont("Poppins", 8)
        pdf.drawString(40, y, "Accessorials")
        pdf.setFillColor(NAVY)
        pdf.setFont("Poppins", 9)
        pdf.drawString(40, y - 14, "  ·  ".join(document["shipment"]["accessorials"]))
        y -= 14

    y = _section(pdf, "Carrier options", y)
    for index, option in enumerate(document["options"]):
        block = _card_height(len(option["charges"])) + 10
        if y - block < 96:
            y = new_page(True)
            y = _section(pdf, "Carrier options", y, lead=8)
        y = _option(pdf, option, index, y, width)


def _num(value: float) -> str:
    return f"{value:g}"


def _section(pdf: canvas.Canvas, title: str, y: float, *, lead: float = SECTION_LEAD) -> float:
    y -= lead
    pdf.setFillColor(BLUE)
    pdf.setFont("Poppins-SemiBold", 11)
    pdf.drawString(40, y, title)
    return y - 18


def _card_height(rows: int) -> float:
    timing_gap = TIMING_GAP if rows else 0
    return 62 + rows * 14 + (8 if rows else 0) + timing_gap


def _table_header(pdf: canvas.Canvas, y: float, width: float) -> float:
    pdf.setFillColor(MINT)
    pdf.rect(40, y - 14, width - 80, 18, fill=1, stroke=0)
    pdf.setFillColor(NAVY)
    pdf.setFont("Poppins-SemiBold", 7)
    for label, x in [("Class", 48), ("Packaging", 100), ("Units", 190), ("Weight", 240), ("Dimensions", 310), ("Notes", 430)]:
        pdf.drawString(x, y - 9, label)
    return y - 18


def _option(pdf: canvas.Canvas, option: dict, index: int, y: float, width: float) -> float:
    rows = len(option["charges"])
    timing_gap = TIMING_GAP if rows else 0
    height = _card_height(rows)
    pdf.setStrokeColor(BAND)
    pdf.setLineWidth(1)
    pdf.setFillColor(white)
    pdf.roundRect(40, y - height, width - 80, height, 8, fill=1, stroke=1)
    pdf.setFillColor(BLUE)
    pdf.setFont("Poppins-SemiBold", 7)
    pdf.drawString(54, y - 14, f"OPTION {index + 1}")
    pdf.setFillColor(NAVY)
    pdf.setFont("Poppins-SemiBold", 12)
    pdf.drawString(54, y - 32, option["carrier_name"])
    meta = "  ·  ".join(
        part
        for part in (
            option.get("scac") or None,
            option.get("service_level"),
            option.get("lane_type").title() if option.get("lane_type") else None,
        )
        if part
    )
    pdf.setFillColor(MUTED)
    pdf.setFont("Poppins", 8)
    pdf.drawString(54, y - 46, meta)
    pdf.setFillColor(BLUE)
    pdf.setFont("Poppins-Bold", 14)
    pdf.drawRightString(width - 54, y - 32, _money(option["price"], option.get("currency") or "USD"))
    cursor = y - 62
    for charge in option["charges"]:
        pdf.setFillColor(NAVY)
        pdf.setFont("Poppins", 8)
        pdf.drawString(54, cursor, charge["description"])
        pdf.drawRightString(width - 54, cursor, _money(charge["amount"], option.get("currency") or "USD"))
        cursor -= 14
    timing = "   ·   ".join(
        part
        for part in (
            _transit(option.get("transit_days")),
            f"Delivers {_long_date_safe(option.get('delivery_date'))}" if option.get("delivery_date") else None,
            f"Expires {_long_date_safe(option.get('expiration_date'))}" if option.get("expiration_date") else None,
        )
        if part
    )
    pdf.setFillColor(MUTED)
    pdf.setFont("Poppins", 7.5)
    pdf.drawString(54, (cursor + 4 - timing_gap) if option["charges"] else y - 58, timing)
    return y - height - 10


def filename_for(document: dict) -> str:
    return customer_pdf_filename(document["quote_date"])
