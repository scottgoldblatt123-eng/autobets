import pytest

from autobets.domain import Side
from autobets.pnl import _apply, book_plan, dutch_plan


def outcomes_after(ids, bets):
    out = {i: 0.0 for i in ids}
    for b in bets:
        out = _apply(out, b["selection_id"], Side(b["side"]), b["price"], b["stake"])
    return out


def test_back_dutch_returns_the_same_whichever_selected_runner_wins():
    r = dutch_plan(Side.BACK, {"A": 2.2, "B": 4.2}, 100)
    assert sum(b["stake"] for b in r["bets"]) == pytest.approx(100, abs=0.02)
    o = outcomes_after(["A", "B"], r["bets"])
    assert o["A"] == pytest.approx(o["B"], abs=0.05) and o["A"] > 44


def test_back_dutch_of_two_of_three_loses_the_total_if_the_third_wins():
    r = dutch_plan(Side.BACK, {"A": 3.0, "B": 3.5}, 100)
    o = outcomes_after(["A", "B", "C"], r["bets"])
    assert o["C"] == pytest.approx(-100, abs=0.05)


def test_lay_dutch_costs_the_same_whichever_selected_runner_wins():
    r = dutch_plan(Side.LAY, {"A": 2.2, "B": 4.2}, 100)
    o = outcomes_after(["A", "B", "C"], r["bets"])
    assert o["A"] == pytest.approx(o["B"], abs=0.05)
    assert o["C"] == pytest.approx(100, abs=0.05)         # none of the laid runners wins: you keep every stake


def test_dutch_drops_stakes_below_the_minimum():
    r = dutch_plan(Side.BACK, {"A": 1.5, "B": 200.0}, 20)
    assert [b["selection_id"] for b in r["bets"]] == ["A"] and r["dropped"][0]["selection_id"] == "B"


def test_book_plan_reaches_the_targets_exactly():
    backs = {"A": 2.0, "B": 3.0, "C": 7.0}
    lays = {"A": 2.02, "B": 3.05, "C": 7.2}
    cur = {"A": -10.0, "B": 25.0, "C": 5.0}
    tgt = {"A": 10.0, "B": 10.0, "C": 10.0}
    r = book_plan(cur, tgt, backs, lays)
    assert not r["error"]
    for k, v in r["after"].items():
        assert v == pytest.approx(tgt[k], abs=0.1)


def test_book_plan_uses_lays_where_the_runner_needs_less():
    r = book_plan({"A": 20.0, "B": -20.0}, {"A": 0.0, "B": 0.0}, {"A": 2.0, "B": 2.0}, {"A": 2.02, "B": 2.02})
    sides = {b["selection_id"]: b["side"] for b in r["bets"]}
    assert sides.get("A") == "LAY" or sides.get("B") == "BACK"
    for v in r["after"].values():
        assert v == pytest.approx(0, abs=0.1)


def test_book_plan_matches_the_green_up_level():
    # equalising two runners should lock the same profit green_plan finds
    from autobets.pnl import green_plan
    backs = {"A": 2.0, "B": 2.0}; lays = {"A": 2.02, "B": 2.02}
    cur = {"A": 20.0, "B": -10.0}
    g = green_plan(cur, backs, lays)
    r = book_plan(cur, {"A": g["locked"], "B": g["locked"]}, backs, lays)
    for v in r["after"].values():
        assert v == pytest.approx(g["locked"], abs=0.1)


def test_book_plan_refuses_a_missing_target_or_price():
    assert book_plan({"A": 0, "B": 0}, {"A": 1}, {"A": 2, "B": 2}, {"A": 2, "B": 2})["error"]
    assert book_plan({"A": 0, "B": 0}, {"A": 1, "B": 1}, {"A": 2, "B": None}, {"A": 2, "B": None})["error"]


# ---- through the engine and API -------------------------------------------------
def _client():
    import os
    os.environ["AUTOBETS_MODE"] = "demo"
    from fastapi.testclient import TestClient
    from autobets.api.app import create_app
    return TestClient(create_app())


def test_dutch_preview_and_place_through_the_api():
    c = _client()
    pre = c.post("/api/dutch/preview", json={"market_id": "1.900001", "selection_ids": ["101", "102"], "side": "BACK", "total": 100}).json()
    assert len(pre["bets"]) == 2 and abs(pre["total_stake"] - 100) < 0.05
    a, b = pre["after"]["101"], pre["after"]["102"]
    assert abs(a - b) < 0.1
    done = c.post("/api/dutch", json={"market_id": "1.900001", "selection_ids": ["101", "102"], "side": "BACK", "total": 100}).json()
    assert done["failed"] == 0 and len(done["placed"]) == 2


def test_dutch_needs_two_runners_and_a_sensible_stake():
    c = _client()
    assert c.post("/api/dutch/preview", json={"market_id": "1.900001", "selection_ids": ["101"], "total": 50}).status_code == 422
    assert c.post("/api/dutch/preview", json={"market_id": "1.900001", "selection_ids": ["101", "102"], "total": 0.5}).status_code == 422


def test_book_through_the_api_hits_the_targets():
    c = _client()
    pre = c.post("/api/book/preview", json={"market_id": "1.900001", "targets": {"101": 5, "102": 5}}).json()
    assert not pre["error"]
    assert all(abs(v - 5) < 0.2 for v in pre["after"].values())
    done = c.post("/api/book", json={"market_id": "1.900001", "targets": {"101": 5, "102": 5}}).json()
    assert done["failed"] == 0
    st = c.get("/api/state?ids=1.900001").json()["markets"]["1.900001"]["outcomes"]
    assert all(abs(v - 5) < 2.0 for v in st.values())      # demo prices drift a little between preview and placement
