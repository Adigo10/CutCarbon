"""Carbon offset portfolio management — browse projects, track purchases, retire credits."""
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import get_db, OffsetPurchaseDB, ScenarioDB, UserDB
from app.models.schemas import (
    OffsetPurchaseCreate, OffsetPurchaseOut, OffsetPortfolioSummary, OffsetRecommendation
)
from app.routers.auth import get_current_user
from app.services.claims import portfolio_claim_statement, sanitize_claim_language
from app.services.data_files import CARBON_OFFSETS as OFFSET_DATA
from app.services.offset_integrity import (
    additionality_risk_warning,
    claim_eligible,
    residual_basis,
    sum_by_registry,
)
from app.utils.time import utcnow

router = APIRouter()


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


@router.post("", response_model=OffsetPurchaseOut)
async def create_purchase(
    purchase: OffsetPurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Record a carbon offset purchase."""
    scenario = None
    if purchase.scenario_id:
        scenario = await db.scalar(
            select(ScenarioDB).where(
                ScenarioDB.id == purchase.scenario_id,
                ScenarioDB.user_id == current_user.id,
            )
        )
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

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
        # Free text saved here is quoted back in the portfolio UI, so it goes
        # through the green-claims linter like any other narrative.
        notes=sanitize_claim_language(purchase.notes)[0] if purchase.notes else None,
        created_at=utcnow(),
        ccp_approved=purchase.ccp_approved,
        article6_adjustment=purchase.article6_adjustment,
        methodology=purchase.methodology,
        retirement_serial=purchase.retirement_serial,
        retirement_date=purchase.retirement_date,
        country=purchase.country,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # The owning scenario is already loaded above — no second round trip needed.
    return _to_out(db_obj, scenario.created_at.year if scenario and scenario.created_at else None)


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
    purchases = result.scalars().all()
    event_years = await _event_years(db, purchases)
    return [_to_out(p, event_years.get(p.scenario_id)) for p in purchases]


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
    p.retired_at = utcnow()
    await db.commit()
    return _to_out(p, (await _event_years(db, [p])).get(p.scenario_id))


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

    # by_registry above is a breakdown of everything *held*; the claim statement may
    # only name the registries whose credits were actually retired (see
    # app/services/claims.py — a held Gold Standard credit must not be described as
    # compensating alongside a retired Verra one).
    retired = [p for p in purchases if p.status == "retired"]
    retired_by_registry = sum_by_registry(retired)

    coverage_pct = None
    claim_statement = ""
    if scenario_id:
        sr = await db.execute(
            select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
        )
        scenario = sr.scalar_one_or_none()
        if scenario and scenario.total_tco2e > 0:
            coverage_pct = round(total_retired / scenario.total_tco2e * 100, 1)
            claim_statement = portfolio_claim_statement(
                scenario.total_tco2e,
                total_retired,
                retired_by_registry,
                credits_claim_eligible=all(claim_eligible(p) for p in retired),
            )

    return OffsetPortfolioSummary(
        total_purchased_tco2e=round(total_purchased, 3),
        total_retired_tco2e=round(total_retired, 3),
        total_cost_usd=round(total_cost, 2),
        by_project_type=by_type,
        by_registry=by_registry,
        coverage_pct=coverage_pct,
        claim_statement=claim_statement,
    )


@router.get("/recommend/{scenario_id}", response_model=List[OffsetRecommendation])
async def recommend_offsets(
    scenario_id: str,
    budget_usd: Optional[float] = None,
    reduction_pct: float = Query(
        default=0.0,
        ge=0,
        le=100,
        description="Committed reduction target (%). The mix is sized against the "
                    "residual left after it, since offsetting applies to residual "
                    "emissions only (ISO 14068-1).",
    ),
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

    # Without a stated reduction the mix is sized against the gross total — reported
    # as basis "gross" so it is never presented as a residual it is not.
    residual, basis = residual_basis(scenario.total_tco2e, reduction_pct)
    projects = OFFSET_DATA["project_types"]

    # Recommended portfolio: 50% avoidance, 30% nature-based, 20% removal
    portfolio_mix = [
        ("renewable_energy", 0.30),
        ("cookstove", 0.20),
        ("forestry_afforestation", 0.15),
        ("blue_carbon", 0.15),
        ("biochar", 0.10),
        ("direct_air_capture", 0.10),
    ]

    # First pass: unconstrained quantities/costs sized to fully cover the residual.
    raw = []
    total_cost_unconstrained = 0.0
    for proj_key, pct in portfolio_mix:
        proj = projects.get(proj_key)
        if not proj:
            continue
        qty = residual * pct
        price = proj["avg_price_usd"]
        raw.append((proj_key, proj, qty, price))
        total_cost_unconstrained += qty * price

    # Scale the whole portfolio down to fit the budget (if any), preserving the mix —
    # so total spend converges to min(budget, full-coverage cost) instead of the old
    # incoherent per-line 1.5x trigger that never summed to the stated budget.
    scale = 1.0
    if budget_usd and total_cost_unconstrained > budget_usd and total_cost_unconstrained > 0:
        scale = budget_usd / total_cost_unconstrained

    recommendations = []
    residual_reported = round(residual, 3)
    for proj_key, proj, qty, price in raw:
        scaled_qty = round(qty * scale, 3)
        risk = proj.get("additionality_risk", "")
        recommendations.append(OffsetRecommendation(
            project_type=proj_key,
            label=proj["label"],
            # Catalog copy is refreshed from external sources — lint it before it
            # is presented as a recommendation.
            description=sanitize_claim_language(proj["description"])[0],
            avg_price_usd=price,
            recommended_qty_tco2e=scaled_qty,
            estimated_cost_usd=round(scaled_qty * price, 2),
            permanence=proj["permanence"],
            additionality_risk=risk,
            risk_warning=additionality_risk_warning(risk),
            co_benefits=proj["co_benefits"],
            sdgs=proj["sdgs"],
            basis=basis,
            residual_tco2e=residual_reported,
        ))

    return recommendations


async def _event_years(
    db: AsyncSession, purchases: Sequence[OffsetPurchaseDB]
) -> Dict[str, int]:
    """Event year per linked scenario id, for the vintage-staleness check.

    A scenario carries no event date of its own, so the year it was created stands
    in for the event year — the comparison only needs to catch a vintage from
    *before* the event was being planned.
    """
    scenario_ids = {p.scenario_id for p in purchases if p.scenario_id}
    if not scenario_ids:
        return {}
    rows = await db.execute(
        select(ScenarioDB.id, ScenarioDB.created_at).where(ScenarioDB.id.in_(scenario_ids))
    )
    return {sid: created.year for sid, created in rows.all() if created}


def _to_out(p: OffsetPurchaseDB, event_year: Optional[int] = None) -> OffsetPurchaseOut:
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
        ccp_approved=p.ccp_approved,
        article6_adjustment=p.article6_adjustment,
        methodology=p.methodology,
        retirement_serial=p.retirement_serial,
        retirement_date=p.retirement_date.isoformat() if p.retirement_date else None,
        country=p.country,
        claim_eligible=claim_eligible(p),
        vintage_stale=bool(event_year and p.vintage_year and p.vintage_year < event_year),
    )
