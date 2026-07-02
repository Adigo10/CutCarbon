from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.database import get_db, ScenarioDB, FinancialReportDB, UserDB
from app.models.schemas import ComplianceRequest, FinancialRequest, FinancialResult, ComplianceReport
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


@router.post("/compliance", response_model=ComplianceReport)
async def check_compliance(
    req: ComplianceRequest,
    current_user: UserDB = Depends(get_current_user),
):
    """Check compliance across GHG Protocol, ISO 20121, SBTi and regional standards."""
    return get_compliance_report(
        req.total_tco2e, req.has_scope3, req.has_ghg_report,
        req.region, req.event_days, req.attendees,
    )


