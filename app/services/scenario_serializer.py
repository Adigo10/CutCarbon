"""Single source for ScenarioDB <-> dict/schema mapping.

Previously this ~18-field mapping was repeated in four places (scenario router
save/update/clone paths and the exports serializer) and drifted between them.
Both routers import from here; this module imports only models + the engine, so
there is no router-to-router import cycle.
"""

from typing import Any

from app.models.database import ScenarioDB
from app.models.schemas import (
    EmissionBreakdown,
    EventScenarioInput,
    ScenarioResult,
    ScopeBreakdown,
)
from app.services.emissions_engine import build_factors_snapshot, get_benchmark_comparison

# Columns that must never be copied when cloning a scenario row.
_CLONE_EXCLUDED = {"id", "user_id", "created_at", "updated_at"}


def serialize_scenario(s: ScenarioDB) -> dict[str, Any]:
    """ScenarioDB row -> the wire/report dict used by the API and all exports."""
    event_type = getattr(s, "event_type", "conference") or "conference"
    per_attendee_day = (
        round(s.per_attendee_tco2e / max(s.event_days or 1, 1), 4) if s.per_attendee_tco2e else 0
    )
    benchmark = get_benchmark_comparison(event_type, per_attendee_day, s.per_attendee_tco2e)
    return {
        "scenario_id": s.id,
        "name": s.name,
        "event_name": s.event_name,
        "location": getattr(s, "location", None) or (s.input_payload or {}).get("location") or "",
        "event_type": event_type,
        "attendees": s.attendees,
        "event_days": s.event_days,
        "mode": getattr(s, "mode", None) or "basic",
        "emissions": {
            "travel_tco2e": s.travel_tco2e,
            "venue_energy_tco2e": s.venue_energy_tco2e,
            "accommodation_tco2e": s.accommodation_tco2e,
            "catering_tco2e": s.catering_tco2e,
            "materials_waste_tco2e": s.materials_waste_tco2e,
            "equipment_tco2e": getattr(s, "equipment_tco2e", 0) or 0,
            "swag_tco2e": getattr(s, "swag_tco2e", 0) or 0,
            "digital_tco2e": getattr(s, "digital_tco2e", 0) or 0,
            "total_tco2e": s.total_tco2e,
            "per_attendee_tco2e": s.per_attendee_tco2e,
            "per_attendee_day_tco2e": per_attendee_day,
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


def result_to_column_values(result: ScenarioResult, payload: EventScenarioInput) -> dict[str, Any]:
    """ScenarioResult + validated input -> the ScenarioDB column values to persist."""
    e = result.emissions
    scopes = e.scopes
    return {
        "name": result.name,
        "event_name": result.event_name,
        "location": result.location or payload.location,
        "event_type": result.event_type,
        "attendees": result.attendees,
        "event_days": result.event_days,
        "mode": payload.mode.value,
        "travel_tco2e": e.travel_tco2e,
        "venue_energy_tco2e": e.venue_energy_tco2e,
        "accommodation_tco2e": e.accommodation_tco2e,
        "catering_tco2e": e.catering_tco2e,
        "materials_waste_tco2e": e.materials_waste_tco2e,
        "equipment_tco2e": e.equipment_tco2e,
        "swag_tco2e": e.swag_tco2e,
        "digital_tco2e": e.digital_tco2e,
        "total_tco2e": e.total_tco2e,
        "per_attendee_tco2e": e.per_attendee_tco2e,
        "data_quality": e.data_quality,
        "scope1_tco2e": scopes.scope1_tco2e if scopes else 0,
        "scope2_tco2e": scopes.scope2_tco2e if scopes else 0,
        "scope3_tco2e": scopes.scope3_tco2e if scopes else 0,
        "assumptions": result.assumptions,
        "input_payload": payload.model_dump(),
        "factors_snapshot": build_factors_snapshot(payload),
    }


def db_row_to_result(s: ScenarioDB) -> ScenarioResult:
    """Rehydrate a stored row into a ScenarioResult (for engine functions that
    operate on results, e.g. reduction suggestions)."""
    return ScenarioResult(
        scenario_id=s.id,
        name=s.name,
        event_name=s.event_name or "",
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
            digital_tco2e=getattr(s, "digital_tco2e", 0) or 0,
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


def copy_scenario_columns(orig: ScenarioDB) -> dict[str, Any]:
    """All persisted column values of a row except identity/timestamps (for clones)."""
    return {
        col.name: getattr(orig, col.name)
        for col in ScenarioDB.__table__.columns
        if col.name not in _CLONE_EXCLUDED
    }
