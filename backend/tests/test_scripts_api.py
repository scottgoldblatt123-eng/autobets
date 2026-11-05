import pytest
from fastapi.testclient import TestClient
from autobets.api.app import create_app
from autobets.api.engine import Engine
from tests.test_scripts import LAY_A

MID = "1.900001"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return TestClient(create_app(Engine.demo()))


def test_script_crud_and_validation(client):
    assert client.post("/api/scripts", json={"name": "x", "rules": []}).status_code == 422
    s = client.post("/api/scripts", json=LAY_A).json()
    assert s["version"] == 1 and s["text"][0]["id"] == "r1"
    assert client.put(f"/api/scripts/{s['id']}", json={**LAY_A, "name": "Renamed"}).json()["version"] == 2
    assert client.post(f"/api/scripts/{s['id']}/enable", json={"on": True}).json()["enabled"] is True
    c = client.post(f"/api/scripts/{s['id']}/clone", json={"name": "Copy"}).json()
    assert c["name"] == "Copy" and not c["enabled"]
    assert len(client.get("/api/scripts").json()) == 2
    assert client.delete(f"/api/scripts/{c['id']}").status_code == 200
    assert client.put("/api/scripts/nope", json=LAY_A).status_code == 404


def test_plan_flow_rename_follows_and_in_use_script_cannot_be_deleted(client):
    s = client.post("/api/scripts", json=LAY_A).json()
    r = client.post("/api/plan", json={"market_id": MID, "selection_id": "101", "script_id": s["id"]}).json()
    assert r["state"] == "armed" and r["strategy"] == LAY_A["name"] and r["max_liability"] == 12.0
    assert client.post("/api/plan", json={"market_id": MID, "selection_id": "101", "script_id": s["id"]}).status_code == 422     # duplicate
    client.put(f"/api/scripts/{s['id']}", json={**LAY_A, "name": "New name"})
    plan = client.get("/api/plan").json()
    assert plan["rows"][0]["strategy"] == "New name" and plan["summary"]["markets"] == 1 and plan["summary"]["max_liability"] == 12.0
    assert client.delete(f"/api/scripts/{s['id']}").status_code == 422
    assert client.patch(f"/api/plan/{r['id']}", json={"stake": 4}).json()["stake"] == 4
    assert client.patch(f"/api/plan/{r['id']}", json={"stake": 0.5}).status_code == 422
    assert client.delete(f"/api/plan/{r['id']}").status_code == 200
    assert client.delete(f"/api/scripts/{s['id']}").status_code == 200


def test_watching_row_has_no_script_and_bets_list_labels_sources(client):
    r = client.post("/api/plan", json={"market_id": MID, "selection_id": None, "script_id": None}).json()
    assert r["state"] == "watching" and r["strategy"].startswith("None")
    st = client.get(f"/api/state?ids={MID}").json()
    client.post("/api/orders", json={"market_id": MID, "selection_id": "101", "side": "BACK", "price": 50.0, "size": 5})
    bets = client.get("/api/plan/bets").json()
    assert bets[0]["placed_by"] == "You" and bets[0]["strategy"] == "Manual" and bets[0]["runner"]


def test_build_endpoint_without_key_is_a_clear_error(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/api/scripts/build", json={"prompt": "lay the draw"})
    assert r.status_code == 502 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_ai_draft_parses_validates_and_rejects_bad_json():
    from autobets.ai.claude import Claude
    from autobets.ai.scriptbuilder import draft
    from autobets.ai.usage import Usage
    import json
    def fake(text):
        c = Claude(key="k", post=lambda body: {"model": "m", "content": [{"type": "text", "text": text}], "usage": {"input_tokens": 10, "output_tokens": 10}})
        return draft(c, Usage(), "idea")
    ok = fake("Here you go.\n```script\n" + json.dumps(LAY_A) + "\n```")
    assert ok["script"]["name"] == LAY_A["name"] and ok["text"] and ok["error"] is None
    bad = fake("x\n```script\n{\"name\": \"a\", \"rules\": [{\"kind\": \"entry\"}]}\n```")
    assert bad["script"] is None and "not a valid script" in bad["error"]
    none = fake("That needs a condition I do not have.")
    assert none["script"] is None and none["error"] is None


def test_placeholder_events_are_recognised():
    from autobets.api.engine import is_placeholder
    for ev in ("Test W v Test F", "test a v test b", "Test C v Test V", "Demo A v Demo B"):
        assert is_placeholder({"event": ev, "competition": "Other"})
    for ev in ("Arsenal v Chelsea", "Testimonial XI v Celtic", "A. Player v B. Player", "Tester FC v Real Madrid"):
        assert not is_placeholder({"event": ev, "competition": "Friendlies"})
