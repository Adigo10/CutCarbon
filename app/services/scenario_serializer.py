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

# -- Data-quality tiers --------------------------------------------------------
# Canonical vocabulary, coarsest first. "primary" is an *evidence* tier: it is
# awarded only when supporting documents are attached, which the deterministic
# engine cannot observe, so the engine never emits it (see calculate_scenario).
DATA_QUALITY_TIERS = ("modelled", "partly_primary", "primary")

# Rows written before the rename still carry the retired words. Map them forward
# on every read path so the API and the exports never emit the old vocabulary.
# The old "verified" was awarded for filling in every advanced-mode form — a
# completeness signal with no evidence behind it — so it maps down to
# "partly_primary", never up to the evidence tier.
_LEGACY_DATA_QUALITY = {
    "estimated": "modelled",
    "partial": "partly_primary",
    "verified": "partly_primary",
}

# Client-facing rendering (exports, UI). Values, not claims: the tier number
# names the strength of the underlying data, not an assurance level.
_DATA_QUALITY_LABELS = {
    "modelled": "Tier 3 — modelled",
    "partly_primary": "Tier 2 — partly primary",
    "primary": "Tier 1 — primary (evidenced)",
}


def normalize_data_quality(value: Any) -> str:
    """Any stored/legacy data-quality value -> the canonical tier.

    Unknown or missing values fall back to the most conservative tier, so a bad
    row can never overstate how well evidenced a footprint is.
    """
    if value in DATA_QUALITY_TIERS:
        return value
    return _LEGACY_DATA_QUALITY.get(value, "modelled")


def data_quality_label(value: Any) -> str:
    """Canonical or legacy tier -> the label rendered in reports and the UI."""
    return _DATA_QUALITY_LABELS[normalize_data_quality(value)]


# -- Primary-data coverage -----------------------------------------------------
# The per-category flags the engine writes into assumptions use their own keys;
# map each onto the emissions field that carries its tonnage.
_COVERAGE_CATEGORY_FIELDS = {
    "travel": "travel_tco2e",
    "venue_energy": "venue_energy_tco2e",
    "accommodation": "accommodation_tco2e",
    "catering": "catering_tco2e",
    "waste": "materials_waste_tco2e",
    "equipment": "equipment_tco2e",
    "swag": "swag_tco2e",
    "digital": "digital_tco2e",
}


def primary_data_coverage_pct(
    emissions: dict[str, Any], assumptions: dict[str, Any] | None
) -> float | None:
    """Share of the footprint (%) that came from measured, category-level inputs.

    Weighted by tCO2e, not by category count, so a measured category that happens
    to be tiny cannot dress up a proxy-dominated footprint. Only the "actual" flag
    earns credit: "partial" means part of the category is still proxy data, and
    "not applicable"/"not provided" categories carry no tonnes, so they neither
    earn nor dilute coverage.

    Derived at read time from stored columns, so scenarios saved before this
    existed report a coverage figure without being recalculated. Returns None when
    there is no footprint to apportion.
    """
    total = float(emissions.get("total_tco2e") or 0)
    if total <= 0:
        return None
    flags = (assumptions or {}).get("category_data_quality")
    if flags is None:
        # A row written before the per-category disclosure existed: nothing about it
        # can be claimed as primary data.
        return 0.0
    if not isinstance(flags, dict):
        return None
    measured = sum(
        float(emissions.get(field) or 0)
        for key, field in _COVERAGE_CATEGORY_FIELDS.items()
        if flags.get(key) == "actual"
    )
    # Category totals are stored rounded, so the sum can drift a hair past the total.
    return round(min(measured / total, 1.0) * 100, 1)


def serialize_scenario(s: ScenarioDB) -> dict[str, Any]:
    """ScenarioDB row -> the wire/report dict used by the API and all exports."""
    event_type = getattr(s, "event_type", "conference") or "conference"
    per_attendee_day = (
        round(s.per_attendee_tco2e / max(s.event_days or 1, 1), 4) if s.per_attendee_tco2e else 0
    )
    benchmark = get_benchmark_comparison(event_type, per_attendee_day, s.per_attendee_tco2e)
    assumptions = s.assumptions or {}
    input_payload = s.input_payload or {}
    emissions = {
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
        "data_quality": normalize_data_quality(s.data_quality),
        "scopes": {
            "scope1_tco2e": getattr(s, "scope1_tco2e", 0) or 0,
            "scope2_tco2e": getattr(s, "scope2_tco2e", 0) or 0,
            "scope3_tco2e": getattr(s, "scope3_tco2e", 0) or 0,
        },
    }
    return {
        "scenario_id": s.id,
        "name": s.name,
        "event_name": s.event_name,
        "location": getattr(s, "location", None) or input_payload.get("location") or "",
        "event_type": event_type,
        "attendees": s.attendees,
        "event_days": s.event_days,
        "mode": getattr(s, "mode", None) or "basic",
        "emissions": emissions,
        "assumptions": assumptions,
        "input_payload": input_payload,
        "factors_snapshot": getattr(s, "factors_snapshot", None) or {},
        "coverage_pct": primary_data_coverage_pct(emissions, assumptions),
        "exclusions": input_payload.get("exclusions") or None,
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
            data_quality=normalize_data_quality(s.data_quality),
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
