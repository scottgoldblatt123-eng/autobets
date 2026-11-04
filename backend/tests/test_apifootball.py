import json
import pytest
import time
from autobets.football.apifootball import ApiFootball, ApiFootballError, current_season


def fake(resp):
    return lambda path, params: resp


def test_status_reads_plan_and_allowance():
    api = ApiFootball(key="k", fetch=fake({"errors": [], "response": {"subscription": {"plan": "Pro", "active": True, "end": "2026-12-01"}, "requests": {"current": 12, "limit_day": 7500}}}))
    assert api.status() == {"plan": "Pro", "active": True, "ends": "2026-12-01", "used_today": 12, "limit_day": 7500}


def test_errors_inside_a_200_are_raised():
    api = ApiFootball(key="k", fetch=fake({"errors": {"token": "Error/Missing application key"}, "response": []}))
    with pytest.raises(ApiFootballError, match="token"):
        api.get("fixtures")


def test_no_key_is_a_clear_error():
    with pytest.raises(ApiFootballError, match="API_FOOTBALL_KEY"):
        ApiFootball(key="", fetch=fake({})).get("status")


def test_responses_are_saved_raw(tmp_path):
    api = ApiFootball(key="k", store_dir=str(tmp_path), fetch=fake({"errors": [], "response": [{"x": 1}]}))
    api.get("fixtures", league=39)
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1 and json.loads(files[0].read_text())["params"] == {"league": 39}


def test_season_rolls_over_in_july():
    assert current_season(time.strptime("2026-11-04", "%Y-%m-%d")) == 2026
    assert current_season(time.strptime("2027-03-01", "%Y-%m-%d")) == 2026
    assert current_season(time.strptime("2027-07-01", "%Y-%m-%d")) == 2027
