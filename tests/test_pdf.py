import json
import os

from pypdf import PdfReader
from io import BytesIO

from freight.customer import build_customer_quote
from freight.pdf_quote import filename_for, render_customer_pdf
from freight.quote import quote_ltl

os.environ["P1_API_KEY"] = ""
os.environ["P1_MOCK"] = "true"

SHIPMENT = {
    "origin_zip_code": "72205",
    "origin_city": "Little Rock",
    "origin_state": "AR",
    "destination_zip_code": "60606",
    "destination_city": "Chicago",
    "destination_state": "IL",
    "pickup_date": "2026-10-20",
    "distance_miles": 644,
    "total_weight": 275,
    "items": [
        {
            "freight_class": "150",
            "packaging_type": "Pallet",
            "units": 1,
            "pieces": 1,
            "total_weight": 275,
            "length": 48,
            "width": 40,
            "height": 40,
            "description": "Hardware",
            "is_hazardous": False,
            "is_stackable": False,
        }
    ],
    "accessorials": [{"code": "LGPU", "description": "Lift Gate Pickup"}],
}


def pdf_text(data: bytes) -> dict:
    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    info = {key: str(value) for key, value in (reader.metadata or {}).items()}
    return {"text": "\n".join(pages), "pages": pages, "info": info}


def test_pdf_shows_sell_price_and_hides_buy_rate():
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "preparer_name": "Priya Shah",
            "preparer_title": "Logistics Manager",
            "preparer_email": "priya@easypost.com",
            "show_priority1": False,
            "shipment": SHIPMENT,
            "options": [
                {
                    "carrier_name": "Southeastern Freight",
                    "scac": "SEFL",
                    "service_level": "STANDARD",
                    "service_level_description": "Standard",
                    "lane_type": "DIRECT",
                    "transit_days": 4,
                    "delivery_date": "2026-10-23T16:00:00",
                    "expiration_date": "2026-10-26T16:00:00",
                    "customer_total": 252.4,
                    "currency": "USD",
                    "charges": [
                        {"code": "FSC", "description": "Fuel Surcharge", "amount": 42.22},
                        {"code": "GFC", "description": "Gross Freight Charge", "amount": 210.18},
                    ],
                    "internal": {
                        "base_total": 235.89,
                        "carrier_base_cost": 196.43,
                        "markup_percent": 7,
                        "markup_amount": 16.51,
                        "margin_percent": 6.54,
                        "carrier_quote_number": "Q1234",
                    },
                    "id": 21108,
                    "base_cost": 235.89,
                    "carrier_quote_number": "Q1234",
                }
            ],
        }
    )
    parsed = pdf_text(render_customer_pdf(document))
    haystack = f"{parsed['text']}\n{json.dumps(parsed['info'])}".lower()
    assert "Alex Chen" in parsed["text"]
    assert "Northwind Goods" in parsed["text"]
    assert "Southeastern Freight" in parsed["text"]
    assert "SEFL" in parsed["text"]
    assert "$252.40" in parsed["text"]
    assert "Prepared by Priya Shah, Logistics Manager, EasyPost · priya@easypost.com" in parsed["text"]
    assert "dawson" not in haystack
    for page in parsed["pages"]:
        assert "Priya Shah" in page
    for token in ["markup", "base cost", "basecost", "margin", "235.89", "196.43", "16.51", "21108", "q1234", "priority1"]:
        assert token not in haystack
    assert parsed["info"].get("/Title") == "EasyPost Freight Quote"
    assert parsed["info"].get("/Author") == "Priya Shah, EasyPost"
    assert filename_for(document) == "EasyPost-Freight-Quote-2026-10-19.pdf"


def test_pdf_mentions_capacity_partner_only_when_asked():
    quote = quote_ltl(
        {
            "markup_percent": 10,
            "origin_zip_code": "90221",
            "origin_city": "Los Angeles",
            "origin_state_abbreviation": "CA",
            "destination_zip_code": "72205",
            "destination_city": "Little Rock",
            "destination_state_abbreviation": "AR",
            "pickup_date": "2026-10-21",
            "items": [
                {
                    "freight_class": "70",
                    "packaging_type": "Pallet",
                    "units": 2,
                    "total_weight": 800,
                    "length": 48,
                    "width": 40,
                    "height": 40,
                }
            ],
        }
    )
    hidden = build_customer_quote(
        {"company": "Northwind Goods", "quote_date": "2026-10-19", "shipment": quote["shipment"], "options": [quote["rates"][0]]}
    )
    shown = build_customer_quote(
        {
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "show_priority1": True,
            "shipment": quote["shipment"],
            "options": [quote["rates"][0]],
        }
    )
    hidden_text = pdf_text(render_customer_pdf(hidden))["text"]
    shown_text = pdf_text(render_customer_pdf(shown))["text"]
    assert "priority1" not in hidden_text.lower()
    assert "Priority1" in shown_text
    assert f"{quote['rates'][0]['internal']['base_total']:.2f}" not in hidden_text
    assert "Northwind Goods" in hidden_text


