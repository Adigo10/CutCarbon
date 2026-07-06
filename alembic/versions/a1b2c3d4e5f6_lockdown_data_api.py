"""lock down PostgREST/anon Data API: enable RLS + revoke anon/authenticated grants

Codifies the security posture that Supabase had only enabled out-of-band, so a fresh
`alembic upgrade head` produces locked-down tables instead of world-CRUD ones.

Revision ID: a1b2c3d4e5f6
Revises: 3089f7bc722b
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op

from app.models.database import Base
from app.models.db_security import lock_down_tables, revoke_default_privileges

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3089f7bc722b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# App tables + Alembic's own bookkeeping table (also PostgREST-exposed by default).
_TABLES = [t.name for t in Base.metadata.sorted_tables] + ["alembic_version"]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # sqlite dev fallback has no PostgREST / anon roles
    # op.get_bind() is already a sync Connection under Alembic's run_sync wrapper.
    lock_down_tables(bind, _TABLES, "public")
    revoke_default_privileges(bind, "public")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    # Restore Supabase's default posture (RLS off; anon/authenticated grants back).
    roles = [
        r[0]
        for r in bind.execute(
            text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
        ).all()
    ]
    roles_csv = ", ".join(roles)
    for table in _TABLES:
        op.execute(f'ALTER TABLE "public"."{table}" DISABLE ROW LEVEL SECURITY')
        if roles:
            op.execute(f'GRANT ALL ON "public"."{table}" TO {roles_csv}')
    if roles:
        for kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
            op.execute(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "public" GRANT ALL ON {kind} TO {roles_csv}'
            )
