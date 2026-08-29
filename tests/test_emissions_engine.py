"""Pure-unit tests for the deterministic emissions engine (no DB, no HTTP)."""

import pytest

from app.models.schemas import (
    AccommodationGroup,
    CateringGroup,
    DigitalGroup,
    EquipmentGroup,
    EventScenarioInput,
    SwagGroup,
    TravelClass,
    TravelMode,
    TravelSegment,
    VenueEnergy,
    WasteGroup,
)
from app.services.emissions_engine import (
    EF,
    _OFFSET_PRICE_USD,
    _travel_proxy_kg,
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

    def test_virtual_event_with_segments_gets_no_proxy_remainder(self):
        # A 5-person crew flying to the studio must not book 495 long-haul proxies for
        # the audience sitting at home.
        crew = TravelSegment(mode=TravelMode.LONG_HAUL_FLIGHT, attendees=5, distance_km=4000)
        virtual = calculate_scenario(
            EventScenarioInput(
                name="v-crew", attendees=500, event_type="virtual_event", travel_segments=[crew]
            )
        )
        crew_only = calculate_scenario(
            EventScenarioInput(name="crew-only", attendees=5, travel_segments=[crew])
        )
        assert virtual.emissions.travel_tco2e == pytest.approx(crew_only.emissions.travel_tco2e, rel=1e-9)
        assert "travel_coverage" not in virtual.assumptions

    def test_hybrid_event_nets_declared_virtual_attendees_out_of_the_base(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="hybrid-coverage",
                attendees=500,
                event_type="hybrid_event",
                digital=DigitalGroup(virtual_attendees=200),
                travel_segments=[
                    TravelSegment(mode=TravelMode.SHORT_HAUL_FLIGHT, attendees=100, distance_km=800)
                ],
            )
        )
        # 500 headcount - 200 remote - 100 covered = 200 unallocated travellers.
        segments_only = calculate_scenario(
            EventScenarioInput(
                name="segs",
                attendees=100,
                travel_segments=[
                    TravelSegment(mode=TravelMode.SHORT_HAUL_FLIGHT, attendees=100, distance_km=800)
                ],
            )
        ).emissions.travel_tco2e
        expected = segments_only + _travel_proxy_kg(200) / 1000
        assert result.emissions.travel_tco2e == pytest.approx(expected, abs=1e-4)

        note = result.assumptions["travel_coverage"]
        assert "100 of 300" in note
        assert "200 remote attendees" in note

    def test_hybrid_no_segments_proxy_also_nets_the_remote_cohort(self):
        # The basic-mode path: no travel data at all. The declared remote cohort must be
        # netted here too, or adding travel data would discontinuously drop the total.
        result = calculate_scenario(
            EventScenarioInput(
                name="hybrid-noseg",
                attendees=500,
                event_type="hybrid_event",
                digital=DigitalGroup(virtual_attendees=200),
            )
        )
        assert result.emissions.travel_tco2e == pytest.approx(_travel_proxy_kg(300) / 1000, abs=1e-4)
        note = result.assumptions["travel"]
        assert "300 of 500" in note
        assert "200 remote attendees" in note

    def test_hybrid_no_segments_without_declared_cohort_is_unchanged(self):
        result = calculate_scenario(
            EventScenarioInput(name="hybrid-plain", attendees=500, event_type="hybrid_event")
        )
        assert result.emissions.travel_tco2e == pytest.approx(_travel_proxy_kg(500) / 1000, abs=1e-4)

    def test_conference_no_segments_proxy_ignores_declared_stream_audience(self):
        # A conference's streamed audience is additive, not overlapping — netting must
        # not leak outside hybrid events.
        result = calculate_scenario(
            EventScenarioInput(
                name="conf-stream",
                attendees=500,
                digital=DigitalGroup(virtual_attendees=200),
            )
        )
        assert result.emissions.travel_tco2e == pytest.approx(_travel_proxy_kg(500) / 1000, abs=1e-4)

    def test_adding_travel_data_never_inflates_a_hybrid_total(self):
        """Guards the discontinuity this fix removes: both paths proxy over one base.

        The load-bearing assertion is the identity at the end — the two totals differ by
        exactly (measured cohort - the proxy it replaced), which holds for any segment
        weight. The inequality checked first is weaker and specific to this segment: it
        holds only because a 100-person 800km short-haul cohort is lighter per head than
        the proxy it displaces. A heavier segment could legitimately exceed the
        no-segments total without the base being wrong.
        """
        def hybrid(segments):
            return calculate_scenario(
                EventScenarioInput(
                    name="mono",
                    attendees=500,
                    event_type="hybrid_event",
                    digital=DigitalGroup(virtual_attendees=200),
                    travel_segments=segments,
                )
            ).emissions.travel_tco2e

        segment = TravelSegment(mode=TravelMode.SHORT_HAUL_FLIGHT, attendees=100, distance_km=800)
        no_segments = hybrid([])
        with_segment = hybrid([segment])
        assert with_segment <= no_segments

        # The stronger invariant that holds for any segment weight: the two differ only by
        # (measured cohort - the proxy it replaced), i.e. the proxy base is continuous.
        measured_kg = 100 * 800 * EF["travel"]["short_haul_flight"]["economy"]
        assert with_segment == pytest.approx(
            no_segments - _travel_proxy_kg(100) / 1000 + measured_kg / 1000, abs=1e-4
        )

    def test_hybrid_without_declared_virtual_attendees_uses_full_headcount(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="hybrid-no-digital",
                attendees=500,
                event_type="hybrid_event",
                travel_segments=[
                    TravelSegment(mode=TravelMode.SHORT_HAUL_FLIGHT, attendees=100, distance_km=800)
                ],
            )
        )
        assert "100 of 500 attendees" in result.assumptions["travel_coverage"]


