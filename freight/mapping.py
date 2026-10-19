"""Turn a Priority1 response into the desk model. Upstream ids stay out."""

from __future__ import annotations

from freight.accessorials import accessorial_label
from freight.constants import ZIP_HINTS
from freight.markup import apply_markup


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _hint(zip_code: str) -> tuple[str, str] | None:
    return ZIP_HINTS.get((zip_code or "")[:5])


def map_ltl_response(raw: dict, quote: dict, meta: dict) -> dict:
    rates = []
    for index, rate in enumerate(raw.get("rateQuotes") or []):
        detail = rate.get("rateQuoteDetail") or {}
        total = detail.get("total")
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            continue
        priced = apply_markup(total, detail.get("charges") or [], quote["markup_percent"])
        scac = _text(rate.get("carrierCode")) or ""
        service = _text(rate.get("serviceLevel")) or "STANDARD"
        base_cost = detail.get("baseCost")
        rates.append(
            {
                "option_id": f"ltl-{index + 1}-{scac or 'carrier'}-{service}".lower(),
                "carrier_name": _text(rate.get("carrierName")) or "Carrier",
                "scac": scac,
                "service_level": service,
                "service_level_description": _text(rate.get("serviceLevelDescription")),
                "lane_type": _text(rate.get("laneType")),
                "transit_days": rate.get("transitDays") if isinstance(rate.get("transitDays"), int) else None,
                "delivery_date": _text(rate.get("deliveryDate")),
                "expiration_date": _text(rate.get("expirationDate")),
                "customer_total": priced.customer_total,
                "currency": "USD",
                "charges": [
                    {"code": charge.code, "description": charge.description, "amount": charge.customer_amount}
                    for charge in priced.charges
                ],
                "internal": {
                    "base_total": priced.base_total,
                    "carrier_base_cost": base_cost if isinstance(base_cost, (int, float)) and not isinstance(base_cost, bool) else None,
                    "markup_percent": priced.markup_percent,
                    "markup_amount": priced.markup_amount,
                    "margin_percent": priced.margin_percent,
                    "carrier_quote_number": _text(rate.get("carrierQuoteNumber")),
                    "charges": [
                        {
                            "code": charge.code,
                            "description": charge.description,
                            "base_amount": charge.base_amount,
                            "customer_amount": charge.customer_amount,
                        }
                        for charge in priced.charges
                    ],
                },
            }
        )
    rates.sort(key=lambda rate: (rate["customer_total"], rate["transit_days"] if rate["transit_days"] is not None else 99))
    failed = []
    for item in raw.get("invalidRateQuotes") or []:
        messages = item.get("errorMessages") or []
        text = next((_text(message.get("text")) for message in messages if isinstance(message, dict)), None)
        failed.append(
            {
                "carrier_name": _text(item.get("carrierName")) or "Carrier",
                "scac": _text(item.get("carrierCode")) or "",
                "message": text or "This carrier did not return a rate.",
            }
        )
    detail = raw.get("rateQuoteRequestDetail") or {}
    origin_hint = _hint(quote["origin_zip_code"])
    dest_hint = _hint(quote["destination_zip_code"])
    shipment = {
        "origin_zip_code": _text(detail.get("originZipCode")) or quote["origin_zip_code"],
        "origin_city": _text(detail.get("originCity")) or quote.get("origin_city") or (origin_hint[0] if origin_hint else None),
        "origin_state": _text(detail.get("originStateAbbreviation"))
        or quote.get("origin_state_abbreviation")
        or (origin_hint[1] if origin_hint else None),
        "destination_zip_code": _text(detail.get("destinationZipCode")) or quote["destination_zip_code"],
        "destination_city": _text(detail.get("destinationCity")) or quote.get("destination_city") or (dest_hint[0] if dest_hint else None),
        "destination_state": _text(detail.get("destinationStateAbbreviation"))
        or quote.get("destination_state_abbreviation")
        or (dest_hint[1] if dest_hint else None),
        "pickup_date": (_text(detail.get("pickupDate")) or quote["pickup_date"])[:10],
        "distance_miles": int(round(detail["distance"])) if isinstance(detail.get("distance"), (int, float)) else None,
        "total_weight": detail.get("totalWeight") if isinstance(detail.get("totalWeight"), (int, float)) else sum(item["total_weight"] for item in quote["items"]),
        "linear_feet": detail.get("linearFeet") if isinstance(detail.get("linearFeet"), (int, float)) else None,
        "items": [
            {
                "freight_class": str(item["freight_class"]),
                "packaging_type": item["packaging_type"],
                "units": item["units"],
                "pieces": item.get("pieces"),
                "total_weight": item["total_weight"],
                "length": item["length"],
                "width": item["width"],
                "height": item["height"],
                "description": item.get("description"),
                "is_hazardous": bool(item.get("is_hazardous")),
                "is_stackable": bool(item.get("is_stackable")),
            }
            for item in quote["items"]
        ],
        "accessorials": [
            {"code": code, "description": accessorial_label(code)} for code in quote.get("accessorial_services") or []
        ],
    }
    warnings = [_text(message.get("text")) for message in (raw.get("messages") or []) if isinstance(message, dict)]
    return {
        "mode": meta["mode"],
        "environment": meta["environment"],
        "mode_label": meta["mode_label"],
        "product": "ltl",
        "markup_percent": rates[0]["internal"]["markup_percent"] if rates else quote["markup_percent"],
        "shipment": shipment,
        "rates": rates,
        "failed_carriers": failed,
        "warnings": [warning for warning in warnings if warning],
    }


