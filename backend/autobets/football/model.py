"""Football goals model v1 ('poisson'): team attack/defence strengths from stored results -> scoreline grid -> prices.

For a league, over the last DAYS days of finished matches before the kick-off (no look-ahead), time-decayed:
  home_goals ~ Poisson(mu_h), away_goals ~ Poisson(mu_a)
  mu_h = league_home_avg * att_home_team * def_away_team,  mu_a = league_away_avg * att_away_team * def_home_team
Strengths are shrunk toward 1 (SHRINK pseudo-games). A Dixon-Coles style low-score correction (RHO) adjusts 0-0, 1-0, 0-1, 1-1.
Output: home/draw/away, over/under lines, both teams to score, top correct scores. Recommendation-only."""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

VERSION = "fb-v1-poisson"
DAYS, HALF_LIFE, SHRINK, RHO, MIN_GAMES, MAXG = 730, 270.0, 6.0, -0.05, 8, 10
TOT_W = 0.0        # weight pulling a match's expected total goals toward the league average (keeps the home/away ratio); tuned by tools/football_model_tune.py


def strengths(db, lock, league_id: int, kickoff: str):
    k0 = dt.datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    lo = (k0 - dt.timedelta(days=DAYS)).isoformat()
    with lock:
        rows = db.execute("SELECT kickoff, home_id, away_id, goals_h, goals_a FROM fixtures WHERE league_id=? AND status IN ('FT','AET','PEN') "
                          "AND goals_h IS NOT NULL AND kickoff>=? AND kickoff<?", (league_id, lo, k0.isoformat())).fetchall()
    if len(rows) < 100:
        return None
    w_tot = hg = ag = 0.0
    gf, ga, wt = defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0])   # [home, away] splits
    for ko, h, a, gh, gaw in rows:
        age = (k0 - dt.datetime.fromisoformat(ko.replace("Z", "+00:00"))).days
        w = 0.5 ** (age / HALF_LIFE)
        w_tot += w; hg += w * gh; ag += w * gaw
        gf[h][0] += w * gh; ga[h][0] += w * gaw; wt[h][0] += w
        gf[a][1] += w * gaw; ga[a][1] += w * gh; wt[a][1] += w
    lh, la = hg / w_tot, ag / w_tot
    return {"lh": lh, "la": la, "gf": gf, "ga": ga, "wt": wt, "n": len(rows)}


def _poisson(mu: float):
    return [math.exp(-mu) * mu ** k / math.factorial(k) for k in range(MAXG + 1)]


def _tau(i, j, mh, ma):
    if i == 0 and j == 0: return 1 - mh * ma * RHO
    if i == 0 and j == 1: return 1 + mh * RHO
    if i == 1 and j == 0: return 1 + ma * RHO
    if i == 1 and j == 1: return 1 - RHO
    return 1.0


def grid(mh: float, ma: float):
    ph, pa = _poisson(mh), _poisson(ma)
    g = [[ph[i] * pa[j] * _tau(i, j, mh, ma) for j in range(MAXG + 1)] for i in range(MAXG + 1)]
    z = sum(map(sum, g))
    return [[x / z for x in row] for row in g]


def expected_goals(st: dict, home_id: int, away_id: int):
    """-> (mu_home, mu_away, games_home, games_away) or None if either team has too few games."""
    def rate(team, side, scored, league):
        s = st["gf" if scored else "ga"][team][side]; w = st["wt"][team][side]
        return (s + SHRINK * league) / (w + SHRINK), w
    # attack: goals scored per game at that venue, relative to the league venue average; defence: goals conceded
    ah, wh = rate(home_id, 0, True, st["lh"]);  dh, _ = rate(home_id, 0, False, st["la"])
    aa, wa = rate(away_id, 1, True, st["la"]);  da, _ = rate(away_id, 1, False, st["lh"])
    if wh < MIN_GAMES * 0.3 or wa < MIN_GAMES * 0.3:
        return None
    mh = st["lh"] * (ah / st["lh"]) * (da / st["lh"])
    ma = st["la"] * (aa / st["la"]) * (dh / st["la"])
    if TOT_W:
        t, t0 = mh + ma, st["lh"] + st["la"]
        k = ((1 - TOT_W) * t + TOT_W * t0) / t
        mh, ma = mh * k, ma * k
    return mh, ma, wh, wa


def price(mh: float, ma: float) -> dict:
    g = grid(mh, ma)
    n = len(g)
    home = sum(g[i][j] for i in range(n) for j in range(n) if i > j); draw = sum(g[i][i] for i in range(n)); away = 1 - home - draw
    out = {"home": home, "draw": draw, "away": away, "mu": [mh, ma], "version": VERSION}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        over = sum(g[i][j] for i in range(n) for j in range(n) if i + j > line)
        out[f"over_{line}"] = over
    out["btts"] = sum(g[i][j] for i in range(1, n) for j in range(1, n))
    out["correct"] = sorted(((f"{i}-{j}", g[i][j]) for i in range(6) for j in range(6)), key=lambda x: -x[1])[:6]
    return out


def predict(db, lock, league_id: int, kickoff: str, home_id: int, away_id: int):
    st = strengths(db, lock, league_id, kickoff)
    if not st:
        return None
    xg = expected_goals(st, home_id, away_id)
    if not xg:
        return None
    r = price(xg[0], xg[1]); r["games"] = [round(xg[2]), round(xg[3])]
    return r
