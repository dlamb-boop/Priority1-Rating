"""Customer-facing quote document. Internal economics are dropped by allow-list."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from freight.constants import PREPARED_BY

FORBIDDEN = [
    "markup",
    "basecost",
    "base cost",
    "base total",
    "margin",
    "carrierquotenumber",
    "quoteid",
    "rateid",
    "priority1",
]


def _clean(value: object, limit: int = 120) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _money(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    if value != value:
        return None
    return round(float(value) * 100) / 100


def _place(city: str | None, state: str | None, zip_code: str) -> str:
    place = ", ".join(part for part in (city, state) if part)
    return f"{place} {zip_code}".strip() if place else zip_code


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _add_days(iso_date: str, days: int) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso_date)
    if not match:
        return iso_date
    cursor = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
    cursor += timedelta(days=days)
    return cursor.strftime("%Y-%m-%d")


def _reference(quote_date: str, origin: str, destination: str) -> str:
    seed = f"{quote_date}|{origin}|{destination}"
    digest = 2166136261
    for char in seed:
        digest ^= ord(char)
        digest = (digest * 16777619) & 0xFFFFFFFF
    return f"EPQ-{digest:X}"[:10]


def customer_pdf_filename(quote_date: str) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", quote_date or "")
    stamp = match.group(1) if match else "quote"
    return f"EasyPost-Freight-Quote-{stamp}.pdf"


def to_customer_rate(rate: dict) -> dict:
    return {
        "option_id": rate.get("option_id"),
        "carrier_name": rate.get("carrier_name"),
        "scac": rate.get("scac"),
        "service_level": rate.get("service_level"),
        "service_level_description": rate.get("service_level_description"),
        "lane_type": rate.get("lane_type"),
        "transit_days": rate.get("transit_days"),
        "delivery_date": rate.get("delivery_date"),
        "expiration_date": rate.get("expiration_date"),
        "customer_total": rate.get("customer_total"),
        "currency": rate.get("currency"),
        "charges": [
            {"code": charge.get("code"), "description": charge.get("description"), "amount": charge.get("amount")}
            for charge in rate.get("charges") or []
        ],
    }


def build_customer_quote(payload: dict) -> dict:
    shipment = payload.get("shipment")
    if not shipment:
        raise ValueError("A shipment summary is required.")
    selected = list(payload.get("options") or [])[:12]
    if not selected:
        raise ValueError("Choose at least one carrier option for the quote.")
    raw_date = payload.get("quote_date") or ""
    quote_date = raw_date[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", str(raw_date)) else _today()
    options = []
    for option in selected:
        price = _money(option.get("customer_total", option.get("price")))
        if price is None:
            raise ValueError("Each selected option needs a customer price.")
        charges = []
        for charge in option.get("charges") or []:
            if not isinstance(charge, dict):
                continue
            amount = _money(charge.get("amount", charge.get("customer_amount")))
            if amount is None:
                continue
            charges.append(
                {
                    "code": _clean(charge.get("code"), 20) or "CHG",
                    "description": _clean(charge.get("description"), 80) or "Charge",
                    "amount": amount,
                }
            )
        options.append(
            {
                "carrier_name": _clean(option.get("carrier_name"), 80) or "Carrier option",
                "scac": _clean(option.get("scac"), 8).upper(),
                "service_level": _clean(option.get("service_level_description"), 80)
                or _clean(option.get("service_level"), 40)
                or "Standard",
                "lane_type": _clean(option.get("lane_type"), 20) or None,
                "transit_days": option.get("transit_days") if isinstance(option.get("transit_days"), int) else None,
                "delivery_date": _clean(option.get("delivery_date"), 40) or None,
                "expiration_date": _clean(option.get("expiration_date"), 40) or None,
                "price": price,
                "currency": _clean(option.get("currency"), 3) or "USD",
                "charges": charges,
            }
        )
    expirations = sorted(
        date[:10]
        for date in (option["expiration_date"] for option in options)
        if isinstance(date, str) and re.match(r"^\d{4}-\d{2}-\d{2}", date)
    )
    origin_zip = _clean(shipment.get("origin_zip_code"), 12)
    destination_zip = _clean(shipment.get("destination_zip_code"), 12)
    accessorials = []
    for item in shipment.get("accessorials") or []:
        label = item if isinstance(item, str) else item.get("description")
        cleaned = _clean(label, 80)
        if cleaned:
            accessorials.append(cleaned)
    return {
        "customer_name": _clean(payload.get("customer_name"), 80),
        "company": _clean(payload.get("company"), 80),
        "quote_date": quote_date,
        "valid_through": expirations[0] if expirations else _add_days(quote_date, 7),
        "reference": _reference(quote_date, origin_zip, destination_zip),
        "mention_capacity_partner": payload.get("show_priority1") is True,
        "shipment": {
            "origin_label": _place(_clean(shipment.get("origin_city"), 60) or None, _clean(shipment.get("origin_state"), 8) or None, origin_zip),
            "destination_label": _place(
                _clean(shipment.get("destination_city"), 60) or None,
                _clean(shipment.get("destination_state"), 8) or None,
                destination_zip,
            ),
            "pickup_date": _clean(shipment.get("pickup_date"), 40)[:10],
            "distance_miles": int(round(shipment["distance_miles"])) if isinstance(shipment.get("distance_miles"), (int, float)) else None,
            "total_weight": shipment.get("total_weight") if isinstance(shipment.get("total_weight"), (int, float)) else None,
            "items": [
                {
                    "freight_class": _clean(item.get("freight_class"), 8),
                    "packaging_type": _clean(item.get("packaging_type"), 20),
                    "units": int(item.get("units") or 0),
                    "pieces": item.get("pieces"),
                    "total_weight": float(item.get("total_weight") or 0),
                    "length": float(item.get("length") or 0),
                    "width": float(item.get("width") or 0),
                    "height": float(item.get("height") or 0),
                    "description": _clean(item.get("description"), 120) or None,
                    "is_hazardous": bool(item.get("is_hazardous")),
                    "is_stackable": bool(item.get("is_stackable")),
                }
                for item in shipment.get("items") or []
            ],
            "accessorials": accessorials,
        },
        "options": options,
    }


def assert_customer_safe(document: dict, raw_base_amounts: list[str] | None = None) -> None:
    serialized = json.dumps(document).lower()
    forbidden = FORBIDDEN
    if document.get("mention_capacity_partner"):
        forbidden = [word for word in FORBIDDEN if word != "priority1"]
    for word in forbidden:
        if word in serialized:
            raise AssertionError(f"Customer quote includes restricted text ({word}).")
    for amount in raw_base_amounts or []:
        if amount and amount.lower() in serialized:
            raise AssertionError("Customer quote includes a pre-markup amount.")


def prepared_by_line() -> str:
    return PREPARED_BY
