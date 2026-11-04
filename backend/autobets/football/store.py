"""SQLite store for football data. Fixtures are upserted as they change; live scores are appended as a time series;
match stats, events and lineups are kept once a match is finished. The raw JSON is kept alongside the columns."""
from __future__ import annotations

import json
import sqlite3
import threading
import time

FINISHED = ("FT", "AET", "PEN")
LIVE = ("1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE")


class FootballStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS fixtures(id INTEGER PRIMARY KEY, league_id INT, season INT, kickoff TEXT, status TEXT, elapsed INT,
                home_id INT, home TEXT, away_id INT, away TEXT, goals_h INT, goals_a INT, ht_h INT, ht_a INT, venue TEXT, referee TEXT,
                updated REAL, raw TEXT);
            CREATE INDEX IF NOT EXISTS fx_kick ON fixtures(kickoff);
            CREATE INDEX IF NOT EXISTS fx_league ON fixtures(league_id, season);
            CREATE TABLE IF NOT EXISTS live(fixture_id INT, t REAL, status TEXT, elapsed INT, goals_h INT, goals_a INT);
            CREATE INDEX IF NOT EXISTS live_fx ON live(fixture_id, t);
            CREATE TABLE IF NOT EXISTS stats(fixture_id INT, team_id INT, data TEXT, fetched REAL, PRIMARY KEY(fixture_id, team_id));
            CREATE TABLE IF NOT EXISTS events(fixture_id INT PRIMARY KEY, data TEXT, fetched REAL);
            CREATE TABLE IF NOT EXISTS lineups(fixture_id INT PRIMARY KEY, data TEXT, fetched REAL);
            CREATE TABLE IF NOT EXISTS standings(league_id INT, season INT, day TEXT, data TEXT, PRIMARY KEY(league_id, season, day));
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
            """)
            self.db.commit()

    # ---- fixtures -------------------------------------------------------------------------------------------
    def upsert_fixture(self, item: dict) -> bool:
        """Insert or update one fixture from an API-Football fixtures item. Returns True if the score or status changed."""
        f, lg, tm, g = item["fixture"], item["league"], item["teams"], item.get("goals") or {}
        ht = (item.get("score") or {}).get("halftime") or {}
        st = (f.get("status") or {})
        row = (f["id"], lg.get("id"), lg.get("season"), f.get("date"), st.get("short"), st.get("elapsed"),
               tm["home"].get("id"), tm["home"].get("name"), tm["away"].get("id"), tm["away"].get("name"),
               g.get("home"), g.get("away"), ht.get("home"), ht.get("away"), (f.get("venue") or {}).get("name"), f.get("referee"),
               time.time(), json.dumps(item))
        with self.lock:
            old = self.db.execute("SELECT status, goals_h, goals_a FROM fixtures WHERE id=?", (f["id"],)).fetchone()
            self.db.execute("INSERT OR REPLACE INTO fixtures VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            self.db.commit()
        return old is None or old != (st.get("short"), g.get("home"), g.get("away"))

    def snapshot_live(self, item: dict) -> None:
        f, g = item["fixture"], item.get("goals") or {}
        with self.lock:
            last = self.db.execute("SELECT status, elapsed, goals_h, goals_a FROM live WHERE fixture_id=? ORDER BY t DESC LIMIT 1", (f["id"],)).fetchone()
            now = (f["status"].get("short"), f["status"].get("elapsed"), g.get("home"), g.get("away"))
            if last != now:
                self.db.execute("INSERT INTO live VALUES(?,?,?,?,?,?)", (f["id"], time.time(), *now))
                self.db.commit()

    def live_ids(self) -> list[int]:
        with self.lock:
            return [r[0] for r in self.db.execute(f"SELECT id FROM fixtures WHERE status IN ({','.join('?' * len(LIVE))})", LIVE)]

    def playing_soon(self, now_iso: str, before_min: int = 20, after_min: int = 190) -> bool:
        """Is any tracked fixture about to start, or plausibly still in progress? Decides how often to poll for live scores."""
        import datetime as dt
        t = dt.datetime.fromisoformat(now_iso)
        lo, hi = (t - dt.timedelta(minutes=after_min)).isoformat(), (t + dt.timedelta(minutes=before_min)).isoformat()
        with self.lock:
            n = self.db.execute("SELECT COUNT(*) FROM fixtures WHERE kickoff BETWEEN ? AND ? AND status NOT IN ('FT','AET','PEN','PST','CANC','ABD','AWD','WO')", (lo, hi)).fetchone()[0]
        return n > 0

    def needing_details(self, limit: int) -> list[int]:
        """Finished fixtures without stats yet, newest first."""
        with self.lock:
            q = f"""SELECT id FROM fixtures WHERE status IN ({','.join('?' * len(FINISHED))})
                    AND id NOT IN (SELECT fixture_id FROM events) ORDER BY kickoff DESC LIMIT ?"""
            return [r[0] for r in self.db.execute(q, (*FINISHED, limit))]

    # ---- details --------------------------------------------------------------------------------------------
    def save_details(self, fixture_id: int, stats: list, events: list, lineups: list) -> None:
        now = time.time()
        with self.lock:
            for s in stats or []:
                self.db.execute("INSERT OR REPLACE INTO stats VALUES(?,?,?,?)", (fixture_id, (s.get("team") or {}).get("id"), json.dumps(s), now))
            self.db.execute("INSERT OR REPLACE INTO lineups VALUES(?,?,?)", (fixture_id, json.dumps(lineups or []), now))
            self.db.execute("INSERT OR REPLACE INTO events VALUES(?,?,?)", (fixture_id, json.dumps(events or []), now))      # last: marks the fixture as done
            self.db.commit()

    def save_standings(self, league_id: int, season: int, day: str, data: list) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO standings VALUES(?,?,?,?)", (league_id, season, day, json.dumps(data)))
            self.db.commit()

    def set_meta(self, k: str, v) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v)))
            self.db.commit()

    def get_meta(self, k: str, default=None):
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def counts(self) -> dict:
        with self.lock:
            q = lambda s: self.db.execute(s).fetchone()[0]
            return {"fixtures": q("SELECT COUNT(*) FROM fixtures"), "finished": q(f"SELECT COUNT(*) FROM fixtures WHERE status IN {FINISHED}"),
                    "with_details": q("SELECT COUNT(*) FROM events"), "live_snapshots": q("SELECT COUNT(*) FROM live"),
                    "live_now": len(self.live_ids())}
