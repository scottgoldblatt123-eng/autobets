"""Records Betfair prices together with the live score, for every tennis and football match-odds market on the list.

One row per market whenever its best back/lay prices, in-play flag or score changes (so quiet markets cost almost nothing).
This is the dataset for testing models against the market (pre-match price vs result, and how prices react to breaks and goals).
Read-only: it only reads prices. On a delayed Betfair key the prices lag real time; the lag is stored nowhere else, so keep that in mind
when analysing. Runs in a background thread inside the API process; every failure is logged and retried, never raised."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time

log = logging.getLogger("autobets.pricelog")
SPORTS = ("tennis", "football")
FAST, SLOW = 15.0, 60.0         # seconds between passes when something is in play / when nothing is


class PriceStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ticks(t REAL, market_id TEXT, sport TEXT, event TEXT, start TEXT, in_play INT, status TEXT, prices TEXT, ctx TEXT);
            CREATE INDEX IF NOT EXISTS tk_m ON ticks(market_id, t);
            CREATE INDEX IF NOT EXISTS tk_t ON ticks(t);
            CREATE TABLE IF NOT EXISTS runners(market_id TEXT PRIMARY KEY, names TEXT);
            """)
            self.db.commit()
        self.last: dict[str, tuple] = {}

    def add(self, t: float, m: dict, book, ctx: dict | None) -> bool:
        prices = {sid: [s.backs[0].price if s.backs else None, s.lays[0].price if s.lays else None] for sid, s in book.selections.items()}
        c = json.dumps(self._slim(ctx), sort_keys=True) if ctx else None
        key = (json.dumps(prices, sort_keys=True), bool(book.in_play), book.status, c)
        if self.last.get(m["market_id"]) == key:
            return False
        self.last[m["market_id"]] = key
        with self.lock:
            self.db.execute("INSERT INTO ticks VALUES(?,?,?,?,?,?,?,?,?)", (t, m["market_id"], m.get("sport"), m.get("event"), m.get("start"), 1 if book.in_play else 0,
                                                                          book.status, key[0], c))
            self.db.execute("INSERT OR REPLACE INTO runners VALUES(?,?)", (m["market_id"], json.dumps(m.get("runners", {}))))
            self.db.commit()
        return True

    @staticmethod
    def _slim(ctx: dict) -> dict:
        keep = ("kind", "status", "live", "sets", "game", "serving", "elapsed", "goals", "model")
        return {k: ctx[k] for k in keep if k in ctx}

    def counts(self) -> dict:
        with self.lock:
            q = lambda s: self.db.execute(s).fetchone()[0]
            return {"ticks": q("SELECT COUNT(*) FROM ticks"), "markets": q("SELECT COUNT(DISTINCT market_id) FROM ticks"),
                    "in_play_ticks": q("SELECT COUNT(*) FROM ticks WHERE in_play=1"), "first": q("SELECT MIN(t) FROM ticks"), "last": q("SELECT MAX(t) FROM ticks")}


class PriceLogger:
    def __init__(self, engine, match_context, store: PriceStore, now=time.time) -> None:
        self.engine, self.ctx, self.store, self.now = engine, match_context, store, now
        self.stop = threading.Event()
        self.last_error: str | None = None

    def once(self) -> bool:
        """One pass over the listed markets. Returns True if any market is in play."""
        any_live, t = False, self.now()
        for sport in SPORTS:
            markets = self.engine.markets(sport)
            for i in range(0, len(markets), 40):
                chunk = markets[i:i + 40]
                with self.engine.lock:
                    books = {b.market_id: b for b in self.engine.feed.get_books([m["market_id"] for m in chunk])}
                for m in chunk:
                    b = books.get(m["market_id"])
                    if not b:
                        continue
                    any_live = any_live or b.in_play
                    try:
                        ctx = self.ctx.for_market(m)
                    except Exception:
                        ctx = None
                    self.store.add(t, {**m, "sport": sport}, b, ctx)
        return any_live

    def run_forever(self) -> None:
        wait = SLOW
        while not self.stop.is_set():
            try:
                wait = FAST if self.once() else SLOW
                self.last_error = None
            except Exception as e:
                log.warning("price logger: %s", e); self.last_error = str(e); wait = 60.0
            self.stop.wait(wait)

    def status(self) -> dict:
        return {**self.store.counts(), "last_error": self.last_error}
