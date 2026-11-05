import json
import time
import pytest
from fastapi.testclient import TestClient
from autobets.analyse import ai_learning, models, performance
from autobets.api.app import create_app
from autobets.api.engine import Engine
from autobets.ledger import Ledger
from autobets.pricelog import PriceStore
from autobets.recs import Recs
from tests.test_backtest import LAY_FAV, market

MID = "1.900001"


def test_performance_periods_curve_and_strategy_split():
    now = time.time()
    l = Ledger()
    l.add("1", "A", now - 86400, 10.0, "x", 10, {"Lay the draw": 6.0, "Manual trades": 4.0})
    l.add("2", "B", now - 3600, -4.0, "x", 10, {"Lay the draw": -4.0})
    l.add("3", "C", now - 40 * 86400, 7.0, "x", 10, {"Manual trades": 7.0})            # previous period
    p = performance(l, Recs(), 1.5, 30, now)
    assert p["current"] == {"net": 6.0, "trades": 2, "win_rate": 50.0} and p["previous"]["net"] == 7.0 and p["costs"] == 1.5
    assert [c["v"] for c in p["curve"]] == [10.0, 6.0]
    s = {x["name"]: x for x in p["strategies"]}
    assert s["Lay the draw"]["pnl"] == 2.0 and s["Lay the draw"]["trades"] == 2 and s["Manual trades"]["pnl"] == 4.0


def test_models_compares_model_and_market_on_resulted_matches():
    st = PriceStore()
    ctx = {"kind": "tennis", "players": ["Alpha Smith", "Beta Jones"], "model": {"p": [0.7, 0.3], "odds": [1 / 0.7, 1 / 0.3], "version": "v3"}}
    for mid, winner in (("1", "A"), ("2", "B")):
        st.db.execute("INSERT INTO ticks VALUES(?,?,?,?,?,?,?,?,?)", (time.time(), mid, "tennis", "x", "x", 0, "OPEN", json.dumps({"A": [1.9, 1.92], "B": [2.1, 2.12]}), json.dumps(ctx)))
        st.db.execute("INSERT INTO runners VALUES(?,?)", (mid, json.dumps({"A": "Alpha Smith", "B": "Beta Jones"})))
        st.set_result(mid, winner, time.time())
    m = models(st)
    t = m["live"]["tennis"]
    assert t["matches"] == 2 and t["model_accuracy"] == 50.0 and 0 < t["model_brier"] < 1 and 0 < t["market_brier"] < 1 and m["offline"]
    assert models(None)["available"] is False


def test_ai_learning_counts_reasons_and_clv_by_confidence():
    r = Recs()
    r.items = {"c1": {"id": "c1", "kind": "trade", "status": "dismissed", "dismiss_reason": "Edge too small", "clv": None, "confidence": "Low", "edge": .05, "created": 1},
               "c2": {"id": "c2", "kind": "trade", "status": "applied", "dismiss_reason": "", "clv": 0.02, "confidence": "Low", "edge": .05, "created": 1}}
    a = ai_learning(r)
    assert a["dismiss_reasons"] == [{"reason": "edge too small", "n": 1}] and a["clv_by_confidence"]["Low"]["avg_clv_pts"] == 2.0


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return TestClient(create_app(Engine.demo()))


def test_backtest_endpoint_runs_and_stores(client):
    assert client.post("/api/backtests", json={"script_id": "s1"}).status_code == 422          # no price log in demo
    eng = client.app.state.__dict__ if False else None
    st = PriceStore()
    for i in range(6):
        m = market(f"1.{i}", time.time() - 5000 + i * 100, "A" if i % 2 else "B", [(1.5, 3.0, False), (1.5, 3.0, True), (1.5, 3.0, True)])
        for t, ip, status, prices, _ in m["ticks"]:
            st.db.execute("INSERT INTO ticks VALUES(?,?,?,?,?,?,?,?,?)", (t, m["market_id"], "tennis", m["event"], "x", 1 if ip else 0, status, json.dumps(prices), None))
        st.db.execute("INSERT INTO runners VALUES(?,?)", (m["market_id"], json.dumps(m["runners"])))
        st.set_result(m["market_id"], m["winner"], time.time())
    # the app exposes the engine through closures; find it through the script we create
    sid = client.post("/api/scripts", json=LAY_FAV).json()["id"]
    import autobets.api.app as appmod
    appmod_engine = [c.cell_contents for f in client.app.routes if hasattr(f, "endpoint") and getattr(f.endpoint, "__closure__", None) for c in f.endpoint.__closure__ if isinstance(getattr(c, "cell_contents", None), Engine)][0]
    appmod_engine.price_store = st
    r = client.post("/api/backtests", json={"script_id": sid, "target": "favourite", "days": 1}).json()
    assert r["trades"] == 6 and r["script"] == "Lay fav" and r["data"]["markets"] == 6
    assert client.post("/api/backtests", json={"script_id": sid, "target": "nope"}).status_code == 422
    lst = client.get("/api/backtests").json()
    assert len(lst["items"]) == 1 and "trade_list" not in lst["items"][0]
    assert client.get(f"/api/backtests/{r['id']}").json()["trade_list"]
    assert client.get("/api/analyse/performance?days=30").json()["current"]["trades"] == 0
    assert client.get("/api/analyse/ai").json()["ideas"] == 0
