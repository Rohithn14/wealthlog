"""Tests for AlertService: rule CRUD, evaluation per kind, and same-day dedup."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AlertKind, AssetType, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.alerts import AlertService
from wealthlog.services.budget import BudgetService
from wealthlog.services.expense import ExpenseService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.sip import SIPService


@pytest.fixture
def svc(db_session):
    return AlertService(db_session)


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


def _add_price(session, investment_id, price_inr):
    session.add(
        PriceCache(
            investment_id=investment_id,
            price_native=Decimal(price_inr),
            price_inr=Decimal(price_inr),
            fetched_at=dt.datetime.now(),
        )
    )
    session.commit()


class TestRuleCrud:
    def test_threshold_required(self, svc):
        with pytest.raises(ValueError):
            svc.add_rule(AlertKind.PRICE_DROP)

    def test_sip_due_needs_no_threshold(self, svc):
        rule = svc.add_rule(AlertKind.SIP_DUE)
        assert rule.id is not None

    def test_add_and_deactivate(self, svc):
        rule = svc.add_rule(AlertKind.BUDGET_PCT, threshold="90")
        assert svc.deactivate(rule.id) is True
        assert svc.list_rules() == []
        assert len(svc.list_rules(include_inactive=True)) == 1


class TestPriceDrop:
    def test_fires_on_drop(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, inv.id, "80")  # -20%
        svc.add_rule(AlertKind.PRICE_DROP, threshold="10")
        fired = svc.evaluate(as_of=dt.date(2026, 2, 1))
        assert len(fired) == 1
        assert "INFY.NS" in fired[0].message

    def test_no_fire_above_threshold(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, inv.id, "95")  # -5%, less than 10
        svc.add_rule(AlertKind.PRICE_DROP, threshold="10")
        assert svc.evaluate(as_of=dt.date(2026, 2, 1)) == []

    def test_scoped_to_investment(self, svc, portfolio, db_session):
        a = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        b = portfolio.add_investment("B.NS", "B", AssetType.STOCK_IN)
        portfolio.add_transaction(a.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(b.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, a.id, "50")
        _add_price(db_session, b.id, "50")
        svc.add_rule(AlertKind.PRICE_DROP, threshold="10", investment_id=a.id)
        fired = svc.evaluate(as_of=dt.date(2026, 2, 1))
        assert len(fired) == 1
        assert "A.NS" in fired[0].message and "B.NS" not in fired[0].message


class TestBudgetPct:
    def test_fires_when_over_pct(self, svc, db_session):
        cat = BudgetService(db_session)
        category_id = _category(db_session, "Food")
        cat.set_budget(category_id, 6, 2026, "1000")
        ExpenseService(db_session).add_expense(dt.date(2026, 6, 5), "950", category_id=category_id)
        svc.add_rule(AlertKind.BUDGET_PCT, threshold="90")
        fired = svc.evaluate(as_of=dt.date(2026, 6, 10))
        assert len(fired) == 1
        assert "Food" in fired[0].message


class TestSipDue:
    def test_fires_when_pending(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("120503", "MF", AssetType.MF)
        SIPService(db_session).add_schedule(inv.id, "5000", 5, dt.date(2026, 1, 1))
        svc.add_rule(AlertKind.SIP_DUE)
        fired = svc.evaluate(as_of=dt.date(2026, 3, 10))
        assert len(fired) == 1
        assert "SIP" in fired[0].message


class TestDedup:
    def test_same_day_fires_once(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, inv.id, "80")
        svc.add_rule(AlertKind.PRICE_DROP, threshold="10")
        first = svc.evaluate(as_of=dt.date(2026, 2, 1))
        second = svc.evaluate(as_of=dt.date(2026, 2, 1))
        assert len(first) == 1
        assert second == []  # already fired today

    def test_fires_again_next_day(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, inv.id, "80")
        svc.add_rule(AlertKind.PRICE_DROP, threshold="10")
        svc.evaluate(as_of=dt.date(2026, 2, 1))
        again = svc.evaluate(as_of=dt.date(2026, 2, 2))
        assert len(again) == 1


def _category(session, name):
    from wealthlog.constants import CategoryType
    from wealthlog.db.models import Category

    cat = Category(name=name, type=CategoryType.EXPENSE)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat.id
