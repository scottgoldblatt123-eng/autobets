"""Automation scripts: a script is plain data (rules of 'if these conditions then this action') that is validated, versioned and
evaluated by plain code. The AI may draft one, but it only ever produces this data; the same validator and the same safety rules apply.

A script has a target selection (the runner it acts on), filled in when it is added to the Plan.
  rule kinds: entry (opens a position, fires once), exit (needs an earlier rule to have matched), safety (can close and stop the script)."""
from __future__ import annotations

import time

KINDS = ("entry", "exit", "safety")
SPORTS = ("tennis", "football", "any")
OPS = (">=", "<=", "==", ">", "<")
PRICE_REFS = ("last", "back", "lay")
ACTIONS = ("back", "lay", "green", "close", "stop")
PERSIST = ("KEEP", "CANCEL", "TAKE_SP")

# condition type -> required fields (value types are checked below)
CONDITIONS = {
    "price": ("op", "value"),            # price of the target runner; optional "ref": last | back | lay
    "in_play": ("value",),               # true / false
    "set_number": ("op", "value"),       # tennis: the set being played (1, 2, 3 …)
    "set_games_diff": ("op", "value"),   # tennis: games won by the target player minus the opponent in the current set (-1 = a game behind, e.g. broken)
    "sets_diff": ("op", "value"),        # tennis: sets won by the target player minus the opponent
    "serving": ("value",),               # tennis: true when the target player is serving
    "game_points_diff": ("op", "value"), # tennis: points won in the current game by the target player minus the opponent (0, 15, 30, 40, advantage = 0..4)
    "game_score_is": ("me", "opp"),      # tennis: exact points in the current game from the target player's view, e.g. 0 and 0, or 15 and 40
    "breaks_diff": ("op", "value"),      # tennis: service breaks in the current set, the target player's minus the opponent's (+1 = one break up). Worked out from the games and who serves
    "break_point": ("side",),            # tennis: 'against' = the target is serving and facing a break point; 'for' = the target is receiving with a break point
    "set_games_total": ("op", "value"),  # tennis: games played so far in the current set
    "prev_set_games_diff": ("op", "value"),  # tennis: games won by the target in the previous set minus the opponent (+3 = won it by 3 or more)
    "half_time": ("value",),             # football: true during the half-time break
    "goals_total": ("op", "value"),      # football: goals scored so far by both teams
    "score_is": ("home", "away"),        # football: exact score
    "minute": ("op", "value"),           # football: match minute
    "rule_matched": ("rule",),           # an earlier rule of this script has fired
    "position_loss": ("op", "value"),    # £ the position would lose if the worst outcome happened
    "clock": ("start", "end"),           # UK time window, "HH:MM"
    "ticks_from_entry": ("op", "value"), # ticks the price you could exit at is better (+) or worse (-) than where this script was matched
    "ticks_from_peak": ("value",),       # trailing stop: the exit price has given back this many ticks from its best since you were matched
    "minutes_to_start": ("op", "value"), # minutes until the scheduled start (negative once it should have started)
    "spread_ticks": ("op", "value"),     # ticks between best back and best lay on the runner
    "market_matched": ("op", "value"),   # £ matched on the whole market so far
    "price_move": ("op", "value", "seconds"),  # ticks the runner's price has moved over the last N seconds (+ = drifted out, - = shortened)
}


class ScriptError(ValueError):
    pass


def _num(v, what: str, lo: float = 0, hi: float = 1_000_000) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ScriptError(f"{what} must be a number")
    if not (lo <= v <= hi) or v != v:
        raise ScriptError(f"{what} must be between {lo:g} and {hi:g}")
    return float(v)


def _hhmm(v, what: str) -> str:
    try:
        h, m = str(v).split(":")
        assert 0 <= int(h) < 24 and 0 <= int(m) < 60 and len(m) == 2
    except Exception:
        raise ScriptError(f"{what} must be a time like 19:30") from None
    return f"{int(h):02d}:{m}"


