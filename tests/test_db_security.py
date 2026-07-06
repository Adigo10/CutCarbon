"""Verifies the Data-API lockdown helper (used by the RLS migration): after
lock_down_tables, every app table has RLS enabled and anon/authenticated hold no
grants — even if Supabase's default privileges had granted them full CRUD first.

Self-contained (own scratch schema) so it doesn't slow the shared per-test fixture.
"""
import asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.models.database as database
from app.models.db_security import lock_down_tables

APP_TABLES = [t.name for t in database.Base.metadata.sorted_tables]


def _engine(url: str, schema: str | None = None):
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
    }
    if schema:
        connect_args["server_settings"] = {"search_path": schema}
    return create_async_engine(url, poolclass=NullPool, connect_args=connect_args)


def test_lockdown_enables_rls_and_revokes_api_role_grants(pg_base_url):
    schema = f"sec_{uuid4().hex}"
    admin = _engine(pg_base_url)
    eng = _engine(pg_base_url, schema)

    async def setup():
        async with admin.begin() as c:
            await c.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with eng.begin() as c:
            await c.run_sync(database.Base.metadata.create_all)
            # Simulate Supabase's default full-CRUD grants to prove the revoke removes them.
            api_roles = [
                r[0]
                for r in (
                    await c.execute(
                        text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
                    )
                ).all()
            ]
            for t in APP_TABLES:
                for role in api_roles:
                    await c.execute(text(f'GRANT ALL ON "{schema}"."{t}" TO {role}'))
            await c.run_sync(lambda s: lock_down_tables(s, APP_TABLES, schema))

    asyncio.run(setup())

    try:
        async def checks():
            async with eng.connect() as c:
                rls = (
                    await c.execute(
                        text(
                            "SELECT relname, relrowsecurity FROM pg_class "
                            "WHERE relnamespace = to_regnamespace(:s) AND relkind = 'r'"
                        ),
                        {"s": schema},
                    )
                ).all()
                assert rls, "no tables found in scratch schema"
                off = [name for name, on in rls if not on]
                assert not off, f"RLS not enabled on: {off}"

                grants = (
                    await c.execute(
                        text(
                            "SELECT grantee, table_name FROM information_schema.role_table_grants "
                            "WHERE table_schema = :s AND grantee IN ('anon','authenticated')"
                        ),
                        {"s": schema},
                    )
                ).all()
                assert grants == [], f"anon/authenticated still hold grants: {grants}"

        asyncio.run(checks())
    finally:
        async def teardown():
            async with admin.begin() as c:
                await c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await eng.dispose()
            await admin.dispose()

        asyncio.run(teardown())
