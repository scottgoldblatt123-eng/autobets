"""Validate point-by-point derived service/return games against the reported statistics, on matches that have both."""
import json, os, sqlite3, sys, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.tennis import tables
db = sqlite3.connect("/opt/autobets/data/tennis.db")
n = same = 0; diffs = []
for tour in ("ATP", "WTA"):
    for (raw,) in db.execute("SELECT raw FROM matches WHERE tour=? AND status='Finished' AND date>='2026-03-01' LIMIT 1500", (tour,)):
        m = json.loads(raw); rep = tables.parse_match(copy.deepcopy(m))
        if not rep: continue
        out = {k: {kk: v for kk, v in d.items() if kk not in ("hold", "rgw")} for k, d in rep.items()}
        if not tables.derive_games(m, out): continue
        n += 1
        ok = all(out[k]["hold"] == rep[k]["hold"] and out[k]["rgw"] == rep[k]["rgw"] for k in rep)
        same += ok
        if not ok and len(diffs) < 5:
            diffs.append((m.get("event_first_player"), m.get("event_second_player"), {k: (rep[k]["hold"], out[k]["hold"]) for k in rep}))
print(f"matches with both: {n}; derived equals reported: {same} ({100*same/max(n,1):.1f}%)")
for d in diffs: print("  mismatch:", d)
