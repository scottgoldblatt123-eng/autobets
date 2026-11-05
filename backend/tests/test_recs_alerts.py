import time
import pytest
from fastapi.testclient import TestClient
from autobets.alerts import Alerts
from autobets.api.app import create_app
from autobets.api.engine import Engine
from autobets.domain import MarketBook, PriceLevel, SelectionBook
from autobets.recs import Recs

MID = "1.900001"


def book(back=2.0, lay=2.02, status="OPEN", in_play=False, b=(2.0, 2.02)):
    sel = lambda i, b, l: SelectionBook(i, backs=[PriceLevel(b, 100)], lays=[PriceLevel(l, 100)], last_traded=b)
    return MarketBook("1.5", in_play=in_play, status=status, selections={"A": sel("A", back, lay), "B": sel("B", *b)})


INFO = {"runners": {"A": "Alpha Smith", "B": "Beta Jones"}, "event": "Alpha Smith v Beta Jones", "name": "Match Odds", "start": "2030-01-01T10:00:00Z"}
CTX = lambda pa: {"kind": "tennis", "players": ["Alpha Smith", "Beta Jones"], "model": {"p": [pa, 1 - pa], "odds": [1 / pa, 1 / (1 - pa)], "version": "v3"}}


def test_candidate_finds_a_back_edge_and_ignores_small_ones_and_wide_spreads():
    c = Recs.candidate("tennis", INFO, book(back=2.2, lay=2.24, b=(2.2, 2.24)), CTX(0.55))      # model 55% vs 1/2.2 = 45.5%
    assert c and c["side"] == "BACK" and c["selection_id"] == "A" and c["edge"] == pytest.approx(0.0955, abs=1e-3)
    assert Recs.candidate("tennis", INFO, book(back=2.0, lay=2.02, b=(2.0, 2.02)), CTX(0.51)) is None          # edge under 4 points
    assert Recs.candidate("tennis", INFO, book(back=2.2, lay=3.0, b=(2.2, 2.24)), CTX(0.55)) is None            # spread too wide to trust
    assert Recs.candidate("tennis", INFO, book(), None) is None                                  # no model, no idea


def test_candidate_can_suggest_a_lay():
    c = Recs.candidate("tennis", INFO, book(back=1.8, lay=1.82, b=(1.8, 1.82)), CTX(0.45))     # model 45% vs market 55%: lay A
    assert c["side"] == "LAY" and c["selection_id"] == "A"


def test_upsert_refreshes_same_idea_and_replaces_a_different_one_and_never_claims_high_confidence():
    r = Recs()
    c1 = Recs.candidate("tennis", INFO, book(back=2.2, lay=2.24, b=(2.5, 2.52)), CTX(0.60))
    a, new = r.upsert("1.5", INFO, c1, 10)
    assert new and a["confidence"] == "Medium" and "not yet beaten the market" in a["reason"] and a["max_loss"] == 10
    b, new2 = r.upsert("1.5", INFO, c1, 10)
    assert not new2 and b["id"] == a["id"]
    st = r.stats()
    assert st["pending"] == 1 and st["evidence"] == 0 and st["auto_apply_unlocked"] is False
    assert all(x["confidence"] != "High" for x in r.items.values())


def test_clv_is_measured_when_the_market_goes_in_play(eng=None):
    class Feed:
        def get_books(self, ids, depth=False):
            return [book(in_play=True)]
    class E: feed = Feed()
    r = Recs()
    rec, _ = r.upsert("1.5", INFO, Recs.candidate("tennis", INFO, book(back=2.2, lay=2.24, b=(2.5, 2.52)), CTX(0.6)), 10)
    rec["last_back"], rec["last_lay"] = 2.0, 2.02          # market shortened from 2.2 to ~2.01 before the off
    assert r.measure_clv(E()) == 1
    assert rec["clv"] > 0 and rec["status"] == "expired"    # backed at 2.2, closed ~2.01: moved our way


def test_alerts_dedupe_by_key_and_resolve():
    a = Alerts()
    assert a.add("warning", "feed stale", needs_action=True, key="h:x") and a.add("warning", "feed stale", key="h:x") is None
    assert a.counts()["needs_action"] == 1
    a.resolve("h:x", "Recovered")
    assert a.counts()["needs_action"] == 0 and a.add("warning", "stale again", key="h:x")
    assert [x["text"] for x in a.list("warnings")] == ["stale again", "feed stale"]
    assert a.mark_read() == 2 and a.counts()["unread"] == 0


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return TestClient(create_app(Engine.demo()))


def _seed_rec(e):
    st = e.state([MID])
    price = st["markets"][MID]["selections"]["101"]["backs"][0][0]
    info = {"runners": {"101": "A. Player"}, "event": "A v B", "name": "Match Odds", "start": None}
    cand = {"selection_id": "101", "runner": "A. Player", "side": "BACK", "price": price, "model_p": 0.7, "market_p": round(1 / price, 4), "edge": 0.1, "back": price, "lay": price + 0.02, "sport": "tennis"}
    rec, _ = e.recs.upsert(MID, info, cand, 10)
    return rec


def test_apply_places_an_ai_order_adds_a_plan_row_and_cannot_be_applied_twice():
    e = Engine.demo()
    rec = _seed_rec(e)
    out = e.rec_apply(rec["id"])
    assert out["rec"]["status"] == "applied" and e.ex.get_order(out["order"]["order_id"]).request.source == "ai"
    assert any(r["added_by"] == "ai" and r["state"] == "watching" for r in e.plan.rows.values())
    with pytest.raises(ValueError, match="applied"):
        e.rec_apply(rec["id"])


def test_apply_is_blocked_when_automation_is_off_and_dismiss_records_reason():
    e = Engine.demo()
    rec = _seed_rec(e)
    e.update_settings({"automation_enabled": False})
    with pytest.raises(ValueError, match="kill switch"):
        e.rec_apply(rec["id"])
    assert e.rec_dismiss(rec["id"], "edge too small")["status"] == "dismissed"


def test_recs_alerts_health_endpoints(client):
    assert client.get("/api/recs").json()["stats"]["pending"] == 0
    assert client.get("/api/recs/nope/apply").status_code in (404, 405)
    assert client.post("/api/recs/nope/apply", json={}).status_code == 404
    assert client.post("/api/recs/nope/dismiss", json={}).status_code == 404
    al = client.get("/api/alerts").json()
    assert "counts" in al and al["items"] == []
    client.post("/api/automation/stop")
    al = client.get("/api/alerts?chip=warnings").json()
    assert any("Automation stopped" in a["text"] for a in al["items"])
    assert client.post("/api/alerts/read", json={}).json()["marked"] >= 1
    h = client.get("/api/health").json()
    assert {i["key"] for i in h["items"]} >= {"betfair", "tennis", "football", "claude"} and h["issues"] == 0
