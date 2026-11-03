"""Trading engine behind the API: price feed + practice exchange + journal + guardrails + order service.
Modes: 'demo' (synthetic prices), 'practice' (real delayed Betfair prices, simulated orders). 'live' is not built yet."""
from __future__ import annotations

import itertools
import threading
import time
from collections import defaultdict
from dataclasses import dataclass

from .. import pnl, ticks
from ..domain import Order, OrderRequest, Persistence, Position, Side, Status
from ..guardrails import Guardrails
from ..journal import Journal
from ..order_service import Blocked, OrderService
from .demo import DemoFeed
from .history import Tracker, load_logged
from .practice import PracticeExchange

OPEN = (Status.UNMATCHED, Status.PARTIAL)


@dataclass
class Trigger:
    """'Green up this selection when its price reaches `price`'. Plain code, held in memory (lost on restart)."""
    id: str
    market_id: str
    selection_id: str
    price: float
    direction: str           # 'le': fires when the last traded price is at or below; 'ge': at or above
    label: str               # 'take profit' | 'stop loss' (from the profit locked at that price)
    locked: float


def locked(fn):
    def wrapper(self, *a, **k):
        with self.lock:
            return fn(self, *a, **k)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    wrapper.__wrapped__ = fn
    return wrapper


class Engine:
    def __init__(self, feed, mode: str, journal_path: str = ":memory:", prices_db: str = "") -> None:
        self.feed, self.mode = feed, mode
        self.lock = threading.RLock()          # the API serves requests on several threads
        self.ex = PracticeExchange()
        self.guard = Guardrails()
        self.service = OrderService(self.ex, Journal(journal_path), self.guard)
        self._info: dict[str, dict] = {}
        self.triggers: dict[str, Trigger] = {}
        self.events: list[dict] = []
        self._trigger_ids = itertools.count(1)
        self._bg: threading.Thread | None = None
        self._markets_cache: dict[str, tuple[float, list]] = {}
        self.tracker = Tracker()
        self.prices_db, self._seeded = prices_db, set()      # logged history for the chart (price logger database)

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
        now = time.time()
        for b in books:
            if b.market_id not in self._seeded:
                self._seeded.add(b.market_id)
                self.tracker.seed(b.market_id, load_logged(self.prices_db, b.market_id))
        self.tracker.record(books, now)
        info = self.info(ids)
        pos = self.positions()
        markets = {}
        for b in books:
            mi = info.get(b.market_id, {})
            markets[b.market_id] = {
                "name": mi.get("name", ""), "event": mi.get("event", ""), "competition": mi.get("competition", ""),
                "start": mi.get("start"), "in_play": b.in_play, "runners": mi.get("runners", {}),
                "selections": {sid: {"backs": [[l.price, l.size] for l in s.backs], "lays": [[l.price, l.size] for l in s.lays],
                                     "traded": sorted([p, v] for p, v in s.traded.items()), "last": s.last_traded,
                                     "recent": self.tracker.recent(b.market_id, sid, s.traded, now)}
                               for sid, s in b.selections.items()},
                "positions": {sid: {"win": p.win, "lose": p.lose} for sid, p in pos.get(b.market_id, {}).items()},
            }
        for b in books:
            m = markets[b.market_id]
            sels = b.selections
            full = {sid: pos.get(b.market_id, {}).get(sid, Position()) for sid in sels}
            if any(abs(p.win) > 0.004 or abs(p.lose) > 0.004 for p in full.values()):
                m["outcomes"] = pnl.market_outcomes(full)
                plan = pnl.green_plan(m["outcomes"], {k: (v.backs[0].price if v.backs else None) for k, v in sels.items()},
                                      {k: (v.lays[0].price if v.lays else None) for k, v in sels.items()})
                m["green"] = plan
        self._check_triggers()
        orders = [self._order(o) for o in self.ex.open_orders() if o.status in OPEN and o.request.market_id in ids]
        allpos = [p for m in pos.values() for p in m.values()]
        exposure = round(sum(-min(p.win, p.lose, 0) for p in allpos), 2)
        return {"mode": self.mode, "t": time.time(), "markets": markets, "orders": orders,
                "totals": {"exposure": exposure, "open_pnl": round(sum(p.win if p.win < 0 else 0 for p in allpos), 2)},
                "warnings": self.service.warnings[-3:],
                "triggers": [t.__dict__ for t in self.triggers.values() if t.market_id in ids],
                "events": self.events[-5:]}

    @locked
    def busy(self) -> dict:
        """What would be lost by restarting the service: stops / take-profits (held in memory) and unmatched orders."""
        return {"triggers": len(self.triggers), "open_orders": len([o for o in self.ex.open_orders() if o.status in OPEN])}

    @locked
    def history(self, market_id: str, selection_id: str, seconds: int = 900) -> dict:
        return self.tracker.chart(market_id, selection_id, seconds)

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
        if h is None or h[1] < 1.0:
            return {"closed": False, "reason": "position is level to within the £1 minimum stake"}
        res = self.place(market_id, selection_id, h[0].value, price, h[1])
        return {"closed": True, "locked_profit": h[2], **res}


    # ---- market-level green up / hard close ------------------------------
    @locked
    def green_market(self, market_id: str, hard: bool = False) -> dict:
        """Equalise every outcome of the market at the prices available now. hard=True first cancels unmatched orders."""
        cancelled = self.cancel_many(market_id) if hard else 0
        self.ex.refresh(self.feed.get_books([market_id], depth=False))
        book = self.ex.get_book(market_id)
        pos = self.positions().get(market_id, {})
        full = {sid: pos.get(sid, Position()) for sid in book.selections}
        plan = pnl.green_plan(pnl.market_outcomes(full), {k: (v.backs[0].price if v.backs else None) for k, v in book.selections.items()},
                              {k: (v.lays[0].price if v.lays else None) for k, v in book.selections.items()})
        if plan is None:
            return {"greened": False, "cancelled": cancelled, "reason": "nothing to green up (level, or no prices available)"}
        placed = []
        for b in plan["bets"]:
            r = self.place(market_id, b["selection_id"], b["side"], b["price"], b["stake"])
            placed.append({**b, "status": r["order"]["status"]})
        return {"greened": True, "cancelled": cancelled, "locked": plan["locked"], "level": plan["level"], "placed": placed}

    # ---- triggers ----------------------------------------------------------
    @locked
    def add_trigger(self, market_id: str, selection_id: str, price: float) -> dict:
        if not ticks.is_valid(price):
            raise ValueError(f"{price} is not a valid Betfair price")
        self.ex.refresh(self.feed.get_books([market_id], depth=False))
        sel = self.ex.get_book(market_id).selections[selection_id]
        p = self.positions().get(market_id, {}).get(selection_id, Position())
        if abs(p.win) < 0.005 and abs(p.lose) < 0.005:
            raise ValueError("no position on this selection to protect")
        ref = sel.last_traded or (sel.backs[0].price if sel.backs else None)
        if ref is None:
            raise ValueError("no current price for this selection")
        if abs(price - ref) < 1e-9:
            raise ValueError("that is the current price; just hedge it")
        h = pnl.hedge(p, price)
        locked_at = h[2] if h else 0.0
        t = Trigger(f"T{next(self._trigger_ids)}", market_id, selection_id, price, "le" if price < ref else "ge",
                    "take profit" if locked_at >= 0 else "stop loss", locked_at)
        self.triggers[t.id] = t
        return t.__dict__

    @locked
    def cancel_trigger(self, trigger_id: str) -> bool:
        return self.triggers.pop(trigger_id, None) is not None

    def _check_triggers(self) -> None:
        """Fire any trigger whose price has been reached (uses the books already loaded into the exchange)."""
        for t in list(self.triggers.values()):
            try:
                sel = self.ex.get_book(t.market_id).selections[t.selection_id]
            except Exception:
                continue
            ltp = sel.last_traded
            if ltp is None:
                continue
            if (t.direction == "le" and ltp <= t.price + 1e-9) or (t.direction == "ge" and ltp >= t.price - 1e-9):
                self.triggers.pop(t.id, None)
                try:
                    res = self.close_position.__wrapped__(self, t.market_id, t.selection_id)
                    msg = f"{t.label.capitalize()} fired at {t.price:.2f}: " + (f"closed, locked £{res.get('locked_profit', 0):.2f}" if res.get("closed") else res.get("reason", "nothing to close"))
                except Exception as e:           # never let a failed trigger break the loop; say so loudly
                    msg = f"{t.label.capitalize()} at {t.price:.2f} FAILED to close: {e}"
                self.events.append({"t": time.time(), "text": msg, "trigger": t.id})

    @locked
    def check_triggers_now(self) -> None:
        mids = sorted({t.market_id for t in self.triggers.values()})
        if mids:
            self.ex.refresh(self.feed.get_books(mids, depth=False))
            self._check_triggers()

    def start_background(self, every: float = 2.0) -> None:
        """Keep triggers working when no browser is open."""
        if self._bg:
            return
        def loop():
            while True:
                time.sleep(every)
                try:
                    self.check_triggers_now()
                except Exception:
                    pass
        self._bg = threading.Thread(target=loop, daemon=True, name="triggers")
        self._bg.start()
