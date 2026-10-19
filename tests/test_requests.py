import re

from freight.requests import build_ltl_rates_request, build_suggested_class_request, build_tl_rates_request
from freight.validation import normalize_ltl, normalize_tl

LTL = {
    "markup_percent": 7,
    "origin_zip_code": "72205",
    "destination_zip_code": "60606",
    "pickup_date": "2026-10-20",
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
            "is_stackable": False,
            "is_hazardous": False,
            "is_used": False,
            "is_machinery": False,
        }
    ],
    "accessorial_services": ["LGPU", "APPT"],
}


def test_ltl_rates_body_matches_schema():
    body = build_ltl_rates_request(normalize_ltl(LTL))
    assert body == {
        "originZipCode": "72205",
        "destinationZipCode": "60606",
        "pickupDate": "2026-10-20T00:00:00",
        "items": [
            {
                "freightClass": "150",
                "packagingType": "Pallet",
                "units": 1,
                "pieces": 1,
                "totalWeight": 275,
                "length": 48,
                "width": 40,
                "height": 40,
                "isStackable": False,
                "isHazardous": False,
                "isUsed": False,
                "isMachinery": False,
            }
        ],
        "accessorialServices": [{"code": "LGPU"}, {"code": "APPT"}],
    }
    assert "markup" not in str(body).lower()
    assert "Z" not in body["pickupDate"]


def test_suggested_class_body():
    assert build_suggested_class_request(
        {"total_weight": 200, "width": 100, "height": 100, "length": 100, "units": 1}
    ) == {
        "totalWeight": 200,
        "length": 100,
        "width": 100,
        "height": 100,
        "units": 1,
    }


def test_truckload_body_is_origin_local():
    body = build_tl_rates_request(
        normalize_tl(
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
                "truckload_quote_service_type_id": "Full",
                "weight": 100,
                "weight_unit_id": "lbs",
                "pallet_count": 3,
                "description": "Olives",
                "start_time": "08:00",
                "end_time": "20:00",
            }
        )
    )
    assert body["pickupDateOpen"] == "2026-10-20T00:00:00"
    assert body["equipment"] == "53_Foot_Dry_Van"
    assert body["truckloadQuoteServiceTypeId"] == "Full"
    assert body["weightUnitId"] == "lbs"
    assert "markupPercent" not in body
    assert re.search(r"Z|[+-]\d{2}:\d{2}$", body["pickupDateOpen"]) is None
