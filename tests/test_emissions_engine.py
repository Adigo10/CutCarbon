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
    WasteGroup,
)
from app.services.emissions_engine import (
    EF,
    _OFFSET_PRICE_USD,
    calculate_scenario,
    estimate_venue_kwh,
    get_benchmark_comparison,
    get_reduction_suggestions,
)

_KWH_INTENSITY = EF["venue_energy"]["proxy_kwh_intensity"]["conference_centre_kwh_per_m2_day"]["factor"]


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


class TestRoundTripTravel:
    def _travel(self, *, round_trip: bool) -> float:
        scenario = EventScenarioInput(
            name="rt",
            attendees=10,
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT, attendees=10, distance_km=1000, round_trip=round_trip
                )
            ],
        )
        return calculate_scenario(scenario).emissions.travel_tco2e

    def test_round_trip_doubles_the_segment(self):
        one_way = self._travel(round_trip=False)
        assert one_way > 0
        assert self._travel(round_trip=True) == pytest.approx(one_way * 2, rel=1e-9)

    def test_default_is_one_way(self):
        segment = TravelSegment(mode=TravelMode.LONG_HAUL_FLIGHT, attendees=10, distance_km=1000)
        assert segment.round_trip is False

    def test_one_way_convention_is_recorded(self):
        scenario = EventScenarioInput(
            name="rt-note",
            attendees=10,
            travel_segments=[TravelSegment(mode=TravelMode.LONG_HAUL_FLIGHT, attendees=10, distance_km=1000)],
        )
        assert "one-way" in calculate_scenario(scenario).assumptions["travel_distance_basis"]


class TestUnallocatedAttendeeReconciliation:
    def _scenario(self, attendees: int, segment_attendees: int) -> EventScenarioInput:
        return EventScenarioInput(
            name="coverage",
            attendees=attendees,
            travel_segments=[
                TravelSegment(mode=TravelMode.SHORT_HAUL_FLIGHT, attendees=segment_attendees, distance_km=800)
            ],
        )

    def test_remainder_is_estimated_via_proxy(self):
        partial = calculate_scenario(self._scenario(500, 100)).emissions.travel_tco2e
        segments_only = calculate_scenario(self._scenario(100, 100)).emissions.travel_tco2e
        assert partial > segments_only

    def test_coverage_note_present(self):
        result = calculate_scenario(self._scenario(500, 100))
        note = result.assumptions["travel_coverage"]
        assert "100 of 500" in note
        assert "20" in note  # 20% covered

    def test_travel_quality_downgraded_to_partial(self):
        result = calculate_scenario(self._scenario(500, 100))
        assert result.assumptions["category_data_quality"]["travel"] == "partial"

    def test_full_coverage_keeps_actual_and_adds_nothing(self):
        result = calculate_scenario(self._scenario(100, 100))
        assert "travel_coverage" not in result.assumptions
        assert result.assumptions["category_data_quality"]["travel"] == "actual"


class TestVenueKwh:
    def test_actual_kwh_wins(self):
        assert estimate_venue_kwh(VenueEnergy(kwh_consumed=2500, venue_area_m2=999), 120, 2) == 2500

    def test_area_proxy(self):
        assert estimate_venue_kwh(VenueEnergy(venue_area_m2=100), 120, 2) == 100 * 2 * _KWH_INTENSITY

    def test_attendee_proxy(self):
        assert estimate_venue_kwh(None, 120, 2) == 120 * 2.0 * 2 * _KWH_INTENSITY


class TestVenueProxyReconciliation:
    """The two venue proxies (kg/m2/day vs kWh/m2/day x grid) must agree."""

    def _venue(self, venue_energy) -> float:
        return calculate_scenario(
            EventScenarioInput(name="venue", attendees=300, event_days=2, venue_energy=venue_energy)
        ).emissions.venue_energy_tco2e

    def test_kwh_intensity_is_a_sourced_factor_entry(self):
        entry = EF["venue_energy"]["proxy_kwh_intensity"]["conference_centre_kwh_per_m2_day"]
        assert entry["source"] and entry["methodology"]
        assert entry["unit"] == "kwh_per_m2_per_day"

    def test_grid_only_venue_matches_the_area_intensity_proxy(self):
        no_venue_input = self._venue(None)
        grid_only = self._venue(VenueEnergy(grid_region="global_average"))
        assert no_venue_input > 0
        ratio = grid_only / no_venue_input
        assert 0.7 <= ratio <= 1.3, f"venue proxies disagree by {ratio:.2f}x"

    def test_venue_basis_recorded_for_each_path(self):
        def basis(venue_energy):
            return calculate_scenario(
                EventScenarioInput(name="v", attendees=100, event_days=1, venue_energy=venue_energy)
            ).assumptions["venue_basis"]

        assert basis(None) == "area_intensity_proxy"
        assert basis(VenueEnergy(grid_region="singapore")) == "attendee_kwh_proxy"
        assert basis(VenueEnergy(grid_region="singapore", venue_area_m2=500)) == "area_kwh_proxy"
        assert basis(VenueEnergy(grid_region="singapore", kwh_consumed=1000)) == "measured_kwh"


