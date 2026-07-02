import asyncio
import os

# Must be set before app.config is imported: the shared limiter reads it at import.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.models.database as database
from app.config import settings
from app.main import app


@pytest.fixture()
def client(tmp_path):
    """TestClient backed by a fresh temp SQLite DB, restoring globals afterwards."""
    db_path = (tmp_path / "test_app.db").resolve()
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    old_database_url = settings.DATABASE_URL
    old_engine = database.engine
    old_session = database.AsyncSessionLocal

    test_engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    test_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    settings.DATABASE_URL = db_url
    database.engine = test_engine
    database.AsyncSessionLocal = test_session

    with TestClient(app) as test_client:
        yield test_client

    settings.DATABASE_URL = old_database_url
    database.engine = old_engine
    database.AsyncSessionLocal = old_session
    asyncio.run(test_engine.dispose())
