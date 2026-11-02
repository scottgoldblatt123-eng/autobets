from autobets import pnl
from autobets.domain import Position


def test_outcomes_two_runner_back():
    pos = {"A": Position(win=15.0, lose=-10.0), "B": Position()}
    assert pnl.market_outcomes(pos) == {"A": 15.0, "B": -10.0}


def test_green_two_runner_levels_both_outcomes():
    o = {"A": 15.0, "B": -10.0}
    plan = pnl.green_plan(o, backs={"A": 2.0, "B": 2.1}, lays={"A": 2.02, "B": 2.12})
    assert plan["level"] and abs(plan["after"]["A"] - plan["after"]["B"]) < 0.05
    assert plan["locked"] > 0 and plan["locked"] <= 15


def test_green_three_runner_levels_all_outcomes():
    # backed the home side only: wins +20 if home wins, -10 otherwise
    o = {"H": 20.0, "D": -10.0, "A": -10.0}
    plan = pnl.green_plan(o, backs={"H": 2.1, "D": 3.4, "A": 3.8}, lays={"H": 2.12, "D": 3.5, "A": 3.9})
    assert plan["level"], plan
    vals = list(plan["after"].values())
    assert max(vals) - min(vals) < 0.05
    assert len(plan["bets"]) <= 2                              # one selection is left alone


def test_already_level_returns_none():
    assert pnl.green_plan({"A": 3.0, "B": 3.0}, {"A": 2.0, "B": 2.0}, {"A": 2.02, "B": 2.02}) is None


def test_green_uses_whichever_selection_has_a_price():
    plan = pnl.green_plan({"A": 10.0, "B": -5.0}, {"A": 2.0, "B": None}, {"A": 2.02, "B": None})
    assert plan["level"] and [b["selection_id"] for b in plan["bets"]] == ["A"]


def test_no_prices_at_all_cannot_green():
    assert pnl.green_plan({"A": 10.0, "B": -5.0}, {"A": None, "B": None}, {"A": None, "B": None}) is None


def test_tiny_difference_not_hedged_below_minimum_stake():
    plan = pnl.green_plan({"A": 0.4, "B": -0.1}, {"A": 2.0, "B": 2.0}, {"A": 2.02, "B": 2.02})
    assert plan is not None and plan["bets"] == [] and not plan["level"]
