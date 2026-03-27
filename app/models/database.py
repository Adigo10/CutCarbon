"""
SQLAlchemy async database layer.
Uses SQLite locally; swap DATABASE_URL to postgresql+asyncpg://... for Postgres.
"""
import json
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, JSON, text
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── ORM Models ─────────────────────────────────────────────────────────────────

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

    id = Column(String, primary_key=True)
    event_id = Column(String)
    name = Column(String, nullable=False)
    event_name = Column(String)
    attendees = Column(Integer)
    event_days = Column(Integer)
    mode = Column(String, default="basic")

    # Emissions breakdown (stored flat for easy querying)
    travel_tco2e = Column(Float, default=0.0)
    venue_energy_tco2e = Column(Float, default=0.0)
    accommodation_tco2e = Column(Float, default=0.0)
    catering_tco2e = Column(Float, default=0.0)
    materials_waste_tco2e = Column(Float, default=0.0)
    total_tco2e = Column(Float, default=0.0)
    per_attendee_tco2e = Column(Float, default=0.0)
    data_quality = Column(String, default="estimated")

    assumptions = Column(JSON, default={})
    input_payload = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=True)


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    role = Column(String)
    content = Column(Text)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=True)


class FinancialReportDB(Base):
    __tablename__ = "financial_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String)
    region = Column(String)
    baseline_tco2e = Column(Float)
    reduced_tco2e = Column(Float)
    total_savings_usd = Column(Float)
    report_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


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


# ── Session dependency ─────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add user_id to existing tables — safe to run repeatedly (SQLite ignores duplicate columns)
        for sql in [
            "ALTER TABLE scenarios ADD COLUMN user_id INTEGER REFERENCES users(id)",
            "ALTER TABLE chat_messages ADD COLUMN user_id INTEGER REFERENCES users(id)",
        ]:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # Column already exists
