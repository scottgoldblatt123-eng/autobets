"""In-play tennis win probability from the live score (points, games, sets, server), independent points.

  pa = P(A wins a point on A's serve), pb = P(B wins a point on B's serve)
  live_prob(...) -> P(A wins the match) from the exact current state.
Pre-match strengths come from the v3 price: calibrate() shifts the v2 serve rates until the model's pre-match probability equals v3's.
Recommendation-only: a fair price to compare with the market, never an order."""
from __future__ import annotations

from functools import lru_cache

from . import model2

PTS = {"0": 0, "15": 1, "30": 2, "40": 3, "A": 4, "AD": 4}


def parse_points(a, b):
    """'40','A' -> (3,4); None if unparseable."""
    try:
        return PTS[str(a).upper()], PTS[str(b).upper()]
    except KeyError:
        return None


def _game_from(x: int, y: int, p: float) -> float:
    """P(server wins the game) when server has x points and receiver y (0,1,2,3 = 0,15,30,40; 4 = advantage)."""
    q = 1 - p
    deuce = p * p / (p * p + q * q)
    if x >= 3 and y >= 3:                                   # 40-40 or advantage states
        return deuce if x == y else (p + q * deuce if x > y else p * deuce)
    @lru_cache(maxsize=None)
    def f(i, j):
        if i == 4: return 1.0
        if j == 4: return 0.0
        if i == 3 and j == 3: return deuce
        return p * f(i + 1, j) + q * f(i, j + 1)
    return f(x, y)


def _set_from(ga, gb, a_serves, pa, pb, game_pts=(0, 0)):
    """P(A wins the set) from games (ga, gb); a_serves = A serves the current game; game_pts = points in it (server first)."""
    start = ga + gb
    gA, gB = model2.game(pa), model2.game(pb)
    tb = model2.tiebreak(pa, pb)

    @lru_cache(maxsize=None)
    def f(a, b):
        if (a == 6 and b <= 4) or a == 7: return 1.0
        if (b == 6 and a <= 4) or b == 7: return 0.0
        if a == 6 and b == 6: return tb
        serves = a_serves if (a + b - start) % 2 == 0 else not a_serves
        pg = gA if serves else 1 - gB
        return pg * f(a + 1, b) + (1 - pg) * f(a, b + 1)

    if game_pts == (0, 0) or (ga == 6 and gb == 6):
        return f(ga, gb)
    x, y = game_pts
    pg = _game_from(x, y, pa if a_serves else pb)           # server's chance of holding from this point score
    pg = pg if a_serves else 1 - pg                         # -> A's chance of winning the current game
    return pg * f(ga + 1, gb) + (1 - pg) * f(ga, gb + 1)


def live_prob(pa, pb, sets=(0, 0), games=(0, 0), points=(0, 0), a_serving=True, best_of=3) -> float:
    """P(A wins the match). sets = sets won (A, B); games = games in the current set; points = (A, B) in the current game."""
    need = best_of // 2 + 1
    sa, sb = sets
    s_fresh = 0.5 * (model2.set_prob(pa, pb) + 1 - model2.set_prob(pb, pa))     # a new set: either player may serve first
    cur = _set_from(games[0], games[1], a_serving, pa, pb, (points if a_serving else (points[1], points[0])) if True else points)

    @lru_cache(maxsize=None)
    def m(x, y):
        if x == need: return 1.0
        if y == need: return 0.0
        return s_fresh * m(x + 1, y) + (1 - s_fresh) * m(x, y + 1)
    return cur * m(sa + 1, sb) + (1 - cur) * m(sa, sb + 1)


def calibrate(serve_a: float, serve_b: float, target: float, best_of: int = 3) -> tuple[float, float]:
    """Shift A's serve rate up and B's down (equal and opposite) until the pre-match match probability equals `target` (0-1)."""
    lo, hi = -0.15, 0.15
    clip = lambda x: min(0.85, max(0.4, x))
    for _ in range(40):
        d = (lo + hi) / 2
        if model2.match_prob(clip(serve_a + d), clip(serve_b - d), best_of) < target:
            lo = d
        else:
            hi = d
    d = (lo + hi) / 2
    return clip(serve_a + d), clip(serve_b - d)
