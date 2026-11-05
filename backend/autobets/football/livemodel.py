"""In-play football prices from the live score and clock.

Remaining goals for each team are Poisson with the pre-match expected goals scaled by the share of the match still to play
(goals are slightly more frequent in the second half: 45% of goals in the first half, 55% in the second). Independent teams; no red-card
or score-effect adjustment yet. Recommendation-only: a fair price to compare with the market."""
from __future__ import annotations

import math

H1_SHARE = 0.45
LIVE = ("1H", "HT", "2H")


def remaining_share(elapsed: int | None, code: str) -> float:
    """Fraction of a match's goals still to come."""
    if code == "HT":
        t = 45.0
    elif elapsed is None:
        return 1.0
    else:
        t = float(elapsed)
    if t <= 45:
        done = H1_SHARE * t / 45
    else:
        done = H1_SHARE + (1 - H1_SHARE) * min(t - 45, 45) / 45
    return max(1 - done, 0.02)                      # never zero: stoppage time can still bring a goal


def _pois(mu: float, n: int = 12):
    return [math.exp(-mu) * mu ** k / math.factorial(k) for k in range(n)]


def price(mu_h: float, mu_a: float, goals: tuple[int, int], elapsed: int | None, code: str) -> dict:
    r = remaining_share(elapsed, code)
    ph, pa = _pois(mu_h * r), _pois(mu_a * r)
    gh, ga = goals
    home = draw = away = btts = 0.0
    totals: dict[int, float] = {}
    for i, a in enumerate(ph):
        for j, b in enumerate(pa):
            p = a * b
            fh, fa = gh + i, ga + j
            if fh > fa: home += p
            elif fh == fa: draw += p
            else: away += p
            if fh > 0 and fa > 0: btts += p
            totals[fh + fa] = totals.get(fh + fa, 0.0) + p
    z = home + draw + away
    out = {"home": home / z, "draw": draw / z, "away": away / z, "btts": btts / z, "version": "fb-live-v1", "remaining": r}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        out[f"over_{line}"] = sum(p for t, p in totals.items() if t > line) / z
    return out
