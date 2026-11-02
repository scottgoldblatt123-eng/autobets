import pytest
from fastapi.testclient import TestClient
from autobets.api.app import create_app
from autobets.api.engine import Engine

MID = "1.900001"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return TestClient(create_app(Engine.demo()))


def test_markets_and_state(client):
    ms = client.get("/api/markets?sport=tennis").json()
    assert any(m["market_id"] == MID for m in ms)
    st = client.get(f"/api/state?ids={MID}").json()
    sel = st["markets"][MID]["selections"]["101"]
    assert sel["backs"] and sel["lays"] and sel["traded"]
    assert sel["backs"][0][0] < sel["lays"][0][0]            # best back below best lay


def test_back_at_market_matches_and_creates_position(client):
    st = client.get(f"/api/state?ids={MID}").json()
    price = st["markets"][MID]["selections"]["101"]["backs"][0][0]
    r = client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": price, "size": 10})
    assert r.status_code == 200 and r.json()["order"]["status"] == "MATCHED"
    pos = client.get(f"/api/state?ids={MID}").json()["markets"][MID]["positions"]["101"]
    assert pos["lose"] == -10 and pos["win"] > 0


def test_resting_order_cancel_and_validation(client):
    r = client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 50.0, "size": 5})
    o = r.json()["order"]
    assert o["status"] == "UNMATCHED"                         # nobody offers 50.0, so it rests
    assert any(x["order_id"] == o["order_id"] for x in client.get(f"/api/state?ids={MID}").json()["orders"])
    assert client.delete(f"/api/orders/{o['order_id']}").json()["status"] == "CANCELLED"
    assert not client.get(f"/api/state?ids={MID}").json()["orders"]
    r = client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "LAY", "price": 1.015, "size": 5})
    assert r.status_code == 422                               # not a valid tick
    r = client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 2.0, "size": 0.5})
    assert r.status_code == 422                               # below minimum stake


def test_close_position_levels_the_book(client):
    st = client.get(f"/api/state?ids={MID}").json()
    price = st["markets"][MID]["selections"]["101"]["backs"][0][0]
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": price, "size": 20})
    c = client.post(f"/api/markets/{MID}/close/101").json()
    assert c["closed"] is True
    pos = client.get(f"/api/state?ids={MID}").json()["markets"][MID]["positions"]["101"]
    assert abs(pos["win"] - pos["lose"]) < 0.6               # levelled to within rounding and tick spread


def test_token_required_outside_demo(monkeypatch):
    monkeypatch.setenv("AUTOBETS_TOKEN", "s3cret")
    c = TestClient(create_app(Engine.demo()))
    assert c.get("/api/markets").status_code == 401
    assert c.get("/api/markets", headers={"X-Auth": "s3cret"}).status_code == 200
