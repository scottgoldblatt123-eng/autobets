"""Live match context for a Betfair market: score, clock and serve from the stored api-tennis / API-Football data.
Matching is by names and time. When nothing matches clearly the answer is None; we never guess."""
from __future__ import annotations

import datetime as dt
import difflib
import json
import re
import unicodedata

from .tennis.matching import same_player, split_event

FOOTBALL_STATUS = {"NS": "Not started", "TBD": "Time to be defined", "1H": "First half", "HT": "Half time", "2H": "Second half", "ET": "Extra time",
                   "BT": "Break", "P": "Penalties", "SUSP": "Suspended", "INT": "Interrupted", "FT": "Full time", "AET": "After extra time",
                   "PEN": "After penalties", "PST": "Postponed", "CANC": "Cancelled", "ABD": "Abandoned", "LIVE": "Live"}
_NOISE = {"fc", "afc", "cf", "sc", "ac", "as", "us", "ssc", "rc", "rcd", "ud", "cd", "sv", "vfb", "vfl", "fsv", "tsg", "the", "club", "de", "1899", "04", "05", "09", "1860"}


def _team_tokens(name: str) -> list[str]:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s.replace("&", " and "))
    return [t for t in s.split() if t not in _NOISE]


def same_team(a: str, b: str) -> bool:
    """'Man Utd' / 'Manchester United', 'Bayern Munich' / 'Bayern München', 'Atletico Madrid' / 'Atlético de Madrid'."""
    ta, tb = _team_tokens(a), _team_tokens(b)
    if not ta or not tb:
        return False
    ja, jb = " ".join(ta), " ".join(tb)
    if ja == jb or set(ta) <= set(tb) or set(tb) <= set(ta):
        return True
    if difflib.SequenceMatcher(None, ja, jb).ratio() >= 0.82:
        return True
    abbr = {"man": "manchester", "utd": "united", "wolves": "wolverhampton", "spurs": "tottenham", "inter": "internazionale", "psg": "paris"}
    ex = lambda ts: [abbr.get(t, t) for t in ts]
    ea, eb = ex(ta), ex(tb)
    return set(ea) <= set(eb) or set(eb) <= set(ea)


def _iso(x) -> dt.datetime | None:
    try:
        d = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


class MatchContext:
    def __init__(self, tennis=None, football=None):
        self.tennis, self.football = tennis, football          # the live stores, or None when that collector is off

    def for_market(self, info: dict) -> dict | None:
        try:
            if self.tennis is not None:
                t = self._tennis(info)
                if t:
                    return t
            if self.football is not None:
                return self._football(info)
        except Exception:      # context is decoration: a bad row must never break the trading screen
            return None
        return None

    # ---- tennis -----------------------------------------------------------------------------------------------
    def _tennis(self, info: dict) -> dict | None:
        names = split_event(info.get("event") or "")
        if not names:
            return None
        a, b = names
        now = dt.datetime.now(dt.timezone.utc)
        days = [(now + dt.timedelta(days=d)).strftime("%Y-%m-%d") for d in (-1, 0, 1)]
        with self.tennis.lock:
            rows = self.tennis.db.execute(f"SELECT raw FROM matches WHERE day IN ({','.join('?' * len(days))})", days).fetchall()
        hits = []
        for (raw,) in rows:
            m = json.loads(raw)
            p1, p2 = m.get("event_first_player"), m.get("event_second_player")
            if same_player(p1, a) and same_player(p2, b):
                hits.append((m, False))
            elif same_player(p1, b) and same_player(p2, a):
                hits.append((m, True))
        if len(hits) != 1:
            return None                      # none, or ambiguous (two matches, e.g. a rematch on consecutive days): say nothing
        m, swapped = hits[0]
        sets = [(s.get("score_first"), s.get("score_second")) for s in (m.get("scores") or [])]
        if swapped:
            sets = [(y, x) for x, y in sets]
        res = (m.get("event_final_result") or "").split(" - ")
        if len(res) == 2 and swapped:
            res = res[::-1]
        game = (m.get("event_game_result") or "").split(" - ")
        if len(game) == 2 and swapped and game != ["-"]:
            game = game[::-1]
        serve = {"First Player": 0, "Second Player": 1}.get(m.get("event_serve") or "")
        if serve is not None and swapped:
            serve = 1 - serve
        return {"kind": "tennis", "source": "api-tennis", "status": m.get("event_status"), "live": str(m.get("event_live")) == "1",
                "tournament": m.get("tournament_name"), "round": m.get("tournament_round"),
                "players": [a, b], "sets": [list(s) for s in sets], "sets_won": res if len(res) == 2 else None,
                "game": game if len(game) == 2 and game != ["-"] else None, "serving": serve}

    # ---- football ---------------------------------------------------------------------------------------------
    def _football(self, info: dict) -> dict | None:
        ev = info.get("event") or ""
        for sep in (" v ", " vs "):
            if sep in ev:
                h, a = [x.strip() for x in ev.split(sep, 1)]
                break
        else:
            return None
        start = _iso(info.get("start"))
        if not start:
            return None
        lo, hi = (start - dt.timedelta(hours=3)).isoformat(), (start + dt.timedelta(hours=3)).isoformat()
        with self.football.lock:
            rows = self.football.db.execute("SELECT home, away, status, elapsed, goals_h, goals_a, ht_h, ht_a, kickoff FROM fixtures WHERE kickoff BETWEEN ? AND ?", (lo, hi)).fetchall()
        hits = [r for r in rows if same_team(r[0], h) and same_team(r[1], a)]
        if len(hits) != 1:
            return None
        home, away, status, elapsed, gh, ga, hh, ha, ko = hits[0]
        return {"kind": "football", "source": "API-Football", "status": FOOTBALL_STATUS.get(status, status), "code": status,
                "live": status in ("1H", "HT", "2H", "ET", "BT", "P", "LIVE"), "elapsed": elapsed, "teams": [h, a],
                "goals": [gh, ga] if gh is not None else None, "ht": [hh, ha] if hh is not None else None, "kickoff": ko}
