from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.database import get_db, ScenarioDB, UserDB
from app.models.schemas import EventScenarioInput, ScenarioResult, ScenarioExport
from app.services.emissions_engine import (
    calculate_scenario,
    get_reduction_suggestions,
    build_factors_snapshot,
    get_benchmark_comparison,
)
from app.routers.auth import get_current_user

router = APIRouter()


def _db_to_result(s: ScenarioDB) -> dict:
    event_type = getattr(s, "event_type", "conference") or "conference"
    per_attendee_day = round(s.per_attendee_tco2e / max(s.event_days or 1, 1), 4) if s.per_attendee_tco2e else 0
    benchmark = get_benchmark_comparison(event_type, per_attendee_day)
    return {
        "scenario_id": s.id,
        "name": s.name,
        "event_name": s.event_name,
        "event_type": event_type,
        "attendees": s.attendees,
        "event_days": s.event_days,
        "emissions": {
            "travel_tco2e": s.travel_tco2e,
            "venue_energy_tco2e": s.venue_energy_tco2e,
            "accommodation_tco2e": s.accommodation_tco2e,
            "catering_tco2e": s.catering_tco2e,
            "materials_waste_tco2e": s.materials_waste_tco2e,
            "equipment_tco2e": getattr(s, "equipment_tco2e", 0) or 0,
            "swag_tco2e": getattr(s, "swag_tco2e", 0) or 0,
            "total_tco2e": s.total_tco2e,
            "per_attendee_tco2e": s.per_attendee_tco2e,
            "per_attendee_day_tco2e": round(s.per_attendee_tco2e / max(s.event_days, 1), 4) if s.per_attendee_tco2e else 0,
            "data_quality": s.data_quality,
            "scopes": {
                "scope1_tco2e": getattr(s, "scope1_tco2e", 0) or 0,
                "scope2_tco2e": getattr(s, "scope2_tco2e", 0) or 0,
                "scope3_tco2e": getattr(s, "scope3_tco2e", 0) or 0,
            },
        },
        "assumptions": s.assumptions or {},
        "input_payload": s.input_payload or {},
        "factors_snapshot": getattr(s, "factors_snapshot", None) or {},
        "benchmark": benchmark.model_dump() if benchmark else None,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


def _save_result(scenario_id: str, result: ScenarioResult, payload: EventScenarioInput, user_id: int) -> ScenarioDB:
    """Build a ScenarioDB object from calculation result."""
    return ScenarioDB(
        id=scenario_id,
        name=result.name,
        event_name=result.event_name,
        event_type=result.event_type,
        attendees=result.attendees,
        event_days=result.event_days,
        mode=payload.mode.value,
        travel_tco2e=result.emissions.travel_tco2e,
        venue_energy_tco2e=result.emissions.venue_energy_tco2e,
        accommodation_tco2e=result.emissions.accommodation_tco2e,
        catering_tco2e=result.emissions.catering_tco2e,
        materials_waste_tco2e=result.emissions.materials_waste_tco2e,
        equipment_tco2e=result.emissions.equipment_tco2e,
        swag_tco2e=result.emissions.swag_tco2e,
        total_tco2e=result.emissions.total_tco2e,
        per_attendee_tco2e=result.emissions.per_attendee_tco2e,
        data_quality=result.emissions.data_quality,
        scope1_tco2e=result.emissions.scopes.scope1_tco2e if result.emissions.scopes else 0,
        scope2_tco2e=result.emissions.scopes.scope2_tco2e if result.emissions.scopes else 0,
        scope3_tco2e=result.emissions.scopes.scope3_tco2e if result.emissions.scopes else 0,
        assumptions=result.assumptions,
        input_payload=payload.model_dump(),
        factors_snapshot=build_factors_snapshot(payload),
        created_at=datetime.utcnow(),
        user_id=user_id,
    )


def _apply_result_to_existing(existing: ScenarioDB, result: ScenarioResult, payload: EventScenarioInput) -> None:
    """Apply a ScenarioResult onto an existing ScenarioDB row."""
    existing.name = result.name
    existing.event_name = result.event_name
    existing.event_type = result.event_type
    existing.attendees = result.attendees
    existing.event_days = result.event_days
    existing.mode = payload.mode.value
    existing.travel_tco2e = result.emissions.travel_tco2e
    existing.venue_energy_tco2e = result.emissions.venue_energy_tco2e
    existing.accommodation_tco2e = result.emissions.accommodation_tco2e
    existing.catering_tco2e = result.emissions.catering_tco2e
    existing.materials_waste_tco2e = result.emissions.materials_waste_tco2e
    existing.equipment_tco2e = result.emissions.equipment_tco2e
    existing.swag_tco2e = result.emissions.swag_tco2e
    existing.total_tco2e = result.emissions.total_tco2e
    existing.per_attendee_tco2e = result.emissions.per_attendee_tco2e
    existing.data_quality = result.emissions.data_quality
    existing.scope1_tco2e = result.emissions.scopes.scope1_tco2e if result.emissions.scopes else 0
    existing.scope2_tco2e = result.emissions.scopes.scope2_tco2e if result.emissions.scopes else 0
    existing.scope3_tco2e = result.emissions.scopes.scope3_tco2e if result.emissions.scopes else 0
    existing.assumptions = result.assumptions
    existing.input_payload = payload.model_dump()
    existing.factors_snapshot = build_factors_snapshot(payload)
    existing.updated_at = datetime.utcnow()


@router.post("/recalculate/all", response_model=dict)
async def recalculate_all_scenarios(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Recalculate every saved scenario for the current user using latest factors."""
    result_q = await db.execute(
        select(ScenarioDB)
        .where(ScenarioDB.user_id == current_user.id)
        .order_by(ScenarioDB.created_at.desc())
    )
    scenarios = result_q.scalars().all()

    all_rows: List[dict] = []
    failures: List[dict] = []

    for existing in scenarios:
        payload_dict = existing.input_payload or {}
        try:
            payload = EventScenarioInput.model_validate(payload_dict)
            result = calculate_scenario(payload)
            _apply_result_to_existing(existing, result, payload)
            all_rows.append(_db_to_result(existing))
        except Exception as exc:
            failures.append({
                "scenario_id": existing.id,
                "name": existing.name,
                "error": str(exc),
            })
            # Keep scenario in response even when recalculation fails.
            all_rows.append(_db_to_result(existing))

    await db.commit()

    return {
        "updated_count": len(scenarios) - len(failures),
        "failed_count": len(failures),
        "failures": failures,
        "scenarios": all_rows,
    }


@router.post("", response_model=dict)
async def create_scenario(
    payload: EventScenarioInput,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Calculate emissions for a scenario and save to DB."""
    result: ScenarioResult = calculate_scenario(payload)
    scenario_id = str(uuid.uuid4())[:8]
    db_obj = _save_result(scenario_id, result, payload, current_user.id)
    db.add(db_obj)
    await db.commit()
    return {**_db_to_result(db_obj), "scenario_id": scenario_id, "benchmark": result.benchmark.model_dump() if result.benchmark else None}


@router.put("/{scenario_id}", response_model=dict)
async def update_scenario(
    scenario_id: str,
    payload: EventScenarioInput,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Recalculate and update an existing scenario with new inputs."""
    result_q = await db.execute(
        select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    existing = result_q.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Scenario not found")

    result: ScenarioResult = calculate_scenario(payload)

    _apply_result_to_existing(existing, result, payload)

    await db.commit()
    return {**_db_to_result(existing), "benchmark": result.benchmark.model_dump() if result.benchmark else None}


@router.get("", response_model=List[dict])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """List all saved scenarios for the current user."""
    result = await db.execute(
        select(ScenarioDB)
        .where(ScenarioDB.user_id == current_user.id)
        .order_by(ScenarioDB.created_at.desc())
    )
    return [_db_to_result(s) for s in result.scalars().all()]


@router.get("/{scenario_id}", response_model=dict)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    result = await db.execute(
        select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _db_to_result(s)


@router.delete("/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    await db.execute(
        delete(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    await db.commit()
    return {"deleted": scenario_id}


@router.post("/{scenario_id}/clone")
async def clone_scenario(
    scenario_id: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Clone a scenario for what-if comparisons."""
    result = await db.execute(
        select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    orig = result.scalar_one_or_none()
    if not orig:
        raise HTTPException(status_code=404, detail="Scenario not found")

    new_id = str(uuid.uuid4())[:8]
    clone = ScenarioDB(
        id=new_id,
        name=name,
        event_name=orig.event_name,
        event_type=getattr(orig, "event_type", "conference") or "conference",
        attendees=orig.attendees,
        event_days=orig.event_days,
        mode=orig.mode,
        travel_tco2e=orig.travel_tco2e,
        venue_energy_tco2e=orig.venue_energy_tco2e,
        accommodation_tco2e=orig.accommodation_tco2e,
        catering_tco2e=orig.catering_tco2e,
        materials_waste_tco2e=orig.materials_waste_tco2e,
        equipment_tco2e=getattr(orig, "equipment_tco2e", 0) or 0,
        swag_tco2e=getattr(orig, "swag_tco2e", 0) or 0,
        total_tco2e=orig.total_tco2e,
        per_attendee_tco2e=orig.per_attendee_tco2e,
        data_quality=orig.data_quality,
        scope1_tco2e=getattr(orig, "scope1_tco2e", 0) or 0,
        scope2_tco2e=getattr(orig, "scope2_tco2e", 0) or 0,
        scope3_tco2e=getattr(orig, "scope3_tco2e", 0) or 0,
        assumptions={**(orig.assumptions or {}), "cloned_from": scenario_id},
        input_payload=orig.input_payload,
        factors_snapshot=orig.factors_snapshot or {},
        created_at=datetime.utcnow(),
        user_id=current_user.id,
    )
    db.add(clone)
    await db.commit()
    return _db_to_result(clone)


@router.get("/{scenario_id}/suggestions")
async def reduction_suggestions(
    scenario_id: str,
    target_pct: float = 30.0,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Get ranked reduction suggestions for a scenario."""
    result = await db.execute(
        select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.models.schemas import ScenarioResult, EmissionBreakdown, ScopeBreakdown
    sr = ScenarioResult(
        scenario_id=s.id,
        name=s.name,
        event_name=s.event_name,
        event_type=getattr(s, "event_type", "conference") or "conference",
        attendees=s.attendees,
        event_days=s.event_days,
        emissions=EmissionBreakdown(
            travel_tco2e=s.travel_tco2e,
            venue_energy_tco2e=s.venue_energy_tco2e,
            accommodation_tco2e=s.accommodation_tco2e,
            catering_tco2e=s.catering_tco2e,
            materials_waste_tco2e=s.materials_waste_tco2e,
            equipment_tco2e=getattr(s, "equipment_tco2e", 0) or 0,
            swag_tco2e=getattr(s, "swag_tco2e", 0) or 0,
            total_tco2e=s.total_tco2e,
            per_attendee_tco2e=s.per_attendee_tco2e,
            data_quality=s.data_quality,
            scopes=ScopeBreakdown(
                scope1_tco2e=getattr(s, "scope1_tco2e", 0) or 0,
                scope2_tco2e=getattr(s, "scope2_tco2e", 0) or 0,
                scope3_tco2e=getattr(s, "scope3_tco2e", 0) or 0,
            ),
        ),
    )
    return get_reduction_suggestions(sr, target_pct)


@router.get("/{scenario_id}/export")
async def export_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Export scenario data as JSON for reporting."""
    result = await db.execute(
        select(ScenarioDB).where(ScenarioDB.id == scenario_id, ScenarioDB.user_id == current_user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")

    data = _db_to_result(s)
    export = {
        "report_title": f"Carbon Footprint Report - {s.event_name}",
        "methodology": "GHG Protocol Corporate Standard, ISO 14064-1",
        "scenario": data,
        "scope_breakdown": data["emissions"]["scopes"],
        "total_emissions_tco2e": s.total_tco2e,
        "per_attendee_tco2e": s.per_attendee_tco2e,
        "data_quality": s.data_quality,
        "assumptions": s.assumptions or {},
        "input_data": s.input_payload or {},
        "exported_at": datetime.utcnow().isoformat(),
        "disclaimer": "Calculations based on industry-standard emission factors. Actual emissions may vary. For verified reporting, engage an accredited third-party verifier.",
    }
    return JSONResponse(
        content=export,
        headers={"Content-Disposition": f"attachment; filename=cutcarbon_{scenario_id}.json"},
    )


@router.get("/compare/all")
async def compare_scenarios(
    ids: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Compare multiple scenarios. Pass ?ids=id1,id2,id3 or leave empty for all."""
    if ids:
        id_list = ids.split(",")
        result = await db.execute(
            select(ScenarioDB).where(ScenarioDB.id.in_(id_list), ScenarioDB.user_id == current_user.id)
        )
    else:
        result = await db.execute(
            select(ScenarioDB)
            .where(ScenarioDB.user_id == current_user.id)
            .order_by(ScenarioDB.created_at.desc())
            .limit(10)
        )
    scenarios = result.scalars().all()
    return [_db_to_result(s) for s in scenarios]
