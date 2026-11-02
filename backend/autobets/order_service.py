"""Journal-before-send order placement with idempotency and reconciliation."""
from __future__ import annotations

import uuid

from .domain import Order, OrderRequest, Status
from .exchange.base import ExchangeAdapter, ExchangeError
from .guardrails import Guardrails
from .journal import CONFIRMED, FAILED, INTENT, SENT, UNKNOWN, Journal


class Blocked(Exception):
    pass


class OrderService:
    def __init__(self, exchange: ExchangeAdapter, journal: Journal, guardrails: Guardrails) -> None:
        self.ex, self.j, self.g = exchange, journal, guardrails
        self.warnings: list[str] = []

    def place(self, req: OrderRequest) -> Order | None:
        ok, why = self.g.check(req.source, req.size)
        if not ok:
            raise Blocked(why)
        if why:
            self.warnings.append(why)
        if not req.client_ref:
            req.client_ref = uuid.uuid4().hex
        self.j.intent(req.client_ref, req)               # 1. write ahead
        self.j.set_state(req.client_ref, SENT)           # 2. mark sent
        try:
            order = self.ex.place_order(req)             # 3. send
        except ExchangeError as e:
            self.j.set_state(req.client_ref, UNKNOWN, note=str(e))   # outcome unknown: reconcile
            return None
        state = FAILED if order.status is Status.REJECTED else CONFIRMED
        self.j.set_state(req.client_ref, state, exchange_id=order.order_id)
        return order

    def reconcile(self) -> list[str]:
        """Resolve orders whose outcome is unknown by asking the exchange. Never re-places an order:
        found -> confirmed; not found -> marked failed (the user is told, nothing is sent again)."""
        resolved = []
        for ref in self.j.in_state(UNKNOWN, SENT, INTENT):
            found = self.ex.find_by_ref(ref)
            if found is None:
                self.j.set_state(ref, FAILED, note="not found on exchange")
            else:
                self.j.set_state(ref, FAILED if found.status is Status.REJECTED else CONFIRMED,
                                 exchange_id=found.order_id, note="reconciled")
            resolved.append(ref)
        return resolved