def validate_condition(c: dict) -> dict:
    if not isinstance(c, dict) or c.get("type") not in CONDITIONS:
        raise ScriptError(f"unknown condition {c.get('type') if isinstance(c, dict) else c!r}; use one of {sorted(CONDITIONS)}")
    t = c["type"]
    for f in CONDITIONS[t]:
        if f not in c:
            raise ScriptError(f"condition '{t}' needs '{f}'")
    out: dict = {"type": t}
    if "op" in CONDITIONS[t]:
        if c["op"] not in OPS:
            raise ScriptError(f"op must be one of {OPS}")
        out["op"] = c["op"]
    if t == "price":
        out["value"] = _num(c["value"], "price", 1.01, 1000)
        ref = c.get("ref", "last")
        if ref not in PRICE_REFS:
            raise ScriptError(f"price ref must be one of {PRICE_REFS}")
        out["ref"] = ref
    elif t == "in_play":
        if not isinstance(c["value"], bool):
            raise ScriptError("in_play must be true or false")
        out["value"] = c["value"]
    elif t in ("set_games_diff", "sets_diff", "prev_set_games_diff"):
        out["value"] = _num(c["value"], t, -20, 20)
    elif t == "set_games_total":
        out["value"] = _num(c["value"], t, 0, 40)
    elif t == "breaks_diff":
        out["value"] = _num(c["value"], t, -6, 6)
    elif t in ("serving", "half_time"):
        if not isinstance(c["value"], bool):
            raise ScriptError(f"{t} must be true or false")
        out["value"] = c["value"]
    elif t == "game_points_diff":
        out["value"] = int(_num(c["value"], t, -4, 4))
    elif t == "game_score_is":
        for k in ("me", "opp"):
            v = str(c[k]).upper().replace("AD", "A")
            if v not in ("0", "15", "30", "40", "A"):
                raise ScriptError(f"game_score_is {k} must be 0, 15, 30, 40 or A")
            out[k] = v
    elif t == "break_point":
        if c["side"] not in ("against", "for"):
            raise ScriptError("break_point side must be 'against' or 'for'")
        out["side"] = c["side"]
    elif t in ("set_number", "goals_total", "minute"):
        out["value"] = _num(c["value"], t, 0, 200)
    elif t == "position_loss":
        out["value"] = _num(c["value"], "loss", 0, 100000)
    elif t == "ticks_from_entry":
        out["value"] = int(_num(c["value"], "ticks", -200, 200))
    elif t == "ticks_from_peak":
        out["value"] = int(_num(c["value"], "ticks", 1, 200))
    elif t == "minutes_to_start":
        out["value"] = _num(c["value"], "minutes", -600, 100000)
    elif t == "spread_ticks":
        out["value"] = int(_num(c["value"], "ticks", 0, 200))
    elif t == "market_matched":
        out["value"] = _num(c["value"], "matched £", 0, 1e9)
    elif t == "price_move":
        out["value"] = int(_num(c["value"], "ticks", -200, 200))
        out["seconds"] = int(_num(c["seconds"], "seconds", 5, 600))
    elif t == "score_is":
        out["home"], out["away"] = int(_num(c["home"], "home", 0, 30)), int(_num(c["away"], "away", 0, 30))
    elif t == "rule_matched":
        out["rule"] = str(c["rule"])
    elif t == "clock":
        out["start"], out["end"] = _hhmm(c["start"], "start"), _hhmm(c["end"], "end")
    return out


def validate_action(a: dict) -> dict:
    if not isinstance(a, dict) or a.get("type") not in ACTIONS:
        raise ScriptError(f"unknown action {a.get('type') if isinstance(a, dict) else a!r}; use one of {ACTIONS}")
    t, out = a["type"], {"type": a["type"]}
    if t in ("back", "lay"):
        price = a.get("price", "best")
        out["price"] = "best" if price == "best" else _num(price, "price", 1.01, 1000)
        out["stake"] = _num(a.get("stake"), "stake", 1, 100000)
        out["basis"] = a.get("basis", "stake")
        if out["basis"] not in ("stake", "liability"):
            raise ScriptError("basis must be stake or liability")
        out["persistence"] = a.get("persistence", "CANCEL")
        if out["persistence"] not in PERSIST:
            raise ScriptError(f"persistence must be one of {PERSIST}")
    if t in ("green", "close") and a.get("percent") not in (None, 100):
        out["percent"] = int(_num(a["percent"], "percent", 1, 99))
    return out


