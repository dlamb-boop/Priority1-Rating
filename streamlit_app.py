"""EasyPost freight quote desk. Entry point for Streamlit Community Cloud."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from freight.accessorials import ACCESSORIALS, code_from_label, option_label
from freight.company_lookup import enrich_candidate, image_to_png, lookup_by_website, merge_website_lookup, search_companies
from freight.config import get_config, read_setting
from freight.constants import EQUIPMENT_LABELS, EQUIPMENT_TYPES, FREIGHT_CLASSES, PACKAGING_TYPES
from freight.customer import build_customer_quote, format_customer_address, to_customer_rate
from freight.preparers import ADD_PREPARER, apply_preparer_choice, load_preparers, preparer_options
from freight.markup import MARKUP_DEFAULT, MARKUP_MAX, MARKUP_MIN
from freight.pdf_quote import filename_for, render_customer_pdf
from freight.quote import public_error, quote_ltl, quote_tl, suggest_class

ROOT = Path(__file__).resolve().parent
LOGO = ROOT / "assets" / "easypost-logo.png"
ICON = ROOT / "assets" / "easypost-icon.png"

st.set_page_config(
    page_title="EasyPost Freight Quotes",
    page_icon=str(ICON),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
    html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {
      font-family: Poppins, "Segoe UI", sans-serif;
    }
    .stApp { background: #FFFFFF; }
    [data-testid="stSidebar"] { background: #E8EDFF; }
    [data-testid="stHeader"] { background: transparent; }
    .ep-kicker {
      color: #164DFF;
      font-weight: 600;
      letter-spacing: 0.08em;
      font-size: 0.75rem;
      margin: 0;
    }
    .ep-title {
      color: #061242;
      font-weight: 700;
      font-size: 2rem;
      line-height: 1.15;
      margin: 0.15rem 0 0.35rem;
    }
    .ep-sub { color: #3C4A78; margin: 0 0 0.6rem; }
    .ep-chip {
      display: inline-block;
      background: #CBF9EE;
      color: #061242;
      border-radius: 999px;
      padding: 0.2rem 0.7rem;
      font-weight: 600;
      font-size: 0.8rem;
    }
    div[data-testid="stButton"] > button[kind="primary"],
    div[data-testid="stDownloadButton"] > button {
      background: #164DFF;
      color: white;
      border: none;
      border-radius: 10px;
      font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _next_business_day(today: date | None = None) -> date:
    cursor = (today or date.today()) + timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor += timedelta(days=1)
    return cursor


def _boot() -> None:
    ss = st.session_state
    if ss.get("_booted"):
        return
    ss._booted = True
    ss._seq = 1
    ss.customer_name = ""
    ss.company = ""
    ss.origin_zip = ""
    ss.origin_city = ""
    ss.origin_state = ""
    ss.dest_zip = ""
    ss.dest_city = ""
    ss.dest_state = ""
    ss.pickup = _next_business_day()
    ss.markup = float(MARKUP_DEFAULT)
    ss.item_ids = ["item1"]
    ss.class_item1 = "70"
    ss.pack_item1 = "Pallet"
    ss.units_item1 = 1
    ss.pieces_item1 = 1
    ss.weight_item1 = 500
    ss.length_item1 = 48
    ss.width_item1 = 40
    ss.height_item1 = 48
    ss.desc_item1 = ""
    ss.stack_item1 = False
    ss.haz_item1 = False
    ss.used_item1 = False
    ss.mach_item1 = False
    ss.nmfc_item1 = ""
    ss.sub_item1 = ""
    ss.accessorials = []
    ss.show_internal_ltl = False
    ss.show_internal_tl = False
    ss.show_partner_ltl = False
    ss.show_partner_tl = False
    ss.ltl_quote = None
    ss.tl_equipment = "53_Foot_Dry_Van"
    ss.tl_service = "Full"
    ss.tl_weight = 18000
    ss.tl_pallets = 20
    ss.tl_desc = ""
    ss.tl_lift = False
    ss.tl_quote = None
    ss.preparer_choice = ""
    ss.preparer_name = ""
    ss.preparer_title = ""
    ss.preparer_email = ""
    ss.preparer_custom_name = ""
    ss.preparer_custom_title = ""
    ss.preparer_custom_email = ""
    ss.company_name_from_lookup = False
    _reset_customer_details(ss)
    ss.company_candidates = []
    ss.lookup_message = ""
    ss.logo_upload_generation = 0


def _reset_customer_details(ss) -> None:
    ss.company_website = ""
    ss.customer_street = ""
    ss.customer_suite = ""
    ss.customer_city = ""
    ss.customer_state = ""
    ss.customer_postal = ""
    ss.customer_country = "US"
    ss.customer_logo_png = None
    ss.customer_logo_off = False
    ss.customer_logo_source = ""
    ss.customer_address_source = ""
    ss.customer_website_source = ""
    ss.customer_hand_edited = set()


def _ensure_customer_keys() -> None:
    ss = st.session_state
    if "company_website" not in ss:
        _reset_customer_details(ss)
    ss.setdefault("company_candidates", [])
    ss.setdefault("lookup_message", "")
    ss.setdefault("logo_upload_generation", 0)
    ss.setdefault("customer_logo_png", None)
    ss.setdefault("company_name_from_lookup", False)
    ss.setdefault("customer_hand_edited", set())


def _load_sample() -> None:
    ss = st.session_state
    ss.customer_name = "Alex Chen"
    ss.company = "Northwind Goods"
    ss.origin_zip = "72205"
    ss.origin_city = "Little Rock"
    ss.origin_state = "AR"
    ss.dest_zip = "60606"
    ss.dest_city = "Chicago"
    ss.dest_state = "IL"
    ss.pickup = _next_business_day()
    ss.markup = float(MARKUP_DEFAULT)
    ss.accessorials = [option_label("LGPU"), option_label("APPT")]
    ss.item_ids = ["item1"]
    ss.class_item1 = "70"
    ss.pack_item1 = "Pallet"
    ss.units_item1 = 1
    ss.pieces_item1 = 1
    ss.weight_item1 = 500
    ss.length_item1 = 48
    ss.width_item1 = 40
    ss.height_item1 = 48
    ss.desc_item1 = "Packaged hardware"
    ss.stack_item1 = False
    ss.haz_item1 = False
    ss.used_item1 = False
    ss.mach_item1 = False
    ss.nmfc_item1 = ""
    ss.sub_item1 = ""
    ss.tl_weight = 18000
    ss.tl_pallets = 20
    ss.tl_desc = "Packaged hardware"
    ss.tl_equipment = "53_Foot_Dry_Van"
    _reset_customer_details(ss)
    ss.company_name_from_lookup = False
    ss.company_candidates = []
    ss.lookup_message = ""
    ss.logo_upload_generation = int(ss.get("logo_upload_generation") or 0) + 1


def _add_item() -> None:
    st.session_state._seq += 1
    iid = f"item{st.session_state._seq}"
    st.session_state.item_ids.append(iid)
    st.session_state[f"class_{iid}"] = "70"
    st.session_state[f"pack_{iid}"] = "Pallet"
    st.session_state[f"units_{iid}"] = 1
    st.session_state[f"pieces_{iid}"] = 1
    st.session_state[f"weight_{iid}"] = 500
    st.session_state[f"length_{iid}"] = 48
    st.session_state[f"width_{iid}"] = 40
    st.session_state[f"height_{iid}"] = 48
    st.session_state[f"desc_{iid}"] = ""
    st.session_state[f"stack_{iid}"] = False
    st.session_state[f"haz_{iid}"] = False
    st.session_state[f"used_{iid}"] = False
    st.session_state[f"mach_{iid}"] = False
    st.session_state[f"nmfc_{iid}"] = ""
    st.session_state[f"sub_{iid}"] = ""


def _read_items() -> list[dict]:
    items = []
    for iid in st.session_state.item_ids:
        items.append(
            {
                "freight_class": st.session_state.get(f"class_{iid}", "70"),
                "packaging_type": st.session_state.get(f"pack_{iid}", "Pallet"),
                "units": int(st.session_state.get(f"units_{iid}") or 1),
                "pieces": int(st.session_state.get(f"pieces_{iid}") or 1),
                "total_weight": float(st.session_state.get(f"weight_{iid}") or 0),
                "length": float(st.session_state.get(f"length_{iid}") or 0),
                "width": float(st.session_state.get(f"width_{iid}") or 0),
                "height": float(st.session_state.get(f"height_{iid}") or 0),
                "description": st.session_state.get(f"desc_{iid}") or "",
                "is_stackable": bool(st.session_state.get(f"stack_{iid}")),
                "is_hazardous": bool(st.session_state.get(f"haz_{iid}")),
                "is_used": bool(st.session_state.get(f"used_{iid}")),
                "is_machinery": bool(st.session_state.get(f"mach_{iid}")),
                "nmfc_item_code": st.session_state.get(f"nmfc_{iid}") or "",
                "nmfc_sub_code": st.session_state.get(f"sub_{iid}") or "",
                "_id": iid,
            }
        )
    return items


def _roster() -> list[dict]:
    roster = load_preparers(ROOT / "data" / "preparers.json")
    st.session_state._preparer_roster = roster
    return roster


def _select_preparer() -> None:
    roster = st.session_state.get("_preparer_roster") or []
    chosen = apply_preparer_choice(
        st.session_state.get("preparer_choice") or "",
        roster,
        {
            "name": st.session_state.get("preparer_custom_name") or "",
            "title": st.session_state.get("preparer_custom_title") or "",
            "email": st.session_state.get("preparer_custom_email") or "",
        },
    )
    st.session_state.preparer_name = chosen["name"]
    st.session_state.preparer_title = chosen["title"]
    st.session_state.preparer_email = chosen["email"]


def _preparer_fields() -> None:
    st.markdown("Prepare a custom customer LTL/FTL quote")
    roster = _roster()
    if not roster:
        st.warning("No sales roster found. Enter your name, title, and email.")
        st.text_input("Your name", key="preparer_name", placeholder="Casey Ng", live=True)
        st.text_input("Title", key="preparer_title", placeholder="Account Executive", live=True)
        st.text_input("Email", key="preparer_email", placeholder="casey.ng@example.com", live=True)
        return
    for key, default in (
        ("preparer_choice", ""),
        ("preparer_custom_name", ""),
        ("preparer_custom_title", ""),
        ("preparer_custom_email", ""),
    ):
        if key not in st.session_state:
            st.session_state[key] = default
    options = preparer_options(roster)
    labels = dict(options)
    st.selectbox(
        "Your name",
        [value for value, _label in options],
        format_func=lambda value: labels.get(value, "Select your name"),
        key="preparer_choice",
        on_change=_select_preparer,
        filter_mode="fuzzy",
        help="Pick your name, or add someone who is not on the roster.",
    )
    if st.session_state.get("preparer_choice") == ADD_PREPARER:
        st.text_input("Your name", key="preparer_custom_name", placeholder="Casey Ng", live=True)
        st.text_input("Title", key="preparer_custom_title", placeholder="Account Executive", live=True)
        st.text_input("Email", key="preparer_custom_email", placeholder="casey.ng@example.com", live=True)
        st.session_state.preparer_name = st.session_state.get("preparer_custom_name") or ""
        st.session_state.preparer_title = st.session_state.get("preparer_custom_title") or ""
        st.session_state.preparer_email = st.session_state.get("preparer_custom_email") or ""
        return
    email = (st.session_state.get("preparer_email") or "").strip()
    if email:
        st.caption(email)
    with st.expander("Edit details"):
        st.text_input("Title", key="preparer_title", live=True)
        st.text_input("Email", key="preparer_email", live=True)


def _preparer_summary() -> None:
    """Read-only echo of the sidebar fields. Same session keys, no second inputs."""
    lines = [
        (st.session_state.get(key) or "").strip()
        for key in ("preparer_name", "preparer_title", "preparer_email")
    ]
    filled = [line for line in lines if line]
    if not filled:
        st.caption("Add your details in the sidebar")
        return
    st.markdown("**Prepared by**")
    for line in filled:
        st.text(line)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_search(name: str, places_key: str) -> list[dict]:
    return search_companies(name, places_key)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_enrich(payload: str) -> dict:
    return enrich_candidate(json.loads(payload))


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_website(website: str, places_key: str) -> dict:
    return lookup_by_website(website, places_key)


def _apply_candidate(candidate: dict) -> None:
    ss = st.session_state
    slim = {key: value for key, value in candidate.items() if key != "logo_png"}
    try:
        enriched = _cached_enrich(json.dumps(slim, sort_keys=True))
    except Exception:
        enriched = {}
    ss.logo_upload_generation = int(ss.get("logo_upload_generation") or 0) + 1
    ss.company = enriched.get("name") or ss.get("company") or ""
    ss.company_website = enriched.get("website") or ""
    ss.customer_street = enriched.get("street") or ""
    ss.customer_suite = enriched.get("suite") or ""
    ss.customer_city = enriched.get("city") or ""
    ss.customer_state = enriched.get("state") or ""
    ss.customer_postal = enriched.get("postal") or ""
    ss.customer_country = enriched.get("country") or "US"
    ss.customer_logo_png = enriched.get("logo_png")
    ss.customer_logo_off = False
    ss.customer_logo_source = enriched.get("logo_source") or ""
    ss.customer_address_source = enriched.get("address_source") or ""
    ss.customer_website_source = enriched.get("website_source") or ""
    bits = []
    if ss.company_website and ss.customer_website_source:
        bits.append(f"website from {ss.customer_website_source}")
    has_address = any((ss.customer_street, ss.customer_city, ss.customer_state, ss.customer_postal))
    if has_address and ss.customer_address_source:
        bits.append(f"address from {ss.customer_address_source}")
    elif not has_address:
        bits.append("no address was found, so it was left blank")
    if ss.customer_logo_source:
        bits.append(f"logo from {ss.customer_logo_source}")
    else:
        bits.append("no logo was found")
    note = "Looked up " + ", ".join(bits) + "."
    if len(ss.get("company_candidates") or []) > 1:
        note += " Pick another match if this is the wrong company."
    ss.lookup_message = note


def _clear_lookup() -> None:
    ss = st.session_state
    _reset_customer_details(ss)
    ss.company_candidates = []
    ss.company_match = ""
    ss.logo_upload_generation = int(ss.get("logo_upload_generation") or 0) + 1
    ss.lookup_message = "Nothing was found for that name. The address was left blank."


_DETAIL_LOCKS = {
    "customer_street": "street",
    "customer_suite": "suite",
    "customer_city": "city",
    "customer_state": "state",
    "customer_postal": "postal",
    "customer_country": "country",
}


def _remember_edit(field: str) -> None:
    locked_name = _DETAIL_LOCKS.get(field, field)
    locked = set(st.session_state.get("customer_hand_edited") or [])
    value = st.session_state.get(field) or ""
    if isinstance(value, str) and value.strip():
        locked.add(locked_name)
    else:
        locked.discard(locked_name)
    st.session_state.customer_hand_edited = locked


def _on_company_typed() -> None:
    st.session_state.company_name_from_lookup = False


def _on_website_typed() -> None:
    website = (st.session_state.get("company_website") or "").strip()
    if website:
        _lookup_from_website()


def _lookup_from_website() -> None:
    ss = st.session_state
    website = (ss.get("company_website") or "").strip()
    if not website:
        return
    try:
        found = _cached_website(website, read_setting("GOOGLE_PLACES_API_KEY", ""))
    except Exception:
        found = {"found": False}
    if not isinstance(found, dict):
        found = {"found": False}
    current = {
        "name": ss.get("company") or "",
        "street": ss.get("customer_street") or "",
        "suite": ss.get("customer_suite") or "",
        "city": ss.get("customer_city") or "",
        "state": ss.get("customer_state") or "",
        "postal": ss.get("customer_postal") or "",
        "country": ss.get("customer_country") or "US",
        "logo_png": ss.get("customer_logo_png"),
        "logo_source": ss.get("customer_logo_source") or "",
        "address_source": ss.get("customer_address_source") or "",
    }
    merged = merge_website_lookup(
        current,
        found,
        ss.get("customer_hand_edited") or (),
        name_from_lookup=bool(ss.get("company_name_from_lookup")),
    )
    ss.company = merged["name"]
    ss.company_name_from_lookup = merged["name_from_lookup"]
    ss.customer_street = merged["street"]
    ss.customer_suite = merged["suite"]
    ss.customer_city = merged["city"]
    ss.customer_state = merged["state"]
    ss.customer_postal = merged["postal"]
    ss.customer_country = merged["country"] or "US"
    ss.customer_logo_png = merged["logo_png"]
    ss.customer_logo_source = merged["logo_source"]
    ss.customer_address_source = merged["address_source"]
    if found.get("found"):
        ss.company_candidates = []
        ss.lookup_message = "Found from website."
    else:
        ss.lookup_message = "Nothing was found for that website. The address was left blank."


def _lookup_company() -> None:
    st.session_state.customer_hand_edited = set()
    st.session_state.company_name_from_lookup = True
    name = (st.session_state.get("company") or "").strip()
    if len(name) < 2:
        _clear_lookup()
        return
    try:
        candidates = _cached_search(name, read_setting("GOOGLE_PLACES_API_KEY", ""))
    except Exception:
        candidates = []
    st.session_state.company_candidates = candidates
    if not candidates:
        _clear_lookup()
        return
    st.session_state.company_match = candidates[0].get("label") or ""
    _apply_candidate(candidates[0])


def _select_match() -> None:
    label = st.session_state.get("company_match") or ""
    for candidate in st.session_state.get("company_candidates") or []:
        if candidate.get("label") == label:
            _apply_candidate(candidate)
            return


def _uploaded_logo() -> bytes | None:
    generation = int(st.session_state.get("logo_upload_generation") or 0)
    uploaded = st.session_state.get(f"customer_logo_file_{generation}")
    if uploaded is None:
        st.session_state.logo_upload_error = ""
        return None
    try:
        data = uploaded.getvalue() if hasattr(uploaded, "getvalue") else bytes(uploaded)
        png = image_to_png(data, source="upload")
    except Exception:
        png = None
    st.session_state.logo_upload_error = "" if png else "That file couldn't be used as a logo."
    return png


def _active_logo() -> bytes | None:
    if st.session_state.get("customer_logo_off"):
        return None
    uploaded = _uploaded_logo()
    if uploaded:
        return uploaded
    logo = st.session_state.get("customer_logo_png")
    return logo if isinstance(logo, (bytes, bytearray)) else None


def _customer_address() -> dict:
    return {
        "street": st.session_state.get("customer_street") or "",
        "suite": st.session_state.get("customer_suite") or "",
        "city": st.session_state.get("customer_city") or "",
        "state": st.session_state.get("customer_state") or "",
        "postal": st.session_state.get("customer_postal") or "",
        "country": st.session_state.get("customer_country") or "",
    }


def _company_details() -> None:
    candidates = st.session_state.get("company_candidates") or []
    if len(candidates) > 1:
        labels = [candidate.get("label") or "Company" for candidate in candidates]
        current = st.session_state.get("company_match")
        if current not in labels:
            st.session_state.company_match = labels[0]
        st.selectbox(
            "Matching companies",
            labels,
            key="company_match",
            on_change=_select_match,
            help="Name, city, and website. The closest match is already filled in.",
        )
    message = (st.session_state.get("lookup_message") or "").strip()
    if message:
        if message.startswith("Nothing was found"):
            st.warning(message)
        else:
            st.caption(message)
    logo = _active_logo()
    lines = format_customer_address(**_customer_address())
    website = (st.session_state.get("company_website") or "").strip()
    if logo or lines or website:
        preview, text = st.columns([1, 4])
        if logo:
            preview.image(logo, width=72)
        else:
            preview.caption("No logo")
        if lines:
            for line in lines:
                text.text(line)
        else:
            text.caption("No address found.")
        if website:
            text.caption(website)
    with st.expander("Edit details", expanded=False):
        st.text_input(
            "Website",
            key="company_website",
            placeholder="https://example.com",
            on_change=_on_website_typed,
            help="Type a website if the name lookup missed. Logo, address, and company name fill in from that site.",
        )
        street, suite = st.columns(2)
        street.text_input("Street", key="customer_street", on_change=_remember_edit, args=("customer_street",))
        suite.text_input("Suite", key="customer_suite", placeholder="Optional", on_change=_remember_edit, args=("customer_suite",))
        city, state, postal, country = st.columns([1.4, 0.6, 0.8, 0.7])
        city.text_input("City", key="customer_city", on_change=_remember_edit, args=("customer_city",))
        state.text_input("State", key="customer_state", on_change=_remember_edit, args=("customer_state",))
        postal.text_input("ZIP", key="customer_postal", on_change=_remember_edit, args=("customer_postal",))
        country.text_input("Country", key="customer_country", on_change=_remember_edit, args=("customer_country",))
        st.checkbox("Leave logo off", key="customer_logo_off")
        generation = int(st.session_state.get("logo_upload_generation") or 0)
        st.file_uploader(
            "Replace logo",
            type=["png", "jpg", "jpeg", "webp", "ico"],
            key=f"customer_logo_file_{generation}",
        )
        if st.session_state.get("logo_upload_error"):
            st.caption(st.session_state.logo_upload_error)


def _lane_fields() -> None:
    left, right = st.columns(2)
    with left:
        st.text_input("Customer name", key="customer_name", placeholder="Alex Chen")
        c1, c2, c3 = st.columns([1.2, 1, 0.6])
        c1.text_input("Origin ZIP", key="origin_zip", placeholder="72205")
        c2.text_input("Origin city", key="origin_city", placeholder="Little Rock")
        c3.text_input("Origin state", key="origin_state", placeholder="AR", max_chars=2)
    with right:
        name_col, look_col = st.columns([4, 1], vertical_alignment="bottom")
        name_col.text_input(
            "Company",
            key="company",
            placeholder="Northwind Goods",
            on_change=_on_company_typed,
            help="Type the customer company name and press Look up. A website under Edit details looks the company up again.",
        )
        look_col.button("Look up", on_click=_lookup_company, key="lookup_company")
        c1, c2, c3 = st.columns([1.2, 1, 0.6])
        c1.text_input("Destination ZIP", key="dest_zip", placeholder="60606")
        c2.text_input("Destination city", key="dest_city", placeholder="Chicago")
        c3.text_input("Destination state", key="dest_state", placeholder="IL", max_chars=2)
    dcol, mcol = st.columns(2)
    dcol.date_input("Pickup date", key="pickup")
    mcol.slider(
        "Markup",
        min_value=float(MARKUP_MIN),
        max_value=float(MARKUP_MAX),
        step=0.1,
        key="markup",
        help="Applied in code, from 5% to 10%. The customer quote shows only the sell price.",
    )
    _company_details()


def _suggest(iid: str) -> None:
    """Runs before widgets draw, so the class select can take the new value."""
    try:
        result = suggest_class(
            {
                "total_weight": st.session_state.get(f"weight_{iid}"),
                "length": st.session_state.get(f"length_{iid}"),
                "width": st.session_state.get(f"width_{iid}"),
                "height": st.session_state.get(f"height_{iid}"),
                "units": st.session_state.get(f"units_{iid}"),
            }
        )
        st.session_state[f"class_{iid}"] = result["suggested_class"]
        st.session_state[f"suggestion_{iid}"] = result["suggested_class"]
        st.session_state[f"suggestion_error_{iid}"] = ""
    except Exception as exc:  # noqa: BLE001 — show the desk error, never a raw payload
        st.session_state[f"suggestion_error_{iid}"] = public_error(exc)


def _render_item(iid: str, index: int) -> None:
    st.markdown(f"**Item {index + 1}**")
    a, b, c, d, e = st.columns(5)
    a.selectbox("Freight class", FREIGHT_CLASSES, key=f"class_{iid}")
    b.selectbox("Packaging", PACKAGING_TYPES, key=f"pack_{iid}")
    c.number_input("Units", min_value=1, step=1, key=f"units_{iid}")
    d.number_input("Pieces", min_value=1, step=1, key=f"pieces_{iid}")
    e.number_input("Total weight (lb)", min_value=1, step=1, key=f"weight_{iid}")
    a, b, c, d, e = st.columns(5)
    a.number_input("Length (in)", min_value=1, step=1, key=f"length_{iid}")
    b.number_input("Width (in)", min_value=1, step=1, key=f"width_{iid}")
    c.number_input("Height (in)", min_value=1, step=1, key=f"height_{iid}")
    d.text_input("Description", key=f"desc_{iid}")
    e.button("Suggest class", key=f"suggest_{iid}", on_click=_suggest, args=(iid,))
    if st.session_state.get(f"suggestion_error_{iid}"):
        st.error(st.session_state[f"suggestion_error_{iid}"])
    if st.session_state.get(f"suggestion_{iid}"):
        st.caption(f"Suggested class {st.session_state[f'suggestion_{iid}']}")
    a, b = st.columns(2)
    a.text_input("NMFC item", key=f"nmfc_{iid}")
    b.text_input("NMFC sub", key=f"sub_{iid}")
    a, b, c, d, e = st.columns(5)
    a.checkbox("Stackable", key=f"stack_{iid}")
    b.checkbox("Hazmat", key=f"haz_{iid}")
    c.checkbox("Used", key=f"used_{iid}")
    d.checkbox("Machinery", key=f"mach_{iid}")
    if len(st.session_state.item_ids) > 1 and e.button("Remove", key=f"remove_{iid}"):
        st.session_state.item_ids = [item for item in st.session_state.item_ids if item != iid]
        st.rerun()
    st.divider()


def _money(amount: float, currency: str = "USD") -> str:
    symbol = "$" if currency in {"USD", ""} else f"{currency} "
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def _short_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return value
    return parsed.strftime("%b %-d, %Y").replace(" 0", " ") if False else f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def _service(rate: dict) -> str:
    description = (rate.get("service_level_description") or "").strip()
    if description:
        return description
    raw = (rate.get("service_level") or "Standard").replace("_", " ")
    return raw[:1].upper() + raw[1:].lower() if raw.isupper() else raw


def _place(shipment: dict, side: str) -> str:
    if side == "origin":
        city = ", ".join(part for part in (shipment.get("origin_city"), shipment.get("origin_state")) if part)
        return f"{city} {shipment['origin_zip_code']}".strip()
    city = ", ".join(part for part in (shipment.get("destination_city"), shipment.get("destination_state")) if part)
    return f"{city} {shipment['destination_zip_code']}".strip()


def _rates_panel(quote: dict, product: str) -> None:
    st.markdown(f"### {_place(quote['shipment'], 'origin')} → {_place(quote['shipment'], 'destination')}")
    bits = [f"Pickup {_short_date(quote['shipment']['pickup_date'])}"]
    if quote["shipment"].get("total_weight") is not None:
        bits.append(f"{quote['shipment']['total_weight']:,.0f} lb")
    if quote["shipment"].get("distance_miles") is not None:
        bits.append(f"{quote['shipment']['distance_miles']:,.0f} miles")
    bits.append(f"{len(quote['rates'])} options, lowest price first")
    st.caption(" · ".join(bits))
    for warning in quote["warnings"]:
        st.warning(warning)
    if not quote["rates"]:
        st.info("No carrier returned a rate.")
    else:
        header = st.columns([0.7, 2.1, 0.8, 1.3, 0.9, 1.3, 1.3, 1.2])
        for column, label in zip(header, ["Include", "Carrier", "SCAC", "Service", "Transit", "Est. delivery", "Expires", "Customer price"]):
            column.markdown(f"**{label}**")
        for rate in quote["rates"]:
            key = f"pick_{product}_{rate['option_id']}"
            if key not in st.session_state:
                st.session_state[key] = True
            cols = st.columns([0.7, 2.1, 0.8, 1.3, 0.9, 1.3, 1.3, 1.2])
            cols[0].checkbox("Include", key=key, label_visibility="collapsed")
            cols[1].markdown(f"**{rate['carrier_name']}**")
            cols[2].markdown(rate["scac"] or "—")
            lane = f"<br><span style='color:#3C4A78;font-size:0.8rem'>{rate['lane_type'].title()}</span>" if rate.get("lane_type") else ""
            cols[3].markdown(f"{_service(rate)}{lane}", unsafe_allow_html=True)
            days = rate["transit_days"]
            cols[4].markdown("—" if days is None else ("1 day" if days == 1 else f"{days} days"))
            cols[5].markdown(_short_date(rate["delivery_date"]))
            cols[6].markdown(_short_date(rate["expiration_date"]))
            cols[7].markdown(f"**{_money(rate['customer_total'], rate['currency'])}**")
    internal_key = f"show_internal_{product}"
    partner_key = f"show_partner_{product}"
    st.checkbox("Show internal costs", key=internal_key, help="Off by default. These figures never go on the customer PDF.")
    if st.session_state[internal_key]:
        st.markdown(
            "<div style='background:#EAD6FB;border-radius:12px;padding:12px 14px'>"
            "<strong>Internal only.</strong> Buy rate, markup, and margin stay off the customer quote."
            "</div>",
            unsafe_allow_html=True,
        )
        rows = []
        for rate in quote["rates"]:
            internal = rate["internal"]
            rows.append(
                {
                    "Carrier": rate["carrier_name"],
                    "Buy rate": _money(internal["base_total"], rate["currency"]),
                    "Markup": f"{_money(internal['markup_amount'], rate['currency'])} ({internal['markup_percent']:g}%)",
                    "Margin": f"{internal['margin_percent']:.2f}%",
                    "Carrier quote #": internal.get("carrier_quote_number") or "—",
                }
            )
        st.dataframe(rows, hide_index=True, width="stretch")
    if quote["failed_carriers"]:
        st.caption("No rate returned")
        for failed in quote["failed_carriers"]:
            scac = f" ({failed['scac']})" if failed["scac"] else ""
            st.caption(f"{failed['carrier_name']}{scac}: {failed['message']}")
    st.checkbox("Mention Priority1 on the customer PDF", key=partner_key)
    selected = []
    for rate in quote["rates"]:
        if st.session_state.get(f"pick_{product}_{rate['option_id']}", True):
            selected.append(to_customer_rate(rate))
    if not selected:
        st.info("Choose at least one carrier option for the quote.")
        return
    try:
        document = build_customer_quote(
            {
                "customer_name": st.session_state.customer_name,
                "company": st.session_state.company,
                "preparer_name": st.session_state.preparer_name,
                "preparer_title": st.session_state.preparer_title,
                "preparer_email": st.session_state.preparer_email,
                "show_priority1": st.session_state[partner_key],
                "shipment": quote["shipment"],
                "address": _customer_address(),
                "options": selected,
            }
        )
        pdf = render_customer_pdf(document, logo_png=_active_logo())
    except Exception as exc:  # noqa: BLE001
        st.error(public_error(exc))
        return
    st.download_button(
        "Download customer PDF",
        data=pdf,
        file_name=filename_for(document),
        mime="application/pdf",
        type="primary",
        key=f"download_{product}",
    )


def _ltl_tab() -> None:
    st.subheader("Line items")
    if st.button("Add item"):
        _add_item()
        st.rerun()
    for index, iid in enumerate(list(st.session_state.item_ids)):
        _render_item(iid, index)
    st.subheader("Accessorials")
    st.multiselect(
        "Accessorials",
        options=[option_label(code) for code, _desc, _group in ACCESSORIALS],
        key="accessorials",
        help="Hazmat on a line item also sends HAZM.",
        label_visibility="collapsed",
    )
    if st.button("Get rates", type="primary", key="ltl_go"):
        try:
            st.session_state.ltl_quote = quote_ltl(
                {
                    "markup_percent": st.session_state.markup,
                    "origin_zip_code": st.session_state.origin_zip,
                    "origin_city": st.session_state.origin_city,
                    "origin_state_abbreviation": st.session_state.origin_state,
                    "destination_zip_code": st.session_state.dest_zip,
                    "destination_city": st.session_state.dest_city,
                    "destination_state_abbreviation": st.session_state.dest_state,
                    "pickup_date": st.session_state.pickup.isoformat(),
                    "accessorial_services": [code_from_label(label) for label in st.session_state.accessorials],
                    "items": _read_items(),
                }
            )
            st.session_state.show_internal_ltl = False
        except Exception as exc:  # noqa: BLE001
            st.session_state.ltl_quote = None
            st.error(public_error(exc))
    if st.session_state.ltl_quote:
        _rates_panel(st.session_state.ltl_quote, "ltl")


def _tl_tab() -> None:
    st.subheader("Truckload")
    st.caption("Live calls fail clearly if this key does not include truckload. Responses have no carrier name or SCAC.")
    a, b, c, d, e = st.columns(5)
    a.selectbox("Equipment", EQUIPMENT_TYPES, format_func=lambda value: EQUIPMENT_LABELS[value], key="tl_equipment")
    b.selectbox("Service", ["Full", "Team"], key="tl_service")
    c.number_input("Weight (lb)", min_value=1, step=100, key="tl_weight")
    d.number_input("Pallets", min_value=1, step=1, key="tl_pallets")
    e.text_input("Commodity", key="tl_desc")
    equipment = st.session_state.tl_equipment
    if equipment == "Sprinter_Van" or "Straight_Truck" in equipment:
        st.checkbox("Lift gate required", key="tl_lift")
    else:
        st.caption("Lift gate is only sent for straight trucks and sprinter vans, matching the API.")
    if st.button("Get truckload rates", type="primary"):
        try:
            st.session_state.tl_quote = quote_tl(
                {
                    "markup_percent": st.session_state.markup,
                    "origin_zip_code": st.session_state.origin_zip,
                    "origin_city": st.session_state.origin_city,
                    "origin_state": st.session_state.origin_state,
                    "destination_zip_code": st.session_state.dest_zip,
                    "destination_city": st.session_state.dest_city,
                    "destination_state": st.session_state.dest_state,
                    "pickup_date_open": st.session_state.pickup.isoformat(),
                    "equipment": st.session_state.tl_equipment,
                    "truckload_quote_service_type_id": st.session_state.tl_service,
                    "weight": int(st.session_state.tl_weight),
                    "weight_unit_id": "lbs",
                    "pallet_count": int(st.session_state.tl_pallets),
                    "description": st.session_state.tl_desc,
                    "requires_lift_gate": bool(st.session_state.get("tl_lift")),
                    "start_time": "08:00",
                    "end_time": "17:00",
                }
            )
            st.session_state.show_internal_tl = False
        except Exception as exc:  # noqa: BLE001
            st.session_state.tl_quote = None
            st.error(public_error(exc))
    if st.session_state.tl_quote:
        _rates_panel(st.session_state.tl_quote, "tl")


def main() -> None:
    _boot()
    _ensure_customer_keys()
    config = get_config()
    with st.sidebar:
        st.image(str(LOGO), width="stretch")
        st.markdown('<p class="ep-title">EasyPost</p>', unsafe_allow_html=True)
        st.caption(
            "Shop LTL rates, and truckload when the account allows it. Customer quotes show the sell price only."
        )
        _preparer_fields()
        st.markdown("**Freight quote desk**")
        st.markdown(f"<span class='ep-chip'>{config.mode_label}</span>", unsafe_allow_html=True)
    st.markdown('<p class="ep-title">Quote freight without leaving the desk.</p>', unsafe_allow_html=True)
    _preparer_summary()
    if st.button("Load sample lane", key="load_sample"):
        _load_sample()
        st.rerun()
    _lane_fields()
    ltl, truck = st.tabs(["LTL", "Truckload"])
    with ltl:
        _ltl_tab()
    with truck:
        _tl_tab()


main()
