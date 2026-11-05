import pytest
from fastapi.testclient import TestClient
from autobets.api.app import create_app
from autobets.api.engine import Engine
from autobets.ledger import Ledger, uk_date
from autobets.settings import Settings

MID = "1.900001"


@pytest.fixture
def eng():
    return Engine.demo()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return TestClient(create_app(Engine.demo()))


def _back(e, size=10, source="manual"):
    st = e.state([MID])
    price = st["markets"][MID]["selections"]["101"]["backs"][0][0]
    return e.place(MID, "101", "BACK", price, size, source=source)


def test_settings_defaults_and_validation():
    s = Settings()
    assert s.daily_loss_limit == 0 and s.weekly_loss_limit == 0 and s.max_open_liability == 0 and s.lay_basis == "stake"
    with pytest.raises(ValueError):
        s.update({"daily_loss_limit": -5})
    with pytest.raises(ValueError):
        s.update({"ai_mode": "full"})
    with pytest.raises(ValueError):
        s.update({"nonsense": 1})
    s.update({"daily_loss_limit": "25", "lay_basis": "liability"})
    assert s.daily_loss_limit == 25.0 and s.lay_basis == "liability"
    with pytest.raises(ValueError):
        s.update({"daily_loss_limit": 99, "ai_mode": "bogus"})
    assert s.daily_loss_limit == 25.0                       # a rejected update changes nothing


def test_ledger_books_a_market_once_and_sums_periods():
    import time
    l = Ledger()
    now = time.time()
    assert l.add("1.1", "A v B", now, -12.5, "x") and not l.add("1.1", "A v B", now, 99, "x")
    l.add("1.2", "C v D", now, 30.0, "y")
    p = l.periods(now)
    assert p["today"] == 17.5 and p["week"] == 17.5 and p["month"] == 17.5 and p["month_markets"] == 2 and p["month_win_rate"] == 50
    assert uk_date(now) is not None


def test_settlement_books_result_and_removes_position(eng):
    _back(eng, 10)
    assert eng.positions()[MID]["101"].lose == -10
    eng.feed.status[MID] = "CLOSED"
    orig = eng.feed.get_books

    def settled(ids, depth=False):
        bs = orig(ids, depth=depth)
        for b in bs:
            for sid, s in b.selections.items():
                s.status = "WINNER" if sid == "101" else "LOSER"
        return bs
    eng.feed.get_books = settled
    assert eng.settle_check() == 1
    assert eng.settle_check() == 0                            # only booked once
    assert MID not in eng.positions()
    e = eng.ledger.entries[0]
    assert e["winner"] == "101" and e["result"] > 0
    assert eng.pnl_summary()["settled_today"] == e["result"]


def test_automated_orders_blocked_by_loss_limit_but_manual_still_allowed(eng):
    eng.update_settings({"daily_loss_limit": 5})
    eng.ledger.add("9.9", "old", __import__("time").time(), -6.0, "z")
    eng._refresh_guard()
    with pytest.raises(ValueError, match="loss limit"):
        _back(eng, 2, source="ai")
    r = _back(eng, 2, source="manual")                        # manual is never blocked
    assert r["order"]["status"] == "MATCHED"
    assert any("loss limit" in w for w in r["warnings"])


def test_no_limit_set_means_no_blocking(eng):
    eng.ledger.add("9.9", "old", __import__("time").time(), -500.0, "z")
    assert _back(eng, 2, source="ai")["order"]["status"] == "MATCHED"


def test_open_liability_limit_counts_automation_only_unless_switched(eng):
    _back(eng, 10, source="manual")
    eng.update_settings({"max_open_liability": 15})
    assert _back(eng, 8, source="ai")["order"]                # manual £10 not counted: 8 <= 15
    eng.update_settings({"include_manual_in_liability": True})
    with pytest.raises(ValueError, match="exposure"):
        _back(eng, 8, source="ai")                            # 10 + 8 + 8 > 15


