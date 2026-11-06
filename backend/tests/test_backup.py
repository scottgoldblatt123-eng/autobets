import datetime as dt
import gzip
import os
import sqlite3

from autobets import health
from autobets.backup import Backups, disk


def _data(tmp_path):
    d = tmp_path / "data"; d.mkdir()
    con = sqlite3.connect(d / "journal.db"); con.execute("create table t(x)"); con.execute("insert into t values (42)"); con.commit(); con.close()
    (d / "state.json").write_text('{"ok": true}')
    (d / "notes.txt").write_text("ignored")
    return d


def test_backup_copies_databases_and_state_and_is_restorable(tmp_path):
    d = _data(tmp_path)
    b = Backups(str(d)); b.root = str(d / "backups"); os.makedirs(b.root)
    assert b.run(dt.date(2026, 11, 6)) == 2
    day = d / "backups" / "2026-11-06"
    assert sorted(os.listdir(day)) == ["journal.db.gz", "state.json.gz"]
    restored = tmp_path / "r.db"; restored.write_bytes(gzip.open(day / "journal.db.gz").read())
    assert sqlite3.connect(restored).execute("select x from t").fetchone() == (42,)
    assert b.status()["last_ok"] and not b.status()["last_error"]


def test_prune_keeps_seven_days_and_recent_sundays(tmp_path):
    d = _data(tmp_path)
    b = Backups(str(d)); os.makedirs(b.root)
    start = dt.date(2026, 10, 1)
    for i in range(36):
        b.run(start + dt.timedelta(days=i))
    left = sorted(os.listdir(b.root))
    today = start + dt.timedelta(days=35)
    assert all((today - dt.date.fromisoformat(x)).days < 7 or dt.date.fromisoformat(x).weekday() == 6 for x in left)
    assert len([x for x in left if (today - dt.date.fromisoformat(x)).days < 7]) == 7 and len(left) <= 7 + 4


def test_failed_backup_records_error_and_leaves_previous(tmp_path):
    d = _data(tmp_path)
    b = Backups(str(d)); os.makedirs(b.root)
    b.run(dt.date(2026, 11, 5))
    (d / "bad.db").write_text("this is not a database")
    try:
        b.run(dt.date(2026, 11, 6))
        assert False
    except Exception:
        pass
    assert b.status()["last_error"] and os.path.isdir(d / "backups" / "2026-11-05") and not os.path.isdir(d / "backups" / "2026-11-06")


def test_health_reports_disk_and_backup_age():
    class E:
        def feed_health(self): return {"ok": True, "detail": "ok"}
    import time
    ok = health.build(E(), None, None, None, True, {}, {"disk": {"free_gb": 40, "total_gb": 80, "free_pct": 50}, "backup": {"last_ok": time.time() - 3600, "last_error": ""}, "db_mb": 120})
    assert {i["key"]: i["level"] for i in ok["items"]}["disk"] == "ok" and {i["key"]: i["level"] for i in ok["items"]}["backup"] == "ok"
    bad = health.build(E(), None, None, None, True, {}, {"disk": {"free_gb": 3, "total_gb": 80, "free_pct": 4}, "backup": {"last_ok": time.time() - 3 * 86400, "last_error": "x"}, "db_mb": 120})
    lv = {i["key"]: i["level"] for i in bad["items"]}
    assert lv["disk"] == "bad" and lv["backup"] == "bad" and bad["issues"] >= 2
    assert disk("/")["total_gb"] > 0
