"""Look up a customer company from its name.

No API key is required. The chain is Wikidata, then the company homepage
(schema.org PostalAddress and logo), then icon and favicon fallbacks.
Google Places is used first for the address and website only when
GOOGLE_PLACES_API_KEY is set. A domain is never invented from the name.
"""

from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlencode, urljoin, urlparse

import requests
from PIL import Image

USER_AGENT = "EasyPostFreightDesk/1.0"
CONNECT_TIMEOUT = 2
READ_TIMEOUT = 4
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

SOURCE_WIKIDATA = "Wikidata"
SOURCE_PLACES = "Google Places"
SOURCE_SITE = "company website"
SOURCE_APPLE = "apple-touch-icon"
SOURCE_ICON = "site icon"
SOURCE_WIKIMEDIA = "Wikimedia"
SOURCE_GOOGLE_FAVICON = "Google favicon"
SOURCE_DDG = "DuckDuckGo favicon"
FAVICON_SOURCES = {SOURCE_GOOGLE_FAVICON, SOURCE_DDG}

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
PLACES_SEARCH = "https://places.googleapis.com/v1/places:searchText"
DISAMBIGUATION_QID = "Q4167410"

_SKIP_HOSTS = ("wikipedia.org", "wikidata.org", "wikimedia.org", "google.com", "g.page")

US_STATES = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}
_STATE_BY_NAME = {name.lower(): abbr for name, abbr in US_STATES.items()}
_STATE_ABBR = set(US_STATES.values())