_PHYSICAL_PRESENCE_FIELDS = (
    "venue_energy_tco2e",
    "accommodation_tco2e",
    "catering_tco2e",
    "materials_waste_tco2e",
)


class TestHybridPhysicalPresenceNetting:
    """A hybrid event's physical proxies must size to the people actually on site.

    Netting travel but not venue/accommodation/catering/waste would have the engine
    simultaneously report 300 people travelling and 500 people eating.
    """

    def _assert_same(self, left, right, fields=_PHYSICAL_PRESENCE_FIELDS):
        for field in fields:
            assert getattr(left.emissions, field) == pytest.approx(
                getattr(right.emissions, field), abs=1e-4
            ), field

    def test_hybrid_proxies_size_to_the_on_site_headcount(self):
        # Identity pin: a 500-person hybrid with 200 declared remote must produce the
        # same physical proxies as a plain 300-person event.
        hybrid = calculate_scenario(
            EventScenarioInput(
                name="hybrid",
                attendees=500,
                event_days=2,
                event_type="hybrid_event",
                digital=DigitalGroup(virtual_attendees=200),
            )
        )
        on_site = calculate_scenario(
            EventScenarioInput(name="on-site", attendees=300, event_days=2)
        )
        self._assert_same(hybrid, on_site)

    def test_hybrid_netting_is_disclosed_per_category(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="hybrid-notes",
                attendees=500,
                event_days=2,
                event_type="hybrid_event",
                digital=DigitalGroup(virtual_attendees=200),
            )
        )
        for key in ("venue", "accommodation", "catering", "waste"):
            note = result.assumptions[key]
            assert "300 of 500" in note, f"{key}: {note}"
            assert "200 remote" in note, f"{key}: {note}"

    def test_hybrid_actuals_are_never_netted(self):
        supplied = dict(
            attendees=500,
            event_days=2,
            mode="advanced",
            venue_energy=VenueEnergy(grid_region="singapore", kwh_consumed=5000),
            accommodation=AccommodationGroup(room_nights=400),
            catering=CateringGroup(meals=1000),
            waste=WasteGroup(general_waste_kg=800, recycled_kg=200),
        )
        hybrid = calculate_scenario(
            EventScenarioInput(
                name="hybrid-actual",
                event_type="hybrid_event",
                digital=DigitalGroup(virtual_attendees=200),
                **supplied,
            )
        )
        conference = calculate_scenario(EventScenarioInput(name="conf-actual", **supplied))
        self._assert_same(hybrid, conference)

    def test_conference_stream_audience_keeps_full_headcount_proxies(self):
        # Regression guard: a conference's streamed audience is additive, not overlapping.
        streamed = calculate_scenario(
            EventScenarioInput(
                name="conf-stream",
                attendees=500,
                event_days=2,
                digital=DigitalGroup(virtual_attendees=200),
            )
        )
        plain = calculate_scenario(EventScenarioInput(name="conf", attendees=500, event_days=2))
        self._assert_same(streamed, plain)

    def test_hybrid_without_declared_cohort_keeps_full_headcount_proxies(self):
        hybrid = calculate_scenario(
            EventScenarioInput(
                name="hybrid-plain", attendees=500, event_days=2, event_type="hybrid_event"
            )
        )
        plain = calculate_scenario(EventScenarioInput(name="conf", attendees=500, event_days=2))
        self._assert_same(hybrid, plain)

    def test_swag_is_not_netted(self):
        # Swag is often shipped to remote attendees, so it stays at the full headcount.
        swag = SwagGroup(tshirts=500, tote_bags=500)
        hybrid = calculate_scenario(
            EventScenarioInput(
                name="hybrid-swag",
                attendees=500,
                event_type="hybrid_event",
                digital=DigitalGroup(virtual_attendees=200),
                swag=swag,
            )
        )
        plain = calculate_scenario(
            EventScenarioInput(name="conf-swag", attendees=500, swag=swag)
        )
        assert hybrid.emissions.swag_tco2e == pytest.approx(plain.emissions.swag_tco2e, abs=1e-6)
        assert hybrid.emissions.swag_tco2e > 0


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


