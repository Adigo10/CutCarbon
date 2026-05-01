import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.models.database as database
from app.config import settings
from app.main import app
from app.models.database import UserDB
from app.models.schemas import EventScenarioInput, OffsetProjectType, OffsetPurchaseCreate, TravelMode, TravelSegment, VenueEnergy
from app.routers.exports import build_scenario_report_payload
from app.services.emissions_engine import calculate_scenario


@pytest.fixture()
def client(tmp_path):
    db_path = (tmp_path / "test_reporting.db").resolve()
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


def register_user(client: TestClient, email: str = "reporter@example.com") -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "super-secret"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_seeded_scenario(client: TestClient, headers: dict[str, str]) -> str:
    scenario_payload = {
        "name": "APAC Summit Baseline",
        "event_name": "APAC Summit 2026",
        "location": "Singapore",
        "event_type": "conference",
        "attendees": 120,
        "event_days": 2,
        "mode": "basic",
        "travel_segments": [
            {
                "mode": "long_haul_flight",
                "travel_class": "economy",
                "attendees": 40,
                "distance_km": 6200,
                "label": "Long-haul delegates",
            }
        ],
        "venue_energy": {
            "grid_region": "singapore",
            "kwh_consumed": 2500,
            "renewable_pct": 10,
            "event_days": 2,
        },
        "accommodation": {
            "accommodation_type": "standard_hotel",
            "room_nights": 90,
            "attendees_sharing": 1.5,
        },
        "catering": {
            "catering_type": "vegetarian_meal",
            "meals": 240,
            "include_beverages": True,
            "include_alcohol": False,
            "coffee_tea_cups": 120,
        },
    }
    response = client.post("/api/scenarios", json=scenario_payload, headers=headers)
    assert response.status_code == 200
    scenario_id = response.json()["scenario_id"]

    purchase_response = client.post(
        "/api/offsets",
        json={
            "scenario_id": scenario_id,
            "project_type": "renewable_energy",
            "registry": "gold_standard",
            "quantity_tco2e": 2.5,
            "price_per_tco2e_usd": 11.0,
            "vintage_year": 2025,
            "notes": "Seeded test purchase",
        },
        headers=headers,
    )
    assert purchase_response.status_code == 200
    purchase_id = purchase_response.json()["id"]

    retire_response = client.post(f"/api/offsets/{purchase_id}/retire", headers=headers)
    assert retire_response.status_code == 200

    return scenario_id


def load_user(email: str) -> UserDB:
    async def _runner():
        async with database.AsyncSessionLocal() as session:
            result = await session.execute(select(UserDB).where(UserDB.email == email))
            return result.scalar_one()

    return asyncio.run(_runner())


def build_payload_for_test(scenario_id: str, user: UserDB):
    async def _runner():
        async with database.AsyncSessionLocal() as session:
            return await build_scenario_report_payload(
                scenario_id=scenario_id,
                db=session,
                current_user=user,
                region="eu",
                has_scope3=False,
                has_ghg_report=False,
            )

    return asyncio.run(_runner())


def test_shared_report_payload_includes_offsets_and_compliance_overrides(client: TestClient):
    headers = register_user(client)
    scenario_id = create_seeded_scenario(client, headers)
    user = load_user("reporter@example.com")

    report = build_payload_for_test(scenario_id, user)

    assert report.scenario["scenario_id"] == scenario_id
    assert report.offset_portfolio.total_retired_tco2e == pytest.approx(2.5)
    assert report.offset_portfolio.coverage_pct is not None
    assert report.compliance_overrides.region == "eu"
    assert report.compliance_overrides.has_scope3 is False
    assert "EU CSRD" in report.compliance.mandatory_frameworks
    assert report.categories


@pytest.mark.parametrize("fmt", ["json", "csv", "xlsx", "pdf"])
def test_single_scenario_report_exports_require_auth(client: TestClient, fmt: str):
    response = client.get(f"/api/exports/scenarios/missing.{fmt}")
    assert response.status_code == 401