def validate(script: dict) -> dict:
    """Return a clean copy of the script or raise ScriptError saying what is wrong. Everything the AI or an import supplies passes through here."""
    if not isinstance(script, dict):
        raise ScriptError("a script must be an object")
    name = str(script.get("name", "")).strip()
    if not name or len(name) > 80:
        raise ScriptError("a script needs a name (up to 80 characters)")
    sport = script.get("sport", "any")
    if sport not in SPORTS:
        raise ScriptError(f"sport must be one of {SPORTS}")
    rules_in = script.get("rules")
    if not isinstance(rules_in, list) or not rules_in or len(rules_in) > 12:
        raise ScriptError("a script needs between 1 and 12 rules")
    rules, ids = [], set()
    for i, r in enumerate(rules_in, 1):
        if not isinstance(r, dict) or r.get("kind") not in KINDS:
            raise ScriptError(f"rule {i}: kind must be one of {KINDS}")
        rid = str(r.get("id") or f"r{i}")
        if rid in ids:
            raise ScriptError(f"rule {i}: duplicate id {rid}")
        conds = r.get("when")
        if not isinstance(conds, list) or not conds:
            raise ScriptError(f"rule {i}: needs at least one condition in 'when'")
        acts = r.get("then")
        if not isinstance(acts, list) or not acts:
            raise ScriptError(f"rule {i}: needs at least one action in 'then'")
        try:
            rule = {"id": rid, "kind": r["kind"], "when": [validate_condition(c) for c in conds], "then": [validate_action(a) for a in acts]}
        except ScriptError as e:
            raise ScriptError(f"rule {i}: {e}") from None
        for c in rule["when"]:
            if c["type"] == "rule_matched" and c["rule"] not in ids:
                raise ScriptError(f"rule {i}: refers to rule '{c['rule']}', which must come earlier in the script")
        if rule["kind"] == "exit" and not any(c["type"] == "rule_matched" for c in rule["when"]):
            raise ScriptError(f"rule {i}: an exit rule must depend on an earlier rule (add 'rule_matched')")
        if any(a["type"] in ("green", "close", "stop") for a in rule["then"]) and rule["kind"] == "entry":
            raise ScriptError(f"rule {i}: an entry rule opens a position; use back or lay")
        if rule["kind"] == "entry":
            rep = r.get("repeat", 1)
            if isinstance(rep, bool) or not isinstance(rep, int) or not 1 <= rep <= 100:
                raise ScriptError(f"rule {i}: repeat must be a whole number from 1 to 100")
            rule["repeat"] = rep
        ids.add(rid)
        rules.append(rule)
    if not any(r["kind"] == "entry" for r in rules):
        raise ScriptError("a script needs an entry rule")
    return {"name": name, "sport": sport, "description": str(script.get("description", ""))[:400], "rules": rules}


def _cmp(a: float, op: str, b: float) -> bool:
    return {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b}[op]


def _price(view: dict, ref: str) -> float | None:
    p = view.get("prices", {})
    order = {"last": ("last", "back", "lay"), "back": ("back",), "lay": ("lay",)}[ref]
    for k in order:
        if p.get(k):
            return p[k]
    return None


def gain_ticks(side: str, entry_price: float, prices: dict) -> int | None:
    """Ticks of profit available to exit now versus the entry price (negative = against you); None if there is no exit price."""
    from . import ticks
    exit_p = (prices or {}).get("lay" if side == "BACK" else "back")
    if not exit_p:
        return None
    e, x = ticks.nearest(entry_price), ticks.nearest(exit_p)
    return ticks.ticks_between(x, e) if side == "BACK" else ticks.ticks_between(e, x)


_PTS = {"0": 0, "15": 1, "30": 2, "40": 3, "A": 4, "AD": 4}


def _pt(x) -> int | None:
    return _PTS.get(str(x).strip().upper())


