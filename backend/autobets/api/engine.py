"""Trading engine behind the API: price feed + practice exchange + journal + guardrails + order service.
Modes: 'demo' (synthetic prices), 'practice' (real delayed Betfair prices, simulated orders). 'live' is not built yet."""
from __future__ import annotations

import itertools
import json
import os
import threading
import datetime as dt
import re
import time
from zoneinfo import ZoneInfo
from collections import defaultdict
from dataclasses import asdict, dataclass, field

from .. import pnl, ticks
from ..domain import Order, OrderRequest, Persistence, Position, Side, Status
from ..alerts import Alerts
from ..guardrails import Guardrails, Limits
from ..journal import Journal
from ..ledger import Ledger
from ..plan import Plan
from ..recs import Recs
from ..order_service import Blocked, OrderService
from ..scripts import ScriptStore, check, describe, describe_cond, evaluate, gain_ticks, headline
from ..settings import Settings
from .demo import DemoFeed
from .history import Tracker, load_logged
from .practice import PracticeExchange

OPEN = (Status.UNMATCHED, Status.PARTIAL)


@dataclass
class Trigger:
    """'Green up this selection when its price reaches `price`'. Plain code; saved to disk with the rest of the state so it survives a restart."""
    id: str
    market_id: str
    selection_id: str
    price: float
    direction: str           # 'le': fires when the last traded price is at or below; 'ge': at or above
    label: str               # 'take profit' | 'stop loss' (from the profit locked at that price)
    locked: float
    cancel: list = field(default_factory=list)   # order ids to cancel first when it fires (an entry's resting offset order)
    link: str = ""                               # the entry order this stop belongs to, if any


@dataclass
class MarketTrigger:
    """'Green up the whole market when the profit I could lock reaches / falls to `level`'. Saved to disk so it survives a restart."""
    id: str
    market_id: str
    level: float
    direction: str           # 'ge' | 'le'
    label: str               # 'take profit' | 'stop loss'


@dataclass
class Entry:
    """A bet placed with an offset and/or stop: when it matches, a closing bet is placed `offset` ticks away and a stop is armed."""
    order_id: str
    market_id: str
    selection_id: str
    side: str
    offset: int
    stop: int
    persistence: str
    processed: float = 0.0
    stop_id: str = ""
    close_ids: list = field(default_factory=list)


def locked(fn):
    def wrapper(self, *a, **k):
        with self.lock:
            try:
                return fn(self, *a, **k)
            finally:
                self._save()                  # keep what is held in memory safe on disk (cheap when nothing changed)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    wrapper.__wrapped__ = fn
    return wrapper


class _TrackedFeed:
    """Wraps the price feed to remember when it last answered and the last error, for the health panel. Everything else passes straight through."""

    def __init__(self, feed, engine) -> None:
        object.__setattr__(self, "_feed", feed)
        object.__setattr__(self, "_engine", engine)

    def __getattr__(self, name):
        attr = getattr(self._feed, name)
        if name not in ("get_books", "list_markets", "market_info") or not callable(attr):
            return attr

        def call(*a, **k):
            try:
                out = attr(*a, **k)
            except Exception as ex:      # noqa: BLE001
                self._engine.feed_error, self._engine.feed_error_at = f"{type(ex).__name__}: {ex}", time.time()
                raise
            self._engine.feed_ok_at = time.time()
            return out
        return call


_PLACEHOLDER = re.compile(r"^\s*(test|demo|dummy|placeholder)\b|\bvirtual\b|\(virtual\)", re.I)


def is_placeholder(m: dict) -> bool:
    """Betfair's own test events ('Test W v Test F') and virtual fixtures are not real matches and never belong in the list."""
    sides = [x for x in re.split(r"\s+v(?:s\.?)?\s+", m.get("event", ""), flags=re.I) if x.strip()]
    return bool(sides) and (all(_PLACEHOLDER.search(x) for x in sides) or bool(_PLACEHOLDER.search(m.get("competition", "") or "")) and any(_PLACEHOLDER.search(x) for x in sides))


UK = ZoneInfo("Europe/London")