class TestEquipmentDoubleCountGuard:
    """A venue meter reading already covers the equipment plugged into it."""

    _EQUIPMENT = dict(
        stage_m2=50,
        lighting_days=3,
        sound_system_days=3,
        led_screen_m2=20,
        projectors=4,
        generator_hours=10,
        freight_tonne_km=100,
    )

    def _result(self, venue_energy):
        return calculate_scenario(
            EventScenarioInput(
                name="eq",
                attendees=200,
                event_days=3,
                venue_energy=venue_energy,
                equipment=EquipmentGroup(**self._EQUIPMENT),
            )
        )

    def test_metered_venue_kwh_lowers_equipment_total(self):
        metered = self._result(VenueEnergy(grid_region="singapore", kwh_consumed=50000))
        unmetered = self._result(VenueEnergy(grid_region="singapore"))
        assert metered.emissions.equipment_tco2e < unmetered.emissions.equipment_tco2e

    def test_metered_equipment_keeps_only_non_electricity_lines(self):
        eq = EF["equipment"]
        expected_kg = (
            50 * 3 * eq["stage_per_m2_per_day"]["factor"]
            + 100 * eq["freight_truck_per_km"]["factor"]
            + 10 * eq["generator_diesel_per_hour"]["factor"]
        )
        result = self._result(VenueEnergy(grid_region="singapore", kwh_consumed=50000))
        assert result.emissions.equipment_tco2e == pytest.approx(expected_kg / 1000, abs=1e-4)
        assert "metered venue supply" in result.assumptions["equipment_electricity"]

    def test_metered_equipment_contributes_no_scope2(self):
        result = self._result(VenueEnergy(grid_region="singapore", kwh_consumed=50000))
        venue_scope2 = result.emissions.venue_energy_tco2e
        assert result.emissions.scopes.scope2_tco2e == pytest.approx(venue_scope2, abs=1e-4)

    def test_unmetered_venue_still_counts_equipment_electricity(self):
        result = self._result(VenueEnergy(grid_region="singapore"))
        assert "metered venue supply" not in result.assumptions.get("equipment_electricity", "")
        assert result.emissions.scopes.scope2_tco2e > result.emissions.venue_energy_tco2e


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


class TestWaste:
    def _waste(self, *, event_days: int = 1, waste=None) -> float:
        return calculate_scenario(
            EventScenarioInput(name="w", attendees=200, event_days=event_days, waste=waste)
        ).emissions.materials_waste_tco2e

    def test_proxy_scales_with_event_days(self):
        assert self._waste(event_days=5) > self._waste(event_days=1)

    def test_only_general_waste_scales_not_printed_handouts(self):
        mw = EF["materials_waste"]
        printed_kg = 200 * 0.5 * mw["paper_cardboard"]["factor"]
        general_per_day_kg = 200 * 0.3 * mw["general_landfill"]["factor"]
        assert self._waste(event_days=5) == pytest.approx(
            (printed_kg + general_per_day_kg * 5) / 1000, abs=1e-4
        )

    def test_measured_waste_drops_the_printed_materials_proxy(self):
        mw = EF["materials_waste"]
        measured = WasteGroup(general_waste_kg=400, recycled_kg=150)
        expected_kg = (
            400 * mw["general_landfill"]["factor"] + 150 * mw["recycled_mixed"]["factor"]
        )
        assert self._waste(waste=measured) == pytest.approx(expected_kg / 1000, abs=1e-4)

    def test_measured_waste_records_the_exclusion(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="w", attendees=200, waste=WasteGroup(general_waste_kg=400, recycled_kg=150)
            )
        )
        assert "printed" in result.assumptions["waste"].lower()

    def test_explicit_printed_materials_choice_is_honored(self):
        mw = EF["materials_waste"]
        measured = WasteGroup(general_waste_kg=400, printed_materials_per_attendee=True)
        expected_kg = (
            400 * mw["general_landfill"]["factor"]
            + 200 * mw["printed_materials_per_attendee"]["factor"]
        )
        assert self._waste(waste=measured) == pytest.approx(expected_kg / 1000, abs=1e-4)

    def test_unmeasured_waste_group_still_adds_printed_materials(self):
        mw = EF["materials_waste"]
        booths_only = WasteGroup(exhibition_booths_m2=100)
        expected_kg = (
            100 * mw["exhibition_booth_per_m2"]["factor"]
            + 200 * mw["printed_materials_per_attendee"]["factor"]
        )
        assert self._waste(waste=booths_only) == pytest.approx(expected_kg / 1000, abs=1e-4)


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
