"""Numbers behind the Analyse screens, computed from the ledger, the recommendations and the price log."""
from __future__ import annotations

import json
import time
from collections import defaultdict

from .ai.snapshot import _model_odds


def performance(ledger, recs, ai_cost_gbp: float, days: int, now: float | None = None) -> dict:
    """The last `days` days against the `days` before them."""
    now = now or time.time()
    span = days * 86400
    out = performance_between(ledger, recs, ai_cost_gbp, now - span, now, now - 2 * span, now - span)
    return {**out, "days": days}


def performance_between(ledger, recs, ai_cost_gbp: float, start: float, end: float, cstart: float | None = None, cend: float | None = None) -> dict:
    """Settled results in [start, end), optionally against a comparison window [cstart, cend). The comparison curve is shifted onto the main period so they overlay."""
    cur = ledger.window(start, end)
    comp = ledger.window(cstart, cend) if cstart is not None and cend is not None else []
    has_cmp = cstart is not None and cend is not None

    def stats(rows):
        n = len(rows)
        wins = sum(1 for e in rows if e["result"] > 0)
        return {"net": round(sum(e["result"] for e in rows), 2), "trades": n, "win_rate": round(100 * wins / n, 1) if n else None}
    c, p = stats(cur), stats(comp)
    cum, curve = 0.0, []
    for e in sorted(cur, key=lambda e: e["t"]):
        cum += e["result"]
        curve.append({"t": e["t"], "v": round(cum, 2)})
    pcum, pcurve = 0.0, []
    shift = (start - cstart) if has_cmp else 0
    for e in sorted(comp, key=lambda e: e["t"]):
        pcum += e["result"]
        pcurve.append({"t": e["t"] + shift, "v": round(pcum, 2)})

    def split(rows):
        by: dict[str, dict] = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0})
        for e in rows:
            for name, v in (e.get("parts") or {"Unattributed (before tracking)": e["result"]}).items():
                b = by[name]
                b["trades"] += 1
                b["pnl"] += v
                b["wins"] += 1 if v > 0 else 0
        return by
    by, pby = split(cur), split(comp)
    names = set(by) | (set(pby) if has_cmp else set())
    z = {"trades": 0, "pnl": 0.0, "wins": 0}
    strategies = sorted(({"name": k, "trades": by.get(k, z)["trades"], "pnl": round(by.get(k, z)["pnl"], 2),
                          "win_rate": round(100 * by[k]["wins"] / by[k]["trades"], 1) if k in by else 0,
                          **({"prev_trades": pby.get(k, z)["trades"], "prev_pnl": round(pby.get(k, z)["pnl"], 2)} if has_cmp else {})} for k in names), key=lambda x: -x["pnl"])
    st = recs.stats(start)
    return {"days": max(1, round((end - start) / 86400)), "compare": has_cmp, "start": start, "end": end, "current": c, "previous": p, "clv": st["avg_clv_pts"], "clv_n": st["evidence"],
            "costs": round(ai_cost_gbp, 2), "curve": curve, "prev_curve": pcurve, "strategies": strategies}


def models(store, since_days: int = 90) -> dict:
    """Model against market on recorded matches: for each finished market, the last price before the off versus the model's own probabilities."""
    if store is None:
        return {"available": False, "reason": "The Betfair price log is not running."}
    since = time.time() - since_days * 86400
    with store.lock:
        rows = store.db.execute("""SELECT t.market_id, t.sport, t.prices, t.ctx, r.winner, n.names FROM ticks t JOIN results r ON r.market_id=t.market_id
                                   LEFT JOIN runners n ON n.market_id=t.market_id WHERE t.in_play=0 AND t.t>=? ORDER BY t.market_id, t.t""", (since,)).fetchall()
    last: dict[str, tuple] = {}
    for mid, sport, prices, ctx, winner, names in rows:
        if ctx:
            last[mid] = (sport, json.loads(prices), json.loads(ctx), winner, json.loads(names or "{}"))      # keeps overwriting: ends as the last pre-play tick that had a model
    agg: dict[str, dict] = defaultdict(lambda: {"n": 0, "model_brier": 0.0, "market_brier": 0.0, "model_right": 0, "market_right": 0})
    for mid, (sport, prices, ctx, winner, names) in last.items():
        fair = _model_odds(ctx, names)
        if not fair or winner not in fair or any(not (prices.get(s) and prices[s][0] and prices[s][1]) for s in fair):
            continue
        mp = {s: 1 / fair[s] for s in fair}
        z = sum(mp.values())
        mp = {s: v / z for s, v in mp.items()}
        kp = {s: 2 / (prices[s][0] + prices[s][1]) for s in fair}
        z = sum(kp.values())
        kp = {s: v / z for s, v in kp.items()}
        a = agg[sport]
        a["n"] += 1
        a["model_brier"] += sum((mp[s] - (1 if s == winner else 0)) ** 2 for s in fair)
        a["market_brier"] += sum((kp[s] - (1 if s == winner else 0)) ** 2 for s in fair)
        a["model_right"] += 1 if max(mp, key=mp.get) == winner else 0
        a["market_right"] += 1 if max(kp, key=kp.get) == winner else 0
    live = {sp: {"matches": a["n"], "model_brier": round(a["model_brier"] / a["n"], 4), "market_brier": round(a["market_brier"] / a["n"], 4),
                 "model_accuracy": round(100 * a["model_right"] / a["n"], 1), "market_accuracy": round(100 * a["market_right"] / a["n"], 1)} for sp, a in agg.items() if a["n"]}
    return {"available": True, "live": live, "offline": OFFLINE}


# Results of the offline backtests run on the collected match history (see tools/). They test the models on results only, not against market prices.
OFFLINE = [
    {"sport": "Tennis", "name": "v1 (spreadsheet port)", "matches": 18579, "accuracy": 57.9, "brier": 0.2407, "note": "since 2025-11-01, walk-forward"},
    {"sport": "Tennis", "name": "v2 (point-by-point Markov)", "matches": 18579, "accuracy": 59.9, "brier": 0.2355, "note": "overconfident at the extremes"},
    {"sport": "Tennis", "name": "Elo", "matches": 18579, "accuracy": 62.9, "brier": 0.2253, "note": ""},
    {"sport": "Tennis", "name": "v3 (Elo blended with v2) — in use", "matches": 18579, "accuracy": 63.1, "brier": 0.2249, "note": "bookmakers and the exchange typically sit near 68–70%"},
    {"sport": "Football", "name": "Goals model, 1X2 — in use", "matches": 3074, "accuracy": 49.7, "brier": 0.6093, "note": "league-average baseline: 43.9% / 0.6490 (three-outcome Brier)"},
]


def ai_learning(recs) -> dict:
    items = list(recs.items.values())
    reasons: dict[str, int] = defaultdict(int)
    for r in items:
        if r["status"] == "dismissed" and r.get("dismiss_reason"):
            reasons[r["dismiss_reason"].strip().lower()] += 1
    by_conf: dict[str, list] = defaultdict(list)
    for r in items:
        if r["kind"] == "trade" and r["clv"] is not None:
            by_conf[r["confidence"]].append(r["clv"])
    st = recs.stats()
    return {"stats": st, "dismiss_reasons": sorted(({"reason": k, "n": v} for k, v in reasons.items()), key=lambda x: -x["n"])[:10],
            "clv_by_confidence": {k: {"n": len(v), "avg_clv_pts": round(100 * sum(v) / len(v), 2)} for k, v in by_conf.items()},
            "ideas": len([r for r in items if r["kind"] == "trade"])}
