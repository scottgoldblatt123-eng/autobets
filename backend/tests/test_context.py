import datetime as dt
from autobets.context import MatchContext, same_team
from autobets.football.store import FootballStore
from autobets.tennis.livestore import TennisStore


def today(): return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def tm(key, p1, p2, **kw):
    return {"event_key": key, "event_date": today(), "event_time": "12:00", "event_type_type": "Atp Singles", "tournament_name": "Paris", "tournament_round": "Quarter",
            "event_first_player": p1, "first_player_key": 1, "event_second_player": p2, "second_player_key": 2, "event_status": kw.get("status", "Set 2"),
            "event_final_result": kw.get("result", "1 - 0"), "event_live": "1", "event_game_result": kw.get("game", "30 - 15"), "event_serve": kw.get("serve", "First Player"),
            "scores": [{"score_first": "6", "score_second": "4"}, {"score_first": "2", "score_second": "3"}]}


def test_team_names_match_across_sources():
    assert same_team("Man Utd", "Manchester United") and same_team("Bayern Munich", "Bayern München") and same_team("Atletico Madrid", "Atlético de Madrid")
    assert same_team("Wolves", "Wolverhampton Wanderers") and same_team("Tottenham", "Tottenham Hotspur")
    assert not same_team("Manchester United", "Manchester City") and not same_team("Real Madrid", "Real Sociedad")


def test_tennis_context_in_betfair_order_even_when_the_api_lists_them_the_other_way():
    st = TennisStore(); st.upsert(tm(1, "C. Alcaraz", "J. Sinner", serve="First Player"))
    c = MatchContext(tennis=st).for_market({"event": "Jannik Sinner v Carlos Alcaraz"})
    assert c["players"] == ["Jannik Sinner", "Carlos Alcaraz"]
    assert c["sets"] == [["4", "6"], ["3", "2"]] and c["sets_won"] == ["0", "1"] and c["game"] == ["15", "30"] and c["serving"] == 1


def test_tennis_ambiguous_or_missing_match_says_nothing():
    st = TennisStore(); st.upsert(tm(1, "J. Sinner", "C. Alcaraz")); st.upsert(tm(2, "J. Sinner", "C. Alcaraz"))
    assert MatchContext(tennis=st).for_market({"event": "Jannik Sinner v Carlos Alcaraz"}) is None
    assert MatchContext(tennis=TennisStore()).for_market({"event": "Jannik Sinner v Carlos Alcaraz"}) is None
    assert MatchContext(tennis=st).for_market({"event": "A. Player / B. Player v C. Player / D. Player"}) is None      # doubles


def test_football_context_needs_both_teams_and_a_close_kickoff():
    st = FootballStore()
    ko = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    for fid, h, a in ((1, "Manchester United", "Liverpool"), (2, "Chelsea", "Arsenal")):
        st.upsert_fixture({"fixture": {"id": fid, "date": ko.isoformat(), "status": {"short": "1H", "elapsed": 34}}, "league": {"id": 39, "season": 2026},
                           "teams": {"home": {"id": 1, "name": h}, "away": {"id": 2, "name": a}}, "goals": {"home": 1, "away": 0}, "score": {"halftime": {}}})
    c = MatchContext(football=st).for_market({"event": "Man Utd v Liverpool", "start": ko.isoformat()})
    assert c["goals"] == [1, 0] and c["elapsed"] == 34 and c["live"] and c["status"] == "First half"
    assert MatchContext(football=st).for_market({"event": "Man Utd v Liverpool", "start": (ko + dt.timedelta(days=2)).isoformat()}) is None
    assert MatchContext(football=st).for_market({"event": "Everton v Fulham", "start": ko.isoformat()}) is None


def test_tennis_details_have_rank_form_and_head_to_head_in_betfair_order():
    st = TennisStore()
    def old(key, day, w, p1k=1, p2k=2, p1="J. Sinner", p2="C. Alcaraz"):
        m = tm(key, p1, p2, status="Finished", result="2 - 1"); m.update(event_date=day, event_live="0", event_winner=w, first_player_key=p1k, second_player_key=p2k, event_first_player=p1, event_second_player=p2); return m
    st.upsert(old(10, "2026-09-01", "First Player")); st.upsert(old(11, "2026-08-01", "Second Player"))
    live = tm(1, "C. Alcaraz", "J. Sinner"); live.update(first_player_key=2, second_player_key=1); st.upsert(live)
    st.save_standings("ATP", today(), [{"place": "1", "player": "J. Sinner", "player_key": 1, "points": "11000", "country": "ITA"}, {"place": "2", "player": "C. Alcaraz", "player_key": 2, "points": "9000", "country": "ESP"}])
    d = MatchContext(tennis=st).details({"event": "Jannik Sinner v Carlos Alcaraz"})
    assert [p["name"] for p in d["players"]] == ["Jannik Sinner", "Carlos Alcaraz"]
    assert d["players"][0]["rank"]["place"] == "1" and d["players"][1]["rank"]["points"] == "9000"
    assert d["h2h_wins"] == [1, 1] and len(d["h2h"]) == 2 and d["players"][0]["form"][0]["won"] is True


def test_football_details_have_table_form_and_head_to_head():
    st = FootballStore(); ko = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    def fx(fid, h, a, gh, ga, when, status="FT", hid=1, aid=2):
        st.upsert_fixture({"fixture": {"id": fid, "date": when.isoformat(), "status": {"short": status, "elapsed": 90}}, "league": {"id": 39, "season": 2026},
                           "teams": {"home": {"id": hid, "name": h}, "away": {"id": aid, "name": a}}, "goals": {"home": gh, "away": ga}, "score": {"halftime": {}}})
    fx(1, "Manchester United", "Liverpool", None, None, ko, "NS")
    fx(2, "Liverpool", "Manchester United", 2, 0, ko - dt.timedelta(days=60), hid=2, aid=1)
    fx(3, "Manchester United", "Liverpool", 1, 1, ko - dt.timedelta(days=200))
    st.save_standings(39, 2026, today(), [{"league": {"standings": [[{"rank": 3, "team": {"id": 1}, "points": 20, "goalsDiff": 5, "form": "WWDLW", "all": {"played": 10, "win": 6, "draw": 2, "lose": 2}}]]}}])
    d = MatchContext(football=st).details({"event": "Man Utd v Liverpool", "start": ko.isoformat()})
    assert d["teams"][0]["table"]["place"] == 3 and d["teams"][1]["table"] is None
    assert d["h2h_wins"] == [0, 1] and len(d["h2h"]) == 2 and d["teams"][0]["form"][0]["result"] == "L"
