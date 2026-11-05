import pytest
from autobets.scripts import ScriptError, ScriptStore, check, describe, evaluate, validate

LAY_A = {"name": "Tennis: lay A, green, not set 3", "sport": "tennis", "rules": [
    {"id": "r1", "kind": "entry", "when": [{"type": "price", "op": ">=", "value": 2.2}, {"type": "set_number", "op": "<", "value": 3}, {"type": "in_play", "value": True}],
     "then": [{"type": "lay", "price": 2.2, "stake": 10}]},
    {"id": "r2", "kind": "exit", "when": [{"type": "rule_matched", "rule": "r1"}, {"type": "price", "op": "<=", "value": 1.7}], "then": [{"type": "green"}]},
    {"id": "r3", "kind": "safety", "when": [{"type": "set_number", "op": ">=", "value": 3}, {"type": "rule_matched", "rule": "r1"}], "then": [{"type": "close"}, {"type": "stop"}]},
]}


def view(price=None, sets=None, in_play=True, loss=0.0, goals=None, elapsed=None, clock="12:00"):
    return {"prices": {"last": price}, "in_play": in_play, "ctx": {"sets": sets, "goals": goals, "elapsed": elapsed}, "position_loss": loss, "clock": clock}


def test_valid_script_round_trips_and_describes():
    s = validate(LAY_A)
    assert [r["id"] for r in s["rules"]] == ["r1", "r2", "r3"] and s["rules"][0]["then"][0]["basis"] == "stake"
    text = describe(s)
    assert "Lay at 2.2" in text[0]["then"][0] and "set number < 3" in text[0]["if"][1]


@pytest.mark.parametrize("mut,msg", [
    (lambda s: s.update(name=""), "name"),
    (lambda s: s.update(rules=[]), "rules"),
    (lambda s: s["rules"][0]["when"].append({"type": "nonsense"}), "unknown condition"),
    (lambda s: s["rules"][0]["then"].__setitem__(0, {"type": "lay", "price": 2.2, "stake": 0.5}), "stake"),
    (lambda s: s["rules"][0]["then"].__setitem__(0, {"type": "lay", "price": 1.0, "stake": 5}), "price"),
    (lambda s: s["rules"][1]["when"].__delitem__(0), "exit rule must depend"),
    (lambda s: s["rules"][0]["when"].append({"type": "rule_matched", "rule": "r2"}), "earlier"),
    (lambda s: s["rules"][0]["then"].append({"type": "green"}), "entry rule"),
    (lambda s: s.update(sport="cricket"), "sport"),
])
def test_invalid_scripts_are_refused_with_a_reason(mut, msg):
    import copy
    s = copy.deepcopy(LAY_A)
    mut(s)
    with pytest.raises(ScriptError, match=msg):
        validate(s)


def test_entry_fires_once_when_conditions_hold_and_not_before():
    s = validate(LAY_A)
    assert evaluate(s, view(2.0, [("1", "2")]), set()) == []
    assert evaluate(s, view(2.2, [("1", "2")], in_play=False), set()) == []
    fire = evaluate(s, view(2.3, [("1", "2")]), set())
    assert [(r["id"], a["type"]) for r, a in fire] == [("r1", "lay")]
    assert evaluate(s, view(2.3, [("1", "2")]), {"r1"}) == []          # already fired


def test_exit_needs_entry_and_safety_wins():
    s = validate(LAY_A)
    assert evaluate(s, view(1.6, [("1", "2")]), set()) == []           # price is low but r1 never matched
    assert [r["id"] for r, a in evaluate(s, view(1.6, [("1", "2")]), {"r1"})] == ["r2"]
    fire = evaluate(s, view(1.6, [("1", "2"), ("3", "3"), ("0", "0")]), {"r1"})
    assert [a["type"] for r, a in fire] == ["close", "stop"]            # set 3 starts: safety closes and stops, no green


def test_football_conditions_and_clock_window():
    c = lambda t, **k: {"type": t, **k}
    assert check(c("score_is", home=0, away=0), view(goals=[0, 0]), set()) and not check(c("score_is", home=0, away=0), view(goals=[1, 0]), set())
    assert check(c("minute", op=">=", value=45), view(elapsed=46), set()) and not check(c("minute", op=">=", value=45), view(), set())
    assert check(c("goals_total", op="<=", value=1), view(goals=[1, 0]), set())
    assert check(c("clock", start="19:30", end="19:45"), view(clock="19:40"), set()) and not check(c("clock", start="19:30", end="19:45"), view(clock="19:50"), set())
    assert check(c("clock", start="23:00", end="01:00"), view(clock="00:10"), set())          # window across midnight
    assert not check(c("price", op=">=", value=2.0, ref="last"), view(None), set())             # no price, no match
    assert check(c("position_loss", op=">=", value=15), view(loss=16), set())


def test_store_versions_clone_enable_delete():
    st = ScriptStore()
    a = st.create(LAY_A, "ai", "drafted by Claude")
    assert a["version"] == 1 and a["origin"] == "ai" and not a["enabled"]
    b = st.update(a["id"], {**LAY_A, "name": "Renamed"})
    assert b["version"] == 2 and b["name"] == "Renamed" and len(b["history"]) == 2
    c = st.clone(a["id"], "")
    assert c["name"] == "Copy of Renamed" and c["id"] != a["id"] and not c["enabled"]
    assert st.set_enabled(a["id"], True)["enabled"]
    st2 = ScriptStore(st.export())
    assert len(st2.list()) == 2 and st2.create(LAY_A)["id"] not in (a["id"], c["id"])
    st.delete(a["id"])
    with pytest.raises(KeyError):
        st.get(a["id"])