def normalize_domain(value: str | None) -> str | None:
    """Return a bare host, or None. Does not guess a domain from a company name."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text or any(char.isspace() for char in text):
        return None
    if "://" not in text:
        text = "https://" + text.lstrip("/")
    host = (urlparse(text).hostname or "").strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        return None
    labels = host.split(".")
    if len(labels) < 2 or any(not label or len(label) > 63 for label in labels):
        return None
    if len(labels[-1]) < 2 or not re.search(r"[a-z]", host):
        return None
    return host


def http_request(method: str, url: str, *, headers: dict | None = None, data: bytes | None = None, timeout: tuple[float, float] = TIMEOUT) -> tuple[int, bytes, str]:
    """GET or POST. Timeouts and transport errors become an empty result."""
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            data=data,
            timeout=timeout,
            allow_redirects=True,
        )
        content_type = response.headers.get("Content-Type", "")
        return response.status_code, response.content or b"", content_type
    except requests.RequestException:
        return 0, b"", ""


def http_get(url: str, *, headers: dict | None = None, timeout: tuple[float, float] = TIMEOUT) -> tuple[int, bytes, str]:
    return http_request("GET", url, headers=headers, timeout=timeout)


def image_to_png(data: bytes, *, source: str = "") -> bytes | None:
    """Convert a fetched image to a clean PNG. Reject tiny, blank, or banner images."""
    if not data or len(data) < 32:
        return None
    head = data[:200].lstrip().lower()
    if head.startswith(b"<svg") or head.startswith(b"<?xml") or b"<svg" in head[:80]:
        return None
    image = _open_image(data)
    if image is None:
        return None
    width, height = image.size
    if source == "og:image" and (width > 1200 or height <= 0 or width / height > 2.2):
        return None
    if min(width, height) < 32:
        return None
    image = image.convert("RGBA")
    if _is_blank(image):
        return None
    image.thumbnail((256, 256))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def search_companies(name: str, places_api_key: str = "") -> list[dict]:
    """Candidate matches for a company name. No logo bytes."""
    cleaned = re.sub(r"\s+", " ", name or "").strip()
    if len(cleaned) < 2:
        return []
    wiki = _wikidata_candidates(cleaned)
    places_key = (places_api_key or "").strip()
    places = _places_candidates(cleaned, places_key) if places_key else []
    if not places:
        return _label_candidates(_strong(wiki))[:5]
    merged: list[dict] = []
    used: set[int] = set()
    for place in places:
        match = next((item for item in wiki if _same_company(place, item)), None)
        if match is not None:
            used.add(id(match))
            _fill_gaps(place, match)
        merged.append(place)
    for item in wiki:
        if id(item) not in used:
            merged.append(item)
    return _label_candidates(_strong(merged))[:5]


def enrich_candidate(candidate: dict) -> dict:
    """Fill logo bytes and any address the search did not already have."""
    result = {
        "name": _plain(candidate.get("name"), 120),
        "label": _plain(candidate.get("label"), 180),
        "qid": _plain(candidate.get("qid"), 20),
        "domain": normalize_domain(candidate.get("domain") or candidate.get("website") or ""),
        "website": "",
        "street": _plain(candidate.get("street"), 120),
        "suite": _plain(candidate.get("suite"), 40),
        "city": _plain(candidate.get("city"), 60),
        "state": _state_abbrev(_plain(candidate.get("state"), 40)) or _plain(candidate.get("state"), 40),
        "postal": _plain(candidate.get("postal"), 16),
        "country": _country_code(_plain(candidate.get("country"), 40)),
        "website_source": _plain(candidate.get("website_source"), 40),
        "address_source": _plain(candidate.get("address_source"), 80),
        "logo_source": "",
        "logo_png": None,
    }
    website = _plain(candidate.get("website"), 300)
    domain = result["domain"]
    if domain and not _skipped_host(domain):
        result["domain"] = domain
        result["website"] = website if normalize_domain(website) == domain else f"https://{domain}"
    else:
        result["domain"] = ""
        result["website"] = ""
        result["website_source"] = ""
    if result["state"] in _STATE_ABBR and not result["country"]:
        result["country"] = "US"
    page_assets: dict = {}
    if result["domain"]:
        page_assets = _enrich_from_site(result)
    logo, logo_source = _best_logo(candidate.get("logo_filename") or "", result["domain"], page_assets)
    result["logo_png"] = logo
    result["logo_source"] = logo_source
    return result


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8", "Accept-Language": "en"}


def _plain(value: object, limit: int = 120) -> str:
    if not isinstance(value, str):
        return ""
    text = unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _json_body(status: int, body: bytes) -> dict | None:
    if status != 200 or not body:
        return None
    try:
        parsed = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _open_image(data: bytes) -> Image.Image | None:
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception:
        return None
    if image.format == "ICO" and hasattr(image, "ico"):
        try:
            sizes = list(image.ico.sizes())
            if sizes:
                largest = max(sizes, key=lambda size: size[0] * size[1])
                frame = image.ico.getimage(largest)
                frame.load()
                return frame
        except Exception:
            return image
    return image


def _is_blank(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    if alpha.getextrema()[1] < 10:
        return True
    pixels = image.size[0] * image.size[1]
    if pixels and alpha.histogram()[0] / pixels > 0.98:
        return True
    sample = image.convert("RGB").resize((24, 24))
    colors = sample.getcolors(576) or []
    if not colors:
        return True
    colors.sort(reverse=True)
    return colors[0][0] / (24 * 24) > 0.98


def _logo_area(png: bytes, source: str) -> float:
    image = Image.open(BytesIO(png))
    area = image.size[0] * image.size[1]
    if source in FAVICON_SOURCES:
        area *= 0.25
    return area


def _state_abbrev(value: str) -> str:
    text = _plain(value, 40)
    if not text:
        return ""
    if text.upper() in _STATE_ABBR and len(text) == 2:
        return text.upper()
    return _STATE_BY_NAME.get(text.lower(), "")


def _country_code(value: str) -> str:
    text = _plain(value, 60)
    if not text:
        return ""
    lowered = text.lower().rstrip(".")
    if lowered in {"us", "usa", "united states", "united states of america"}:
        return "US"
    if len(text) == 2 and text.isalpha():
        return text.upper()
    return text


def _skipped_host(domain: str) -> bool:
    return any(domain == host or domain.endswith("." + host) for host in _SKIP_HOSTS)


def _note_source(current: str, source: str) -> str:
    if not source:
        return current
    if not current:
        return source
    if source in current:
        return current
    return f"{current} + {source}"


def _empty_candidate(name: str, *, source: str = "") -> dict:
    return {
        "name": name,
        "qid": "",
        "domain": "",
        "website": "",
        "street": "",
        "suite": "",
        "city": "",
        "state": "",
        "postal": "",
        "country": "",
        "website_source": "",
        "address_source": "",
        "logo_filename": "",
        "rank": 0,
        "label": "",
    }


def _choice_label(candidate: dict) -> str:
    place = ", ".join(part for part in (candidate.get("city") or "", candidate.get("state") or "") if part)
    parts = [candidate.get("name") or "Company"]
    if place:
        parts.append(place)
    if candidate.get("domain"):
        parts.append(candidate["domain"])
    return " — ".join(parts)


def _label_candidates(candidates: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    labeled = []
    for candidate in candidates:
        base = _choice_label(candidate)
        seen[base] = seen.get(base, 0) + 1
        item = dict(candidate)
        item.pop("_hq", None)
        item.pop("_description", None)
        item["label"] = base if seen[base] == 1 else f"{base} ({seen[base]})"
        labeled.append(item)
    return labeled


def _strong(candidates: list[dict]) -> list[dict]:
    useful = [item for item in candidates if item.get("domain") or item.get("city")]
    return useful or candidates


def _is_county(label: str) -> bool:
    lowered = f" {label.lower()} "
    return any(token in lowered for token in (" county", " parish", " borough", " census area"))


def _is_place_description(description: str) -> bool:
    text = description.lower()
    return any(
        token in text
        for token in (
            "town in",
            "city in",
            "village in",
            "county in",
            "census-designated",
            "neighborhood",
            "municipality",
            "unincorporated",
            "township",
        )
    )


def _is_business_description(description: str) -> bool:
    text = description.lower()
    return any(token in text for token in ("company", "retailer", "brand", "corporation", "business", "manufacturer", "chain"))


def _same_company(left: dict, right: dict) -> bool:
    if left.get("domain") and left.get("domain") == right.get("domain"):
        return True
    left_name = re.sub(r"[^a-z0-9]", "", (left.get("name") or "").lower())
    right_name = re.sub(r"[^a-z0-9]", "", (right.get("name") or "").lower())
    if not left_name or not right_name:
        return False
    if left_name == right_name:
        return True
    short, long = sorted((left_name, right_name), key=len)
    return len(short) >= 5 and long.startswith(short)


def _fill_gaps(target: dict, extra: dict) -> None:
    if not target.get("domain") and extra.get("domain"):
        target["domain"] = extra["domain"]
        target["website"] = extra.get("website") or f"https://{extra['domain']}"
        target["website_source"] = extra.get("website_source") or target.get("website_source") or ""
    if not target.get("logo_filename") and extra.get("logo_filename"):
        target["logo_filename"] = extra["logo_filename"]
    filled = False
    for field in ("street", "suite", "city", "state", "postal", "country"):
        if not target.get(field) and extra.get(field):
            target[field] = extra[field]
            filled = True
    if filled:
        target["address_source"] = _note_source(target.get("address_source") or "", extra.get("address_source") or SOURCE_WIKIDATA)


def _fetch_entities(qids: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    pending = [qid for qid in dict.fromkeys(qids) if qid]
    while pending:
        batch, pending = pending[:50], pending[50:]
        query = urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims|labels|descriptions",
                "languages": "en",
                "format": "json",
            }
        )
        payload = _json_body(*http_get(f"{WIKIDATA_API}?{query}", headers=_headers())[:2])
        if not payload:
            continue
        for qid, entity in (payload.get("entities") or {}).items():
            if isinstance(entity, dict) and "missing" not in entity:
                found[qid] = entity
    return found


def _fetch_admin_chain(entities: dict[str, dict], start_ids: list[str]) -> None:
    """Load headquarters and up to three located-in hops."""
    pending = [qid for qid in start_ids if qid and qid not in entities]
    for _hop in range(4):
        if not pending:
            return
        loaded = _fetch_entities(pending)
        entities.update(loaded)
        next_ids = []
        for qid in pending:
            entity = entities.get(qid) or {}
            for claim in _claims(entity, "P131"):
                parent = _entity_id(claim)
                if parent and parent not in entities:
                    next_ids.append(parent)
        pending = list(dict.fromkeys(next_ids))


def _claims(entity: dict, pid: str) -> list[dict]:
    claims = (entity.get("claims") or {}).get(pid) or []
    if not isinstance(claims, list):
        return []
    preferred = [claim for claim in claims if claim.get("rank") == "preferred"]
    return preferred or claims


def _entity_id(claim: dict) -> str:
    value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
    if isinstance(value, dict):
        qid = value.get("id")
        return qid if isinstance(qid, str) else ""
    return ""


def _snak_text(snak: dict) -> str:
    value = (snak.get("datavalue") or {}).get("value")
    if isinstance(value, str):
        return _plain(value, 160)
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return _plain(value["text"], 160)
    return ""


def _claim_text(entity: dict, pid: str) -> str:
    for claim in _claims(entity, pid):
        text = _snak_text(claim.get("mainsnak") or {})
        if text:
            return text
    return ""


def _qualifier_text(claim: dict, pid: str) -> str:
    for snak in (claim.get("qualifiers") or {}).get(pid) or []:
        text = _snak_text(snak)
        if text:
            return text
    return ""


def _entity_label(entity: dict) -> str:
    label = ((entity.get("labels") or {}).get("en") or {}).get("value")
    return _plain(label, 120) if isinstance(label, str) else ""


def _is_disambiguation(entity: dict) -> bool:
    description = ((entity.get("descriptions") or {}).get("en") or {}).get("value")
    if isinstance(description, str) and "disambiguation" in description.lower():
        return True
    return any(_entity_id(claim) == DISAMBIGUATION_QID for claim in _claims(entity, "P31"))


def _candidate_from_entity(entity: dict, hit: dict) -> dict:
    candidate = _empty_candidate(hit.get("label") or _entity_label(entity) or "Company")
    candidate["qid"] = hit.get("id") or ""
    candidate["rank"] = hit.get("rank", 0)
    candidate["name"] = _entity_label(entity) or candidate["name"]
    website = _claim_text(entity, "P856")
    domain = normalize_domain(website)
    if domain and not _skipped_host(domain):
        candidate["website"] = website
        candidate["domain"] = domain
        candidate["website_source"] = SOURCE_WIKIDATA
    filename = _claim_text(entity, "P154")
    if filename:
        candidate["logo_filename"] = filename
    hq_claim = next((claim for claim in _claims(entity, "P159") if _entity_id(claim)), None)
    street = _qualifier_text(hq_claim, "P6375") if hq_claim else ""
    postal = _qualifier_text(hq_claim, "P281") if hq_claim else ""
    if not street:
        street = _claim_text(entity, "P6375")
    if not postal:
        postal = _claim_text(entity, "P281")
    candidate["street"] = street
    candidate["postal"] = postal
    candidate["_hq"] = _entity_id(hq_claim) if hq_claim else ""
    return candidate


def _wikidata_candidates_finalize(candidates: list[dict], entities: dict[str, dict]) -> None:
    for candidate in candidates:
        hq_id = candidate.pop("_hq", "")
        hq = entities.get(hq_id) or {}
        city, state, country, hq_street, hq_postal = _place_from_hq(hq, entities)
        if not candidate["street"]:
            candidate["street"] = hq_street
        if not candidate["postal"]:
            candidate["postal"] = hq_postal
        candidate["city"] = city
        candidate["state"] = state
        candidate["country"] = country or ("US" if state in _STATE_ABBR else "")
        if candidate["street"] and candidate["city"] and "," in candidate["street"] and candidate["city"].lower() in candidate["street"].lower():
            candidate["street"] = candidate["street"].split(",")[0].strip()
        if candidate["city"] or candidate["street"] or candidate["postal"]:
            candidate["address_source"] = SOURCE_WIKIDATA


def _place_from_hq(hq: dict, entities: dict[str, dict]) -> tuple[str, str, str, str, str]:
    if not hq:
        return "", "", "", "", ""
    admins: list[str] = []
    current = hq
    seen = set()
    for _hop in range(3):
        parent_id = next((_entity_id(claim) for claim in _claims(current, "P131") if _entity_id(claim)), "")
        if not parent_id or parent_id in seen or parent_id not in entities:
            break
        seen.add(parent_id)
        current = entities[parent_id]
        label = _entity_label(current)
        if label:
            admins.append(label)
    city = ""
    state = ""
    country = ""
    for label in admins:
        if label.lower().startswith("united states"):
            country = "US"
        abbrev = _state_abbrev(label)
        if abbrev and not state:
            state = abbrev
    hq_label = _entity_label(hq)
    facility = any(word in hq_label.lower() for word in ("office", "headquarters", "building", "campus", "center", "centre", "store", "supercenter"))
    if hq_label and not facility and not _is_county(hq_label) and not _state_abbrev(hq_label):
        city = hq_label
    else:
        for label in admins:
            if _state_abbrev(label) or _is_county(label) or label.lower().startswith("united states"):
                continue
            city = label
            break
        if not city and hq_label and not _is_county(hq_label) and not _state_abbrev(hq_label):
            city = hq_label
    if not country:
        for label in reversed(admins):
            if label.lower().startswith("united states"):
                country = "US"
                break
        if not country and state:
            country = "US"
        elif not country and admins:
            country = _country_code(admins[-1])
    if city and _state_abbrev(city):
        city = ""
    street = _claim_text(hq, "P6375")
    postal = _claim_text(hq, "P281")
    return city, state, country, street, postal


def _places_candidates(name: str, api_key: str) -> list[dict]:
    body = json.dumps({"textQuery": name, "maxResultCount": 5, "languageCode": "en"}).encode()
    status, raw, _ctype = http_request(
        "POST",
        PLACES_SEARCH,
        headers={
            **_headers(),
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.websiteUri,places.formattedAddress,places.addressComponents,places.id",
        },
        data=body,
    )
    payload = _json_body(status, raw)
    if not payload:
        return []
    candidates = []
    for rank, place in enumerate(payload.get("places") or []):
        if not isinstance(place, dict):
            continue
        candidate = _candidate_from_place(place, rank)
        if candidate["name"]:
            candidates.append(candidate)
    return candidates


def _component_text(component: dict, short: bool = False) -> str:
    if short:
        value = component.get("shortText") or component.get("short_name") or component.get("longText") or component.get("long_name") or ""
    else:
        value = component.get("longText") or component.get("long_name") or component.get("shortText") or component.get("short_name") or ""
    return _plain(value, 120)


def _candidate_from_place(place: dict, rank: int) -> dict:
    display = place.get("displayName")
    if isinstance(display, dict):
        name = _plain(display.get("text"), 120)
    else:
        name = _plain(display, 120)
    candidate = _empty_candidate(name or "Company")
    candidate["rank"] = rank
    candidate["qid"] = _plain(place.get("id"), 80)
    website = _plain(place.get("websiteUri"), 300)
    domain = normalize_domain(website)
    if domain and not _skipped_host(domain):
        candidate["website"] = website
        candidate["domain"] = domain
        candidate["website_source"] = SOURCE_PLACES
    parts: dict[str, str] = {}
    for component in place.get("addressComponents") or []:
        if not isinstance(component, dict):
            continue
        types = component.get("types") or []
        if not isinstance(types, list):
            continue
        for kind in types:
            if kind not in parts:
                parts[kind] = _component_text(component, short=kind in {"administrative_area_level_1", "country"})
    number = parts.get("street_number", "")
    route = parts.get("route", "")
    if number and route and not route.startswith(number):
        street = f"{number} {route}"
    else:
        street = route or number
    postal = parts.get("postal_code", "")
    suffix = parts.get("postal_code_suffix", "")
    if postal and suffix:
        postal = f"{postal}-{suffix}"
    candidate["street"] = _plain(street, 120)
    candidate["suite"] = parts.get("subpremise", "")
    candidate["city"] = parts.get("locality") or parts.get("postal_town") or ""
    candidate["state"] = _state_abbrev(parts.get("administrative_area_level_1", "")) or parts.get("administrative_area_level_1", "")
    candidate["postal"] = postal
    candidate["country"] = _country_code(parts.get("country", ""))
    if candidate["state"] in _STATE_ABBR and not candidate["country"]:
        candidate["country"] = "US"
    if not candidate["street"] and not candidate["city"]:
        formatted = _plain(place.get("formattedAddress"), 160)
        if formatted:
            candidate["street"] = formatted
    if candidate["street"] or candidate["city"] or candidate["postal"]:
        candidate["address_source"] = SOURCE_PLACES
    return candidate


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.icons: list[tuple[str, str, str]] = []
        self.og_image = ""
        self.blocks: list[str] = []
        self._capture = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "link":
            rel = values.get("rel", "").lower()
            href = values.get("href", "")
            if href and "icon" in rel:
                self.icons.append((rel, href, values.get("sizes", "")))
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key == "og:image" and not self.og_image:
                self.og_image = values.get("content", "")
        if tag == "script" and "ld+json" in values.get("type", "").lower():
            self._capture = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            self.blocks.append("".join(self._buffer))
            self._capture = False


def _parse_page(html: str, base_url: str) -> dict:
    parser = _PageParser()
    try:
        parser.feed(html[:800_000])
        parser.close()
    except Exception:
        pass
    apples: list[tuple[int, str]] = []
    icons: list[tuple[int, str]] = []
    for rel, href, sizes in parser.icons:
        if "mask-icon" in rel or href.startswith("data:"):
            continue
        url = urljoin(base_url, href)
        area = _icon_area(sizes)
        if "apple-touch-icon" in rel:
            apples.append((area, url))
        elif "icon" in rel:
            icons.append((area, url))
    address = {"street": "", "suite": "", "city": "", "state": "", "postal": "", "country": ""}
    logos: list[str] = []
    for block in parser.blocks:
        _read_jsonld(block, address, logos, base_url)
    return {
        "apple": _best_urls(apples),
        "icons": _best_urls(icons),
        "og_image": urljoin(base_url, parser.og_image) if parser.og_image and not parser.og_image.startswith("data:") else "",
        "logos": logos[:3],
        "address": address,
    }


def _icon_area(sizes: str) -> int:
    match = re.search(r"(\d+)\s*x\s*(\d+)", sizes or "")
    if match:
        return int(match.group(1)) * int(match.group(2))
    if "any" in (sizes or "").lower():
        return 512 * 512
    return 0


def _best_urls(pairs: list[tuple[int, str]]) -> list[str]:
    ordered = sorted(pairs, key=lambda item: item[0], reverse=True)
    urls = []
    for _area, url in ordered:
        if url not in urls:
            urls.append(url)
        if len(urls) == 2:
            break
    return urls


def _read_jsonld(block: str, address: dict, logos: list[str], base_url: str) -> None:
    try:
        payload = json.loads(block)
    except json.JSONDecodeError:
        return
    nodes = list(_iter_nodes(payload))
    orgs = [node for node in nodes if _is_org(node)]
    targets = orgs or nodes
    for node in targets:
        if not address["street"]:
            _read_address(node.get("address"), address)
        logo = _logo_url(node.get("logo"))
        if logo and _is_org(node):
            absolute = urljoin(base_url, logo)
            if absolute not in logos and not absolute.startswith("data:"):
                logos.append(absolute)
    if not address["street"]:
        for node in nodes:
            types = _types(node)
            if "postaladdress" in types:
                _read_address(node, address)
                if address["street"]:
                    break


def _iter_nodes(payload: object):
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_nodes(item)
        return
    if isinstance(payload, dict):
        yield payload
        if payload.get("@graph") is not None:
            yield from _iter_nodes(payload.get("@graph"))


def _types(node: dict) -> set[str]:
    raw = node.get("@type") or []
    if isinstance(raw, str):
        raw = [raw]
    found = set()
    for item in raw:
        if isinstance(item, str):
            found.add(item.split("/")[-1].split(":")[-1].lower())
    return found


def _is_org(node: dict) -> bool:
    for name in _types(node):
        if name in {"organization", "localbusiness", "corporation", "store"} or name.endswith("business") or "organization" in name:
            return True
    return False


def _read_address(value: object, address: dict) -> None:
    if isinstance(value, list):
        for item in value:
            _read_address(item, address)
            if address["street"]:
                return
        return
    if isinstance(value, str) and not address["street"]:
        address["street"] = _plain(value, 120)
        return
    if not isinstance(value, dict):
        return
    street = _plain(value.get("streetAddress"), 120) if isinstance(value.get("streetAddress"), str) else ""
    if street and not address["street"]:
        address["street"] = street
    mapping = (
        ("city", "addressLocality"),
        ("state", "addressRegion"),
        ("postal", "postalCode"),
        ("suite", "postOfficeBoxNumber"),
    )
    for field, key in mapping:
        if not address[field]:
            text = value.get(key)
            if isinstance(text, str):
                address[field] = _state_abbrev(text) or _plain(text, 60) if field == "state" else _plain(text, 60)
    if not address["country"]:
        address["country"] = _country_code(_text_value(value.get("addressCountry")))


def _text_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "text", "value"):
            if isinstance(value.get(key), str):
                return value[key]
    if isinstance(value, list) and value:
        return _text_value(value[0])
    return ""


def _logo_url(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            found = _logo_url(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("url", "contentUrl"):
            if isinstance(value.get(key), str):
                return value[key].strip()
    return ""


def _enrich_from_site(result: dict) -> dict:
    host, homepage = _fetch_html(result["domain"])
    assets = {"apple": [], "icons": [], "og_image": "", "logos": [], "address": {}}
    if homepage:
        assets = _parse_page(homepage, f"https://{host}/")
        _apply_site_address(result, assets["address"])
    if not result["street"]:
        for suffix in ("contact", "about"):
            page = _fetch_html_url(f"https://{host}/{suffix}")
            if not page:
                continue
            extra = _parse_page(page, f"https://{host}/")
            _apply_site_address(result, extra["address"])
            if result["street"]:
                break
    return assets


def _apply_site_address(result: dict, address: dict) -> None:
    if not address:
        return
    filled = False
    for field in ("street", "suite", "city", "state", "postal", "country"):
        value = address.get(field) or ""
        if field == "state":
            value = _state_abbrev(value) or value
        if field == "country":
            value = _country_code(value)
        if value and not result.get(field):
            result[field] = value
            filled = True
    if result.get("state") in _STATE_ABBR and not result.get("country"):
        result["country"] = "US"
    if filled:
        result["address_source"] = _note_source(result.get("address_source") or "", SOURCE_SITE)


def _fetch_html(domain: str) -> tuple[str, str]:
    for host in (domain, f"www.{domain}"):
        html = _fetch_html_url(f"https://{host}/")
        if html:
            return host, html
    return domain, ""


def _fetch_html_url(url: str) -> str:
    status, body, content_type = http_get(url, headers=_headers())
    if status != 200 or not body:
        return ""
    sample = body[:600].lstrip().lower()
    if "html" not in content_type.lower() and not sample.startswith(b"<!doctype") and not sample.startswith(b"<html") and b"<html" not in sample:
        return ""
    return body[:800_000].decode("utf-8", errors="replace")


def _best_logo(filename: str, domain: str, assets: dict) -> tuple[bytes | None, str]:
    found: list[tuple[float, int, bytes, str]] = []

    def consider(raw: bytes, source: str) -> None:
        decode_as = "og:image" if source == "og:image" else source
        png = image_to_png(raw, source=decode_as)
        if not png:
            return
        label = SOURCE_SITE if source == "og:image" else source
        # A real logo wins a tie with an upscaled favicon of the same adjusted area.
        priority = 1 if label in FAVICON_SOURCES else 0
        found.append((_logo_area(png, label), -priority, png, label))

    thumb = _commons_thumb(filename) if filename else ""
    if thumb:
        consider(_fetch_bytes(thumb), SOURCE_WIKIMEDIA)
    for url in assets.get("logos") or []:
        consider(_fetch_bytes(url), SOURCE_SITE)
    for url in assets.get("apple") or []:
        consider(_fetch_bytes(url), SOURCE_APPLE)
    for url in assets.get("icons") or []:
        consider(_fetch_bytes(url), SOURCE_ICON)
    if assets.get("og_image"):
        consider(_fetch_bytes(assets["og_image"]), "og:image")
    best_real = max((area for area, _priority, _png, source in found if source not in FAVICON_SOURCES), default=0)
    # A real 128px icon already beats a 256px favicon service image after the 0.25 weight.
    if domain and best_real < 128 * 128:
        consider(_fetch_bytes(f"https://www.google.com/s2/favicons?domain={domain}&sz=256"), SOURCE_GOOGLE_FAVICON)
        if not any(source == SOURCE_GOOGLE_FAVICON for _area, _priority, _png, source in found):
            consider(_fetch_bytes(f"https://icons.duckduckgo.com/ip3/{domain}.ico"), SOURCE_DDG)
    if not found:
        return None, ""
    _area, _priority, png, source = max(found, key=lambda item: (item[0], item[1]))
    return png, source


def _fetch_bytes(url: str) -> bytes:
    if not url or url.startswith("data:"):
        return b""
    status, body, content_type = http_get(url, headers=_headers())
    if status != 200 or not body or "svg" in content_type.lower():
        return b""
    return body


def _commons_thumb(filename: str) -> str:
    title = filename if filename.lower().startswith("file:") else f"File:{filename}"
    query = urlencode(
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 256,
            "format": "json",
        }
    )
    payload = _json_body(*http_get(f"{COMMONS_API}?{query}", headers=_headers())[:2])
    if not payload:
        return ""
    pages = ((payload.get("query") or {}).get("pages") or {})
    page_list = pages.values() if isinstance(pages, dict) else pages
    for page in page_list:
        if not isinstance(page, dict):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        thumb = info.get("thumburl") or ""
        if thumb:
            return thumb
        original = info.get("url") or ""
        if original and not original.lower().split("?")[0].endswith(".svg"):
            return original
    return ""


# The HQ id is stashed on the candidate while entities are still in scope.
# Fold that resolution into the search so enrich never sees the private key.
def _wikidata_candidates(name: str) -> list[dict]:
    query = urlencode(
        {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "limit": 5,
            "type": "item",
            "format": "json",
        }
    )
    payload = _json_body(*http_get(f"{WIKIDATA_API}?{query}", headers=_headers())[:2])
    if not payload:
        return []
    hits = []
    for rank, hit in enumerate(payload.get("search") or []):
        if not isinstance(hit, dict) or not hit.get("id"):
            continue
        description = _plain(hit.get("description"), 200).lower()
        if "disambiguation" in description:
            continue
        hits.append(
            {
                "id": str(hit["id"]),
                "label": _plain(hit.get("label"), 120) or name,
                "description": description,
                "rank": rank,
            }
        )
    if not hits:
        return []
    entities = _fetch_entities([hit["id"] for hit in hits])
    hq_ids = []
    usable = []
    for hit in hits:
        entity = entities.get(hit["id"]) or {}
        if not entity or _is_disambiguation(entity):
            continue
        usable.append((hit, entity))
        for claim in _claims(entity, "P159"):
            qid = _entity_id(claim)
            if qid:
                hq_ids.append(qid)
    _fetch_admin_chain(entities, hq_ids)
    candidates = []
    for hit, entity in usable:
        candidate = _candidate_from_entity(entity, hit)
        candidates.append(candidate)
    _wikidata_candidates_finalize(candidates, entities)
    for candidate, (hit, _entity) in zip(candidates, usable):
        candidate["_description"] = hit.get("description") or ""
    candidates.sort(key=_candidate_sort_key)
    return candidates


def _candidate_sort_key(item: dict) -> tuple:
    description = item.get("_description") or ""
    place = _is_place_description(description)
    business = _is_business_description(description)
    return (
        0 if item.get("domain") else 1,
        0 if business and not place else 1,
        1 if place else 0,
        item.get("rank", 0),
    )
