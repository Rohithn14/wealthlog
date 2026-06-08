"""XIRR (money-weighted annualised return) calculation.

Wraps :mod:`pyxirr` (fast, Rust-backed) with a wealthlog-friendly Decimal interface
and well-defined edge-case behaviour:

* Fewer than two cash flows                  -> ``None``.
* All cash flows the same sign (e.g. only
  buys, no sale/valuation yet)               -> ``None`` (pyxirr raises
  ``InvalidPaymentsError``; we treat "no return computable yet" as ``None``).
* No real root / non-convergence             -> ``None``.

Cash-flow sign convention: outflows (buys) are **negative**, inflows (sells,
dividends, and the terminal market valuation) are **positive**.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pyxirr

from wealthlog.logging_conf import get_logger

logger = get_logger(__name__)

CashFlow = tuple[dt.date, Decimal]


def calculate_xirr(cash_flows: list[CashFlow]) -> Decimal | None:
    """Compute the XIRR of a series of dated cash flows.

    Args:
        cash_flows: A list of ``(date, amount)`` tuples. Amounts are Decimals;
            outflows negative, inflows positive. Order does not matter.

    Returns:
        The annualised internal rate of return as a Decimal (e.g. ``Decimal("0.0997")``
        for ~9.97%), or ``None`` when it is undefined (too few flows, all one sign,
        or no convergence).
    """
    if len(cash_flows) < 2:
        return None

    dates = [d for d, _ in cash_flows]
    amounts = [float(a) for _, a in cash_flows]

    # If every amount is the same sign, XIRR is undefined.
    signs = {a > 0 for a in amounts if a != 0}
    if len(signs) < 2:
        return None

    try:
        rate = pyxirr.xirr(dates, amounts)
    except pyxirr.InvalidPaymentsError:
        return None
    except Exception as exc:  # noqa: BLE001 - surface unexpected solver errors as None + log
        logger.warning("XIRR computation failed: %s", exc)
        return None

    if rate is None:
        return None
    return Decimal(str(rate))
