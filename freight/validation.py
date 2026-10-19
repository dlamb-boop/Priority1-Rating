"""Validate desk input and shape it for the Priority1 v2 schemas."""

from __future__ import annotations

import re

from freight.accessorials import BY_CODE
from freight.constants import (
    COUNTRY_CODES,
    EQUIPMENT_TYPES,
    FREIGHT_CLASSES,
    PACKAGING_TYPES,
    TL_SERVICE_TYPES,
    WEIGHT_UNITS,
)

US_OR_MX = re.compile(r"^\d{5}(-\d{4})?$")
CA_POSTAL = re.compile(r"^[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d$")
DATE_ONLY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
TIME_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class QuoteError(ValueError):
    """The quote form cannot be sent."""


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuoteError(f"{label} is required.")
    return value.strip()


def _optional(value: object, limit: int = 80) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise QuoteError("Expected text.")
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > limit:
        raise QuoteError(f"Keep this under {limit} characters.")
    return trimmed


def _positive(value: object, label: str) -> float:
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        numeric = float("nan")
    if numeric != numeric or numeric <= 0:
        raise QuoteError(f"{label} must be greater than zero.")
    return numeric


def _positive_int(value: object, label: str, limit: int) -> int:
    try:
        numeric = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise QuoteError(f"{label} must be a whole number from 1 to {limit}.") from None
    if isinstance(value, float) and not value.is_integer():
        raise QuoteError(f"{label} must be a whole number from 1 to {limit}.")
    if numeric < 1 or numeric > limit:
        raise QuoteError(f"{label} must be a whole number from 1 to {limit}.")
    return numeric


def _flag(value: object) -> bool:
    return value is True or value == "true" or value == 1


def is_postal(value: str) -> bool:
    return bool(US_OR_MX.match(value.strip()) or CA_POSTAL.match(value.strip()))


def to_pickup_datetime(value: str) -> str:
    """Origin-local timestamp with no Z and no numeric offset."""
    trimmed = value.strip()
    if DATE_ONLY.match(trimmed):
        return f"{trimmed}T00:00:00"
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$", trimmed):
        return trimmed if len(trimmed) > 16 else f"{trimmed}:00"
    raise QuoteError("Pickup date must be a calendar date.")


def _postal(value: str, label: str) -> str:
    if not is_postal(value):
        raise QuoteError(f"{label} must be a US ZIP or Canadian postal code.")
    return value.strip().upper()


def _state(value: str | None, label: str) -> str | None:
    if not value:
        return None
    if not re.match(r"^[A-Za-z]{2}$", value):
        raise QuoteError(f"{label} must be a 2-letter abbreviation.")
    return value.upper()