def _tennis_football_check(cond: dict, view: dict, ctx: dict) -> bool:
    t, i = cond["type"], view.get("player_idx")
    if t == "half_time":
        return (ctx.get("code") == "HT") == cond["value"]
    if i is None:
        return False
    try:
        if t == "set_games_total":
            return bool(ctx.get("sets")) and _cmp(sum(ctx["sets"][-1]), cond["op"], cond["value"])
        if t == "prev_set_games_diff":
            sets = ctx.get("sets") or []
            return len(sets) >= 2 and _cmp(sets[-2][i] - sets[-2][1 - i], cond["op"], cond["value"])
        srv = ctx.get("serving")
        if t == "breaks_diff":
            sets = ctx.get("sets")
            if srv is None or not sets or sum(sets[-1]) >= 12:                 # unknown server, or a tie-break set where alternation no longer holds
                return False
            n, d = sum(sets[-1]), sets[-1][i] - sets[-1][1 - i]
            me_first = (srv == i) == (n % 2 == 0)                              # who served the first game of this set
            hold_only = (1 if me_first else -1) if n % 2 else 0                # the games difference if every game had been held
            return _cmp((d - hold_only) / 2, cond["op"], cond["value"])
        if t == "serving":
            return srv is not None and (srv == i) == cond["value"]
        game = ctx.get("game")
        if not game:
            return False
        me, opp = _pt(game[i]), _pt(game[1 - i])
        if me is None or opp is None:
            return False
        if t == "game_points_diff":
            return _cmp(me - opp, cond["op"], cond["value"])
        if t == "game_score_is":
            return me == _pt(cond["me"]) and opp == _pt(cond["opp"])
        if t == "break_point":
            if srv is None:
                return False
            return (srv == i and opp >= 3 and opp > me) if cond["side"] == "against" else (srv != i and me >= 3 and me > opp)
    except (TypeError, ValueError, IndexError):
        return False
    return False


def check(cond: dict, view: dict, fired: set[str]) -> bool:
    """Is one condition true right now? `view` carries prices, in_play, ctx (score/set/minute), position_loss, clock (UK 'HH:MM')."""
    t, ctx = cond["type"], view.get("ctx") or {}
    if t == "price":
        p = _price(view, cond["ref"])
        return p is not None and _cmp(p, cond["op"], cond["value"])
    if t == "in_play":
        return bool(view.get("in_play")) == cond["value"]
    if t == "set_number":
        sets = ctx.get("sets")
        return bool(sets) and _cmp(len(sets), cond["op"], cond["value"])
    if t in ("serving", "game_points_diff", "game_score_is", "break_point", "set_games_total", "prev_set_games_diff", "half_time", "breaks_diff"):
        return _tennis_football_check(cond, view, ctx)
    if t in ("set_games_diff", "sets_diff"):
        i = view.get("player_idx")
        try:
            if i is None:
                return False
            if t == "sets_diff":
                won = ctx.get("sets_won")
                return bool(won) and _cmp(int(won[i]) - int(won[1 - i]), cond["op"], cond["value"])
            sets = ctx.get("sets")
            return bool(sets) and _cmp(sets[-1][i] - sets[-1][1 - i], cond["op"], cond["value"])
        except (TypeError, ValueError, IndexError):
            return False
    if t in ("goals_total", "score_is", "minute"):
        goals = ctx.get("goals")
        if t == "minute":
            return ctx.get("elapsed") is not None and _cmp(ctx["elapsed"], cond["op"], cond["value"])
        if not goals:
            return False
        if t == "goals_total":
            return _cmp(sum(goals), cond["op"], cond["value"])
        return goals[0] == cond["home"] and goals[1] == cond["away"]
    if t == "rule_matched":
        return cond["rule"] in fired
    if t == "position_loss":
        return _cmp(view.get("position_loss", 0.0), cond["op"], cond["value"])
    if t == "ticks_from_entry":
        ent = view.get("entry")
        if not ent:
            return False                      # not matched yet
        g = gain_ticks(ent["side"], ent["price"], view.get("prices"))
        return g is not None and _cmp(g, cond["op"], cond["value"])
    if t == "ticks_from_peak":
        ent = view.get("entry")
        if not ent:
            return False
        g = gain_ticks(ent["side"], ent["price"], view.get("prices"))
        return g is not None and ent.get("peak", 0) - g >= cond["value"]
    if t == "minutes_to_start":
        m = view.get("mins_to_start")
        return m is not None and _cmp(m, cond["op"], cond["value"])
    if t == "spread_ticks":
        from . import ticks
        pr = view.get("prices") or {}
        if not pr.get("back") or not pr.get("lay"):
            return False
        return _cmp(ticks.ticks_between(ticks.nearest(pr["back"]), ticks.nearest(pr["lay"])), cond["op"], cond["value"])
    if t == "market_matched":
        m = view.get("matched")
        return m is not None and _cmp(m, cond["op"], cond["value"])
    if t == "price_move":
        from . import ticks
        hist, now = view.get("history") or [], view.get("now")
        cur = (view.get("prices") or {}).get("back") or (view.get("prices") or {}).get("last")
        if not hist or now is None or not cur:
            return False
        old = [h for h in hist if h[0] <= now - cond["seconds"]]
        if not old or now - hist[0][0] < cond["seconds"] * 0.9:
            return False                      # not enough history yet
        then = old[-1][1]
        return _cmp(ticks.ticks_between(ticks.nearest(then), ticks.nearest(cur)), cond["op"], cond["value"])
    if t == "clock":
        now, s, e = view.get("clock", ""), cond["start"], cond["end"]
        return s <= now <= e if s <= e else (now >= s or now <= e)
    return False


