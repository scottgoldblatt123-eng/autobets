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


def dutch_plan(side: Side, prices: dict[str, float], total: float, min_stake: float = 1.0) -> dict:
    """Split `total` across the chosen selections so that every one of them returns the same.

    Stake_i = total * (1/p_i) / sum(1/p). For backs, whichever selected runner wins pays the same; for lays (the same split) it costs the same.
    Stakes under the minimum are reported in `dropped` rather than placed."""
    inv = sum(1.0 / p for p in prices.values())
    if not prices or inv <= 0:
        return {"bets": [], "dropped": [], "error": "pick at least one runner"}
    bets, dropped = [], []
    for sid, p in prices.items():
        stake = round(total * (1.0 / p) / inv, 2)
        (bets if stake >= min_stake else dropped).append({"selection_id": sid, "side": side.value, "price": p, "stake": stake})
    return {"bets": bets, "dropped": dropped, "book": round(inv * 100, 2), "error": ""}


def book_plan(outcomes: dict[str, float], targets: dict[str, float], backs: dict[str, float | None], lays: dict[str, float | None],
              min_stake: float = 1.0) -> dict:
    """Bets that move every outcome of a market from where it is to the target profit you name for each runner (bookmaking).

    A bet x_j on runner j (positive = back stake, negative = lay stake) at price p_j changes the outcome if j wins by x_j*p_j - S, where S is the
    sum of all x. So the change d_j = target_j - outcome_j needs x_j = (d_j + S)/p_j, and S = sum(d_j/p_j) / (1 - sum(1/p_j)). Back prices are used
    for backs and lay prices for lays, so the signs are settled by iterating until they stop changing."""
    ids = list(outcomes)
    if set(targets) != set(ids):
        return {"bets": [], "dropped": [], "after": dict(outcomes), "error": "give a target for every runner"}
    d = {j: targets[j] - outcomes[j] for j in ids}
    sign = {j: (1 if d[j] >= 0 else -1) for j in ids}          # start: back where more profit is wanted, lay where less
    x: dict[str, float] = {}
    p: dict[str, float] = {}
    for _ in range(12):
        for j in ids:
            pr = backs.get(j) if sign[j] > 0 else lays.get(j)
            if not pr:
                return {"bets": [], "dropped": [], "after": dict(outcomes), "error": "no price available on one of the runners"}
            p[j] = pr
        inv = sum(1.0 / p[j] for j in ids)
        if abs(1.0 - inv) < 1e-6:
            return {"bets": [], "dropped": [], "after": dict(outcomes), "error": "these prices make a book of exactly 100%, so these targets cannot be reached with bets on these prices"}
        S = sum(d[j] / p[j] for j in ids) / (1.0 - inv)
        x = {j: (d[j] + S) / p[j] for j in ids}
        new = {j: (sign[j] if abs(x[j]) < 0.005 else (1 if x[j] > 0 else -1)) for j in ids}       # a bet of ~nothing keeps its side
        if new == sign:
            break
        sign = new
    bets, dropped = [], []
    for j in ids:
        if abs(x[j]) < 0.005:
            continue
        b = {"selection_id": j, "side": "BACK" if x[j] > 0 else "LAY", "price": p[j], "stake": round(abs(x[j]), 2)}
        (bets if b["stake"] >= min_stake else dropped).append(b)
    after = dict(outcomes)
    for b in bets:
        after = _apply(after, b["selection_id"], Side(b["side"]), b["price"], b["stake"])
    return {"bets": bets, "dropped": dropped, "after": {i: round(v, 2) for i, v in after.items()}, "error": ""}
