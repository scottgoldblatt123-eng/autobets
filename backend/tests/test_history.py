from types import SimpleNamespace as NS
from autobets.api.history import Tracker
from autobets.api.app import create_app
from autobets.api.engine import Engine
from fastapi.testclient import TestClient


def book(traded, ltp=2.0, back=1.99, lay=2.02, mid="1.1", sid="1"):
    sel = NS(traded=traded, last_traded=ltp, backs=[NS(price=back)], lays=[NS(price=lay)])
    return NS(market_id=mid, selections={sid: sel})


def test_recent_volume_short_and_long_windows():
    t = Tracker(short_s=60, long_s=300)
    v = {2.0: 1000.0}
    for i in range(0, 301, 2):                         # 100 matched at 2.0 every 2 s sample... for 5 minutes
        v = {2.0: 1000.0 + i * 10}
        t.record([book(v)], now=1000.0 + i)
    r = t.recent("1.1", "1", v, now=1000.0 + 300)
    assert r["long"] == [[2.0, 3000.0]]                # 300 s x 10 per s
    assert r["short"] == [[2.0, 600.0]]                # 60 s x 10 per s
    assert r["long_span"] == 300 and r["short_span"] == 60


def test_short_history_reports_how_little_there_is():
    t = Tracker()
    t.record([book({2.0: 10.0})], now=0.0)
    t.record([book({2.0: 40.0})], now=10.0)
    r = t.recent("1.1", "1", {2.0: 40.0}, now=10.0)
    assert r["short"] == [[2.0, 30.0]] and r["short_span"] == 10.0   # only 10 s of history so far


def test_chart_points_and_volume_deltas():
    t = Tracker()
    for i, tot in enumerate([100.0, 150.0, 150.0, 400.0]):
        t.record([book({2.0: tot}, ltp=2.0 + i * 0.02)], now=100.0 + i * 3)
    pts = t.chart("1.1", "1")["points"]
    assert [p[4] for p in pts] == [0.0, 50.0, 0.0, 250.0]
    assert pts[-1][1] == 2.06


def test_api_exposes_recent_and_history(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    c = TestClient(create_app(Engine.demo()))
    sel = c.get("/api/state?ids=1.900001").json()["markets"]["1.900001"]["selections"]["101"]
    assert set(sel["recent"]) >= {"short", "long", "short_s", "long_s"}
    h = c.get("/api/history?market_id=1.900001&selection_id=101").json()
    assert h["points"] and len(h["points"][0]) == 5
