import datetime as dt
import pytest
from autobets.tennis.apitennis import ApiTennis, ApiTennisError, wanted
from autobets.tennis.collector import TennisCollector, HISTORY_DAYS, CHUNK
from autobets.tennis.livestore import TennisStore


def match(key, status="Finished", typ="Atp Singles", live="0", result="2 - 0", day="2026-11-04", t="12:00"):
    return {"event_key": key, "event_date": day, "event_time": t, "event_type_type": typ, "tournament_name": "T", "event_first_player": "A",
            "first_player_key": 1, "event_second_player": "B", "second_player_key": 2, "event_status": status, "event_final_result": result,
            "event_live": live, "scores": [{"score_first": "6", "score_second": "4"}], "statistics": [{"stat_name": "Aces"}]}


class Fake:
    def __init__(self, **by): self.by, self.calls = by, []
    def __call__(self, params):
        self.calls.append(params); r = self.by.get(params["method"], [])
        return {"success": 1, "result": r(params) if callable(r) else r}


def make(fake, now="2026-11-04T12:10:00+00:00"):
    st = TennisStore(); return TennisCollector(ApiTennis(key="k", fetch=fake), st, now=lambda: dt.datetime.fromisoformat(now)), st


def test_only_tour_singles_are_kept():
    assert wanted("Atp Singles") and wanted("Wta Singles") and wanted("Challenger Men Singles")
    assert not wanted("Itf Men Singles") and not wanted("Atp Doubles") and not wanted("Challenger Men Doubles")


def test_bad_key_is_a_clear_error():
    with pytest.raises(ApiTennisError, match="Invalid"):
        ApiTennis(key="k", fetch=lambda p: {"success": 0, "error": "Invalid API key"}).get("get_events")


def test_fixtures_are_filtered_and_stored_with_their_stats():
    c, st = make(Fake(get_fixtures=[match(1), match(2, typ="Itf Men Singles"), match(3, typ="Atp Doubles")]))
    assert c.sync_fixtures("2026-11-01", "2026-11-04") == 1
    assert st.counts()["matches"] == 1 and st.counts()["with_stats"] == 1


def test_live_changes_are_logged_once_and_finished_matches_are_reread():
    live = [match(1, "Set 1", live="1", result="0 - 0")]
    fake = Fake(get_livescore=lambda p: live, get_fixtures=[match(1, "Finished", result="2 - 0")])
    c, st = make(fake)
    c.sync_live(); c.sync_live()
    assert st.counts()["live_snapshots"] == 1 and st.live_keys() == [1]
    live.clear()                                         # the match drops out of the live feed
    c.sync_live()
    assert st.live_keys() == [] and st.db.execute("SELECT status FROM matches WHERE event_key=1").fetchone()[0] == "Finished"


def test_history_walk_goes_back_a_week_at_a_time_then_stops():
    fake = Fake(get_fixtures=[])
    c, st = make(fake)
    assert c.walk_history() and fake.calls[-1]["date_stop"] == "2026-11-03" and fake.calls[-1]["date_start"] == "2026-10-28"
    st.set_meta("hist_days", HISTORY_DAYS)
    assert c.walk_history() is False


def test_polling_is_fast_only_around_play():
    c, st = make(Fake())
    st.upsert(match(1, "Not Started", t="12:30", result="-"))
    assert st.active_soon("2026-11-04T12:10:00+00:00")          # due in 20 minutes
    assert not st.active_soon("2026-11-04T06:00:00+00:00")