class Engine:
    def __init__(self, feed, mode: str, journal_path: str = ":memory:", prices_db: str = "", state_path: str = "", exchange=None) -> None:
        self.feed, self.mode = _TrackedFeed(feed, self), mode
        self.feed_ok_at, self.feed_error, self.feed_error_at = 0.0, "", 0.0
        self.lock = threading.RLock()          # the API serves requests on several threads
        self.ex = exchange or PracticeExchange()
        self._pxhist: dict[tuple, list] = {}
        self.live = mode == "live"
        self.guard = Guardrails()
        self.service = OrderService(self.ex, Journal(journal_path), self.guard)
        self._info: dict[str, dict] = {}
        self.triggers: dict[str, Trigger] = {}
        self.events: list[dict] = []
        self.log: list[dict] = []                      # activity log: everything the engine did, newest last
        self.mtriggers: dict[str, MarketTrigger] = {}
        self.entries: dict[str, Entry] = {}
        self.fok: dict[str, float] = {}                # order_id -> time after which any unmatched part is cancelled
        self._trigger_ids = itertools.count(1)
        self._bg: threading.Thread | None = None
        self._markets_cache: dict[str, tuple[float, list]] = {}
        self._event_cache: dict[str, tuple[float, list]] = {}
        self.tracker = Tracker()
        self.prices_db, self._seeded = prices_db, set()      # logged history for the chart (price logger database)
        self.state_path, self._last_saved = state_path, ""
        self.settings = Settings()
        self.ledger = Ledger()
        self.scripts = ScriptStore()
        self.plan = Plan()
        self.alerts = Alerts()
        self.price_store = None                        # set by the app when the price log is running
        self.backtests: list[dict] = []
        self.recs = Recs()
        self.context_fn = None                         # set by the app: market info -> live score / set / minute, when known
        self._susp: dict[str, float] = {}
        self._mtm_m: dict[str, dict] = {}
        self._mtm = 0.0                                # open positions marked to market (what closing them now would lock in)
        self._load()
        self._apply_settings()

    # ---- keeping state across restarts ----------------------------------
    def _snapshot(self) -> dict:
        return {"v": 1, "triggers": [asdict(t) for t in self.triggers.values()], "mtriggers": [asdict(t) for t in self.mtriggers.values()],
                "entries": [asdict(t) for t in self.entries.values()], "fok": self.fok, "log": self.log[-200:],
                "exchange": self.ex.export_state(), "settings": self.settings.to_dict(), "ledger": self.ledger.entries,
                "scripts": self.scripts.export(), "plan": self.plan.export(), "alerts": self.alerts.export(), "recs": self.recs.export(), "backtests": self.backtests[-10:]}

    def _save(self) -> None:
        """Write stops, entries, auto-greens, fill-or-kill timers and (in practice) the practice orders and positions to disk, so a restart or
        crash loses nothing. Never allowed to break trading: a failed write is only logged."""
        if not self.state_path:
            return
        try:
            text = json.dumps(self._snapshot(), sort_keys=True)
            if text == self._last_saved:
                return
            tmp = self.state_path + ".tmp"
            with open(tmp, "w") as f:
                f.write(text)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
            self._last_saved = text
        except Exception as ex:          # noqa: BLE001
            if getattr(self, "_save_warned", None) != str(ex):
                self._save_warned = str(ex)
                self._log(f"Could not save state to disk: {ex}", "warn")

    def _load(self) -> None:
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            st = json.load(open(self.state_path))
            self.ex.import_state(st.get("exchange", {}))
            self.triggers = {t["id"]: Trigger(**t) for t in st.get("triggers", [])}
            self.mtriggers = {t["id"]: MarketTrigger(**t) for t in st.get("mtriggers", [])}
            self.entries = {t["order_id"]: Entry(**t) for t in st.get("entries", [])}
            self.fok = {k: float(v) for k, v in st.get("fok", {}).items()}
            self.log = list(st.get("log", []))
            self.settings = Settings.from_dict(st.get("settings", {}))
            self.ledger = Ledger(st.get("ledger", []))
            self.scripts = ScriptStore(st.get("scripts"))
            self.plan = Plan.load(st.get("plan"))
            self.alerts = Alerts.load(st.get("alerts"))
            self.recs = Recs.load(st.get("recs"))
            self.backtests = list(st.get("backtests", []))
            top = max([int(i[1:]) for i in list(self.triggers) + list(self.mtriggers) if i[1:].isdigit()] or [0])
            self._trigger_ids = itertools.count(top + 1)
            self._last_saved = json.dumps(self._snapshot(), sort_keys=True)
            self._log(f"Restarted: restored {len(self.ex.all_orders())} orders, {len(self.triggers)} stops, {len(self.entries)} entries and {len(self.mtriggers)} auto-greens", "info")
            self.alerts.add("system", f"AutoBets restarted at {self._uk_clock()}", f"Restored {len(self.ex.all_orders())} orders, {len(self.triggers)} stops and {len(self.entries)} entries. If you did not expect this, check the server log.", False)
        except Exception as ex:          # noqa: BLE001
            self._log(f"Could not restore saved state ({ex}); starting empty", "warn")

    def _log(self, text: str, kind: str = "info") -> None:
        self.log.append({"t": time.time(), "kind": kind, "text": text})
        del self.log[:-300]

    @classmethod
    def demo(cls) -> "Engine":
        return cls(DemoFeed(), "demo")

    # ---- discovery ------------------------------------------------------
    @locked
    def markets(self, sport: str, day: str | None = None) -> list[dict]:
        """Match-odds markets. day=None: the next to start. day='YYYY-MM-DD': every market scheduled on that UK calendar day."""
        if day:
            dt.datetime.strptime(day, "%Y-%m-%d")                      # ValueError for a non-date (the API turns it into a 400)
        key = f"{sport}|{day or ''}"
        hit = self._markets_cache.get(key)
        if hit and time.time() - hit[0] < 30:
            return hit[1]
        if self.mode == "demo":
            res = self.feed.list_markets(sport) if not day or day == dt.datetime.now(UK).strftime("%Y-%m-%d") else []
        elif day:
            res = self._markets_on(sport, day)
        else:
            res = self.feed.list_markets({"tennis": "2", "football": "1"}[sport], "MATCH_ODDS", max_results=100)
            res = [m for m in res if not is_placeholder(m)]
            try:                      # the catalogue does not say which markets are in play; the books do (<= 40 markets per call)
                flags = {}
                for i in range(0, len(res), 40):
                    for b in self.feed.get_books([m["market_id"] for m in res[i:i + 40]]):
                        flags[b.market_id] = b.in_play
                for m in res:
                    m["in_play"] = flags.get(m["market_id"], False)
            except Exception:
                pass
        for m in res:
            self._info[m["market_id"]] = m
        self._markets_cache[key] = (time.time(), res)
        return res

    def _markets_on(self, sport: str, day: str) -> list[dict]:
        """One UK calendar day, fetched in 3-hour windows so Betfair's 100-result cap cannot cut a busy day short."""
        d = dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UK)
        start = d.astimezone(dt.timezone.utc)
        end = (dt.datetime.strptime(day, "%Y-%m-%d") + dt.timedelta(days=1)).replace(tzinfo=UK).astimezone(dt.timezone.utc)
        seen: dict[str, dict] = {}
        t = start
        while t < end:
            nxt = min(t + dt.timedelta(hours=3), end)
            for m in self.feed.list_markets({"tennis": "2", "football": "1"}[sport], "MATCH_ODDS", max_results=100,
                                            start_from=t.strftime("%Y-%m-%dT%H:%M:%SZ"), start_to=(nxt - dt.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")):
                seen[m["market_id"]] = m
            t = nxt
        return sorted(seen.values(), key=lambda m: m.get("start") or "")
    @locked
    def event_markets(self, event_id: str) -> list[dict]:
        hit = self._event_cache.get(event_id)
        if hit and time.time() - hit[0] < 30:
            return hit[1]
        res = self.feed.event_markets(event_id)
        for m in res:
            self._info[m["market_id"]] = m
        self._event_cache[event_id] = (time.time(), res)
        return res

    @locked
    def info(self, ids: list[str]) -> dict[str, dict]:
        missing = [i for i in ids if i not in self._info]
        if missing:
            self._info.update(self.feed.market_info(missing))
        return {i: self._info[i] for i in ids if i in self._info}

    # ---- state ----------------------------------------------------------
    def positions(self, sources: str = "all") -> dict[str, dict[str, Position]]:
        """Open positions (settled markets are in the ledger instead). sources='automated' leaves out manual orders."""
        pos: dict[str, dict[str, Position]] = defaultdict(lambda: defaultdict(Position))
        done = {e["market_id"] for e in self.ledger.entries}
        for f in self.ex.fills():
            r = self.ex.get_order(f.order_id).request
            if r.market_id in done or (sources == "automated" and r.source == "manual"):
                continue
            pos[r.market_id][r.selection_id] = pnl.apply_fill(pos[r.market_id][r.selection_id], r.side, f.price, f.size)
        return pos

    @locked
    def state(self, ids: list[str], short_s: int | None = None, long_s: int | None = None) -> dict:
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
                "start": mi.get("start"), "in_play": b.in_play, "status": b.status, "runners": mi.get("runners", {}),
                "selections": {sid: {"backs": [[l.price, l.size] for l in s.backs], "lays": [[l.price, l.size] for l in s.lays],
                                     "traded": sorted([p, v] for p, v in s.traded.items()), "last": s.last_traded, "status": s.status,
                                     "recent": self.tracker.recent(b.market_id, sid, s.traded, now, short_s, long_s)}
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
        self._process_entries()
        self._check_triggers()
        self._check_market_triggers()
        self._check_fok()
        orders = [self._order(o) for o in self.ex.open_orders() if o.status in OPEN and o.request.market_id in ids]
        allpos = [p for m in pos.values() for p in m.values()]
        exposure = round(sum(-min(p.win, p.lose, 0) for p in allpos), 2)
        return {"mode": self.mode, "t": time.time(), "markets": markets, "orders": orders,
                "totals": {"exposure": exposure, "open_pnl": round(sum(p.win if p.win < 0 else 0 for p in allpos), 2)},
                "warnings": self.service.warnings[-3:],
                "triggers": [{k: v for k, v in t.__dict__.items() if k not in ("cancel",)} for t in self.triggers.values() if t.market_id in ids],
                "market_triggers": [t.__dict__ for t in self.mtriggers.values() if t.market_id in ids],
                "matched_bets": self.matched_bets(ids),
                "events": self.events[-5:]}

    @locked
    def matched_bets(self, ids: list[str], n: int = 200) -> list[dict]:
        """Every bet with something matched on it (newest first), with what each would win or lose on its own."""
        out = []
        for o in self.ex.all_orders():
            r = o.request
            if r.market_id not in ids or o.matched <= 0:
                continue
            back = r.side.value == "BACK"
            win = o.matched * (o.avg_price - 1) * (1 if back else -1)
            lose = -o.matched if back else o.matched
            out.append({"order_id": o.order_id, "market_id": r.market_id, "selection_id": r.selection_id, "side": r.side.value,
                        "price": o.avg_price, "asked": r.price, "size": o.matched, "source": r.source, "t": o.last_fill_at or o.placed_at,
                        "if_wins": round(win, 2), "if_loses": round(lose, 2)})
        out.sort(key=lambda x: -x["t"])
        return out[:n]

    @locked
    def activity(self, n: int = 100) -> list[dict]:
        return self.log[-n:]

    @locked
    def busy(self) -> dict:
        """What a restart would interrupt: stops, entries, auto-greens and unmatched orders. All of it is saved to disk and restored, so this is a caution, not a loss."""
        return {"triggers": len(self.triggers) + len(self.mtriggers) + len(self.entries), "open_orders": len([o for o in self.ex.open_orders() if o.status in OPEN])}

    @locked
    def history(self, market_id: str, selection_id: str, seconds: int = 900) -> dict:
        return self.tracker.chart(market_id, selection_id, seconds)

    @staticmethod
    def _order(o: Order) -> dict:
        r = o.request
        return {"order_id": o.order_id, "market_id": r.market_id, "selection_id": r.selection_id, "side": r.side.value,
                "price": r.price, "size": r.size, "matched": o.matched, "avg_price": o.avg_price,
                "remaining": o.remaining, "status": o.status.value, "source": r.source,
                "persistence": r.persistence.value, "placed_at": o.placed_at}

    # ---- settings, results and limits ------------------------------------
    def _apply_settings(self) -> None:
        st = self.settings
        self.guard.limits = Limits(max_stake=0.0, max_open_exposure=st.max_open_liability,
                                   daily_loss_limit=st.daily_loss_limit, weekly_loss_limit=st.weekly_loss_limit)
        self.guard.kill_switch = not st.automation_enabled

    def _worst_case(self, pos: dict[str, dict[str, Position]]) -> float:
        """Most that could be lost across the given positions: per market, the worst outcome (including 'a runner I have no bet on wins')."""
        total = 0.0
        for mid, m in pos.items():
            held = dict(m)
            out = list(pnl.market_outcomes(held).values())
            if len(held) < len(self._info.get(mid, {}).get("runners", {}) or [0] * (len(held) + 1)):
                out.append(round(sum(p.lose for p in held.values()), 2))
            if out:
                total += max(0.0, -min(out))
        return round(total, 2)

    def _open_liability(self, include_manual: bool) -> float:
        total = self._worst_case(self.positions("all" if include_manual else "automated"))
        for o in self.ex.open_orders():
            if o.status in OPEN and (include_manual or o.request.source != "manual"):
                r = o.request
                total += o.remaining if r.side is Side.BACK else o.remaining * (r.price - 1)
        return round(total, 2)

    def _refresh_guard(self) -> None:
        """Feed the safety rules the figures they judge by. Cheap and needs no network, so it runs before every order."""
        now = time.time()
        per = self.ledger.periods(now)
        self.guard.realised_today = round(per["today"] + self._mtm, 2)
        self.guard.realised_week = round(per["week"] + self._mtm, 2)
        self.guard.open_exposure = self._open_liability(self.settings.include_manual_in_liability)
        lim = self.guard.limits
        hit = (lim.daily_loss_limit > 0 and -self.guard.realised_today >= lim.daily_loss_limit) or (lim.weekly_loss_limit > 0 and -self.guard.realised_week >= lim.weekly_loss_limit)
        if hit:
            self.alerts.add("warning", "Loss limit reached. Scripts and the AI cannot place orders until it clears; manual trading is not blocked.", "Automation blocked", True, key="losslimit")
        else:
            self.alerts.resolve("losslimit", "Back under the limit")

    def _watch_status(self, b, now: float) -> None:
        """Note when a market you hold or plan stays suspended for a while, and say how long once it reopens."""
        started = self._susp.get(b.market_id)
        if b.status == "SUSPENDED" and started is None:
            self._susp[b.market_id] = now
        elif b.status == "OPEN" and started is not None:
            del self._susp[b.market_id]
            if now - started >= 20:
                ev = self._info.get(b.market_id, {}).get("event", b.market_id)
                self.alerts.add("suspension", f"{ev} was suspended for about {int(now - started)}s", "Orders held, resumed on reopen", False, {"kind": "market", "id": b.market_id})

    def feed_health(self) -> dict:
        now = time.time()
        if self.mode == "demo":
            return {"ok": True, "detail": "Demo prices (not real)"}
        if self.feed_error and self.feed_error_at > self.feed_ok_at:
            return {"ok": False, "detail": f"Last request failed: {self.feed_error[:140]}"}
        if self.feed_ok_at and now - self.feed_ok_at > 600:
            return {"ok": False, "detail": f"No successful price request for {int((now - self.feed_ok_at) / 60)} min"}
        return {"ok": True, "detail": "Prices flowing (delayed key: about a minute behind)" if self.feed_ok_at else "Waiting for the first request"}

    @locked
    def settle_check(self) -> int:
        """Book the result of every market Betfair has settled, and re-mark the open positions. Returns how many markets were booked."""
        pos = self.positions()
        books = []
        mids = list(pos)
        for i in range(0, len(mids), 40):
            books += self.feed.get_books(mids[i:i + 40], depth=False)
        now, booked, mtm = time.time(), 0, 0.0
        for b in books:
            self._watch_status(b, now)
            held = pos.get(b.market_id, {})
            full = {sid: held.get(sid, Position()) for sid in set(b.selections) | set(held)}
            out = pnl.market_outcomes(full)
            winners = [sid for sid, s in b.selections.items() if s.status == "WINNER"]
            if b.status == "CLOSED" and winners:
                ev = self._info.get(b.market_id, {}).get("event", "") or b.market_id
                if self.ledger.add(b.market_id, ev, now, out.get(winners[0], 0.0), winners[0], self._staked(b.market_id), self._parts(b.market_id, winners[0], b.selections)):
                    booked += 1
                    self._log(f"Settled {ev}: {out.get(winners[0], 0.0):+.2f}", "info")
                    self._check_cleared(b.market_id, ev, out.get(winners[0], 0.0))
                    self.alerts.add("trade", f"Settled {ev}: {out.get(winners[0], 0.0):+.2f}", "Result booked to today's P&L", False, {"kind": "market", "id": b.market_id})
            elif b.status != "CLOSED":
                held_m = out and any(abs(p.win) > 0.004 or abs(p.lose) > 0.004 for p in full.values())
                plan = pnl.green_plan(out, {k: (v.backs[0].price if v.backs else None) for k, v in b.selections.items()},
                                      {k: (v.lays[0].price if v.lays else None) for k, v in b.selections.items()}) if out else None
                mv = plan["locked"] if plan else (min(out.values()) if out else 0.0)
                mtm += mv
                self._mtm_m[b.market_id] = {"pnl": round(mv, 2), "exposure": round(max(0.0, -min(out.values())), 2) if out else 0.0}
        for mid in list(self._mtm_m):
            if mid not in pos:
                del self._mtm_m[mid]
        self._mtm = round(mtm, 2)
        self._refresh_guard()
        return booked

    @locked
    def update_locked(self, fn):
        """Run a change to scripts or the plan under the engine lock so it is saved with everything else."""
        return fn()

    @staticmethod
    def _label(source: str) -> str:
        return "Manual trades" if source == "manual" else ("AI ideas" if source == "ai" else source.split(":", 1)[1].removesuffix(":exit"))

    def _parts(self, market_id: str, winner: str, selections) -> dict:
        """The market's result split by who placed the bets: each script, AI ideas, manual trades."""
        by: dict[str, dict[str, Position]] = defaultdict(lambda: defaultdict(Position))
        for f in self.ex.fills():
            r = self.ex.get_order(f.order_id).request
            if r.market_id == market_id:
                by[self._label(r.source)][r.selection_id] = pnl.apply_fill(by[self._label(r.source)][r.selection_id], r.side, f.price, f.size)
        out = {}
        for label, held in by.items():
            full = {sid: held.get(sid, Position()) for sid in set(selections) | set(held)}
            out[label] = pnl.market_outcomes(full).get(winner, 0.0)
        return out

    def _staked(self, market_id: str) -> float:
        """Money put at risk on a market: back stakes plus lay liabilities, over everything matched."""
        tot = 0.0
        for f in self.ex.fills():
            r = self.ex.get_order(f.order_id).request
            if r.market_id == market_id:
                tot += f.size if r.side is Side.BACK else f.size * (r.price - 1)
        return tot

    @locked
    def home(self) -> dict:
        """Everything the Home screen shows, in one call."""
        self._refresh_guard()
        now = time.time()
        per = self.ledger.periods(now)
        rec = self.recs.stats()
        running = [r for r in self.plan.rows.values() if r["state"] in ("armed", "running") and r["script_id"] and self.scripts.scripts.get(r["script_id"], {}).get("enabled")]
        pos = self.positions()
        vol: dict[str, float] = defaultdict(float)
        for f in self.ex.fills():
            vol[self.ex.get_order(f.order_id).request.market_id] += f.size
        overview, seen = [], set()
        for r in self.plan.rows.values():
            v = self._row_view(r)
            m = self._mtm_m.get(r["market_id"], {})
            seen.add(r["market_id"])
            overview.append({"market_id": r["market_id"], "event": r["event"], "market": r["market_name"], "strategy": v["strategy"], "rules": v["trigger"], "by": r["added_by"],
                             "state": r["state"], "pnl": m.get("pnl"), "exposure": m.get("exposure"), "matched": round(vol.get(r["market_id"], 0.0), 2), "start": v["start"]})
        for mid in pos:
            if mid not in seen:
                info = self._info.get(mid, {})
                m = self._mtm_m.get(mid, {})
                overview.append({"market_id": mid, "event": info.get("event", mid), "market": info.get("name", ""), "strategy": "Manual", "rules": "", "by": "you", "state": "open",
                                 "pnl": m.get("pnl"), "exposure": m.get("exposure"), "matched": round(vol.get(mid, 0.0), 2), "start": info.get("start")})
        open_orders = [self._order(o) | {"event": self._info.get(o.request.market_id, {}).get("event", ""), "runner": self._name(o.request.market_id, o.request.selection_id)}
                       for o in self.ex.open_orders() if o.status in OPEN]
        return {"today": round(per["today"] + self._mtm, 2), "exposure": self._open_liability(True), "automation": self.settings.automation_enabled,
                "kpis": {"month": per["month"], "roi": per["month_roi"], "last7": per["last7"], "win_rate": per["month_win_rate"], "markets": per["month_markets"],
                         "clv": rec["avg_clv_pts"], "scripts_running": len(running), "recs_pending": rec["pending"]},
                "overview": sorted(overview, key=lambda x: x["start"] or "~"), "open_orders": open_orders[:20],
                "recs": self.recs.list("all", "pending")[:4], "alerts": self.alerts.list("all")[:6]}

    @locked
    def pnl_summary(self) -> dict:
        self._refresh_guard()
        per = self.ledger.periods(time.time())
        return {"today": round(per["today"] + self._mtm, 2), "week": round(per["week"] + self._mtm, 2), "month": round(per["month"] + self._mtm, 2),
                "settled_today": per["today"], "open_pnl": self._mtm, "month_markets": per["month_markets"], "month_win_rate": per["month_win_rate"],
                "exposure": self._open_liability(True), "automation": self.settings.automation_enabled, "mode": self.mode,
                "limits": {"daily": self.settings.daily_loss_limit, "weekly": self.settings.weekly_loss_limit,
                           "liability": self.settings.max_open_liability}}

    @locked
    def update_settings(self, patch: dict) -> dict:
        was = self.settings.automation_enabled
        self.settings.update(patch)
        self._apply_settings()
        if was != self.settings.automation_enabled:
            self._log("Automation switched " + ("on" if self.settings.automation_enabled else "off"), "info")
        return self.settings.to_dict()

    @locked
    def stop_automation(self) -> dict:
        """Stop all automation: cancel every unmatched order placed by scripts or the AI, switch automation off. Open positions stay open and
        manual trading is untouched."""
        self.settings.automation_enabled = False
        self._apply_settings()
        n = 0
        for o in self.ex.open_orders():
            if o.status in OPEN and o.request.source != "manual":
                self.ex.cancel_order(o.order_id); self.fok.pop(o.order_id, None)
                self.entries.pop(o.order_id, None); n += 1
        self.alerts.add("warning", f"Automation stopped. {n} unmatched automated order{'s' if n != 1 else ''} cancelled.", "Scripts paused; open positions untouched", False)
        self._log(f"STOP ALL AUTOMATION: cancelled {n} unmatched automated order{'s' if n != 1 else ''}; scripts and the AI can no longer place orders", "warn")
        return {"cancelled": n, "automation": False}

    # ---- scripts and the plan ---------------------------------------------
    @staticmethod
    def _uk_clock() -> str:
        import datetime as dt
        from ..ledger import UK
        return dt.datetime.now(UK).strftime("%H:%M")

    def _cancel_source(self, market_id: str, source: str) -> int:
        n = 0
        for o in self.ex.open_orders():
            if o.status in OPEN and o.request.market_id == market_id and o.request.source == source:
                self.ex.cancel_order(o.order_id); self.fok.pop(o.order_id, None); n += 1
        return n

    def _script_view(self, row: dict, book) -> dict:
        sel = book.selections.get(row["selection_id"])
        held = {sid: p for sid, p in self.positions().get(row["market_id"], {}).items()}
        full = {sid: held.get(sid, Position()) for sid in book.selections}
        out = list(pnl.market_outcomes(full).values()) if held else [0.0]
        info = self.info([row["market_id"]]).get(row["market_id"], {})
        ctx = None
        if self.context_fn:
            try:
                ctx = self.context_fn({**info, "market_id": row["market_id"]})
            except Exception:       # noqa: BLE001
                ctx = None
        entry = None
        eo = row.get("entry_order")
        prices = {"last": sel.last_traded if sel else None, "back": sel.backs[0].price if sel and sel.backs else None,
                  "lay": sel.lays[0].price if sel and sel.lays else None}
        if eo:
            try:
                o = self.ex.get_order(eo)
                if o.matched > 0:
                    g = gain_ticks(o.request.side.value, o.avg_price, prices)
                    if g is not None:
                        row["peak"] = max(row.get("peak", 0), g)               # best the exit price has been since we were matched (for trailing stops)
                    entry = {"side": o.request.side.value, "price": o.avg_price, "peak": row.get("peak", 0)}
            except Exception:       # noqa: BLE001
                entry = None
        now = time.time()
        key = (row["market_id"], row["selection_id"])
        hist = self._pxhist.setdefault(key, [])
        px = prices["back"] or prices["last"]
        if px and (not hist or now - hist[-1][0] >= 1.0):
            hist.append((now, px))
        while hist and now - hist[0][0] > 900:
            hist.pop(0)
        start = info.get("start")
        try:
            mins = (dt.datetime.fromisoformat(str(start).replace("Z", "+00:00")).timestamp() - now) / 60 if start else None
        except ValueError:
            mins = None
        pidx = None
        if ctx and ctx.get("kind") == "tennis" and ctx.get("players"):
            from .ai.snapshot import same_name
            nm = info.get("runners", {}).get(row["selection_id"], "")
            pidx = next((i for i, pl in enumerate(ctx["players"]) if same_name(pl, nm)), None)
        return {"ref_price": row.get("ref_price"), "player_idx": pidx, "entry": entry, "mins_to_start": mins, "matched": info.get("matched"), "history": list(hist), "now": now, "prices": prices,
                "in_play": book.in_play, "ctx": ctx, "position_loss": max(0.0, -min(out)), "clock": self._uk_clock()}

    def _fire(self, row: dict, rule: dict, act: dict, script: dict, book) -> None:
        mid, sid, t = row["market_id"], row["selection_id"], act["type"]
        src = f"script:{script['name']}" + (":exit" if rule["kind"] != "entry" else "")
        if t in ("back", "lay"):
            sel = book.selections[sid]
            side = t.upper()
            price = act["price"]
            if price == "best":
                lv = sel.backs if side == "BACK" else sel.lays
                if not lv:
                    raise ValueError("no price available to bet at")
                price = lv[0].price
            price = ticks.nearest(float(price))
            stake = float(row["stake"] or act["stake"])
            size = round(stake / (price - 1), 2) if (act["basis"] == "liability" and side == "LAY") else round(stake, 2)
            r = self.place(mid, sid, side, price, size, act["persistence"], source=src)
            row["orders"].append(r["order"]["order_id"])
            row["entry_order"] = r["order"]["order_id"]
            row["state"] = "running"
        elif t in ("green", "close"):
            self._cancel_source(mid, f"script:{script['name']}")
            part = act.get("percent")
            res = self.green_market(mid, hard=(t == "close" and not part), pct=(part / 100 if part else 1.0), source=src)
            if not res.get("greened") and "nothing to green" not in res.get("reason", ""):
                raise RuntimeError(res.get("reason", "could not close"))
            if not part and not (rule["kind"] == "safety" and any(a["type"] == "stop" for a in rule["then"])):          # a safety rule's close is followed by its stop, which ends the script as Stopped
                row["state"] = "done"
        elif t == "stop":
            self._cancel_source(mid, f"script:{script['name']}")
            row["state"] = "stopped"

    @locked
    def _check_cleared(self, market_id: str, event: str, ours: float) -> None:
        """Live only: compare our computed result (before commission) with what Betfair actually cleared. A gap means a fill was missed or mis-priced."""
        if not self.live:
            return
        try:
            c = self.feed.cleared_orders(market_id)
        except Exception:        # noqa: BLE001
            return
        if c["bets"] and abs((c["profit"] + c["commission"]) - ours) > 0.10:
            self.alerts.add("warning", f"Result differs from Betfair for {event}",
                            f"AutoBets computed {ours:+.2f} before commission; Betfair cleared {c['profit'] + c['commission']:+.2f}. Check the bets for this market.", False, {"kind": "market", "id": market_id})

    def live_status(self) -> dict:
        """Live trading state for Settings and the header: armed or not, whether Betfair order sync is healthy, funds."""
        if not self.live:
            return {"live": False}
        out = {"live": True, "armed": self.ex.armed, "sync_error": self.ex.sync_error, "sync_ok_at": self.ex.sync_ok_at, "funds": None}
        if time.time() - getattr(self, "_funds_at", 0) > 60:
            try:
                self._funds, self._funds_at = self.feed.account_funds(), time.time()
            except Exception:        # noqa: BLE001
                self._funds, self._funds_at = None, time.time()
        out["funds"] = getattr(self, "_funds", None)
        return out

    @locked
    def live_arm(self, confirm: str) -> dict:
        if not self.live:
            raise ValueError("not in live mode")
        self.ex.arm(confirm)
        self._log("LIVE TRADING ARMED: new orders are real Betfair orders", "warn")
        self.alerts.add("warning", "Live trading armed", "Real orders can now be placed", False)
        return self.live_status()

    @locked
    def live_disarm(self) -> dict:
        if not self.live:
            raise ValueError("not in live mode")
        self.ex.disarm()
        self._log("Live trading disarmed: no new orders will be sent (cancels still work)", "warn")
        return self.live_status()

    def live_reconcile(self) -> dict:
        """Start-up: compare the saved orders with what Betfair holds and say what differed."""
        r = self.ex.reconcile()
        if not r["ok"]:
            self.alerts.add("warning", "Could not check your Betfair orders at start-up", r["error"][:160], False)
        elif r["adopted"] or r["closed"]:
            self.alerts.add("warning", f"Start-up check: {len(r['adopted'])} Betfair order(s) were not in AutoBets and are now shown; {len(r['closed'])} saved order(s) no longer exist on Betfair",
                            "Review Manual > open orders", False)
        self._log(f"Start-up check against Betfair: {r}", "info")
        return r

    def run_scripts(self) -> int:
        """One pass of the script runner: evaluate every live plan row against current prices and score, and act on rules that fire."""
        if not self.settings.automation_enabled:
            return 0
        rows = [r for r in self.plan.active() if r["script_id"] in self.scripts.scripts and self.scripts.get(r["script_id"])["enabled"]]
        if not rows:
            return 0
        acted = 0
        books = {}
        mids = sorted({r["market_id"] for r in rows})
        for i in range(0, len(mids), 40):
            for b in self.feed.get_books(mids[i:i + 40], depth=False):
                books[b.market_id] = b
        for row in rows:
            book = books.get(row["market_id"])
            if book is None or book.status != "OPEN":
                continue
            self.ex.refresh([book])
            script = self.scripts.current(row["script_id"])
            if row.get("await_flat"):
                if self._rearm(row, script, book):
                    acted += 1
                continue
            if self._stale_entry(row, script):
                continue
            fired = set(row["fired"])
            for rule, act in evaluate(script, self._script_view(row, book), fired):
                ok = True
                try:
                    self._fire(row, rule, act, script, book)
                    acted += 1
                    self.alerts.add("trade", f"{script['name']}: {rule['kind']} rule {rule['id']} acted ({act['type']}) on {row['runner']} · {row['event']}", "Script action", False, {"kind": "plan", "id": row["id"]})
                except Exception as ex:        # noqa: BLE001
                    ok = False
                    row["note"] = f"{rule['id']}: {ex}"
                    self._log(f"Script '{script['name']}' on {row['event']}: {rule['id']} could not act: {ex}", "warn")
                    self.alerts.add("warning", f"Script '{script['name']}' could not act on {row['event']}: {ex}", "Script " + ("stopped" if rule["kind"] == "entry" else "will retry"), False, {"kind": "plan", "id": row["id"]})
                    if rule["kind"] == "entry":
                        row["state"] = "stopped"
                if (ok or rule["kind"] == "entry") and rule["id"] not in row["fired"]:
                    row["fired"].append(rule["id"])      # entries are never retried; exits are retried on the next pass
                if ok and rule["kind"] == "exit" and act["type"] in ("green", "close") and row["state"] == "done":
                    entry_rule = next((r for r in script["rules"] if r["kind"] == "entry"), {})
                    row["cycle"] = row.get("cycle", 1)
                    if row["cycle"] < entry_rule.get("repeat", 1):
                        row["state"], row["await_flat"] = "running", True       # wait for the green-up to level the position, then go again
                if row["state"] in ("done", "stopped") or not ok or row.get("await_flat"):
                    break
        return acted

    def plan_why(self, rid: str) -> dict:
        """Why has this row (not) fired? Each rule's conditions with whether they are met right now, plus the live readings the conditions look at."""
        row = self.plan.rows.get(rid)
        if not row:
            raise KeyError(rid)
        if not row.get("script_id") or row["script_id"] not in self.scripts.scripts:
            return {"ok": False, "reason": "This row has no script."}
        script = self.scripts.current(row["script_id"])
        out = {"ok": True, "state": row["state"], "cycle": row.get("cycle", 1), "note": row.get("note", ""), "automation": self.settings.automation_enabled,
               "script_enabled": bool(self.scripts.get(row["script_id"])["enabled"]), "rules": [], "readings": {}}
        book = next(iter(self.feed.get_books([row["market_id"]], depth=False)), None)
        if book is None:
            out["reason"] = "No prices for this market right now."
            return out
        self.ex.refresh([book])
        view = self._script_view(row, book)
        pr, ctx = view["prices"], view.get("ctx") or {}
        sp = ticks.ticks_between(ticks.nearest(pr["back"]), ticks.nearest(pr["lay"])) if pr.get("back") and pr.get("lay") else None
        out["readings"] = {"Market status": book.status, "In-play": bool(view.get("in_play")), "Best back": pr["back"], "Best lay": pr["lay"], "Spread (ticks)": sp,
                           "Live score feed": bool(ctx), "Minute": ctx.get("elapsed"), "Goals": sum(ctx["goals"]) if ctx.get("goals") else None, "Entry matched": bool(view.get("entry"))}
        fired = set(row["fired"])
        for r in script["rules"]:
            out["rules"].append({"id": r["id"], "kind": r["kind"], "done": r["id"] in fired,
                                 "conditions": [{"text": describe_cond(c), "met": bool(check(c, view, fired))} for c in r["when"]]})
        return out

    STALE_ENTRY_S = 45

    def _stale_entry(self, row: dict, script: dict) -> bool:
        """A script's entry bet that nobody has matched for a while is cancelled and the same run re-armed. Without this a scalp whose first bet was left behind by the price would sit 'running' forever: its exits need a matched entry, so nothing would ever fire or repeat."""
        eo = row.get("entry_order")
        if row.get("state") != "running" or not eo or row.get("await_flat"):
            return False
        try:
            o = self.ex.get_order(eo)
        except Exception:       # noqa: BLE001
            return False
        if o.matched > 0 or o.status not in OPEN or time.time() - o.placed_at < self.STALE_ENTRY_S:
            return False
        self.ex.cancel_order(eo)
        self.fok.pop(eo, None)
        row.update({"fired": [], "state": "armed", "entry_order": None, "note": ""})
        self._log(f"Script '{script['name']}' on {row['event']}: entry bet unmatched for {self.STALE_ENTRY_S}s, cancelled; run {row.get('cycle', 1)} re-armed", "info")
        self.alerts.add("info", f"{script['name']}: entry bet on {row['runner']} was not matched within {self.STALE_ENTRY_S}s, so it was cancelled and the script is trying again", "Script retry", False, {"kind": "plan", "id": row["id"]})
        return True

    def _rearm(self, row: dict, script: dict, book) -> bool:
        """After an exit has greened, start the next cycle once the position is level and nothing of this script is still waiting."""
        mid = row["market_id"]
        waiting = any(o.status in OPEN and o.request.market_id == mid and o.request.source.startswith(f"script:{script['name']}") for o in self.ex.open_orders())
        held = self.positions().get(mid, {})
        full = {sid: held.get(sid, Position()) for sid in book.selections}
        out = list(pnl.market_outcomes(full).values()) if held else [0.0]
        if waiting or (max(out) - min(out)) > 0.10:
            row["note"] = "Waiting for the green-up to match before the next run"
            return False
        row.update({"fired": [], "await_flat": False, "state": "armed", "note": "", "cycle": row.get("cycle", 1) + 1, "entry_order": None, "peak": 0})
        self._log(f"Script '{script['name']}' on {row['event']}: run {row['cycle']} of {next((r for r in script['rules'] if r['kind'] == 'entry'), {}).get('repeat', 1)} armed", "info")
        return True

    @locked
    def plan_add(self, market_id: str, selection_id: str | None, script_id: str | None, stake: float | None = None, added_by: str = "you") -> dict:
        info = self.info([market_id]).get(market_id)
        if not info:
            raise ValueError("unknown market")
        if script_id:
            self.scripts.get(script_id)
            if not selection_id:
                raise ValueError("pick the runner this script acts on")
        runner = info.get("runners", {}).get(selection_id or "", "")
        if script_id and not runner:
            raise ValueError("that runner is not in this market")
        if stake is not None and stake < 1:
            raise ValueError("minimum stake is £1")
        import datetime as dt
        from ..ledger import UK
        return self._row_view(self.plan.add(market_id, selection_id or "", script_id, info.get("event", ""), info.get("name", ""), runner, added_by, stake,
                                            dt.datetime.now(UK).strftime("%Y-%m-%d")))

    def _row_view(self, r: dict) -> dict:
        sc = self.scripts.scripts.get(r["script_id"]) if r["script_id"] else None
        cur = sc["versions"][-1] if sc else None
        stake, liab, trig = r["stake"], None, ""
        if cur:
            entry = next((x for x in cur["rules"] if x["kind"] == "entry"), None)
            act = entry["then"][0] if entry else None
            if act:
                stake = r["stake"] or act["stake"]
                if act["type"] == "back":
                    liab = stake
                elif act["price"] != "best":
                    liab = round(stake * (act["price"] - 1), 2) if act["basis"] == "stake" else stake
            trig = "; ".join(next(d for d in describe(cur) if d["id"] == entry["id"])["if"]) if entry else ""
        info = self._info.get(r["market_id"], {})
        rep = next((x.get("repeat", 1) for x in (cur["rules"] if cur else []) if x["kind"] == "entry"), 1)
        return {**r, "cycle": r.get("cycle", 1), "repeat": rep, "strategy": cur["name"] if cur else "None (watching)", "script_enabled": bool(sc and sc["enabled"]), "stake": stake, "max_liability": liab,
                "trigger": trig, "headline": headline(cur) if cur else "", "text": describe(cur) if cur else [], "origin": sc["origin"] if sc else "", "start": info.get("start"), "sport": cur["sport"] if cur else ""}

    @locked
    def plan_view(self) -> dict:
        rows = [self._row_view(r) for r in self.plan.rows.values()]
        live = [r for r in rows if r["state"] in ("armed", "running")]
        return {"rows": sorted(rows, key=lambda r: (r["start"] or "", r["id"])),
                "summary": {"markets": len({r["market_id"] for r in rows}), "you": sum(1 for r in rows if r["added_by"] == "you"), "ai": sum(1 for r in rows if r["added_by"] == "ai"),
                            "stake": round(sum(r["stake"] or 0 for r in live), 2), "max_liability": round(sum(r["max_liability"] or 0 for r in live), 2),
                            "clashes": len(self.plan.clashes())},
                "clashes": [{"market_id": m, "rows": ids} for m, ids in self.plan.clashes()]}

    @locked
    def plan_edit(self, rid: str, stake: float | None, script_id: str | None = None) -> dict:
        row = self.plan.get(rid)
        if stake is not None:
            if stake < 1:
                raise ValueError("minimum stake is £1")
            row["stake"] = stake
        if script_id:
            self.scripts.get(script_id)
            row.update(script_id=script_id, state="armed", fired=[], note="")
        return self._row_view(row)

    @locked
    def plan_remove(self, rid: str) -> dict:
        row = self.plan.get(rid)
        if row["script_id"]:
            sc = self.scripts.scripts.get(row["script_id"])
            if sc:
                self._cancel_source(row["market_id"], f"script:{sc['versions'][-1]['name']}")
        self.plan.remove(rid)
        return {"removed": rid}

    @locked
    def plan_bets(self, statuses: list[str] | None = None) -> list[dict]:
        out = []
        for o in self.ex.all_orders():
            r = o.request
            info = self._info.get(r.market_id, {})
            row = self._order(o)
            row.update(event=info.get("event", ""), market=info.get("name", ""), runner=self._name(r.market_id, r.selection_id),
                       strategy=r.source.split(":", 1)[1].removesuffix(":exit") if r.source.startswith("script:") else ("AI" if r.source == "ai" else "Manual"),
                       placed_by="Script" if r.source.startswith("script:") else ("AI" if r.source == "ai" else "You"))
            if not statuses or o.status.value in statuses:
                out.append(row)
        return sorted(out, key=lambda x: -x["placed_at"])[:300]

    @locked
    def rec_apply(self, rid: str, price: float | None = None, stake: float | None = None) -> dict:
        """Place an accepted recommendation as an 'ai' order (guardrails apply), after checking the price has not run away from the idea."""
        r = self.recs.items.get(rid)
        if r is None:
            raise KeyError(rid)
        if r["status"] != "pending":
            raise ValueError(f"this recommendation is {r['status']}")
        if r["kind"] == "setup":
            return self._accept_setup(r, stake)
        if r["kind"] == "script":
            return self._accept_proposal(r)
        if r["kind"] != "trade":
            raise ValueError("this recommendation cannot be applied")
        book = self.feed.get_books([r["market_id"]], depth=False)[0]
        if book.status != "OPEN":
            raise ValueError(f"the market is {book.status.lower()}")
        sel = book.selections.get(r["selection_id"])
        lv = (sel.backs if r["side"] == "BACK" else sel.lays) if sel else []
        if not lv:
            raise ValueError("no price available right now")
        cur = lv[0].price
        use = ticks.nearest(price) if price else cur
        drift = ticks.ticks_between(r["price"], cur) if r["side"] == "BACK" else ticks.ticks_between(cur, r["price"])
        if not price and drift < -3:
            raise ValueError(f"the price has moved from {r['price']} to {cur}; refresh and look again")
        size = float(stake or r["stake"])
        res = self.place(r["market_id"], r["selection_id"], r["side"], use, size, "KEEP", 0, 0, 0, source="ai")
        r.update(status="applied", applied_at=time.time(), order_id=res["order"]["order_id"], stake=size, price=use)
        self.alerts.resolve_ref("rec", rid, "Applied")
        try:
            self.plan.add(r["market_id"], r["selection_id"], None, r["event"], r["market_name"], r["runner"], "ai", size)
        except ValueError:
            pass
        return {"rec": r, "order": res["order"], "warnings": res["warnings"]}

    def _accept_proposal(self, r: dict) -> dict:
        """Approving an AI script proposal saves it to the library, switched OFF. Putting it to work (Plan) stays your decision."""
        body = {**r["script"]}
        names = {s["versions"][-1]["name"] for s in self.scripts.scripts.values()}
        base, n = body["name"], 1
        while body["name"] in names:
            n += 1
            body["name"] = f"{base} #{n}"
        view = self.scripts.create(body, "ai", f"AI proposal {r['id']}")
        r.update(status="applied", applied_at=time.time(), script_id=view["id"])
        self._save()
        return {"rec": r, "script": view, "row": None, "order": None, "warnings": []}

    def _accept_setup(self, r: dict, stake: float | None) -> dict:
        """Accepting a trade setup saves its script to the library (switched on) and puts the market on the Plan with it. No bet is placed now:
        the script places bets itself, in play, when its conditions are met."""
        body = {**r["script"]}
        if stake and stake < 1:
            raise ValueError("minimum stake is £1")
        # One reusable script per kind of setup, shared by every match: reuse it if the library already has it, create it only the first time.
        have = next((sid for sid, sc in self.scripts.scripts.items() if sc["versions"][-1]["name"] == body["name"]), None)
        if have:
            view = self.scripts.set_enabled(have, True)
        else:
            view = self.scripts.create(body, "ai", f"from recommendation {r['id']}")
            view = self.scripts.set_enabled(view["id"], True)
        row = self.plan_add(r["market_id"], r["selection_id"], view["id"], float(stake or r["stake"]), "ai")
        self.plan.rows[row["id"]]["ref_price"] = r.get("price")
        r.update(status="applied", applied_at=time.time(), script_id=view["id"], plan_row=row["id"], stake=float(stake or r["stake"]))
        self.alerts.resolve_ref("rec", r["id"], "Added to the Plan")
        self._save()
        return {"rec": r, "script": view, "row": row, "order": None, "warnings": []}

    @locked
    def rec_dismiss(self, rid: str, reason: str = "") -> dict:
        r = self.recs.items.get(rid)
        if r is None:
            raise KeyError(rid)
        if r["status"] == "pending":
            r.update(status="dismissed", dismiss_reason=reason[:200])
            self.alerts.resolve_ref("rec", rid, "Dismissed")
        return r

    def script_library(self) -> list[dict]:
        from ..scripts import headline
        return [{"name": v["name"], "sport": v.get("sport", "any"), "headline": headline(v)} for v in (s["versions"][-1] for s in self.scripts.scripts.values())]

    def setup_results(self) -> list[str]:
        out: dict[str, list] = {}
        for r in self.recs.items.values():
            if r["kind"] == "setup" and r["status"] == "applied":
                out.setdefault(r["template"], []).append(r.get("result"))
        return [f"{t}: {len(v)} accepted, {sum(1 for x in v if x is not None)} settled, net £{sum(x for x in v if x is not None):.2f}" for t, v in out.items()]

    def add_proposals(self, ideas: list[dict]) -> int:
        with self.lock:
            made = [r for r in (self.recs.add_proposal(i) for i in ideas) if r]
            for r in made:
                self.alerts.add("recommendation", f"New script proposal: {r['title']}", "Waiting for your decision", True, {"kind": "rec", "id": r["id"]})
            self._save()
        return len(made)

    def rec_scan(self) -> int:
        """Look for ideas. The slow part (price requests) runs without holding the trading lock; only the bookkeeping takes it."""
        stake = min(10.0, self.settings.ai_max_stake)
        created = self.recs.scan(self, stake)
        self.recs.measure_clv(self)
        with self.lock:
            booked = {e["market_id"]: e["result"] for e in self.ledger.entries}
            for r in self.recs.items.values():                           # how did each accepted setup turn out, once its market settled
                if r["kind"] == "setup" and r["status"] == "applied" and r.get("result") is None and r["market_id"] in booked:
                    r["result"] = booked[r["market_id"]]
            for r in created:
                self.alerts.add("recommendation", f"New trade setup: {r['title']}", "Waiting for your decision", True, {"kind": "rec", "id": r["id"]})
            self._save()
        return len(created)

    # ---- actions --------------------------------------------------------
    @locked
    def place(self, market_id: str, selection_id: str, side: str, price: float, size: float, persistence: str = "KEEP", fok_s: float = 0, offset: int = 0, stop: int = 0, source: str = "manual") -> dict:
        if not ticks.is_valid(price):
            raise ValueError(f"{price} is not a valid Betfair price")
        if size < 1.0:
            raise ValueError("minimum stake is £1")
        self.service.warnings.clear()
        self._refresh_guard()
        self.ex.refresh(self.feed.get_books([market_id], depth=True))       # match against the freshest prices
        self._require_open(market_id, selection_id)
        req = OrderRequest(market_id, selection_id, Side(side), price, size, persistence=Persistence(persistence), source=source)
        try:
            order = self.service.place(req)
        except Blocked as e:
            raise ValueError(str(e))
        if order is None:
            raise RuntimeError("order outcome unknown; it will be reconciled")
        if fok_s and order.status in OPEN:
            self.fok[order.order_id] = time.time() + fok_s
        if (offset or stop) and order.status in OPEN + (Status.MATCHED,):
            self.entries[order.order_id] = Entry(order.order_id, market_id, selection_id, side, int(offset), int(stop), persistence)
            self._process_entries()
        self._log(f"{side} £{size:.2f} @ {price:.2f} on {self._name(market_id, selection_id)}: {order.status.value.lower()}"
                  + (f" (£{order.matched:.2f} matched)" if order.matched and order.status is not Status.MATCHED else ""), "order")
        return {"order": self._order(order), "warnings": list(self.service.warnings)}

    def _name(self, market_id: str, selection_id: str) -> str:
        return self._info.get(market_id, {}).get("runners", {}).get(selection_id, selection_id)

    def _require_open(self, market_id: str, selection_id: str | None = None) -> None:
        """Betfair refuses orders on a suspended or closed market and on a removed runner; say so before sending anything."""
        book = self.ex.get_book(market_id)
        if book.status != "OPEN":
            raise ValueError(f"the market is {book.status.lower()} - orders cannot be placed or hedged right now")
        sel = book.selections.get(selection_id) if selection_id else None
        if sel is not None and sel.status != "ACTIVE":
            raise ValueError(f"{self._name(market_id, selection_id)} is {sel.status.lower()} in this market")

    @locked
    def edit_order(self, order_id: str, price: float | None = None, size: float | None = None) -> dict:
        """Change an unmatched order's price and/or stake. The unmatched remainder is cancelled and re-placed (as Betfair's own
        'replace' does), keeping its at-the-off setting. Anything already matched is untouched."""
        o = self.ex.get_order(order_id)
        if o.status not in OPEN:
            raise ValueError("that order is no longer open")
        r = o.request
        new_price = r.price if price is None else price
        new_size = o.remaining if size is None else size
        if not ticks.is_valid(new_price):
            raise ValueError(f"{new_price} is not a valid Betfair price")
        if new_size < 1.0:
            raise ValueError("minimum stake is £1")
        self.ex.refresh(self.feed.get_books([r.market_id], depth=True))
        self._require_open(r.market_id, r.selection_id)
        self.ex.cancel_order(order_id)
        deadline = self.fok.pop(order_id, None)
        res = self.place(r.market_id, r.selection_id, r.side.value, new_price, new_size, r.persistence.value)
        if deadline:
            self.fok[res["order"]["order_id"]] = deadline
        self._log(f"Changed {r.side.value} order on {self._name(r.market_id, r.selection_id)} to £{new_size:.2f} @ {new_price:.2f}", "order")
        return res

    @locked
    def set_persistence(self, persistence: str, market_ids: list[str] | None = None, order_id: str | None = None) -> int:
        """What happens to unmatched bets when the match goes in play: KEEP, CANCEL (lapse) or TAKE_SP."""
        p = Persistence(persistence)
        n = 0
        for o in self.ex.open_orders():
            r = o.request
            if o.status in OPEN and (order_id in (None, o.order_id)) and (not market_ids or r.market_id in market_ids):
                self.ex.set_persistence(o.order_id, p); n += 1
        if n:
            self._log(f"At the off: {n} unmatched bet{'s' if n != 1 else ''} set to {persistence.replace('_', ' ').lower()}", "order")
        return n

    # ---- offset and stop on entry ------------------------------------------
    def _process_entries(self) -> None:
        for e in list(self.entries.values()):
            try:
                o = self.ex.get_order(e.order_id)
            except Exception:
                self.entries.pop(e.order_id, None); continue
            new = round(o.matched - e.processed, 2)
            if new >= 1.0 and o.avg_price:
                p = o.avg_price
                chunk = Position(win=round(new * (p - 1), 2), lose=-new) if e.side == "BACK" else Position(win=-round(new * (p - 1), 2), lose=new)
                try:
                    if e.offset:
                        target = ticks.nearest(p)
                        target = ticks.move(target, -e.offset if e.side == "BACK" else e.offset)
                        h = pnl.hedge(chunk, target)
                        if h and h[1] >= 1.0:
                            res = self.place(e.market_id, e.selection_id, h[0].value, target, h[1], e.persistence)
                            e.close_ids.append(res["order"]["order_id"])
                            self._log(f"Offset: {h[0].value} £{h[1]:.2f} @ {target:.2f} placed to close the {e.side} @ {p:.2f} ({e.offset} ticks)", "order")
                    if e.stop and not e.stop_id:
                        sp = ticks.move(ticks.nearest(p), e.stop if e.side == "BACK" else -e.stop)
                        h = pnl.hedge(chunk, sp)
                        t = Trigger(f"T{next(self._trigger_ids)}", e.market_id, e.selection_id, sp, "ge" if e.side == "BACK" else "le",
                                    "stop loss", h[2] if h else 0.0, cancel=e.close_ids, link=e.order_id)
                        self.triggers[t.id] = t; e.stop_id = t.id
                        self._log(f"Stop armed at {sp:.2f} ({e.stop} ticks against the {e.side} @ {p:.2f})", "trigger")
                    e.processed = round(e.processed + new, 2)
                except ValueError:
                    continue                      # e.g. market suspended: try again next time
            done_entry = o.status not in OPEN
            if done_entry and e.processed + 0.9999 >= o.matched:
                closed = bool(e.close_ids) and all(self.ex.get_order(c).status is Status.MATCHED for c in e.close_ids)
                if closed or not e.close_ids:
                    if closed and e.stop_id:
                        self.triggers.pop(e.stop_id, None)          # the offset bet matched: the position is closed, the stop is not needed
                        self._log("Offset matched: position closed, stop removed", "order")
                    self.entries.pop(e.order_id, None)

    def _market_figure(self, market_id: str) -> float | None:
        """What a hard close would lock at the prices loaded now (or the guaranteed result if there is nothing to hedge)."""
        book = self.ex.get_book(market_id)
        pos = self.positions().get(market_id, {})
        full = {sid: pos.get(sid, Position()) for sid in book.selections}
        if not any(abs(p.win) > 0.004 or abs(p.lose) > 0.004 for p in full.values()):
            return None
        out = pnl.market_outcomes(full)
        plan = pnl.green_plan(out, {k: (v.backs[0].price if v.backs else None) for k, v in book.selections.items()},
                              {k: (v.lays[0].price if v.lays else None) for k, v in book.selections.items()})
        return plan["locked"] if plan and plan["bets"] else min(out.values())

    @locked
    def add_market_trigger(self, market_id: str, level: float) -> dict:
        self.ex.refresh(self.feed.get_books([market_id], depth=False))
        fig = self._market_figure(market_id)
        if fig is None:
            raise ValueError("no position in this market to protect")
        if abs(level - fig) < 0.005:
            raise ValueError("that is where the market's profit is right now")
        t = MarketTrigger(f"M{next(self._trigger_ids)}", market_id, round(level, 2), "ge" if level > fig else "le",
                          "take profit" if level >= 0 else "stop loss")
        self.mtriggers[t.id] = t
        self._log(f"Auto-green set: hard close the market when the profit reaches {t.level:+.2f} (now {fig:+.2f})", "trigger")
        return t.__dict__

    @locked
    def cancel_market_trigger(self, trigger_id: str) -> bool:
        return self.mtriggers.pop(trigger_id, None) is not None

    def _check_market_triggers(self) -> None:
        for t in list(self.mtriggers.values()):
            try:
                if self.ex.get_book(t.market_id).status != "OPEN":
                    continue
                fig = self._market_figure(t.market_id)
            except Exception:
                continue
            if fig is None:
                self.mtriggers.pop(t.id, None); continue
            if (t.direction == "ge" and fig >= t.level - 1e-9) or (t.direction == "le" and fig <= t.level + 1e-9):
                self.mtriggers.pop(t.id, None)
                try:
                    res = self.green_market.__wrapped__(self, t.market_id, True)
                    msg = f"Auto-green fired at {fig:+.2f}: " + (f"hard close, locked £{res.get('locked', 0):.2f}" if res.get("greened") else res.get("reason", "nothing to do"))
                except Exception as ex:
                    msg = f"Auto-green at {t.level:+.2f} FAILED: {ex}"
                self.events.append({"t": time.time(), "text": msg, "trigger": t.id}); self._log(msg, "trigger")

    def _check_fok(self) -> None:
        now = time.time()
        for oid, deadline in list(self.fok.items()):
            try:
                o = self.ex.get_order(oid)
            except Exception:
                self.fok.pop(oid, None); continue
            if o.status not in OPEN:
                self.fok.pop(oid, None)
            elif now >= deadline:
                left = o.remaining
                self.ex.cancel_order(oid); self.fok.pop(oid, None)
                msg = f"Fill-or-kill: cancelled the unmatched £{left:.2f} of the {o.request.side.value} @ {o.request.price:.2f} on {self._name(o.request.market_id, o.request.selection_id)}"
                self.events.append({"t": now, "text": msg, "trigger": ""}); self._log(msg, "order")

    @locked
    def cancel(self, order_id: str) -> dict:
        o = self.ex.cancel_order(order_id)
        self.fok.pop(order_id, None)
        self._log(f"Cancelled {o.request.side.value} @ {o.request.price:.2f} on {self._name(o.request.market_id, o.request.selection_id)}", "order")
        return self._order(o)

    @locked
    def cancel_many(self, market_id: str, selection_id: str | None = None, side: str | None = None) -> int:
        n = 0
        for o in self.ex.open_orders():
            r = o.request
            if o.status in OPEN and r.market_id == market_id and (selection_id in (None, r.selection_id)) and (side in (None, r.side.value)):
                self.ex.cancel_order(o.order_id); self.fok.pop(o.order_id, None); n += 1
        if n:
            self._log(f"Cancelled {n} unmatched bet{'s' if n != 1 else ''}", "order")
        return n

    @locked
    def close_position(self, market_id: str, selection_id: str) -> dict:
        p = self.positions().get(market_id, {}).get(selection_id, Position())
        if self.ex.get_book(market_id).status != "OPEN":
            return {"closed": False, "reason": f"the market is {self.ex.get_book(market_id).status.lower()}; nothing can be placed right now"}
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
    def green_market(self, market_id: str, hard: bool = False, pct: float = 1.0, source: str = "manual") -> dict:
        """Equalise every outcome of the market at the prices available now. hard=True first cancels unmatched orders."""
        self.ex.refresh(self.feed.get_books([market_id], depth=False))
        if self.ex.get_book(market_id).status != "OPEN":
            return {"greened": False, "cancelled": 0, "reason": f"the market is {self.ex.get_book(market_id).status.lower()}; nothing can be placed right now"}
        cancelled = self.cancel_many(market_id) if hard else 0
        book = self.ex.get_book(market_id)
        pos = self.positions().get(market_id, {})
        full = {sid: pos.get(sid, Position()) for sid in book.selections}
        plan = pnl.green_plan(pnl.market_outcomes(full), {k: (v.backs[0].price if v.backs else None) for k, v in book.selections.items()},
                              {k: (v.lays[0].price if v.lays else None) for k, v in book.selections.items()})
        if plan is None:
            return {"greened": False, "cancelled": cancelled, "reason": "nothing to green up (level, or no prices available)"}
        placed = []
        bets = plan["bets"]
        if pct < 0.999:                                     # partial hedge: only part of the way to level
            bets = [{**b, "stake": round(b["stake"] * pct, 2)} for b in bets]
            bets = [b for b in bets if b["stake"] >= 1.0]
            if not bets:
                return {"greened": False, "cancelled": cancelled, "reason": f"{int(pct * 100)}% of the hedge is under the £1 minimum stake"}
            after = pnl.market_outcomes(full)
            for b in bets:
                after = pnl._apply(after, b["selection_id"], Side(b["side"]), b["price"], b["stake"])
            plan = {**plan, "locked": round(min(after.values()), 2), "level": False}
        for b in bets:
            r = self.place(market_id, b["selection_id"], b["side"], b["price"], b["stake"], source=source)
            placed.append({**b, "status": r["order"]["status"]})
        self._log(f"{'Hard close' if hard else 'Green up'} on {self._info.get(market_id, {}).get('event', market_id)}: locked £{plan['locked']:.2f}", "order")
        return {"greened": True, "cancelled": cancelled, "locked": plan["locked"], "level": plan["level"], "placed": placed}

    # ---- dutching and bookmaking ---------------------------------------------
    def _plan_inputs(self, market_id: str):
        self.ex.refresh(self.feed.get_books([market_id], depth=False))
        book = self.ex.get_book(market_id)
        pos = self.positions().get(market_id, {})
        full = {sid: pos.get(sid, Position()) for sid in book.selections}
        cur = pnl.market_outcomes(full)
        backs = {k: (v.backs[0].price if v.backs else None) for k, v in book.selections.items()}
        lays = {k: (v.lays[0].price if v.lays else None) for k, v in book.selections.items()}
        return book, cur, backs, lays

    def _decorate(self, market_id: str, plan: dict, cur: dict) -> dict:
        after = dict(cur)
        for b in plan["bets"]:
            after = pnl._apply(after, b["selection_id"], Side(b["side"]), b["price"], b["stake"])
            b["runner"] = self._name(market_id, b["selection_id"])
        plan["before"] = cur
        plan["after"] = {i: round(v, 2) for i, v in after.items()}
        plan["total_stake"] = round(sum(b["stake"] for b in plan["bets"]), 2)
        for b in plan["dropped"]:
            b["runner"] = self._name(market_id, b["selection_id"])
        return plan

    @locked
    def dutch_preview(self, market_id: str, selection_ids: list[str], side: str, total: float, prices: dict[str, float] | None = None) -> dict:
        """Spread `total` over the chosen runners so each returns the same. Prices default to the best available (back price for a back, lay price for a lay)."""
        book, cur, backs, lays = self._plan_inputs(market_id)
        if total < 1.0:
            raise ValueError("the total stake must be at least £1")
        if len(selection_ids) < 2:
            raise ValueError("pick at least two runners to dutch")
        use: dict[str, float] = {}
        for sid in selection_ids:
            if sid not in book.selections:
                raise ValueError(f"unknown runner {sid}")
            pr = (prices or {}).get(sid) or (backs.get(sid) if side == "BACK" else lays.get(sid))
            if not pr:
                raise ValueError(f"no {'back' if side == 'BACK' else 'lay'} price available on {self._name(market_id, sid)}")
            if not ticks.is_valid(pr):
                raise ValueError(f"{pr} is not a valid Betfair price")
            use[sid] = pr
        plan = pnl.dutch_plan(Side(side), use, total)
        return self._decorate(market_id, plan, cur)

    @locked
    def dutch_place(self, market_id: str, selection_ids: list[str], side: str, total: float, prices: dict[str, float] | None = None) -> dict:
        plan = self.dutch_preview(market_id, selection_ids, side, total, prices)
        return self._place_plan(market_id, plan, f"Dutch {side} £{plan['total_stake']:.2f}")

    @locked
    def book_preview(self, market_id: str, targets: dict[str, float]) -> dict:
        """The bets that make each runner's outcome the profit you name, from where the market is now."""
        book, cur, backs, lays = self._plan_inputs(market_id)
        for sid in targets:
            if sid not in book.selections:
                raise ValueError(f"unknown runner {sid}")
        plan = pnl.book_plan(cur, {k: float(targets[k]) for k in targets}, backs, lays)
        out = self._decorate(market_id, {**plan, "bets": plan["bets"], "dropped": plan["dropped"]}, cur)
        out["after"] = plan["after"]
        return out

    @locked
    def book_place(self, market_id: str, targets: dict[str, float]) -> dict:
        plan = self.book_preview(market_id, targets)
        if plan.get("error"):
            raise ValueError(plan["error"])
        return self._place_plan(market_id, plan, "Book")

    def _place_plan(self, market_id: str, plan: dict, label: str) -> dict:
        if plan.get("error"):
            raise ValueError(plan["error"])
        if not plan["bets"]:
            raise ValueError("nothing to place: every bet is under the £1 minimum stake, or the market is already where you want it")
        self._require_open(market_id)
        placed = []
        for b in plan["bets"]:
            try:
                r = self.place(market_id, b["selection_id"], b["side"], b["price"], b["stake"])
                placed.append({**b, "status": r["order"]["status"], "order_id": r["order"]["order_id"]})
            except Exception as ex:          # noqa: BLE001  (one leg failing must not hide the legs already placed)
                placed.append({**b, "status": "FAILED", "error": str(ex)})
        failed = [p for p in placed if p["status"] in ("FAILED", "REJECTED")]
        self._log(f"{label} on {self._info.get(market_id, {}).get('event', market_id)}: {len(placed) - len(failed)} of {len(placed)} bets placed"
                  + (f", {len(failed)} FAILED" if failed else ""), "order")
        return {"placed": placed, "failed": len(failed), "after": plan["after"]}

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
            if ltp is None or self.ex.get_book(t.market_id).status != "OPEN":
                continue                      # a suspended market cannot be traded: the stop waits and fires when it reopens
            if (t.direction == "le" and ltp <= t.price + 1e-9) or (t.direction == "ge" and ltp >= t.price - 1e-9):
                self.triggers.pop(t.id, None)
                for oid in t.cancel:
                    try:
                        if self.ex.get_order(oid).status in OPEN:
                            self.ex.cancel_order(oid)
                    except Exception:
                        pass
                if t.link:
                    self.entries.pop(t.link, None)
                try:
                    res = self.close_position.__wrapped__(self, t.market_id, t.selection_id)
                    msg = f"{t.label.capitalize()} fired at {t.price:.2f}: " + (f"closed, locked £{res.get('locked_profit', 0):.2f}" if res.get("closed") else res.get("reason", "nothing to close"))
                except Exception as e:           # never let a failed trigger break the loop; say so loudly
                    msg = f"{t.label.capitalize()} at {t.price:.2f} FAILED to close: {e}"
                self.events.append({"t": time.time(), "text": msg, "trigger": t.id}); self._log(msg, "trigger")

    @locked
    def check_triggers_now(self) -> None:
        mids = sorted({t.market_id for t in self.triggers.values()} | {t.market_id for t in self.mtriggers.values()} | {e.market_id for e in self.entries.values()})
        if mids:
            self.ex.refresh(self.feed.get_books(mids, depth=False))
            self._process_entries()
            self._check_triggers()
            self._check_market_triggers()
        self._check_fok()

    def start_background(self, every: float = 2.0) -> None:
        """Keep triggers working when no browser is open."""
        if self._bg:
            return
        if self.live:
            try:
                self.live_reconcile()
            except Exception as e:        # noqa: BLE001
                self._log(f"Start-up check against Betfair failed: {e}", "warn")
        def loop():
            n = 0
            while True:
                time.sleep(every)
                n += 1
                try:
                    if self.live:
                        self.ex.sync()
                    self.check_triggers_now()
                    self.run_scripts()
                    if n % max(1, int(15 / every)) == 0:
                        self.settle_check()
                except Exception:
                    pass
        self._bg = threading.Thread(target=loop, daemon=True, name="triggers")
        self._bg.start()
