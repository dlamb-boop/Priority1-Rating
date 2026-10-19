"""JSON bodies for the Priority1 v2 quote endpoints.

Field names match the OpenAPI schema. Timestamps are origin-local and have no Z.
"""

from __future__ import annotations

from freight.validation import to_pickup_datetime


def _omit(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def build_ltl_line_item(item: dict) -> dict:
    return _omit(
        {
            "freightClass": str(item["freight_class"]),
            "packagingType": item["packaging_type"],
            "units": item["units"],
            "pieces": item.get("pieces"),
            "totalWeight": item["total_weight"],
            "length": item["length"],
            "width": item["width"],
            "height": item["height"],
            "isStackable": bool(item.get("is_stackable")),
            "isHazardous": bool(item.get("is_hazardous")),
            "isUsed": bool(item.get("is_used")),
            "isMachinery": bool(item.get("is_machinery")),
            "nmfcItemCode": item.get("nmfc_item_code") or None,
            "nmfcSubCode": item.get("nmfc_sub_code") or None,
            "description": item.get("description") or None,
        }
    )


def build_ltl_rates_request(quote: dict) -> dict:
    accessorials = quote.get("accessorial_services") or []
    timeout = quote.get("carrier_timeout_seconds")
    return _omit(
        {
            "originCity": quote.get("origin_city"),
            "originStateAbbreviation": quote.get("origin_state_abbreviation"),
            "originZipCode": quote["origin_zip_code"],
            "originCountryCode": quote.get("origin_country_code"),
            "destinationCity": quote.get("destination_city"),
            "destinationStateAbbreviation": quote.get("destination_state_abbreviation"),
            "destinationZipCode": quote["destination_zip_code"],
            "destinationCountryCode": quote.get("destination_country_code"),
            "pickupDate": to_pickup_datetime(quote["pickup_date"]),
            "items": [build_ltl_line_item(item) for item in quote["items"]],
            "accessorialServices": [{"code": code} for code in accessorials] if accessorials else None,
            "apiConfiguration": {"timeout": timeout} if timeout is not None else None,
        }
    )


def build_suggested_class_request(payload: dict) -> dict:
    return {
        "totalWeight": payload["total_weight"],
        "length": payload["length"],
        "width": payload["width"],
        "height": payload["height"],
        "units": payload["units"],
    }


def build_tl_rates_request(quote: dict) -> dict:
    return _omit(
        {
            "originZipCode": quote["origin_zip_code"],
            "originCity": quote.get("origin_city"),
            "originState": quote.get("origin_state"),
            "originCountryCode": quote.get("origin_country_code"),
            "destinationZipCode": quote["destination_zip_code"],
            "destinationCity": quote.get("destination_city"),
            "destinationState": quote.get("destination_state"),
            "destinationCountryCode": quote.get("destination_country_code"),
            "pickupDateOpen": to_pickup_datetime(quote["pickup_date_open"]),
            "pickupDateClose": to_pickup_datetime(quote["pickup_date_close"]) if quote.get("pickup_date_close") else None,
            "startTime": quote.get("start_time"),
            "endTime": quote.get("end_time"),
            "equipment": quote["equipment"],
            "truckloadQuoteServiceTypeId": quote.get("truckload_quote_service_type_id"),
            "weight": quote["weight"],
            "weightUnitId": quote.get("weight_unit_id"),
            "palletCount": quote.get("pallet_count"),
            "linearFeet": quote.get("linear_feet"),
            "description": quote.get("description"),
            "isFloorLoaded": bool(quote.get("is_floor_loaded")),
            "receiveLoadOnWeekend": bool(quote.get("receive_load_on_weekend")),
            "requiresLiftGate": bool(quote.get("requires_lift_gate")),
            "hasETrack": bool(quote.get("has_e_track")),
            "loadBarCount": quote.get("load_bar_count"),
            "strapCount": quote.get("strap_count"),
            "needsHeadboard": bool(quote.get("needs_headboard")),
            "chainCount": quote.get("chain_count"),
            "pipeStakeCount": quote.get("pipe_stake_count"),
            "coilRackCount": quote.get("coil_rack_count"),
        }
    )
