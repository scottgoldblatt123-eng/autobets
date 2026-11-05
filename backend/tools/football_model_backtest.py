"""Backtest of the football goals model (fb-v1-poisson) against actual results, walk-forward: every match is priced using only
earlier matches of its league (last 730 days, time-decayed), exactly as the app does.
Reports 1X2 accuracy / Brier (3-way) / log loss, over 2.5 and both-teams-to-score log loss and Brier, against a naive baseline that
always quotes each league's historical home/draw/away, over 2.5 and BTTS rates, plus calibration of the home win chance.
Usage: python3 backend/tools/football_model_backtest.py [--db /opt/autobets/data/football.db] [--since 2025-08-01]"""
import argparse, collections, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.football import model
from autobets.football.store import FootballStore

LEAGUES = {39: "Premier League", 40: "Championship", 78: "Bundesliga", 140: "La Liga", 135: "Serie A", 61: "Ligue 1", 179: "Scottish Premiership"}


def run(store, since: str):
    with store.lock:
        rows = store.db.execute("SELECT league_id, kickoff, home_id, away_id, goals_h, goals_a FROM fixtures WHERE status='FT' AND goals_h IS NOT NULL "
                                "AND league_id IN (%s) ORDER BY kickoff" % ",".join(str(k) for k in LEAGUES)).fetchall()
    base = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])             # per league before `since`: n, home, draw, away, over2.5, btts
    for lg, ko, h, a, gh, ga in rows:
        if ko < since:
            b = base[lg]; b[0] += 1; b[1] += gh > ga; b[2] += gh == ga; b[3] += gh < ga; b[4] += gh + ga > 2; b[5] += gh > 0 and ga > 0
    out = []
    for lg, ko, h, a, gh, ga in rows:
        if ko < since:
            continue
        pr = model.predict(store.db, store.lock, lg, ko, h, a)
        b = base[lg]
        if not pr or b[0] < 100:
            continue
        res = 0 if gh > ga else 1 if gh == ga else 2
        out.append({"league": lg, "res": res, "p": (pr["home"], pr["draw"], pr["away"]), "over": gh + ga > 2, "p_over": pr["over_2.5"],
                    "btts": gh > 0 and ga > 0, "p_btts": pr["btts"], "b": (b[1] / b[0], b[2] / b[0], b[3] / b[0]), "b_over": b[4] / b[0], "b_btts": b[5] / b[0]})
    return out


def _ll(p): return -math.log(min(1 - 1e-6, max(1e-6, p)))


def metrics(rows, key="p", over="p_over", btts="p_btts"):
    n = len(rows)
    acc = sum(1 for r in rows if max(range(3), key=lambda i: r[key][i]) == r["res"]) / n
    brier = sum(sum((r[key][i] - (1 if r["res"] == i else 0)) ** 2 for i in range(3)) for r in rows) / n
    ll = sum(_ll(r[key][r["res"]]) for r in rows) / n
    ob = sum((r[over] - r["over"]) ** 2 for r in rows) / n; oll = sum(_ll(r[over] if r["over"] else 1 - r[over]) for r in rows) / n
    bb = sum((r[btts] - r["btts"]) ** 2 for r in rows) / n; bll = sum(_ll(r[btts] if r["btts"] else 1 - r[btts]) for r in rows) / n
    return acc, brier, ll, ob, oll, bb, bll


def report(rows):
    if not rows:
        return "no matches could be priced"
    out = []
    groups = [("ALL", rows)] + [(LEAGUES[k], [r for r in rows if r["league"] == k]) for k in LEAGUES]
    for label, g in groups:
        if not g:
            continue
        out.append(f"\n{label}: {len(g)} matches")
        for name, args in (("model", {}), ("baseline", {"key": "b", "over": "b_over", "btts": "b_btts"})):
            a, b, l, ob, ol, bb, bl = metrics(g, **args)
            out.append(f"  {name:9s} 1X2 accuracy {100 * a:5.1f}%  Brier {b:.4f}  log loss {l:.4f} | over 2.5 Brier {ob:.4f} ll {ol:.4f} | BTTS Brier {bb:.4f} ll {bl:.4f}")
    out.append("\nHome-win calibration (model chance -> actual):")
    for lo in range(10, 90, 10):
        b = [r for r in rows if lo <= 100 * r["p"][0] < lo + 10]
        if b: out.append(f"  {lo:3d}-{lo + 10:3d}%  n={len(b):5d}  predicted {100 * sum(r['p'][0] for r in b) / len(b):5.1f}%  actual {100 * sum(r['res'] == 0 for r in b) / len(b):5.1f}%")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default="/opt/autobets/data/football.db"); ap.add_argument("--since", default="2025-08-01")
    a = ap.parse_args()
    print(report(run(FootballStore(a.db), a.since)))
