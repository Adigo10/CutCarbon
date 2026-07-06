import asyncio
import os
from uuid import uuid4

# These must be set before app.config is imported (settings read env at import time):
#  - the shared limiter reads RATE_LIMIT_ENABLED
#  - the Supabase verifier reads SUPABASE_* to accept the HS256 tokens tests mint
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-only-hs256-secret-please-do-not-use-in-prod-0123456789")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

import app.models.database as database
from app.config import settings
from app.main import app


def _to_asyncpg(url: str) -> str:
    """Normalize a Postgres URL to the asyncpg driver and drop libpq-only params."""
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    # asyncpg doesn't understand libpq's sslmode; strip it (add ?ssl=... yourself if needed).
    if "sslmode=" in url:
        parts = [p for p in url.replace("?", "&", 1).split("&") if not p.startswith("sslmode=")]
        if len(parts) > 1:
            url = parts[0] + "?" + "&".join(parts[1:])
        else:
            url = parts[0]
    return url


def _pg_engine(url: str, schema: str | None = None):
    """A NullPool asyncpg engine (pgbouncer-safe), optionally pinned to a schema.

    NullPool opens a fresh connection per checkout in the *current* event loop, which
    is what lets the direct-session `asyncio.run(...)` tests coexist with the TestClient
    loop without asyncpg's cross-loop connection errors.
    """
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
    }
    if schema:
        connect_args["server_settings"] = {"search_path": schema}
    return create_async_engine(url, echo=False, poolclass=NullPool, connect_args=connect_args)


@pytest.fixture(scope="session")
def pg_base_url() -> str:
    """Base Postgres URL for the test run.

    Primary: TEST_DATABASE_URL (a direct/session connection — NOT the transaction
    pooler, since schema DDL wants a stable session). Fallback: an ephemeral
    testcontainers postgres:15 (requires Docker). Skips the DB-backed suite otherwise.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        # NB: this fixture is a generator (the container branch yields), so this
        # branch must yield too — a plain `return` would yield nothing.
        yield _to_asyncpg(url)
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("Postgres unavailable: set TEST_DATABASE_URL or install testcontainers + Docker")

    container = PostgresContainer("postgres:17")  # match Supabase prod (17.x)
    try:
        container.start()
    except Exception as exc:  # Docker not running / not installed
        pytest.skip(f"Could not start a Postgres testcontainer ({exc}); set TEST_DATABASE_URL")

    try:
        yield _to_asyncpg(container.get_connection_url())
    finally:
        container.stop()


@pytest.fixture()
def client(pg_base_url):
    """TestClient backed by a fresh Postgres schema per test, restoring globals after."""
    assert pg_base_url.startswith("postgresql+asyncpg"), "tests require a Postgres URL"
    schema = f"test_{uuid4().hex}"

    admin_engine = _pg_engine(pg_base_url)
    test_engine = _pg_engine(pg_base_url, schema=schema)

    async def _setup():
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with test_engine.begin() as conn:
            await conn.run_sync(database.Base.metadata.create_all)

    asyncio.run(_setup())

    old_url = settings.DATABASE_URL
    old_engine = database.engine
    old_session = database.AsyncSessionLocal

    settings.DATABASE_URL = pg_base_url
    database.engine = test_engine
    database.AsyncSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.DATABASE_URL = old_url
        database.engine = old_engine
        database.AsyncSessionLocal = old_session

        async def _teardown():
            async with admin_engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await test_engine.dispose()
            await admin_engine.dispose()

        asyncio.run(_teardown())
