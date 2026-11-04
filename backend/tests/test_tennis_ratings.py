import json
from autobets.tennis import ratings
from autobets.tennis.livestore import TennisStore


def stat(pk, t, n, w, tot, period="match"):
    return {"stat_period": period, "player_key": pk, "stat_type": t, "stat_name": n, "stat_value": "x", "stat_won": w, "stat_total": tot}


def match(i, day, p1, p2, s1, s2):
    stats = []
    for pk, (svc, ret, hold, rg) in ((p1, s1), (p2, s2)):
        stats += [stat(pk, "Points", "Service Points Won", svc, 100), stat(pk, "Points", "Return Points Won", ret, 100),
                  stat(pk, "Games", "Service games won", hold, 12), stat(pk, "Games", "Return games won", rg, 12)]
    return {"event_key": i, "event_date": day, "event_time": "10:00", "event_type_type": "Wta Singles", "tournament_name": "T", "tournament_season": "2026",
            "event_first_player": f"P{p1}", "first_player_key": p1, "event_second_player": f"P{p2}", "second_player_key": p2,
            "event_status": "Finished", "event_final_result": "2 - 0", "event_winner": "First Player", "event_live": "0", "statistics": stats}


def test_table_and_price_no_lookahead():
    st = TennisStore()
    i = 0
    for rnd in range(6):                                    # strong player 1 beats weak player 2 six times, plus 20 filler players
        i += 1; st.upsert(match(i, f"2026-10-0{rnd + 1}", 1, 2, (68, 46, 11, 8), (55, 34, 4, 1)))
    for k in range(3, 23):
        for j in range(5):
            i += 1; st.upsert(match(i, f"2026-09-1{j}", k, k + 100, (60, 40, 9, 5), (60, 40, 9, 5)))
    rows = ratings.build(st, "WTA", "2026-10-05")
    assert rows["1"]["matches"] == 4                         # only matches before the day
    rows = ratings.build(st, "WTA", "2026-11-01")
    out = ratings.price(rows, 1, 2)
    assert out["v2"]["p_a"] > 70 and out["v1"]["version"] == "v1-sheet"
    assert ratings.price(rows, 1, 999) is None
