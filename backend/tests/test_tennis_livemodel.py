import pytest
from autobets.tennis import livemodel as lm, model2


def test_start_state_equals_prematch():
    assert lm.live_prob(0.64, 0.60) == pytest.approx(model2.match_prob(0.64, 0.60), abs=1e-9)


def test_break_down_hurts_and_serving_helps():
    base = lm.live_prob(0.64, 0.62, games=(3, 3), a_serving=True)
    down = lm.live_prob(0.64, 0.62, games=(2, 3), a_serving=False)           # A lost a game: behind a break
    assert down < base - 0.05


def test_points_and_sets_move_the_price():
    assert lm.live_prob(0.64, 0.62, sets=(1, 0)) > 0.8 * 0 + 0.6
    assert lm.live_prob(0.64, 0.62, games=(3, 3), points=(0, 3), a_serving=True) < lm.live_prob(0.64, 0.62, games=(3, 3), points=(0, 0), a_serving=True)
    assert lm.live_prob(0.64, 0.62, sets=(1, 1), games=(5, 2)) > 0.9
    assert lm.live_prob(0.6, 0.6, sets=(0, 0), games=(6, 3)) == pytest.approx(lm.live_prob(0.6, 0.6, sets=(1, 0)), abs=0.0)  # set won = next set


def test_calibrate_hits_target():
    a, b = lm.calibrate(0.62, 0.62, 0.7)
    assert model2.match_prob(a, b) == pytest.approx(0.7, abs=1e-3)


def test_parse_points():
    assert lm.parse_points("40", "A") == (3, 4) and lm.parse_points("x", "0") is None