def _baselines(data: bytes) -> list[tuple[str, float]]:
    reader = PdfReader(BytesIO(data))
    found: list[tuple[str, float]] = []

    def visitor(text, _cm, tm, _font, _size):
        if text and text.strip():
            found.append((text, tm[5]))

    reader.pages[0].extract_text(visitor_text=visitor)
    return found


def _baseline(rows: list[tuple[str, float]], needle: str) -> float:
    matches = [y for text, y in rows if needle in text]
    assert matches, needle
    return matches[0]


def test_pdf_section_and_card_spacing():
    quote = quote_ltl(
        {
            "markup_percent": 7,
            "origin_zip_code": "72205",
            "origin_city": "Little Rock",
            "origin_state_abbreviation": "AR",
            "destination_zip_code": "60606",
            "destination_city": "Chicago",
            "destination_state_abbreviation": "IL",
            "pickup_date": "2026-10-20",
            "accessorial_services": ["LGPU", "APPT"],
            "items": [
                {
                    "freight_class": "70",
                    "packaging_type": "Pallet",
                    "units": 1,
                    "total_weight": 500,
                    "length": 48,
                    "width": 40,
                    "height": 48,
                    "description": "Packaged hardware",
                }
            ],
        }
    )
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "shipment": quote["shipment"],
            "options": quote["rates"],
        }
    )
    rows = _baselines(render_customer_pdf(document))
    # PDF y grows upward, so a lower baseline is further down the page.
    company = _baseline(rows, "Northwind Goods")
    shipment = _baseline(rows, "Shipment")
    accessorials = _baseline(rows, "Lift Gate Pickup")
    options = _baseline(rows, "Carrier options")
    discount = _baseline(rows, "Carrier discount")
    transit = _baseline(rows, "Delivers")
    assert company - shipment >= 24
    assert accessorials - options >= 24
    assert discount - transit >= 14


def test_pdf_prints_address_and_hides_logo_source():
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGBA", (80, 80), (10, 40, 180, 255))
    for x in range(40):
        for y in range(80):
            image.putpixel((x, y), (220, 40, 40, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    # A text chunk would be a way for a source URL to ride along. Re-encoding must drop it.
    dirty = Image.new("RGBA", (80, 80), (10, 40, 180, 255))
    for x in range(40):
        for y in range(80):
            dirty.putpixel((x, y), (220, 40, 40, 255))
    dirty_buffer = BytesIO()
    dirty.save(dirty_buffer, format="PNG")
    dirty_png = dirty_buffer.getvalue() + b"\nhttps://www.google.com/s2/favicons?domain=example.com https://commons.wikimedia.org/wiki/File:Logo.svg https://icons.duckduckgo.com/ip3/example.com.ico"
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind",
            "quote_date": "2026-10-19",
            "shipment": SHIPMENT,
            "address": {
                "street": "100 Main Street",
                "city": "Bentonville",
                "state": "AR",
                "postal": "72712",
                "country": "US",
            },
            "options": [
                {
                    "carrier_name": "Southeastern Freight",
                    "scac": "SEFL",
                    "service_level_description": "Standard",
                    "transit_days": 2,
                    "customer_total": 100,
                    "charges": [],
                }
            ],
        }
    )
    data = render_customer_pdf(document, logo_png=dirty_png)
    extracted = pdf_text(data)
    assert "100 Main Street" in extracted["text"]
    assert "Bentonville, AR 72712" in extracted["text"]
    assert "United States" not in extracted["text"]
    lowered = data.lower()
    metadata = " ".join(extracted["info"].values()).lower()
    for token in (b"http", b"wikidata", b"google.com/s2", b"duckduckgo", b"commons.wikimedia"):
        assert token not in lowered
        assert token.decode() not in metadata
