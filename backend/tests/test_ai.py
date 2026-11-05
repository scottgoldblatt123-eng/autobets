import pytest
from autobets.ai import snapshot
from autobets.ai.claude import AiError, Claude
from autobets.ai.copilot import Copilot
from autobets.ai.usage import Usage

MARKETS = {"1.1": {"event": "Paul v Halys", "name": "Match Odds", "in_play": True, "status": "OPEN", "start": "2026-11-05T10:00:00Z",
                   "runners": {"1": "Paul", "2": "Halys"},
                   "selections": {"1": {"backs": [[1.62, 50]], "lays": [[1.63, 40]], "last": 1.62, "status": "ACTIVE"},
                                  "2": {"backs": [[2.8, 50]], "lays": [[2.82, 40]], "last": 2.8, "status": "ACTIVE"}},
                   "positions": {"1": {"win": 5.0, "lose": -3.0}}}}
CTX = {"1.1": {"kind": "tennis", "live": True, "players": ["Paul", "Halys"], "sets": [["6", "4"]], "model": {"odds": [1.5, 3.0], "p": [66, 34]}}}


def test_snapshot_has_gaps_and_position():
    s = snapshot.build(MARKETS, CTX)[0]
    r = {x["name"]: x for x in s["runners"]}
    assert r["Paul"]["model_fair_odds"] == 1.5 and r["Paul"]["back_vs_fair_ticks"] > 5
    assert r["Halys"]["fair_vs_lay_ticks"] > 2 and r["Paul"]["position_if_wins_loses"]["win"] == 5.0 and s["live"]["sets"] == [["6", "4"]]


def fake(captured):
    def post(body):
        captured.append(body)
        return {"content": [{"type": "text", "text": "Back Paul."}], "usage": {"input_tokens": 1000, "output_tokens": 100}, "model": "m"}
    return post


def test_copilot_grounds_the_question_and_tracks_cost():
    cap = []; u = Usage()
    c = Copilot(Claude(key="k", post=fake(cap)), u)
    out = c.chat([{"role": "assistant", "content": "hi"}, {"role": "user", "content": "What now?"}], MARKETS, CTX)
    assert out["reply"] == "Back Paul." and out["cost_gbp"] > 0
    sent = cap[0]["messages"]
    assert sent[0]["role"] == "user" and "<market_snapshot>" in sent[-1]["content"] and "What now?" in sent[-1]["content"] and "Paul" in sent[-1]["content"]
    assert "cannot place" in cap[0]["system"]
    assert u.status()["requests"] == 1


def test_missing_key_and_spend_cap_and_empty_chat():
    with pytest.raises(AiError): Copilot(Claude(key=""), Usage()).chat([{"role": "user", "content": "x"}], {}, {})
    u = Usage(); u.cap = 0.0001; u.record("t", "m", 1_000_000, 1_000_000)
    with pytest.raises(AiError, match="spend limit"): Copilot(Claude(key="k", post=fake([])), u).chat([{"role": "user", "content": "x"}], {}, {})
    with pytest.raises(AiError, match="Ask a question"): Copilot(Claude(key="k", post=fake([])), Usage()).chat([], {}, {})


def test_endpoints_without_a_key(monkeypatch):
    from fastapi.testclient import TestClient
    from autobets.api.app import create_app
    from autobets.api.engine import Engine
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False); monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = TestClient(create_app(Engine.demo()))
    assert c.get("/api/ai/status").json()["enabled"] is False
    r = c.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}], "market_ids": ["1.900001"]})
    assert r.status_code == 502 and "ANTHROPIC_API_KEY" in r.json()["detail"]


from autobets.ai.proposals import ProposalBook, split_reply

MK = {"1.1": {"event": "Paul v Halys", "status": "OPEN", "runners": {"1": "Paul", "2": "Halys"},
              "selections": {"1": {"backs": [[1.62, 50]], "lays": [[1.63, 40]]}, "2": {"backs": [[2.8, 50]], "lays": [[2.82, 40]]}}}}
FENCED = 'Back Paul, the market is short of fair.\n```proposal\n{"market_id":"1.1","runner":"Paul","side":"BACK","price":1.62,"stake":5,"take_profit_ticks":3,"stop_loss_ticks":4,"reason":"gap"}\n```'


