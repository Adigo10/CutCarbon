import asyncio
from copy import deepcopy
from datetime import timedelta

import pytest
from sqlalchemy import select
from app.models import database
from app.models.database import AgentRunDB, FactorCatalogDB
from app.services import factor_catalog as catalog
from app.services import web_search_agent as fetch
from app.config import settings
from app.utils.time import utcnow
from helpers import register_user, create_scenario


def grid_result(agent, value):
    result = agent.extract({"factor": value, "unit": "kg_co2e_per_kwh"})
    result["_provenance"] = {"source_url": agent.url, "run_id": "resp_test", "model": settings.OPENAI_MODEL,
                              "fetched_at": utcnow().isoformat(), "original_unit": "kg_co2e_per_kwh"}
    return result


def test_catalog_atomic_refresh_cache_version_and_exports(client):
    agent = fetch.SingaporeGridFactorAgent()
    async def verify():
        before = await catalog.load_catalog()
        token = await catalog.acquire_refresh_lease()
        try:
            with pytest.raises(catalog.RefreshBusyError):
                await catalog.acquire_refresh_lease()
            result = grid_result(agent, 0.45)
            fields = await fetch._persist_task(agent, token, "success", result)
            assert fields == ["venue_energy.grids.singapore.factor"]
            after = await catalog.load_catalog()
            assert after["version"] != before["version"]
            assert after["venue_energy"]["grids"]["singapore"]["factor"] == 0.45
            assert await fetch._persist_task(agent, token, "success", result) == []
            assert (await catalog.load_catalog())["version"] == after["version"]
            assert (await fetch._get_cached_run(agent.name))["_provenance"] == result["_provenance"]
            await fetch._persist_task(agent, token, "no_data", error="Unsupported unit")
            assert (await catalog.load_catalog())["version"] == after["version"]
        finally:
            await catalog.release_refresh_lease(token)
    asyncio.run(verify())
    headers = register_user(client)
    exported = client.get("/api/exports/emission-factors.json", headers=headers)
    assert exported.json()["venue_energy"]["grids"]["singapore"]["factor"] == 0.45
    status = client.get("/api/agents/status", headers=headers).json()
    sg = next(item for item in status if item["name"] == agent.name)
    assert sg["last_status"] == "no_data" and sg["cache_valid"] is True


def test_concurrent_tasks_merge_without_lost_updates(client):
    sg, uk = fetch.SingaporeGridFactorAgent(), fetch.UKGridFactorAgent()
    async def verify():
        token = await catalog.acquire_refresh_lease()
        try:
            await asyncio.gather(fetch._persist_task(sg, token, "success", grid_result(sg, 0.45)),
                                 fetch._persist_task(uk, token, "success", grid_result(uk, 0.20)))
            factors = await catalog.load_catalog()
            assert factors["venue_energy"]["grids"]["singapore"]["factor"] == 0.45
            assert factors["venue_energy"]["grids"]["uk"]["factor"] == 0.20
        finally:
            await catalog.release_refresh_lease(token)
    asyncio.run(verify())


def test_expired_lease_rejects_late_writer(client):
    async def verify():
        token = await catalog.acquire_refresh_lease()
        async with database.AsyncSessionLocal() as db:
            row = await db.get(FactorCatalogDB, 1)
            row.refresh_expires_at = utcnow() - timedelta(seconds=1)
            await db.commit()
        replacement = await catalog.acquire_refresh_lease()
        with pytest.raises(RuntimeError, match="lease"):
            agent = fetch.SingaporeGridFactorAgent()
            await fetch._persist_task(agent, token, "success", grid_result(agent, 0.5))
        await catalog.release_refresh_lease(token)
        async with database.AsyncSessionLocal() as db:
            assert (await db.get(FactorCatalogDB, 1)).refresh_token == replacement
        await catalog.release_refresh_lease(replacement)
    asyncio.run(verify())


def test_request_snapshot_isolated_from_later_refresh():
    first = deepcopy(catalog.BASELINE)
    first["version"] = "request-one"
    async def request_snapshot(version):
        document = deepcopy(first)
        document["version"] = version
        token = catalog._snapshot.set(document)
        try:
            await asyncio.sleep(0)
            assert catalog.EF["version"] == version
        finally:
            catalog._snapshot.reset(token)
    async def verify():
        await asyncio.gather(request_snapshot("one"), request_snapshot("two"))
    asyncio.run(verify())
    assert catalog.EF["version"] == catalog.BASELINE["version"]


def test_refresh_partial_failure_and_cached_reuse(client, monkeypatch):
    sg, uk = fetch.SingaporeGridFactorAgent(), fetch.UKGridFactorAgent()
    calls = []
    async def run_sg():
        calls.append("sg")
        return grid_result(sg, 0.45)
    async def run_uk():
        raise fetch.NoDataError("No cited value")
    monkeypatch.setattr(sg, "run", run_sg)
    monkeypatch.setattr(uk, "run", run_uk)
    monkeypatch.setattr(fetch, "REGISTERED_AGENTS", [sg, uk])
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-only")
    result = asyncio.run(fetch.run_and_update())
    assert result["status"] == "partial"
    assert result["agent_results"][uk.name]["status"] == "no_data"
    second = asyncio.run(fetch.run_and_update())
    assert second["agent_results"][sg.name]["status"] == "cached"
    assert calls == ["sg"]
    asyncio.run(fetch.run_and_update(force=True))
    assert calls == ["sg", "sg"]


def test_zero_price_is_applied(client):
    async def verify():
        agent = fetch.SingaporeCarbonTaxAgent()
        result = agent.extract({"current_rate_sgd": 0})
        result["_provenance"] = {"source_url": agent.url, "fetched_at": utcnow().isoformat(), "model": settings.OPENAI_MODEL}
        token = await catalog.acquire_refresh_lease()
        try:
            await fetch._persist_task(agent, token, "success", result)
            assert (await catalog.load_catalog())["carbon_tax_live"]["singapore_current_sgd"] == 0
        finally:
            await catalog.release_refresh_lease(token)
    asyncio.run(verify())


def test_scenario_becomes_stale_after_refresh(client):
    headers = register_user(client)
    scenario = create_scenario(client, headers)
    async def refresh():
        agent = fetch.SingaporeGridFactorAgent()
        token = await catalog.acquire_refresh_lease()
        try:
            await fetch._persist_task(agent, token, "success", grid_result(agent, 0.45))
        finally:
            await catalog.release_refresh_lease(token)
    asyncio.run(refresh())
    listed = client.get("/api/scenarios", headers=headers).json()
    updated = next(item for item in listed if item["scenario_id"] == scenario["scenario_id"])
    assert updated["factors_stale"] is True
