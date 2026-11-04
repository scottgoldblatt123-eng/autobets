"""Tennis model v2 ('markov'): serve/return point rates -> game -> set -> match win probability.

Inputs per player (rows as built by tables.build, percentages): service_pts, return_pts, matches.
  1. shrink each rate toward the tour average with weight SHRINK_K matches (small samples count for less);
  2. p(A wins a point on A's serve) = svc_A + (avg_ret - ret_B)   (and the mirror for B), the same opponent
     adjustment as the workbook, but applied to point rates and clipped to a sane range;
  3. exact game, tie-break, set and match probabilities from those two point probabilities (iid points).
Recommendation-only: the output is a probability and fair odds, never an order."""
from __future__ import annotations

from functools import lru_cache

VERSION = "v2-markov"
SHRINK_K = 10.0


def shrink(x: float, n: float, avg: float, k: float = SHRINK_K) -> float:
    return (n * x + k * avg) / (n + k)


@lru_cache(maxsize=None)
def game(p: float) -> float:
    """P(server wins a game) given point probability p."""
    q = 1 - p
    pre = sum(_c(3 + i, i) * p ** 4 * q ** i for i in range(3))      # win to 0, 15, 30
    deuce = _c(6, 3) * p ** 3 * q ** 3                                  # reach 3-3
    return pre + deuce * p * p / (p * p + q * q)


def _c(n: int, k: int) -> int:
    from math import comb
    return comb(n, k)


def tiebreak(pa: float, pb: float) -> float:
    """P(A wins a 7-point tie-break); A serves first, serves alternate 1-2-2-2... Approximated with the mean point prob."""
    p = (pa + (1 - pb)) / 2
    q = 1 - p
    win = sum(_c(6 + i, i) * p ** 7 * q ** i for i in range(6))
    tie = _c(12, 6) * p ** 6 * q ** 6
    return win + tie * p * p / (p * p + q * q)


def set_prob(pa: float, pb: float) -> float:
    """P(A wins a set). pa = A's point prob on A's serve, pb = B's point prob on B's serve. A serves first."""
    ga, gb = game(pa), game(pb)
    # state (games A, games B) with alternating server; A serves when total games is even
    from functools import lru_cache as lc

    @lc(maxsize=None)
    def f(a: int, b: int) -> float:
        if a == 6 and b <= 4 or a == 7:
            return 1.0
        if b == 6 and a <= 4 or b == 7:
            return 0.0
        if a == 6 and b == 6:
            return tiebreak(pa, pb)
        pg = ga if (a + b) % 2 == 0 else 1 - gb
        return pg * f(a + 1, b) + (1 - pg) * f(a, b + 1)
    return f(0, 0)


def match_prob(pa: float, pb: float, best_of: int = 3) -> float:
    s = set_prob(pa, pb)
    need = best_of // 2 + 1
    from math import comb
    return sum(comb(need - 1 + i, i) * s ** need * (1 - s) ** i for i in range(need))


def price(a: dict, b: dict, avg: dict, best_of: int = 3) -> dict:
    """a, b: {'service_pts','return_pts','matches'}; avg: {'service_pts','return_pts'} (all in %)."""
    sa = shrink(a["service_pts"], a["matches"], avg["service_pts"]); ra = shrink(a["return_pts"], a["matches"], avg["return_pts"])
    sb = shrink(b["service_pts"], b["matches"], avg["service_pts"]); rb = shrink(b["return_pts"], b["matches"], avg["return_pts"])
    clip = lambda x: min(0.85, max(0.4, x / 100))
    pa, pb = clip(sa + (avg["return_pts"] - rb)), clip(sb + (avg["return_pts"] - ra))
    p = match_prob(pa, pb, best_of)
    return {"p_a": 100 * p, "p_b": 100 * (1 - p), "odds_a": 1 / p, "odds_b": 1 / (1 - p),
            "serve_a": pa, "serve_b": pb, "version": VERSION}