class TestOrganizationalBoundary:
    """GHG Protocol control approach: a contracted venue is not the organizer's Scope 1/2."""

    _EQUIPMENT = dict(stage_m2=40, lighting_days=2, sound_system_days=2, generator_hours=12)

    def _result(self, control):
        return calculate_scenario(
            EventScenarioInput(
                name="boundary",
                attendees=200,
                event_days=2,
                venue_energy=VenueEnergy(grid_region="singapore", control=control),
                equipment=EquipmentGroup(control=control, **self._EQUIPMENT),
            )
        )

    def test_contracted_is_the_default(self):
        assert VenueEnergy().control.value == "contracted"
        assert EquipmentGroup().control.value == "contracted"

    def test_contracted_routes_venue_and_equipment_to_scope3(self):
        result = self._result("contracted")
        scopes = result.emissions.scopes
        assert scopes.scope1_tco2e == pytest.approx(0.0, abs=1e-6)
        assert scopes.scope2_tco2e == pytest.approx(0.0, abs=1e-6)
        assert scopes.scope3_tco2e == pytest.approx(result.emissions.total_tco2e, abs=1e-3)
        assert "contracted" in result.assumptions["boundary"]

    def test_owned_operated_keeps_scope1_and_scope2(self):
        result = self._result("owned_operated")
        scopes = result.emissions.scopes
        eq = EF["equipment"]
        expected_scope1 = 12 * eq["generator_diesel_per_hour"]["factor"] / 1000
        assert scopes.scope1_tco2e == pytest.approx(expected_scope1, abs=1e-4)
        assert scopes.scope2_tco2e > result.emissions.venue_energy_tco2e - 1e-9
        assert scopes.scope2_tco2e > 0
        assert "owned/operated" in result.assumptions["boundary"]

    def test_routing_alone_does_not_change_the_total(self):
        contracted = self._result("contracted")
        owned = self._result("owned_operated")
        assert contracted.emissions.total_tco2e == pytest.approx(owned.emissions.total_tco2e, abs=1e-6)
        for field in ("venue_energy_tco2e", "equipment_tco2e"):
            assert getattr(contracted.emissions, field) == pytest.approx(
                getattr(owned.emissions, field), abs=1e-6
            )

    def test_contracted_scenario_reports_no_scope2_figures(self):
        scopes = self._result("contracted").emissions.scopes
        assert scopes.scope2_location_tco2e == 0.0
        assert scopes.scope2_market_tco2e == 0.0

    def _mixed_result(self):
        """Hired venue, but the organizer owns the production kit — a real combination."""
        return calculate_scenario(
            EventScenarioInput(
                name="mixed",
                attendees=200,
                event_days=2,
                venue_energy=VenueEnergy(grid_region="singapore", control="contracted"),
                equipment=EquipmentGroup(control="owned_operated", **self._EQUIPMENT),
            )
        )

    def test_mixed_boundary_keeps_owned_equipment_in_scope1_and_scope2(self):
        result = self._mixed_result()
        scopes = result.emissions.scopes
        eq = EF["equipment"]
        expected_scope1 = 12 * eq["generator_diesel_per_hour"]["factor"] / 1000
        expected_scope2 = (
            2 * eq["lighting_rig_per_day"]["factor"] + 2 * eq["sound_system_per_day"]["factor"]
        ) / 1000
        assert scopes.scope1_tco2e == pytest.approx(expected_scope1, abs=1e-4)
        assert scopes.scope2_tco2e == pytest.approx(expected_scope2, abs=1e-4)
        # The venue is contracted, so none of the venue line is in Scope 2.
        assert scopes.scope2_tco2e < result.emissions.venue_energy_tco2e

    def test_mixed_boundary_note_does_not_deny_the_scope2_it_reports(self):
        """Regression: the disclosure branched on the venue alone and claimed 'no Scope 2'
        while owned equipment electricity was sitting in a non-zero Scope 2."""
        result = self._mixed_result()
        scopes = result.emissions.scopes
        reporting = result.assumptions["scope2_reporting"]
        assert scopes.scope2_tco2e > 0
        assert "no Scope 2" not in reporting["note"]
        # The fields must agree with the scope totals, equipment electricity included.
        assert reporting["location_based_tco2e"] == pytest.approx(scopes.scope2_location_tco2e)
        assert reporting["market_based_tco2e"] == pytest.approx(scopes.scope2_market_tco2e)
        # ...and the note must say where that Scope 2 came from, given the venue is not in it.
        assert "equipment" in reporting["note"]
        assert "contracted" in reporting["note"]

    def test_virtual_event_with_owned_equipment_still_reports_its_scope2(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="virtual-owned-kit",
                event_type="virtual_event",
                attendees=100,
                event_days=1,
                equipment=EquipmentGroup(control="owned_operated", lighting_days=2),
            )
        )
        scopes = result.emissions.scopes
        note = result.assumptions["scope2_reporting"]["note"]
        assert scopes.scope2_tco2e > 0
        assert "no venue" in note.lower()
        # No venue does not mean no Scope 2 — the owned lighting rig is in it.
        assert "no Scope 2 is reported" not in note
        assert "equipment" in note

    def test_owned_note_labels_the_venue_line_and_the_scope_total_separately(self):
        """The prose quoted venue-line figures while the fields carried scope totals."""
        result = calculate_scenario(
            EventScenarioInput(
                name="owned-both",
                attendees=200,
                event_days=2,
                venue_energy=VenueEnergy(grid_region="singapore", control="owned_operated"),
                equipment=EquipmentGroup(control="owned_operated", **self._EQUIPMENT),
            )
        )
        scopes = result.emissions.scopes
        reporting = result.assumptions["scope2_reporting"]
        note = reporting["note"]
        # Equipment electricity means the scope total exceeds the venue line; both
        # quantities appear in the note, each named.
        assert scopes.scope2_location_tco2e > 0
        assert f"{scopes.scope2_location_tco2e:.4f}" in note
        assert "venue electricity" in note
        assert "Scope 2 total" in note

    def test_contracted_still_discloses_the_scope2_duality(self):
        result = calculate_scenario(
            EventScenarioInput(
                name="boundary",
                attendees=200,
                event_days=2,
                venue_energy=VenueEnergy(
                    grid_region="singapore", renewable_pct=100, renewable_instrument="rec"
                ),
            )
        )
        note = result.assumptions["scope2_reporting"]["note"]
        assert "location" in note and "market" in note
        assert result.emissions.scopes.scope2_location_tco2e == 0.0


