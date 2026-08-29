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


def test_vercel_config_defines_vite_and_fastapi_services():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    services = config["experimentalServices"]

    assert services["frontend"] == {
        "entrypoint": "frontend",
        "routePrefix": "/",
        "framework": "vite",
    }
    assert services["backend"]["entrypoint"] == "index.py"
    assert services["backend"]["routePrefix"] == "/api"
    assert services["backend"]["includeFiles"] == "app/data/**"


def test_vercel_entrypoint_uses_service_relative_routes():
    env = os.environ.copy()
    env["VERCEL"] = "1"
    code = (
        "from index import app; "
        "paths = {route.path for route in app.routes}; "
        "assert '/scenarios' in paths; "
        "assert '/api/scenarios' not in paths; "
        "assert '/health' in paths"
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
