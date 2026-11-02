"""Show tour counts and the exact layout of statistics / point-by-point in the raw store."""
import json, sqlite3, collections
db = sqlite3.connect("/opt/autobets/data/tennis.db")
print("By tour / surface:")
for t, s, n in db.execute("SELECT tour, coalesce(surface,'?'), count(*) FROM matches GROUP BY 1,2 HAVING count(*)>150 ORDER BY 1,3 DESC"):
    print(f"  {t:4s} {s:16s} {n}")
print("Date range:", db.execute("SELECT min(date), max(date) FROM matches").fetchone())
row = db.execute("SELECT raw FROM matches WHERE tour='ATP' AND has_stats=1 ORDER BY date DESC LIMIT 1").fetchone()
m = json.loads(row[0])
print("\nFixture keys:", sorted(m.keys()))
print("Players:", m.get("event_first_player"), "v", m.get("event_second_player"), "| result:", m.get("event_final_result"), "| status:", m.get("event_status"))
st = m["statistics"]
print("\nstatistics: type", type(st).__name__, "len", len(st))
print("distinct (period,type,name):")
seen = collections.OrderedDict()
for x in st:
    seen[(x.get("stat_period"), x.get("stat_type"), x.get("stat_name"))] = x
for k, x in list(seen.items())[:60]:
    print(" ", k, "->", {a: b for a, b in x.items() if a not in ("stat_period", "stat_type", "stat_name")})
pb = m["pointbypoint"]
print("\npointbypoint: type", type(pb).__name__, "len", len(pb))
print(json.dumps(pb[0] if isinstance(pb, list) else pb)[:900])
