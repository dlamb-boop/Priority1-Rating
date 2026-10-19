"""Quote LTL and truckload rates. Demo mode needs no API key."""

from __future__ import annotations

from freight.client import Priority1Error, post_priority1, truckload_unavailable_message
from freight.config import get_config
from freight.mapping import map_ltl_response, map_tl_response
from freight.markup import MarkupError, normalize_markup_percent
from freight.mock_rates import mock_ltl_rates, mock_tl_rates, suggest_freight_class
from freight.requests import build_ltl_rates_request, build_suggested_class_request, build_tl_rates_request
from freight.validation import QuoteError, normalize_ltl, normalize_tl


def _meta() -> dict:
    config = get_config()
    return {
        "mode": "mock" if config.mock else "live",
        "environment": config.environment,
        "mode_label": config.mode_label,
    }


def quote_ltl(raw: dict) -> dict:
    quote = normalize_ltl(raw)
    quote["markup_percent"] = normalize_markup_percent(raw.get("markup_percent"))
    meta = _meta()
    if meta["mode"] == "mock":
        upstream = mock_ltl_rates(quote)
    else:
        upstream = post_priority1("/v2/ltl/quotes/rates", build_ltl_rates_request(quote))
    return map_ltl_response(upstream, quote, meta)


def quote_tl(raw: dict) -> dict:
    quote = normalize_tl(raw)
    quote["markup_percent"] = normalize_markup_percent(raw.get("markup_percent"))
    meta = _meta()
    if meta["mode"] == "mock":
        return map_tl_response(mock_tl_rates(quote), quote, meta)
    try:
        upstream = post_priority1("/v2/tl/truckloadquotes/rates", build_tl_rates_request(quote))
    except Priority1Error as exc:
        friendly = truckload_unavailable_message(exc)
        if friendly:
            raise QuoteError(friendly) from exc
        raise
    return map_tl_response(upstream, quote, meta)


def suggest_class(raw: dict) -> dict:
    request = build_suggested_class_request(
        {
            "total_weight": float(raw["total_weight"]),
            "length": float(raw["length"]),
            "width": float(raw["width"]),
            "height": float(raw["height"]),
            "units": int(raw["units"]),
        }
    )
    for key, value in request.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise QuoteError(f"Enter {key} before suggesting a class.")
    meta = _meta()
    if meta["mode"] == "mock":
        return {
            "suggested_class": suggest_freight_class(
                request["totalWeight"], request["length"], request["width"], request["height"], int(request["units"])
            ),
            "mode": "mock",
        }
    upstream = post_priority1("/v2/ltl/quotes/suggestedclass", request)
    suggested = (upstream.get("suggestedClass") or "").strip()
    if not suggested:
        raise Priority1Error(502, ["No freight class was suggested."])
    return {"suggested_class": suggested, "mode": "live"}


def public_error(exc: Exception) -> str:
    if isinstance(exc, (QuoteError, MarkupError, ValueError)):
        return str(exc)
    if isinstance(exc, Priority1Error):
        return " ".join(exc.messages)
    return "The quote could not be completed."
