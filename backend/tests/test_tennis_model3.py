import pytest
from autobets.tennis import model3
from autobets.tennis.livestore import TennisStore
from test_tennis_ratings import match


def test_blend_and_elo_update():
    assert model3.blend(0.5, 0.5) == pytest.approx(0.5)
    assert 0.6 < model3.blend(0.6, 0.8) < 0.8
    st = TennisStore()
    for i in range(6):
        st.upsert(match(i + 1, f"2026-10-0{i + 1}", 1, 2, (68, 46, 11, 8), (55, 34, 4, 1)))
    elo, played = model3.ratings(st, "2026-11-01")
    assert elo["1"] > 1500 > elo["2"] and played["1"] == 6
    r = model3.price(0.6, elo, 1, 2)
    assert r["p_a"] > 60 and r["p_a"] + r["p_b"] == pytest.approx(100) and r["version"] == model3.VERSION
