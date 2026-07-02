"""Pure-unit tests for the deterministic emissions engine (no DB, no HTTP)."""

import pytest

from app.models.schemas import (
    DigitalGroup,
    EquipmentGroup,
    EventScenarioInput,
    TravelClass,
    TravelMode,
    TravelSegment,
    VenueEnergy,
)
from app.services.emissions_engine import (
    EF,
    _OFFSET_PRICE_USD,
    calculate_scenario,
    estimate_venue_kwh,
    get_benchmark_comparison,
    get_reduction_suggestions,
)


def _travel_total(mode: TravelMode, travel_class: TravelClass) -> float:
    scenario = EventScenarioInput(
        name="travel",
        attendees=10,
        travel_segments=[TravelSegment(mode=mode, travel_class=travel_class, attendees=10, distance_km=100)],
    )
    return calculate_scenario(scenario).emissions.travel_tco2e


class TestTravelClassMatrix:
    def test_ground_modes_ignore_cabin_class(self):
        for mode in (TravelMode.TRAIN_EUROPE, TravelMode.CAR_PETROL, TravelMode.BUS_COACH, TravelMode.FERRY):
            eco = _travel_total(mode, TravelClass.ECONOMY)
            assert _travel_total(mode, TravelClass.BUSINESS) == eco
            assert _travel_total(mode, TravelClass.FIRST) == eco

    def test_long_haul_cabin_classes_differentiated(self):
        eco = _travel_total(TravelMode.LONG_HAUL_FLIGHT, TravelClass.ECONOMY)
        business = _travel_total(TravelMode.LONG_HAUL_FLIGHT, TravelClass.BUSINESS)
        first = _travel_total(TravelMode.LONG_HAUL_FLIGHT, TravelClass.FIRST)
        assert eco < business < first

    def test_short_haul_first_falls_back_to_business(self):
        # No published short-haul first-class factor; the old code invented 0.6.
        assert _travel_total(TravelMode.SHORT_HAUL_FLIGHT, TravelClass.FIRST) == _travel_total(
            TravelMode.SHORT_HAUL_FLIGHT, TravelClass.BUSINESS
        )

    def test_short_haul_fallback_is_noted(self):
        scenario = EventScenarioInput(
            name="fallback",
            attendees=10,
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.SHORT_HAUL_FLIGHT, travel_class=TravelClass.FIRST, attendees=10, distance_km=100
                )
            ],
        )
        result = calculate_scenario(scenario)
        assert "travel_short_haul_flight_class" in result.assumptions


class TestVenueKwh:
    def test_actual_kwh_wins(self):
        assert estimate_venue_kwh(VenueEnergy(kwh_consumed=2500, venue_area_m2=999), 120, 2) == 2500

    def test_area_proxy(self):
        assert estimate_venue_kwh(VenueEnergy(venue_area_m2=100), 120, 2) == 100 * 2 * 30

    def test_attendee_proxy(self):
        assert estimate_venue_kwh(None, 120, 2) == 120 * 2.0 * 2 * 30


