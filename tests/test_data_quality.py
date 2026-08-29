"""Data-quality tier vocabulary: engine assignment, legacy mapping, export labels.

The tiers are `modelled` / `partly_primary` / `primary`. `primary` is an
evidence tier: nothing the engine can see (mode, form completeness) may award
it, and stored rows written under the retired vocabulary
("estimated"/"partial"/"verified") must never surface through the API or an
export.
"""

import pytest
from fastapi.testclient import TestClient

from app.models.database import ScenarioDB
from app.models.schemas import EventScenarioInput, ScenarioMode
from app.services.emissions_engine import calculate_scenario
from app.services.scenario_serializer import (
    DATA_QUALITY_TIERS,
    data_quality_label,
    db_row_to_result,
    normalize_data_quality,
    serialize_scenario,
)
from helpers import create_seeded_scenario, register_user

_FULLY_POPULATED = {
    "name": "full",
    "attendees": 100,
    "event_days": 2,
    "travel_segments": [
        {"mode": "long_haul_flight", "travel_class": "economy", "attendees": 100, "distance_km": 4000}
    ],
    "venue_energy": {"grid_region": "singapore", "kwh_consumed": 5000},
    "accommodation": {"accommodation_type": "standard_hotel", "room_nights": 200},
    "catering": {"catering_type": "mixed_buffet", "meals": 400},
    "waste": {"general_waste_kg": 300, "recycled_kg": 120},
    "equipment": {"led_screen_m2": 20, "lighting_days": 2},
    "swag": {"tshirts": 100, "lanyards": 100},
    "digital": {"virtual_attendees": 50, "streaming_hours_per_day": 4},
}


def _quality(**overrides) -> str:
    payload = {**_FULLY_POPULATED, **overrides}
    return calculate_scenario(EventScenarioInput(**payload)).emissions.data_quality


class TestEngineTierAssignment:
    def test_bare_scenario_is_modelled(self):
        assert _quality(
            travel_segments=[], venue_energy=None, accommodation=None, catering=None,
            waste=None, equipment=None, swag=None, digital=None,
        ) == "modelled"

    def test_some_measured_input_is_partly_primary(self):
        assert _quality(
            travel_segments=[], accommodation=None, catering=None, waste=None,
            equipment=None, swag=None, digital=None,
        ) == "partly_primary"

    def test_primary_is_not_reachable_from_mode_or_form_completeness(self):
        # Every combination of mode x completeness: filling in forms proves
        # completeness, not provenance, so Tier 1 must stay unreachable.
        for mode in (ScenarioMode.BASIC, ScenarioMode.ADVANCED):
            assert _quality(mode=mode) != "primary"
            assert _quality(mode=mode) == "partly_primary"
            assert _quality(
                mode=mode, travel_segments=[], venue_energy=None, accommodation=None,
                catering=None, waste=None, equipment=None, swag=None, digital=None,
            ) == "modelled"

    def test_engine_never_emits_the_retired_vocabulary(self):
        for mode in (ScenarioMode.BASIC, ScenarioMode.ADVANCED):
            assert _quality(mode=mode) in DATA_QUALITY_TIERS


class TestLegacyMapping:
    @pytest.mark.parametrize(
        "stored,expected",
        [
            ("estimated", "modelled"),
            ("partial", "partly_primary"),
            # The old "verified" was awarded for form completeness alone, with no
            # evidence attached — it must not be promoted to the evidence tier.
            ("verified", "partly_primary"),
            ("modelled", "modelled"),
            ("partly_primary", "partly_primary"),
            ("primary", "primary"),
            (None, "modelled"),
            ("", "modelled"),
            ("something_unknown", "modelled"),
        ],
    )
    def test_normalize(self, stored, expected):
        assert normalize_data_quality(stored) == expected

    @pytest.mark.parametrize("stored", ["estimated", "partial", "verified"])
    def test_serialize_scenario_never_emits_old_words(self, stored):
        row = _row(stored)
        assert serialize_scenario(row)["emissions"]["data_quality"] not in (
            "estimated", "partial", "verified",
        )

    def test_serialize_scenario_maps_old_verified_to_partly_primary(self):
        assert serialize_scenario(_row("verified"))["emissions"]["data_quality"] == "partly_primary"

    def test_db_row_to_result_maps_too(self):
        assert db_row_to_result(_row("estimated")).emissions.data_quality == "modelled"


class TestDisplayLabels:
    @pytest.mark.parametrize(
        "value,label",
        [
            ("modelled", "Tier 3 — modelled"),
            ("partly_primary", "Tier 2 — partly primary"),
            ("primary", "Tier 1 — primary (evidenced)"),
            # Legacy stored values render under the new vocabulary too.
            ("estimated", "Tier 3 — modelled"),
            ("verified", "Tier 2 — partly primary"),
        ],
    )
    def test_label(self, value, label):
        assert data_quality_label(value) == label

    def test_csv_export_renders_the_tier_label(self, client: TestClient):
        headers = register_user(client, email="tier-csv@example.com")
        scenario_id = create_seeded_scenario(client, headers)

        content = client.get(f"/api/exports/scenarios/{scenario_id}.csv", headers=headers).text

        assert "metadata,data_quality,Data Quality,Tier 2 — partly primary," in content
        for retired in ("estimated", "partial", "verified"):
            assert f"Data Quality,{retired}" not in content


def _row(data_quality: str) -> ScenarioDB:
    return ScenarioDB(
        id="00000000-0000-0000-0000-000000000001",
        name="legacy",
        event_name="Legacy Event",
        location="Singapore",
        event_type="conference",
        attendees=100,
        event_days=2,
        mode="advanced",
        travel_tco2e=1.0,
        venue_energy_tco2e=0.5,
        accommodation_tco2e=0.5,
        catering_tco2e=0.2,
        materials_waste_tco2e=0.1,
        equipment_tco2e=0.1,
        swag_tco2e=0.1,
        digital_tco2e=0.1,
        total_tco2e=2.6,
        per_attendee_tco2e=0.026,
        scope1_tco2e=0.0,
        scope2_tco2e=0.5,
        scope3_tco2e=2.1,
        data_quality=data_quality,
        assumptions={},
        input_payload={},
        factors_snapshot={},
    )
