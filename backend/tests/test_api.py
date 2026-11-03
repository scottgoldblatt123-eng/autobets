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


def test_close_nearly_level_position_is_a_message_not_an_error(client):
    st = client.get(f"/api/state?ids={MID}").json()
    sel = st["markets"][MID]["selections"]["101"]
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": sel["backs"][0][0], "size": 1})
    r = client.post(f"/api/markets/{MID}/close/101")
    assert r.status_code == 200 and r.json()["closed"] is False


def test_open_orders_list_excludes_matched(client):
    st = client.get(f"/api/state?ids={MID}").json()
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": st["markets"][MID]["selections"]["101"]["backs"][0][0], "size": 5})
    assert client.get(f"/api/state?ids={MID}").json()["orders"] == []


def test_exchange_errors_become_502_with_a_message(monkeypatch):
    from autobets.exchange.base import ExchangeError
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    eng = Engine.demo()
    eng.feed.list_markets = lambda *a, **k: (_ for _ in ()).throw(ExchangeError("login failed: INVALID_USERNAME_OR_PASSWORD"))
    c = TestClient(create_app(eng))
    r = c.get("/api/markets?sport=tennis")
    assert r.status_code == 502 and "login failed" in r.json()["detail"]


def _back(client, size=20):
    st = client.get(f"/api/state?ids={MID}").json()
    price = st["markets"][MID]["selections"]["101"]["backs"][0][0]
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": price, "size": size})


def test_state_has_market_outcomes_and_green_plan(client):
    _back(client)
    m = client.get(f"/api/state?ids={MID}").json()["markets"][MID]
    assert m["outcomes"]["101"] > 0 > m["outcomes"]["102"]
    assert m["green"]["level"] and m["green"]["bets"]


def test_green_market_levels_outcomes(client):
    _back(client)
    r = client.post(f"/api/markets/{MID}/green").json()
    assert r["greened"] and r["placed"]
    o = client.get(f"/api/state?ids={MID}").json()["markets"][MID]["outcomes"]
    assert abs(o["101"] - o["102"]) < 1.0                    # levelled, within a tick of price movement between calls


def test_hard_close_cancels_resting_orders_first(client):
    _back(client)
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 60.0, "size": 5})
    assert client.get(f"/api/state?ids={MID}").json()["orders"]
    r = client.post(f"/api/markets/{MID}/green?hard=true").json()
    assert r["cancelled"] == 1 and r["greened"]
    assert client.get(f"/api/state?ids={MID}").json()["orders"] == []


def test_trigger_needs_a_position_and_fires_and_greens(client):
    r = client.post("/api/triggers", json={"market_id": MID, "selection_id": "101", "price": 1.5})
    assert r.status_code == 422 and "no position" in r.json()["detail"]
    _back(client)
    st = client.get(f"/api/state?ids={MID}").json()["markets"][MID]["selections"]["101"]
    ltp = st["last"]
    r = client.post("/api/triggers", json={"market_id": MID, "selection_id": "101", "price": ltp})
    assert r.status_code == 422                                # the current price
    below = round(max(1.02, ltp - 0.5), 2)
    t = client.post("/api/triggers", json={"market_id": MID, "selection_id": "101", "price": below}).json()
    assert t["direction"] == "le" and t["label"] in ("take profit", "stop loss")
    assert [x["id"] for x in client.get(f"/api/state?ids={MID}").json()["triggers"]] == [t["id"]]
    assert client.delete(f"/api/triggers/{t['id']}").json()["cancelled"] is True
    assert client.get(f"/api/state?ids={MID}").json()["triggers"] == []


def test_trigger_logic_directly():
    from autobets.api.engine import Engine
    e = Engine.demo()
    st = e.state([MID])
    sel = st["markets"][MID]["selections"]["101"]
    e.place(MID, "101", "BACK", sel["backs"][0][0], 20)
    ltp = e.ex.get_book(MID).selections["101"].last_traded
    t = e.add_trigger(MID, "101", ticks_move(ltp, 2))      # above the price -> 'ge'
    assert t["direction"] == "ge"
    e.ex.get_book(MID).selections["101"].last_traded = ticks_move(ltp, 3)   # price moves through it
    e._check_triggers()
    assert e.triggers == {} and "fired" in e.events[-1]["text"].lower()


def ticks_move(p, n):
    from autobets import ticks
    return ticks.move(p, n)


def test_busy_reports_what_a_restart_would_lose(client):
    assert client.get("/api/busy").json() == {"triggers": 0, "open_orders": 0}
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 50.0, "size": 5})
    assert client.get("/api/busy").json()["open_orders"] == 1
