"""Tennis model v3 ('elo-blend'): an Elo rating that updates after every tour-level match, blended 70/30 with the v2 point model
on the log-odds scale. Chosen from the walk-forward backtest (tools/tennis_model_backtest.py): better than v1, v2 or Elo alone.
Recommendation-only."""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict

from .matching import tour_group

VERSION = "v3-elo-blend"
W_V2 = 0.3
_cache: dict = {}
_lock = threading.Lock()


def logit(p: float) -> float:
    p = min(0.99, max(0.01, p))
    return math.log(p / (1 - p))


def blend(p2: float, pe: float, w: float = W_V2) -> float:
    return 1 / (1 + math.exp(-(w * logit(p2) + (1 - w) * logit(pe))))


def expected(ra: float, rb: float) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def update(elo, played, k1: str, k2: str, r: float) -> None:
    e = expected(elo[k1], elo[k2])
    for k, sign in ((k1, 1), (k2, -1)):
        elo[k] += sign * (250 / (played[k] + 5) ** 0.4) * (r - e)
    played[k1] += 1; played[k2] += 1


def ratings(store, before_day: str, ttl: float = 600.0):
    """-> (elo, played) from every finished tour-level singles match before `before_day`. Cached for `ttl` seconds."""
    with _lock:
        hit = _cache.get((id(store), before_day))
        if hit and time.time() - hit[0] < ttl:
            return hit[1], hit[2]
    elo, played = defaultdict(lambda: 1500.0), defaultdict(int)
    with store.lock:
        rows = store.db.execute("SELECT type, p1_key, p2_key, winner FROM matches WHERE status='Finished' AND day<? ORDER BY day, time", (before_day,)).fetchall()
    for typ, k1, k2, w in rows:
        if tour_group(typ) and w in ("First Player", "Second Player") and k1 and k2:
            update(elo, played, str(k1), str(k2), 1.0 if w == "First Player" else 0.0)
    with _lock:
        _cache.clear() if len(_cache) > 8 else None
        _cache[(id(store), before_day)] = (time.time(), elo, played)
    return elo, played


def price(p2_a: float, elo, key_a, key_b) -> dict:
    """p2_a: v2 probability (0-1) that A wins."""
    pe = expected(elo[str(key_a)], elo[str(key_b)])
    p = blend(p2_a, pe)
    return {"p_a": 100 * p, "p_b": 100 * (1 - p), "odds_a": 1 / p, "odds_b": 1 / (1 - p), "elo": [round(elo[str(key_a)]), round(elo[str(key_b)])], "version": VERSION}
