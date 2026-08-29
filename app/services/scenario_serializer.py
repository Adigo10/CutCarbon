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
from app.services.emissions_engine import (
    build_factors_snapshot,
    current_versions,
    get_benchmark_comparison,
)

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


def _factor_drift(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compare a stored factors snapshot against what a fresh calculation would use.

    A scenario is "stale" when it was calculated under a different factor catalog or
    a different engine version — i.e. re-running "Recalculate all" would change it.
    A scenario with no snapshot at all is not flagged: there is nothing to compare.
    """
    current = current_versions()
    stale = bool(snapshot) and (
        str(snapshot.get("ef_version") or "") != current["ef_version"]
        or str(snapshot.get("engine_version") or "") != current["engine_version"]
    )
    return {
        "current_ef_version": current["ef_version"],
        "current_engine_version": current["engine_version"],
        "factors_stale": stale,
    }


def scope2_dual_bases(assumptions: Any, scope2_tco2e: float) -> tuple[float, float]:
    """Stored assumptions -> the (location-based, market-based) Scope 2 pair.

    The engine writes both figures into ``assumptions["scope2_reporting"]`` (a JSONB
    column that already round-trips), so no dedicated columns are needed. Rows written
    before dual reporting carry only the headline figure; with no contractual
    instrument on record the two bases coincide, so both fall back to it.
    """
    reporting = (assumptions or {}).get("scope2_reporting") or {}
    headline = float(scope2_tco2e or 0)
    location = reporting.get("location_based_tco2e")
    market = reporting.get("market_based_tco2e")
    return (
        float(location) if isinstance(location, (int, float)) else headline,
        float(market) if isinstance(market, (int, float)) else headline,
    )


def serialize_scenario(s: ScenarioDB) -> dict[str, Any]:
    """ScenarioDB row -> the wire/report dict used by the API and all exports."""
    event_type = getattr(s, "event_type", "conference") or "conference"
    factors_snapshot = getattr(s, "factors_snapshot", None) or {}
    per_attendee_day = (
        round(s.per_attendee_tco2e / max(s.event_days or 1, 1), 4) if s.per_attendee_tco2e else 0
    )
    benchmark = get_benchmark_comparison(event_type, per_attendee_day, s.per_attendee_tco2e)
    scope2 = getattr(s, "scope2_tco2e", 0) or 0
    scope2_location, scope2_market = scope2_dual_bases(s.assumptions, scope2)
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
            "data_quality": normalize_data_quality(s.data_quality),
            "scopes": {
                "scope1_tco2e": getattr(s, "scope1_tco2e", 0) or 0,
                "scope2_tco2e": scope2,
                "scope3_tco2e": getattr(s, "scope3_tco2e", 0) or 0,
                "scope2_location_tco2e": scope2_location,
                "scope2_market_tco2e": scope2_market,
            },
        },
        "assumptions": s.assumptions or {},
        "input_payload": s.input_payload or {},
        "factors_snapshot": factors_snapshot,
        **_factor_drift(factors_snapshot),
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
    scope2_location, scope2_market = scope2_dual_bases(
        s.assumptions, getattr(s, "scope2_tco2e", 0) or 0
    )
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
                scope2_location_tco2e=scope2_location,
                scope2_market_tco2e=scope2_market,
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
