"""Fixed-deposit / debt-instrument valuation.

FDs have no live market price; their value at any date is principal plus accrued
interest. Interest is computed on an Actual/365 day-count basis. Both simple and
compound interest (annual, semi-annual, quarterly, monthly) are supported.

Accrual is clamped to ``[start_date, maturity_date]``: queries before the start return
the principal; queries after maturity return the matured value (no over-accrual).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, getcontext

from wealthlog.constants import (
    COMPOUNDING_PERIODS_PER_YEAR,
    DAYS_PER_YEAR,
    CompoundingFrequency,
)
from wealthlog.money import to_decimal, to_money

# Wide precision for intermediate exp/ln; final result is quantized to money (2dp).
getcontext().prec = 50


def _decimal_pow(base: Decimal, exponent: Decimal) -> Decimal:
    """Raise ``base`` to a (possibly fractional) ``exponent`` using Decimal exp/ln."""
    if base <= 0:
        raise ValueError("base must be positive for fractional exponentiation")
    if exponent == 0:
        return Decimal(1)
    return (exponent * base.ln()).exp()


def calculate_fd_value(
    principal: Decimal | int | str,
    annual_rate_pct: Decimal | int | str,
    start_date: dt.date,
    as_of_date: dt.date,
    compounding: CompoundingFrequency = CompoundingFrequency.QUARTERLY,
    maturity_date: dt.date | None = None,
) -> Decimal:
    """Value a fixed deposit as of a given date.

    Args:
        principal: The deposited principal (INR).
        annual_rate_pct: Annual interest rate as a percentage (e.g. ``7.1`` for 7.1%).
        start_date: The deposit start date.
        as_of_date: The valuation date.
        compounding: Compounding frequency (or SIMPLE for simple interest).
        maturity_date: Optional maturity date; accrual is capped here.

    Returns:
        The FD value (principal + accrued interest) as an INR Decimal (2dp). Returns
        the principal if ``as_of_date`` is on/before ``start_date``.

    Raises:
        ValueError: If ``maturity_date`` precedes ``start_date``.
    """
    p = to_decimal(principal)
    rate = to_decimal(annual_rate_pct) / Decimal(100)

    if maturity_date is not None and maturity_date < start_date:
        raise ValueError("maturity_date cannot be before start_date")

    effective_date = as_of_date
    if maturity_date is not None and effective_date > maturity_date:
        effective_date = maturity_date

    if effective_date <= start_date:
        return to_money(p)

    days = (effective_date - start_date).days
    t_years = Decimal(days) / Decimal(DAYS_PER_YEAR)

    periods = COMPOUNDING_PERIODS_PER_YEAR[compounding]
    if periods is None:  # simple interest
        value = p * (Decimal(1) + rate * t_years)
    else:
        n = Decimal(periods)
        value = p * _decimal_pow(Decimal(1) + rate / n, n * t_years)

    return to_money(value)


def fd_accrued_interest(
    principal: Decimal | int | str,
    annual_rate_pct: Decimal | int | str,
    start_date: dt.date,
    as_of_date: dt.date,
    compounding: CompoundingFrequency = CompoundingFrequency.QUARTERLY,
    maturity_date: dt.date | None = None,
) -> Decimal:
    """Return only the accrued interest portion of an FD (value − principal)."""
    value = calculate_fd_value(
        principal, annual_rate_pct, start_date, as_of_date, compounding, maturity_date
    )
    return to_money(value - to_decimal(principal))
