"""Keeps the football store filled from API-Football: season fixtures, live scores, then match details for finished games.
Request budget (Pro plan: 7,500 a day, 300 a minute): live polling comes first, backfill only uses what is spare."""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time

from .apifootball import ApiFootball, ApiFootballError, current_season
from .store import FootballStore

log = logging.getLogger("autobets.football")

# Top flights of the six countries, plus the Championship (Betfair liquidity). Add more ids here; one call per league per season.
LEAGUES = {39: "Premier League", 40: "Championship", 78: "Bundesliga", 140: "La Liga", 135: "Serie A", 61: "Ligue 1", 179: "Scottish Premiership"}
BACKFILL_SEASONS = 4            # past seasons kept for model training (the current one is always synced)
DAILY_CAP = 7500
SPARE_FLOOR = 2500              # backfill stops once fewer than this many requests are left today: live polling must never starve


class Collector:
    def __init__(self, api: ApiFootball, store: FootballStore, now=None):
        self.api, self.store = api, store
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.used_today = 0
        self.stop = threading.Event()

    # ---- steps ----------------------------------------------------------------------------------------------
    def sync_season(self, league: int, season: int) -> int:
        items = self.api.get("fixtures", league=league, season=season).get("response") or []
        for it in items:
            self.store.upsert_fixture(it)
        return len(items)

    def sync_live(self) -> int:
        items = [i for i in (self.api.get("fixtures", _save=False, live="all").get("response") or []) if i["league"]["id"] in LEAGUES]
        for it in items:
            self.store.upsert_fixture(it)
            self.store.snapshot_live(it)
        # a game that has just ended drops out of live=all, so re-read any we still hold as in play
        gone = set(self.store.live_ids()) - {i["fixture"]["id"] for i in items}
        for fid in list(gone)[:5]:
            for it in self.api.get("fixtures", id=fid).get("response") or []:
                self.store.upsert_fixture(it)
                self.store.snapshot_live(it)
        return len(items)

    def sync_today(self) -> int:
        n = 0
        for it in self.api.get("fixtures", date=self.now().strftime("%Y-%m-%d")).get("response") or []:
            if it["league"]["id"] in LEAGUES:
                self.store.upsert_fixture(it); n += 1
        return n

    def sync_standings(self, league: int, season: int) -> None:
        r = self.api.get("standings", league=league, season=season).get("response") or []
        self.store.save_standings(league, season, self.now().strftime("%Y-%m-%d"), r)

    def backfill_details(self, n: int) -> int:
        done = 0
        for fid in self.store.needing_details(n):
            stats = self.api.get("fixtures/statistics", fixture=fid).get("response") or []
            events = self.api.get("fixtures/events", fixture=fid).get("response") or []
            lineups = self.api.get("fixtures/lineups", fixture=fid).get("response") or []
            self.store.save_details(fid, stats, events, lineups)
            done += 1
        return done

    def refresh_budget(self) -> None:
        try:
            self.used_today = int(self.api.status().get("used_today") or 0)
        except (ApiFootballError, TypeError, ValueError):
            pass

    # ---- the loop -------------------------------------------------------------------------------------------
    def tick(self, state: dict) -> None:
        """One pass. `state` remembers when each job last ran, so a restart simply carries on."""
        now = self.now(); ts = time.time()
        if now.timestamp() - state.get("budget", 0) >= 300:
            self.refresh_budget(); state["budget"] = now.timestamp()
        season = current_season()
        playing = self.store.playing_soon(now.isoformat())
        if playing and ts - state.get("live", 0) >= 30:
            self.sync_live(); state["live"] = ts
        elif not playing and ts - state.get("live", 0) >= 600:
            self.sync_live(); state["live"] = ts            # a slow check in case a fixture was moved
        if ts - state.get("today", 0) >= 3600:
            self.sync_today(); state["today"] = ts
        if ts - state.get("season", 0) >= 6 * 3600:          # whole current season per league: kick-off changes, postponements, results
            for lg in LEAGUES:
                self.sync_season(lg, season)
            state["season"] = ts
        if ts - state.get("standings", 0) >= 24 * 3600:
            for lg in LEAGUES:
                self.sync_standings(lg, season)
            state["standings"] = ts
        # history for the models: one call per league per past season, then details newest first while there is spare budget
        for back in range(1, BACKFILL_SEASONS + 1):
            key = f"hist{season - back}"
            if not self.store.get_meta(key) and DAILY_CAP - self.used_today > SPARE_FLOOR:
                for lg in LEAGUES:
                    self.sync_season(lg, season - back)
                self.store.set_meta(key, True)
        if DAILY_CAP - self.used_today > SPARE_FLOOR:
            self.backfill_details(6)

    def run_forever(self) -> None:
        state: dict = {}
        while not self.stop.is_set():
            try:
                self.tick(state)
                self.store.set_meta("last_tick", self.now().isoformat())
                self.store.set_meta("last_error", None)
            except ApiFootballError as e:
                log.warning("football collector: %s", e)
                self.store.set_meta("last_error", str(e))
                self.stop.wait(60)
            except Exception:
                log.exception("football collector crashed this pass")
                self.stop.wait(60)
            self.stop.wait(10)

    def status(self) -> dict:
        return {**self.store.counts(), "requests_used_today": self.used_today, "last_tick": self.store.get_meta("last_tick"),
                "last_error": self.store.get_meta("last_error"), "leagues": list(LEAGUES.values())}


if __name__ == "__main__":      # python -m autobets.football.collector : run one pass by hand and print what is stored
    import os
    data = os.environ.get("AUTOBETS_DATA", "/opt/autobets/data")
    c = Collector(ApiFootball(store_dir=data + "/apifootball"), FootballStore(data + "/football.db"))
    c.tick({}); print(c.status())
