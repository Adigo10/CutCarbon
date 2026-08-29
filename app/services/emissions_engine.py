"""
Deterministic emissions calculation engine.
Implements GHG Protocol Scope 1/2/3 methodology for events.
"""
import json
import logging
from pathlib import Path
from typing import NamedTuple, Optional
from datetime import datetime

from app.models.schemas import (
    EventScenarioInput, ScenarioResult, EmissionBreakdown, ScopeBreakdown,
    BenchmarkComparison, BoundaryControl, RenewableInstrument, TravelMode,
    TravelClass, GridRegion, ScenarioMode
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"

with open(_DATA_DIR / "emission_factors.json", encoding="utf-8") as f:
    EF = json.load(f)

from app.services.data_files import TAX_DATA as _TAX_DATA  # noqa: E402
from app.utils.time import utcnow

# Single source for the offset price used in suggestions (Gold Standard / VCS average).
_OFFSET_PRICE_USD = (
    _TAX_DATA.get("reduction_action_savings", {})
    .get("carbon_offset_purchase", {})
    .get("cost_per_tco2e_usd", 15.0)
)


def reload_factors() -> None:
    """Re-read emission_factors.json into the shared EF dict IN PLACE.

    The in-place update (clear + update) is deliberate: other modules import this
    same dict object (e.g. ``from app.services.emissions_engine import EF``), so
    rebinding the name would not propagate. Mutating in place means a TinyFish
    refresh is reflected by the very next calculation without a process restart.
    """
    with open(_DATA_DIR / "emission_factors.json", encoding="utf-8") as f:
        fresh = json.load(f)
    EF.clear()
    EF.update(fresh)


def physical_attendee_count(scenario) -> int:
    """Headcount physically present at the venue.

    Hybrid events net out an explicitly declared remote cohort — those people neither
    travel to the venue nor occupy a hotel room, a seat at lunch, or floor space. Every
    other event type uses the full headcount: a conference's streamed audience is
    *additive* to the room, not overlapping with it, and a virtual event is gated
    separately in calculate_scenario.

    Single source for the netting, shared by the travel base, the physical-presence
    proxies and the financial back-calculation, so the categories cannot disagree about
    how many people were in the building.
    """
    if scenario.event_type.value != "hybrid_event":
        return scenario.attendees
    declared_remote = scenario.digital.virtual_attendees if scenario.digital else 0
    return scenario.attendees - min(declared_remote, scenario.attendees)


def _netting_note(physical_attendees: int, attendees: int) -> str:
    """Disclosure clause appended to a proxy note when a remote cohort was netted out."""
    remote = attendees - physical_attendees
    if remote <= 0:
        return ""
    return (
        f" (sized for {physical_attendees} of {attendees} attendees; "
        f"{remote} remote attendees are not physically present)"
    )


def _holds_control(group) -> bool:
    """True when the organizer holds operational control of ``group``'s asset.

    Absent input (no venue/equipment block at all) falls back to the schema default,
    ``contracted`` — an organizer who never declared a boundary hired the space.
    """
    if group is None:
        return False
    control = getattr(group, "control", BoundaryControl.CONTRACTED)
    return getattr(control, "value", control) == BoundaryControl.OWNED_OPERATED.value


def _travel_proxy_kg(attendees: float) -> float:
    """Per-head travel proxy: 70% fly long-haul 2000km economy, 30% local MRT 50km."""
    long_haul = attendees * 0.7 * 2000 * EF["travel"]["long_haul_flight"]["economy"]
    local = attendees * 0.3 * 50 * EF["travel"]["mrt_metro"]["factor"]
    return long_haul + local


def _travel_emissions(
    segments,
    attendees: int,
    *,
    reconcile: bool = True,
    remote_attendees: int = 0,
) -> tuple[float, dict]:
    """Returns travel kg CO2e and assumption notes.

    ``reconcile`` gates the unallocated-attendee remainder. It is off for virtual events,
    where the headcount is an audience that never travels — supplied segments (e.g. a crew
    flying to the studio) count as-is and nothing is inferred on top.
    ``remote_attendees`` is netted out of the travelling base for hybrid events, so the
    declared virtual cohort does not get booked physical travel it never took. It applies
    to BOTH proxy paths — the no-segments proxy and the unallocated remainder — so that
    supplying travel data for part of the headcount cannot discontinuously change the base.
    """
    total_kg = 0.0
    notes = {}
    travel_base = attendees - remote_attendees

    if not segments:
        total_kg = _travel_proxy_kg(travel_base)
        notes["travel"] = "Proxy: 70% long-haul flight 2000km economy, 30% local MRT 50km"
        if remote_attendees > 0:
            notes["travel"] += (
                f", applied to {travel_base} of {attendees} attendees; "
                f"{remote_attendees} remote attendees do not travel to the venue"
            )
    else:
        for seg in segments:
            mode = seg.mode.value
            ef_data = EF["travel"].get(mode)
            if not isinstance(ef_data, dict):
                logger.error("No emission factor for travel mode %r; segment excluded", mode)
                notes[f"travel_{mode}"] = f"No emission factor for '{mode}'; segment excluded from total"
                continue
            if "economy" in ef_data:
                # Cabin-class factor table (flights). If the requested class has no
                # published factor (e.g. short-haul first), fall back to the highest
                # class available rather than inventing a multiplier.
                requested = seg.travel_class.value
                if requested in ef_data:
                    ef = ef_data[requested]
                else:
                    fallback = "business" if "business" in ef_data else "economy"
                    ef = ef_data[fallback]
                    notes[f"travel_{mode}_class"] = (
                        f"No published {requested}-class factor for {mode}; used {fallback}"
                    )
            elif "factor" in ef_data:
                # Single-factor mode (rail, road, ferry, private jet): cabin class
                # does not change the per-passenger-km factor.
                ef = ef_data["factor"]
            else:
                logger.error("Malformed emission factor for travel mode %r; segment excluded", mode)
                notes[f"travel_{mode}"] = f"No usable emission factor for '{mode}'; segment excluded from total"
                continue
            legs = 2 if seg.round_trip else 1
            total_kg += seg.attendees * seg.distance_km * legs * ef

        notes["travel_distance_basis"] = (
            "Segment distances are treated as one-way unless round_trip is set (then doubled)"
        )

        # Reconcile against the headcount: attendees not covered by any segment would
        # otherwise travel to the event for free. Estimate the remainder with the same
        # proxy used when no segments are supplied at all. Only attendees who actually
        # travel to the venue are in the base — remote attendees never do.
        if reconcile:
            covered = sum(seg.attendees for seg in segments)
            unallocated = max(0, travel_base - covered)
            if unallocated > 0:
                total_kg += _travel_proxy_kg(unallocated)
                coverage_pct = (covered / travel_base * 100) if travel_base > 0 else 0.0
                note = (
                    f"Travel data covers {covered} of {travel_base} attendees ({coverage_pct:.0f}%); "
                    f"the remaining {unallocated} estimated via proxy "
                    "(70% long-haul flight 2000km economy, 30% local MRT 50km)"
                )
                if remote_attendees > 0:
                    note += (
                        f". {remote_attendees} remote attendees were netted out of the "
                        f"{attendees}-person headcount — they do not travel to the venue"
                    )
                notes["travel_coverage"] = note

    return total_kg, notes


# Floor area assumed per attendee when only a headcount is known (seated conference
# space including circulation). Shared by both venue proxy paths so they reconcile.
_VENUE_M2_PER_ATTENDEE = 2.0


def _venue_kwh_intensity() -> float:
    """kWh/m2/day for an active event day, from emission_factors.json.

    Sourced entry (not a code constant) so the derivation from the kg CO2e/m2/day
    proxy and the global-average grid factor is auditable alongside the factors.
    """
    return (
        EF["venue_energy"]
        .get("proxy_kwh_intensity", {})
        .get("conference_centre_kwh_per_m2_day", {})
        .get("factor", 6.0)
    )


def estimate_venue_kwh(venue_energy, attendees: int, event_days: int) -> float:
    """Electricity consumption (kWh) implied by a venue-energy input.

    Single source for the kWh derivation shared by _venue_energy_emissions and by
    financial back-calculations: actual kWh when provided, else area proxy, else
    attendee proxy.
    """
    intensity = _venue_kwh_intensity()
    if venue_energy is not None:
        if venue_energy.kwh_consumed is not None:
            return venue_energy.kwh_consumed
        if venue_energy.venue_area_m2 is not None:
            return venue_energy.venue_area_m2 * event_days * intensity
    return attendees * _VENUE_M2_PER_ATTENDEE * event_days * intensity


def _residual_mix_uplift() -> float:
    """Ratio between a grid's residual mix and its published location factor.

    Sourced (not a code constant) so the derivation and its documented limitations
    travel with the number in emission_factors.json.
    """
    return (
        EF["venue_energy"]
        .get("residual_mix", {})
        .get("global_uplift_on_location_factor", {})
        .get("factor", 1.43)
    )


def residual_mix_factor(grid_ef: float) -> float:
    """Residual-mix emission factor (kg CO2e/kWh) for a grid whose location factor is ``grid_ef``.

    Under the GHG Protocol Scope 2 Guidance, a market-based figure may only zero out
    the share of electricity backed by a contractual instrument; the *remainder* must
    be priced at the residual mix — what is left of the grid once everyone else's
    instrument-backed clean output has been claimed — not at the (cleaner) published
    grid average.
    """
    return grid_ef * _residual_mix_uplift()


class VenueEnergyResult(NamedTuple):
    """Venue electricity outcome, carrying both Scope 2 reporting bases.

    ``total_kg`` is the headline figure (market basis when an instrument backs the
    renewable claim, location basis otherwise). ``location_kg``/``market_kg`` are the
    dual-reporting pair; on the proxy path (no venue input) they both equal the total,
    because a kg CO2e/m2/day proxy carries no renewable claim to substantiate.
    """

    total_kg: float
    scope1_kg: float
    location_kg: float
    market_kg: float
    instrument_backed: bool
    notes: dict


def _venue_energy_emissions(
    venue_energy, attendees: int, event_days: int, physical_attendees: Optional[int] = None
) -> VenueEnergyResult:
    """Venue electricity emissions with both Scope 2 bases.

    ``physical_attendees`` sizes the floor-area proxies; a metered kWh reading is an
    actual and is never netted.
    """
    notes = {}
    scope1_kg = 0.0
    on_site = attendees if physical_attendees is None else physical_attendees

    if venue_energy is None:
        proxy_area = on_site * _VENUE_M2_PER_ATTENDEE
        proxy_factor = EF["venue_energy"]["proxy_factors"]["conference_centre_per_m2_day"]
        total_kg = proxy_area * event_days * proxy_factor
        notes["venue"] = (
            f"Proxy: {proxy_area}m2 at {proxy_factor} kg CO2e/m2/day"
            f"{_netting_note(on_site, attendees)}"
        )
        notes["venue_basis"] = "area_intensity_proxy"
        return VenueEnergyResult(total_kg, scope1_kg, total_kg, total_kg, False, notes)

    grid_key = venue_energy.grid_region.value
    grid_ef = EF["venue_energy"]["grids"].get(grid_key, EF["venue_energy"]["grids"]["global_average"])["factor"]

    kwh = estimate_venue_kwh(venue_energy, on_site, event_days)
    intensity = _venue_kwh_intensity()
    if venue_energy.kwh_consumed is not None:
        notes["venue"] = f"Actual kWh: {kwh:.0f}"
        notes["venue_basis"] = "measured_kwh"
    elif venue_energy.venue_area_m2 is not None:
        notes["venue"] = f"Proxy kWh from area: {kwh:.0f} ({intensity} kWh/m2/day)"
        notes["venue_basis"] = "area_kwh_proxy"
    else:
        notes["venue"] = (
            f"Proxy kWh from attendees: {kwh:.0f} "
            f"({_VENUE_M2_PER_ATTENDEE}m2/attendee at {intensity} kWh/m2/day)"
        )
        notes["venue"] += _netting_note(on_site, attendees)
        notes["venue_basis"] = "attendee_kwh_proxy"

    renewable_pct = venue_energy.renewable_pct
    instrument = getattr(venue_energy, "renewable_instrument", RenewableInstrument.NONE)
    instrument_value = getattr(instrument, "value", instrument) or "none"

    # Location basis: every kWh at the published grid factor, no renewable discount.
    location_kg = kwh * grid_ef

    # Market basis: only an instrument-backed share may be zeroed, and only the
    # remainder is repriced at the residual mix. A renewable percentage with no
    # instrument behind it is an unsubstantiated claim and earns nothing.
    instrument_backed = instrument_value != "none" and renewable_pct > 0
    if instrument_backed:
        market_kg = kwh * (1 - renewable_pct / 100) * residual_mix_factor(grid_ef)
    else:
        market_kg = location_kg

    total_kg = market_kg if instrument_backed else location_kg

    if renewable_pct > 0:
        if instrument_backed:
            notes["venue"] += (
                f" ({renewable_pct}% renewable via {instrument_value}, grid: {grid_key})"
            )
        else:
            notes["venue"] += (
                f" ({renewable_pct}% renewable claimed with no contractual instrument, "
                f"so not deducted; grid: {grid_key})"
            )

    return VenueEnergyResult(
        total_kg, scope1_kg, location_kg, market_kg, instrument_backed, notes
    )


def _accommodation_emissions(
    accom, attendees: int, event_days: int, physical_attendees: Optional[int] = None
) -> tuple[float, dict]:
    notes = {}
    on_site = attendees if physical_attendees is None else physical_attendees

    if accom is None:
        room_nights = (on_site * 0.8 / 1.5) * event_days
        ef = EF["accommodation"]["standard_hotel"]["factor"]
        total_kg = room_nights * ef
        notes["accommodation"] = (
            f"Proxy: 80% attendees, standard hotel, {room_nights:.0f} room-nights"
            f"{_netting_note(on_site, attendees)}"
        )
        return total_kg, notes

    ef_key = accom.accommodation_type.value
    ef = EF["accommodation"].get(ef_key, EF["accommodation"]["standard_hotel"])["factor"]
    total_kg = accom.room_nights * ef
    notes["accommodation"] = f"{accom.room_nights} room-nights x {ef} kg CO2e ({ef_key})"

    return total_kg, notes


def _catering_emissions(
    catering, attendees: int, event_days: int, physical_attendees: Optional[int] = None
) -> tuple[float, dict]:
    notes = {}
    on_site = attendees if physical_attendees is None else physical_attendees

    if catering is None:
        meals = on_site * event_days * 2
        ef = EF["catering"]["mixed_buffet"]["factor"]
        beverage_ef = EF["catering"]["beverages_per_person_day"]["factor"]
        total_kg = meals * ef + on_site * event_days * beverage_ef
        notes["catering"] = (
            f"Proxy: {meals} mixed meals + beverages{_netting_note(on_site, attendees)}"
        )
        return total_kg, notes

    ef_key = catering.catering_type.value
    ef = EF["catering"].get(ef_key, EF["catering"]["mixed_buffet"])["factor"]
    total_kg = catering.meals * ef

    if catering.include_beverages:
        bev_kg = attendees * event_days * EF["catering"]["beverages_per_person_day"]["factor"]
        total_kg += bev_kg

    if catering.include_alcohol:
        # Estimate: 2 drinks per attendee per day average, using JSON factors
        alcohol_data = EF["catering"]["alcohol"]
        beer_ef = alcohol_data.get("beer_per_serving", {}).get("factor", 0.55)
        spirits_ef = alcohol_data.get("spirits_per_serving", {}).get("factor", 0.35)
        avg_drink_ef = (beer_ef + spirits_ef) / 2
        alcohol_kg = attendees * event_days * 2 * avg_drink_ef
        total_kg += alcohol_kg
        notes["alcohol"] = f"Estimated {attendees * event_days * 2} alcoholic drinks"

    if catering.coffee_tea_cups > 0:
        coffee_ef = EF["catering"].get("coffee_tea_per_cup", {}).get("factor", 0.06)
        total_kg += catering.coffee_tea_cups * coffee_ef

    notes["catering"] = f"{catering.meals} {catering.catering_type.value} meals"
    return total_kg, notes


def _waste_emissions(
    waste, attendees: int, event_days: int, physical_attendees: Optional[int] = None
) -> tuple[float, dict]:
    notes = {}
    on_site = attendees if physical_attendees is None else physical_attendees

    if waste is None:
        # Printed handouts are a one-off per attendee; general waste accrues per day,
        # matching every other proxy in the engine.
        total_kg = (
            on_site * 0.5 * EF["materials_waste"]["paper_cardboard"]["factor"]
            + on_site * 0.3 * event_days * EF["materials_waste"]["general_landfill"]["factor"]
        )
        notes["waste"] = (
            "Proxy: 0.5kg printed per attendee + 0.3kg general waste per attendee per day"
            f"{_netting_note(on_site, attendees)}"
        )
        return total_kg, notes

    total_kg = (
        waste.general_waste_kg * EF["materials_waste"]["general_landfill"]["factor"]
        + waste.recycled_kg * EF["materials_waste"]["recycled_mixed"]["factor"]
        + waste.composted_kg * EF["materials_waste"]["composted_food"]["factor"]
        + waste.exhibition_booths_m2 * EF["materials_waste"]["exhibition_booth_per_m2"]["factor"]
    )

    # Weighed waste already contains the printed paper, so the per-attendee printed
    # proxy would double count it. Unset (None) means "decide from the data"; an
    # explicit True/False from the user is always honored.
    measured_weights = waste.general_waste_kg > 0 or waste.recycled_kg > 0
    include_printed = (
        waste.printed_materials_per_attendee
        if waste.printed_materials_per_attendee is not None
        else not measured_weights
    )

    if include_printed:
        total_kg += attendees * EF["materials_waste"]["printed_materials_per_attendee"]["factor"]
        notes["waste"] = "Actual waste data provided; printed-materials proxy added per attendee"
    elif measured_weights:
        notes["waste"] = (
            "Actual waste data provided; printed-materials proxy omitted "
            "(printed paper is already inside the measured waste weights)"
        )
    else:
        notes["waste"] = "Actual waste data provided; printed-materials proxy excluded"

    return total_kg, notes


def _equipment_emissions(
    equipment, event_days: int, venue_metered: bool = False
) -> tuple[float, float, float, float, dict]:
    """Returns total kg, scope1 kg (generators), scope2 kg (electricity), scope3 kg (stage+freight), notes.

    ``venue_metered`` says the venue supplied an actual kWh reading. That meter already
    covers the lighting/sound/LED/projector loads plugged into the venue supply, so the
    equipment electricity lines are skipped to avoid double counting. Non-electricity
    lines (generator fuel, stage build, freight) are unaffected.
    """
    notes = {}
    if equipment is None:
        return 0.0, 0.0, 0.0, 0.0, notes

    eq = EF.get("equipment", {})
    scope1_kg = 0.0
    scope2_kg = 0.0
    scope3_kg = 0.0

    # Stage
    stage_kg = equipment.stage_m2 * event_days * eq.get("stage_per_m2_per_day", {}).get("factor", 0.5)

    # Electricity lines (Scope 2): lighting, sound, LED screens, projectors.
    electricity_kg = (
        equipment.lighting_days * eq.get("lighting_rig_per_day", {}).get("factor", 45.0)
        + equipment.sound_system_days * eq.get("sound_system_per_day", {}).get("factor", 25.0)
        + equipment.led_screen_m2 * event_days * eq.get("led_screen_per_m2_per_day", {}).get("factor", 2.5)
        + equipment.projectors * event_days * eq.get("projector_per_day", {}).get("factor", 3.8)
    )
    if not venue_metered:
        scope2_kg += electricity_kg

    # Generator (Scope 1 - direct combustion)
    gen_kg = equipment.generator_hours * eq.get("generator_diesel_per_hour", {}).get("factor", 8.5)
    scope1_kg += gen_kg

    # Freight (Scope 3 — upstream transport) and stage build (Scope 3 — purchased materials)
    freight_kg = equipment.freight_tonne_km * eq.get("freight_truck_per_km", {}).get("factor", 0.107)
    scope3_kg = stage_kg + freight_kg

    total_kg = scope1_kg + scope2_kg + scope3_kg

    if total_kg > 0:
        notes["equipment"] = f"Stage {equipment.stage_m2}m2, lighting {equipment.lighting_days}d, sound {equipment.sound_system_days}d, LED {equipment.led_screen_m2}m2, gen {equipment.generator_hours}h"
    if venue_metered and electricity_kg > 0:
        notes["equipment_electricity"] = (
            f"Equipment electricity (lighting, sound, LED, projectors, {electricity_kg:.0f} kg CO2e) "
            "excluded — already included in the metered venue supply."
        )
    elif scope2_kg > 0:
        notes["equipment_electricity"] = (
            "Equipment electricity uses global-average grid factors, not the venue grid."
        )

    return total_kg, scope1_kg, scope2_kg, scope3_kg, notes


def _digital_emissions(digital, attendees: int, event_days: int, event_type: str) -> tuple[float, dict]:
    """Digital/virtual emissions: streaming, livestream production, event app, email.

    All Scope 3. Proxy fires only for virtual/hybrid events with no digital input
    (100% / 30% of attendees streaming 6h per day respectively).
    """
    notes = {}
    dig = EF.get("digital", {})
    stream_ef = dig.get("virtual_attendee_per_hour", {}).get("factor", 0.036)

    if digital is None:
        if event_type == "virtual_event":
            virtual_attendees = attendees
        elif event_type == "hybrid_event":
            virtual_attendees = round(attendees * 0.3)
        else:
            return 0.0, notes
        total_kg = virtual_attendees * 6.0 * event_days * stream_ef
        notes["digital"] = f"Proxy: {virtual_attendees} virtual attendees streaming 6h/day"
        return total_kg, notes

    total_kg = digital.virtual_attendees * digital.streaming_hours_per_day * event_days * stream_ef

    if digital.livestream_production_hours > 0:
        # Factor is per hour per 1000 viewers (encoding + CDN delivery).
        production_ef = dig.get("livestream_per_hour", {}).get("factor", 4.5)
        total_kg += digital.livestream_production_hours * production_ef * max(digital.virtual_attendees, 1) / 1000

    if digital.event_app_users > 0:
        total_kg += digital.event_app_users * event_days * dig.get("event_app_per_user", {}).get("factor", 0.008)

    if digital.emails_sent > 0:
        total_kg += digital.emails_sent / 1000 * dig.get("email_campaign_per_1000", {}).get("factor", 0.6)

    if total_kg > 0:
        parts = [f"{digital.virtual_attendees} virtual attendees x {digital.streaming_hours_per_day:g}h/day"]
        if digital.event_app_users:
            parts.append(f"{digital.event_app_users} app users")
        if digital.emails_sent:
            parts.append(f"{digital.emails_sent} emails")
        notes["digital"] = ", ".join(parts)

    return total_kg, notes


def _swag_emissions(swag, attendees: int) -> tuple[float, dict]:
    """Returns swag/merchandise kg CO2e and notes."""
    notes = {}
    if swag is None:
        return 0.0, notes

    sw = EF.get("swag_merchandise", {})
    total_kg = 0.0

    # T-shirts
    if swag.tshirts > 0:
        tshirt_key = {
            "cotton": "cotton_tshirt",
            "organic": "organic_cotton_tshirt",
            "recycled": "recycled_tshirt",
        }.get(swag.tshirt_type, "cotton_tshirt")
        total_kg += swag.tshirts * sw.get(tshirt_key, {}).get("factor", 8.0)

    # Tote bags
    total_kg += swag.tote_bags * sw.get("tote_bag_cotton", {}).get("factor", 3.8)

    # Lanyards
    total_kg += swag.lanyards * sw.get("lanyard", {}).get("factor", 0.08)

    # Badges
    badge_key = "name_badge_recycled" if swag.badge_type == "recycled" else "name_badge_plastic"
    total_kg += swag.badges * sw.get(badge_key, {}).get("factor", 0.05)

    # Notebooks
    total_kg += swag.notebooks * sw.get("notebook_pen_set", {}).get("factor", 0.45)

    # Water bottles
    total_kg += swag.water_bottles * sw.get("reusable_water_bottle", {}).get("factor", 1.2)

    if total_kg > 0:
        notes["swag"] = f"{swag.tshirts} tshirts ({swag.tshirt_type}), {swag.tote_bags} totes, {swag.lanyards} lanyards, {swag.badges} badges, {swag.notebooks} notebooks, {swag.water_bottles} bottles"

    return total_kg, notes


# Benchmark bands keyed per *whole-event* attendee (not per attendee-day). For these
# event types the comparison must use the per-attendee value, otherwise a multi-day
# event is divided by days and looks artificially better than the band.
_PER_ATTENDEE_BENCHMARK_TYPES = {"gala_dinner", "sporting_event", "wedding"}


def get_benchmark_comparison(
    event_type: str,
    per_attendee_day: float,
    per_attendee: Optional[float] = None,
) -> Optional[BenchmarkComparison]:
    """Compare against industry benchmarks.

    Most bands are per attendee-day; gala/sporting/wedding bands are per whole-event
    attendee, so we compare those against ``per_attendee`` when it is provided.
    """
    benchmarks = EF.get("benchmarks", {})
    type_map = {
        "conference": "conference_per_attendee_day",
        "trade_show": "trade_show_per_attendee_day",
        "gala_dinner": "gala_dinner_per_attendee",
        "music_festival": "music_festival_per_attendee_day",
        "corporate_meeting": "corporate_meeting_per_attendee_day",
        "sporting_event": "sporting_event_per_attendee",
        "virtual_event": "virtual_event_per_attendee_day",
        "hybrid_event": "hybrid_event_per_attendee_day",
        "wedding": "wedding_per_guest",
    }
    bm_key = type_map.get(event_type)
    if not bm_key or bm_key not in benchmarks:
        return None

    # Pick the comparison basis that matches the band's unit.
    compare_value = per_attendee_day
    if event_type in _PER_ATTENDEE_BENCHMARK_TYPES and per_attendee is not None:
        compare_value = per_attendee
    per_attendee_day = compare_value

    bm = benchmarks[bm_key]
    typical = bm["typical"]
    best = bm["best_practice"]

    if per_attendee_day <= best:
        rank = "best practice"
    elif per_attendee_day <= (typical + best) / 2:
        rank = "below average"
    elif per_attendee_day <= typical:
        rank = "average"
    else:
        rank = "above average"

    gap = ((per_attendee_day - best) / best * 100) if best > 0 else 0

    return BenchmarkComparison(
        event_type=event_type,
        your_per_attendee_day=round(per_attendee_day, 4),
        industry_typical=typical,
        industry_best_practice=best,
        percentile_rank=rank,
        gap_to_best_practice_pct=round(gap, 1),
    )


def _boundary_note(venue_owned: bool, equipment_owned: bool) -> str:
    """Disclosure of the organizational boundary each energy line was routed under."""
    parts = []
    if venue_owned:
        parts.append("venue electricity as Scope 2 (operational control held: owned/operated)")
    else:
        parts.append("venue electricity as Scope 3 (operational control not held: contracted)")
    if equipment_owned:
        parts.append(
            "equipment generator fuel as Scope 1 and equipment electricity as Scope 2 "
            "(operational control held: owned/operated)"
        )
    else:
        parts.append("equipment, including generator fuel, as Scope 3 (contracted)")
    return (
        "GHG Protocol control approach — reporting "
        + "; ".join(parts)
        + ". The emissions are counted in the total either way; only the scope they land in changes."
    )


def _scope2_reporting_note(
    venue_energy,
    venue: VenueEnergyResult,
    *,
    venue_owned: bool,
    location_kg: float,
    market_kg: float,
) -> dict:
    """Dual Scope 2 disclosure (GHG Protocol Scope 2 Guidance), persisted in assumptions.

    Doubles as the persistence vehicle for the two figures: ``assumptions`` is JSONB
    and already round-trips through the DB, so stored scenarios rehydrate both bases
    without a schema migration (see scenario_serializer.scope2_dual_bases).
    """
    instrument = getattr(venue_energy, "renewable_instrument", RenewableInstrument.NONE)
    instrument_value = getattr(instrument, "value", instrument) or "none"
    renewable_pct = getattr(venue_energy, "renewable_pct", 0.0) or 0.0
    grid_key = (
        venue_energy.grid_region.value if venue_energy is not None else "not applicable"
    )

    if venue.instrument_backed:
        uplift = _residual_mix_uplift()
        basis_text = (
            f"{renewable_pct:g}% of venue electricity is backed by a "
            f"'{instrument_value}' instrument and is zeroed on the market basis; the "
            f"unclaimed remainder is priced at the residual mix ({uplift}x the "
            f"{grid_key} grid factor), not at the grid average."
        )
    else:
        basis_text = (
            "No contractual instrument was recorded, so the market basis equals the "
            "location basis."
        )
        if renewable_pct > 0:
            basis_text += (
                f" The {renewable_pct:g}% renewable share claimed for this venue is "
                "unsubstantiated and earns no market-based reduction."
            )

    if venue_energy is None and venue.location_kg == 0.0:
        # Virtual event with no declared venue: there is no electricity line to
        # report on either basis, so say that rather than quoting two zeros.
        note = (
            "No venue energy is in scope (no venue declared), so neither a "
            "location-based nor a market-based Scope 2 figure is reported."
        )
    elif venue_owned:
        note = (
            "Scope 2 reported on both bases per the GHG Protocol Scope 2 Guidance. "
            f"Location-based {venue.location_kg / 1000:.4f} tCO2e, market-based "
            f"{venue.market_kg / 1000:.4f} tCO2e for the venue electricity line. "
            f"The headline total uses the "
            f"{'market' if venue.instrument_backed else 'location'}-based figure. "
            + basis_text
        )
    else:
        note = (
            "The venue is contracted, so its electricity is reported as Scope 3 and no "
            "Scope 2 figures are reported. For disclosure, that electricity line is "
            f"{venue.location_kg / 1000:.4f} tCO2e on a location basis and "
            f"{venue.market_kg / 1000:.4f} tCO2e on a market basis. " + basis_text
        )

    return {
        "location_based_tco2e": round(location_kg / 1000, 4),
        "market_based_tco2e": round(market_kg / 1000, 4),
        "headline_basis": "market_based" if venue.instrument_backed else "location_based",
        "renewable_instrument": instrument_value,
        "note": note,
    }


def calculate_scenario(scenario: EventScenarioInput) -> ScenarioResult:
    """Main entry point: calculate all emissions for a scenario."""
    attendees = scenario.attendees
    days = scenario.event_days
    assumptions = {}

    # Scope tracking
    scope1_total = 0.0
    scope2_total = 0.0
    scope3_total = 0.0

    # Fully virtual events get NO physical proxies — without this gate the travel
    # proxy alone (70% long-haul flights) would dwarf a virtual event's real
    # footprint. Explicitly provided inputs (e.g. a studio venue) are still honored.
    is_virtual = scenario.event_type.value == "virtual_event"

    # People actually in the building. On a hybrid event this nets out an explicitly
    # declared remote cohort; everywhere else it is the full headcount. One base for the
    # travel reconciliation AND every physical-presence proxy, so the categories cannot
    # disagree about how many people were on site. Only a *declared* cohort counts — the
    # hybrid digital proxy (30% of attendees) is itself an assumption and must not
    # silently shrink any base.
    physical_attendees = physical_attendee_count(scenario)
    remote_attendees = attendees - physical_attendees

    # Travel (Scope 3)
    if is_virtual and not scenario.travel_segments:
        travel_kg, t_notes = 0.0, {"travel": "Virtual event: no physical travel assumed"}
    else:
        # On a virtual event the headcount is an audience that stays home: any supplied
        # segment (a crew flying to the studio) counts as-is, with no proxy remainder.
        travel_kg, t_notes = _travel_emissions(
            scenario.travel_segments,
            attendees,
            reconcile=not is_virtual,
            remote_attendees=remote_attendees,
        )
        if is_virtual and scenario.travel_segments:
            t_notes["travel"] = (
                "Virtual event: only the travel segments supplied are counted; "
                "the remote audience is not assumed to travel"
            )
    scope3_total += travel_kg

    # Venue energy. Scope 2 (purchased electricity) only when the organizer holds
    # operational control of the venue; a hired venue is a purchased service (Scope 3).
    if is_virtual and scenario.venue_energy is None:
        venue = VenueEnergyResult(
            0.0, 0.0, 0.0, 0.0, False,
            {
                "venue": "Virtual event: no physical venue assumed",
                "venue_basis": "not applicable (virtual event)",
            },
        )
    else:
        venue = _venue_energy_emissions(
            scenario.venue_energy, attendees, days, physical_attendees
        )
    energy_kg, venue_s1_kg, e_notes = venue.total_kg, venue.scope1_kg, venue.notes

    venue_owned = _holds_control(scenario.venue_energy)
    if venue_owned:
        scope2_total += energy_kg
        scope1_total += venue_s1_kg
        scope2_location_kg = venue.location_kg
        scope2_market_kg = venue.market_kg
    else:
        scope3_total += energy_kg + venue_s1_kg
        scope2_location_kg = 0.0
        scope2_market_kg = 0.0

    # Accommodation (Scope 3)
    if is_virtual and scenario.accommodation is None:
        accom_kg, a_notes = 0.0, {}
    else:
        accom_kg, a_notes = _accommodation_emissions(
            scenario.accommodation, attendees, days, physical_attendees
        )
    scope3_total += accom_kg

    # Catering (Scope 3)
    if is_virtual and scenario.catering is None:
        catering_kg, c_notes = 0.0, {}
    else:
        catering_kg, c_notes = _catering_emissions(
            scenario.catering, attendees, days, physical_attendees
        )
    scope3_total += catering_kg

    # Waste (Scope 3)
    if is_virtual and scenario.waste is None:
        waste_kg, w_notes = 0.0, {}
    else:
        waste_kg, w_notes = _waste_emissions(scenario.waste, attendees, days, physical_attendees)
    scope3_total += waste_kg

    # Equipment (Scope 1 generators + Scope 2 electricity + Scope 3 stage/freight
    # when owned/operated; wholly Scope 3 when the rig and genset are contracted).
    # A venue meter reading already covers the equipment on the venue supply.
    venue_metered = scenario.venue_energy is not None and scenario.venue_energy.kwh_consumed is not None
    equip_kg, equip_s1, equip_s2, equip_s3, eq_notes = _equipment_emissions(
        scenario.equipment, days, venue_metered=venue_metered
    )
    equipment_owned = _holds_control(scenario.equipment)
    if equipment_owned:
        scope1_total += equip_s1
        scope2_total += equip_s2
        scope3_total += equip_s3
        # Equipment electricity carries no contractual instrument, so it prices the
        # same on both bases and simply adds to each.
        scope2_location_kg += equip_s2
        scope2_market_kg += equip_s2
    else:
        scope3_total += equip_kg

    # Swag (Scope 3)
    swag_kg, sw_notes = _swag_emissions(scenario.swag, attendees)
    scope3_total += swag_kg

    # Digital / virtual (Scope 3)
    digital_kg, d_notes = _digital_emissions(scenario.digital, attendees, days, scenario.event_type.value)
    scope3_total += digital_kg

    assumptions.update(t_notes)
    assumptions.update(e_notes)
    assumptions.update(a_notes)
    assumptions.update(c_notes)
    assumptions.update(w_notes)
    assumptions.update(eq_notes)
    assumptions.update(sw_notes)
    assumptions.update(d_notes)

    assumptions["boundary"] = _boundary_note(venue_owned, equipment_owned)
    assumptions["scope2_reporting"] = _scope2_reporting_note(
        scenario.venue_energy,
        venue,
        venue_owned=venue_owned,
        location_kg=scope2_location_kg,
        market_kg=scope2_market_kg,
    )

    total_kg = travel_kg + energy_kg + accom_kg + catering_kg + waste_kg + equip_kg + swag_kg + digital_kg
    total_tco2e = total_kg / 1000
    per_attendee = total_tco2e / attendees if attendees > 0 else 0
    per_attendee_day = per_attendee / days if days > 0 else per_attendee

    # Data quality tier. A populated venue_energy (even grid + renewable only) counts
    # as real input. The engine can award "modelled" (Tier 3, everything from proxies)
    # and "partly_primary" (Tier 2, at least one measured input) only — "primary"
    # (Tier 1) requires attached supporting evidence, which the engine has no view of.
    # Filling in every advanced-mode form proves completeness, not provenance, so a
    # fully populated scenario still lands on Tier 2. See
    # app.services.scenario_serializer.DATA_QUALITY_TIERS for the canonical vocabulary.
    core_provided = {
        "travel": bool(scenario.travel_segments),
        "venue_energy": scenario.venue_energy is not None,
        "accommodation": scenario.accommodation is not None,
        "catering": scenario.catering is not None,
        "waste": scenario.waste is not None,
    }
    has_actual_data = (
        any(core_provided.values())
        or scenario.equipment is not None
        or scenario.swag is not None
        or scenario.digital is not None
    )
    all_core_provided = all(core_provided.values())

    # Per-category primary-vs-proxy disclosure (NZCE/TRACE expect this). Persisted in
    # assumptions so it flows into every export's Assumptions section automatically.
    def _quality(provided: bool, gated: bool = False, optional: bool = False) -> str:
        if provided:
            return "actual"
        if gated:
            return "not applicable (virtual event)"
        return "not provided" if optional else "proxy"

    # Segments that cover only part of the headcount are a mix of measured and proxy
    # data, so the travel category is flagged "partial" (a per-category coverage flag,
    # distinct from the scenario-level tier assigned below).
    travel_quality = "partial" if "travel_coverage" in t_notes else _quality(
        core_provided["travel"], gated=is_virtual
    )

    assumptions["category_data_quality"] = {
        "travel": travel_quality,
        "venue_energy": _quality(core_provided["venue_energy"], gated=is_virtual),
        "accommodation": _quality(core_provided["accommodation"], gated=is_virtual),
        "catering": _quality(core_provided["catering"], gated=is_virtual),
        "waste": _quality(core_provided["waste"], gated=is_virtual),
        "equipment": _quality(scenario.equipment is not None, optional=True),
        "swag": _quality(scenario.swag is not None, optional=True),
        "digital": (
            "actual" if scenario.digital is not None
            else ("proxy" if scenario.event_type.value in ("virtual_event", "hybrid_event") else "not provided")
        ),
    }

    quality = "partly_primary" if has_actual_data else "modelled"

    if scenario.mode == ScenarioMode.ADVANCED and not all_core_provided:
        missing = [k for k, v in core_provided.items() if not v]
        assumptions["data_quality"] = (
            "Advanced mode: some categories still use proxy estimates "
            f"({', '.join(missing)})."
        )

    scopes = ScopeBreakdown(
        scope1_tco2e=round(scope1_total / 1000, 4),
        scope2_tco2e=round(scope2_total / 1000, 4),
        scope3_tco2e=round(scope3_total / 1000, 4),
        scope2_location_tco2e=round(scope2_location_kg / 1000, 4),
        scope2_market_tco2e=round(scope2_market_kg / 1000, 4),
    )

    emissions = EmissionBreakdown(
        travel_tco2e=round(travel_kg / 1000, 4),
        venue_energy_tco2e=round(energy_kg / 1000, 4),
        accommodation_tco2e=round(accom_kg / 1000, 4),
        catering_tco2e=round(catering_kg / 1000, 4),
        materials_waste_tco2e=round(waste_kg / 1000, 4),
        equipment_tco2e=round(equip_kg / 1000, 4),
        swag_tco2e=round(swag_kg / 1000, 4),
        digital_tco2e=round(digital_kg / 1000, 4),
        total_tco2e=round(total_tco2e, 4),
        per_attendee_tco2e=round(per_attendee, 4),
        per_attendee_day_tco2e=round(per_attendee_day, 4),
        data_quality=quality,
        scopes=scopes,
    )

    # Benchmark
    benchmark = get_benchmark_comparison(scenario.event_type.value, per_attendee_day, per_attendee)

    return ScenarioResult(
        name=scenario.name,
        event_name=scenario.event_name,
        location=scenario.location,
        event_type=scenario.event_type.value,
        attendees=attendees,
        event_days=days,
        emissions=emissions,
        benchmark=benchmark,
        assumptions=assumptions,
        created_at=utcnow().isoformat(),
    )


def build_factors_snapshot(scenario: EventScenarioInput) -> dict:
    """Capture the emission factor values used for this scenario calculation."""
    grid_key = "global_average"
    if scenario.venue_energy and scenario.venue_energy.grid_region:
        grid_key = scenario.venue_energy.grid_region.value
    grid_ef = EF["venue_energy"]["grids"].get(grid_key, EF["venue_energy"]["grids"]["global_average"])["factor"]

    accom_type = "standard_hotel"
    if scenario.accommodation:
        accom_type = scenario.accommodation.accommodation_type.value
    accom_ef = EF["accommodation"].get(accom_type, EF["accommodation"]["standard_hotel"])["factor"]

    catering_type = "mixed_buffet"
    if scenario.catering:
        catering_type = scenario.catering.catering_type.value
    catering_ef = EF["catering"].get(catering_type, EF["catering"]["mixed_buffet"])["factor"]

    return {
        "travel_long_haul_economy_kg_per_pkm": EF["travel"]["long_haul_flight"]["economy"],
        "travel_short_haul_economy_kg_per_pkm": EF["travel"]["short_haul_flight"]["economy"],
        "travel_short_haul_business_kg_per_pkm": EF["travel"]["short_haul_flight"]["business"],
        "travel_car_petrol_kg_per_pkm": EF["travel"]["car_petrol"]["factor"],
        "venue_grid_kg_per_kwh": grid_ef,
        "venue_grid_region": grid_key,
        # Prices the unclaimed remainder on the Scope 2 market basis; recorded even
        # when unused so a reader can see what a market-based claim would have cost.
        "venue_residual_mix_kg_per_kwh": round(residual_mix_factor(grid_ef), 4),
        "accommodation_kg_per_room_night": accom_ef,
        "accommodation_type": accom_type,
        "catering_kg_per_meal": catering_ef,
        "catering_type": catering_type,
        "waste_landfill_kg_per_kg": EF["materials_waste"]["general_landfill"]["factor"],
        "ef_version": EF.get("version", "unknown"),
        "captured_at": utcnow().isoformat(),
    }


def get_reduction_suggestions(
    result: ScenarioResult,
    target_pct: float = 30.0,
    catering_type: Optional[str] = None,
    equipment_input: Optional[dict] = None,
) -> list[dict]:
    """Generate ranked reduction suggestions as a realistic portfolio.

    Each lever's saving is drawn from the remaining (un-claimed) emissions in its
    category and clamped to what is left, so the suggested reductions can never sum
    to more than the category — or the event — total. Carbon offsets are returned as
    a separate neutralization entry (``is_neutralization=True``) appended after the
    ranked reductions and applied to the *residual* after reductions, so buying
    credits never ranks among (or inflates) the actual reductions.
    """
    emissions = result.emissions
    attendees = result.attendees
    days = result.event_days

    # Remaining reducible budget per category (tCO2e).
    remaining = {
        "travel": max(0.0, emissions.travel_tco2e),
        "catering": max(0.0, emissions.catering_tco2e),
        "energy": max(0.0, emissions.venue_energy_tco2e),
        "equipment": max(0.0, emissions.equipment_tco2e),
        "accommodation": max(0.0, emissions.accommodation_tco2e),
        "waste": max(0.0, emissions.materials_waste_tco2e),
        "swag": max(0.0, emissions.swag_tco2e),
        "digital": max(0.0, emissions.digital_tco2e),
    }

    reductions: list[dict] = []

    def add(action, label, category, raw_saved, cost, difficulty, scope):
        cap = remaining.get(category)
        saved = raw_saved
        if cap is not None:
            saved = min(raw_saved, cap)
            remaining[category] = max(0.0, cap - saved)
        if saved <= 0:
            return
        reductions.append({
            "action": action,
            "label": label,
            "co2e_saved_tco2e": round(saved, 3),
            "estimated_cost_usd": round(cost, 0),
            "category": category,
            "difficulty": difficulty,
            "scope": scope,
        })

    # Travel — levers share the (clamped) travel budget, so they can't sum past 100%.
    if remaining["travel"] > 0:
        add("enable_hybrid", "Enable hybrid/virtual attendance (30% remote)",
            "travel", emissions.travel_tco2e * 0.30, attendees * 0.3 * 30, "medium", 3)
        add("shift_to_rail", "Shift short-haul flights to rail (where <4h journey)",
            "travel", emissions.travel_tco2e * 0.15, -attendees * 0.2 * 15, "hard", 3)
        add("shuttle_bus", "Provide shuttle buses from airports/stations to venue",
            "travel", emissions.travel_tco2e * 0.05, attendees * 5, "easy", 3)

    # Catering — vegetarian and local/seasonal are mutually exclusive (take the bigger
    # lever). Skip the vegetarian switch entirely when the menu is already plant-based.
    if remaining["catering"] > 0:
        already_low = (catering_type or "") in {"vegetarian_meal", "vegan_meal", "local_organic"}
        if already_low:
            add("local_seasonal", "Source local and seasonal ingredients",
                "catering", emissions.catering_tco2e * 0.15, attendees * days * 2 * 1.5, "medium", 3)
        else:
            add("vegetarian_menu", "Switch to a fully vegetarian menu",
                "catering", emissions.catering_tco2e * 0.55, -attendees * days * 2 * 2.5, "easy", 3)

    # Renewable energy tariff zeroes purchased-electricity (market-based) emissions.
    if remaining["energy"] > 0:
        add("renewable_energy", "Switch venue to 100% renewable energy tariff",
            "energy", emissions.venue_energy_tco2e, attendees * days * 2, "easy", 2)

    # Equipment — the LED retrofit applies only to the lighting-electricity share,
    # never to the generators or freight also bundled in equipment_tco2e.
    if remaining["equipment"] > 0 and equipment_input:
        lighting_days = equipment_input.get("lighting_days") or 0
        lighting_ef = EF.get("equipment", {}).get("lighting_rig_per_day", {}).get("factor", 45.0)
        lighting_tco2e = lighting_days * lighting_ef / 1000
        if lighting_tco2e > 0:
            add("led_lighting", "Switch to LED lighting (40% lighting-energy reduction)",
                "equipment", lighting_tco2e * 0.40, 500 * days, "easy", 2)

    # Accommodation
    if remaining["accommodation"] > 0:
        add("eco_accommodation", "Choose green-certified hotels (eco-lodge / green mark)",
            "accommodation", emissions.accommodation_tco2e * 0.40, 0, "medium", 3)

    # Waste — digital materials + zero-waste both draw from the waste budget.
    if remaining["waste"] > 0:
        add("digital_materials", "Replace printed materials with digital (app/QR)",
            "waste", attendees * 0.00025, -attendees * 2.0, "easy", 3)
        add("zero_waste", "Zero-waste catering (compost + eliminate single-use)",
            "waste", attendees * 0.0008 * days, attendees * 1.5, "medium", 3)

    # Swag
    if remaining["swag"] > 0:
        add("sustainable_swag", "Switch to recycled materials or digital-only swag",
            "swag", emissions.swag_tco2e * 0.60, -attendees * 3, "easy", 3)

    # Rank reductions by impact.
    reductions.sort(key=lambda x: x["co2e_saved_tco2e"], reverse=True)

    # Neutralization (offsets) — applied to the residual AFTER reductions and kept out
    # of the reduction ranking. Buying credits is a cost, not an emission reduction.
    total_reduced = sum(s["co2e_saved_tco2e"] for s in reductions)
    residual = max(0.0, emissions.total_tco2e - total_reduced)
    offset_qty = round(residual * (target_pct / 100), 3)
    if offset_qty > 0:
        reductions.append({
            "action": "offset_residual",
            "label": "Neutralize residual emissions with Gold Standard credits (a cost, not a reduction)",
            "co2e_saved_tco2e": offset_qty,
            "estimated_cost_usd": round(offset_qty * _OFFSET_PRICE_USD, 0),
            "category": "offsets",
            "difficulty": "easy",
            "scope": "all",
            "is_neutralization": True,
        })

    return reductions
