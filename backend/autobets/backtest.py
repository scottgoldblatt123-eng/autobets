"""Replay a script over recorded Betfair prices.

Data: the price log (best back/lay per change, in-play flag, live score) plus the recorded result of each market. Only markets with a
recorded result are used. Orders are filled by the same simulated exchange as practice mode, against the recorded best prices (sizes are
treated as unlimited, so fast trading is flattered). Commission is charged on each market's net winnings. The last part of the period
(by time) is reported separately as out-of-sample. This tests how a script would have behaved on this recorded data, not how it will behave."""
from __future__ import annotations

import datetime as dt
import json
import time
from collections import defaultdict

from . import pnl
from .domain import MarketBook, OrderRequest, Persistence, Position, PriceLevel, SelectionBook, Side, Status
from .exchange.simulated import SimulatedExchange
from .ledger import UK
from .scripts import describe, evaluate

OPEN = (Status.UNMATCHED, Status.PARTIAL)
BIG = 1_000_000.0
TARGETS = ("favourite", "underdog", "draw", "first", "second")
MIN_SAMPLE_WARN = 30


def load(store, sport: str, since: float, until: float | None = None) -> list[dict]:
    """Markets with a recorded result, each with its ticks in time order."""
    until = until or time.time() + 1
    q = "SELECT t.market_id, t.sport, t.event, t.start, t.t, t.in_play, t.status, t.prices, t.ctx, r.winner, n.names FROM ticks t JOIN results r ON r.market_id=t.market_id LEFT JOIN runners n ON n.market_id=t.market_id WHERE t.t>=? AND t.t<=?"
    args: list = [since, until]
    if sport != "any":
        q += " AND t.sport=?"
        args.append(sport)
    q += " ORDER BY t.market_id, t.t"
    out: dict[str, dict] = {}
    with store.lock:
        rows = store.db.execute(q, args).fetchall()
    for mid, sp, ev, start, t, ip, st, prices, ctx, winner, names in rows:
        m = out.setdefault(mid, {"market_id": mid, "sport": sp, "event": ev, "start": start, "winner": winner, "runners": json.loads(names or "{}"), "ticks": []})
        m["ticks"].append((t, bool(ip), st, json.loads(prices), json.loads(ctx) if ctx else None))
    return list(out.values())


def pick_target(m: dict, which: str) -> str | None:
    """Which runner the script acts on, chosen from the first prices of the market."""
    names = m["runners"]
    first = next((tk[3] for tk in m["ticks"] if tk[3] and all(v[0] for v in tk[3].values())), None)
    if not first:
        return None
    if which == "draw":
        return next((sid for sid, n in names.items() if "draw" in n.lower()), None)
    ordered = sorted(first, key=lambda sid: first[sid][0])
    if which == "favourite":
        return ordered[0]
    if which == "underdog":
        return ordered[-1] if "draw" not in names.get(ordered[-1], "").lower() else (ordered[-2] if len(ordered) > 2 else ordered[-1])
    keys = list(names)
    return keys[0 if which == "first" else 1] if len(keys) > 1 else None


def _book(mid: str, tick) -> MarketBook:
    t, ip, st, prices, _ = tick
    sels = {}
    for sid, (b, l) in prices.items():
        sels[sid] = SelectionBook(sid, [PriceLevel(b, BIG)] if b else [], [PriceLevel(l, BIG)] if l else [], last_traded=b)
    return MarketBook(mid, in_play=ip, selections=sels, status=st)


