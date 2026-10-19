"""Deterministic demo rates used when no API key is configured."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from freight.constants import ZIP_HINTS
from freight.markup import round_cents

CARRIERS = [
    {"carrierName": "Southeastern Freight", "carrierCode": "SEFL", "multiplier": 1, "transitDays": 3, "discount": False},
    {"carrierName": "R&L Carriers", "carrierCode": "RLCA", "multiplier": 1.14, "transitDays": 4, "discount": True},
    {"carrierName": "Estes", "carrierCode": "EXLA", "multiplier": 1.21, "transitDays": 3, "discount": False},
    {"carrierName": "Saia", "carrierCode": "SAIA", "multiplier": 1.28, "transitDays": 4, "discount": True},
    {"carrierName": "ABF Freight", "carrierCode": "ABFS", "multiplier": 1.36, "transitDays": 5, "discount": False},
]

ACCESSORIAL_FEES = {
    "LGPU": 55,
    "LGDEL": 55,
    "RESPU": 48,
    "RESDEL": 78,
    "INPU": 65,
    "INDEL": 85,
    "LTDPU": 70,
    "LTDDEL": 70,
    "APPT": 22,
    "NOTIFY": 15,
    "HAZM": 45,
    "PFZ": 35,
    "SATPU": 80,
    "LUMPER": 95,
    "BLIND": 40,
    "BOND": 60,
}

COORDS = {
    "72205": (34.75, -92.29),
    "60606": (41.88, -87.64),
    "90221": (33.94, -118.21),
    "10001": (40.75, -73.99),
    "30303": (33.75, -84.39),
    "75201": (32.79, -96.8),
    "98101": (47.61, -122.33),
    "94105": (37.79, -122.39),
}


def _hash(value: str) -> int:
    h = 2166136261
    for char in value:
        h ^= ord(char)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _shift(iso_date: str, days: int, business: bool) -> str:
    year, month, day = (int(part) for part in iso_date[:10].split("-"))
    cursor = datetime(year, month, day, tzinfo=timezone.utc)
    if business:
        remaining = days
        while remaining > 0:
            cursor += timedelta(days=1)
            if cursor.weekday() < 5:
                remaining -= 1
    else:
        cursor += timedelta(days=days)
    return cursor.strftime("%Y-%m-%dT16:00:00")


def _distance(origin: str, destination: str) -> int:
    a = COORDS.get(origin[:5])
    b = COORDS.get(destination[:5])
    if a and b:
        miles = math.hypot((a[0] - b[0]) * 69, (a[1] - b[1]) * 53)
        return max(40, int(math.floor(miles + 0.5)))
    return 180 + (_hash(f"{origin}|{destination}") % 1600)


def suggest_freight_class(total_weight: float, length: float, width: float, height: float, units: int) -> str:
    cubic_feet = (length * width * height * max(1, units)) / 1728
    density = total_weight / cubic_feet if cubic_feet else 0
    bands = [
        (50, "50"),
        (35, "55"),
        (30, "60"),
        (22.5, "65"),
        (15, "70"),
        (13.5, "77.5"),
        (12, "85"),
        (10.5, "92.5"),
        (9, "100"),
        (8, "110"),
        (7, "125"),
        (6, "150"),
        (5, "175"),
        (4, "200"),
        (3, "250"),
        (2, "300"),
        (1, "400"),
        (0, "500"),
    ]
    for minimum, freight_class in bands:
        if density >= minimum:
            return freight_class
    return "500"


def mock_ltl_rates(quote: dict) -> dict:
    origin = ZIP_HINTS.get(quote["origin_zip_code"][:5])
    destination = ZIP_HINTS.get(quote["destination_zip_code"][:5])
    distance = _distance(quote["origin_zip_code"], quote["destination_zip_code"])
    weight = sum(item["total_weight"] for item in quote["items"])
    average = sum(float(item["freight_class"]) * item["total_weight"] for item in quote["items"]) / max(weight, 1)
    linear = max(
        1,
        int(
            math.floor(
                sum((item["length"] / 12) * (2 if item["width"] > 50 else 1) * item["units"] for item in quote["items"])
                + 0.5
            )
        ),
    )
    class_factor = 0.72 + average / 180
    anchor = max(110, weight * 0.22 * class_factor * (distance / 480))
    accessorial_base = sum(ACCESSORIAL_FEES.get(code, 32) for code in quote.get("accessorial_services") or [])
    pickup = quote["pickup_date"][:10]
    rate_quotes = []
    for index, carrier in enumerate(CARRIERS):
        linehaul = round_cents(anchor * carrier["multiplier"])
        fuel = round_cents(linehaul * 0.185)
        accessorial = round_cents(accessorial_base * (1 + index * 0.03))
        gross = round_cents(linehaul + fuel + accessorial)
        discount = round_cents(gross * -0.12) if carrier["discount"] else 0
        total = round_cents(gross + discount)
        charges = [
            {"code": "GFC", "description": "Gross Freight Charge", "amount": linehaul},
            {"code": "FSC", "description": "Fuel Surcharge", "amount": fuel},
        ]
        if accessorial > 0:
            charges.append({"code": "ACC", "description": "Accessorials", "amount": accessorial})
        if discount:
            charges.append({"code": "DSC", "description": "Carrier discount", "amount": discount})
        transit = carrier["transitDays"] + (1 if distance > 1200 else 0)
        rate_quotes.append(
            {
                "id": 900000 + index,
                "carrierName": carrier["carrierName"],
                "carrierCode": carrier["carrierCode"],
                "serviceLevel": "STANDARD",
                "serviceLevelDescription": "Standard",
                "transitDays": transit,
                "laneType": "INTERLINE" if distance > 1500 else "DIRECT",
                "deliveryDate": _shift(pickup, transit, True),
                "effectiveDate": _shift(pickup, 0, False),
                "expirationDate": _shift(pickup, 7, False),
                "carrierQuoteNumber": f"DEMO-{carrier['carrierCode']}-{1000 + index}",
                "rateQuoteDetail": {"total": total, "baseCost": linehaul, "charges": charges},
            }
        )
    warning = []
    if quote.get("origin_city") and origin and quote["origin_city"].lower() != origin[0].lower():
        warning.append(
            {
                "severity": "Warning",
                "text": f"Origin city was normalized to {origin[0]}, {origin[1]} for ZIP {quote['origin_zip_code']}.",
            }
        )
    return {
        "id": 424242,
        "rateQuotes": rate_quotes,
        "invalidRateQuotes": [
            {
                "carrierCode": "ODFL",
                "carrierName": "Old Dominion Freight Line",
                "errorMessages": [{"severity": "Error", "text": "An error occurred while retrieving rates."}],
            }
        ],
        "rateQuoteRequestDetail": {
            "originZipCode": quote["origin_zip_code"],
            "originCity": quote.get("origin_city") or (origin[0] if origin else None),
            "originStateAbbreviation": quote.get("origin_state_abbreviation") or (origin[1] if origin else None),
            "destinationZipCode": quote["destination_zip_code"],
            "destinationCity": quote.get("destination_city") or (destination[0] if destination else None),
            "destinationStateAbbreviation": quote.get("destination_state_abbreviation") or (destination[1] if destination else None),
            "pickupDate": f"{pickup}T00:00:00",
            "linearFeet": linear,
            "distance": distance,
            "totalWeight": weight,
        },
        "messages": warning,
    }


def mock_tl_rates(quote: dict) -> dict:
    distance = _distance(quote["origin_zip_code"], quote["destination_zip_code"])
    pounds = quote["weight"] * 2.20462 if quote.get("weight_unit_id") == "kg" else quote["weight"]
    equipment = str(quote.get("equipment") or "")
    premium = 1.22 if ("Flatbed" in equipment or "Step" in equipment) else 1
    team = 1.18 if quote.get("truckload_quote_service_type_id") == "Team" else 1
    anchor = max(1450, 1.55 * distance + pounds * 0.08) * premium * team
    pickup = quote["pickup_date_open"][:10]
    profiles = [
        {"factor": 1, "days": 4 if distance > 1400 else 3},
        {"factor": 1.08, "days": 4 if distance > 800 else 2},
        {"factor": 1.16, "days": 5 if distance > 500 else 3},
    ]
    rates = []
    for index, profile in enumerate(profiles):
        linehaul = round_cents(anchor * profile["factor"])
        fuel = round_cents(linehaul * 0.19)
        lift = 175 if quote.get("requires_lift_gate") else 0
        total = round_cents(linehaul + fuel + lift)
        charges = [
            {"code": "LineHaul", "description": "Line Haul", "amount": linehaul},
            {"code": "Fuel", "description": "Fuel", "amount": fuel},
        ]
        if lift:
            charges.append({"code": "LiftGate", "description": "Lift gate", "amount": lift})
        rates.append(
            {
                "rateId": 8000 + index,
                "currencyTypeId": "USD",
                "total": total,
                "truckloadRateQuoteDetail": {"total": total, "charges": charges},
                "expirationDate": _shift(pickup, 3, False),
                "pickupDate": f"{pickup}T08:00:00",
                "deliveryDate": _shift(pickup, profile["days"], True),
                "transitDays": profile["days"],
            }
        )
    return {
        "id": 515151,
        "rates": rates,
        "truckloadRateQuoteResponseDetail": {
            "originZipCode": quote["origin_zip_code"],
            "destinationZipCode": quote["destination_zip_code"],
            "pickupDate": f"{pickup}T08:00:00",
            "linearFeet": quote.get("linear_feet") if quote.get("linear_feet") is not None else min(53, max(8, int(round(pounds / 800)))),
            "distance": distance,
            "totalWeight": int(round(pounds)),
        },
        "additionalInformation": None,
    }
