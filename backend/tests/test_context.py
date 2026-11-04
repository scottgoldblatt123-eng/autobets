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
