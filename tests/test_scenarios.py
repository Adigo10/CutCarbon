import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models.database as database
from app.models.database import ScenarioDB

from helpers import SEEDED_SCENARIO_PAYLOAD, create_scenario, register_user


def test_scenario_crud_roundtrip(client: TestClient):
    headers = register_user(client, email="crud@example.com")

    created = create_scenario(client, headers)
    scenario_id = created["scenario_id"]
    assert created["emissions"]["total_tco2e"] > 0
    assert created["mode"] == "basic"
    assert created["benchmark"] is not None

    fetched = client.get(f"/api/scenarios/{scenario_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["scenario_id"] == scenario_id

    listed = client.get("/api/scenarios", headers=headers)
    assert listed.status_code == 200
    assert [s["scenario_id"] for s in listed.json()] == [scenario_id]

    updated_payload = {**SEEDED_SCENARIO_PAYLOAD, "attendees": 240}
    updated = client.put(f"/api/scenarios/{scenario_id}", json=updated_payload, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["attendees"] == 240
    assert updated.json()["emissions"]["total_tco2e"] != created["emissions"]["total_tco2e"]

    deleted = client.delete(f"/api/scenarios/{scenario_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/api/scenarios/{scenario_id}", headers=headers).status_code == 404


def test_clone_scenario(client: TestClient):
    headers = register_user(client, email="clone@example.com")
    scenario_id = create_scenario(client, headers)["scenario_id"]

    clone = client.post(f"/api/scenarios/{scenario_id}/clone?name=What-if", headers=headers)
    assert clone.status_code == 200
    body = clone.json()
    assert body["name"] == "What-if"
    assert body["scenario_id"] != scenario_id
    assert body["assumptions"]["cloned_from"] == scenario_id
    # Emissions columns are copied verbatim.
    original = client.get(f"/api/scenarios/{scenario_id}", headers=headers).json()
    assert body["emissions"]["total_tco2e"] == original["emissions"]["total_tco2e"]


def test_clone_name_bounds(client: TestClient):
    headers = register_user(client, email="clonebounds@example.com")
    scenario_id = create_scenario(client, headers)["scenario_id"]

    too_long = "x" * 201
    assert client.post(f"/api/scenarios/{scenario_id}/clone?name={too_long}", headers=headers).status_code == 422
    assert client.post(f"/api/scenarios/{scenario_id}/clone?name=", headers=headers).status_code == 422


def test_suggestions_target_pct_bounds(client: TestClient):
    headers = register_user(client, email="sugbounds@example.com")
    scenario_id = create_scenario(client, headers)["scenario_id"]

    ok = client.get(f"/api/scenarios/{scenario_id}/suggestions?target_pct=50", headers=headers)
    assert ok.status_code == 200
    assert client.get(f"/api/scenarios/{scenario_id}/suggestions?target_pct=150", headers=headers).status_code == 422


def test_recalculate_all_isolates_poisoned_rows(client: TestClient):
    headers = register_user(client, email="recalc@example.com")
    good_id = create_scenario(client, headers)["scenario_id"]
    bad_id = create_scenario(client, headers, name="Poisoned")["scenario_id"]

    async def _poison():
        async with database.AsyncSessionLocal() as session:
            row = (await session.execute(select(ScenarioDB).where(ScenarioDB.id == bad_id))).scalar_one()
            row.input_payload = {"name": "Poisoned", "attendees": -5}
            await session.commit()

    asyncio.run(_poison())

    response = client.post("/api/scenarios/recalculate/all", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["updated_count"] == 1
    assert body["failed_count"] == 1
    assert body["failures"][0]["scenario_id"] == bad_id
    assert {s["scenario_id"] for s in body["scenarios"]} == {good_id, bad_id}


def test_cross_user_isolation(client: TestClient):
    headers_a = register_user(client, email="owner@example.com")
    headers_b = register_user(client, email="intruder@example.com")
    scenario_id = create_scenario(client, headers_a)["scenario_id"]

    assert client.get(f"/api/scenarios/{scenario_id}", headers=headers_b).status_code == 404
    assert client.put(
        f"/api/scenarios/{scenario_id}", json=SEEDED_SCENARIO_PAYLOAD, headers=headers_b
    ).status_code == 404
    assert client.post(f"/api/scenarios/{scenario_id}/clone?name=steal", headers=headers_b).status_code == 404
    assert client.get(f"/api/scenarios/{scenario_id}/suggestions", headers=headers_b).status_code == 404
    assert client.get("/api/scenarios", headers=headers_b).json() == []
