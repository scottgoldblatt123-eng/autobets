"""Live match context for a Betfair market: score, clock and serve from the stored api-tennis / API-Football data.
Matching is by names and time. When nothing matches clearly the answer is None; we never guess."""
from __future__ import annotations

import datetime as dt
import difflib
import json
import re
import unicodedata

from .tennis.matching import same_player, split_event, tour_group

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
    def _find_tennis(self, info: dict):
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
        return hits[0][0], hits[0][1], a, b

    def _tennis(self, info: dict) -> dict | None:
        found = self._find_tennis(info)
        if not found:
            return None
        m, swapped, a, b = found
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
    def _find_football(self, info: dict):
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
            rows = self.football.db.execute("SELECT home, away, status, elapsed, goals_h, goals_a, ht_h, ht_a, kickoff, home_id, away_id, league_id, season FROM fixtures WHERE kickoff BETWEEN ? AND ?", (lo, hi)).fetchall()
        hits = [r for r in rows if same_team(r[0], h) and same_team(r[1], a)]
        if len(hits) != 1:
            return None
        return hits[0], h, a

    def _football(self, info: dict) -> dict | None:
        found = self._find_football(info)
        if not found:
            return None
        (home, away, status, elapsed, gh, ga, hh, ha, ko, *_), h, a = found
        return {"kind": "football", "source": "API-Football", "status": FOOTBALL_STATUS.get(status, status), "code": status,
                "live": status in ("1H", "HT", "2H", "ET", "BT", "P", "LIVE"), "elapsed": elapsed, "teams": [h, a],
                "goals": [gh, ga] if gh is not None else None, "ht": [hh, ha] if hh is not None else None, "kickoff": ko}


    def explain(self, info: dict) -> str:
        """Why no match was found for this market, in one line (shown in the Match info tab so a miss can be diagnosed)."""
        try:
            ev = info.get("event") or ""
            parts = [f"event '{ev}'", f"start {info.get('start')}"]
            names = split_event(ev)
            if names and self.tennis is not None:
                now = dt.datetime.now(dt.timezone.utc)
                days = [(now + dt.timedelta(days=d)).strftime("%Y-%m-%d") for d in (-1, 0, 1)]
                with self.tennis.lock:
                    rows = self.tennis.db.execute(f"SELECT raw FROM matches WHERE day IN ({','.join('?' * len(days))})", days).fetchall()
                near = []
                for (raw,) in rows:
                    m = json.loads(raw)
                    p1, p2 = m.get("event_first_player"), m.get("event_second_player")
                    if same_player(p1, names[0]) or same_player(p2, names[0]) or same_player(p1, names[1]) or same_player(p2, names[1]):
                        near.append(f"{p1} v {p2}")
                parts.append(f"tennis: {len(rows)} stored matches on those days, {len(near)} involving these names {near[:3]}")
            if self.football is not None:
                start = _iso(info.get("start"))
                if start:
                    lo, hi = (start - dt.timedelta(hours=3)).isoformat(), (start + dt.timedelta(hours=3)).isoformat()
                    with self.football.lock:
                        n = self.football.db.execute("SELECT COUNT(*) FROM fixtures WHERE kickoff BETWEEN ? AND ?", (lo, hi)).fetchone()[0]
                    parts.append(f"football: {n} stored fixtures within 3h of start; collected leagues are England (top two tiers), Germany, Spain, Italy, France and Scotland only")
                else:
                    parts.append("football: market has no usable start time")
            return "; ".join(parts)
        except Exception as e:
            return f"explain failed: {e!r}"

    # ---- richer match information: rankings, form, head-to-head ------------------------------------------------
    def details(self, info: dict) -> dict | None:
        try:
            if self.tennis is not None:
                d = self._tennis_details(info)
                if d:
                    return d
            if self.football is not None:
                return self._football_details(info)
        except Exception:
            return None
        return None

    def _tennis_details(self, info: dict) -> dict | None:
        found = self._find_tennis(info)
        if not found:
            return None
        m, swapped, a, b = found
        k1, k2 = m.get("first_player_key"), m.get("second_player_key")
        keys = [k2, k1] if swapped else [k1, k2]                      # in Betfair order
        tour = tour_group(m.get("event_type_type"))
        day = m.get("event_date") or ""
        db, lock = self.tennis.db, self.tennis.lock

        def finished_with(*ks):
            with lock:
                return db.execute("SELECT day, tournament, p1, p1_key, p2, p2_key, result, winner, type FROM matches WHERE status='Finished' AND day < ? AND "
                                  + " AND ".join(f"(p1_key={int(k)} OR p2_key={int(k)})" for k in ks) + " ORDER BY day DESC, time DESC LIMIT 60", (day,)).fetchall()

        def won(row, k):
            w = (row[7] or "")
            return w == ("First Player" if row[3] == k else "Second Player")

        players = []
        for name, k in zip((a, b), keys):
            rank = None
            if tour:
                with lock:
                    r = db.execute("SELECT data FROM standings WHERE tour=? ORDER BY day DESC LIMIT 1", (tour,)).fetchone()
                for x in (json.loads(r[0]) if r else []):
                    if str(x.get("player_key")) == str(k):
                        rank = {"place": x.get("place"), "points": x.get("points"), "country": x.get("country"), "movement": x.get("movement")}
                        break
            rows = finished_with(k)[:6]
            players.append({"name": name, "rank": rank, "form": [{"day": r[0], "opponent": r[4] if r[3] == k else r[2], "won": won(r, k), "score": r[6], "tournament": r[1]} for r in rows]})
        h2h_rows = [r for r in finished_with(keys[0], keys[1])][:8]
        h2h = [{"day": r[0], "tournament": r[1], "winner": a if won(r, keys[0]) else b, "score": r[6]} for r in h2h_rows]
        model_out = None
        try:
            if tour and day:
                from .tennis import ratings
                bo = 5 if tour == "ATP" and any(g in (m.get("tournament_name") or "").lower() for g in ("australian open", "french open", "roland", "wimbledon", "us open")) else 3
                model_out = ratings.price(ratings.build(self.tennis, tour, day), keys[0], keys[1], bo)
                if model_out:
                    from .tennis import model3
                    elo, _ = model3.ratings(self.tennis, day)
                    model_out["v3"] = model3.price(model_out["v2"]["p_a"] / 100, elo, keys[0], keys[1])
        except Exception:
            model_out = None
        return {"kind": "tennis", "tour": tour, "players": players, "model": model_out, "h2h": h2h, "h2h_wins": [sum(1 for x in h2h if x["winner"] == a), sum(1 for x in h2h if x["winner"] == b)],
                "note": "Head-to-head and form come from matches stored since the data collection began, so older meetings may be missing."}

    def _football_details(self, info: dict) -> dict | None:
        found = self._find_football(info)
        if not found:
            return None
        row, h, a = found
        home, away, hid, aid, league, season = row[0], row[1], row[9], row[10], row[11], row[12]
        db, lock = self.football.db, self.football.lock
        table = []
        with lock:
            r = db.execute("SELECT data FROM standings WHERE league_id=? AND season=? ORDER BY day DESC LIMIT 1", (league, season)).fetchone()
        try:
            for grp in ((json.loads(r[0]) or [{}])[0].get("league", {}).get("standings") or []) if r else []:
                table += grp
        except (IndexError, AttributeError, TypeError):
            table = []

        def team_row(tid):
            for x in table:
                if (x.get("team") or {}).get("id") == tid:
                    al = x.get("all") or {}
                    return {"place": x.get("rank"), "points": x.get("points"), "played": al.get("played"), "gd": x.get("goalsDiff"), "form": x.get("form"),
                            "record": f"{al.get('win')}-{al.get('draw')}-{al.get('lose')}"}
            return None

        def last(tid):
            with lock:
                rows = db.execute("SELECT kickoff, home_id, home, away, goals_h, goals_a FROM fixtures WHERE status IN ('FT','AET','PEN') AND (home_id=? OR away_id=?) AND kickoff < ? ORDER BY kickoff DESC LIMIT 6", (tid, tid, row[8])).fetchall()
            out = []
            for k, hi_, hn, an, gh, ga in rows:
                us, them = (gh, ga) if hi_ == tid else (ga, gh)
                out.append({"day": (k or "")[:10], "opponent": an if hi_ == tid else hn, "venue": "H" if hi_ == tid else "A", "score": f"{gh}-{ga}", "result": "W" if us > them else "D" if us == them else "L"})
            return out

        with lock:
            hrows = db.execute("SELECT kickoff, home_id, home, away, goals_h, goals_a FROM fixtures WHERE status IN ('FT','AET','PEN') AND ((home_id=? AND away_id=?) OR (home_id=? AND away_id=?)) AND kickoff < ? ORDER BY kickoff DESC LIMIT 8", (hid, aid, aid, hid, row[8])).fetchall()
        h2h = [{"day": (k or "")[:10], "home": hn, "away": an, "score": f"{gh}-{ga}"} for k, _, hn, an, gh, ga in hrows]
        wins = [0, 0]
        for k, hi_, hn, an, gh, ga in hrows:
            if gh == ga:
                continue
            winner_id = hi_ if gh > ga else (aid if hi_ == hid else hid)
            wins[0 if winner_id == hid else 1] += 1
        try:
            from .football import model as fbmodel
            fb_model = fbmodel.predict(db, lock, league, row[8], hid, aid)
        except Exception:
            fb_model = None
        return {"kind": "football", "league": league, "fmodel": fb_model, "teams": [{"name": h, "table": team_row(hid), "form": last(hid)}, {"name": a, "table": team_row(aid), "form": last(aid)}],
                "h2h": h2h, "h2h_wins": wins}
