"""Compare api-tennis-derived player tables with a Tennis Insight extract (service file + return file).
Usage: python3 backend/tools/tennis_compare.py --tour ATP --surface all --start 2025-07-01 --stop 2026-07-14 \
         --service FILE31.csv --ret FILE32.csv [--matches FILE30.csv]"""
import argparse, csv, os, sqlite3, sys, statistics as st
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.tennis import tables

ap = argparse.ArgumentParser()
ap.add_argument("--tour", default="ATP"); ap.add_argument("--surface", default="all")
ap.add_argument("--start"); ap.add_argument("--stop")
ap.add_argument("--service", required=True); ap.add_argument("--ret", required=True)
ap.add_argument("--db", default="/opt/autobets/data/tennis.db"); ap.add_argument("--min", type=int, default=8)
a = ap.parse_args()
rows, used, skipped = tables.build(sqlite3.connect(a.db), a.tour, None if a.surface == "all" else a.surface, a.start, a.stop)
print(f"api-tennis: {used} matches used, {skipped} skipped (no stats), {len(rows)} players")
ti = {}
for fn, cols in ((a.service, {"Service Pts W %": "service_pts", "Service hold %": "hold", "BP save %": "bp_save", "1st Serve W %": "first_w", "2nd Serve W %": "second_w", "1st Serve %": "first_serve_in"}),
                 (a.ret, {"Return Pts W %": "return_pts", "Opponent Hold %": "opp_hold", "BP W %": "bp_conv"})):
    for r in csv.DictReader(open(fn, encoding="utf-8-sig")):
        d = ti.setdefault(r["Player"], {"matches": float(r["Match Stat Matches"])})
        for c, k in cols.items():
            try: d[k] = float(r[c])
            except (KeyError, ValueError): pass
by_name = {r["name"]: r for r in rows.values()}
pairs, unmatched = [], []
for full, d in ti.items():
    best = None
    for api, r in by_name.items():
        if tables.match_name(api, [full]) == full: best = r if best is None else "dup"
    if best in (None, "dup"): unmatched.append(full); continue
    pairs.append((full, d, best))
print(f"matched {len(pairs)} of {len(ti)} Tennis Insight players; unmatched {len(unmatched)}: {unmatched[:8]}")
big = [p for p in pairs if p[1]["matches"] >= a.min and p[2]["matches"] >= a.min]
print(f"\nPlayers with >= {a.min} matches in both: {len(big)}")
print(f"{'metric':16s} {'mean diff':>9s} {'mean |diff|':>11s} {'corr':>6s}   (api-tennis minus Tennis Insight, % points)")
for k in ("service_pts", "return_pts", "hold", "opp_hold", "bp_save", "bp_conv", "first_serve_in"):
    x = [(p[2][k], p[1][k]) for p in big if p[2].get(k) is not None and p[1].get(k) is not None]
    if len(x) < 5: continue
    d = [u - v for u, v in x]
    c = st.correlation([u for u, _ in x], [v for _, v in x]) if len(x) > 2 else float("nan")
    print(f"{k:16s} {st.mean(d):9.2f} {st.mean(abs(v) for v in d):11.2f} {c:6.2f}")
print("\nLargest differences (service_pts):")
for full, d, r in sorted(big, key=lambda p: -abs(p[2]["service_pts"] - p[1].get("service_pts", 0)))[:6]:
    print(f"  {full:24s} TI {d.get('service_pts')} ({d['matches']:.0f}m)  API {r['service_pts']} ({r['matches']}m)")
