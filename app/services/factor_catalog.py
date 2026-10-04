"""Database-backed factors with a consistent snapshot for each request."""
from collections.abc import Mapping
from contextvars import ContextVar
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, HTTPException
from sqlalchemy import select, update, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import database
from app.models.database import FactorCatalogDB
from app.routers.auth import get_current_user
from app.utils.time import utcnow

with open(Path(__file__).parent.parent / "data" / "emission_factors.json", encoding="utf-8") as f:
    BASELINE = json.load(f)

_snapshot = ContextVar("factor_catalog_snapshot", default=None)


class RequestFactors(Mapping):
    """Compatibility facade for engine imports; never shares mutable live state."""

    def __getitem__(self, key):
        return (_snapshot.get() or BASELINE)[key]

    def __iter__(self):
        return iter(_snapshot.get() or BASELINE)

    def __len__(self):
        return len(_snapshot.get() or BASELINE)


EF = RequestFactors()


async def ensure_catalog() -> None:
    async with database.AsyncSessionLocal() as db:
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
        await db.execute(insert(FactorCatalogDB).values(
            id=1, document=deepcopy(BASELINE), revision=0, updated_at=utcnow(),
        ).on_conflict_do_nothing(index_elements=["id"]))
        await db.commit()


async def load_catalog() -> dict:
    async with database.AsyncSessionLocal() as db:
        row = await db.get(FactorCatalogDB, 1)
        if row is None:
            raise RuntimeError("Factor catalog is not initialized; apply migrations and restart")
        return deepcopy(row.document)


async def bind_catalog(current_user=Depends(get_current_user)):
    try:
        snapshot = await load_catalog()
    except Exception as exc:
        raise HTTPException(503, "Factor catalog unavailable") from exc
    token = _snapshot.set(snapshot)
    try:
        yield
    finally:
        _snapshot.reset(token)


class RefreshBusyError(RuntimeError):
    pass


async def acquire_refresh_lease() -> str:
    token = str(uuid4())
    now = utcnow()
    async with database.AsyncSessionLocal() as db:
        result = await db.execute(update(FactorCatalogDB).where(
            FactorCatalogDB.id == 1,
            or_(FactorCatalogDB.refresh_token.is_(None), FactorCatalogDB.refresh_expires_at <= now),
        ).values(refresh_token=token, refresh_expires_at=now + timedelta(seconds=300)))
        await db.commit()
        if result.rowcount != 1:
            raise RefreshBusyError("A factor refresh is already running; retry after it finishes")
    return token


async def release_refresh_lease(token: str) -> None:
    async with database.AsyncSessionLocal() as db:
        await db.execute(update(FactorCatalogDB).where(
            FactorCatalogDB.id == 1, FactorCatalogDB.refresh_token == token,
        ).values(refresh_token=None, refresh_expires_at=None))
        await db.commit()
