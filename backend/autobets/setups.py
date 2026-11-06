"""Trade setups: where the models and the market disagree about *how a game will unfold*, not who wins.

Betfair's match prices are far better than any model we can build, so nothing here says "back this player to win". A setup is a plan to trade
the market's reaction to events: a break of serve, a quiet first quarter of an hour, a 0-0 that both the model and the market expect to last.
Each setup carries a complete script (the same rules the Scripts screen edits), a plain-English reason, and what to watch. Accepting one puts the
script into your library and the market on your Plan; nothing is bet until the script's own conditions are met in play."""
from __future__ import annotations

from . import ticks
from .ai.snapshot import _model_odds

TENNIS_GAP = 0.015           # model vs market win probability: enough to lean one way, not enough to bet the result
TENNIS_PRICE = (1.25, 7.0)   # volatility lives here: a 1.05 favourite barely moves, a 20.0 outsider is mostly noise
TENNIS_REACT = 0.12          # the price must already have moved this much (12%) from its pre-match level before we trade the swing
OVER_GAP = 0.04              # model's Over 2.5 probability above the market's by this much
OVER_PRICE = (1.5, 3.2)
UNDER_PRICE = (1.65, 2.4)    # an Under 2.5 price close to evens is a market that expects few goals but is not sure: ideal for scalping
UNDER_MIN_P = 0.50
CAVEAT = "This is a trading idea about price movement, not a prediction of the result. The models are still being tested, so check it yourself."


def _mid(sel) -> float | None:
    if not sel or not sel.backs or not sel.lays:
        return None
    return (sel.backs[0].price + sel.lays[0].price) / 2


def _implied(mids: dict) -> dict:
    """Normalise the implied probabilities of a book so they sum to 1 (removes the over-round)."""
    raw = {k: 1.0 / v for k, v in mids.items() if v}
    z = sum(raw.values())
    return {k: v / z for k, v in raw.items()} if z else {}


def _rule(rid, kind, when, then, **extra):
    return {"id": rid, "kind": kind, "when": when, "then": then, **extra}


def _scaled(price: float, k: float) -> float:
    return ticks.nearest(max(1.01, round(price * k, 2)))