def _country(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.upper()
    if upper not in COUNTRY_CODES:
        raise QuoteError("Country must be US, CA, MX, or PR.")
    return upper


def normalize_line_item(raw: dict, index: int) -> dict:
    prefix = f"Item {index + 1}"
    freight_class = _required(str(raw.get("freight_class") or ""), f"{prefix} freight class")
    if freight_class not in FREIGHT_CLASSES:
        raise QuoteError(f"{prefix} freight class must be one of {', '.join(FREIGHT_CLASSES)}.")
    packaging = _required(str(raw.get("packaging_type") or ""), f"{prefix} packaging")
    if packaging not in PACKAGING_TYPES:
        raise QuoteError(f"{prefix} packaging must be one of {', '.join(PACKAGING_TYPES)}.")
    nmfc_item = _optional(raw.get("nmfc_item_code"), 20)
    nmfc_sub = _optional(raw.get("nmfc_sub_code"), 20)
    if bool(nmfc_item) != bool(nmfc_sub):
        raise QuoteError(f"{prefix} needs both an NMFC item code and sub code.")
    pieces = raw.get("pieces")
    return {
        "freight_class": freight_class,
        "packaging_type": packaging,
        "units": _positive_int(raw.get("units"), f"{prefix} units", 200),
        "pieces": None if pieces in (None, "") else _positive_int(pieces, f"{prefix} pieces", 10000),
        "total_weight": _positive(raw.get("total_weight"), f"{prefix} total weight"),
        "length": _positive(raw.get("length"), f"{prefix} length"),
        "width": _positive(raw.get("width"), f"{prefix} width"),
        "height": _positive(raw.get("height"), f"{prefix} height"),
        "is_stackable": _flag(raw.get("is_stackable")),
        "is_hazardous": _flag(raw.get("is_hazardous")),
        "is_used": _flag(raw.get("is_used")),
        "is_machinery": _flag(raw.get("is_machinery")),
        "nmfc_item_code": nmfc_item,
        "nmfc_sub_code": nmfc_sub,
        "description": _optional(raw.get("description"), 120),
    }


def normalize_accessorials(codes: object, hazardous: bool) -> list[str]:
    unique: list[str] = []
    for code in codes or []:
        if not isinstance(code, str) or not code.strip():
            continue
        upper = code.strip().upper()
        if upper not in BY_CODE:
            raise QuoteError(f"Unknown accessorial code {upper}.")
        if upper not in unique:
            unique.append(upper)
    if hazardous and "HAZM" not in unique:
        unique.append("HAZM")
    return unique


def normalize_ltl(raw: dict) -> dict:
    items_raw = raw.get("items") or []
    if not items_raw:
        raise QuoteError("Add at least one freight line item.")
    if len(items_raw) > 20:
        raise QuoteError("A quote can include up to 20 line items.")
    items = [normalize_line_item(item, index) for index, item in enumerate(items_raw)]
    accessorials = normalize_accessorials(raw.get("accessorial_services"), any(item["is_hazardous"] for item in items))
    if "HAZM" in accessorials and not any(item["is_hazardous"] for item in items):
        for item in items:
            item["is_hazardous"] = True
    timeout = raw.get("carrier_timeout_seconds")
    if timeout not in (None, ""):
        timeout = _positive_int(timeout, "Carrier timeout", 60)
        if timeout < 5:
            raise QuoteError("Carrier timeout must be a whole number of seconds from 5 to 60.")
    else:
        timeout = None
    return {
        "markup_percent": raw.get("markup_percent"),
        "origin_zip_code": _postal(_required(raw.get("origin_zip_code"), "Origin ZIP"), "Origin ZIP"),
        "origin_city": _optional(raw.get("origin_city"), 60),
        "origin_state_abbreviation": _state(_optional(raw.get("origin_state_abbreviation"), 2), "Origin state"),
        "origin_country_code": _country(_optional(raw.get("origin_country_code"), 2)),
        "destination_zip_code": _postal(_required(raw.get("destination_zip_code"), "Destination ZIP"), "Destination ZIP"),
        "destination_city": _optional(raw.get("destination_city"), 60),
        "destination_state_abbreviation": _state(
            _optional(raw.get("destination_state_abbreviation"), 2), "Destination state"
        ),
        "destination_country_code": _country(_optional(raw.get("destination_country_code"), 2)),
        "pickup_date": to_pickup_datetime(_required(str(raw.get("pickup_date") or ""), "Pickup date"))[:10],
        "items": items,
        "accessorial_services": accessorials,
        "carrier_timeout_seconds": timeout,
    }


def normalize_tl(raw: dict) -> dict:
    equipment = _required(str(raw.get("equipment") or ""), "Equipment")
    if equipment not in EQUIPMENT_TYPES:
        raise QuoteError(f"Equipment must be one of {', '.join(EQUIPMENT_TYPES)}.")
    service = _optional(raw.get("truckload_quote_service_type_id"), 10) or "Full"
    if service not in TL_SERVICE_TYPES:
        raise QuoteError("Service type must be Full or Team.")
    unit = _optional(raw.get("weight_unit_id"), 4) or "lbs"
    if unit not in WEIGHT_UNITS:
        raise QuoteError("Weight unit must be lbs or kg.")
    start = _optional(raw.get("start_time"), 5)
    end = _optional(raw.get("end_time"), 5)
    if start and not TIME_HHMM.match(start):
        raise QuoteError("Window start must be HH:mm.")
    if end and not TIME_HHMM.match(end):
        raise QuoteError("Window end must be HH:mm.")
    lift_ok = equipment == "Sprinter_Van" or "Straight_Truck" in equipment
    close = raw.get("pickup_date_close")
    return {
        "markup_percent": raw.get("markup_percent"),
        "origin_zip_code": _postal(_required(raw.get("origin_zip_code"), "Origin ZIP"), "Origin ZIP"),
        "origin_city": _optional(raw.get("origin_city"), 60),
        "origin_state": _state(_optional(raw.get("origin_state"), 2), "Origin state"),
        "origin_country_code": _country(_optional(raw.get("origin_country_code"), 2)),
        "destination_zip_code": _postal(_required(raw.get("destination_zip_code"), "Destination ZIP"), "Destination ZIP"),
        "destination_city": _optional(raw.get("destination_city"), 60),
        "destination_state": _state(_optional(raw.get("destination_state"), 2), "Destination state"),
        "destination_country_code": _country(_optional(raw.get("destination_country_code"), 2)),
        "pickup_date_open": to_pickup_datetime(_required(str(raw.get("pickup_date_open") or ""), "Pickup open date"))[:10],
        "pickup_date_close": to_pickup_datetime(str(close))[:10] if close else None,
        "start_time": start,
        "end_time": end,
        "equipment": equipment,
        "truckload_quote_service_type_id": service,
        "weight": _positive_int(raw.get("weight"), "Weight", 200000),
        "weight_unit_id": unit,
        "pallet_count": None if raw.get("pallet_count") in (None, "") else _positive_int(raw.get("pallet_count"), "Pallet count", 100),
        "linear_feet": None if raw.get("linear_feet") in (None, "") else _positive_int(raw.get("linear_feet"), "Linear feet", 53),
        "description": _optional(raw.get("description"), 120),
        "is_floor_loaded": _flag(raw.get("is_floor_loaded")),
        "receive_load_on_weekend": _flag(raw.get("receive_load_on_weekend")),
        "requires_lift_gate": _flag(raw.get("requires_lift_gate")) if lift_ok else False,
        "has_e_track": _flag(raw.get("has_e_track")),
        "load_bar_count": None if raw.get("load_bar_count") in (None, "") else _positive_int(raw.get("load_bar_count"), "Load bars", 20),
        "strap_count": None if raw.get("strap_count") in (None, "") else _positive_int(raw.get("strap_count"), "Straps", 20),
        "needs_headboard": _flag(raw.get("needs_headboard")),
        "chain_count": None if raw.get("chain_count") in (None, "") else _positive_int(raw.get("chain_count"), "Chains", 20),
        "pipe_stake_count": None if raw.get("pipe_stake_count") in (None, "") else _positive_int(raw.get("pipe_stake_count"), "Pipe stakes", 20),
        "coil_rack_count": None if raw.get("coil_rack_count") in (None, "") else _positive_int(raw.get("coil_rack_count"), "Coil racks", 20),
    }
