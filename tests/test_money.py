"""Tests for the Decimal money/price/FX/unit helpers.

Broad coverage: precision per quantum, half-up rounding, type safety (no floats),
string/int/Decimal inputs, negatives, zero, and large magnitudes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from wealthlog.money import to_decimal, to_fx, to_money, to_price, to_units


class TestToDecimal:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("0", Decimal("0")),
            ("10", Decimal("10")),
            (10, Decimal("10")),
            ("-5.25", Decimal("-5.25")),
            ("1234567.891234", Decimal("1234567.891234")),
            (Decimal("3.14"), Decimal("3.14")),
        ],
    )
    def test_valid_inputs(self, value, expected):
        assert to_decimal(value) == expected

    def test_rejects_float(self):
        with pytest.raises(TypeError):
            to_decimal(1.5)

    @pytest.mark.parametrize("value", ["abc", "", "1.2.3", "₹100"])
    def test_invalid_string_raises_value_error(self, value):
        with pytest.raises(ValueError):
            to_decimal(value)


class TestToMoney:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("10", "10.00"),
            ("10.1", "10.10"),
            ("10.005", "10.01"),  # half-up
            ("10.004", "10.00"),
            ("0", "0.00"),
            ("-2.5", "-2.50"),
            ("999999.999", "1000000.00"),
        ],
    )
    def test_quantization(self, value, expected):
        assert to_money(value) == Decimal(expected)

    def test_always_two_places(self):
        assert to_money("7").as_tuple().exponent == -2


class TestToPrice:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("100", "100.0000"),
            ("100.12345", "100.1235"),  # half-up at 4dp
            ("100.12344", "100.1234"),
            ("0.00005", "0.0001"),
        ],
    )
    def test_quantization(self, value, expected):
        assert to_price(value) == Decimal(expected)

    def test_four_places(self):
        assert to_price("1").as_tuple().exponent == -4


class TestToFx:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("83", "83.000000"),
            ("83.1234565", "83.123457"),  # half-up at 6dp
            ("83.1234564", "83.123456"),
        ],
    )
    def test_quantization(self, value, expected):
        assert to_fx(value) == Decimal(expected)

    def test_six_places(self):
        assert to_fx("83").as_tuple().exponent == -6


class TestToUnits:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("10", "10.0000"),
            ("10.123456", "10.1235"),
            ("0.00004", "0.0000"),
        ],
    )
    def test_quantization(self, value, expected):
        assert to_units(value) == Decimal(expected)


@pytest.mark.parametrize("fn", [to_money, to_price, to_fx, to_units])
def test_helpers_reject_floats(fn):
    with pytest.raises(TypeError):
        fn(1.23)
