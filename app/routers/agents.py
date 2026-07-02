from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import select, desc, func

from app.models.database import AgentRunDB, AsyncSessionLocal, UserDB
from app.rate_limit import limiter
from app.services.tinyfish_agent import run_and_update, REGISTERED_AGENTS, AGENT_TTL_HOURS
from app.routers.auth import get_current_user, require_admin

router = APIRouter()


# Agent runs scrape ~10 external sites and rewrite the emission-factor file that
# drives EVERY user's calculations — admin-only, and rate limited even for admins.

@router.post("/run")
@limiter.limit("2/hour")
async def trigger_agents(
    request: Request,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Bypass TTL cache and re-fetch all agents"),
    current_user: UserDB = Depends(require_admin),
):
    """Trigger all TinyFish web agents to refresh emission factor data (admin only)."""
    background_tasks.add_task(run_and_update, force)
    return {
        "status": "agents_dispatched",
        "agents": [a.name for a in REGISTERED_AGENTS],
        "force": force,
        "ttl_hours": AGENT_TTL_HOURS,
        "note": "Agents run in background; check /agents/status for results",
    }


@router.get("/run/sync")
@limiter.limit("2/hour")
async def trigger_agents_sync(
    request: Request,
    force: bool = Query(False, description="Bypass TTL cache"),
    current_user: UserDB = Depends(require_admin),
):
    """Synchronously run all agents and return results (admin only; may be slow)."""
    result = await run_and_update(force=force)
    return result


@router.get("/status")
async def agent_status(current_user: UserDB = Depends(get_current_user)):
    """Return last run info for each registered agent, including DB history."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=AGENT_TTL_HOURS)

    async with AsyncSessionLocal() as session:
        # Get the most recent run per agent name
        subq = (
            select(AgentRunDB.agent_name, func.max(AgentRunDB.fetched_at).label("latest"))
            .group_by(AgentRunDB.agent_name)
            .subquery()
        )
        rows = (
            await session.execute(
                select(AgentRunDB)
                .join(subq, (AgentRunDB.agent_name == subq.c.agent_name) & (AgentRunDB.fetched_at == subq.c.latest))
            )
        ).scalars().all()
    last_runs = {r.agent_name: r for r in rows}

    return [
        {
            "name": a.name,
            "category": a.category,
            "url": a.url,
            "goal_preview": a.goal[:80] + "…",
            "ttl_hours": AGENT_TTL_HOURS,
            "last_run": last_runs[a.name].fetched_at.isoformat() if a.name in last_runs else None,
            "last_status": last_runs[a.name].status if a.name in last_runs else None,
            "cache_valid": (
                last_runs[a.name].status == "success"
                and last_runs[a.name].fetched_at >= cutoff
            ) if a.name in last_runs else False,
            "run_id": last_runs[a.name].run_id if a.name in last_runs else None,
        }
        for a in REGISTERED_AGENTS
    ]


@router.get("/history")
async def agent_history(
    agent_name: str = Query(None, description="Filter by agent name"),
    limit: int = Query(50, le=200),
    current_user: UserDB = Depends(get_current_user),
):
    """Return paginated agent run history from the database."""
    async with AsyncSessionLocal() as session:
        q = select(AgentRunDB).order_by(desc(AgentRunDB.fetched_at)).limit(limit)
        if agent_name:
            q = q.where(AgentRunDB.agent_name == agent_name)
        rows = (await session.execute(q)).scalars().all()

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
