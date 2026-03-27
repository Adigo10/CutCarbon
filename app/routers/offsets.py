"""Carbon offset portfolio management — browse projects, track purchases, retire credits."""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import get_db, OffsetPurchaseDB, ScenarioDB, UserDB
from app.models.schemas import (
    OffsetPurchaseCreate, OffsetPurchaseOut, OffsetPortfolioSummary, OffsetRecommendation
)
from app.routers.auth import get_current_user

router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"

with open(_DATA_DIR / "carbon_offsets.json") as f:
    OFFSET_DATA = json.load(f)


@router.get("/projects")
async def list_offset_projects():
    """Browse available carbon offset project types with pricing and co-benefits."""
    return OFFSET_DATA["project_types"]


@router.get("/registries")
async def list_registries():
    """List accredited carbon credit registries."""
    return OFFSET_DATA["registries"]


@router.get("/market")
async def market_overview():
    """Current carbon market data and pricing trends."""
    return OFFSET_DATA["market_data"]


@router.get("/guidance")
async def retirement_guidance():
    """Best practices for claiming and retiring carbon credits."""
    return OFFSET_DATA["retirement_guidance"]


@router.post("", response_model=OffsetPurchaseOut)
async def create_purchase(
    purchase: OffsetPurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Record a carbon offset purchase."""
    total_cost = purchase.quantity_tco2e * purchase.price_per_tco2e_usd
    db_obj = OffsetPurchaseDB(
        user_id=current_user.id,
        scenario_id=purchase.scenario_id,
        project_type=purchase.project_type.value,
        registry=purchase.registry,
        quantity_tco2e=purchase.quantity_tco2e,
        price_per_tco2e_usd=purchase.price_per_tco2e_usd,
        total_cost_usd=total_cost,
        vintage_year=purchase.vintage_year,
        serial_number=purchase.serial_number,
        status="purchased",
        notes=purchase.notes,
        created_at=datetime.utcnow(),
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return _to_out(db_obj)


@router.get("", response_model=List[OffsetPurchaseOut])
async def list_purchases(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """List all offset purchases for the current user."""
    result = await db.execute(
        select(OffsetPurchaseDB)
        .where(OffsetPurchaseDB.user_id == current_user.id)
        .order_by(OffsetPurchaseDB.created_at.desc())
    )
    return [_to_out(p) for p in result.scalars().all()]


@router.post("/{purchase_id}/retire")
async def retire_credit(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Retire a purchased credit (mark as permanently used)."""
    result = await db.execute(
        select(OffsetPurchaseDB).where(
            OffsetPurchaseDB.id == purchase_id,
            OffsetPurchaseDB.user_id == current_user.id
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if p.status == "retired":
        raise HTTPException(status_code=400, detail="Already retired")

    p.status = "retired"
    p.retired_at = datetime.utcnow()
    await db.commit()
    return _to_out(p)


@router.delete("/{purchase_id}")
async def cancel_purchase(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Cancel a purchase (only if not yet retired)."""
    result = await db.execute(
        select(OffsetPurchaseDB).where(
            OffsetPurchaseDB.id == purchase_id,
            OffsetPurchaseDB.user_id == current_user.id
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if p.status == "retired":
        raise HTTPException(status_code=400, detail="Cannot cancel retired credits")

    p.status = "cancelled"
    await db.commit()
    return {"cancelled": purchase_id}


@router.get("/portfolio", response_model=OffsetPortfolioSummary)
async def portfolio_summary(
    scenario_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Aggregate portfolio summary across all purchases."""
    result = await db.execute(
        select(OffsetPurchaseDB).where(
            OffsetPurchaseDB.user_id == current_user.id,
            OffsetPurchaseDB.status != "cancelled",
        )
    )
    purchases = result.scalars().all()

    total_purchased = sum(p.quantity_tco2e for p in purchases)
    total_retired = sum(p.quantity_tco2e for p in purchases if p.status == "retired")
    total_cost = sum(p.total_cost_usd for p in purchases)

    by_type = {}
    by_registry = {}
    for p in purchases:
        by_type[p.project_type] = by_type.get(p.project_type, 0) + p.quantity_tco2e
        by_registry[p.registry] = by_registry.get(p.registry, 0) + p.quantity_tco2e

    coverage_pct = None
    if scenario_id:
        sr = await db.execute(
            select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
        )
        scenario = sr.scalar_one_or_none()
        if scenario and scenario.total_tco2e > 0:
            coverage_pct = round(total_retired / scenario.total_tco2e * 100, 1)

    return OffsetPortfolioSummary(
        total_purchased_tco2e=round(total_purchased, 3),
        total_retired_tco2e=round(total_retired, 3),
        total_cost_usd=round(total_cost, 2),
        by_project_type=by_type,
        by_registry=by_registry,
        coverage_pct=coverage_pct,
    )


@router.get("/recommend/{scenario_id}", response_model=List[OffsetRecommendation])
async def recommend_offsets(
    scenario_id: str,
    budget_usd: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Recommend offset portfolio mix for a scenario's residual emissions."""
    result = await db.execute(
        select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    residual = scenario.total_tco2e
    projects = OFFSET_DATA["project_types"]

    recommendations = []
    # Recommended portfolio: 50% avoidance, 30% nature-based, 20% removal
    portfolio_mix = [
        ("renewable_energy", 0.30),
        ("cookstove", 0.20),
        ("forestry_afforestation", 0.15),
        ("blue_carbon", 0.15),
        ("biochar", 0.10),
        ("direct_air_capture", 0.10),
    ]

    for proj_key, pct in portfolio_mix:
        proj = projects.get(proj_key)
        if not proj:
            continue
        qty = round(residual * pct, 3)
        price = proj["avg_price_usd"]
        cost = round(qty * price, 2)

        if budget_usd and cost > budget_usd * pct * 1.5:
            # Adjust quantity to fit budget
            qty = round(budget_usd * pct / price, 3)
            cost = round(qty * price, 2)

        recommendations.append(OffsetRecommendation(
            project_type=proj_key,
            label=proj["label"],
            description=proj["description"],
            avg_price_usd=price,
            recommended_qty_tco2e=qty,
            estimated_cost_usd=cost,
            permanence=proj["permanence"],
            co_benefits=proj["co_benefits"],
            sdgs=proj["sdgs"],
        ))

    return recommendations


def _to_out(p: OffsetPurchaseDB) -> OffsetPurchaseOut:
    return OffsetPurchaseOut(
        id=p.id,
        scenario_id=p.scenario_id,
        project_type=p.project_type,
        registry=p.registry,
        quantity_tco2e=p.quantity_tco2e,
        price_per_tco2e_usd=p.price_per_tco2e_usd,
        total_cost_usd=p.total_cost_usd,
        vintage_year=p.vintage_year,
        serial_number=p.serial_number,
        status=p.status,
        retired_at=p.retired_at.isoformat() if p.retired_at else None,
        notes=p.notes,
        created_at=p.created_at.isoformat() if p.created_at else "",
    )
