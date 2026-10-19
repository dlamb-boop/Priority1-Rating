"""Hidden markup applied to carrier totals and itemized charges."""

from __future__ import annotations

import math
from dataclasses import dataclass

MARKUP_MIN = 5.0
MARKUP_MAX = 10.0
MARKUP_DEFAULT = 7.0


class MarkupError(ValueError):
    """Markup is missing or outside the allowed range."""


@dataclass
class RatedCharge:
    code: str
    description: str
    base_amount: float
    customer_amount: float


@dataclass
class MarkupResult:
    markup_percent: float
    base_total: float
    customer_total: float
    markup_amount: float
    margin_percent: float
    charges: list[RatedCharge]


def _half_up(value: float) -> int:
    """Match JavaScript Math.round for the non-negative values we pass in."""
    return math.floor(value + 0.5)


def round_cents(amount: float) -> float:
    """Round half-up, away from zero, to the nearest cent."""
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount):
        raise MarkupError("Amount must be a finite number.")
    sign = -1.0 if amount < 0 else 1.0
    cents = _half_up(abs(float(amount)) * 100 + 1e-8)
    return sign * cents / 100.0


def _round_to_tenth(amount: float) -> float:
    sign = -1.0 if amount < 0 else 1.0
    tenths = _half_up(abs(amount) * 10 + 1e-8)
    return sign * tenths / 10.0


def normalize_markup_percent(value: object) -> float:
    """Accept 5% through 10% inclusive, stored to a tenth of a percent."""
    if isinstance(value, bool) or value is None:
        numeric = math.nan
    elif isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str) and value.strip() != "":
        try:
            numeric = float(value)
        except ValueError:
            numeric = math.nan
    else:
        numeric = math.nan

    if not math.isfinite(numeric):
        raise MarkupError("Markup percent must be a number.")
    if numeric < MARKUP_MIN - 1e-9 or numeric > MARKUP_MAX + 1e-9:
        raise MarkupError(f"Markup must be between {MARKUP_MIN:g}% and {MARKUP_MAX:g}%.")
    rounded = _round_to_tenth(numeric)
    if rounded < MARKUP_MIN or rounded > MARKUP_MAX:
        raise MarkupError(f"Markup must be between {MARKUP_MIN:g}% and {MARKUP_MAX:g}%.")
    return rounded


def _reconcile(lines: list[RatedCharge], customer_total: float) -> None:
    if not lines:
        return
    sum_cents = sum(int(round(line.customer_amount * 100)) for line in lines)
    diff_cents = int(round(customer_total * 100)) - sum_cents
    if diff_cents == 0:
        return
    index = max(range(len(lines)), key=lambda i: abs(int(round(lines[i].base_amount * 100))))
    lines[index].customer_amount = round_cents(lines[index].customer_amount + diff_cents / 100.0)


def apply_markup(total: float, charges: list[dict] | None, markup_percent_input: object) -> MarkupResult:
    """Mark up the carrier total and scale every itemized charge by the same factor.

    When the carrier's charges do not already foot to the total, a remainder line
    is added. Penny rounding lands on the largest charge so the lines still add
    up to the customer total.
    """
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not math.isfinite(total):
        raise MarkupError("Rate total must be a finite number.")

    markup_percent = normalize_markup_percent(markup_percent_input)
    factor = 1 + markup_percent / 100.0
    base_total = round_cents(float(total))
    customer_total = round_cents(base_total * factor)
    markup_amount = round_cents(customer_total - base_total)
    margin_percent = 0.0 if customer_total == 0 else round((markup_amount / customer_total) * 10000) / 100.0

    normalized: list[RatedCharge] = []
    for charge in charges or []:
        amount = charge.get("amount") if isinstance(charge, dict) else None
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount):
            continue
        code = str(charge.get("code") or "CHG").strip() or "CHG"
        description = str(charge.get("description") or "Charge").strip() or "Charge"
        normalized.append(RatedCharge(code, description, round_cents(float(amount)), 0.0))

    if normalized:
        base_sum = round_cents(sum(line.base_amount for line in normalized))
        remainder = round_cents(base_total - base_sum)
        if remainder != 0:
            normalized.append(RatedCharge("OTHER", "Other charges", remainder, 0.0))

    for line in normalized:
        line.customer_amount = round_cents(line.base_amount * factor)
    _reconcile(normalized, customer_total)

    return MarkupResult(
        markup_percent=markup_percent,
        base_total=base_total,
        customer_total=customer_total,
        markup_amount=markup_amount,
        margin_percent=margin_percent,
        charges=normalized,
    )
