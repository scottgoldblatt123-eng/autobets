"""Simulated exchange: deterministic matching against a book you control. No network, no money."""
from __future__ import annotations

import time

import itertools

from .. import ticks
from ..domain import (Fill, MarketBook, Order, OrderRequest, OrderType, PriceLevel,
                      Persistence, SelectionBook, Side, Status)
from .base import ExchangeAdapter, ExchangeError

MIN_STAKE = 1.0


class SimulatedExchange(ExchangeAdapter):
    def __init__(self) -> None:
        self._books: dict[str, MarketBook] = {}
        self._orders: dict[str, Order] = {}
        self._by_ref: dict[str, str] = {}
        self._fills: list[Fill] = []
        self._ids = itertools.count(1)
        self.fail_next_place = False       # test hook: simulate a lost response

    # ---- market control (test and replay side) -------------------------
    def set_book(self, market_id: str, selections: dict[str, dict], in_play: bool = False, status: str = "OPEN") -> None:
        """selections: {sel_id: {"backs": [(price, size)...], "lays": [(price, size)...]}}"""
        book = MarketBook(market_id, in_play, status=status)
        for sid, s in selections.items():
            book.selections[sid] = SelectionBook(
                sid,
                backs=sorted((PriceLevel(p, z) for p, z in s.get("backs", [])), key=lambda l: -l.price),
                lays=sorted((PriceLevel(p, z) for p, z in s.get("lays", [])), key=lambda l: l.price),
                last_traded=s.get("last"),
                status=s.get("status", "ACTIVE"),
            )
        self._books[market_id] = book
        self._match_resting(market_id)

    def go_in_play(self, market_id: str) -> None:
        """At the off: CANCEL-persistence orders lapse, TAKE_SP converts, KEEP stays."""
        self._books[market_id].in_play = True
        self._at_the_off(market_id)

    def _at_the_off(self, market_id: str) -> None:
        for o in self._orders.values():
            r = o.request
            if r.market_id != market_id or o.status not in (Status.UNMATCHED, Status.PARTIAL):
                continue
            if r.persistence is Persistence.CANCEL:
                o.status = Status.LAPSED
            elif r.persistence is Persistence.TAKE_SP:
                o.status = Status.CANCELLED  # SP conversion not modelled; treated as removed

    # ---- ExchangeAdapter -----------------------------------------------
    def get_book(self, market_id: str) -> MarketBook:
        if market_id not in self._books:
            raise ExchangeError(f"unknown market {market_id}")
        return self._books[market_id]

    def place_order(self, req: OrderRequest) -> Order:
        if req.client_ref and req.client_ref in self._by_ref:
            return self._orders[self._by_ref[req.client_ref]]
        if self.fail_next_place:
            self.fail_next_place = False
            # order is accepted by the exchange but the caller never hears back
            self._accept(req)
            raise ExchangeError("connection lost after send")
        return self._accept(req)

    def _accept(self, req: OrderRequest) -> Order:
        oid = f"S{next(self._ids)}"
        order = Order(oid, req)
        self._orders[oid] = order
        if req.client_ref:
            self._by_ref[req.client_ref] = oid
        if req.size < MIN_STAKE:
            order.status = Status.REJECTED
            return order
        if req.order_type is OrderType.LIMIT and not ticks.is_valid(req.price):
            order.status = Status.REJECTED
            return order
        if req.market_id not in self._books:
            order.status = Status.REJECTED
            return order
        book = self._books[req.market_id]
        sel = book.selections.get(req.selection_id)
        if book.status != "OPEN" or (sel is not None and sel.status != "ACTIVE"):
            order.status = Status.REJECTED            # Betfair refuses orders on a suspended or closed market and on removed runners
            return order
        self._match(order)
        return order

    def cancel_order(self, order_id: str) -> Order:
        o = self.get_order(order_id)
        if o.status in (Status.UNMATCHED, Status.PARTIAL):
            o.status = Status.CANCELLED
        return o

    def set_persistence(self, order_id: str, persistence: Persistence) -> Order:
        o = self.get_order(order_id)
        if o.status in (Status.UNMATCHED, Status.PARTIAL):
            o.request.persistence = persistence
        return o

    def replace_order(self, order_id: str, new_price: float) -> Order:
        o = self.get_order(order_id)
        if o.status not in (Status.UNMATCHED, Status.PARTIAL) or not ticks.is_valid(new_price):
            raise ExchangeError("cannot replace")
        o.request.price = new_price
        self._match(o)
        return o

    def open_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if o.status in (Status.UNMATCHED, Status.PARTIAL, Status.MATCHED)]

    def get_order(self, order_id: str) -> Order:
        if order_id not in self._orders:
            raise ExchangeError(f"unknown order {order_id}")
        return self._orders[order_id]

    def find_by_ref(self, client_ref: str) -> Order | None:
        oid = self._by_ref.get(client_ref)
        return self._orders[oid] if oid else None

    def export_state(self) -> dict:
        """Everything needed to rebuild this exchange after a restart: orders, fills and the id counter."""
        def req(r):
            return {"market_id": r.market_id, "selection_id": r.selection_id, "side": r.side.value, "price": r.price, "size": r.size,
                    "order_type": r.order_type.value, "persistence": r.persistence.value, "source": r.source, "client_ref": r.client_ref}
        return {"orders": [{"order_id": o.order_id, "request": req(o.request), "status": o.status.value, "matched": o.matched,
                            "avg_price": o.avg_price, "placed_at": o.placed_at, "last_fill_at": o.last_fill_at} for o in self._orders.values()],
                "fills": [{"order_id": f.order_id, "price": f.price, "size": f.size} for f in self._fills]}

    def import_state(self, st: dict) -> None:
        from ..domain import OrderRequest, OrderType, Persistence, Side
        self._orders.clear(); self._by_ref.clear(); self._fills.clear()
        top = 0
        for d in st.get("orders", []):
            r = d["request"]
            req = OrderRequest(r["market_id"], r["selection_id"], Side(r["side"]), r["price"], r["size"], OrderType(r["order_type"]),
                               Persistence(r["persistence"]), r["source"], r["client_ref"])
            o = Order(d["order_id"], req, Status(d["status"]), d["matched"], d["avg_price"], d["placed_at"], d.get("last_fill_at", 0.0))
            self._orders[o.order_id] = o
            if req.client_ref:
                self._by_ref[req.client_ref] = o.order_id
            if o.order_id[1:].isdigit():
                top = max(top, int(o.order_id[1:]))
        self._fills.extend(Fill(f["order_id"], f["price"], f["size"]) for f in st.get("fills", []))
        self._ids = itertools.count(top + 1)

    def all_orders(self) -> list[Order]:
        return list(self._orders.values())

    def fills(self) -> list[Fill]:
        return list(self._fills)

    # ---- matching -------------------------------------------------------
    def _match(self, o: Order) -> None:
        r = o.request
        if self._books[r.market_id].status != "OPEN":
            return                                   # nothing matches while a market is suspended
        sel = self._books[r.market_id].selections.get(r.selection_id)
        if sel is None:
            o.status = Status.REJECTED
            return
        levels = sel.backs if r.side is Side.BACK else sel.lays
        # BACK takes "available to back" at price >= asked; LAY takes "available to lay" at price <= asked
        for lvl in list(levels):
            if o.remaining <= 0:
                break
            ok = lvl.price >= r.price if r.side is Side.BACK else lvl.price <= r.price
            if not ok or lvl.size <= 0:
                continue
            take = round(min(o.remaining, lvl.size), 2)
            lvl.size = round(lvl.size - take, 2)
            total = o.avg_price * o.matched + lvl.price * take
            o.matched = round(o.matched + take, 2)
            o.avg_price = round(total / o.matched, 4)
            self._fills.append(Fill(o.order_id, lvl.price, take))
            o.last_fill_at = time.time()
        sel.backs = [l for l in sel.backs if l.size > 0]
        sel.lays = [l for l in sel.lays if l.size > 0]
        o.status = (Status.MATCHED if o.remaining <= 0
                    else Status.PARTIAL if o.matched > 0 else Status.UNMATCHED)

    def _match_resting(self, market_id: str) -> None:
        for o in self._orders.values():
            if o.request.market_id == market_id and o.status in (Status.UNMATCHED, Status.PARTIAL):
                self._match(o)
