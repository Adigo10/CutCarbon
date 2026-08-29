"""least-privilege runtime role `cutcarbon_app` + permissive RLS policies

Creates a non-owner, non-bypassrls login role scoped to DML on the app tables, plus a
FOR ALL policy so it works under the RLS enabled in the previous migration. The app's
per-user ownership is still enforced in Python; this is defense-in-depth + blast-radius
reduction (the runtime can no longer DDL, manage roles, or read the auth schema).

The role's PASSWORD is intentionally NOT set here — set it out-of-band (Supabase SQL
editor: `ALTER ROLE cutcarbon_app PASSWORD '...'`) and point runtime DATABASE_URL at it.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APP_ROLE = "cutcarbon_app"
# The app tables that exist as of this revision. Literal, not `Base.metadata` — see
# the note in a1b2c3d4e5f6. The ALTER DEFAULT PRIVILEGES grant below still covers
# tables created by later migrations; each of those also creates its own RLS policy.
_TABLES = [
    "agent_runs",
    "emission_factors",
    "users",
    "chat_messages",
    "scenarios",
    "financial_reports",
    "offset_purchases",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                CREATE ROLE {_APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {_APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_APP_ROLE}"
    )
    for table in _TABLES:
        q = f'"public"."{table}"'
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {q} TO {_APP_ROLE}")
        op.execute(f'DROP POLICY IF EXISTS app_all ON {q}')
        op.execute(
            f"CREATE POLICY app_all ON {q} FOR ALL TO {_APP_ROLE} USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in _TABLES:
        op.execute(f'DROP POLICY IF EXISTS app_all ON "public"."{table}"')
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {_APP_ROLE}';
                EXECUTE 'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {_APP_ROLE}';
                EXECUTE 'REVOKE USAGE ON SCHEMA public FROM {_APP_ROLE}';
                EXECUTE 'DROP OWNED BY {_APP_ROLE}';
                EXECUTE 'DROP ROLE {_APP_ROLE}';
            END IF;
        END
        $$;
        """
    )
