from fastapi.testclient import TestClient

from app.config import settings
import app.routers.agents as agents_router

from helpers import register_user


def _mock_run_and_update(monkeypatch):
    calls = {"count": 0}

    async def fake_run_and_update(force=False):
        calls["count"] += 1
        return {"status": "ok", "force": force, "results": {}}

    monkeypatch.setattr(agents_router, "run_and_update", fake_run_and_update)
    return calls


def test_agent_triggers_require_admin(client: TestClient, monkeypatch):
    _mock_run_and_update(monkeypatch)
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")

    user_headers = register_user(client, email="pleb@example.com")
    admin_headers = register_user(client, email="admin@example.com")

    assert client.post("/api/agents/run", headers=user_headers).status_code == 403
    assert client.get("/api/agents/run/sync", headers=user_headers).status_code == 403

    dispatched = client.post("/api/agents/run", headers=admin_headers)
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "agents_dispatched"

    sync = client.get("/api/agents/run/sync", headers=admin_headers)
    assert sync.status_code == 200
    assert sync.json()["status"] == "ok"


def test_empty_admin_list_locks_everyone_out(client: TestClient, monkeypatch):
    _mock_run_and_update(monkeypatch)
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "")
    headers = register_user(client, email="nobody@example.com")
    assert client.post("/api/agents/run", headers=headers).status_code == 403


def test_status_and_history_stay_plain_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")
    headers = register_user(client, email="viewer@example.com")

    status = client.get("/api/agents/status", headers=headers)
    assert status.status_code == 200
    agents = status.json()
    assert len(agents) == 10
    assert {"name", "category", "url", "ttl_hours", "last_run", "cache_valid"} <= set(agents[0])

    history = client.get("/api/agents/history", headers=headers)
    assert history.status_code == 200
    assert history.json() == []

    # Unauthenticated requests are still rejected.
    assert client.get("/api/agents/status").status_code == 401
