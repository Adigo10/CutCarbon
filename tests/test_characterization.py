"""Characterization tests pinning current engine outputs for the seeded payload.

Any deliberate change to calculation behavior must update these expected values
in the same commit, making math changes explicit, reviewed diffs.
"""

import pytest

from app.models.schemas import EventScenarioInput
from app.services.emissions_engine import calculate_scenario, get_reduction_suggestions

from helpers import SEEDED_SCENARIO_PAYLOAD


@pytest.fixture()
def seeded_result():
    scenario = EventScenarioInput(**SEEDED_SCENARIO_PAYLOAD)
    return calculate_scenario(scenario)


def test_seeded_scenario_category_totals(seeded_result):
    e = seeded_result.emissions
    assert e.travel_tco2e == pytest.approx(48.36, abs=0.01)
    assert e.venue_energy_tco2e == pytest.approx(0.9045, abs=0.001)
    assert e.accommodation_tco2e == pytest.approx(2.835, abs=0.001)
    assert e.catering_tco2e == pytest.approx(0.4392, abs=0.001)
    assert e.materials_waste_tco2e == pytest.approx(0.0757, abs=0.001)
    assert e.equipment_tco2e == 0.0
    assert e.swag_tco2e == 0.0
    assert e.total_tco2e == pytest.approx(52.6144, abs=0.01)
    assert e.per_attendee_tco2e == pytest.approx(0.4385, abs=0.001)


def test_seeded_scenario_suggestions_shape(seeded_result):
    suggestions = get_reduction_suggestions(seeded_result, 30.0, catering_type="vegetarian_meal")

    actions = [s["action"] for s in suggestions]
    assert actions == [
        "enable_hybrid",
        "shift_to_rail",
        "shuttle_bus",
        "eco_accommodation",
        "renewable_energy",
        "local_seasonal",
        "zero_waste",
        "digital_materials",
        "offset_residual",
    ]

    for s in suggestions:
        assert {"action", "label", "co2e_saved_tco2e", "estimated_cost_usd", "category", "difficulty", "scope"} <= set(s)

    assert suggestions[0]["co2e_saved_tco2e"] == pytest.approx(14.508, abs=0.001)

    reductions = [s for s in suggestions if not s.get("is_neutralization")]
    assert sum(s["co2e_saved_tco2e"] for s in reductions) <= seeded_result.emissions.total_tco2e + 1e-6

    offset = suggestions[-1]
    assert offset["is_neutralization"] is True
    assert offset["co2e_saved_tco2e"] == pytest.approx(7.876, abs=0.001)
    # Priced from tax_incentives.json carbon_offset_purchase.cost_per_tco2e_usd ($15/t).
    assert offset["estimated_cost_usd"] == pytest.approx(118.0, abs=0.5)
