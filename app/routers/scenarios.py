from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.database import get_db, ScenarioDB, UserDB
from app.models.schemas import EventScenarioInput, ScenarioResult
from app.services.emissions_engine import calculate_scenario, get_reduction_suggestions
from app.routers.auth import get_current_user

router = APIRouter()


def _db_to_result(s: ScenarioDB) -> dict:
    return {
        "scenario_id": s.id,
        "name": s.name,
        "event_name": s.event_name,
        "attendees": s.attendees,
        "event_days": s.event_days,
        "emissions": {
            "travel_tco2e": s.travel_tco2e,
            "venue_energy_tco2e": s.venue_energy_tco2e,
            "accommodation_tco2e": s.accommodation_tco2e,
            "catering_tco2e": s.catering_tco2e,
            "materials_waste_tco2e": s.materials_waste_tco2e,
            "total_tco2e": s.total_tco2e,
            "per_attendee_tco2e": s.per_attendee_tco2e,
            "data_quality": s.data_quality,
        },
        "assumptions": s.assumptions or {},
        "created_at": s.created_at.isoformat() if s.created_at else "",
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

    db_obj = ScenarioDB(
        id=scenario_id,
        name=result.name,
        event_name=result.event_name,
        attendees=result.attendees,
        event_days=result.event_days,
        mode=payload.mode.value,
        travel_tco2e=result.emissions.travel_tco2e,
        venue_energy_tco2e=result.emissions.venue_energy_tco2e,
        accommodation_tco2e=result.emissions.accommodation_tco2e,
        catering_tco2e=result.emissions.catering_tco2e,
        materials_waste_tco2e=result.emissions.materials_waste_tco2e,
        total_tco2e=result.emissions.total_tco2e,
        per_attendee_tco2e=result.emissions.per_attendee_tco2e,
        data_quality=result.emissions.data_quality,
        assumptions=result.assumptions,
        input_payload=payload.model_dump(),
        created_at=datetime.utcnow(),
        user_id=current_user.id,
    )
    db.add(db_obj)
    await db.commit()

    return {**_db_to_result(db_obj), "scenario_id": scenario_id}


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
        attendees=orig.attendees,
        event_days=orig.event_days,
        mode=orig.mode,
        travel_tco2e=orig.travel_tco2e,
        venue_energy_tco2e=orig.venue_energy_tco2e,
        accommodation_tco2e=orig.accommodation_tco2e,
        catering_tco2e=orig.catering_tco2e,
        materials_waste_tco2e=orig.materials_waste_tco2e,
        total_tco2e=orig.total_tco2e,
        per_attendee_tco2e=orig.per_attendee_tco2e,
        data_quality=orig.data_quality,
        assumptions={**orig.assumptions, "cloned_from": scenario_id},
        input_payload=orig.input_payload,
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

    # Reconstruct minimal ScenarioResult for the suggestions engine
    from app.models.schemas import ScenarioResult, EmissionBreakdown
    sr = ScenarioResult(
        scenario_id=s.id,
        name=s.name,
        event_name=s.event_name,
        attendees=s.attendees,
        event_days=s.event_days,
        emissions=EmissionBreakdown(
            travel_tco2e=s.travel_tco2e,
            venue_energy_tco2e=s.venue_energy_tco2e,
            accommodation_tco2e=s.accommodation_tco2e,
            catering_tco2e=s.catering_tco2e,
            materials_waste_tco2e=s.materials_waste_tco2e,
            total_tco2e=s.total_tco2e,
            per_attendee_tco2e=s.per_attendee_tco2e,
            data_quality=s.data_quality,
        ),
    )
    return get_reduction_suggestions(sr, target_pct)


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
