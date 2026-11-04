"""Keeps the tennis store filled from api-tennis: upcoming and recent fixtures, live scores, rankings, and a walk back through
history (a week per request, newest first) so the model can be rebuilt from our own data."""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time

from .apitennis import ApiTennis, ApiTennisError
from .livestore import TennisStore

log = logging.getLogger("autobets.tennis")
HISTORY_DAYS = 730          # how far back to walk (two years)
CHUNK = 7                   # days per history request


class TennisCollector:
    def __init__(self, api: ApiTennis, store: TennisStore, now=None):
        self.api, self.store = api, store
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.stop = threading.Event()

    def sync_fixtures(self, start: str, stop: str) -> int:
        n = 0
        for m in self.api.fixtures(start, stop):
            self.store.upsert(m); n += 1
        return n

    def sync_live(self) -> int:
        items = self.api.livescore()
        for m in items:
            self.store.upsert(m); self.store.snapshot(m)
        gone = set(self.store.live_keys()) - {int(m["event_key"]) for m in items}      # finished since the last poll: re-read their final state
        if gone:
            d = self.now().strftime("%Y-%m-%d")
            for m in self.api.fixtures(d, d):
                if int(m["event_key"]) in gone:
                    self.store.upsert(m); self.store.snapshot(m)
        return len(items)

    def sync_standings(self) -> None:
        day = self.now().strftime("%Y-%m-%d")
        for tour in ("ATP", "WTA"):
            self.store.save_standings(tour, day, self.api.get("get_standings", event_type=tour))

    def walk_history(self) -> bool:
        """One more week further back. Returns False when the whole span has been covered."""
        today = self.now().date()
        done = self.store.get_meta("hist_days", 0)
        if done >= HISTORY_DAYS:
            return False
        stop = today - dt.timedelta(days=done + 1)
        start = stop - dt.timedelta(days=CHUNK - 1)
        self.sync_fixtures(start.isoformat(), stop.isoformat())
        self.store.set_meta("hist_days", done + CHUNK)
        return True

    def tick(self, state: dict) -> None:
        now = self.now(); ts = time.time()
        active = self.store.active_soon(now.isoformat())
        if ts - state.get("live", 0) >= (30 if active else 600):
            self.sync_live(); state["live"] = ts
        if ts - state.get("fixtures", 0) >= 3600:
            d0 = now.date(); self.sync_fixtures((d0 - dt.timedelta(days=2)).isoformat(), (d0 + dt.timedelta(days=3)).isoformat()); state["fixtures"] = ts
        if ts - state.get("standings", 0) >= 86400:
            self.sync_standings(); state["standings"] = ts
        self.walk_history()

    def run_forever(self) -> None:
        state: dict = {}
        while not self.stop.is_set():
            try:
                self.tick(state)
                self.store.set_meta("last_tick", self.now().isoformat()); self.store.set_meta("last_error", None)
            except ApiTennisError as e:
                log.warning("tennis collector: %s", e); self.store.set_meta("last_error", str(e)); self.stop.wait(60)
            except Exception:
                log.exception("tennis collector crashed this pass"); self.stop.wait(60)
            self.stop.wait(10)

    def status(self) -> dict:
        return {**self.store.counts(), "history_days_done": self.store.get_meta("hist_days", 0), "history_target": HISTORY_DAYS,
                "last_tick": self.store.get_meta("last_tick"), "last_error": self.store.get_meta("last_error")}
