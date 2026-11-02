"""Find why point-by-point games differ from reported games: per-set comparison for a few mismatched matches."""
import collections, json, os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.tennis import tables
db = sqlite3.connect("/opt/autobets/data/tennis.db"); shown = 0
for (raw,) in db.execute("SELECT raw FROM matches WHERE tour='ATP' AND status='Finished' AND date>='2026-03-01'"):
    m = json.loads(raw); rep = tables.parse_match(m)
    if not rep: continue
    a = str(m["first_player_key"]); out = {k: {} for k in rep}
    if not tables.derive_games(m, out) or all(out[k]["hold"] == rep[k]["hold"] for k in rep): continue
    print(f"\n{m['event_first_player']} v {m['event_second_player']} | {m['tournament_name']} {m.get('tournament_round')} | result {m.get('event_final_result')} | scores {[(x.get('score_first'), x.get('score_second')) for x in m.get('scores', [])]}")
    print("  match reported service games (won,total) first/second:", rep[a]["hold"], [rep[k]["hold"] for k in rep if k != a])
    for sset in ("set1", "set2", "set3", "set4", "set5"):
        r = [(s["player_key"], s["stat_won"], s["stat_total"]) for s in m["statistics"] if s["stat_period"] == sset and s["stat_name"] == "Service games won"]
        if r: print(f"  reported {sset} service games:", r)
    per = collections.defaultdict(lambda: [0, 0])
    for g in m["pointbypoint"]:
        per[(g["set_number"], g["player_served"])][1] += 1
        per[(g["set_number"], g["player_served"])][0] += g["serve_winner"] == g["player_served"]
    print("  point-by-point (set, server) -> (held, played):", dict(per))
    print("  first 3 pbp games:", [(g["set_number"], g["number_game"], g["player_served"], g["serve_winner"], g["score"]) for g in m["pointbypoint"][:3]])
    shown += 1
    if shown >= 3: break
