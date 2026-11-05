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
