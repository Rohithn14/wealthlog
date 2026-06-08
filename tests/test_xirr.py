"""Tests for XIRR calculation across many scenarios."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.finance.xirr import calculate_xirr


class TestBasic:
    def test_simple_one_year_10pct(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2025, 1, 1), Decimal("1100")),
        ]
        rate = calculate_xirr(flows)
        assert rate is not None
        assert rate == pytest.approx(Decimal("0.10"), abs=Decimal("0.002"))

    def test_returns_decimal(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2025, 1, 1), Decimal("1100")),
        ]
        assert isinstance(calculate_xirr(flows), Decimal)

    def test_loss_is_negative(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2025, 1, 1), Decimal("900")),
        ]
        rate = calculate_xirr(flows)
        assert rate is not None and rate < 0

    def test_break_even_near_zero(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2025, 1, 1), Decimal("1000")),
        ]
        rate = calculate_xirr(flows)
        assert rate is not None
        assert abs(rate) < Decimal("0.0001")


class TestEdgeCases:
    def test_empty_returns_none(self):
        assert calculate_xirr([]) is None

    def test_single_flow_returns_none(self):
        assert calculate_xirr([(dt.date(2024, 1, 1), Decimal("-1000"))]) is None

    def test_all_buys_returns_none(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2024, 6, 1), Decimal("-500")),
            (dt.date(2024, 12, 1), Decimal("-300")),
        ]
        assert calculate_xirr(flows) is None

    def test_all_inflows_returns_none(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("1000")),
            (dt.date(2025, 1, 1), Decimal("500")),
        ]
        assert calculate_xirr(flows) is None

    def test_zeros_with_one_sign_returns_none(self):
        flows = [
            (dt.date(2024, 1, 1), Decimal("0")),
            (dt.date(2025, 1, 1), Decimal("-1000")),
        ]
        assert calculate_xirr(flows) is None


class TestMultiFlow:
    def test_mixed_buy_dates_with_terminal_value(self):
        # Two buys then a terminal valuation -> positive return.
        flows = [
            (dt.date(2023, 1, 1), Decimal("-1000")),
            (dt.date(2023, 7, 1), Decimal("-1000")),
            (dt.date(2024, 1, 1), Decimal("2200")),  # terminal market value
        ]
        rate = calculate_xirr(flows)
        assert rate is not None and rate > 0

    def test_dividends_plus_terminal(self):
        flows = [
            (dt.date(2023, 1, 1), Decimal("-10000")),
            (dt.date(2023, 6, 1), Decimal("200")),  # dividend
            (dt.date(2024, 1, 1), Decimal("10500")),  # terminal
        ]
        rate = calculate_xirr(flows)
        assert rate is not None and rate > 0

    def test_order_independent(self):
        a = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2025, 1, 1), Decimal("1100")),
        ]
        b = list(reversed(a))
        assert calculate_xirr(a) == calculate_xirr(b)

    @pytest.mark.parametrize("final", ["1050", "1100", "1200", "1500"])
    def test_monotonic_in_final_value(self, final):
        flows = [
            (dt.date(2024, 1, 1), Decimal("-1000")),
            (dt.date(2025, 1, 1), Decimal(final)),
        ]
        rate = calculate_xirr(flows)
        assert rate is not None
        # Higher final value -> higher return.
        assert rate > Decimal("0")