def simulate(script: dict, m: dict, target: str, stake: float | None, commission: float) -> dict | None:
    """One script on one market. Returns the trade, or None if the script never entered."""
    ex = SimulatedExchange()
    fired: set[str] = set()
    state, entered_at, orders = "armed", None, []
    for tick in m["ticks"]:
        t, ip, st, prices, ctx = tick
        book = _book(m["market_id"], tick)
        sels = {sid: {"backs": [(l.price, l.size) for l in s.backs], "lays": [(l.price, l.size) for l in s.lays], "last": s.last_traded, "status": "ACTIVE"} for sid, s in book.selections.items()}
        ex.set_book(m["market_id"], sels, in_play=ip, status=st)
        if st != "OPEN" or state in ("done", "stopped") or target not in book.selections:
            continue
        sel = book.selections[target]
        held = defaultdict(Position)
        for f in ex.fills():
            r = ex.get_order(f.order_id).request
            held[r.selection_id] = pnl.apply_fill(held[r.selection_id], r.side, f.price, f.size)
        full = {sid: held.get(sid, Position()) for sid in book.selections}
        out = pnl.market_outcomes(full)
        view = {"prices": {"last": sel.last_traded, "back": sel.backs[0].price if sel.backs else None, "lay": sel.lays[0].price if sel.lays else None},
                "in_play": ip, "ctx": ctx, "position_loss": max(0.0, -min(out.values())) if held else 0.0,
                "clock": dt.datetime.fromtimestamp(t, UK).strftime("%H:%M")}
        for rule, act in evaluate(script, view, fired):
            fired.add(rule["id"])
            a = act["type"]
            if a in ("back", "lay"):
                lv = sel.backs if a == "back" else sel.lays
                price = act["price"] if act["price"] != "best" else (lv[0].price if lv else None)
                if price is None:
                    continue
                s_ = float(stake or act["stake"])
                size = round(s_ / (price - 1), 2) if (act["basis"] == "liability" and a == "lay") else s_
                o = ex.place_order(OrderRequest(m["market_id"], target, Side(a.upper()), price, size, persistence=Persistence(act["persistence"]), source="bt"))
                orders.append(o.order_id)
                entered_at = entered_at or t
                state = "running"
            elif a in ("green", "close"):
                if a == "close":
                    for o in ex.open_orders():
                        if o.status in OPEN:
                            ex.cancel_order(o.order_id)
                plan = pnl.green_plan(out, {k: (v.backs[0].price if v.backs else None) for k, v in book.selections.items()},
                                      {k: (v.lays[0].price if v.lays else None) for k, v in book.selections.items()})
                for b in (plan or {}).get("bets", []):
                    ex.place_order(OrderRequest(m["market_id"], b["selection_id"], Side(b["side"]), b["price"], b["stake"], source="bt"))
                state = "done"
            elif a == "stop":
                for o in ex.open_orders():
                    if o.status in OPEN:
                        ex.cancel_order(o.order_id)
                state = "stopped"
    fills = ex.fills()
    if not fills:
        return None
    held = defaultdict(Position)
    staked = 0.0
    for f in fills:
        r = ex.get_order(f.order_id).request
        held[r.selection_id] = pnl.apply_fill(held[r.selection_id], r.side, f.price, f.size)
        staked += f.size if r.side is Side.BACK else f.size * (r.price - 1)
    sids = set(m["runners"]) | set(held) | ({m["winner"]} if m["winner"] else set())
    out = pnl.market_outcomes({sid: held.get(sid, Position()) for sid in sids})
    gross = out.get(m["winner"], 0.0)
    net = gross - (gross * commission if gross > 0 else 0.0)
    first = ex.get_order(next(iter(o.order_id for o in ex.all_orders()))).request
    return {"market_id": m["market_id"], "event": m["event"], "t": entered_at, "date": dt.datetime.fromtimestamp(entered_at, UK).strftime("%d %b"), "runner": m["runners"].get(target, target),
            "side": first.side.value, "entry": first.price, "pnl": round(net, 2), "staked": round(staked, 2), "state": state, "won": net > 0}


def run(script: dict, markets: list[dict], target: str = "favourite", stake: float | None = None, commission: float = 0.05, oos_fraction: float = 0.3) -> dict:
    trades = []
    skipped = 0
    for m in markets:
        sel = pick_target(m, target)
        if not sel or not m["winner"]:
            skipped += 1
            continue
        tr = simulate(script, m, sel, stake, commission)
        if tr:
            trades.append(tr)
    trades.sort(key=lambda x: x["t"])
    cum, peak, dd, curve, dd_bars = 0.0, 0.0, 0.0, [], []
    for tr in trades:
        cum += tr["pnl"]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
        curve.append(round(cum, 2))
        dd_bars.append(round(peak - cum, 2))
    n = len(trades)
    k = max(0, n - int(n * oos_fraction)) if n >= 5 else n
    oos = trades[k:] if k < n else []
    staked = sum(t["staked"] for t in trades)
    months: dict[str, float] = defaultdict(float)
    for tr in trades:
        months[dt.datetime.fromtimestamp(tr["t"], UK).strftime("%b %Y")] += tr["pnl"]
    lo, hi = (min(t["pnl"] for t in trades), max(t["pnl"] for t in trades)) if trades else (0, 0)
    buckets = [0] * 12
    for tr in trades:
        i = 0 if hi == lo else min(11, int((tr["pnl"] - lo) / (hi - lo) * 12))
        buckets[i] += 1
    warnings = []
    if n < MIN_SAMPLE_WARN:
        warnings.append(f"{n} trade{'s' if n != 1 else ''} is a small sample, so this result could easily be luck.")
    warnings.append("Fills are estimated from recorded best prices with unlimited size, and may be better than reality.")
    if n >= 5:
        warnings.append("The shaded last part of the period is the out-of-sample result: it is what counts.")
    return {"script": script["name"], "target": target, "markets": len(markets), "trades": n, "skipped": skipped, "net": round(sum(t["pnl"] for t in trades), 2),
            "roi": round(100 * sum(t["pnl"] for t in trades) / staked, 1) if staked else None, "staked": round(staked, 2), "wins": sum(1 for t in trades if t["won"]),
            "losses": sum(1 for t in trades if not t["won"]), "max_drawdown": round(dd, 2), "oos": {"trades": len(oos), "net": round(sum(t["pnl"] for t in oos), 2)} if oos else None,
            "oos_from": k if oos else None, "curve": curve, "drawdown": dd_bars, "by_month": {k_: round(v, 2) for k_, v in months.items()}, "histogram": {"lo": lo, "hi": hi, "counts": buckets},
            "trade_list": trades[-200:], "commission": commission, "warnings": warnings, "rules": describe(script)}