# ---- tennis ------------------------------------------------------------------------------------------------------------------------------------
def tennis(info: dict, book, ctx: dict | None, stake: float) -> dict | None:
    fair = _model_odds(ctx, info.get("runners", {}))
    if len(fair) != 2:
        return None
    mids = {sid: _mid(book.selections.get(sid)) for sid in fair}
    if not all(mids.values()):
        return None
    mkt = _implied(mids)
    gap = {sid: round(1.0 / fair[sid] - mkt[sid], 4) for sid in fair}
    best = max(gap, key=gap.get)                                  # the player the model rates higher than the market does
    other = next(s for s in gap if s != best)
    names = info["runners"]
    lean = gap[best] >= TENNIS_GAP
    sel = book.selections[best]
    back = sel.backs[0].price
    if not lean:                                   # no view on the winner: still a trade on the price reaction to an early break (fade the outsider's lead)
        other = max(gap, key=lambda k: book.selections[k].backs[0].price)
    if lean and back >= TENNIS_PRICE[0]:
        # The market under-rates `best`: if he goes behind, the price over-reacts. Back him after the swing, leave when it is back on serve.
        tgt, side, p0 = best, "back", back
        title = f"Back {names[best]} if he is broken · {info['event']}"
        why = (f"The model gives {names[best]} a {1 / fair[best] * 100:.0f}% chance and the market {mkt[best] * 100:.0f}%. If he drops serve early in set 1, "
               f"the market tends to lengthen his price more than a single break justifies. The script waits for that, backs him, and hedges when he gets back on serve or after a profit target.")
        watch = [f"{names[best]} goes a game or more behind in set 1 and his price lengthens by about {TENNIS_REACT * 100:.0f}% or more",
                 "He gets back on serve (the script greens up) or the price runs 10 ticks against you (it closes out)"]
        entry = [{"type": "in_play", "value": True}, {"type": "set_number", "op": "==", "value": 1}, {"type": "set_games_diff", "op": "<=", "value": -1},
                 {"type": "price", "op": ">=", "rel": round(1 + TENNIS_REACT, 2), "ref": "back"}]
        level = {"type": "set_games_diff", "op": ">=", "value": 0}
    else:
        # `best` is a heavy favourite, so trade the other side of the same view: the market over-rates `other`; lay him when he races ahead.
        s2 = book.selections[other]
        if not s2.backs or s2.backs[0].price < TENNIS_PRICE[0] or s2.backs[0].price > (TENNIS_PRICE[1] if lean else 5.0):
            return None
        tgt, side, p0 = other, "lay", s2.backs[0].price
        title = f"Lay {names[other]} if he gets ahead · {info['event']}"
        why = ((f"The model gives {names[other]} a {1 / fair[other] * 100:.0f}% chance and the market {mkt[other] * 100:.0f}%. " if lean else
                f"The model and the market agree on {names[other]} ({mkt[other] * 100:.0f}%), so this is not a view on the winner. ") +
               f"If he breaks early in set 1 the market tends to shorten him more than one break justifies. The script waits for that, lays him, and hedges when the set is level again or after a profit target.")
        watch = [f"{names[other]} goes a game or more ahead in set 1 and his price shortens by about {TENNIS_REACT * 100:.0f}% or more",
                 "The set comes back level (the script greens up) or the price runs 10 ticks against you (it closes out)"]
        entry = [{"type": "in_play", "value": True}, {"type": "set_number", "op": "==", "value": 1}, {"type": "set_games_diff", "op": ">=", "value": 1},
                 {"type": "price", "op": "<=", "rel": round(1 - TENNIS_REACT, 2), "ref": "back"}]
        level = {"type": "set_games_diff", "op": "<=", "value": 0}
    if not (TENNIS_PRICE[0] <= p0 <= TENNIS_PRICE[1]):
        return None
    nm = names[tgt].split()[-1]
    script = {"name": f"Setup: {'Back' if side == 'back' else 'Lay'} the player on the swing", "sport": "tennis",
              "description": "Trade the price reaction to an early break in set 1. Exits when the set is level again, on a profit target, at the end of set 1 or on a stop.",
              "rules": [_rule("r1", "entry", entry, [{"type": side, "price": "best", "stake": stake, "basis": "stake", "persistence": "CANCEL"}]),
                        _rule("r2", "exit", [{"type": "rule_matched", "rule": "r1"}, level], [{"type": "green"}]),
                        _rule("r3", "exit", [{"type": "rule_matched", "rule": "r1"}, {"type": "ticks_from_entry", "op": ">=", "value": 8}], [{"type": "green"}]),
                        _rule("r4", "exit", [{"type": "rule_matched", "rule": "r1"}, {"type": "set_number", "op": ">=", "value": 2}], [{"type": "green"}]),
                        _rule("r5", "safety", [{"type": "ticks_from_entry", "op": "<=", "value": -10}], [{"type": "close"}, {"type": "stop"}])]}
    liab = stake if side == "back" else round(stake * (p0 - 1), 2)
    return {"template": ("tennis_swing_" if lean else "tennis_fade_") + side, "sport": "tennis", "selection_id": tgt, "runner": names[tgt], "side": side.upper(), "price": p0,
            "model_p": round(1 / fair[tgt], 4), "market_p": round(mkt[tgt], 4), "edge": abs(gap[best]) if lean else 0.005, "title": title, "reason": why + " " + CAVEAT,
            "watch": watch, "script": script, "stake": stake, "max_loss": liab}


# ---- football ----------------------------------------------------------------------------------------------------------------------------------
def goals_market(ms: list[dict]) -> dict | None:
    for m in ms:
        if m.get("market_type") == "OVER_UNDER_25" or str(m.get("name", "")).lower().startswith("over/under 2.5"):
            return m
    return None


def _ou_ids(m: dict) -> tuple[str, str] | None:
    over = under = None
    for sid, name in m.get("runners", {}).items():
        n = name.lower()
        if n.startswith("over"):
            over = sid
        elif n.startswith("under"):
            under = sid
    return (over, under) if over and under else None


