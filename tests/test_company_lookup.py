"""Company lookup with mocked HTTP. No live calls."""

import json
from io import BytesIO

import requests
from PIL import Image

from freight.company_lookup import (
    SOURCE_APPLE,
    SOURCE_GOOGLE_FAVICON,
    SOURCE_PLACES,
    SOURCE_SITE,
    SOURCE_WIKIDATA,
    enrich_candidate,
    http_get,
    image_to_png,
    normalize_domain,
    search_companies,
)
from freight.customer import build_customer_quote, format_customer_address

SECRET = "super-secret-places-key"

SHIPMENT = {
    "origin_zip_code": "72205",
    "origin_city": "Little Rock",
    "origin_state": "AR",
    "destination_zip_code": "60606",
    "destination_city": "Chicago",
    "destination_state": "IL",
    "pickup_date": "2026-10-20",
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
    "accessorials": [],
}


def _png(width: int, height: int) -> bytes:
    image = Image.new("RGBA", (width, height), (10, 40, 180, 255))
    for x in range(width // 2):
        for y in range(height):
            image.putpixel((x, y), (220, 40, 40, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _claim(value: object) -> dict:
    return {"mainsnak": {"datavalue": {"value": value}, "snaktype": "value"}, "rank": "normal", "qualifiers": {}}


def _entity(label: str, claims: dict, description: str = "") -> dict:
    return {
        "labels": {"en": {"value": label}},
        "descriptions": {"en": {"value": description}},
        "claims": claims,
    }


def _wiki_entities() -> dict:
    return {
        "Q1": _entity(
            "Northwind",
            {
                "P856": [_claim("https://www.Northwind.example/home")],
                "P154": [_claim("Northwind logo.png")],
                "P159": [_claim({"entity-type": "item", "id": "Q100"})],
            },
            "retailer",
        ),
        "Q2": _entity(
            "Northwind Canada",
            {
                "P856": [_claim("https://northwind.ca")],
                "P159": [_claim({"entity-type": "item", "id": "Q200"})],
            },
            "subsidiary",
        ),
        "Q100": _entity(
            "Bentonville",
            {
                "P131": [_claim({"entity-type": "item", "id": "Q150"})],
                "P6375": [_claim("100 Main Street")],
                "P281": [_claim("72712")],
            },
        ),
        "Q150": _entity("Benton County", {"P131": [_claim({"entity-type": "item", "id": "Q300"})]}),
        "Q300": _entity("Arkansas", {"P131": [_claim({"entity-type": "item", "id": "Q400"})]}),
        "Q400": _entity("United States", {}),
        "Q200": _entity("Toronto", {"P131": [_claim({"entity-type": "item", "id": "Q500"})]}),
        "Q500": _entity("Ontario", {}),
    }


def _route_wiki(url: str, entities: dict | None = None):
    entities = entities if entities is not None else _wiki_entities()
    if "wbsearchentities" in url:
        body = {
            "search": [
                {"id": "Q1", "label": "Northwind", "description": "retailer"},
                {"id": "Q2", "label": "Northwind Canada", "description": "subsidiary"},
                {"id": "Q9", "label": "Northwind", "description": "Northwind disambiguation page"},
            ]
        }
        return 200, json.dumps(body).encode(), "application/json"
    if "wbgetentities" in url:
        ids = url.split("ids=")[1].split("&")[0].split("%7C")
        ids = [item.replace("|", "") for item in ids]
        # urlencode uses %7C for pipe.
        from urllib.parse import parse_qs, urlparse

        ids = parse_qs(urlparse(url).query).get("ids", [""])[0].split("|")
        found = {qid: entities[qid] for qid in ids if qid in entities}
        return 200, json.dumps({"entities": found}).encode(), "application/json"
    return 0, b"", ""


def test_normalize_domain():
    assert normalize_domain("https://www.Walmart.com/store") == "walmart.com"
    assert normalize_domain("WALMART.com") == "walmart.com"
    assert normalize_domain("//www.walmart.com") == "walmart.com"
    assert normalize_domain("") is None
    assert normalize_domain("not a domain") is None
    assert normalize_domain("Northwind Goods") is None
    assert normalize_domain("localhost") is None


def test_search_returns_city_and_domain_and_skips_disambiguation(monkeypatch):
    monkeypatch.setattr("freight.company_lookup.http_get", lambda url, **kwargs: _route_wiki(url))
    matches = search_companies("Northwind")
    assert len(matches) == 2
    assert matches[0]["name"] == "Northwind"
    assert matches[0]["domain"] == "northwind.example"
    assert matches[0]["city"] == "Bentonville"
    assert matches[0]["state"] == "AR"
    assert matches[0]["street"] == "100 Main Street"
    assert matches[0]["postal"] == "72712"
    assert matches[0]["address_source"] == SOURCE_WIKIDATA
    assert matches[0]["website_source"] == SOURCE_WIKIDATA
    assert "Bentonville, AR" in matches[0]["label"]
    assert "northwind.example" in matches[0]["label"]
    assert matches[1]["city"] == "Toronto"
    assert matches[1]["domain"] == "northwind.ca"
    assert all("disambiguation" not in match["label"].lower() for match in matches)
    assert all("logo_png" not in match for match in matches)


def test_company_ranks_ahead_of_a_town_with_the_same_name(monkeypatch):
    entities = {
        "Q10": _entity(
            "Patagonia",
            {"P856": [_claim("http://townofpatagonia.com")], "P281": [_claim("85624")]},
            "town in Arizona",
        ),
        "Q11": _entity(
            "Patagonia, Inc.",
            {
                "P856": [_claim("https://www.patagonia.com/")],
                "P159": [_claim({"entity-type": "item", "id": "Q12"})],
            },
            "American clothing company",
        ),
        "Q12": _entity("Ventura", {"P131": [_claim({"entity-type": "item", "id": "Q13"})]}),
        "Q13": _entity("Ventura County", {"P131": [_claim({"entity-type": "item", "id": "Q14"})]}),
        "Q14": _entity("California", {}),
    }

    def fake(url, **kwargs):
        if "wbsearchentities" in url:
            body = {
                "search": [
                    {"id": "Q10", "label": "Patagonia", "description": "town in Arizona"},
                    {"id": "Q11", "label": "Patagonia, Inc.", "description": "American clothing company"},
                ]
            }
            return 200, json.dumps(body).encode(), "application/json"
        return _route_wiki(url, entities)

    monkeypatch.setattr("freight.company_lookup.http_get", fake)
    matches = search_companies("Patagonia")
    assert matches[0]["domain"] == "patagonia.com"
    assert matches[0]["city"] == "Ventura"
    assert matches[0]["state"] == "CA"
    assert matches[1]["domain"] == "townofpatagonia.com"


def test_empty_lookup_does_not_raise_or_guess_a_domain(monkeypatch):
    seen = []

    def fake(url, **kwargs):
        seen.append(url)
        if "wbsearchentities" in url:
            return 200, b'{"search":[]}', "application/json"
        return 0, b"", ""

    monkeypatch.setattr("freight.company_lookup.http_get", fake)
    assert search_companies("Northwind Goods") == []
    assert search_companies("") == []
    assert seen
    assert all("wikidata.org" in url for url in seen)


def test_homepage_address_and_apple_icon(monkeypatch):
    html = """
    <html><head>
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <script type="application/ld+json">
    {"@type":"Organization","name":"Northwind","address":{"@type":"PostalAddress","streetAddress":"100 Main Street","addressLocality":"Bentonville","addressRegion":"Arkansas","postalCode":"72712","addressCountry":"US"}}
    </script>
    </head></html>
    """
    icon = _png(96, 96)

    def fake(url, **kwargs):
        if "wikidata.org" in url or "commons.wikimedia.org" in url:
            if "wbsearchentities" in url:
                body = {"search": [{"id": "Q1", "label": "Northwind", "description": "retailer"}]}
                return 200, json.dumps(body).encode(), "application/json"
            if "wbgetentities" in url:
                entity = _entity("Northwind", {"P856": [_claim("https://northwind.example")]}, "retailer")
                return 200, json.dumps({"entities": {"Q1": entity}}).encode(), "application/json"
            return 0, b"", ""
        if url.rstrip("/").endswith("northwind.example"):
            return 200, html.encode(), "text/html"
        if url.endswith("/apple-touch-icon.png"):
            return 200, icon, "image/png"
        return 0, b"", ""

    monkeypatch.setattr("freight.company_lookup.http_get", fake)
    match = search_companies("Northwind")[0]
    enriched = enrich_candidate(match)
    assert enriched["street"] == "100 Main Street"
    assert enriched["city"] == "Bentonville"
    assert enriched["state"] == "AR"
    assert enriched["postal"] == "72712"
    assert enriched["address_source"] == SOURCE_SITE
    assert enriched["logo_source"] == SOURCE_APPLE
    assert enriched["logo_png"]
    public = {key: value for key, value in enriched.items() if key != "logo_png"}
    dumped = json.dumps(public)
    assert "/apple-touch-icon.png" not in dumped
    assert "http://" not in dumped
    assert dumped.count("https://") == 1
    assert enriched["website"] in dumped
    assert "wikidata.org" not in dumped


def test_homepage_timeout_uses_google_favicon(monkeypatch):
    icon = _png(64, 64)

    def fake(url, **kwargs):
        if "wbsearchentities" in url:
            body = {"search": [{"id": "Q1", "label": "Northwind", "description": "retailer"}]}
            return 200, json.dumps(body).encode(), "application/json"
        if "wbgetentities" in url:
            entity = _entity("Northwind", {"P856": [_claim("https://northwind.example")]}, "retailer")
            return 200, json.dumps({"entities": {"Q1": entity}}).encode(), "application/json"
        if "google.com/s2/favicons" in url and "northwind.example" in url:
            return 200, icon, "image/png"
        return 0, b"", ""

    monkeypatch.setattr("freight.company_lookup.http_get", fake)
    enriched = enrich_candidate(search_companies("Northwind")[0])
    assert enriched["logo_source"] == SOURCE_GOOGLE_FAVICON
    assert enriched["street"] == ""
    assert enriched["city"] == ""
    assert enriched["logo_png"]


def test_tiny_and_banner_images_are_rejected(monkeypatch):
    assert image_to_png(_png(8, 8), source=SOURCE_GOOGLE_FAVICON) is None
    solid = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    buffer = BytesIO()
    solid.save(buffer, format="PNG")
    assert image_to_png(buffer.getvalue(), source=SOURCE_APPLE) is None
    assert image_to_png(_png(1400, 400), source="og:image") is None

    def fake(url, **kwargs):
        if "wbsearchentities" in url:
            body = {"search": [{"id": "Q1", "label": "Northwind", "description": "retailer"}]}
            return 200, json.dumps(body).encode(), "application/json"
        if "wbgetentities" in url:
            entity = _entity("Northwind", {"P856": [_claim("https://northwind.example")]}, "retailer")
            return 200, json.dumps({"entities": {"Q1": entity}}).encode(), "application/json"
        if url.rstrip("/").endswith("northwind.example"):
            html = '<html><head><meta property="og:image" content="https://cdn.example/banner.png"></head></html>'
            return 200, html.encode(), "text/html"
        if url.endswith("/banner.png"):
            return 200, _png(1400, 400), "image/png"
        if "google.com/s2/favicons" in url or "duckduckgo.com" in url:
            return 200, _png(8, 8), "image/png"
        return 0, b"", ""

    monkeypatch.setattr("freight.company_lookup.http_get", fake)
    enriched = enrich_candidate(search_companies("Northwind")[0])
    assert enriched["logo_png"] is None
    assert enriched["logo_source"] == ""


def test_places_address_and_key_are_not_leaked(monkeypatch):
    def fake(method, url, **kwargs):
        assert SECRET not in url
        if method == "POST" and "places.googleapis.com" in url:
            assert kwargs["headers"]["X-Goog-Api-Key"] == SECRET
            place = {
                "places": [
                    {
                        "id": "place-1",
                        "displayName": {"text": "Northwind"},
                        "websiteUri": "https://www.northwind.example",
                        "addressComponents": [
                            {"longText": "100", "shortText": "100", "types": ["street_number"]},
                            {"longText": "Main Street", "shortText": "Main St", "types": ["route"]},
                            {"longText": "Suite 5", "shortText": "Suite 5", "types": ["subpremise"]},
                            {"longText": "Bentonville", "shortText": "Bentonville", "types": ["locality"]},
                            {"longText": "Arkansas", "shortText": "AR", "types": ["administrative_area_level_1"]},
                            {"longText": "72712", "shortText": "72712", "types": ["postal_code"]},
                            {"longText": "United States", "shortText": "US", "types": ["country"]},
                        ],
                    }
                ]
            }
            return 200, json.dumps(place).encode(), "application/json"
        if "wbsearchentities" in url:
            return 200, b'{"search":[]}', "application/json"
        return 0, b"", ""

    monkeypatch.setattr("freight.company_lookup.http_request", fake)
    matches = search_companies("Northwind", places_api_key=SECRET)
    assert matches[0]["street"] == "100 Main Street"
    assert matches[0]["suite"] == "Suite 5"
    assert matches[0]["city"] == "Bentonville"
    assert matches[0]["state"] == "AR"
    assert matches[0]["postal"] == "72712"
    assert matches[0]["country"] == "US"
    assert matches[0]["address_source"] == SOURCE_PLACES
    assert matches[0]["website_source"] == SOURCE_PLACES
    assert SECRET not in json.dumps(matches)


def test_places_failure_falls_back_to_wikidata(monkeypatch):
    def fake(method, url, **kwargs):
        if "places.googleapis.com" in url:
            return 403, json.dumps({"error": SECRET}).encode(), "application/json"
        status, body, content_type = _route_wiki(url)
        return status, body, content_type

    monkeypatch.setattr("freight.company_lookup.http_request", fake)
    matches = search_companies("Northwind", places_api_key=SECRET)
    assert matches[0]["address_source"] == SOURCE_WIKIDATA
    assert SECRET not in json.dumps(matches)


def test_http_get_timeout_is_empty(monkeypatch):
    def boom(*_args, **_kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("freight.company_lookup.requests.request", boom)
    assert http_get("https://example.com") == (0, b"", "")


def test_address_formatting_omits_blank_and_default_country():
    assert format_customer_address("", "", "Bentonville", "AR", "72716", "US") == ["Bentonville, AR 72716"]
    assert format_customer_address("702 SW 8th St", "Suite 100", "Bentonville", "ar", "72716", "United States") == [
        "702 SW 8th St, Suite 100",
        "Bentonville, AR 72716",
    ]
    assert format_customer_address("", "", "", "", "", "US") == []
    assert format_customer_address("", "", "", "", "", "") == []
    assert format_customer_address("1 King St", "", "Toronto", "ON", "M5H", "Canada") == [
        "1 King St",
        "Toronto, ON M5H",
        "Canada",
    ]
    document = build_customer_quote(
        {
            "company": "Northwind",
            "shipment": SHIPMENT,
            "options": [{"carrier_name": "Carrier", "customer_total": 10, "charges": []}],
            "address": {"street": "100 Main Street", "city": "Bentonville", "state": "AR", "postal": "72712", "country": "US"},
            "website": "https://cdn.example/secret-logo.png",
        }
    )
    serialized = json.dumps(document).lower()
    assert document["address_lines"] == ["100 Main Street", "Bentonville, AR 72712"]
    assert "cdn.example" not in serialized
    assert "http" not in serialized
