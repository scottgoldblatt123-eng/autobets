"""api-tennis.com trial test. Compares their coverage with the tennis matches Betfair lists, checks
whether live scores and point-by-point data are present, and measures response time.
Usage (on the server): python3 backend/tools/tennis_trial.py
Reads /opt/autobets/secrets/tennis_api_key.env and betfair.env. Never prints keys.
NOTE: endpoint and field names are from memory of the provider's docs and must be confirmed on the trial.
"""
import datetime as dt, json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = "https://api.api-tennis.com/tennis/"
SECRETS = "/opt/autobets/secrets/"


def surname(name: str) -> str:
    """Last word of a player name, lowercase, accents/punctuation stripped. 'N. Djokovic' -> 'djokovic'."""
    name = re.sub(r"[^A-Za-zÀ-ſ\- ]", " ", name or "").strip().lower()
    parts = [p for p in name.split() if len(p) > 1] or name.split()
    return parts[-1] if parts else ""


def split_event(event_name: str):
    for sep in (" v ", " vs ", " - "):
        if sep in event_name:
            a, b = event_name.split(sep, 1)
            return surname(a), surname(b)
    return None


def tokens(name: str) -> set[str]:
    name = re.sub(r"[^A-Za-z\u00c0-\u017f\- ]", " ", name or "").lower()
    return {t for t in name.replace("-", " ").split() if len(t) > 1}


def same_player(a: str, b: str) -> bool:
    """Betfair 'Da Merida' vs API 'Daniel Merida Aguilar': every word of the shorter name is the start
    of some word in the other (so 'da' matches 'daniel'), or the surnames match."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if all(any(w.startswith(t) for w in long_) for t in short):
        return True
    return surname(a) == surname(b)


def coverage(betfair_events: list[str], api_matches: list[tuple[str, str]]):
    """Singles only. Doubles ('A/B v C/D') are returned separately."""
    hit, miss, doubles = [], [], []
    for ev in betfair_events:
        if "/" in ev:
            doubles.append(ev)
            continue
        pair = None
        for sep in (" v ", " vs "):
            if sep in ev:
                pair = tuple(x.strip() for x in ev.split(sep, 1))
                break
        if not pair:
            continue
        ok = any((same_player(pair[0], a) and same_player(pair[1], b)) or
                 (same_player(pair[0], b) and same_player(pair[1], a)) for a, b in api_matches)
        (hit if ok else miss).append(ev)
    return hit, miss, doubles


def get(method: str, key: str, **params):
    q = urllib.parse.urlencode({"method": method, "APIkey": key, **params})
    t = time.time()
    with urllib.request.urlopen(f"{BASE}?{q}", timeout=30) as r:
        data = json.loads(r.read())
    return data, (time.time() - t) * 1000


def load(path):
    env = {}
    for line in open(path):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            env[k] = v
    return env


def main():
    key = load(SECRETS + "tennis_api_key.env")["TENNIS_API_KEY"]
    today = dt.date.today().isoformat()
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    fx, ms = get("get_fixtures", key, date_start=today, date_stop=tomorrow)
    print(f"get_fixtures [{ms:.0f} ms] success={fx.get('success')} keys={list(fx.keys())}")
    rows = fx.get("result") or []
    if not rows:
        print("No fixtures returned. Raw start of response:", json.dumps(fx)[:300]); return
    print("Fields in a fixture:", sorted(rows[0].keys()))
    matches = [(r.get("event_first_player", ""), r.get("event_second_player", "")) for r in rows]
    print(f"Fixtures today and tomorrow: {len(rows)}")
    live, ms = get("get_livescore", key)
    lrows = live.get("result") or []
    print(f"get_livescore [{ms:.0f} ms]: {len(lrows)} live matches")
    if lrows:
        r0 = lrows[0]
        print("Live fields:", sorted(r0.keys()))
        print("Has point-by-point:", bool(r0.get("pointbypoint")), "| has scores:", bool(r0.get("scores")))
    try:
        from autobets.exchange.betfair import BetfairAdapter
        bf = BetfairAdapter.from_env_file(SECRETS + "betfair.env")
        mk = bf.list_markets("2", max_results=200)
        events = [m["event"] for m in mk]
        hit, miss, doubles = coverage(events, matches)
        pct = 100 * len(hit) / max(1, len(hit) + len(miss))
        print(f"Betfair singles checked: {len(hit)+len(miss)} | found in api-tennis: {len(hit)} ({pct:.0f}%) | doubles skipped: {len(doubles)}")
        for m in miss[:15]:
            print("  missing:", m)
    except Exception as e:
        print("Betfair comparison skipped:", type(e).__name__, str(e)[:120])
    print("TRIAL-CHECK-COMPLETE")


if __name__ == "__main__":
    main()
