import pytest
from autobets.football import livemodel as lm


def test_start_and_end_states():
    r = lm.price(1.5, 1.2, (0, 0), 0, "1H")
    assert r["home"] + r["draw"] + r["away"] == pytest.approx(1) and r["home"] > r["away"]
    late = lm.price(1.5, 1.2, (1, 0), 90, "2H")
    assert late["home"] > 0.9 and late["over_0.5"] > 0.95 and late["over_2.5"] < 0.1


def test_goal_and_time_move_prices_the_right_way():
    base = lm.price(1.5, 1.2, (0, 0), 30, "1H")
    assert lm.price(1.5, 1.2, (0, 1), 30, "1H")["home"] < base["home"] - 0.1
    assert lm.price(1.5, 1.2, (0, 0), 75, "2H")["draw"] > base["draw"]          # a goalless game drifts towards the draw
    assert lm.price(1.5, 1.2, (0, 0), 75, "2H")["over_2.5"] < base["over_2.5"]
    assert lm.price(1.5, 1.2, (1, 1), 60, "2H")["btts"] == pytest.approx(1)
    assert lm.remaining_share(None, "1H") == 1 and lm.remaining_share(45, "HT") == pytest.approx(0.55)
