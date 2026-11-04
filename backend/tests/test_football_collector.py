import datetime as dt
from autobets.football.apifootball import ApiFootball
from autobets.football.collector import Collector, LEAGUES
from autobets.football.store import FootballStore


def fixture(fid, status="NS", gh=None, ga=None, league=39, date="2026-11-07T15:00:00+00:00", elapsed=None):
    return {"fixture": {"id": fid, "date": date, "status": {"short": status, "elapsed": elapsed}, "venue": {"name": "V"}, "referee": "R"},
            "league": {"id": league, "season": 2026}, "teams": {"home": {"id": 1, "name": "Home"}, "away": {"id": 2, "name": "Away"}},
            "goals": {"home": gh, "away": ga}, "score": {"halftime": {"home": 0, "away": 0}}}


class Fake:
    """Stands in for the network: answers by endpoint and counts calls."""
    def __init__(self, **by_path):
        self.by, self.calls = by_path, []

    def __call__(self, path, params):
        self.calls.append((path, params))
        r = self.by.get(path)
        return {"errors": [], "response": r(params) if callable(r) else (r or [])}


def make(fake, now="2026-11-07T15:30:00+00:00"):
    st = FootballStore()
    c = Collector(ApiFootball(key="k", fetch=fake), st, now=lambda: dt.datetime.fromisoformat(now))
    return c, st


def test_season_sync_upserts_and_detects_change():
    c, st = make(Fake(fixtures=[fixture(1), fixture(2)]))
    assert c.sync_season(39, 2026) == 2 and st.counts()["fixtures"] == 2
    assert st.upsert_fixture(fixture(1)) is False                 # same again: no change
    assert st.upsert_fixture(fixture(1, "1H", 1, 0, elapsed=12)) is True


def test_live_sync_keeps_only_our_leagues_and_logs_changes_once():
    c, st = make(Fake(fixtures=[fixture(1, "1H", 0, 0, elapsed=10), fixture(9, "1H", 0, 0, league=999, elapsed=10)]))
    assert c.sync_live() == 1
    c.sync_live()                                                  # nothing changed: no second snapshot
    assert st.counts()["live_snapshots"] == 1 and st.counts()["fixtures"] == 1


def test_finished_live_game_is_reread_when_it_drops_out_of_live_feed():
    fake = Fake(fixtures=lambda p: [fixture(1, "FT", 2, 1)] if p.get("id") == 1 else [])
    c, st = make(fake)
    st.upsert_fixture(fixture(1, "2H", 2, 1, elapsed=80))
    c.sync_live()
    assert st.db.execute("SELECT status FROM fixtures WHERE id=1").fetchone()[0] == "FT"


def test_details_backfill_marks_fixture_done_and_newest_first():
    fake = Fake(**{"fixtures/statistics": [{"team": {"id": 1}, "statistics": []}, {"team": {"id": 2}, "statistics": []}], "fixtures/events": [], "fixtures/lineups": []})
    c, st = make(fake)
    st.upsert_fixture(fixture(1, "FT", 1, 0, date="2026-11-01T15:00:00+00:00"))
    st.upsert_fixture(fixture(2, "FT", 0, 0, date="2026-11-05T15:00:00+00:00"))
    assert st.needing_details(5) == [2, 1]
    assert c.backfill_details(1) == 1 and st.needing_details(5) == [1]
    assert st.counts()["with_details"] == 1


def test_polling_speeds_up_around_kickoff():
    c, st = make(Fake())
    st.upsert_fixture(fixture(1, "NS", date="2026-11-07T15:00:00+00:00"))
    assert st.playing_soon("2026-11-07T14:50:00+00:00") and st.playing_soon("2026-11-07T16:30:00+00:00")
    assert not st.playing_soon("2026-11-07T09:00:00+00:00")


def test_tick_runs_every_job_once_and_respects_budget():
    fake = Fake(status={"subscription": {"plan": "Pro"}, "requests": {"current": 7000, "limit_day": 7500}})
    c, st = make(fake)
    c.tick({})
    paths = [p for p, _ in fake.calls]
    assert "fixtures/statistics" not in paths                     # over budget: no backfill, live and season sync still ran
    assert paths.count("fixtures") >= len(LEAGUES)
