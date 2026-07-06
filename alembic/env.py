"""Alembic environment — async, wired to the app's settings and model metadata."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.config import settings
# Importing the database module registers every ORM model on Base.metadata.
from app.models.database import Base, _make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    # Migrations need a stable session + prepared statements → point this at the
    # session pooler (5432) or the direct connection, NOT the transaction pooler.
    return settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL


def _include_object(obj, name, type_, reflected, compare_to):
    # public.users.id -> auth.users(id) is added via raw SQL in a migration (the auth
    # schema is owned by Supabase, not our model). Exclude it so autogenerate/`alembic
    # check` don't try to drop this cross-schema FK and report false drift.
    if type_ == "foreign_key_constraint":
        referred = getattr(obj, "referred_table", None)
        if referred is not None and referred.schema == "auth":
            return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        # Commit each migration on its own so a dropped connection mid-run (the direct
        # IPv6 connection to Supabase is flaky) doesn't roll back already-applied ones.
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = _make_engine(_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
