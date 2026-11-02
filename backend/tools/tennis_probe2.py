"""Second api-tennis.com probe: where are statistics filled, and does the API expose surface,
rankings and player data? Prints structure and counts only; never keys.
Usage: python3 backend/tools/tennis_probe2.py
"""
import collections, datetime as dt, json, os, sys, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
from tennis_trial import get, load, SECRETS
from tennis_history_probe import shape


def main():
    key = load(SECRETS + "tennis_api_key.env")["TENNIS_API_KEY"]
    d0 = dt.date.today() - dt.timedelta(days=7)
    fx, _ = get("get_fixtures", key, date_start=d0.isoformat(), date_stop=(dt.date.today() - dt.timedelta(days=1)).isoformat())
    rows = [r for r in (fx.get("result") or []) if r.get("event_status") == "Finished"]
    print(f"Finished matches in the last 7 days: {len(rows)}")
    by = collections.defaultdict(lambda: [0, 0, 0])
    for r in rows:
        t = r.get("event_type_type", "?")
        by[t][0] += 1
        by[t][1] += 1 if r.get("statistics") else 0
        by[t][2] += 1 if r.get("pointbypoint") else 0
    print("By event type: total / with statistics / with point-by-point")
    for t, (n, s, p) in sorted(by.items(), key=lambda x: -x[1][0]):
        print(f"  {t:28s} {n:4d} / {s:4d} / {p:4d}")
    withstats = [r for r in rows if r.get("statistics")]
    if withstats:
        m = withstats[0]
        print("\nExample with statistics:", m.get("event_first_player"), "v", m.get("event_second_player"), "|", m.get("tournament_name"))
        st = m["statistics"]
        print("statistics sample:", json.dumps(st[:12] if isinstance(st, list) else st)[:1400])
    print("\nOther API methods (names from memory; errors are informative):")
    for method, extra in [("get_events", {}), ("get_tournaments", {}), ("get_standings", {"event_type": "WTA"}),
                          ("get_players", {"player_key": rows[0].get("first_player_key")} if rows else {}),
                          ("get_H2H", {"first_player_key": rows[0].get("first_player_key"), "second_player_key": rows[0].get("second_player_key")} if rows else {})]:
        try:
            r, ms = get(method, key, **extra)
            res = r.get("result")
            n = len(res) if hasattr(res, "__len__") else "-"
            print(f"  {method:16s} ok={r.get('success')} items={n} [{ms:.0f} ms]  sample: {json.dumps(shape(res if not isinstance(res, list) or not res else res[0], maxdepth=2))[:420]}")
        except urllib.error.HTTPError as e:
            print(f"  {method:16s} HTTP {e.code}")
        except Exception as e:
            print(f"  {method:16s} {type(e).__name__}: {str(e)[:100]}")
    surf = [k for r in rows[:1] for k in r.keys() if "surface" in k.lower() or "court" in k.lower()]
    print("\nSurface-like fields on a fixture:", surf or "none found")
    print("PROBE2-COMPLETE")


main()
