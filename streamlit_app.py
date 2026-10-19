"""EasyPost freight quote desk. Entry point for Streamlit Community Cloud."""

from __future__ import annotations

import hmac
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from freight.accessorials import ACCESSORIALS, code_from_label, option_label
from freight.config import get_config, read_setting
from freight.constants import EQUIPMENT_LABELS, EQUIPMENT_TYPES, FREIGHT_CLASSES, PACKAGING_TYPES
from freight.customer import build_customer_quote, to_customer_rate
from freight.markup import MARKUP_DEFAULT, MARKUP_MAX, MARKUP_MIN
from freight.pdf_quote import filename_for, render_customer_pdf
from freight.quote import public_error, quote_ltl, quote_tl, suggest_class

ROOT = Path(__file__).resolve().parent
LOGO = ROOT / "assets" / "easypost-logo.png"

st.set_page_config(
    page_title="EasyPost Freight Quotes",
    page_icon=str(LOGO),
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
    ss.authed = False


def _brand_logo() -> None:
    """Header wordmark. Fall back if this Streamlit build has no size argument."""
    try:
        st.logo(str(LOGO), size="large")
    except TypeError:
        st.logo(str(LOGO))


def _password_gate() -> None:
    expected = read_setting("APP_PASSWORD")
    _brand_logo()
    if not expected:
        st.markdown('<p class="ep-kicker">EASYPOST</p>', unsafe_allow_html=True)
        st.markdown('<p class="ep-title">Freight quote desk</p>', unsafe_allow_html=True)
        st.error("This desk is locked. Set APP_PASSWORD in secrets before anyone can open it.")
        st.stop()
    if st.session_state.get("authed"):
        return
    st.markdown('<p class="ep-kicker">EASYPOST</p>', unsafe_allow_html=True)
    st.markdown('<p class="ep-title">Freight quote desk</p>', unsafe_allow_html=True)
    st.caption("Dawson Lamb · internal rating desk")
    with st.form("gate"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Continue", type="primary")
    if submitted:
        if hmac.compare_digest(entered, expected):
            st.session_state.authed = True
            st.rerun()
        st.error("That password is not recognized.")
    st.stop()


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


def _lane_fields() -> None:
    left, right = st.columns(2)
    with left:
        st.text_input("Customer name", key="customer_name", placeholder="Alex Chen")
        c1, c2, c3 = st.columns([1.2, 1, 0.6])
        c1.text_input("Origin ZIP", key="origin_zip", placeholder="72205")
        c2.text_input("Origin city", key="origin_city", placeholder="Little Rock")
        c3.text_input("Origin state", key="origin_state", placeholder="AR", max_chars=2)
    with right:
        st.text_input("Company", key="company", placeholder="Northwind Goods")
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
                "show_priority1": st.session_state[partner_key],
                "shipment": quote["shipment"],
                "options": selected,
            }
        )
        pdf = render_customer_pdf(document)
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
    _password_gate()
    config = get_config()
    with st.sidebar:
        st.image(str(LOGO), width="stretch")
        st.markdown("**Freight quote desk**")
        st.markdown(f"<span class='ep-chip'>{config.mode_label}</span>", unsafe_allow_html=True)
        st.caption("Dawson Lamb")
        st.caption("Director of Supply Chain Solutions and Partnerships")
    st.markdown('<p class="ep-kicker">EASYPOST</p>', unsafe_allow_html=True)
    st.markdown('<p class="ep-title">Quote freight without leaving the desk.</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ep-sub">Shop LTL rates, and truckload when the account allows it. Customer quotes show the sell price only.</p>',
        unsafe_allow_html=True,
    )
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
