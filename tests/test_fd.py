"""Tests for fixed-deposit valuation (simple & compound, clamping, edge cases)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import CompoundingFrequency
from wealthlog.finance.fd import calculate_fd_value, fd_accrued_interest


class TestSimpleInterest:
    def test_one_year_simple(self):
        # 100000 @ 10% simple for exactly 365 days -> 110000.
        value = calculate_fd_value(
            "100000", "10", dt.date(2024, 1, 1), dt.date(2024, 12, 31),
            compounding=CompoundingFrequency.SIMPLE,
        )
        # 365 days between Jan 1 and Dec 31 of a leap year is 365.
        assert value == Decimal("110000.00")

    def test_half_year_simple(self):
        value = calculate_fd_value(
            "100000", "10", dt.date(2024, 1, 1),
            dt.date(2024, 1, 1) + dt.timedelta(days=182),
            compounding=CompoundingFrequency.SIMPLE,
        )
        # ~half year -> ~5000 interest.
        assert Decimal("104900") < value < Decimal("105100")

    def test_returns_two_dp(self):
        value = calculate_fd_value(
            "100000", "7.35", dt.date(2024, 1, 1), dt.date(2024, 6, 1),
            compounding=CompoundingFrequency.SIMPLE,
        )
        assert value.as_tuple().exponent == -2


class TestCompounding:
    def test_annual_compounding_one_year(self):
        value = calculate_fd_value(
            "100000", "10", dt.date(2024, 1, 1),
            dt.date(2024, 1, 1) + dt.timedelta(days=365),
            compounding=CompoundingFrequency.ANNUAL,
        )
        assert value == pytest.approx(Decimal("110000"), abs=Decimal("1"))

    def test_quarterly_beats_annual(self):
        common = ("100000", "10", dt.date(2024, 1, 1),
                  dt.date(2024, 1, 1) + dt.timedelta(days=365))
        annual = calculate_fd_value(*common, compounding=CompoundingFrequency.ANNUAL)
        quarterly = calculate_fd_value(*common, compounding=CompoundingFrequency.QUARTERLY)
        assert quarterly > annual

    def test_monthly_beats_quarterly(self):
        common = ("100000", "10", dt.date(2024, 1, 1),
                  dt.date(2024, 1, 1) + dt.timedelta(days=365))
        quarterly = calculate_fd_value(*common, compounding=CompoundingFrequency.QUARTERLY)
        monthly = calculate_fd_value(*common, compounding=CompoundingFrequency.MONTHLY)
        assert monthly > quarterly

    @pytest.mark.parametrize(
        "freq",
        [
            CompoundingFrequency.ANNUAL,
            CompoundingFrequency.SEMI_ANNUAL,
            CompoundingFrequency.QUARTERLY,
            CompoundingFrequency.MONTHLY,
        ],
    )
    def test_all_frequencies_accrue_above_principal(self, freq):
        value = calculate_fd_value(
            "50000", "6.5", dt.date(2024, 1, 1),
            dt.date(2024, 1, 1) + dt.timedelta(days=200), compounding=freq,
        )
        assert value > Decimal("50000")


class TestClamping:
    def test_before_start_returns_principal(self):
        value = calculate_fd_value(
            "100000", "7", dt.date(2025, 1, 1), dt.date(2024, 6, 1),
        )
        assert value == Decimal("100000.00")

    def test_on_start_returns_principal(self):
        value = calculate_fd_value(
            "100000", "7", dt.date(2024, 1, 1), dt.date(2024, 1, 1),
        )
        assert value == Decimal("100000.00")

    def test_after_maturity_caps_at_maturity_value(self):
        start = dt.date(2024, 1, 1)
        maturity = start + dt.timedelta(days=365)
        at_maturity = calculate_fd_value(
            "100000", "8", start, maturity, maturity_date=maturity,
        )
        way_after = calculate_fd_value(
            "100000", "8", start, maturity + dt.timedelta(days=500),
            maturity_date=maturity,
        )
        assert at_maturity == way_after

    def test_maturity_before_start_raises(self):
        with pytest.raises(ValueError):
            calculate_fd_value(
                "100000", "8", dt.date(2024, 1, 1), dt.date(2024, 6, 1),
                maturity_date=dt.date(2023, 1, 1),
            )


class TestAccruedInterest:
    def test_accrued_is_value_minus_principal(self):
        start = dt.date(2024, 1, 1)
        as_of = start + dt.timedelta(days=365)
        value = calculate_fd_value("100000", "10", start, as_of,
                                   compounding=CompoundingFrequency.SIMPLE)
        accrued = fd_accrued_interest("100000", "10", start, as_of,
                                      compounding=CompoundingFrequency.SIMPLE)
        assert accrued == value - Decimal("100000.00")

    def test_zero_accrued_before_start(self):
        accrued = fd_accrued_interest("100000", "10", dt.date(2025, 1, 1),
                                      dt.date(2024, 1, 1))
        assert accrued == Decimal("0.00")
