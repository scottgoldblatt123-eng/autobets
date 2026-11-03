"""Stops, entries, auto-greens and practice positions must survive a restart or a crash."""
import json
import os

from autobets.api.demo import DemoFeed
from autobets.api.engine import Engine

MID = "1.900001"


def make(path):
    return Engine(DemoFeed(), "demo", state_path=str(path))


def best(e, side):
    s = e.state([MID])["markets"][MID]["selections"]["101"]
    return s["backs"][0][0] if side == "back" else s["lays"][0][0]


def test_everything_survives_a_restart(tmp_path):
    p = tmp_path / "state.json"
    a = make(p)
    a.place(MID, "101", "BACK", best(a, "back"), 10, "KEEP", 0, 3, 4)          # entry with offset and stop
    a.add_market_trigger(MID, 50.0)
    waiting = a.place(MID, "101", "LAY", 1.30, 10)["order"]                     # a resting order far from the market
    before = a.state([MID])
    b = make(p)                                                                  # "restart"
    after = b.state([MID])
    assert after["markets"][MID]["positions"] == before["markets"][MID]["positions"]
    assert {o["order_id"] for o in after["orders"]} == {o["order_id"] for o in before["orders"]}
    assert waiting["order_id"] in {o["order_id"] for o in after["orders"]}
    assert [t["id"] for t in after["triggers"]] == [t["id"] for t in before["triggers"]] and after["triggers"]
    assert [t["id"] for t in after["market_triggers"]] == [t["id"] for t in before["market_triggers"]] and after["market_triggers"]
    assert b.busy() == a.busy()
    assert any("Restarted" in x["text"] for x in b.activity())


def test_ids_do_not_collide_after_restart(tmp_path):
    p = tmp_path / "state.json"
    a = make(p)
    first = a.place(MID, "101", "LAY", 1.30, 10)["order"]["order_id"]
    b = make(p)
    second = b.place(MID, "101", "LAY", 1.30, 10)["order"]["order_id"]
    assert first != second


def test_a_corrupt_file_starts_empty_and_says_so(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{ not json")
    e = make(p)
    assert e.state([MID])["orders"] == []
    assert any("Could not restore" in x["text"] for x in e.activity())


def test_no_state_path_writes_nothing(tmp_path):
    e = Engine(DemoFeed(), "demo")
    e.place(MID, "101", "LAY", 1.30, 10)
    assert not list(tmp_path.iterdir())


def test_the_file_is_written_atomically_and_is_valid_json(tmp_path):
    p = tmp_path / "state.json"
    a = make(p)
    a.place(MID, "101", "BACK", best(a, "back"), 10)
    data = json.loads(p.read_text())
    assert data["v"] == 1 and data["exchange"]["fills"]
    assert not os.path.exists(str(p) + ".tmp")
