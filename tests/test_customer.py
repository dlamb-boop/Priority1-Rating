import json
import os

import pytest

from freight.customer import (
    assert_customer_safe,
    build_customer_quote,
    customer_pdf_filename,
    prepared_by_line,
    to_customer_rate,
)
from freight.quote import quote_ltl, quote_tl

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
    "linear_feet": 2,
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
    "accessorials": [
        {"code": "LGPU", "description": "Lift Gate Pickup"},
        {"code": "APPT", "description": "Delivery Appointment"},
    ],
}


def _polluted_rate() -> dict:
    return {
        "option_id": "ltl-1-sefl-standard",
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
            "charges": [],
        },
        "id": 21108,
        "quote_id": 21108,
        "rate_id": 21108,
        "base_cost": 196.43,
        "base_total": 235.89,
        "markup_percent": 7,
        "carrier_quote_number": "Q1234",
        "priority1_quote_id": 123456,
    }


def test_prepared_by_line_uses_what_was_entered():
    assert prepared_by_line() == "Prepared by EasyPost"
    assert prepared_by_line("   ", "") == "Prepared by EasyPost"
    assert prepared_by_line("Priya Shah") == "Prepared by Priya Shah, EasyPost"
    assert prepared_by_line("Priya Shah", "Logistics Manager") == "Prepared by Priya Shah, Logistics Manager, EasyPost"
    assert (
        prepared_by_line("Priya Shah", "Logistics Manager", "priya@easypost.com")
        == "Prepared by Priya Shah, Logistics Manager, EasyPost · priya@easypost.com"
    )
    assert prepared_by_line("", "", "") == "Prepared by EasyPost"
    document = build_customer_quote(
        {
            "company": "Northwind Goods",
            "preparer_name": "Priya Shah",
            "preparer_title": "Logistics Manager",
            "shipment": SHIPMENT,
            "options": [_polluted_rate()],
        }
    )
    assert document["prepared_by"] == "Prepared by Priya Shah, Logistics Manager, EasyPost"
    assert "dawson" not in json.dumps(document).lower()


def test_customer_payload_drops_internal_economics():
    rate = _polluted_rate()
    customer = to_customer_rate(rate)
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "show_priority1": False,
            "shipment": SHIPMENT,
            "options": [rate],
        }
    )
    assert_customer_safe(document, ["235.89", "196.43", "16.51", "6.54", "21108", "123456", "Q1234"])
    blob = json.dumps({"customer": customer, "document": document}).lower()
    for token in ["markup", "basecost", "base cost", "margin", "235.89", "196.43", "21108", "123456", "q1234", "priority1"]:
        assert token not in blob
    assert "252.4" in blob
    assert "southeastern freight" in blob
    filename = customer_pdf_filename(document["quote_date"])
    assert filename == "EasyPost-Freight-Quote-2026-10-19.pdf"
    assert "markup" not in filename.lower()
    assert "21108" not in filename


def test_live_mock_quote_customer_projection_hides_buy_rate():
    quote = quote_ltl(
        {
            "markup_percent": 7,
            "origin_zip_code": "72205",
            "destination_zip_code": "60606",
            "pickup_date": "2026-10-20",
            "accessorial_services": ["LGPU"],
            "items": [
                {
                    "freight_class": "70",
                    "packaging_type": "Pallet",
                    "units": 1,
                    "total_weight": 500,
                    "length": 48,
                    "width": 40,
                    "height": 48,
                }
            ],
        }
    )
    bases = [f"{rate['internal']['base_total']:.2f}" for rate in quote["rates"]]
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "shipment": quote["shipment"],
            "options": quote["rates"],
        }
    )
    assert_customer_safe(document, bases)
    raw = json.dumps(quote)
    assert "rateQuoteDetail" not in raw
    assert "424242" not in raw
    assert '"id": 900000' not in raw and '"id":900000' not in raw
    assert quote["rates"][0]["customer_total"] > quote["rates"][0]["internal"]["base_total"]
    totals = [rate["customer_total"] for rate in quote["rates"]]
    assert totals == sorted(totals)


def test_truckload_mock_has_no_scac_and_warns():
    quote = quote_tl(
        {
            "markup_percent": 7,
            "origin_zip_code": "90221",
            "origin_city": "Los Angeles",
            "origin_state": "CA",
            "destination_zip_code": "72205",
            "destination_city": "Little Rock",
            "destination_state": "AR",
            "pickup_date_open": "2026-10-20",
            "equipment": "53_Foot_Dry_Van",
            "weight": 18000,
            "pallet_count": 10,
        }
    )
    assert quote["rates"]
    assert all(rate["scac"] == "" for rate in quote["rates"])
    assert all(rate["carrier_name"].startswith("Truckload option") for rate in quote["rates"])
    assert any("SCAC" in warning for warning in quote["warnings"])
    document = build_customer_quote({"company": "Northwind Goods", "shipment": quote["shipment"], "options": quote["rates"]})
    assert_customer_safe(document, [f"{rate['internal']['base_total']:.2f}" for rate in quote["rates"]])
    assert "priority1" not in json.dumps(document).lower()


def test_truckload_auth_failure_is_friendly(monkeypatch: pytest.MonkeyPatch):
    from freight.client import Priority1Error, truckload_unavailable_message
    from freight import quote as quote_mod

    monkeypatch.setattr(quote_mod, "get_config", lambda: type("C", (), {"mock": False, "environment": "sandbox", "mode_label": "Sandbox"})())

    def boom(*_args, **_kwargs):
        raise Priority1Error(403, ["forbidden"])

    monkeypatch.setattr(quote_mod, "post_priority1", boom)
    with pytest.raises(Exception) as caught:
        quote_tl(
            {
                "markup_percent": 7,
                "origin_zip_code": "90221",
                "destination_zip_code": "72205",
                "pickup_date_open": "2026-10-20",
                "equipment": "53_Foot_Dry_Van",
                "weight": 100,
            }
        )
    assert "Truckload quoting is not available" in str(caught.value)
    assert truckload_unavailable_message(Priority1Error(401, ["no"]))
    assert truckload_unavailable_message(Priority1Error(500, ["no"])) is None
