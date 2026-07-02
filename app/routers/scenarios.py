from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import datetime
import uuid

from app.models.database import get_db, ScenarioDB, UserDB
from app.models.schemas import (
    EventScenarioInput,
    RecalculateAllResponse,
    ScenarioDetail,
    ScenarioResult,
)
from app.services.emissions_engine import calculate_scenario, get_reduction_suggestions
from app.services.scenario_serializer import (
    copy_scenario_columns,
    db_row_to_result,
    result_to_column_values,
    serialize_scenario,
)
from app.routers.auth import get_current_user
from app.utils.time import utcnow

router = APIRouter()


def _save_result(scenario_id: str, result: ScenarioResult, payload: EventScenarioInput, user_id: int) -> ScenarioDB:
    """Build a ScenarioDB object from a calculation result."""
    return ScenarioDB(
        id=scenario_id,
        user_id=user_id,
        created_at=utcnow(),
        **result_to_column_values(result, payload),
    )


def _apply_result_to_existing(existing: ScenarioDB, result: ScenarioResult, payload: EventScenarioInput) -> None:
    """Apply a ScenarioResult onto an existing ScenarioDB row."""
    for field, value in result_to_column_values(result, payload).items():
        setattr(existing, field, value)
    existing.updated_at = utcnow()


@router.post("/recalculate/all", response_model=RecalculateAllResponse)
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
            # Validate + calculate fully before touching the row, and isolate the
            # mutation in a savepoint so a failure rolls back this row only — never
            # commits a half-updated scenario alongside the successes.
            payload = EventScenarioInput.model_validate(payload_dict)
            result = calculate_scenario(payload)
            async with db.begin_nested():
                _apply_result_to_existing(existing, result, payload)
            all_rows.append(serialize_scenario(existing))
        except Exception as exc:
            failures.append({
                "scenario_id": existing.id,
                "name": existing.name,
                "error": str(exc),
            })
            # Reload the un-mutated row so the response reflects its true (unchanged) state.
            await db.refresh(existing)
            all_rows.append(serialize_scenario(existing))

    await db.commit()

    return {
        "updated_count": len(scenarios) - len(failures),
        "failed_count": len(failures),
        "failures": failures,
        "scenarios": all_rows,
    }


@router.post("", response_model=ScenarioDetail)
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
    return serialize_scenario(db_obj)


@router.put("/{scenario_id}", response_model=ScenarioDetail)
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
    return serialize_scenario(existing)


@router.get("", response_model=List[ScenarioDetail])
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
    return [serialize_scenario(s) for s in result.scalars().all()]


@router.get("/{scenario_id}", response_model=ScenarioDetail)
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
    return serialize_scenario(s)


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


@router.post("/{scenario_id}/clone", response_model=ScenarioDetail)
async def clone_scenario(
    scenario_id: str,
    name: str = Query(min_length=1, max_length=200),
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

    clone = ScenarioDB(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        created_at=utcnow(),
        **{
            **copy_scenario_columns(orig),
            "name": name,
            "assumptions": {**(orig.assumptions or {}), "cloned_from": scenario_id},
        },
    )
    db.add(clone)
    await db.commit()
    return serialize_scenario(clone)


@router.get("/{scenario_id}/suggestions")
async def reduction_suggestions(
    scenario_id: str,
    target_pct: float = Query(30.0, ge=0, le=100),
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

    sr = db_row_to_result(s)
    catering_type = ((s.input_payload or {}).get("catering") or {}).get("catering_type")
    equipment_input = (s.input_payload or {}).get("equipment")
    return get_reduction_suggestions(sr, target_pct, catering_type, equipment_input)


