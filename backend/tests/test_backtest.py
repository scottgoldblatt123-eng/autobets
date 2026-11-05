import json
import pytest
from autobets import backtest
from autobets.pricelog import PriceStore
from autobets.scripts import validate

LAY_FAV = validate({"name": "Lay fav", "sport": "any", "rules": [
    {"id": "r1", "kind": "entry", "when": [{"type": "in_play", "value": True}], "then": [{"type": "lay", "price": "best", "stake": 10}]},
    {"id": "r2", "kind": "exit", "when": [{"type": "rule_matched", "rule": "r1"}, {"type": "price", "op": ">=", "value": 2.5, "ref": "lay"}], "then": [{"type": "green"}]}]})


def market(mid, t0, winner, prices_path, names=None):
    names = names or {"A": "Alpha Smith", "B": "Beta Jones"}
    ticks = []
    for i, (a, b, ip) in enumerate(prices_path):
        ticks.append((t0 + i * 10, ip, "OPEN", {"A": [a, round(a * 1.01, 2)], "B": [b, round(b * 1.01, 2)]}, None))
    return {"market_id": mid, "sport": "tennis", "event": "Alpha Smith v Beta Jones", "start": "x", "winner": winner, "runners": names, "ticks": ticks}


def test_target_selection():
    m = market("1", 1000, "A", [(1.5, 3.0, False)])
    assert backtest.pick_target(m, "favourite") == "A" and backtest.pick_target(m, "underdog") == "B" and backtest.pick_target(m, "first") == "A" and backtest.pick_target(m, "second") == "B"
    assert backtest.pick_target(market("2", 1, "A", [(1.5, 3, False)], {"A": "Home", "B": "The Draw"}), "draw") == "B"


def test_lay_favourite_loses_when_favourite_wins_and_wins_when_it_loses():
    win = backtest.simulate(LAY_FAV, market("1", 1000, "A", [(1.5, 3.0, False), (1.5, 3.0, True), (1.5, 3.0, True)]), "A", None, 0.05)
    assert win["side"] == "LAY" and win["pnl"] < 0 and win["won"] is False and win["staked"] > 0           # laid the favourite, it won
    lose = backtest.simulate(LAY_FAV, market("2", 2000, "B", [(1.5, 3.0, False), (1.5, 3.0, True), (1.5, 3.0, True)]), "A", None, 0.05)
    assert lose["pnl"] == pytest.approx(10 * 0.95)                                                          # kept the £10 stake less 5% commission


def test_exit_greens_up_and_locks_a_result_whoever_wins():
    path = [(1.5, 3.0, True), (2.0, 2.0, True), (2.6, 1.6, True), (2.6, 1.6, True)]       # favourite drifts out: laid at ~1.515, greens when lay price >= 2.5
    a = backtest.simulate(LAY_FAV, market("1", 1000, "A", path), "A", None, 0.0)
    b = backtest.simulate(LAY_FAV, market("2", 1000, "B", path), "A", None, 0.0)
    assert a["state"] == "done" and a["pnl"] == pytest.approx(b["pnl"], abs=0.2) and a["pnl"] > 0       # the same profit whichever way it ends


def test_never_entering_is_not_a_trade():
    m = market("1", 1000, "A", [(1.5, 3.0, False), (1.5, 3.0, False)])
    assert backtest.simulate(LAY_FAV, m, "A", None, 0.05) is None


def test_run_aggregates_drawdown_oos_and_warns_small_samples():
    ms = [market(str(i), 1000 + i * 100, "A" if i % 3 else "B", [(1.5, 3.0, False), (1.5, 3.0, True), (1.5, 3.0, True)]) for i in range(10)]
    r = backtest.run(LAY_FAV, ms, "favourite")
    assert r["trades"] == 10 and r["wins"] + r["losses"] == 10 and r["max_drawdown"] >= 0 and len(r["curve"]) == 10
    assert r["oos"]["trades"] == 3 and r["oos_from"] == 7
    assert any("small sample" in w for w in r["warnings"]) and r["net"] == pytest.approx(r["curve"][-1])
    assert backtest.run(LAY_FAV, [], "favourite")["trades"] == 0


def test_load_reads_only_markets_with_results():
    st = PriceStore()
    for mid, winner in (("1.1", "A"), ("1.2", None)):
        st.db.execute("INSERT INTO ticks VALUES(?,?,?,?,?,?,?,?,?)", (1000.0, mid, "tennis", "A v B", "x", 1, "OPEN", json.dumps({"A": [1.5, 1.52], "B": [3.0, 3.1]}), None))
        st.db.execute("INSERT INTO runners VALUES(?,?)", (mid, json.dumps({"A": "Alpha", "B": "Beta"})))
        if winner:
            st.set_result(mid, winner, 2000.0)
    got = backtest.load(st, "tennis", 0)
    assert [m["market_id"] for m in got] == ["1.1"] and got[0]["winner"] == "A" and got[0]["ticks"][0][1] is True
    assert backtest.load(st, "football", 0) == []
