"""Tests for the DecimalText column type — the precision-preserving core of storage."""

from __future__ import annotations

from decimal import Decimal

import pytest

from wealthlog.db.types import DecimalText


class TestBindParam:
    def test_none_passes_through(self):
        assert DecimalText().process_bind_param(None, None) is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (Decimal("10.00"), "10.00"),
            (Decimal("0.000001"), "0.000001"),
            (Decimal("-5.5"), "-5.5"),
            (10, "10"),
            ("123.456", "123.456"),
        ],
    )
    def test_serializes_to_string(self, value, expected):
        assert DecimalText().process_bind_param(value, None) == expected


class TestResultValue:
    def test_none_passes_through(self):
        assert DecimalText().process_result_value(None, None) is None

    def test_returns_decimal(self):
        result = DecimalText().process_result_value("83.123456", None)
        assert isinstance(result, Decimal)
        assert result == Decimal("83.123456")

    def test_requantizes_when_quantum_given(self):
        col = DecimalText(Decimal("0.01"))
        assert col.process_result_value("10.1", None) == Decimal("10.10")
        assert col.process_result_value("10.1", None).as_tuple().exponent == -2

    def test_no_requantize_without_quantum(self):
        col = DecimalText()
        assert col.process_result_value("10.123456789", None) == Decimal("10.123456789")


class TestRoundTrip:
    @pytest.mark.parametrize(
        "value",
        [
            Decimal("0.01"),
            Decimal("999999999.99"),
            Decimal("0.000001"),
            Decimal("-12345.6789"),
            Decimal("83.500000"),
        ],
    )
    def test_exact_round_trip(self, value):
        col = DecimalText()
        stored = col.process_bind_param(value, None)
        loaded = col.process_result_value(stored, None)
        assert loaded == value
