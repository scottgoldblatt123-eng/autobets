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


def market_outcomes(positions: dict[str, Position]) -> dict[str, float]:
    """Profit if each selection wins, across the whole market (before commission).
    o_s = win(s) + sum of lose(t) for every other selection t."""
    total_lose = sum(p.lose for p in positions.values())
    return {s: round(p.win + total_lose - p.lose, 2) for s, p in positions.items()}


def _apply(outcomes: dict[str, float], sel: str, side: Side, price: float, stake: float) -> dict[str, float]:
    out = {}
    for i, v in outcomes.items():
        if side is Side.BACK:
            d = stake * (price - 1) if i == sel else -stake
        else:
            d = -stake * (price - 1) if i == sel else stake
        out[i] = v + d
    return out


def green_plan(outcomes: dict[str, float], backs: dict[str, float | None], lays: dict[str, float | None],
               min_stake: float = 1.0) -> dict | None:
    """Bets that equalise every outcome of a market at current prices, using the fewest bets.

    Leave one selection k un-bet; each other selection i needs stake (o_i - o_k)/q_i: a LAY when o_i > o_k
    (q = best lay price), a BACK when o_i < o_k (q = best back price). Every k is tried and the one that
    locks the most profit wins. Stakes under the minimum are dropped (the result then is not fully level).
    Returns None when outcomes are already level or no usable prices exist.
    """
    vals = list(outcomes.values())
    if not vals or max(vals) - min(vals) < 0.005:
        return None
    best = None
    for k in outcomes:
        bets, ok = [], True
        for i, o in outcomes.items():
            if i == k:
                continue
            diff = o - outcomes[k]
            if abs(diff) < 0.005:
                continue
            side, price = (Side.LAY, lays.get(i)) if diff > 0 else (Side.BACK, backs.get(i))
            if not price:
                ok = False
                break
            stake = round(abs(diff) / price, 2)
            if stake >= min_stake:
                bets.append({"selection_id": i, "side": side.value, "price": price, "stake": stake})
        if not ok:
            continue
        after = dict(outcomes)
        for b in bets:
            after = _apply(after, b["selection_id"], Side(b["side"]), b["price"], b["stake"])
        locked = round(min(after.values()), 2)
        level = max(after.values()) - min(after.values()) < 0.05
        cand = {"locked": locked, "bets": bets, "level": level, "after": {i: round(v, 2) for i, v in after.items()}}
        if best is None or (cand["level"], cand["locked"]) > (best["level"], best["locked"]):
            best = cand
    return best