def map_tl_response(raw: dict, quote: dict, meta: dict) -> dict:
    origin_hint = _hint(quote["origin_zip_code"])
    dest_hint = _hint(quote["destination_zip_code"])
    detail = raw.get("truckloadRateQuoteResponseDetail") or {}
    rates = []
    for index, rate in enumerate(raw.get("rates") or []):
        total = rate.get("total")
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            nested = (rate.get("truckloadRateQuoteDetail") or {}).get("total")
            total = nested
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            continue
        charges = (rate.get("truckloadRateQuoteDetail") or {}).get("charges") or []
        priced = apply_markup(total, charges, quote["markup_percent"])
        rates.append(
            {
                "option_id": f"tl-{index + 1}",
                "carrier_name": f"Truckload option {index + 1}",
                "scac": "",
                "service_level": str(quote.get("truckload_quote_service_type_id") or "Full"),
                "service_level_description": None,
                "lane_type": None,
                "transit_days": rate.get("transitDays") if isinstance(rate.get("transitDays"), int) else None,
                "delivery_date": _text(rate.get("deliveryDate")),
                "expiration_date": _text(rate.get("expirationDate")),
                "customer_total": priced.customer_total,
                "currency": _text(rate.get("currencyTypeId")) or "USD",
                "charges": [
                    {"code": charge.code, "description": charge.description, "amount": charge.customer_amount}
                    for charge in priced.charges
                ],
                "internal": {
                    "base_total": priced.base_total,
                    "carrier_base_cost": None,
                    "markup_percent": priced.markup_percent,
                    "markup_amount": priced.markup_amount,
                    "margin_percent": priced.margin_percent,
                    "carrier_quote_number": None,
                    "charges": [
                        {
                            "code": charge.code,
                            "description": charge.description,
                            "base_amount": charge.base_amount,
                            "customer_amount": charge.customer_amount,
                        }
                        for charge in priced.charges
                    ],
                },
            }
        )
    rates.sort(key=lambda rate: (rate["customer_total"], rate["transit_days"] if rate["transit_days"] is not None else 99))
    warnings = []
    extra = _text(raw.get("additionalInformation"))
    if extra:
        warnings.append(extra)
    warnings.append("Truckload rates from this API do not include a carrier name or SCAC.")
    shipment = {
        "origin_zip_code": _text(detail.get("originZipCode")) or quote["origin_zip_code"],
        "origin_city": quote.get("origin_city") or (origin_hint[0] if origin_hint else None),
        "origin_state": quote.get("origin_state") or (origin_hint[1] if origin_hint else None),
        "destination_zip_code": _text(detail.get("destinationZipCode")) or quote["destination_zip_code"],
        "destination_city": quote.get("destination_city") or (dest_hint[0] if dest_hint else None),
        "destination_state": quote.get("destination_state") or (dest_hint[1] if dest_hint else None),
        "pickup_date": (_text(detail.get("pickupDate")) or quote["pickup_date_open"])[:10],
        "distance_miles": int(round(detail["distance"])) if isinstance(detail.get("distance"), (int, float)) else None,
        "total_weight": detail.get("totalWeight") if isinstance(detail.get("totalWeight"), (int, float)) else quote["weight"],
        "linear_feet": detail.get("linearFeet") if isinstance(detail.get("linearFeet"), (int, float)) else quote.get("linear_feet"),
        "items": [
            {
                "freight_class": "—",
                "packaging_type": "Pallet" if quote.get("pallet_count") else "Truckload",
                "units": quote.get("pallet_count") or 1,
                "pieces": None,
                "total_weight": quote["weight"],
                "length": quote.get("linear_feet") or 0,
                "width": 0,
                "height": 0,
                "description": quote.get("description"),
                "is_hazardous": False,
                "is_stackable": False,
            }
        ],
        "accessorials": [],
    }
    return {
        "mode": meta["mode"],
        "environment": meta["environment"],
        "mode_label": meta["mode_label"],
        "product": "tl",
        "markup_percent": rates[0]["internal"]["markup_percent"] if rates else quote["markup_percent"],
        "shipment": shipment,
        "rates": rates,
        "failed_carriers": [],
        "warnings": warnings,
    }
