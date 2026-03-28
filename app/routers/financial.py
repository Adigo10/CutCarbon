from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.database import get_db, ScenarioDB, FinancialReportDB, UserDB
from app.models.schemas import FinancialRequest, FinancialResult, ComplianceReport
from app.services.financial_engine import generate_financial_report, get_compliance_report
from app.routers.auth import get_current_user

router = APIRouter()


@router.post("/savings", response_model=FinancialResult)
async def calculate_savings(
    req: FinancialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Calculate financial savings from emission reductions."""
    if req.scenario_id:
        scenario = await db.scalar(
            select(ScenarioDB).where(
                ScenarioDB.id == req.scenario_id,
                ScenarioDB.user_id == current_user.id,
            )
        )
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

    result = generate_financial_report(req)

    # Persist report
    db.add(FinancialReportDB(
        scenario_id=req.scenario_id,
        region=req.region,
        baseline_tco2e=req.baseline_tco2e,
        reduced_tco2e=req.reduced_tco2e,
        total_savings_usd=result.total_financial_savings_usd,
        report_json=result.model_dump(),
        created_at=datetime.utcnow(),
        user_id=current_user.id,
    ))
    await db.commit()
    return result


@router.get("/savings/scenario/{scenario_id}")
async def savings_for_scenario(
    scenario_id: str,
    region: str = "singapore",
    reduction_pct: float = 30.0,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Auto-calculate financial savings for an existing scenario."""
    res = await db.execute(
        select(ScenarioDB).where(
            ScenarioDB.id == scenario_id,
            ScenarioDB.user_id == current_user.id,
        )
    )
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")

    reduced_tco2e = s.total_tco2e * (1 - reduction_pct / 100)
    req = FinancialRequest(
        scenario_id=s.id,
        baseline_tco2e=s.total_tco2e,
        reduced_tco2e=reduced_tco2e,
        region=region,
        energy_kwh_saved=s.venue_energy_tco2e * 1000 / 0.4 * (reduction_pct / 100),
        meal_switches=int(s.attendees * s.event_days * 2 * (reduction_pct / 100)),
        attendees=s.attendees,
        actions_taken=["renewable_energy", "vegetarian_menu", "digital_materials"],
    )
    return generate_financial_report(req)


@router.post("/compliance", response_model=ComplianceReport)
async def check_compliance(
    total_tco2e: float,
    has_scope3: bool = True,
    has_ghg_report: bool = False,
    region: str = "singapore",
    event_days: int = 1,
    attendees: int = 100,
):
    """Check compliance across GHG Protocol, ISO 20121, SBTi and regional standards."""
    return get_compliance_report(total_tco2e, has_scope3, has_ghg_report, region, event_days, attendees)


@router.get("/compliance/scenario/{scenario_id}")
async def compliance_for_scenario(
    scenario_id: str,
    region: str = "singapore",
    has_ghg_report: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Compliance report for an existing scenario."""
    res = await db.execute(
        select(ScenarioDB).where(
            ScenarioDB.id == scenario_id,
            ScenarioDB.user_id == current_user.id,
        )
    )
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return get_compliance_report(
        total_tco2e=s.total_tco2e,
        has_scope3=True,
        has_ghg_report=has_ghg_report,
        region=region,
        event_days=s.event_days,
        attendees=s.attendees,
    )


@router.get("/tax-rates")
async def get_tax_rates():
    """Return current carbon tax rates by region."""
    import json
    from pathlib import Path
    data_path = Path(__file__).parent.parent / "data" / "tax_incentives.json"
    with open(data_path) as f:
        data = json.load(f)
    return data["carbon_tax_rates"]


@router.get("/incentives/{region}")
async def get_incentives(region: str):
    """Return available green incentives for a region."""
    import json
    from pathlib import Path
    data_path = Path(__file__).parent.parent / "data" / "tax_incentives.json"
    with open(data_path) as f:
        data = json.load(f)
    region_map = {
        "singapore": "singapore",
        "eu": "european_union",
        "uk": "united_kingdom",
        "australia": "australia",
        "usa": "usa",
    }
    mapped = region_map.get(region.lower(), region.lower())
    incentives = data["green_incentives"].get(mapped, [])
    return {"region": region, "incentives": incentives}
