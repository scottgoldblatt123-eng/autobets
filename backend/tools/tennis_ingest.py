"""Pull finished ATP / WTA / Challenger singles matches from api-tennis into the raw store.
Usage (on the server): python3 backend/tools/tennis_ingest.py --start 2025-07-01 --stop 2026-07-31
Resumable: re-running skips nothing but is idempotent (INSERT OR REPLACE). Prints counts, never keys."""
import argparse, datetime as dt, os, sys, time
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tennis_trial import get, load, SECRETS
from autobets.tennis import store

DB = "/opt/autobets/data/tennis.db"


def surface_map(key):
    r, _ = get("get_tournaments", key)
    out = {}
    for t in r.get("result") or []:
        s = t.get("tournament_surface") or t.get("surface") or t.get("court")
        out[str(t.get("tournament_key"))] = s
    return out, r.get("result") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True); ap.add_argument("--stop", required=True)
    ap.add_argument("--chunk", type=int, default=7); ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.db), exist_ok=True)
    key = load(SECRETS + "tennis_api_key.env")["TENNIS_API_KEY"]
    db = store.connect(a.db)
    surf, tl = surface_map(key)
    print(f"tournaments: {len(tl)}, with surface: {sum(1 for v in surf.values() if v)}")
    print("tournament fields:", sorted(tl[0].keys()) if tl else "-")
    d, end, tot, kept = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.stop), 0, 0
    while d <= end:
        e = min(d + dt.timedelta(days=a.chunk - 1), end)
        try:
            fx, ms = get("get_fixtures", key, date_start=d.isoformat(), date_stop=e.isoformat())
            rows = [r for r in (fx.get("result") or []) if r.get("event_status") == "Finished"]
            k = sum(store.upsert_match(db, r, surf) for r in rows)
            db.commit(); tot += len(rows); kept += k
            print(f"{d}..{e}: finished={len(rows)} kept={k} [{ms:.0f} ms]", flush=True)
        except Exception as ex:
            print(f"{d}..{e}: {type(ex).__name__}: {str(ex)[:120]}", flush=True)
        d = e + dt.timedelta(days=1); time.sleep(0.3)
    for tour, n, st, pb in db.execute("SELECT tour,count(*),sum(has_stats),sum(has_pbp) FROM matches GROUP BY tour"):
        print(f"store {tour}: {n} matches, {st} with statistics, {pb} with point-by-point")
    print("INGEST-COMPLETE")


main()
