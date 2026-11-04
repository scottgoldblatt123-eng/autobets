"""Backtest of tennis model v1 (workbook) and v2 (point model) against actual results, no market prices needed.
Walk forward day by day: price each finished ATP/WTA(+Challenger by gender) singles match using only the previous 365 days, then add it.
Reports accuracy, Brier score and log loss against a 50/50 baseline, plus v2 calibration buckets.
Usage: python3 backend/tools/tennis_model_backtest.py [--db /opt/autobets/data/tennis_api.db] [--since 2025-11-01]"""
import argparse, collections, datetime as dt, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.tennis import model, model2, model3, tables
from autobets.tennis.livestore import TennisStore
from autobets.tennis.matching import tour_group

WINDOW, MIN_M = 365, 5
SLAMS = ("australian open", "french open", "roland garros", "wimbledon", "us open")


def run(store, since: str, window: int = WINDOW):
    with store.lock:
        alldays = [d for (d,) in store.db.execute("SELECT DISTINCT day FROM matches WHERE status='Finished' ORDER BY day")]

    def day_rows(day):                                       # one day at a time: the raw JSON is large, never hold the whole history
        with store.lock:
            return [(tour_group(t), r) for t, r in store.db.execute("SELECT type, raw FROM matches WHERE status='Finished' AND day=?", (day,)) if tour_group(t)]
    acc = {"ATP": collections.defaultdict(lambda: collections.defaultdict(float)), "WTA": collections.defaultdict(lambda: collections.defaultdict(float))}
    names, history, results = {}, collections.deque(), []
    elo, played = collections.defaultdict(lambda: 1500.0), collections.defaultdict(int)
    for day in alldays:
        d0 = dt.date.fromisoformat(day)
        while history and (d0 - history[0][0]).days > window:          # roll the window forward
            _, t, contrib = history.popleft()
            for pk, c in contrib.items():
                for k, v in c.items(): acc[t][pk][k] -= v
        rows = {}
        if day >= since:
            for t in ("ATP", "WTA"):
                n = 0; tot = collections.defaultdict(float)
                rows[t] = {}
                for pk, r in acc[t].items():
                    if r["n"] >= 1 and r["svc_t"] and r["ret_t"] and r["hold_t"] and r["oh_t"]:
                        rows[t][pk] = {"matches": r["n"], "service_pts": 100 * r["svc_w"] / r["svc_t"], "return_pts": 100 * r["ret_w"] / r["ret_t"],
                                       "hold": 100 * r["hold_w"] / r["hold_t"], "opp_hold": 100 * r["oh_w"] / r["oh_t"]}
        todays = []
        for t, r in day_rows(day):
            p = tables.parse_match(r)
            if not p:
                continue
            m = json.loads(r); (a, pa), (b, pb) = p.items()
            if m.get("event_winner") not in ("First Player", "Second Player"):
                continue
            first_won = 1 if m["event_winner"] == "First Player" else 0
            todays.append((t, a, b, p, first_won, m))
            if day >= since and len(rows.get(t, {})) >= 20:
                ra, rb = rows[t].get(a), rows[t].get(b)
                if ra and rb and ra["matches"] >= MIN_M and rb["matches"] >= MIN_M:
                    n = len(rows[t]); avg = {k: sum(x[k] for x in rows[t].values()) / n for k in ("service_pts", "return_pts", "opp_hold")}
                    bo = 5 if t == "ATP" and any(s in (m.get("tournament_name") or "").lower() for s in SLAMS) else 3
                    v2 = model2.price(ra, rb, avg, bo)["p_a"] / 100
                    v1 = model.price(ra, rb, model.Averages(avg["return_pts"], avg["opp_hold"]))["p_a"] / 100
                    pe = 1 / (1 + 10 ** ((elo[b] - elo[a]) / 400))
                    results.append((t, v1, v2, first_won, pe))
        with store.lock:
            basics = store.db.execute("SELECT type, p1_key, p2_key, winner FROM matches WHERE status='Finished' AND day=?", (day,)).fetchall()
        updates = []
        for typ, k1, k2, w in basics:                                      # Elo over every finished tour-level match, priced before the day's updates
            if tour_group(typ) and w in ("First Player", "Second Player") and k1 and k2:
                updates.append((str(k1), str(k2), 1.0 if w == "First Player" else 0.0))
        for k1, k2, r in updates:
            e = 1 / (1 + 10 ** ((elo[k2] - elo[k1]) / 400))
            for k, sign in ((k1, 1), (k2, -1)):
                kf = 250 / (played[k] + 5) ** 0.4
                elo[k] += sign * kf * (r - e)
            played[k1] += 1; played[k2] += 1
        for t, a, b, p, fw, m in todays:                                  # add the day's matches after pricing them
            contrib = {}
            for me, opp in ((a, b), (b, a)):
                mp, op = p[me], p[opp]
                c = {"n": 1, "svc_w": mp["svc"][0], "svc_t": mp["svc"][1], "ret_w": mp["ret"][0], "ret_t": mp["ret"][1],
                     "hold_w": mp["hold"][0], "hold_t": mp["hold"][1], "oh_w": op["hold"][0], "oh_t": op["hold"][1]}
                contrib[me] = c
                for k, v in c.items(): acc[t][me][k] += v
            history.append((dt.date.fromisoformat(day), t, contrib))
    return results


blend = model3.blend


def score(rows, idx):
    n = len(rows); eps = 0.01
    clip = lambda p: min(1 - eps, max(eps, p))
    acc = sum(1 for r in rows if (r[idx] > 0.5) == bool(r[3])) / n
    brier = sum((r[idx] - r[3]) ** 2 for r in rows) / n
    ll = -sum(math.log(clip(r[idx]) if r[3] else 1 - clip(r[idx])) for r in rows) / n
    return acc, brier, ll


def report(results):
    out = []
    for label, sel in (("ALL", lambda r: True), ("WTA", lambda r: r[0] == "WTA"), ("ATP", lambda r: r[0] == "ATP")):
        rows = [r for r in results if sel(r)]
        if not rows:
            continue
        out.append(f"\n{label}: {len(rows)} matches   (50/50 baseline: accuracy 50.0%, Brier 0.2500, log loss 0.6931)")
        for name, i in (("v1 workbook", 1), ("v2 point model", 2), ("Elo rating", 4)):
            a, b, l = score(rows, i); out.append(f"  {name:15s} accuracy {100 * a:5.1f}%   Brier {b:.4f}   log loss {l:.4f}")
        for w in (0.3, 0.5, 0.7):
            bl = [(r[0], r[1], r[2], r[3], blend(r[2], r[4], w)) for r in rows]
            a, b, l = score(bl, 4); out.append(f"  v3 blend {int(w * 100)}% v2 / {int((1 - w) * 100)}% Elo accuracy {100 * a:5.1f}%   Brier {b:.4f}   log loss {l:.4f}")
    rows = results
    if rows:
        out.append("\nv2 calibration (predicted win chance for the first-listed player -> actual):")
        for lo in range(0, 100, 10):
            b = [r for r in rows if lo <= 100 * r[2] < lo + 10]
            if b: out.append(f"  {lo:3d}-{lo + 10:3d}%  n={len(b):5d}  predicted {100 * sum(r[2] for r in b) / len(b):5.1f}%  actual {100 * sum(r[3] for r in b) / len(b):5.1f}%")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default="/opt/autobets/data/tennis_api.db"); ap.add_argument("--since", default="2025-11-01")
    a = ap.parse_args()
    print(report(run(TennisStore(a.db), a.since)))
