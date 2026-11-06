"""Automatic backups of the app's data on the server, plus a disk-space check.

Once a day (and at start-up if today's is missing) every SQLite database in the data folder is copied with SQLite's online backup
(safe while the app is writing) and every .json state file is copied, all gzipped into data/backups/YYYY-MM-DD/. The last 7 days and the
last 4 Sundays are kept. These protect against a bad deploy, a corrupted file or a mistake; they do NOT protect against losing the
whole server, which needs DigitalOcean's droplet backups or an off-server copy."""
from __future__ import annotations

import datetime as dt
import gzip
import os
import shutil
import sqlite3
import threading
import time


class Backups:
    def __init__(self, data_dir: str, keep_days: int = 7, keep_weeks: int = 4) -> None:
        self.dir, self.root = data_dir, os.path.join(data_dir, "backups")
        self.keep_days, self.keep_weeks = keep_days, keep_weeks
        self.last_ok: float = 0.0
        self.last_error: str = ""
        self.last_files: int = 0
        self._thread: threading.Thread | None = None

    def _day(self, day: dt.date) -> str:
        return os.path.join(self.root, day.isoformat())

    def run(self, today: dt.date | None = None) -> int:
        """Back everything up now. Returns the number of files written; records success or the error."""
        day = today or dt.date.today()
        need = folder_mb(self.dir) * 1e6 * 1.2
        if need and shutil.disk_usage(self.dir).free < need:
            self.last_error = "not enough free disk space to back up"
            raise OSError(self.last_error)
        out = self._day(day)
        tmp = out + ".partial"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        n = 0
        try:
            for name in sorted(os.listdir(self.dir)):
                src = os.path.join(self.dir, name)
                if not os.path.isfile(src) or name.endswith(("-wal", "-shm", ".partial")):
                    continue
                if name.endswith((".db", ".sqlite")):
                    mid = os.path.join(tmp, name)
                    con, dst = sqlite3.connect(f"file:{src}?mode=ro", uri=True), sqlite3.connect(mid)
                    try:
                        con.backup(dst)
                    finally:
                        dst.close(); con.close()
                elif name.endswith(".json"):
                    mid = os.path.join(tmp, name)
                    shutil.copy2(src, mid)
                else:
                    continue
                with open(mid, "rb") as f, gzip.open(mid + ".gz", "wb", compresslevel=6) as g:
                    shutil.copyfileobj(f, g)
                os.remove(mid)
                n += 1
            shutil.rmtree(out, ignore_errors=True)
            os.rename(tmp, out)
            self._prune(day)
            self.last_ok, self.last_error, self.last_files = time.time(), "", n
        except Exception as e:        # noqa: BLE001
            shutil.rmtree(tmp, ignore_errors=True)
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            raise
        return n

    def _prune(self, today: dt.date) -> None:
        keep = {(today - dt.timedelta(days=i)).isoformat() for i in range(self.keep_days)}
        for d in os.listdir(self.root):
            try:
                day = dt.date.fromisoformat(d)
            except ValueError:
                continue
            if d in keep or (day.weekday() == 6 and (today - day).days < 7 * self.keep_weeks):
                continue
            shutil.rmtree(os.path.join(self.root, d), ignore_errors=True)

    def has_today(self) -> bool:
        return os.path.isdir(self._day(dt.date.today()))

    def latest(self) -> float:
        """Modified time of the newest backup folder (0 if none), so a restart does not forget when the last one ran."""
        try:
            return max((os.path.getmtime(os.path.join(self.root, d)) for d in os.listdir(self.root) if not d.endswith(".partial")), default=0.0)
        except OSError:
            return 0.0

    def start(self, check_every: float = 3600.0) -> None:
        if self._thread:
            return
        def loop():
            while True:
                try:
                    if not self.has_today():
                        self.run()
                except Exception:        # noqa: BLE001
                    pass                 # recorded in last_error; retried at the next check
                time.sleep(check_every)
        os.makedirs(self.root, exist_ok=True)
        self._thread = threading.Thread(target=loop, name="backups", daemon=True)
        self._thread.start()

    def status(self) -> dict:
        t = self.last_ok or self.latest()
        return {"last_ok": t or None, "last_error": self.last_error, "files": self.last_files}


def disk(path: str) -> dict:
    u = shutil.disk_usage(path)
    return {"free_gb": round(u.free / 1e9, 1), "total_gb": round(u.total / 1e9, 1), "free_pct": round(100 * u.free / u.total, 1)}


def folder_mb(path: str, suffix: str = ".db") -> float:
    tot = 0
    try:
        for n in os.listdir(path):
            if n.endswith(suffix):
                tot += os.path.getsize(os.path.join(path, n))
    except OSError:
        pass
    return round(tot / 1e6, 1)
