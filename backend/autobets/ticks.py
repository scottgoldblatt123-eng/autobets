"""Betfair price ladder: valid prices and tick arithmetic."""
from __future__ import annotations

# (lower bound inclusive, upper bound exclusive, increment)
_BANDS = [
    (1.01, 2.0, 0.01), (2.0, 3.0, 0.02), (3.0, 4.0, 0.05), (4.0, 6.0, 0.1),
    (6.0, 10.0, 0.2), (10.0, 20.0, 0.5), (20.0, 30.0, 1.0), (30.0, 50.0, 2.0),
    (50.0, 100.0, 5.0), (100.0, 1000.0, 10.0),
]
MIN_PRICE, MAX_PRICE = 1.01, 1000.0


def _build() -> list[float]:
    out: list[float] = []
    for lo, hi, inc in _BANDS:
        n = round((hi - lo) / inc)
        out.extend(round(lo + i * inc, 2) for i in range(n))
    out.append(MAX_PRICE)
    return out


LADDER: list[float] = _build()
_INDEX = {p: i for i, p in enumerate(LADDER)}


def is_valid(price: float) -> bool:
    return round(price, 2) in _INDEX


def nearest(price: float) -> float:
    """Closest valid price (ties go up)."""
    price = min(max(price, MIN_PRICE), MAX_PRICE)
    best = min(LADDER, key=lambda p: (abs(p - price), -p))
    return best


def move(price: float, ticks: int) -> float:
    """Move a valid price by a number of ticks, clamped to the ladder ends."""
    i = _INDEX[round(price, 2)] + ticks
    return LADDER[max(0, min(len(LADDER) - 1, i))]


def ticks_between(a: float, b: float) -> int:
    return _INDEX[round(b, 2)] - _INDEX[round(a, 2)]
