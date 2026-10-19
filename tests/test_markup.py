import math

import pytest

from freight.markup import MarkupError, apply_markup, normalize_markup_percent, round_cents


def test_round_cents_half_up():
    assert round_cents(1.004) == 1
    assert round_cents(1.005) == 1.01
    assert round_cents(1.015) == 1.02
    assert round_cents(-1.005) == -1.01
    assert round_cents(252.4023) == 252.4
    assert round_cents(302.2322) == 302.23
    assert round_cents(10.005) == 10.01


def test_normalize_markup_bounds():
    assert normalize_markup_percent(5) == 5
    assert normalize_markup_percent(10) == 10
    assert normalize_markup_percent("7") == 7
    assert normalize_markup_percent(7.04) == 7
    assert normalize_markup_percent(6.96) == 7


@pytest.mark.parametrize("value", [4.99, 0, 10.01, 15, -7, math.nan, "nope", None])
def test_normalize_markup_rejects(value):
    with pytest.raises(MarkupError):
        normalize_markup_percent(value)


def test_apply_markup_spec_sample():
    result = apply_markup(
        235.89,
        [
            {"code": "FSC", "description": "Fuel Surcharge", "amount": 39.46},
            {"code": "GFC", "description": "Gross Freight Charge", "amount": 196.43},
        ],
        7,
    )
    assert result.base_total == 235.89
    assert result.customer_total == 252.4
    assert result.markup_amount == 16.51
    assert [charge.customer_amount for charge in result.charges] == [42.22, 210.18]
    assert round_cents(sum(charge.customer_amount for charge in result.charges)) == result.customer_total


def test_apply_markup_discount_foots():
    result = apply_markup(
        100,
        [
            {"code": "ITEM", "description": "Item Charge", "amount": 150},
            {"code": "DSC", "description": "Discount", "amount": -50},
        ],
        10,
    )
    assert result.customer_total == 110
    assert [charge.customer_amount for charge in result.charges] == [165, -55]
    assert round_cents(sum(charge.customer_amount for charge in result.charges)) == 110


def test_apply_markup_absorbs_penny():
    result = apply_markup(
        10,
        [
            {"code": "A", "description": "A", "amount": 3.33},
            {"code": "B", "description": "B", "amount": 3.33},
            {"code": "C", "description": "C", "amount": 3.34},
        ],
        5,
    )
    assert result.customer_total == 10.5
    assert round_cents(sum(charge.customer_amount for charge in result.charges)) == 10.5


def test_apply_markup_remainder_line():
    result = apply_markup(
        282.46,
        [
            {"code": "FSC", "description": "Fuel Surcharge", "amount": 42.96},
            {"code": "HCSER", "description": "High Cost Service Area Surcharge", "amount": 60},
            {"code": "ITEM", "description": "Item Charge", "amount": 440.98},
            {"code": "DSC", "description": "Discount", "amount": -187.56},
        ],
        7,
    )
    assert result.customer_total == 302.23
    assert any(charge.code == "OTHER" for charge in result.charges)
    assert round_cents(sum(charge.customer_amount for charge in result.charges)) == 302.23
    assert round_cents(sum(charge.base_amount for charge in result.charges)) == 282.46


def test_apply_markup_without_charges():
    result = apply_markup(80, [], 5)
    assert result.customer_total == 84
    assert result.charges == []
