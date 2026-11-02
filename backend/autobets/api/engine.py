"""Trading engine behind the API: price feed + practice exchange + journal + guardrails + order service.
Modes: 'demo' (synthetic prices), 'practice' (real delayed Betfair prices, simulated orders). 'live' is not built yet."""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from .. import pnl, ticks
from ..domain import Order, OrderRequest, Persistence, Position, Side, Status
from ..guardrails import Guardrails
from ..journal import Journal
from ..order_service import Blocked, OrderService
from .demo import DemoFeed
from .practice import PracticeExchange

OPEN = (Status.UNMATCHED, Status.PARTIAL)


def locked(fn):
    def wrapper(self, *a, **k):
        with self.lock:
            return fn(self, *a, **k)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


class Engine:
    def __init__(self, feed, mode: str, journal_path: str = ":memory:") -> None:
        self.feed, self.mode = feed, mode
        self.lock = threading.RLock()          # the API serves requests on several threads
        self.ex = PracticeExchange()
        self.guard = Guardrails()
        self.service = OrderService(self.ex, Journal(journal_path), self.guard)
        self._info: dict[str, dict] = {}
        self._markets_cache: dict[str, tuple[float, list]] = {}

    @classmethod
    def demo(cls) -> "Engine":
        return cls(DemoFeed(), "demo")

    # ---- discovery ------------------------------------------------------
    @locked
    def markets(self, sport: str) -> list[dict]:
        hit = self._markets_cache.get(sport)
        if hit and time.time() - hit[0] < 30:
            return hit[1]
        if self.mode == "demo":
            res = self.feed.list_markets(sport)
        else:
            res = self.feed.list_markets({"tennis": "2", "football": "1"}[sport], "MATCH_ODDS", max_results=100)
        for m in res:
            self._info[m["market_id"]] = m
        self._markets_cache[sport] = (time.time(), res)
        return res

    @locked
    def info(self, ids: list[str]) -> dict[str, dict]:
        missing = [i for i in ids if i not in self._info]
        if missing:
            self._info.update(self.feed.market_info(missing))
        return {i: self._info[i] for i in ids if i in self._info}

    # ---- state ----------------------------------------------------------
    def positions(self) -> dict[str, dict[str, Position]]:
        pos: dict[str, dict[str, Position]] = defaultdict(lambda: defaultdict(Position))
        for f in self.ex.fills():
            r = self.ex.get_order(f.order_id).request
            pos[r.market_id][r.selection_id] = pnl.apply_fill(pos[r.market_id][r.selection_id], r.side, f.price, f.size)
        return pos

    @locked
    def state(self, ids: list[str]) -> dict:
        ids = ids[:5]
        books = self.feed.get_books(ids, depth=True) if ids else []
        self.ex.refresh(books)
        info = self.info(ids)
        pos = self.positions()
        markets = {}
        for b in books:
            mi = info.get(b.market_id, {})
            markets[b.market_id] = {
                "name": mi.get("name", ""), "event": mi.get("event", ""), "competition": mi.get("competition", ""),
                "start": mi.get("start"), "in_play": b.in_play, "runners": mi.get("runners", {}),
                "selections": {sid: {"backs": [[l.price, l.size] for l in s.backs], "lays": [[l.price, l.size] for l in s.lays],
                                     "traded": sorted([p, v] for p, v in s.traded.items()), "last": s.last_traded}
                               for sid, s in b.selections.items()},
                "positions": {sid: {"win": p.win, "lose": p.lose} for sid, p in pos.get(b.market_id, {}).items()},
            }
        orders = [self._order(o) for o in self.ex.open_orders() if o.request.market_id in ids]
        allpos = [p for m in pos.values() for p in m.values()]
        exposure = round(sum(-min(p.win, p.lose, 0) for p in allpos), 2)
        return {"mode": self.mode, "t": time.time(), "markets": markets, "orders": orders,
                "totals": {"exposure": exposure, "open_pnl": round(sum(p.win if p.win < 0 else 0 for p in allpos), 2)},
                "warnings": self.service.warnings[-3:]}

    @staticmethod
    def _order(o: Order) -> dict:
        r = o.request
        return {"order_id": o.order_id, "market_id": r.market_id, "selection_id": r.selection_id, "side": r.side.value,
                "price": r.price, "size": r.size, "matched": o.matched, "avg_price": o.avg_price,
                "remaining": o.remaining, "status": o.status.value, "source": r.source}

    # ---- actions --------------------------------------------------------
    @locked
    def place(self, market_id: str, selection_id: str, side: str, price: float, size: float, persistence: str = "KEEP") -> dict:
        if not ticks.is_valid(price):
            raise ValueError(f"{price} is not a valid Betfair price")
        if size < 1.0:
            raise ValueError("minimum stake is £1")
        self.service.warnings.clear()
        self.ex.refresh(self.feed.get_books([market_id], depth=True))       # match against the freshest prices
        req = OrderRequest(market_id, selection_id, Side(side), price, size, persistence=Persistence(persistence), source="manual")
        try:
            order = self.service.place(req)
        except Blocked as e:
            raise ValueError(str(e))
        if order is None:
            raise RuntimeError("order outcome unknown; it will be reconciled")
        return {"order": self._order(order), "warnings": list(self.service.warnings)}

    @locked
    def cancel(self, order_id: str) -> dict:
        return self._order(self.ex.cancel_order(order_id))

    @locked
    def cancel_many(self, market_id: str, selection_id: str | None = None, side: str | None = None) -> int:
        n = 0
        for o in self.ex.open_orders():
            r = o.request
            if o.status in OPEN and r.market_id == market_id and (selection_id in (None, r.selection_id)) and (side in (None, r.side.value)):
                self.ex.cancel_order(o.order_id); n += 1
        return n

    @locked
    def close_position(self, market_id: str, selection_id: str) -> dict:
        p = self.positions().get(market_id, {}).get(selection_id, Position())
        book = self.ex.get_book(market_id).selections[selection_id]
        # hedge at the price available right now on the side the hedge needs
        probe = pnl.hedge(p, (book.backs[0].price if book.backs else 2.0))
        if probe is None:
            return {"closed": False, "reason": "position is already level"}
        side, _, _ = probe
        levels = book.backs if side is Side.BACK else book.lays
        if not levels:
            return {"closed": False, "reason": "no price available to hedge at"}
        price = levels[0].price
        h = pnl.hedge(p, price)
        res = self.place(market_id, selection_id, h[0].value, price, h[1])
        return {"closed": True, "locked_profit": h[2], **res}
