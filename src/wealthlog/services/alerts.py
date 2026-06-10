"""Portfolio alert rules and evaluation (Milestone C3).

Rules are evaluated against the live service layer; a fired rule writes one
:class:`AlertEvent` per day so the same condition does not re-notify within a day.
The standalone watcher (``wealthlog.alerts.watcher``) calls :meth:`evaluate` and
delivers the results.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import AlertKind
from wealthlog.db.models import AlertEvent, AlertRule, Category, Investment
from wealthlog.services.budget import BudgetService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.results import FiredAlert
from wealthlog.services.sip import SIPService


class AlertService:
    """Manage alert rules and evaluate them against current portfolio state.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_rule(
        self,
        kind: AlertKind,
        threshold: Decimal | int | str | None = None,
        investment_id: int | None = None,
        category_id: int | None = None,
    ) -> AlertRule:
        """Create an alert rule.

        Raises:
            ValueError: If a threshold is missing for a kind that requires one.
        """
        if kind in (AlertKind.PRICE_DROP, AlertKind.BUDGET_PCT) and threshold is None:
            raise ValueError(f"{kind} requires a threshold")
        rule = AlertRule(
            kind=kind,
            threshold=Decimal(str(threshold)) if threshold is not None else None,
            investment_id=investment_id,
            category_id=category_id,
            active=True,
        )
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def list_rules(self, include_inactive: bool = False) -> list[AlertRule]:
        """List alert rules (active only by default)."""
        statement = select(AlertRule)
        if not include_inactive:
            statement = statement.where(AlertRule.active == True)  # noqa: E712
        return list(self.session.exec(statement).all())

    def deactivate(self, rule_id: int) -> bool:
        """Deactivate a rule; ``True`` if it existed."""
        rule = self.session.get(AlertRule, rule_id)
        if rule is None:
            return False
        rule.active = False
        self.session.add(rule)
        self.session.commit()
        return True

    def evaluate(self, as_of: dt.date | None = None) -> list[FiredAlert]:
        """Evaluate all active rules, persisting and returning newly fired alerts.

        Idempotent within a day: a rule that already fired on ``as_of`` is skipped,
        so repeated runs do not produce duplicate notifications.
        """
        as_of = as_of or dt.date.today()
        fired: list[FiredAlert] = []
        for rule in self.list_rules():
            if self._already_fired(rule.id, as_of):
                continue
            message = self._evaluate_rule(rule, as_of)
            if message is None:
                continue
            self.session.add(AlertEvent(rule_id=rule.id, fired_on=as_of, message=message))
            self.session.commit()
            fired.append(FiredAlert(rule_id=rule.id, kind=rule.kind, message=message))
        return fired

    def _already_fired(self, rule_id: int, as_of: dt.date) -> bool:
        return (
            self.session.exec(
                select(AlertEvent).where(
                    AlertEvent.rule_id == rule_id, AlertEvent.fired_on == as_of
                )
            ).first()
            is not None
        )

    def _evaluate_rule(self, rule: AlertRule, as_of: dt.date) -> str | None:
        if rule.kind == AlertKind.PRICE_DROP:
            return self._price_drop(rule, as_of)
        if rule.kind == AlertKind.BUDGET_PCT:
            return self._budget_pct(rule, as_of)
        if rule.kind == AlertKind.SIP_DUE:
            return self._sip_due(rule, as_of)
        return None

    def _price_drop(self, rule: AlertRule, as_of: dt.date) -> str | None:
        threshold = rule.threshold or Decimal(0)
        holdings = PortfolioService(self.session).get_holdings(as_of=as_of)
        breached = []
        for h in holdings:
            if rule.investment_id is not None and h.investment_id != rule.investment_id:
                continue
            if h.pnl_pct is not None and h.pnl_pct <= -threshold:
                breached.append(f"{h.symbol} {h.pnl_pct:+.2f}%")
        if not breached:
            return None
        return f"Price drop ≥ {threshold}%: " + ", ".join(breached)

    def _budget_pct(self, rule: AlertRule, as_of: dt.date) -> str | None:
        threshold = rule.threshold or Decimal(0)
        statuses = BudgetService(self.session).get_budget_status(as_of.year, as_of.month)
        breached = []
        for s in statuses:
            if rule.category_id is not None and s.category_id != rule.category_id:
                continue
            if s.pct_used >= threshold:
                breached.append(f"{s.category_name} {s.pct_used:.0f}%")
        if not breached:
            return None
        return f"Budget ≥ {threshold}% used: " + ", ".join(breached)

    def _sip_due(self, rule: AlertRule, as_of: dt.date) -> str | None:
        pending = SIPService(self.session).get_pending_sips(as_of=as_of)
        if rule.investment_id is not None:
            pending = [p for p in pending if p.investment_id == rule.investment_id]
        if not pending:
            return None
        symbols = ", ".join(sorted({p.symbol for p in pending}))
        return f"{len(pending)} SIP instalment(s) due: {symbols}"

    def describe_rule(self, rule: AlertRule) -> str:
        """Human-readable target for a rule (symbol/category/all)."""
        if rule.investment_id is not None:
            inv = self.session.get(Investment, rule.investment_id)
            return inv.symbol if inv else f"inv#{rule.investment_id}"
        if rule.category_id is not None:
            cat = self.session.get(Category, rule.category_id)
            return cat.name if cat else f"cat#{rule.category_id}"
        return "all"
