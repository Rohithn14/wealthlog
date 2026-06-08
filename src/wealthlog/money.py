"""Decimal helpers for monetary, price, FX, and unit quantities.

All monetary arithmetic in wealthlog uses :class:`decimal.Decimal` — never ``float``.
These helpers enforce consistent quantization (rounding) so values stored in the DB and
shown in the UI always carry the correct number of decimal places.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from wealthlog.constants import (
    FX_QUANTET,
    MONEY_QUANTET,
    PRICE_QUANTET,
    UNITS_QUANTET,
)

Numeric = Decimal | int | str


def to_decimal(value: Numeric) -> Decimal:
    """Coerce a value to :class:`Decimal` safely.

    Args:
        value: A Decimal, int, or numeric string. Floats are rejected to avoid
            binary-float precision errors — pass a string instead.

    Returns:
        The value as a Decimal.

    Raises:
        TypeError: If ``value`` is a float.
        ValueError: If ``value`` cannot be parsed as a Decimal.
    """
    if isinstance(value, float):
        raise TypeError("Refusing to convert float to Decimal; pass a str or Decimal instead.")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot convert {value!r} to Decimal") from exc


def _quantize(value: Numeric, quantum: Decimal) -> Decimal:
    return to_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def to_money(value: Numeric) -> Decimal:
    """Quantize to INR money precision (2 dp, half-up)."""
    return _quantize(value, MONEY_QUANTET)


def to_price(value: Numeric) -> Decimal:
    """Quantize to per-unit price precision (4 dp, half-up)."""
    return _quantize(value, PRICE_QUANTET)


def to_fx(value: Numeric) -> Decimal:
    """Quantize to FX-rate precision (6 dp, half-up)."""
    return _quantize(value, FX_QUANTET)


def to_units(value: Numeric) -> Decimal:
    """Quantize to unit-quantity precision (4 dp, half-up)."""
    return _quantize(value, UNITS_QUANTET)
