import pytest
from autobets.tennis import model2 as m

AVG = {"service_pts": 60.0, "return_pts": 40.0}
P = lambda s, r, n=30: {"service_pts": s, "return_pts": r, "matches": n}


def test_game_known_values():
    assert m.game(0.5) == pytest.approx(0.5)
    assert m.game(0.6) == pytest.approx(0.7357, abs=1e-3)
    assert m.game(0.65) == pytest.approx(0.8304, abs=1e-3)


def test_symmetry_and_sum():
    r = m.price(P(60, 40), P(60, 40), AVG)
    assert r["p_a"] == pytest.approx(50, abs=1e-6)
    r = m.price(P(64, 44), P(58, 38), AVG)
    assert r["p_a"] + r["p_b"] == pytest.approx(100) and r["p_a"] > 60
    r2 = m.price(P(58, 38), P(64, 44), AVG)
    assert r2["p_a"] == pytest.approx(r["p_b"], abs=1e-6)


def test_best_of_five_widens_favourite():
    a, b = P(64, 44), P(58, 38)
    assert m.price(a, b, AVG, 5)["p_a"] > m.price(a, b, AVG, 3)["p_a"]


def test_small_samples_shrink_to_average():
    strong_few = m.price(P(75, 55, 2), P(60, 40, 30), AVG)["p_a"]
    strong_many = m.price(P(75, 55, 60), P(60, 40, 30), AVG)["p_a"]
    assert 50 < strong_few < strong_many
