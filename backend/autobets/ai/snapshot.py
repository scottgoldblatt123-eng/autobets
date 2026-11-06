"""A compact, factual picture of the open markets for the copilot: prices, position, live score, model fair prices and the gap in ticks."""
from __future__ import annotations

from .. import ticks


def _best(levels):
    return levels[0][0] if levels else None


def _norm(s: str) -> str:
    return " ".join("".join(c if c.isalpha() else " " for c in (s or "").lower()).split())


def same_name(a: str, b: str) -> bool:
    """Do two player or team names refer to the same one? Tolerant of initials, order and extra words."""
    na, nb = _norm(a), _norm(b)
    return bool(na) and bool(nb) and (na in nb or nb in na or na.split()[-1] == nb.split()[-1])


def _model_odds(ctx: dict | None, runners: dict) -> dict:
    """Runner id -> model fair odds, matched by name. Empty when the live model or the names do not line up."""
    m = (ctx or {}).get("model")
    if not m:
        return {}
    norm = lambda s: " ".join("".join(c if c.isalpha() else " " for c in (s or "").lower()).split())
    same = lambda a, b: bool(norm(a)) and bool(norm(b)) and (norm(a) in norm(b) or norm(b) in norm(a) or norm(a).split()[-1] == norm(b).split()[-1])
    out = {}
    if ctx.get("kind") == "tennis" and m.get("odds") and ctx.get("players"):
        for sid, name in runners.items():
            for i, p in enumerate(ctx["players"]):
                if same(p, name):
                    out[sid] = m["odds"][i]
    elif ctx.get("kind") == "football" and m.get("home") is not None and ctx.get("teams"):
        for sid, name in runners.items():
            if "draw" in norm(name):
                key = "draw"
            elif same(ctx["teams"][0], name):
                key = "home"
            elif same(ctx["teams"][1], name):
                key = "away"
            else:
                continue
            if m.get(key):
                out[sid] = 1 / m[key]
    return out if len(out) == len(runners) else {}


def build(markets: dict, ctxs: dict) -> list[dict]:
    """markets: engine.state()['markets']; ctxs: market id -> live context (or missing)."""
    out = []
    for mid, m in markets.items():
        ctx = ctxs.get(mid)
        fair = _model_odds(ctx, m.get("runners", {}))
        runners = []
        for sid, name in m.get("runners", {}).items():
            s = (m.get("selections") or {}).get(sid, {})
            back, lay = _best(s.get("backs", [])), _best(s.get("lays", []))
            r = {"name": name, "best_back": back, "best_lay": lay, "last_traded": s.get("last"), "status": s.get("status")}
            if sid in fair:
                f = round(fair[sid], 2); r["model_fair_odds"] = f
                try:
                    if back: r["back_vs_fair_ticks"] = ticks.ticks_between(ticks.nearest(f), back)      # + = market pays more than fair
                    if lay: r["fair_vs_lay_ticks"] = ticks.ticks_between(lay, ticks.nearest(f))          # + = market lay is shorter than fair
                except Exception:
                    pass
            pos = (m.get("positions") or {}).get(sid)
            if pos: r["position_if_wins_loses"] = pos
            runners.append(r)
        entry = {"market_id": mid, "event": m.get("event"), "market": m.get("name"), "start": m.get("start"), "in_play": m.get("in_play"),
                 "status": m.get("status"), "runners": runners}
        if m.get("outcomes"): entry["profit_if_each_runner_wins"] = m["outcomes"]
        if ctx:
            entry["live"] = {k: ctx[k] for k in ("status", "sets", "game", "serving", "elapsed", "goals", "players", "teams") if k in ctx}
        out.append(entry)
    return out
