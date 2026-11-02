"""Probe api-tennis.com for (1) what a finished match's point-by-point and statistics contain and
(2) how far back fixtures go. Prints structure and counts only. Never prints keys.
Usage: python3 backend/tools/tennis_history_probe.py
"""
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from tennis_trial import get, load, SECRETS


def shape(x, depth=0, maxdepth=3):
    if depth >= maxdepth:
        return type(x).__name__
    if isinstance(x, dict):
        return {k: shape(v, depth + 1, maxdepth) for k, v in list(x.items())[:12]}
    if isinstance(x, list):
        return [f"list[{len(x)}]", shape(x[0], depth + 1, maxdepth)] if x else "list[0]"
    return type(x).__name__ if not isinstance(x, (str, int, float)) else repr(x)[:40]


def main():
    key = load(SECRETS + "tennis_api_key.env")["TENNIS_API_KEY"]
    yday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    fx, ms = get("get_fixtures", key, date_start=yday, date_stop=yday)
    done = [r for r in (fx.get("result") or []) if r.get("event_status") == "Finished" and r.get("pointbypoint")
            and "/" not in r.get("event_first_player", "")]
    print(f"Yesterday: {len(fx.get('result') or [])} fixtures, {len(done)} finished singles with point-by-point [{ms:.0f} ms]")
    if done:
        m = done[0]
        print("Match:", m["event_first_player"], "v", m["event_second_player"], "|", m.get("tournament_name"), "|", m.get("event_type_type"))
        print("scores:", json.dumps(m.get("scores"))[:200])
        pbp = m["pointbypoint"]
        print("pointbypoint structure:", json.dumps(shape(pbp), indent=1)[:1500])
        if isinstance(pbp, list) and pbp:
            print("First game raw:", json.dumps(pbp[0])[:700])
        print("statistics structure:", json.dumps(shape(m.get("statistics")), indent=1)[:1200])
    print("\nHistory depth (singles/doubles fixtures returned for one day at each age):")
    for label, days in [("1 month", 30), ("6 months", 183), ("1 year", 365), ("2 years", 730), ("3 years", 1095), ("5 years", 1825)]:
        d = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        try:
            r, ms = get("get_fixtures", key, date_start=d, date_stop=d)
            rows = r.get("result") or []
            withp = sum(1 for x in rows if x.get("pointbypoint"))
            print(f"  {label:9s} {d}: {len(rows)} fixtures, {withp} with point-by-point [{ms:.0f} ms]")
        except Exception as e:
            print(f"  {label:9s} {d}: error {type(e).__name__}")
    print("PROBE-COMPLETE")


main()
