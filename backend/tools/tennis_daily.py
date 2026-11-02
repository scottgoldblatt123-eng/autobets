"""Daily refresh: pull the last few days of finished matches, then snapshot rolling-12-month player tables
(ATP and WTA; main draw, no team events; all surfaces + each surface) into player_tables.
Usage: python3 backend/tools/tennis_daily.py [--days 4]. Intended for cron (see deploy/)."""
import argparse, datetime as dt, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tennis_trial import load, SECRETS
from tennis_ingest import ingest, DB
from autobets.tennis import store, tables


def snapshot(db, asof):
    store.ensure_tables_snapshot(db)
    start = (asof - dt.timedelta(days=365)).isoformat(); stop = asof.isoformat(); n = 0
    for tour in ("ATP", "WTA"):
        for surf in (None, "hard", "clay", "grass"):
            rows, used, _ = tables.build(db, tour, surf, start, stop, main_draw=True, no_cups=True)
            for pk, r in rows.items():
                db.execute("INSERT OR REPLACE INTO player_tables VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                           (stop, tour, surf or "all", pk, r["name"], r["matches"], r["service_pts"], r["return_pts"],
                            r["hold"], r["opp_hold"], r["bp_save"], r["bp_conv"])); n += 1
    db.commit()
    return n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=4); ap.add_argument("--db", default=DB); a = ap.parse_args()
    key = load(SECRETS + "tennis_api_key.env")["TENNIS_API_KEY"]
    db = store.connect(a.db); today = dt.date.today()
    kept = ingest(key, db, (today - dt.timedelta(days=a.days)).isoformat(), today.isoformat(), quiet=True)
    n = snapshot(db, today)
    print(f"{dt.datetime.now().isoformat(timespec='seconds')} ingested {kept} matches; snapshot rows {n}")


if __name__ == "__main__":
    main()