@pytest.mark.parametrize("fmt", ["json", "csv", "xlsx", "pdf"])
def test_single_scenario_report_exports_return_expected_files(client: TestClient, fmt: str):
    headers = register_user(client, email=f"{fmt}@example.com")
    scenario_id = create_seeded_scenario(client, headers)

    response = client.get(
        f"/api/exports/scenarios/{scenario_id}.{fmt}"
        "?region=eu&has_scope3=false&has_ghg_report=false",
        headers=headers,
    )

    assert response.status_code == 200
    assert f".{fmt}" in response.headers["content-disposition"]

    if fmt == "json":
        payload = response.json()
        assert payload["compliance_overrides"]["region"] == "eu"
        assert payload["compliance_overrides"]["has_scope3"] is False
        assert "EU CSRD" in payload["compliance"]["mandatory_frameworks"]
    elif fmt == "csv":
        content = response.content.decode("utf-8")
        assert "section,key,label,value,unit" in content
        assert "metadata,region,Compliance Region,eu," in content
        assert "compliance,overall_score_pct,Overall Score" in content
    elif fmt == "xlsx":
        workbook = load_workbook(io.BytesIO(response.content))
        assert "Report Summary" in workbook.sheetnames
        assert "Compliance" in workbook.sheetnames
    else:
        assert response.content.startswith(b"%PDF")


def test_legacy_scenario_export_alias_returns_shared_payload(client: TestClient):
    headers = register_user(client, email="legacy@example.com")
    scenario_id = create_seeded_scenario(client, headers)

    response = client.get(
        f"/api/scenarios/{scenario_id}/export?region=eu&has_scope3=false&has_ghg_report=false",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["scenario_id"] == scenario_id
    assert payload["compliance_overrides"]["region"] == "eu"
    assert payload["offset_portfolio"]["total_retired_tco2e"] == pytest.approx(2.5)


def test_global_exports_still_work(client: TestClient):
    headers = register_user(client, email="global@example.com")

    factor_json = client.get("/api/exports/emission-factors.json")
    assert factor_json.status_code == 200
    assert "travel" in factor_json.json()

    factor_xlsx = client.get("/api/exports/emission-factors.xlsx")
    assert factor_xlsx.status_code == 200
    assert ".xlsx" in factor_xlsx.headers["content-disposition"]

    agent_xlsx = client.get("/api/exports/agent-runs.xlsx", headers=headers)
    assert agent_xlsx.status_code == 200
    assert ".xlsx" in agent_xlsx.headers["content-disposition"]


def test_invalid_emissions_inputs_are_rejected():
    with pytest.raises(ValidationError):
        EventScenarioInput(
            name="Invalid Travel",
            attendees=100,
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    attendees=-50,
                    distance_km=2000,
                )
            ],
        )

    with pytest.raises(ValidationError):
        EventScenarioInput(
            name="Invalid Renewable",
            attendees=100,
            venue_energy=VenueEnergy(kwh_consumed=1000, renewable_pct=150),
        )

    with pytest.raises(ValidationError):
        EventScenarioInput(
            name="Overallocated Travel",
            attendees=100,
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    attendees=101,
                    distance_km=2000,
                )
            ],
        )

    with pytest.raises(ValidationError):
        OffsetPurchaseCreate(
            project_type=OffsetProjectType.RENEWABLE_ENERGY,
            quantity_tco2e=-5,
            price_per_tco2e_usd=10,
        )


def test_zero_kwh_is_treated_as_actual_data():
    scenario = EventScenarioInput(
        name="Zero kWh",
        attendees=10,
        venue_energy=VenueEnergy(kwh_consumed=0, venue_area_m2=100),
    )

    result = calculate_scenario(scenario)

    assert result.emissions.venue_energy_tco2e == 0
    assert result.assumptions["venue"] == "Actual kWh: 0"


def test_offset_purchase_requires_owned_scenario(client: TestClient):
    headers = register_user(client, email="offset-owner@example.com")

    response = client.post(
        "/api/offsets",
        json={
            "scenario_id": "missing-scenario",
            "project_type": "renewable_energy",
            "registry": "gold_standard",
            "quantity_tco2e": 1,
            "price_per_tco2e_usd": 10,
            "vintage_year": 2025,
        },
        headers=headers,
    )

    assert response.status_code == 404