class TestScope2DualReporting:
    """Both a location-based and a market-based Scope 2 figure, per GHG Protocol Scope 2 Guidance."""

    def _result(self, **venue_kwargs):
        return calculate_scenario(
            EventScenarioInput(
                name="s2",
                attendees=200,
                event_days=2,
                venue_energy=VenueEnergy(
                    grid_region="singapore", control="owned_operated", **venue_kwargs
                ),
            )
        )

    def test_no_renewable_claim_makes_both_bases_equal(self):
        scopes = self._result().emissions.scopes
        assert scopes.scope2_location_tco2e == pytest.approx(scopes.scope2_market_tco2e, abs=1e-6)
        assert scopes.scope2_location_tco2e > 0

    def test_instrument_none_earns_no_market_based_reduction(self):
        claimed = self._result(renewable_pct=100, renewable_instrument="none")
        unclaimed = self._result()
        scopes = claimed.emissions.scopes
        assert scopes.scope2_market_tco2e == pytest.approx(scopes.scope2_location_tco2e, abs=1e-6)
        # An unsubstantiated renewable share must not shrink the footprint at all.
        assert claimed.emissions.venue_energy_tco2e == pytest.approx(
            unclaimed.emissions.venue_energy_tco2e, abs=1e-6
        )
        assert claimed.assumptions["scope2_reporting"]["headline_basis"] == "location_based"

    def test_rec_backed_claim_lowers_the_market_basis(self):
        result = self._result(renewable_pct=100, renewable_instrument="rec")
        scopes = result.emissions.scopes
        assert scopes.scope2_market_tco2e < scopes.scope2_location_tco2e
        assert scopes.scope2_market_tco2e == pytest.approx(0.0, abs=1e-6)
        assert scopes.scope2_tco2e == pytest.approx(scopes.scope2_market_tco2e, abs=1e-6)
        assert result.assumptions["scope2_reporting"]["headline_basis"] == "market_based"

    def test_residual_mix_prices_the_unclaimed_remainder(self):
        result = self._result(renewable_pct=60, renewable_instrument="ppa")
        scopes = result.emissions.scopes
        grid_ef = EF["venue_energy"]["grids"]["singapore"]["factor"]
        uplift = EF["venue_energy"]["residual_mix"]["global_uplift_on_location_factor"]["factor"]
        kwh = estimate_venue_kwh(VenueEnergy(grid_region="singapore"), 200, 2)
        expected_market = kwh * 0.4 * grid_ef * uplift / 1000
        assert scopes.scope2_market_tco2e == pytest.approx(expected_market, abs=1e-4)
        # The remainder is priced ABOVE the grid average — the residual mix is dirtier
        # than the published grid factor once the clean output is contractually claimed.
        assert expected_market > kwh * 0.4 * grid_ef / 1000

    def test_residual_mix_factor_is_documented(self):
        entry = EF["venue_energy"]["residual_mix"]["global_uplift_on_location_factor"]
        assert entry["source"] and entry["methodology"] and entry["limitations"]
        assert entry["factor"] > 1.0


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

    def _result(self, venue_energy, control="contracted"):
        return calculate_scenario(
            EventScenarioInput(
                name="eq",
                attendees=200,
                event_days=3,
                venue_energy=venue_energy,
                equipment=EquipmentGroup(control=control, **self._EQUIPMENT),
            )
        )

    def _owned(self, **venue_kwargs):
        """The same scenario on an owned/operated boundary, where Scope 2 exists.

        The double-count guard is a *quantity* rule (a metered venue supply already
        contains the equipment load), but two of the assertions below read it off the
        Scope 2 figure. Under the default contracted boundary the venue and equipment
        lines are Scope 3, so that figure is 0 by design and would no longer witness
        the guard — these cases pin the boundary that keeps Scope 2 populated.
        """
        return self._result(
            VenueEnergy(grid_region="singapore", control="owned_operated", **venue_kwargs),
            control="owned_operated",
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
        result = self._owned(kwh_consumed=50000)
        venue_scope2 = result.emissions.venue_energy_tco2e
        assert result.emissions.scopes.scope2_tco2e == pytest.approx(venue_scope2, abs=1e-4)

    def test_unmetered_venue_still_counts_equipment_electricity(self):
        result = self._owned()
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

    def test_virtual_event_with_travel_segments_still_has_no_physical_proxies(self):
        # The invariant holds even once a segment exists: the segment counts as-is, and
        # no proxy (travel remainder, venue, accommodation, catering, waste) is invented.
        result = calculate_scenario(
            EventScenarioInput(
                name="v-seg",
                attendees=500,
                event_days=1,
                event_type="virtual_event",
                travel_segments=[
                    TravelSegment(mode=TravelMode.LONG_HAUL_FLIGHT, attendees=5, distance_km=4000)
                ],
            )
        )
        e = result.emissions
        segment_kg = 5 * 4000 * EF["travel"]["long_haul_flight"]["economy"]
        assert e.travel_tco2e == pytest.approx(segment_kg / 1000, abs=1e-4)
        assert e.venue_energy_tco2e == 0
        assert e.accommodation_tco2e == 0
        assert e.catering_tco2e == 0
        assert e.materials_waste_tco2e == 0

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
