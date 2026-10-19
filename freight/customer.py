"""Customer-facing quote document. Internal economics are dropped by allow-list."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

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


def format_customer_address(
    street: str = "",
    suite: str = "",
    city: str = "",
    state: str = "",
    postal: str = "",
    country: str = "",
) -> list[str]:
    """Lines for the customer PDF. Empty parts are omitted, and a lone US country is not printed."""
    street = _clean(street, 120)
    suite = _clean(suite, 40)
    city = _clean(city, 60)
    state = _clean(state, 40)
    postal = _clean(postal, 16)
    country = _clean(country, 60)
    if len(state) == 2:
        state = state.upper()
    lines: list[str] = []
    street_line = ", ".join(part for part in (street, suite) if part)
    if street_line:
        lines.append(street_line)
    locality = ", ".join(part for part in (city, state) if part)
    if postal:
        locality = f"{locality} {postal}".strip()
    if locality:
        lines.append(locality)
    country_key = country.lower().rstrip(".")
    if country and country_key not in {"us", "usa", "united states", "united states of america"}:
        lines.append(country)
    return lines


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
    preparer_name = _clean(payload.get("preparer_name"), 80)
    preparer_title = _clean(payload.get("preparer_title"), 80)
    preparer_email = _clean(payload.get("preparer_email"), 80)
    preparer_phone = _clean(payload.get("preparer_phone"), 40)
    address = payload.get("address") if isinstance(payload.get("address"), dict) else {}
    address_lines = format_customer_address(
        str(address.get("street") or ""),
        str(address.get("suite") or ""),
        str(address.get("city") or ""),
        str(address.get("state") or ""),
        str(address.get("postal") or ""),
        str(address.get("country") or ""),
    )
    return {
        "customer_name": _clean(payload.get("customer_name"), 80),
        "company": _clean(payload.get("company"), 80),
        "address_lines": address_lines,
        "preparer_name": preparer_name,
        "prepared_by": prepared_by_line(preparer_name, preparer_title, preparer_email, preparer_phone),
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


def prepared_by_line(name: str = "", title: str = "", email: str = "", phone: str = "") -> str:
    """Customer footer. EasyPost is always the company; blank contact parts are left out."""
    who = ", ".join(part for part in (_clean(name, 80), _clean(title, 80), "EasyPost") if part)
    contact = " · ".join(part for part in (_clean(email, 80), _clean(phone, 40)) if part)
    line = f"Prepared by {who}"
    if contact:
        line = f"{line} · {contact}"
    return line