def evaluate(script: dict, view: dict, fired: set[str]) -> list[tuple[dict, dict]]:
    """Rules that fire now, as (rule, action) pairs, in script order. A rule fires once; safety rules go first so they win."""
    out = []
    order = sorted(script["rules"], key=lambda r: 0 if r["kind"] == "safety" else 1)
    for r in order:
        if r["id"] in fired:
            continue
        if all(check(c, view, fired) for c in r["when"]):
            out.extend((r, a) for a in r["then"])
            if r["kind"] == "safety":
                break
    return out


def describe(script: dict) -> list[dict]:
    """Plain-English text for each rule, for the screens and for the AI's own check of what it drafted."""
    def c_txt(c):
        t = c["type"]
        if t == "price": return f"price ({c['ref']}) is {c['op']} {c['value']:g}"
        if t == "in_play": return "market is in-play" if c["value"] else "market is not yet in-play"
        if t == "set_number": return f"set number {c['op']} {c['value']:g}"
        if t == "serving": return "this player is serving" if c["value"] else "this player is receiving"
        if t == "game_points_diff": return f"points in the current game, this player minus opponent, {c['op']} {c['value']:g}"
        if t == "game_score_is": return f"game score is {c['me']}-{c['opp']} (this player first)"
        if t == "breaks_diff": return f"service breaks in this set, this player's minus the opponent's, {c['op']} {c['value']:g} (+1 = one break up)"
        if t == "break_point": return "this player is serving and facing a break point" if c["side"] == "against" else "this player has a break point on the opponent's serve"
        if t == "set_games_total": return f"games played in the set {c['op']} {c['value']:g}"
        if t == "prev_set_games_diff": return f"games margin in the previous set, this player minus opponent, {c['op']} {c['value']:g}"
        if t == "half_time": return "it is half time" if c["value"] else "it is not half time"
        if t == "set_games_diff": return f"games won in the current set, this player minus opponent, {c['op']} {c['value']:g} (negative = behind)"
        if t == "sets_diff": return f"sets won, this player minus opponent, {c['op']} {c['value']:g}"
        if t == "goals_total": return f"total goals {c['op']} {c['value']:g}"
        if t == "score_is": return f"score is {c['home']}-{c['away']}"
        if t == "minute": return f"minute {c['op']} {c['value']:g}"
        if t == "rule_matched": return f"rule {c['rule']} has matched"
        if t == "position_loss": return f"position loss {c['op']} £{c['value']:g}"
        if t == "ticks_from_entry": return f"exit price is {c['op']} {c['value']:g} ticks {'in profit' if c['value'] >= 0 else 'against you'} from where you were matched"
        if t == "ticks_from_peak": return f"the exit price has given back {c['value']:g} ticks from its best since you were matched (trailing stop)"
        if t == "minutes_to_start": return f"minutes to the scheduled start {c['op']} {c['value']:g}"
        if t == "spread_ticks": return f"spread between best back and lay {c['op']} {c['value']:g} ticks"
        if t == "market_matched": return f"matched on the market {c['op']} £{c['value']:,.0f}"
        if t == "price_move": return f"price moved {c['op']} {c['value']:g} ticks in the last {c['seconds']}s (+ drifting out, - shortening)"
        return f"time is {c['start']}–{c['end']}"

    def a_txt(a):
        t = a["type"]
        if t in ("back", "lay"):
            at = "at the best available price" if a["price"] == "best" else f"at {a['price']:g}"
            return f"{t.capitalize()} {at}, {a['basis']} £{a['stake']:g}, persistence {a['persistence']}"
        if t in ("green", "close") and a.get("percent"):
            return f"Take out {a['percent']}% of the position (a partial hedge), the rest stays open"
        return {"green": "Hedge to full green at the best available prices", "close": "Close the position at the best available prices",
                "stop": "Stop the script"}[t]
    return [{"id": r["id"], "kind": r["kind"], "if": [c_txt(c) for c in r["when"]],
             "then": [a_txt(a) for a in r["then"]] + ([f"Repeat up to {r['repeat']} times, one at a time, each after the exit has levelled the position"] if r.get("repeat", 1) > 1 else [])}
            for r in script["rules"]]


