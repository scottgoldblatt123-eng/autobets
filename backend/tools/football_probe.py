"""API-Football probe: plan, coverage of the six leagues, and live behaviour.
Usage (server):
  python3 backend/tools/football_probe.py                 # status + coverage + what is live right now
  python3 backend/tools/football_probe.py --watch 30      # also poll live fixtures every 15 s for 30 min,
                                                          # logging every score/minute change to /opt/autobets/data/football_live.jsonl
Never prints the key, name or email."""
import argparse, json, os, sys, time, urllib.request, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from tennis_trial import load, SECRETS

BASE = "https://v3.football.api-sports.io/"
LEAGUES = {39: "England Premier League", 78: "Germany Bundesliga", 140: "Spain La Liga",
           135: "Italy Serie A", 61: "France Ligue 1", 179: "Scotland Premiership"}
LOG = "/opt/autobets/data/football_live.jsonl"


def get(path, key, **q):
    url = BASE + path + ("?" + "&".join(f"{k}={v}" for k, v in q.items()) if q else "")
    req = urllib.request.Request(url, headers={"x-apisports-key": key})
    t = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read()); h = r.headers
    return body, (time.time() - t) * 1000, h.get("x-ratelimit-requests-remaining")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--watch", type=int, default=0); a = ap.parse_args()
    key = load(SECRETS + "api_football_key.env")["API_FOOTBALL_KEY"]
    b, ms, rem = get("status", key)
    r = b.get("response") or {}
    if isinstance(r, dict):
        print("plan:", (r.get("subscription") or {}).get("plan"), "| active:", (r.get("subscription") or {}).get("active"),
              "| requests today:", (r.get("requests") or {}).get("current"), "of", (r.get("requests") or {}).get("limit_day"), f"[{ms:.0f} ms]")
    else:
        print("status response:", str(b.get("errors"))[:200])
    print("\nCoverage, current season (2026):")
    for lid, name in LEAGUES.items():
        b, _, _ = get("leagues", key, id=lid, season=2026)
        if b.get("errors"): print(f"  {name}: ERROR {str(b['errors'])[:140]}"); continue
        resp = b.get("response") or []
        if not resp: print(f"  {name}: no data for season 2026"); continue
        s = [x for x in resp[0]["seasons"] if x["year"] == 2026]
        c = (s[0]["coverage"] if s else {})
        f = c.get("fixtures", {})
        print(f"  {name:24s} events={f.get('events')} lineups={f.get('lineups')} stats={f.get('statistics_fixtures')} odds={c.get('odds')}")
    b, ms, rem = get("fixtures", key, live="all")
    live = b.get("response") or []
    mine = [x for x in live if x["league"]["id"] in LEAGUES]
    print(f"\nLive right now: {len(live)} fixtures worldwide, {len(mine)} in the six leagues [{ms:.0f} ms, quota left {rem}]")
    for x in mine:
        print(f"  {x['league']['name']}: {x['teams']['home']['name']} {x['goals']['home']}-{x['goals']['away']} {x['teams']['away']['name']} ({x['fixture']['status']['elapsed']}')")
    if b.get("errors"): print("errors:", str(b["errors"])[:200])
    if a.watch:
        print(f"\nWatching six leagues for {a.watch} min, polling every 15 s -> {LOG}")
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        last, end = {}, time.time() + a.watch * 60
        while time.time() < end:
            try:
                b, ms, rem = get("fixtures", key, live="all")
                for x in b.get("response") or []:
                    if x["league"]["id"] not in LEAGUES: continue
                    fid = x["fixture"]["id"]
                    state = (x["goals"]["home"], x["goals"]["away"], x["fixture"]["status"]["short"], x["fixture"]["status"]["elapsed"], len(x.get("events") or []))
                    if last.get(fid) != state:
                        last[fid] = state
                        rec = {"t": dt.datetime.utcnow().isoformat(), "fixture": fid, "league": x["league"]["name"],
                               "home": x["teams"]["home"]["name"], "away": x["teams"]["away"]["name"],
                               "score": state[:2], "status": state[2], "elapsed": state[3], "events": state[4]}
                        open(LOG, "a").write(json.dumps(rec) + "\n")
                        print(rec["t"][11:19], rec["home"], state[0], "-", state[1], rec["away"], f"{state[3]}'", state[2], f"events={state[4]}", flush=True)
            except Exception as e:
                print("poll error:", type(e).__name__, str(e)[:100], flush=True)
            time.sleep(15)
    print("FOOTBALL-PROBE-COMPLETE")


main()
