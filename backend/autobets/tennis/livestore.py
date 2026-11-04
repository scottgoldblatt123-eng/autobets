"""SQLite store for tennis matches and a live time series (one row per change in score or status)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time

DONE = ("Finished", "Retired", "Walkover", "Cancelled", "Abandoned")


class TennisStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS matches(event_key INTEGER PRIMARY KEY, day TEXT, time TEXT, type TEXT, tournament TEXT, season TEXT,
                p1 TEXT, p1_key INT, p2 TEXT, p2_key INT, status TEXT, result TEXT, winner TEXT, live INT, updated REAL, raw TEXT);
            CREATE INDEX IF NOT EXISTS m_day ON matches(day);
            CREATE TABLE IF NOT EXISTS live(event_key INT, t REAL, status TEXT, result TEXT, scores TEXT, serve TEXT);
            CREATE INDEX IF NOT EXISTS live_ev ON live(event_key, t);
            CREATE TABLE IF NOT EXISTS standings(tour TEXT, day TEXT, data TEXT, PRIMARY KEY(tour, day));
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
            """)
            self.db.commit()

    def upsert(self, m: dict) -> bool:
        row = (int(m["event_key"]), m.get("event_date"), m.get("event_time"), m.get("event_type_type"), m.get("tournament_name"),
               m.get("tournament_season"), m.get("event_first_player"), m.get("first_player_key"), m.get("event_second_player"),
               m.get("second_player_key"), m.get("event_status"), m.get("event_final_result"), m.get("event_winner"),
               1 if str(m.get("event_live")) == "1" else 0, time.time(), json.dumps(m))
        with self.lock:
            old = self.db.execute("SELECT status, result, live FROM matches WHERE event_key=?", (row[0],)).fetchone()
            self.db.execute("INSERT OR REPLACE INTO matches VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            self.db.commit()
        return old is None or old != (row[10], row[11], row[13])

    def snapshot(self, m: dict) -> None:
        key = int(m["event_key"]); scores = json.dumps(m.get("scores") or []); now = (m.get("event_status"), m.get("event_final_result"), scores, m.get("event_serve"))
        with self.lock:
            last = self.db.execute("SELECT status, result, scores, serve FROM live WHERE event_key=? ORDER BY t DESC LIMIT 1", (key,)).fetchone()
            if last != now:
                self.db.execute("INSERT INTO live VALUES(?,?,?,?,?,?)", (key, time.time(), *now))
                self.db.commit()

    def live_keys(self) -> list[int]:
        with self.lock:
            return [r[0] for r in self.db.execute("SELECT event_key FROM matches WHERE live=1")]

    def active_soon(self, now_iso: str, before_min: int = 30) -> bool:
        """Any match live now, or due to start within `before_min` minutes today?"""
        import datetime as dt
        t = dt.datetime.fromisoformat(now_iso)
        with self.lock:
            if self.db.execute("SELECT 1 FROM matches WHERE live=1 LIMIT 1").fetchone():
                return True
            rows = self.db.execute("SELECT time FROM matches WHERE day=? AND status NOT IN ('Finished','Retired','Walkover','Cancelled','Abandoned')", (t.strftime("%Y-%m-%d"),)).fetchall()
        for (hhmm,) in rows:
            try:
                h, mnt = (int(x) for x in (hhmm or "").split(":")[:2])
            except ValueError:
                continue
            start = t.replace(hour=h, minute=mnt, second=0, microsecond=0)
            if -60 * 5 <= (start - t).total_seconds() / 60 <= before_min:
                return True
        return False

    def save_standings(self, tour: str, day: str, data) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO standings VALUES(?,?,?)", (tour, day, json.dumps(data)))
            self.db.commit()

    def set_meta(self, k, v) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v)))
            self.db.commit()

    def get_meta(self, k, default=None):
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def counts(self) -> dict:
        with self.lock:
            q = lambda s: self.db.execute(s).fetchone()[0]
            return {"matches": q("SELECT COUNT(*) FROM matches"), "finished": q("SELECT COUNT(*) FROM matches WHERE status='Finished'"),
                    "with_stats": q("SELECT COUNT(*) FROM matches WHERE raw LIKE '%\"statistics\": [{%'"),
                    "live_snapshots": q("SELECT COUNT(*) FROM live"), "live_now": q("SELECT COUNT(*) FROM matches WHERE live=1"),
                    "earliest": q("SELECT MIN(day) FROM matches")}
