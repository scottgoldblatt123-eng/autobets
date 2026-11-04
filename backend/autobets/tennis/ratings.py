"""Player rate tables from the live store (tennis_api.db) and the v1/v2 model prices built on them.
Only matches before the given day are used (no look-ahead); all surfaces, last 365 days, same tour."""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from . import model, model2, tables

MIN_MATCHES = 5


def build(store, tour: str, day: str, days: int = 365) -> dict:
    """-> {player_key(str): {name, matches, service_pts, return_pts, hold, opp_hold}} (percentages)."""
    start = (dt.date.fromisoformat(day) - dt.timedelta(days=days)).isoformat()
    with store.lock:
        rows = store.db.execute("SELECT raw FROM matches WHERE status='Finished' AND day>=? AND day<? AND type LIKE ?",
                                (start, day, f"%{tour.lower()}%singles%")).fetchall()
    acc, names = defaultdict(lambda: defaultdict(int)), {}
    for (raw,) in rows:
        p = tables.parse_match(raw)
        if not p:
            continue
        (a, pa), (b, pb) = p.items()
        for me, opp in ((a, b), (b, a)):
            mp, op = p[me], p[opp]; names[me] = mp["name"]; r = acc[me]
            r["n"] += 1
            for k in ("svc", "ret", "hold"):
                r[k + "_w"] += mp[k][0]; r[k + "_t"] += mp[k][1]
            r["oh_w"] += op["hold"][0]; r["oh_t"] += op["hold"][1]
    out = {}
    for pk, r in acc.items():
        if r["svc_t"] and r["ret_t"] and r["hold_t"] and r["oh_t"]:
            out[pk] = {"name": names[pk], "matches": r["n"], "service_pts": 100 * r["svc_w"] / r["svc_t"], "return_pts": 100 * r["ret_w"] / r["ret_t"],
                       "hold": 100 * r["hold_w"] / r["hold_t"], "opp_hold": 100 * r["oh_w"] / r["oh_t"]}
    return out


def price(rows: dict, key_a, key_b, best_of: int = 3) -> dict | None:
    """Price a v-b match from the tables. None unless both players have MIN_MATCHES matches."""
    a, b = rows.get(str(key_a)), rows.get(str(key_b))
    if not a or not b or a["matches"] < MIN_MATCHES or b["matches"] < MIN_MATCHES or len(rows) < 20:
        return None
    n = len(rows)
    avg = {k: sum(r[k] for r in rows.values()) / n for k in ("service_pts", "return_pts")}
    v2 = model2.price(a, b, avg, best_of)
    v1 = model.price(a, b, model.Averages(avg["return_pts"], sum(r["opp_hold"] for r in rows.values()) / n))
    return {"v1": {k: v1[k] for k in ("p_a", "p_b", "odds_a", "odds_b", "version")}, "v2": {k: v2[k] for k in ("p_a", "p_b", "odds_a", "odds_b", "version")},
            "matches": [a["matches"], b["matches"]], "players_in_table": n}
