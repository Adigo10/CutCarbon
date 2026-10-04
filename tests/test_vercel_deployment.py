import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import settings
from app.main import _validate_runtime_config
from app.routers.agents import _require_durable_worker


ROOT = Path(__file__).resolve().parent.parent


def test_vercel_config_builds_frontend_and_routes_api_before_spa():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    frontend, backend = config["builds"]
    assert frontend == {
        "src": "frontend/package.json",
        "use": "@vercel/static-build",
        "config": {"distDir": "dist"},
    }
    assert backend["src"] == "index.py"
    assert backend["config"]["includeFiles"] == "app/data/**"
    assert config["routes"][0] == {
        "src": "/api(?:/.*)?", "dest": "/index.py",
    }
    assert config["routes"][-1]["dest"] == "/frontend/index.html"
    # Filesystem dispatch would resolve / to the index.py function before the SPA.
    assert not any(route.get("handle") == "filesystem" for route in config["routes"])


def test_vercel_entrypoint_handles_preserved_api_paths():
    env = os.environ.copy()
    env["VERCEL"] = "1"
    code = (
        "from index import app; "
        "from fastapi.testclient import TestClient; "
        "client = TestClient(app); "
        "assert client.get('/api/health').json()['status'] == 'ok'; "
        "assert client.get('/health').status_code == 200; "
        "assert client.get('/api/scenarios').status_code == 401; "
        "assert client.get('/scenarios').status_code == 404"
    )

    subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True)


def test_agent_refresh_rejected_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")

    with pytest.raises(HTTPException) as exc_info:
        _require_durable_worker()

    assert exc_info.value.status_code == 503


def test_agent_refresh_allowed_on_durable_runtime(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)

    _require_durable_worker()


def test_vercel_rejects_sqlite_fallback(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///./cutcarbon.db")
    monkeypatch.setattr(settings, "RUN_MIGRATIONS_ON_STARTUP", False)

    with pytest.raises(RuntimeError, match="persistent Postgres"):
        _validate_runtime_config()


def test_vercel_rejects_startup_migrations(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://example")
    monkeypatch.setattr(settings, "RUN_MIGRATIONS_ON_STARTUP", True)

    with pytest.raises(RuntimeError, match="must be false"):
        _validate_runtime_config()
