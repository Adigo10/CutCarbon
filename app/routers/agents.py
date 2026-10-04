from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AgentRunDB, UserDB, get_db
from app.models.schemas import FactorRefreshSummary
from app.rate_limit import limiter
from app.services.web_search_agent import run_and_update, REGISTERED_AGENTS, AGENT_TTL_HOURS
from app.services.factor_catalog import RefreshBusyError
from app.services.openai_client import AIUnavailableError
from app.config import settings
from app.routers.auth import get_current_user, require_admin
from app.utils.time import utcnow

router = APIRouter()


async def _refresh(force: bool):
    try:
        return await run_and_update(force=force)
    except RefreshBusyError as exc:
        raise HTTPException(409, str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Factor refresh could not persist its results") from exc

@router.post("/run", response_model=FactorRefreshSummary)
@limiter.limit("2/hour")
async def trigger_agents(
    request: Request,
    force: bool = Query(False, description="Bypass TTL cache and re-fetch all agents"),
    current_user: UserDB = Depends(require_admin),
):
    """Await a bounded, persistent factor refresh (admin only)."""
    return await _refresh(force)


@router.post("/run/sync", response_model=FactorRefreshSummary)
@limiter.limit("2/hour")
async def trigger_agents_sync(
    request: Request,
    force: bool = Query(False, description="Bypass TTL cache"),
    current_user: UserDB = Depends(require_admin),
):
    """Synchronously run all agents and return results (admin only; may be slow)."""
    return await _refresh(force)


@router.get("/status")
async def agent_status(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Return last run info for each registered agent, including DB history."""
    from datetime import timedelta
    cutoff = utcnow() - timedelta(hours=AGENT_TTL_HOURS)

    # Break timestamp ties deterministically using the autoincrementing ID.
    subq = (
        select(AgentRunDB.id, func.row_number().over(
            partition_by=AgentRunDB.agent_name,
            order_by=(desc(AgentRunDB.fetched_at), desc(AgentRunDB.id)),
        ).label("rank"))
        .subquery()
    )
    rows = (
        await db.execute(
            select(AgentRunDB)
            .join(subq, AgentRunDB.id == subq.c.id).where(subq.c.rank == 1)
        )
    ).scalars().all()
    last_runs = {r.agent_name: r for r in rows}
    successful = (await db.execute(select(AgentRunDB).where(
        AgentRunDB.status == "success", AgentRunDB.fetched_at >= cutoff,
    ))).scalars().all()
    cache_valid = {r.agent_name for r in successful if
                   (r.result_json or {}).get("_provenance", {}).get("model") == settings.OPENAI_MODEL}

    return [
        {
            "name": a.name,
            "category": a.category,
            "url": a.url,
            "goal_preview": a.goal[:80] + "…",
            "ttl_hours": AGENT_TTL_HOURS,
            "last_run": last_runs[a.name].fetched_at.isoformat() if a.name in last_runs else None,
            "last_status": last_runs[a.name].status if a.name in last_runs else None,
            "cache_valid": a.name in cache_valid,
            "run_id": last_runs[a.name].run_id if a.name in last_runs else None,
        }
        for a in REGISTERED_AGENTS
    ]


@router.get("/history")
async def agent_history(
    agent_name: str = Query(None, description="Filter by agent name"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Return paginated agent run history from the database."""
    q = select(AgentRunDB).order_by(desc(AgentRunDB.fetched_at)).limit(limit)
    if agent_name:
        q = q.where(AgentRunDB.agent_name == agent_name)
    rows = (await db.execute(q)).scalars().all()

    return [
        {
            "id": r.id,
            "agent_name": r.agent_name,
            "category": r.category,
            "status": r.status,
            "run_id": r.run_id,
            "num_steps": r.num_steps,
            "source_url": r.source_url,
            "fetched_at": r.fetched_at.isoformat(),
            "error": r.error,
            "data": r.result_json,
        }
        for r in rows
    ]
