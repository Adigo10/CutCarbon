"""
SQLAlchemy async database layer.

Primary backend is Supabase Postgres via asyncpg. A sqlite+aiosqlite:// URL still
works as a local dev fallback. The schema is owned by Alembic on Postgres — see
alembic/ — so init_db() no longer runs migrations there.
"""
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, JSON, Uuid, text,
    ForeignKey, Index, event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
try:
    from sqlalchemy.orm import DeclarativeBase
except ImportError:  # SQLAlchemy 1.4 fallback
    DeclarativeBase = None
from sqlalchemy.orm import declarative_base

from app.config import settings
from app.utils.time import utcnow

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:  # SQLAlchemy 1.4 fallback
    async_sessionmaker = None


def _make_engine(url: str):
    """Build a dialect-aware async engine.

    Postgres runs behind Supabase's transaction pooler (pgbouncer, port 6543), so
    server-side prepared statements must be disabled at both the asyncpg layer
    (statement_cache_size) and the SQLAlchemy-dialect layer
    (prepared_statement_cache_size); a unique statement-name func avoids
    "prepared statement already exists" when pgbouncer reuses a server connection.
    NullPool leaves connection pooling to pgbouncer and — importantly for the test
    suite — means every session checkout opens a fresh asyncpg connection bound to
    the current event loop, so cross-loop `asyncio.run(...)` usages don't clash.
    """
    if url.startswith("postgresql+asyncpg"):
        return create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
            },
        )
    return create_async_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in url else {},
    )


def _register_sqlite_fk_pragma(target_engine) -> None:
    """SQLite needs PRAGMA foreign_keys=ON per connection to enforce FKs. Postgres
    enforces them natively, so this is only wired up for the sqlite dev fallback."""
    @event.listens_for(target_engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = _make_engine(settings.DATABASE_URL)

if "sqlite" in settings.DATABASE_URL:
    _register_sqlite_fk_pragma(engine)

if async_sessionmaker is not None:
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
else:
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Portable column helpers: UUID renders as native `uuid` on Postgres and CHAR(32)
# on sqlite; JSON becomes JSONB on Postgres. as_uuid=False keeps ids as plain
# strings in Python (matching the Supabase `sub` claim and UserOut.id: str).
def _uuid_col(*args, **kwargs):
    return Column(Uuid(as_uuid=False), *args, **kwargs)


def _json_col(*args, **kwargs):
    return Column(JSON().with_variant(JSONB, "postgresql"), *args, **kwargs)


if DeclarativeBase is not None:
    class Base(DeclarativeBase):
        pass
else:
    Base = declarative_base()


# -- ORM Models ----------------------------------------------------------------

class UserDB(Base):
    """App-side profile keyed by the Supabase auth UUID.

    Rows are JIT-provisioned on the first authenticated request (see
    app/routers/auth.py). Credentials live in Supabase's auth.users, not here —
    there is no password column.
    """

    __tablename__ = "users"

    id = _uuid_col(primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    is_active = Column(Boolean, default=True)


class ScenarioDB(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        Index("ix_scenarios_user_created", "user_id", "created_at"),
    )

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    event_name = Column(String)
    location = Column(String)
    event_type = Column(String, default="conference")
    attendees = Column(Integer)
    event_days = Column(Integer)
    mode = Column(String, default="basic")

    # Emissions breakdown (stored flat for easy querying)
    travel_tco2e = Column(Float, default=0.0)
    venue_energy_tco2e = Column(Float, default=0.0)
    accommodation_tco2e = Column(Float, default=0.0)
    catering_tco2e = Column(Float, default=0.0)
    materials_waste_tco2e = Column(Float, default=0.0)
    equipment_tco2e = Column(Float, default=0.0)
    swag_tco2e = Column(Float, default=0.0)
    digital_tco2e = Column(Float, default=0.0)
    total_tco2e = Column(Float, default=0.0)
    per_attendee_tco2e = Column(Float, default=0.0)
    data_quality = Column(String, default="estimated")

    # Scope breakdown
    scope1_tco2e = Column(Float, default=0.0)
    scope2_tco2e = Column(Float, default=0.0)
    scope3_tco2e = Column(Float, default=0.0)

    assumptions = _json_col(default=dict)
    input_payload = _json_col(default=dict)
    factors_snapshot = _json_col(default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    user_id = _uuid_col(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_user_session_created", "user_id", "session_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String)
    content = Column(Text)
    extracted_data = _json_col(nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    user_id = _uuid_col(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


class FinancialReportDB(Base):
    __tablename__ = "financial_reports"
    __table_args__ = (
        Index("ix_financial_reports_user_scenario_created", "user_id", "scenario_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    region = Column(String)
    baseline_tco2e = Column(Float)
    reduced_tco2e = Column(Float)
    total_savings_usd = Column(Float)
    report_json = _json_col()
    created_at = Column(DateTime, default=utcnow, index=True)
    user_id = _uuid_col(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


class EmissionFactorDB(Base):
    """Audit log of TinyFish-fetched factor values with provenance.

    Deliberately write-only: emission_factors.json is the live source of truth for
    calculations; this table records what each agent fetched and when, so auto-fetched
    values (is_verified=False) can be human-reviewed later.
    """

    __tablename__ = "emission_factors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String)
    subcategory = Column(String)
    region = Column(String)
    factor_value = Column(Float)
    unit = Column(String)
    source_url = Column(String, nullable=True)
    methodology_tag = Column(String, nullable=True)
    last_updated = Column(DateTime, default=utcnow)
    is_verified = Column(Boolean, default=False)


class OffsetPurchaseDB(Base):
    __tablename__ = "offset_purchases"
    __table_args__ = (
        Index("ix_offset_purchases_user_scenario_status", "user_id", "scenario_id", "status"),
        Index("ix_offset_purchases_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = _uuid_col(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id = Column(String, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    project_type = Column(String, nullable=False)
    registry = Column(String, nullable=False)
    quantity_tco2e = Column(Float, nullable=False)
    price_per_tco2e_usd = Column(Float, nullable=False)
    total_cost_usd = Column(Float, nullable=False)
    vintage_year = Column(Integer)
    serial_number = Column(String, nullable=True)
    status = Column(String, default="purchased", index=True)  # purchased | retired | cancelled
    retired_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class AgentRunDB(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    status = Column(String, default="success")  # success | error | skipped
    run_id = Column(String, nullable=True)
    num_steps = Column(Integer, nullable=True)
    result_json = _json_col(nullable=True)
    error = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=utcnow, index=True)


# -- Session dependency --------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Startup DB bootstrap.

    On Postgres the schema is owned by Alembic (see alembic/). Migrations are
    applied out-of-band by default; set RUN_MIGRATIONS_ON_STARTUP=true to run
    `alembic upgrade head` from the lifespan (single-instance dev/demo only).

    On the sqlite dev fallback there is no Alembic, so we create tables directly
    from the model metadata.
    """
    if "sqlite" in settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    if settings.RUN_MIGRATIONS_ON_STARTUP:
        _run_alembic_upgrade_head()


def _run_alembic_upgrade_head() -> None:
    """Apply Alembic migrations synchronously (used only when opted in)."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")