class TestReductionSuggestions:
    def test_led_lever_caps_at_lighting_share(self):
        scenario = EventScenarioInput(
            name="gen-heavy",
            attendees=100,
            event_days=2,
            equipment=EquipmentGroup(generator_hours=100, lighting_days=2, freight_tonne_km=500),
        )
        result = calculate_scenario(scenario)
        suggestions = get_reduction_suggestions(
            result, 30.0, equipment_input={"generator_hours": 100, "lighting_days": 2, "freight_tonne_km": 500}
        )
        led = [s for s in suggestions if s["action"] == "led_lighting"]
        lighting_tco2e = 2 * EF["equipment"]["lighting_rig_per_day"]["factor"] / 1000
        assert led and led[0]["co2e_saved_tco2e"] == pytest.approx(lighting_tco2e * 0.40, abs=1e-6)

    def test_led_lever_skipped_without_equipment_input(self):
        scenario = EventScenarioInput(
            name="gen", attendees=100, equipment=EquipmentGroup(generator_hours=50)
        )
        result = calculate_scenario(scenario)
        suggestions = get_reduction_suggestions(result, 30.0)
        assert not [s for s in suggestions if s["action"] == "led_lighting"]

    def test_reductions_never_exceed_total(self):
        scenario = EventScenarioInput(**{
            "name": "clamp", "attendees": 300, "event_days": 3,
            "venue_energy": {"grid_region": "australia", "kwh_consumed": 50000},
        })
        result = calculate_scenario(scenario)
        suggestions = get_reduction_suggestions(result, 30.0)
        reductions = [s for s in suggestions if not s.get("is_neutralization")]
        assert sum(s["co2e_saved_tco2e"] for s in reductions) <= result.emissions.total_tco2e + 1e-6

    def test_offset_price_sourced_from_data(self):
        scenario = EventScenarioInput(name="offsets", attendees=200)
        result = calculate_scenario(scenario)
        suggestions = get_reduction_suggestions(result, 30.0)
        offset = suggestions[-1]
        assert offset["is_neutralization"] is True
        assert offset["estimated_cost_usd"] == pytest.approx(
            round(offset["co2e_saved_tco2e"] * _OFFSET_PRICE_USD, 0), abs=0.5
        )


class TestDigitalCategory:
    def test_virtual_event_has_no_physical_proxies(self):
        result = calculate_scenario(
            EventScenarioInput(name="v", attendees=500, event_days=1, event_type="virtual_event")
        )
        e = result.emissions
        assert e.travel_tco2e == 0
        assert e.venue_energy_tco2e == 0
        assert e.accommodation_tco2e == 0
        assert e.catering_tco2e == 0
        assert e.materials_waste_tco2e == 0
        # 500 attendees x 6h x 0.036 kg = 108 kg
        assert e.digital_tco2e == pytest.approx(0.108, abs=0.001)
        assert e.total_tco2e == pytest.approx(e.digital_tco2e, abs=1e-6)

    def test_virtual_event_honors_explicit_inputs(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="v-studio",
                attendees=500,
                event_type="virtual_event",
                venue_energy=VenueEnergy(grid_region="singapore", kwh_consumed=800),
            )
        )
        assert result.emissions.venue_energy_tco2e > 0

    def test_hybrid_event_gets_both_proxies(self):
        result = calculate_scenario(
            EventScenarioInput(name="h", attendees=500, event_days=1, event_type="hybrid_event")
        )
        assert result.emissions.travel_tco2e > 0
        # 30% of attendees stream 6h/day
        assert result.emissions.digital_tco2e == pytest.approx(150 * 6 * 0.036 / 1000, abs=0.001)

    def test_explicit_digital_group(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="d",
                attendees=100,
                event_days=2,
                digital=DigitalGroup(
                    virtual_attendees=1000, streaming_hours_per_day=4, event_app_users=800, emails_sent=50000
                ),
            )
        )
        # 1000*4*2*0.036 + 800*2*0.008 + 50*0.6 = 288 + 12.8 + 30 = 330.8 kg
        assert result.emissions.digital_tco2e == pytest.approx(0.3308, abs=0.001)

    def test_category_data_quality_flags(self):
        result = calculate_scenario(
            EventScenarioInput(**{
                "name": "dq", "attendees": 100,
                "venue_energy": {"grid_region": "singapore", "kwh_consumed": 100},
            })
        )
        quality = result.assumptions["category_data_quality"]
        assert quality["venue_energy"] == "actual"
        assert quality["travel"] == "proxy"
        assert quality["equipment"] == "not provided"
        assert quality["digital"] == "not provided"


class TestBenchmarks:
    def test_gala_uses_per_attendee_basis(self):
        # Gala bands are per whole-event attendee, not per attendee-day.
        comparison = get_benchmark_comparison("gala_dinner", per_attendee_day=0.01, per_attendee=0.5)
        assert comparison is not None
        assert comparison.your_per_attendee_day == 0.5

    def test_conference_uses_per_attendee_day_basis(self):
        comparison = get_benchmark_comparison("conference", per_attendee_day=0.05, per_attendee=0.5)
        assert comparison is not None
        assert comparison.your_per_attendee_day == 0.05