def football(info: dict, ou_info: dict, ou_book, ctx: dict | None, stake: float) -> dict | None:
    pm = (ctx or {}).get("pre_model") or {}
    p_over = pm.get("over_2.5")
    ids = _ou_ids(ou_info)
    if p_over is None or not ids:
        return None
    over, under = ids
    mids = {over: _mid(ou_book.selections.get(over)), under: _mid(ou_book.selections.get(under))}
    if not all(mids.values()):
        return None
    mkt = _implied(mids)
    o_sel, u_sel = ou_book.selections[over], ou_book.selections[under]
    o_back, u_back = o_sel.backs[0].price, u_sel.backs[0].price
    ev = info.get("event", "")
    base = {"sport": "football", "stake": stake, "max_loss": stake, "market_id": ou_info["market_id"], "market_name": ou_info.get("name", "")}
    gap = round(p_over - mkt[over], 4)
    if gap >= OVER_GAP and OVER_PRICE[0] <= o_back <= OVER_PRICE[1]:
        script = {"name": "Setup: Back Over 2.5 after 15 min", "sport": "football",
                  "description": "Wait out the first 15 minutes, then back Over 2.5 if there are 0 or 1 goals and the price is at least as good as before kick-off. Held to the end.",
                  "rules": [_rule("r1", "entry", [{"type": "in_play", "value": True}, {"type": "minute", "op": ">=", "value": 15}, {"type": "minute", "op": "<=", "value": 40},
                                                  {"type": "goals_total", "op": "<=", "value": 1}, {"type": "price", "op": ">=", "rel": 1.0, "ref": "back"}],
                                  [{"type": "back", "price": "best", "stake": stake, "basis": "stake", "persistence": "CANCEL"}])]}
        return {**base, "template": "football_over_wait", "selection_id": over, "runner": ou_info["runners"][over], "side": "BACK", "price": o_back,
                "model_p": round(p_over, 4), "market_p": round(mkt[over], 4), "edge": gap, "script": script,
                "title": f"Back Over 2.5 Goals after 15 minutes · {ev}",
                "reason": (f"The model gives Over 2.5 goals {p_over * 100:.0f}% and the market {mkt[over] * 100:.0f}%. Rather than take {o_back:.2f} now, the script waits until "
                           f"the 15th minute: if the game is still 0-0 or 1-0 the price is usually longer, and we back it at {o_back:.2f} or better. It is held to the end (no hedge), so you can lose the whole stake. " + CAVEAT),
                "watch": ["Minute 15 arrives with no more than one goal and the Over price is at least " + f"{o_back:.2f}", "If a goal comes early the price shortens and the script simply never enters"]}
    p_under = 1 - p_over
    if p_under >= UNDER_MIN_P and UNDER_PRICE[0] <= u_back <= UNDER_PRICE[1]:
        script = {"name": "Setup: Scalp Under 2.5", "sport": "football",
                  "description": "While the game has 0 or 1 goals, back Under 2.5, green up 2 ticks better, and go again (10 runs). Exits for a loss at 6 ticks against; stops at 2 goals.",
                  "rules": [_rule("r1", "entry", [{"type": "in_play", "value": True}, {"type": "minute", "op": ">=", "value": 2}, {"type": "minute", "op": "<=", "value": 70},
                                                  {"type": "goals_total", "op": "<=", "value": 1}, {"type": "spread_ticks", "op": "<=", "value": 2}],
                                  [{"type": "back", "price": "best", "stake": stake, "basis": "stake", "persistence": "CANCEL"}], repeat=10),
                            _rule("r2", "exit", [{"type": "rule_matched", "rule": "r1"}, {"type": "ticks_from_entry", "op": ">=", "value": 2}], [{"type": "green"}]),
                            _rule("r3", "exit", [{"type": "rule_matched", "rule": "r1"}, {"type": "ticks_from_entry", "op": "<=", "value": -6}], [{"type": "close"}]),
                            _rule("r4", "safety", [{"type": "goals_total", "op": ">=", "value": 2}], [{"type": "close"}, {"type": "stop"}])]}
        return {**base, "template": "football_under_scalp", "selection_id": under, "runner": ou_info["runners"][under], "side": "BACK", "price": u_back,
                "model_p": round(p_under, 4), "market_p": round(mkt[under], 4), "edge": round(p_under - UNDER_MIN_P, 4), "script": script,
                "title": f"Scalp Under 2.5 Goals · {ev}",
                "reason": (f"The model expects a low-scoring game ({p_under * 100:.0f}% Under 2.5, about {sum(pm.get('mu', [0, 0])):.1f} goals) and the market agrees ({mkt[under] * 100:.0f}%), "
                           f"with Under at {u_back:.2f}. When both agree the price tends to creep rather than jump while it stays 0-0, which suits taking 2 ticks at a time, repeatedly. "
                           f"A trade that goes 6 ticks against is closed and the script tries again; a second goal ends it. " + CAVEAT),
                "watch": ["Kick-off and a spread of 2 ticks or less on Under 2.5", "A goal makes Under move sharply: expect a loss hedge on the first run it catches"]}
    return None
