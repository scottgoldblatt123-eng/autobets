"""Position and hedge maths. Commission is applied to net winning markets only."""
from __future__ import annotations

from .domain import Fill, Position, Side


def apply_fill(pos: Position, side: Side, fill_price: float, size: float) -> Position:
    """Add a matched bet to a selection position (win/lose outcomes, before commission)."""
    if side is Side.BACK:
        win_delta, lose_delta = size * (fill_price - 1), -size
    else:
        win_delta, lose_delta = -size * (fill_price - 1), size
    return Position(round(pos.win + win_delta, 2), round(pos.lose + lose_delta, 2))


def hedge(pos: Position, price: float) -> tuple[Side, float, float] | None:
    """Bet that equalises the outcomes at `price`.

    Returns (side, stake, locked_profit) or None if already level.
    """
    diff = pos.lose - pos.win
    if abs(diff) < 0.005:
        return None
    stake = round(abs(diff) / price, 2)
    side = Side.BACK if diff > 0 else Side.LAY
    # re-evaluate with the rounded stake
    after = apply_fill(pos, side, price, stake)
    return side, stake, round(min(after.win, after.lose), 2)


def net_after_commission(profit: float, commission_rate: float = 0.05) -> float:
    return round(profit - max(profit, 0) * commission_rate, 2)
