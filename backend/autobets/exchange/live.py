"""The engine's view of the real Betfair exchange (live mode).

Same surface as the practice exchange, but every order is a real Betfair order. Safety design:
- Starts DISARMED. While disarmed no new order can be placed; cancelling always works.
- Keeps a local mirror of the orders (refreshed from listCurrentOrders at most every `sync_every` seconds) so the engine's
  many reads cost no API calls; place and cancel update the mirror at once.
- Fills are derived from changes in matched size, so positions and P&L work exactly as in practice mode.
- `reconcile()` at start-up compares the saved mirror with what Betfair holds and reports every difference."""
from __future__ import annotations

import threading
import time

from ..domain import Fill, MarketBook, Order, OrderRequest, Persistence, Status
from .base import ExchangeAdapter, ExchangeError

LIVE = (Status.UNMATCHED, Status.PARTIAL)


class LiveExchange(ExchangeAdapter):
    def __init__(self, adapter, sync_every: float = 1.5) -> None:
        self.bf, self.sync_every = adapter, sync_every
        self._books: dict[str, MarketBook] = {}
        self._orders: dict[str, Order] = {}
        self._by_ref: dict[str, str] = {}
        self._fills: list[Fill] = []
        self._lock = threading.RLock()
        self._last_sync = 0.0
        self.sync_error = ""
        self.sync_ok_at = 0.0
        self.armed = False

    # ---- arming -------------------------------------------------------------
    def arm(self, confirm: str) -> None:
        if confirm != "SEND-REAL-ORDERS":
            raise ExchangeError("arming live trading needs the exact confirmation phrase")
        self.bf.enable_trading("SEND-REAL-ORDERS")
        self.armed = True

    def disarm(self) -> None:
        self.armed = False

    def _need_armed(self) -> None:
        if not self.armed:
            raise ExchangeError("live trading is not armed: no new real orders are sent until you arm it in Settings")

    # ---- books (fed by the engine's price feed) ------------------------------------
    def refresh(self, books: list[MarketBook]) -> None:
        for b in books:
            self._books[b.market_id] = b
        self.sync()

    def get_book(self, market_id: str) -> MarketBook:
        if market_id not in self._books:
            raise ExchangeError(f"unknown market {market_id}")
        return self._books[market_id]

    # ---- orders ---------------------------------------------------------------------
    def place_order(self, req: OrderRequest) -> Order:
        self._need_armed()
        with self._lock:
            o = self.bf.place_order(req)
            o.request.source, o.request.client_ref = req.source, req.client_ref or o.request.client_ref      # Betfair does not store who placed it
            self._adopt(o)
            return self._orders[o.order_id]

    def cancel_order(self, order_id: str) -> Order:
        with self._lock:
            o = self.bf.cancel_order(order_id)        # cancelling is never blocked by disarming
            self._adopt(o)
            return self._orders[order_id]

    def replace_order(self, order_id: str, new_price: float) -> Order:
        self._need_armed()
        with self._lock:
            old = self._orders.get(order_id)
            o = self.bf.replace_order(order_id, new_price)
            if old is not None and old.order_id != o.order_id:
                old.status = Status.CANCELLED
            self._adopt(o)
            return self._orders[o.order_id]

    def set_persistence(self, order_id: str, persistence: Persistence) -> Order:
        with self._lock:
            o = self.bf.update_persistence(order_id, persistence)
            self._adopt(o)
            return self._orders[order_id]

    def open_orders(self) -> list[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.status in (Status.UNMATCHED, Status.PARTIAL, Status.MATCHED)]

    def all_orders(self) -> list[Order]:
        with self._lock:
            return list(self._orders.values())

    def get_order(self, order_id: str) -> Order:
        with self._lock:
            if order_id in self._orders:
                return self._orders[order_id]
            o = self.bf.get_order(order_id)
            self._adopt(o)
            return self._orders[order_id]

    def find_by_ref(self, client_ref: str) -> Order | None:
        with self._lock:
            oid = self._by_ref.get(client_ref)
            if oid:
                return self._orders[oid]
            o = self.bf.find_by_ref(client_ref)
            if o:
                self._adopt(o)
                return self._orders[o.order_id]
            return None

    def fills(self) -> list[Fill]:
        with self._lock:
            return list(self._fills)

    # ---- mirror and fills ----------------------------------------------------------------
    def _adopt(self, o: Order) -> None:
        """Take a Betfair order into the mirror, recording any newly matched size as a fill."""
        prev = self._orders.get(o.order_id)
        before, before_avg = (prev.matched, prev.avg_price) if prev else (0.0, 0.0)
        if o.matched > before + 0.004:
            delta = round(o.matched - before, 2)
            price = (o.avg_price * o.matched - before_avg * before) / delta if delta > 0 else o.avg_price
            self._fills.append(Fill(o.order_id, round(price, 3), delta))
            o.last_fill_at = time.time()
        elif prev:
            o.last_fill_at = prev.last_fill_at
        if prev:
            o.placed_at = prev.placed_at
        self._orders[o.order_id] = o
        if o.request.client_ref:
            self._by_ref[o.request.client_ref] = o.order_id

    def sync(self, force: bool = False) -> bool:
        """Pull Betfair's current orders into the mirror. Returns False if Betfair could not be reached (the mirror is left as it was)."""
        with self._lock:
            if not force and time.time() - self._last_sync < self.sync_every:
                return True
            self._last_sync = time.time()
            try:
                current = {o.order_id: o for o in self.bf.open_orders()}
                for o in current.values():
                    mine = self._orders.get(o.order_id)
                    if mine is not None:
                        o.request.source = mine.request.source                  # Betfair does not know who placed it
                        o.request.client_ref = o.request.client_ref or mine.request.client_ref
                    self._adopt(o)
                for oid, mine in list(self._orders.items()):                       # live here but not listed: it finished or was removed
                    if oid not in current and mine.status in LIVE:
                        try:
                            self._adopt(self._carry(self.bf.get_order(oid), mine))
                        except ExchangeError:                                       # gone from Betfair: whatever matched stands
                            mine.status = Status.MATCHED if mine.matched > 0 else Status.LAPSED
                self.sync_error, self.sync_ok_at = "", time.time()
                return True
            except ExchangeError as e:
                self.sync_error = str(e)
                return False

    @staticmethod
    def _carry(o: Order, mine: Order) -> Order:
        o.request.source = mine.request.source
        o.request.client_ref = o.request.client_ref or mine.request.client_ref
        return o

    def reconcile(self) -> dict:
        """Start-up check: adopt orders Betfair holds that we do not know, and close mirror orders Betfair no longer has. Reports every difference."""
        with self._lock:
            known = set(self._orders)
            ok = self.sync(force=True)
            if not ok:
                return {"ok": False, "error": self.sync_error, "adopted": [], "closed": []}
            adopted = [oid for oid in self._orders if oid not in known]
            for oid in adopted:
                self._orders[oid].request.source = "external"
            closed = [oid for oid in known if self._orders[oid].status in (Status.CANCELLED, Status.LAPSED) and self._orders[oid].matched == 0]
            return {"ok": True, "adopted": adopted, "closed": closed}

    # ---- restart persistence ------------------------------------------------------------------
    def export_state(self) -> dict:
        def req(r):
            return {"market_id": r.market_id, "selection_id": r.selection_id, "side": r.side.value, "price": r.price, "size": r.size,
                    "order_type": r.order_type.value, "persistence": r.persistence.value, "source": r.source, "client_ref": r.client_ref}
        with self._lock:
            return {"orders": [{"order_id": o.order_id, "request": req(o.request), "status": o.status.value, "matched": o.matched,
                                "avg_price": o.avg_price, "placed_at": o.placed_at, "last_fill_at": o.last_fill_at} for o in self._orders.values()],
                    "fills": [{"order_id": f.order_id, "price": f.price, "size": f.size} for f in self._fills]}

    def import_state(self, st: dict) -> None:
        from ..domain import OrderType, Side
        with self._lock:
            self._orders.clear(); self._by_ref.clear(); self._fills.clear()
            for d in st.get("orders", []):
                r = d["request"]
                rq = OrderRequest(r["market_id"], r["selection_id"], Side(r["side"]), r["price"], r["size"], OrderType(r["order_type"]),
                                  Persistence(r["persistence"]), r["source"], r["client_ref"])
                o = Order(d["order_id"], rq, Status(d["status"]), d["matched"], d["avg_price"], d["placed_at"], d.get("last_fill_at", 0.0))
                self._orders[o.order_id] = o
                if rq.client_ref:
                    self._by_ref[rq.client_ref] = o.order_id
            self._fills.extend(Fill(f["order_id"], f["price"], f["size"]) for f in st.get("fills", []))