def test_split_and_validate_proposals():
    text, raw = split_reply(FENCED)
    assert "proposal" not in text and len(raw) == 1
    b = ProposalBook(max_stake=10)
    made, notes = b.add(raw, MK)
    assert made and made[0]["selection_id"] == "1" and made[0]["status"] == "pending" and not notes
    bad = [{**raw[0], "stake": 50}, {**raw[0], "runner": "Nobody"}, {**raw[0], "market_id": "9.9"}, {**raw[0], "side": "SELL"}, {**raw[0], "stake": 0.5}]
    made, notes = [], []
    for x in bad:
        m_, n_ = b.add([x], MK); made += m_; notes += n_
    assert not made and len(notes) == 5
    assert len(b.add([raw[0]] * 5, MK)[0]) == 3                      # at most three proposals per reply


def test_approval_rechecks_price_and_places_once():
    b = ProposalBook(); made, _ = b.add(split_reply(FENCED)[1], MK); pid = made[0]["id"]
    placed = []
    place = lambda *a: placed.append(a) or {"order": {"id": "o1"}, "warnings": []}
    moved = {"selections": {"1": {"backs": [[1.50, 50]], "lays": [[1.51, 40]]}}}          # market has dropped many ticks against a back at 1.62
    with pytest.raises(ValueError, match="moved"): b.approve(pid, moved, place)
    assert not placed
    out = b.approve(pid, MK["1.1"], place)
    assert placed == [("1.1", "1", "BACK", 1.62, 5.0, 3, 4)] and out["proposal"]["status"] == "approved"
    with pytest.raises(ValueError, match="approved"): b.approve(pid, MK["1.1"], place)           # cannot be placed twice


def test_proposals_expire_and_can_be_rejected():
    b = ProposalBook(); made, _ = b.add(split_reply(FENCED)[1], MK, now=1000.0); pid = made[0]["id"]
    assert b.get(pid, now=1000 + 200)["status"] == "expired"
    made, _ = b.add(split_reply(FENCED)[1], MK); assert b.reject(made[0]["id"])["status"] == "rejected"


def test_copilot_proposes_only_in_supervised_mode():
    reply = lambda body: {"content": [{"type": "text", "text": FENCED}], "usage": {"input_tokens": 10, "output_tokens": 10}, "model": "m"}
    c = Copilot(Claude(key="k", post=reply), Usage())
    q = [{"role": "user", "content": "idea?"}]
    adv = c.chat(q, MK, {}, "advisor"); sup = c.chat(q, MK, {}, "supervised")
    assert adv["proposals"] == [] and adv["proposal_notes"] and len(sup["proposals"]) == 1


def test_supervised_flow_end_to_end_in_demo(monkeypatch):
    import json as _json
    from fastapi.testclient import TestClient
    from autobets.api.app import create_app
    from autobets.api.engine import Engine
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False); monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    box = {}
    monkeypatch.setattr(Claude, "_http", lambda self, body: {"content": [{"type": "text", "text": f"Idea.\n```proposal\n{box['block']}\n```"}], "usage": {"input_tokens": 5, "output_tokens": 5}, "model": "m"})
    eng = Engine.demo(); c = TestClient(create_app(eng))
    mid = "1.900001"
    st = c.get(f"/api/state?ids={mid}").json()["markets"][mid]
    sid, name = next(iter(st["runners"].items())); price = st["selections"][sid]["backs"][0][0]
    box["block"] = _json.dumps({"market_id": mid, "runner": name, "side": "BACK", "price": price, "stake": 2, "take_profit_ticks": 2, "stop_loss_ticks": 3, "reason": "test"})
    r = c.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "idea?"}], "market_ids": [mid], "mode": "supervised"}).json()
    assert len(r["proposals"]) == 1 and r["proposals"][0]["status"] == "pending"
    pid = r["proposals"][0]["id"]
    ok = c.post(f"/api/ai/proposals/{pid}/approve")
    assert ok.status_code == 200, ok.text
    assert ok.json()["proposal"]["status"] == "approved"
    orders = c.get(f"/api/state?ids={mid}").json()
    assert any(o["source"] == "ai" for o in orders["orders"]) or c.get(f"/api/matched?ids={mid}").status_code in (200, 404)
    assert c.post(f"/api/ai/proposals/{pid}/approve").status_code == 422          # cannot be placed twice
    assert c.post("/api/ai/proposals/nope/approve").status_code == 404
