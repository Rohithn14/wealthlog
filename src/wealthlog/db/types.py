"""Custom SQLAlchemy column types.

SQLite has no native DECIMAL type — its NUMERIC affinity coerces values through
floating point, which silently destroys monetary precision. :class:`DecimalText`
stores :class:`decimal.Decimal` values as canonical strings (TEXT) and rehydrates
them as exact Decimals, optionally re-quantizing to a fixed number of places.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from wealthlog.money import to_decimal


class DecimalText(TypeDecorator):
    """Store a :class:`Decimal` as exact TEXT, preserving full precision.

    Args:
        quantum: Optional Decimal quantum (e.g. ``Decimal("0.01")``) applied on load
            so values always carry a consistent number of decimal places.
    """

    impl = String
    cache_ok = True

    def __init__(self, quantum: Decimal | None = None, *args, **kwargs) -> None:
        self._quantum = quantum
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Decimal | int | str | None, dialect) -> str | None:
        """Serialize a Decimal to a canonical string for storage."""
        if value is None:
            return None
        return str(to_decimal(value))

    def process_result_value(self, value: str | None, dialect) -> Decimal | None:
        """Deserialize stored TEXT back into an exact Decimal."""
        if value is None:
            return None
        result = to_decimal(value)
        if self._quantum is not None:
            result = result.quantize(self._quantum)
        return result