def headline(script: dict) -> str:
    """One line that says what a script does, for lists: entry action, how it exits, safety rules, repeats."""
    rules = script["rules"]
    ent = next((r for r in rules if r["kind"] == "entry"), None)
    parts = []
    if ent:
        a = ent["then"][0]
        parts.append(f"{a['type'].capitalize()} £{a['stake']:g} at {'best' if a['price'] == 'best' else format(a['price'], 'g')}")
    ex = [a["type"] for r in rules if r["kind"] == "exit" for a in r["then"]]
    if ex:
        parts.append("exit: " + "/".join(dict.fromkeys(ex)))
    n = sum(1 for r in rules if r["kind"] == "safety")
    if n:
        parts.append(f"{n} safety rule{'s' if n != 1 else ''}")
    if ent and ent.get("repeat", 1) > 1:
        parts.append(f"×{ent['repeat']}")
    return " · ".join(parts)


class ScriptStore:
    """Scripts with their version history. Editing creates a new version; plan rows follow the script by id, so renaming flows through."""

    def __init__(self, data: dict | None = None) -> None:
        d = data or {}
        self.scripts: dict[str, dict] = dict(d.get("scripts", {}))
        self._next = int(d.get("next", 1))

    def export(self) -> dict:
        return {"scripts": self.scripts, "next": self._next}

    def list(self) -> list[dict]:
        return [self.view(s) for s in sorted(self.scripts.values(), key=lambda s: s["updated"], reverse=True)]

    @staticmethod
    def view(s: dict) -> dict:
        cur = s["versions"][-1]
        return {"id": s["id"], "name": cur["name"], "sport": cur["sport"], "description": cur["description"], "rules": cur["rules"], "text": describe(cur), "headline": headline(cur),
                "version": len(s["versions"]), "origin": s["origin"], "enabled": s["enabled"], "updated": s["updated"],
                "history": [{"version": i + 1, "t": v["t"], "note": v["note"]} for i, v in enumerate(s["versions"])]}

    def get(self, sid: str) -> dict:
        if sid not in self.scripts:
            raise KeyError(sid)
        return self.scripts[sid]

    def current(self, sid: str) -> dict:
        return self.get(sid)["versions"][-1]

    def create(self, body: dict, origin: str = "you", note: str = "created") -> dict:
        clean = validate(body)
        sid = f"s{self._next}"
        self._next += 1
        self.scripts[sid] = {"id": sid, "origin": origin, "enabled": False, "updated": time.time(), "versions": [{**clean, "t": time.time(), "note": note}]}
        return self.view(self.scripts[sid])

    def update(self, sid: str, body: dict, note: str = "edited") -> dict:
        s = self.get(sid)
        clean = validate(body)
        s["versions"].append({**clean, "t": time.time(), "note": note})
        s["updated"] = time.time()
        return self.view(s)

    def set_enabled(self, sid: str, on: bool) -> dict:
        s = self.get(sid)
        s["enabled"] = on
        return self.view(s)

    def clone(self, sid: str, name: str) -> dict:
        cur = self.current(sid)
        return self.create({**cur, "name": name or f"Copy of {cur['name']}"}, "you", f"cloned from {cur['name']}")

    def delete(self, sid: str) -> None:
        self.get(sid)
        del self.scripts[sid]
