"""Data-API lockdown helpers (Postgres/Supabase only).

Supabase auto-exposes the `public` schema through PostgREST, reachable with the
browser-embedded publishable (`anon`) key, and its default grants give `anon` /
`authenticated` full CRUD on every table. This app never uses PostgREST — all data
goes through FastAPI as a privileged DB role — so those API roles should have no
access at all. These helpers enable RLS (defense-in-depth) and revoke the grants,
and are called from both the Alembic migration (on `public`) and the security test
(on a scratch schema) so the invariant is verified the same way it is deployed.
"""
from sqlalchemy import text


def _api_roles_present(sync_conn) -> list[str]:
    rows = sync_conn.execute(
        text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
    ).all()
    return [r[0] for r in rows]


def lock_down_tables(sync_conn, table_names, schema: str = "public") -> None:
    """Enable RLS and revoke anon/authenticated grants on each table.

    Runs inside `connection.run_sync(...)`. Safe to call more than once. On a bare
    Postgres without Supabase's `anon`/`authenticated` roles the REVOKE is skipped.
    """
    api_roles = _api_roles_present(sync_conn)
    roles_csv = ", ".join(api_roles)
    for table in table_names:
        qualified = f'"{schema}"."{table}"'
        sync_conn.execute(text(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY"))
        if api_roles:
            sync_conn.execute(text(f"REVOKE ALL ON {qualified} FROM {roles_csv}"))


def revoke_default_privileges(sync_conn, schema: str = "public") -> None:
    """Stop future objects created in `schema` by the current role from auto-granting
    anything to anon/authenticated (closes the 'next Alembic table is world-CRUD' gap)."""
    api_roles = _api_roles_present(sync_conn)
    if not api_roles:
        return
    roles_csv = ", ".join(api_roles)
    for kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
        sync_conn.execute(
            text(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                f"REVOKE ALL ON {kind} FROM {roles_csv}"
            )
        )
