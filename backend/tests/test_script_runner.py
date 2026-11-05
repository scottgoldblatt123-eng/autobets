import pytest
from autobets.api.engine import Engine
from tests.test_scripts import LAY_A

MID = "1.900001"


def _script(price, stake=5):
    return {"name": "Back test", "sport": "any", "rules": [
        {"id": "r1", "kind": "entry", "when": [{"type": "price", "op": ">=", "value": price, "ref": "back"}], "then": [{"type": "back", "price": "best", "stake": stake}]},
        {"id": "r2", "kind": "exit", "when": [{"type": "rule_matched", "rule": "r1"}, {"type": "price", "op": ">=", "value": 1.01, "ref": "back"}], "then": [{"type": "green"}]}]}


@pytest.fixture
def eng():
    e = Engine.demo()
    e.settle = None
    return e


def _add(e, price=1.01, stake=5, enable=True):
    s = e.scripts.create(_script(price, stake))
    if enable:
        e.scripts.set_enabled(s["id"], True)
    return s, e.plan.add(MID, "101", s["id"], "A v B", "Match Odds", "A. Player")


def test_disabled_script_does_nothing_and_automation_off_does_nothing(eng):
    s, row = _add(eng, enable=False)
    assert eng.run_scripts() == 0 and not row["orders"]
    eng.scripts.set_enabled(s["id"], True)
    eng.update_settings({"automation_enabled": False})
    assert eng.run_scripts() == 0 and not row["orders"]


def test_entry_places_once_as_a_script_order_and_exit_greens(eng):
    s, row = _add(eng)
    eng.run_scripts()
    assert len(row["orders"]) == 1 and "r1" in row["fired"]
    placed = eng.ex.get_order(row["orders"][0])
    assert placed.request.source == "script:Back test" and placed.request.size == 5
    eng.run_scripts()                                        # next pass: the exit rule greens and the row is done
    assert row["state"] == "done" and "r2" in row["fired"]
    assert len(row["orders"]) == 1                           # the entry never repeats


def test_entry_condition_not_met_waits(eng):
    s, row = _add(eng, price=900)
    assert eng.run_scripts() == 0 and row["state"] == "armed" and not row["orders"]


def test_blocked_entry_records_the_reason_and_stops_the_row(eng):
    eng.update_settings({"max_open_liability": 2})
    s, row = _add(eng, stake=5)
    eng.run_scripts()
    assert row["state"] == "stopped" and "exposure" in row["note"] and not row["orders"]
    assert eng.run_scripts() == 0                            # not retried


def test_stake_override_on_the_plan_row(eng):
    s, row = _add(eng, stake=5)
    row["stake"] = 3
    eng.run_scripts()
    assert eng.ex.get_order(row["orders"][0]).request.size == 3


def test_exit_orders_ignore_loss_limits_but_not_the_kill_switch(eng):
    s, row = _add(eng)
    eng.run_scripts()
    eng.update_settings({"daily_loss_limit": 1})
    eng.ledger.add("9.9", "old", __import__("time").time(), -50.0, "z")
    eng._refresh_guard()
    eng.run_scripts()
    assert row["state"] == "done"                            # greening is allowed even though the loss limit is hit


def test_plan_survives_restart_and_clashes_are_reported(tmp_path):
    p = str(tmp_path / "s.json")
    e = Engine(Engine.demo().feed, "demo", state_path=p)
    s = e.scripts.create(_script(1.01))
    e.plan.add(MID, "101", s["id"], "A v B", "Match Odds", "A")
    e.plan.add(MID, "102", s["id"], "A v B", "Match Odds", "B")
    assert len(e.plan.clashes()) == 1
    e._save()
    e2 = Engine(Engine.demo().feed, "demo", state_path=p)
    assert len(e2.plan.rows) == 2 and e2.scripts.list()[0]["name"] == "Back test"
    with pytest.raises(ValueError, match="already"):
        e2.plan.add(MID, "101", s["id"], "A v B", "Match Odds", "A")


SCALP = {"name": "Scalp", "sport": "football", "rules": [
    {"id": "r1", "kind": "entry", "repeat": 3, "when": [{"type": "price", "op": ">=", "value": 1.01, "ref": "back"}], "then": [{"type": "back", "price": "best", "stake": 10}]},
    {"id": "r2", "kind": "exit", "when": [{"type": "rule_matched", "rule": "r1"}, {"type": "ticks_from_entry", "op": ">=", "value": 2}], "then": [{"type": "green"}]},
    {"id": "r3", "kind": "safety", "when": [{"type": "ticks_from_entry", "op": "<=", "value": -6}], "then": [{"type": "close"}, {"type": "stop"}]}]}


def test_scalp_validates_and_describes_repeat():
    from autobets.scripts import describe, validate
    s = validate(SCALP)
    assert s["rules"][0]["repeat"] == 3 and any("Repeat up to 3" in t for t in describe(s)[0]["then"])
    bad = {**SCALP, "rules": [{**SCALP["rules"][0], "repeat": 0}] + SCALP["rules"][1:]}
    with pytest.raises(Exception):
        validate(bad)


def test_ticks_from_entry_condition():
    from autobets.scripts import check
    c = {"type": "ticks_from_entry", "op": ">=", "value": 2}
    view = lambda lay: {"entry": {"side": "BACK", "price": 2.0}, "prices": {"lay": lay, "back": lay - 0.02}}      # noqa: E731
    assert not check(c, {"prices": {"lay": 1.9}}, set())               # not matched yet
    assert not check(c, view(1.99), set()) and check(c, view(1.98), set()) and check(c, view(1.9), set())
    assert check({"type": "ticks_from_entry", "op": "<=", "value": -2}, view(2.04), set())     # against you
    lay_entry = {"entry": {"side": "LAY", "price": 2.0}, "prices": {"back": 2.04, "lay": 2.06}}
    assert check(c, lay_entry, set())


def test_scalp_runs_one_at_a_time_and_stops_after_repeat(eng):
    s = eng.scripts.create(SCALP)
    eng.scripts.set_enabled(s["id"], True)
    row = eng.plan.add(MID, "101", s["id"], "A v B", "Match Odds", "A. Player")
    eng.run_scripts()
    assert len(row["orders"]) == 1 and row["entry_order"] == row["orders"][0]
    # force the exit condition: pretend the price has moved 2 ticks in our favour
    import autobets.scripts as sc
    real = sc.check
    sc.check = lambda c, v, f: True if c["type"] == "ticks_from_entry" and c["op"] == ">=" else (False if c["type"] == "ticks_from_entry" else real(c, v, f))
    try:
        entries = set()
        for _ in range(30):
            eng.run_scripts()
            entries.add(row.get("entry_order"))
            assert len(row["orders"]) <= 3 * 2 + 1
    finally:
        sc.check = real
    entries.discard(None)
    assert len(entries) == 3 and row["cycle"] == 3          # exactly three runs, one at a time
    assert row["state"] == "done" and not row.get("await_flat")
