import time
import pytest
from fastapi.testclient import TestClient
from autobets.api.app import create_app
from autobets.api.engine import Engine
from autobets.domain import Persistence, Status

MID = "1.900001"


@pytest.fixture
def eng(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return Engine.demo()


@pytest.fixture
def client(eng):
    return TestClient(create_app(eng))


def rest(client, price=50.0, size=5, persistence="CANCEL", **kw):
    r = client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": price, "size": size,
                                         "persistence": persistence, **kw})
    assert r.status_code == 200, r.text
    return r.json()["order"]


def test_suspended_market_refuses_orders_and_says_why(client):
    client.post(f"/api/demo/status?market_id={MID}&status=SUSPENDED")
    st = client.get(f"/api/state?ids={MID}").json()
    assert st["markets"][MID]["status"] == "SUSPENDED"
    r = client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 2.0, "size": 5})
    assert r.status_code == 422 and "suspended" in r.json()["detail"]
    g = client.post(f"/api/markets/{MID}/green?hard=true").json()
    assert g["greened"] is False and "suspended" in g["reason"]
    client.post(f"/api/demo/status?market_id={MID}&status=OPEN")
    assert client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 50.0, "size": 5}).status_code == 200


def test_stop_waits_while_suspended(client, eng):
    st = client.get(f"/api/state?ids={MID}").json()
    price = st["markets"][MID]["selections"]["101"]["backs"][0][0]
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": price, "size": 10})
    t = client.post("/api/triggers", json={"market_id": MID, "selection_id": "101", "price": 1.5}).json()
    client.post(f"/api/demo/status?market_id={MID}&status=SUSPENDED")
    client.get(f"/api/state?ids={MID}")
    assert t["id"] in eng.triggers                      # still waiting, not fired and not dropped


def test_edit_order_price_and_size(client):
    o = rest(client, 50.0, 5)
    r = client.patch(f"/api/orders/{o['order_id']}", json={"price": 40.0, "size": 8})
    assert r.status_code == 200
    new = r.json()["order"]
    assert new["price"] == 40.0 and new["size"] == 8 and new["order_id"] != o["order_id"] and new["persistence"] == "CANCEL"
    st = client.get(f"/api/state?ids={MID}").json()
    assert [x["order_id"] for x in st["orders"]] == [new["order_id"]]          # the old one is gone
    assert client.patch(f"/api/orders/{new['order_id']}", json={"size": 0.5}).status_code == 422
    assert client.patch(f"/api/orders/{new['order_id']}", json={"price": 1.015}).status_code == 422


def test_persistence_is_changeable_and_lapses_at_the_off(client, eng):
    a = rest(client, 50.0, 5, "KEEP"); b = rest(client, 48.0, 5, "KEEP")
    assert client.post("/api/orders-persistence", json={"persistence": "CANCEL", "order_id": a["order_id"]}).json()["changed"] == 1
    assert client.post("/api/orders-persistence", json={"persistence": "TAKE_SP", "market_ids": [MID]}).json()["changed"] == 2
    eng.ex.get_order(a["order_id"]).request.persistence = Persistence.CANCEL
    eng.ex.go_in_play(MID)
    assert eng.ex.get_order(a["order_id"]).status is Status.LAPSED and eng.ex.get_order(b["order_id"]).status is Status.CANCELLED


def test_the_off_is_detected_from_the_feed(client, eng):
    keep = rest(client, 50.0, 5, "KEEP"); lapse = rest(client, 48.0, 5, "CANCEL")
    client.post(f"/api/demo/status?market_id={MID}&status=OPEN&in_play=false")
    client.get(f"/api/state?ids={MID}")
    client.post(f"/api/demo/status?market_id={MID}&status=OPEN&in_play=true")
    client.get(f"/api/state?ids={MID}")
    assert eng.ex.get_order(keep["order_id"]).status is Status.UNMATCHED
    assert eng.ex.get_order(lapse["order_id"]).status is Status.LAPSED


def test_fill_or_kill_cancels_the_unmatched_part_after_the_delay(client, eng):
    o = rest(client, 50.0, 5, fok_s=0.2)
    assert o["status"] == "UNMATCHED"
    client.get(f"/api/state?ids={MID}")
    assert eng.ex.get_order(o["order_id"]).status is Status.UNMATCHED       # not yet
    time.sleep(0.3)
    st = client.get(f"/api/state?ids={MID}").json()
    assert eng.ex.get_order(o["order_id"]).status is Status.CANCELLED and not st["orders"]
    assert any("Fill-or-kill" in e["text"] for e in st["events"])


def test_activity_log_records_orders(client):
    o = rest(client, 50.0, 5)
    client.delete(f"/api/orders/{o['order_id']}")
    log = client.get("/api/log").json()
    assert [x["text"][:9] for x in log][-2:] == ["BACK £5.0", "Cancelled"]
