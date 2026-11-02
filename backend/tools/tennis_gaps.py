"""Why are matches skipped? Breaks down stored matches that cannot be turned into player rows.
Usage: python3 backend/tools/tennis_gaps.py [TOUR]"""
import collections, json, os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.tennis import tables
tour = sys.argv[1] if len(sys.argv) > 1 else "ATP"
db = sqlite3.connect("/opt/autobets/data/tennis.db")
reason, month, rnd, tourn = (collections.Counter() for _ in range(4)); ok = collections.Counter()
for raw, d, has in db.execute("SELECT raw,date,has_stats FROM matches WHERE tour=? AND status='Finished'", (tour,)):
    m = json.loads(raw); mo = d[:7]
    if tables.parse_match(m):
        ok[mo] += 1; continue
    st = m.get("statistics") or []
    per = {s.get("stat_period") for s in st}
    if not st: why = "no statistics at all"
    elif "match" not in per: why = "statistics but no 'match' period"
    else:
        have = {(s["stat_type"], s["stat_name"]) for s in st if s.get("stat_period") == "match" and s.get("stat_total") is not None}
        miss = [n for t, n in (("Points", "Service Points Won"), ("Points", "Return Points Won"), ("Games", "Service games won"), ("Games", "Return games won")) if (t, n) not in have]
        why = "match period missing: " + ", ".join(miss) if miss else "other"
    reason[why] += 1; month[mo] += 1; rnd[m.get("tournament_round") or "?"] += 1
    tourn[m.get("tournament_name")] += 1
print(f"{tour}: usable {sum(ok.values())}, skipped {sum(reason.values())}")
for k, v in reason.most_common(8): print(f"  {v:5d}  {k}")
print("Skipped by month (skipped/usable):")
for mo in sorted(set(month) | set(ok)): print(f"  {mo}: {month[mo]}/{ok[mo]}")
print("Top rounds skipped:", rnd.most_common(6))
print("Top tournaments skipped:", tourn.most_common(8))
