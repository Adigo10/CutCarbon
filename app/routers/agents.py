from fastapi import APIRouter, BackgroundTasks
from app.services.tinyfish_agent import run_and_update, REGISTERED_AGENTS

router = APIRouter()


@router.post("/run")
async def trigger_agents(background_tasks: BackgroundTasks):
    """Trigger all TinyFish web agents to refresh emission factor data."""
    background_tasks.add_task(run_and_update)
    return {
        "status": "agents_dispatched",
        "agents": [a.name for a in REGISTERED_AGENTS],
        "note": "Agents run in background; check /agents/status for results",
    }


@router.get("/run/sync")
async def trigger_agents_sync():
    """Synchronously run all agents and return results (may be slow)."""
    result = await run_and_update()
    return result


@router.get("/status")
async def agent_status():
    """Return last run info for each registered agent."""
    return [
        {
            "name": a.name,
            "category": a.category,
            "url": a.url,
            "goal_preview": a.goal[:80] + "…",
            "last_run": a.last_run.isoformat() if a.last_run else None,
            "has_result": a.last_result is not None,
        }
        for a in REGISTERED_AGENTS
    ]
