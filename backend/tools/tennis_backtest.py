"""Model vs market. For each logged Betfair tennis market that can be matched to a finished match in the store:
  - price the match with model v1 from player tables built ONLY from matches before that match (no look-ahead),
  - take the last logged price before the scheduled start as the market view (mid of best back/lay, de-margined),
  - compare Brier score and log loss of model and market against the actual result.
Usage: python3 backend/tools/tennis_backtest.py [--fallback] [--min 5]"""
import argparse, collections, datetime as dt, json, math, os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.tennis import matching, model, tables

TENNIS, PRICES = "/opt/autobets/data/tennis.db", "/opt/autobets/data/betfair_prices.db"


def market_prob(pdb, market_id, start, selections):
    """De-margined probability per selection from the last record before start."""
    rows = pdb.execute("SELECT selection, back, lay, t FROM prices WHERE market_id=? AND t<=? ORDER BY t DESC", (market_id, start)).fetchall()
    last = {}
    for sel, back, lay, t in rows:
        if sel in selections and sel not in last and back and lay:
            last[sel] = (back + lay) / 2
    if len(last) != 2:
        return None
    inv = {k: 1 / v for k, v in last.items()}; z = sum(inv.values())
    return {k: v / z for k, v in inv.items()}


def table_for(cache, tdb, tour, surface, day, fallback):
    k = (tour, surface, day)
    if k not in cache:
        rows, _, _ = tables.build(tdb, tour, surface, (dt.date.fromisoformat(day) - dt.timedelta(days=365)).isoformat(),
                                  (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(), main_draw=True, no_cups=True)
        cache[k] = (rows, model.tour_averages(rows) if rows else None)
    return cache[k]


def find_player(rows, name):
    hits = [r for r in rows.values() if matching.same_player(r["name"], name)]
    return hits[0] if len(hits) == 1 else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fallback", action="store_true", help="use all-surface table when the surface table lacks a player")
    ap.add_argument("--min", type=int, default=5, help="minimum matches per player in the table"); ap.add_argument("--tennis-db", default=TENNIS); ap.add_argument("--prices-db", default=PRICES)
    a = ap.parse_args()
    tdb, pdb = sqlite3.connect(a.tennis_db), sqlite3.connect(a.prices_db)
    finished = collections.defaultdict(list)
    for raw, date, tour, surf in tdb.execute("SELECT raw,date,tour,surface FROM matches WHERE status='Finished' AND tour IN ('ATP','WTA')"):
        m = json.loads(raw); finished[date].append((m, tour, surf))
    cache, out, skip = {}, [], collections.Counter()
    for mid, event, start, runners in pdb.execute("SELECT market_id,event,start,runners FROM markets"):
        names = matching.split_event(event or "")
        if not names: skip["not singles"] += 1; continue
        d0 = dt.datetime.fromisoformat(start.replace("Z", "")).date()
        found = None
        for off in (0, -1, 1):
            for m, tour, surf in finished.get((d0 + dt.timedelta(days=off)).isoformat(), []):
                f, s = m["event_first_player"], m["event_second_player"]
                if matching.same_player(f, names[0]) and matching.same_player(s, names[1]): found = (m, tour, surf, False)
                elif matching.same_player(f, names[1]) and matching.same_player(s, names[0]): found = (m, tour, surf, True)
        if not found: skip["no finished match (yet)"] += 1; continue
        m, tour, surf, swapped = found
        winner = m.get("event_winner")
        if winner not in ("First Player", "Second Player"): skip["no winner"] += 1; continue
        sel = eval(runners)
        # map Betfair selection ids to the two named players
        by_name = {}
        for k, nm in sel.items():
            for i, n in enumerate(names):
                if nm.lower() == n.lower(): by_name[i] = k
        if len(by_name) != 2: skip["runner names"] += 1; continue
        mp = market_prob(pdb, mid, start.replace("Z", ""), set(by_name.values()))
        if not mp: skip["no price before start"] += 1; continue
        sfk = next((k for k, v in tables.SURFACES.items() if surf in v), None)
        day = m["event_date"]; rows, avg = table_for(cache, tdb, tour, sfk, day, a.fallback)
        p0, p1 = (find_player(rows, m["event_first_player"]) if rows else None), (find_player(rows, m["event_second_player"]) if rows else None)
        if (not p0 or not p1 or p0["matches"] < a.min or p1["matches"] < a.min) and a.fallback:
            rows, avg = table_for(cache, tdb, tour, None, day, a.fallback)
            p0, p1 = (find_player(rows, m["event_first_player"]) if rows else None), (find_player(rows, m["event_second_player"]) if rows else None)
        if not p0 or not p1 or p0["matches"] < a.min or p1["matches"] < a.min: skip["player not in table / too few matches"] += 1; continue
        pr = model.price(p0, p1, avg)
        first_won = 1 if winner == "First Player" else 0
        mk_first = mp[by_name[1 if swapped else 0]]
        out.append((pr["p_a"] / 100, mk_first, first_won, tour, sfk, pr["odds_a"], pr["odds_b"], mp[by_name[0 if swapped else 1]]))
    print(f"markets matched and priced: {len(out)}; skipped: {dict(skip)}")
    if not out: return
    brier = lambda p, y: (p - y) ** 2
    ll = lambda p, y: -math.log(max(min(p if y else 1 - p, 1 - 1e-9), 1e-9))
    n = len(out)
    print(f"{'':10s} {'Brier':>7s} {'LogLoss':>8s}")
    for label, idx in (("model", 0), ("market", 1)):
        print(f"{label:10s} {sum(brier(o[idx], o[2]) for o in out) / n:7.4f} {sum(ll(o[idx], o[2]) for o in out) / n:8.4f}")
    print(f"model favourite wins: {sum(1 for o in out if (o[0] > .5) == bool(o[2])) / n:.1%}; market favourite wins: {sum(1 for o in out if (o[1] > .5) == bool(o[2])) / n:.1%}")
    gap = [o[0] - o[1] for o in out]
    print(f"mean |model - market| probability gap: {sum(abs(g) for g in gap) / n:.3f}")
    print("Calibration of model (bin: predicted vs actual):")
    for lo in (0, .3, .4, .5, .6, .7, .8):
        b = [o for o in out if lo <= o[0] < (lo + .1 if lo >= .3 else .3) or (lo == .8 and o[0] >= .8)]
        if lo == .8: b = [o for o in out if o[0] >= .8]
        if b: print(f"  {lo:.1f}+: n={len(b):4d} predicted {sum(o[0] for o in b) / len(b):.3f} actual {sum(o[2] for o in b) / len(b):.3f}")
    print("NOTE: a few hundred matches are needed before any difference between model and market means much.")


if __name__ == "__main__":
    main()