def test_stop_all_automation_cancels_only_automated_unmatched_orders(eng):
    st = eng.state([MID])
    eng.place(MID, "101", "BACK", 50.0, 5, source="ai")
    eng.place(MID, "101", "BACK", 50.0, 5, source="script:test")
    eng.place(MID, "101", "BACK", 50.0, 5, source="manual")
    out = eng.stop_automation()
    assert out["cancelled"] == 2 and out["automation"] is False
    left = eng.state([MID])["orders"]
    assert len(left) == 1 and left[0]["source"] == "manual"
    with pytest.raises(ValueError, match="kill switch"):
        _back(eng, 2, source="ai")
    assert _back(eng, 2, source="manual")["order"]            # manual trading unaffected
    eng.update_settings({"automation_enabled": True})
    assert _back(eng, 2, source="ai")["order"]


def test_settings_persist_across_restart(tmp_path):
    p = str(tmp_path / "state.json")
    e = Engine(Engine.demo().feed, "demo", state_path=p)
    e.update_settings({"daily_loss_limit": 40, "automation_enabled": False})
    e.ledger.add("1.5", "x", __import__("time").time(), 3.0, "a")
    e._save()
    e2 = Engine(Engine.demo().feed, "demo", state_path=p)
    assert e2.settings.daily_loss_limit == 40 and not e2.settings.automation_enabled and e2.guard.kill_switch
    assert len(e2.ledger.entries) == 1


def test_settings_endpoints(client):
    assert client.get("/api/settings").json()["daily_loss_limit"] == 0
    r = client.put("/api/settings", json={"daily_loss_limit": 30, "ai_max_stake": 5})
    assert r.status_code == 200 and r.json()["ai_max_stake"] == 5
    assert client.put("/api/settings", json={"daily_loss_limit": -1}).status_code == 422
    assert client.get("/api/pnl").json()["limits"]["daily"] == 30
    assert client.post("/api/automation/stop").json()["automation"] is False
    assert client.get("/api/pnl").json()["automation"] is False


def test_ledger_tracks_stake_for_roi_and_home_summary(eng):
    import time
    _back(eng, 10)
    eng.feed.status[MID] = "CLOSED"
    orig = eng.feed.get_books

    def settled(ids, depth=False):
        bs = orig(ids, depth=depth)
        for b in bs:
            for sid, s in b.selections.items():
                s.status = "WINNER" if sid == "101" else "LOSER"
        return bs
    eng.feed.get_books = settled
    eng.settle_check()
    p = eng.ledger.periods(time.time())
    assert p["month_staked"] == 10 and p["month_roi"] == round(100 * p["month"] / 10, 1) and p["last7"] == p["month"]
    h = eng.home()
    assert h["kpis"]["month"] == p["month"] and h["kpis"]["roi"] == p["month_roi"] and h["kpis"]["win_rate"] == 100


def test_home_lists_open_manual_positions_and_planned_markets():
    e = Engine.demo()
    _back(e, 5)
    e.settle_check()
    s = e.scripts.create({"name": "S", "sport": "any", "rules": [{"id": "r1", "kind": "entry", "when": [{"type": "in_play", "value": True}], "then": [{"type": "back", "price": "best", "stake": 5}]}]})
    e.plan.add("1.900002", "201", s["id"], "C v D", "Match Odds", "C", "ai")
    ov = {o["market_id"]: o for o in e.home()["overview"]}
    assert ov[MID]["strategy"] == "Manual" and ov[MID]["matched"] == 5 and ov[MID]["pnl"] is not None
    assert ov["1.900002"]["by"] == "ai" and ov["1.900002"]["strategy"] == "S"


def test_credentials_endpoint_reports_presence_never_values(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-value")
    body = client.get("/api/credentials").text
    assert "sk-secret-value" not in body and '"Anthropic (Claude)"' in body
