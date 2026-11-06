import pytest
from fastapi.testclient import TestClient
from autobets.api.app import create_app
from autobets.api.engine import Engine
from autobets.scripts import validate
from autobets.starters import STARTERS, UNSUPPORTED


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("AUTOBETS_TOKEN", raising=False)
    return TestClient(create_app(Engine.demo()))


def test_every_starter_validates_and_ids_are_unique():
    assert len({s["id"] for s in STARTERS}) == len(STARTERS)
    for s in STARTERS:
        validate(s["script"])
        assert s["caveats"] is not None and s["summary"] and UNSUPPORTED


def test_list_and_add_creates_a_disabled_script_once(client):
    r = client.get("/api/starters").json()
    assert len(r["items"]) == len(STARTERS) and r["unsupported"] and not any(i["added"] for i in r["items"])
    sid = r["items"][0]["id"]
    s = client.post(f"/api/starters/{sid}/add")
    assert s.status_code == 200 and s.json()["enabled"] is False
    assert client.post(f"/api/starters/{sid}/add").status_code == 409
    assert client.get("/api/starters").json()["items"][0]["added"] is True
    assert client.post("/api/starters/nope/add").status_code == 404
