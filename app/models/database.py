"""
SQLAlchemy async database layer.
Uses SQLite locally; swap DATABASE_URL to postgresql+asyncpg://... for Postgres.
"""
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, JSON, text,
    ForeignKey, Index, inspect,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine
)
from sqlalchemy.orm import sessionmaker
try:
    from sqlalchemy.orm import DeclarativeBase
except ImportError:  # SQLAlchemy 1.4 fallback
    DeclarativeBase = None
from sqlalchemy.orm import declarative_base

from app.config import settings

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:  # SQLAlchemy 1.4 fallback
    async_sessionmaker = None

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

if async_sessionmaker is not None:
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
else:
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


if DeclarativeBase is not None:
    class Base(DeclarativeBase):
        pass
else:
    Base = declarative_base()


# -- ORM Models ----------------------------------------------------------------

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class EventDB(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    organizer = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScenarioDB(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        Index("ix_scenarios_user_created", "user_id", "created_at"),
        Index("ix_scenarios_event_id", "event_id"),
    )

    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=True)
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
    total_tco2e = Column(Float, default=0.0)
    per_attendee_tco2e = Column(Float, default=0.0)
    data_quality = Column(String, default="estimated")

    # Scope breakdown
    scope1_tco2e = Column(Float, default=0.0)
    scope2_tco2e = Column(Float, default=0.0)
    scope3_tco2e = Column(Float, default=0.0)

    assumptions = Column(JSON, default=dict)
    input_payload = Column(JSON, default=dict)
    factors_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_user_session_created", "user_id", "session_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String)
    content = Column(Text)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)


class FinancialReportDB(Base):
    __tablename__ = "financial_reports"
    __table_args__ = (
        Index("ix_financial_reports_user_scenario_created", "user_id", "scenario_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=True, index=True)
    region = Column(String)
    baseline_tco2e = Column(Float)
    reduced_tco2e = Column(Float)
    total_savings_usd = Column(Float)
    report_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)


class EmissionFactorDB(Base):
    __tablename__ = "emission_factors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String)
    subcategory = Column(String)
    region = Column(String)
    factor_value = Column(Float)
    unit = Column(String)
    source_url = Column(String, nullable=True)
    methodology_tag = Column(String, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)


class OffsetPurchaseDB(Base):
    __tablename__ = "offset_purchases"
    __table_args__ = (
        Index("ix_offset_purchases_user_scenario_status", "user_id", "scenario_id", "status"),
        Index("ix_offset_purchases_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=True, index=True)
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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AgentRunDB(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    status = Column(String, default="success")  # success | error | skipped
    run_id = Column(String, nullable=True)
    num_steps = Column(Integer, nullable=True)
    result_json = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)


# -- Session dependency --------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _table_columns(sync_conn, table_name: str) -> set[str]:
            inspector = inspect(sync_conn)
            if table_name not in inspector.get_table_names():
                return set()
            return {col["name"] for col in inspector.get_columns(table_name)}

        migrations = {
            "scenarios": [
                ("user_id", "ALTER TABLE scenarios ADD COLUMN user_id INTEGER REFERENCES users(id)"),
                ("scope1_tco2e", "ALTER TABLE scenarios ADD COLUMN scope1_tco2e FLOAT DEFAULT 0.0"),
                ("scope2_tco2e", "ALTER TABLE scenarios ADD COLUMN scope2_tco2e FLOAT DEFAULT 0.0"),
                ("scope3_tco2e", "ALTER TABLE scenarios ADD COLUMN scope3_tco2e FLOAT DEFAULT 0.0"),
                ("equipment_tco2e", "ALTER TABLE scenarios ADD COLUMN equipment_tco2e FLOAT DEFAULT 0.0"),
                ("swag_tco2e", "ALTER TABLE scenarios ADD COLUMN swag_tco2e FLOAT DEFAULT 0.0"),
                ("event_type", "ALTER TABLE scenarios ADD COLUMN event_type TEXT DEFAULT 'conference'"),
                ("updated_at", "ALTER TABLE scenarios ADD COLUMN updated_at DATETIME"),
                ("factors_snapshot", "ALTER TABLE scenarios ADD COLUMN factors_snapshot JSON DEFAULT '{}'"),
                ("location", "ALTER TABLE scenarios ADD COLUMN location TEXT"),
            ],
            "chat_messages": [
                ("user_id", "ALTER TABLE chat_messages ADD COLUMN user_id INTEGER REFERENCES users(id)"),
            ],
            "financial_reports": [
                ("user_id", "ALTER TABLE financial_reports ADD COLUMN user_id INTEGER REFERENCES users(id)"),
            ],
        }

        for table_name, table_migrations in migrations.items():
            existing_columns = await conn.run_sync(lambda sync_conn, t=table_name: _table_columns(sync_conn, t))
            for column_name, sql in table_migrations:
                if column_name not in existing_columns:
                    await conn.execute(text(sql))

        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_scenarios_user_created ON scenarios (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_scenarios_event_id ON scenarios (event_id)",
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_user_session_created ON chat_messages (user_id, session_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_financial_reports_user_scenario_created ON financial_reports (user_id, scenario_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_offset_purchases_user_scenario_status ON offset_purchases (user_id, scenario_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_offset_purchases_user_created ON offset_purchases (user_id, created_at)",
        ]
        for sql in indexes:
            await conn.execute(text(sql))
