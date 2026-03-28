"""
Deterministic emissions calculation engine.
Implements GHG Protocol Scope 1/2/3 methodology for events.
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.models.schemas import (
    EventScenarioInput, ScenarioResult, EmissionBreakdown, ScopeBreakdown,
    BenchmarkComparison, TravelMode, TravelClass, GridRegion, ScenarioMode
)

_DATA_DIR = Path(__file__).parent.parent / "data"

with open(_DATA_DIR / "emission_factors.json") as f:
    EF = json.load(f)


def _travel_emissions(segments, attendees: int) -> tuple[float, dict]:
    """Returns travel kg CO2e and assumption notes."""
    total_kg = 0.0
    notes = {}

    if not segments:
        # Proxy: assume 70% fly long-haul 2000km, 30% local 50km
        long_haul = attendees * 0.7 * 2000 * EF["travel"]["long_haul_flight"]["economy"]
        local = attendees * 0.3 * 50 * EF["travel"]["mrt_metro"]["factor"]
        total_kg = long_haul + local
        notes["travel"] = "Proxy: 70% long-haul flight 2000km economy, 30% local MRT 50km"
    else:
        for seg in segments:
            mode = seg.mode.value
            ef_data = EF["travel"].get(mode, {})
            if isinstance(ef_data, dict):
                if seg.travel_class == TravelClass.ECONOMY:
                    ef = ef_data.get("economy", ef_data.get("factor", 0.2))
                elif seg.travel_class == TravelClass.BUSINESS:
                    ef = ef_data.get("business", ef_data.get("factor", 0.2) * 2)
                else:
                    ef = ef_data.get("first", ef_data.get("factor", 0.2) * 3)
            else:
                ef = ef_data if isinstance(ef_data, (int, float)) else 0.1
            seg_kg = seg.attendees * seg.distance_km * ef
            total_kg += seg_kg

    return total_kg, notes


def _venue_energy_emissions(venue_energy, attendees: int, event_days: int) -> tuple[float, float, dict]:
    """Returns venue energy kg CO2e, scope1 kg (generators), notes."""
    notes = {}
    scope1_kg = 0.0

    if venue_energy is None:
        proxy_area = attendees * 2.0
        total_kg = proxy_area * event_days * EF["venue_energy"]["proxy_factors"]["conference_centre_per_m2_day"]
        notes["venue"] = f"Proxy: {proxy_area}m2 at 2.8 kg CO2e/m2/day"
        return total_kg, scope1_kg, notes

    grid_key = venue_energy.grid_region.value
    grid_ef = EF["venue_energy"]["grids"].get(grid_key, EF["venue_energy"]["grids"]["global_average"])["factor"]

    if venue_energy.kwh_consumed:
        kwh = venue_energy.kwh_consumed
        notes["venue"] = f"Actual kWh: {kwh:.0f}"
    elif venue_energy.venue_area_m2:
        kwh = venue_energy.venue_area_m2 * event_days * 30
        notes["venue"] = f"Proxy kWh from area: {kwh:.0f}"
    else:
        kwh = attendees * 2.0 * event_days * 30
        notes["venue"] = f"Proxy kWh from attendees: {kwh:.0f}"

    effective_ef = grid_ef * (1 - venue_energy.renewable_pct / 100)
    total_kg = kwh * effective_ef

    if venue_energy.renewable_pct > 0:
        notes["venue"] += f" ({venue_energy.renewable_pct}% renewable, grid: {grid_key})"

    return total_kg, scope1_kg, notes


def _accommodation_emissions(accom, attendees: int, event_days: int) -> tuple[float, dict]:
    notes = {}

    if accom is None:
        room_nights = (attendees * 0.8 / 1.5) * event_days
        ef = EF["accommodation"]["standard_hotel"]["factor"]
        total_kg = room_nights * ef
        notes["accommodation"] = f"Proxy: 80% attendees, standard hotel, {room_nights:.0f} room-nights"
        return total_kg, notes

    ef_key = accom.accommodation_type.value
    ef = EF["accommodation"].get(ef_key, EF["accommodation"]["standard_hotel"])["factor"]
    total_kg = accom.room_nights * ef
    notes["accommodation"] = f"{accom.room_nights} room-nights x {ef} kg CO2e ({ef_key})"

    return total_kg, notes


def _catering_emissions(catering, attendees: int, event_days: int) -> tuple[float, dict]:
    notes = {}

    if catering is None:
        meals = attendees * event_days * 2
        ef = EF["catering"]["mixed_buffet"]["factor"]
        beverage_ef = EF["catering"]["beverages_per_person_day"]["factor"]
        total_kg = meals * ef + attendees * event_days * beverage_ef
        notes["catering"] = f"Proxy: {meals} mixed meals + beverages"
        return total_kg, notes

    ef_key = catering.catering_type.value
    ef = EF["catering"].get(ef_key, EF["catering"]["mixed_buffet"])["factor"]
    total_kg = catering.meals * ef

    if catering.include_beverages:
        bev_kg = attendees * event_days * EF["catering"]["beverages_per_person_day"]["factor"]
        total_kg += bev_kg

    if catering.include_alcohol:
        # Estimate: 2 drinks per attendee per day average
        alcohol_kg = attendees * event_days * 2 * 0.45  # avg between beer and wine
        total_kg += alcohol_kg
        notes["alcohol"] = f"Estimated {attendees * event_days * 2} alcoholic drinks"

    if catering.coffee_tea_cups > 0:
        coffee_ef = EF["catering"].get("coffee_tea_per_cup", {}).get("factor", 0.06)
        total_kg += catering.coffee_tea_cups * coffee_ef

    notes["catering"] = f"{catering.meals} {catering.catering_type.value} meals"
    return total_kg, notes


def _waste_emissions(waste, attendees: int) -> tuple[float, dict]:
    notes = {}

    if waste is None:
        total_kg = (
            attendees * 0.5 * EF["materials_waste"]["paper_cardboard"]["factor"]
            + attendees * 0.3 * EF["materials_waste"]["general_landfill"]["factor"]
        )
        notes["waste"] = "Proxy: 0.5kg printed + 0.3kg general waste per attendee"
        return total_kg, notes

    total_kg = (
        waste.general_waste_kg * EF["materials_waste"]["general_landfill"]["factor"]
        + waste.recycled_kg * EF["materials_waste"]["recycled_mixed"]["factor"]
        + waste.composted_kg * EF["materials_waste"]["composted_food"]["factor"]
        + waste.exhibition_booths_m2 * EF["materials_waste"]["exhibition_booth_per_m2"]["factor"]
    )

    if waste.printed_materials_per_attendee:
        total_kg += attendees * EF["materials_waste"]["printed_materials_per_attendee"]["factor"]

    notes["waste"] = "Actual waste data provided"
    return total_kg, notes


def _equipment_emissions(equipment, event_days: int) -> tuple[float, float, float, dict]:
    """Returns total kg, scope1 kg (generators), scope2 kg (electricity-based), notes."""
    notes = {}
    if equipment is None:
        return 0.0, 0.0, 0.0, notes

    eq = EF.get("equipment", {})
    scope1_kg = 0.0
    scope2_kg = 0.0

    # Stage
    stage_kg = equipment.stage_m2 * event_days * eq.get("stage_per_m2_per_day", {}).get("factor", 0.5)

    # Lighting (Scope 2 - electricity)
    lighting_kg = equipment.lighting_days * eq.get("lighting_rig_per_day", {}).get("factor", 45.0)
    scope2_kg += lighting_kg

    # Sound (Scope 2)
    sound_kg = equipment.sound_system_days * eq.get("sound_system_per_day", {}).get("factor", 25.0)
    scope2_kg += sound_kg

    # LED screens (Scope 2)
    led_kg = equipment.led_screen_m2 * event_days * eq.get("led_screen_per_m2_per_day", {}).get("factor", 2.5)
    scope2_kg += led_kg

    # Projectors (Scope 2)
    proj_kg = equipment.projectors * event_days * eq.get("projector_per_day", {}).get("factor", 3.8)
    scope2_kg += proj_kg

    # Generator (Scope 1 - direct combustion)
    gen_kg = equipment.generator_hours * eq.get("generator_diesel_per_hour", {}).get("factor", 8.5)
    scope1_kg += gen_kg

    # Freight (Scope 3)
    freight_kg = equipment.freight_tonne_km * eq.get("freight_truck_per_km", {}).get("factor", 0.107)

    total_kg = stage_kg + lighting_kg + sound_kg + led_kg + proj_kg + gen_kg + freight_kg

    if total_kg > 0:
        notes["equipment"] = f"Stage {equipment.stage_m2}m2, lighting {equipment.lighting_days}d, sound {equipment.sound_system_days}d, LED {equipment.led_screen_m2}m2, gen {equipment.generator_hours}h"

    return total_kg, scope1_kg, scope2_kg, notes


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


def get_benchmark_comparison(event_type: str, per_attendee_day: float) -> Optional[BenchmarkComparison]:
    """Compare against industry benchmarks."""
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


def _get_benchmark(event_type: str, per_attendee_day: float) -> Optional[BenchmarkComparison]:
    """Backward-compatible alias for older imports."""
    return get_benchmark_comparison(event_type, per_attendee_day)


def calculate_scenario(scenario: EventScenarioInput) -> ScenarioResult:
    """Main entry point: calculate all emissions for a scenario."""
    attendees = scenario.attendees
    days = scenario.event_days
    assumptions = {}

    # Scope tracking
    scope1_total = 0.0
    scope2_total = 0.0
    scope3_total = 0.0

    # Travel (Scope 3)
    travel_kg, t_notes = _travel_emissions(scenario.travel_segments, attendees)
    scope3_total += travel_kg

    # Venue energy (Scope 2, with potential Scope 1 from generators)
    energy_kg, venue_s1_kg, e_notes = _venue_energy_emissions(scenario.venue_energy, attendees, days)
    scope2_total += energy_kg
    scope1_total += venue_s1_kg

    # Accommodation (Scope 3)
    accom_kg, a_notes = _accommodation_emissions(scenario.accommodation, attendees, days)
    scope3_total += accom_kg

    # Catering (Scope 3)
    catering_kg, c_notes = _catering_emissions(scenario.catering, attendees, days)
    scope3_total += catering_kg

    # Waste (Scope 3)
    waste_kg, w_notes = _waste_emissions(scenario.waste, attendees)
    scope3_total += waste_kg

    # Equipment (Scope 1 generators + Scope 2 electricity + Scope 3 freight)
    equip_kg, equip_s1, equip_s2, eq_notes = _equipment_emissions(scenario.equipment, days)
    scope1_total += equip_s1
    scope2_total += equip_s2
    scope3_total += max(0, equip_kg - equip_s1 - equip_s2)  # freight portion (clamped)

    # Swag (Scope 3)
    swag_kg, sw_notes = _swag_emissions(scenario.swag, attendees)
    scope3_total += swag_kg

    assumptions.update(t_notes)
    assumptions.update(e_notes)
    assumptions.update(a_notes)
    assumptions.update(c_notes)
    assumptions.update(w_notes)
    assumptions.update(eq_notes)
    assumptions.update(sw_notes)

    total_kg = travel_kg + energy_kg + accom_kg + catering_kg + waste_kg + equip_kg + swag_kg
    total_tco2e = total_kg / 1000
    per_attendee = total_tco2e / attendees if attendees > 0 else 0
    per_attendee_day = per_attendee / days if days > 0 else per_attendee

    # Data quality flag
    has_actual_data = any([
        scenario.travel_segments,
        scenario.venue_energy and (scenario.venue_energy.kwh_consumed or scenario.venue_energy.venue_area_m2),
        scenario.accommodation,
        scenario.catering,
        scenario.waste,
        scenario.equipment,
        scenario.swag,
    ])
    quality = "partial" if has_actual_data else "estimated"

    scopes = ScopeBreakdown(
        scope1_tco2e=round(scope1_total / 1000, 4),
        scope2_tco2e=round(scope2_total / 1000, 4),
        scope3_tco2e=round(scope3_total / 1000, 4),
    )

    emissions = EmissionBreakdown(
        travel_tco2e=round(travel_kg / 1000, 4),
        venue_energy_tco2e=round(energy_kg / 1000, 4),
        accommodation_tco2e=round(accom_kg / 1000, 4),
        catering_tco2e=round(catering_kg / 1000, 4),
        materials_waste_tco2e=round(waste_kg / 1000, 4),
        equipment_tco2e=round(equip_kg / 1000, 4),
        swag_tco2e=round(swag_kg / 1000, 4),
        total_tco2e=round(total_tco2e, 4),
        per_attendee_tco2e=round(per_attendee, 4),
        per_attendee_day_tco2e=round(per_attendee_day, 4),
        data_quality=quality,
        scopes=scopes,
    )

    # Benchmark
    benchmark = get_benchmark_comparison(scenario.event_type.value, per_attendee_day)

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
        created_at=datetime.utcnow().isoformat(),
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
        "travel_car_petrol_kg_per_pkm": EF["travel"]["car_petrol"]["factor"],
        "venue_grid_kg_per_kwh": grid_ef,
        "venue_grid_region": grid_key,
        "accommodation_kg_per_room_night": accom_ef,
        "accommodation_type": accom_type,
        "catering_kg_per_meal": catering_ef,
        "catering_type": catering_type,
        "waste_landfill_kg_per_kg": EF["materials_waste"]["general_landfill"]["factor"],
        "ef_version": EF.get("version", "unknown"),
        "captured_at": datetime.utcnow().isoformat(),
    }


def get_reduction_suggestions(result: ScenarioResult, target_pct: float = 30.0) -> list[dict]:
    """Generate ranked reduction suggestions to hit target % reduction."""
    emissions = result.emissions
    suggestions = []

    # Travel is usually biggest lever
    if emissions.travel_tco2e > 0:
        suggestions.append({
            "action": "enable_hybrid",
            "label": "Enable hybrid/virtual attendance (30% remote)",
            "co2e_saved_tco2e": round(emissions.travel_tco2e * 0.3, 3),
            "estimated_cost_usd": result.attendees * 0.3 * 30,
            "category": "travel",
            "difficulty": "medium",
            "scope": 3,
        })
        suggestions.append({
            "action": "shift_to_rail",
            "label": "Shift short-haul flights to rail (where <4h journey)",
            "co2e_saved_tco2e": round(emissions.travel_tco2e * 0.15, 3),
            "estimated_cost_usd": -result.attendees * 0.2 * 15,
            "category": "travel",
            "difficulty": "hard",
            "scope": 3,
        })
        suggestions.append({
            "action": "shuttle_bus",
            "label": "Provide shuttle buses from airports/stations to venue",
            "co2e_saved_tco2e": round(emissions.travel_tco2e * 0.05, 3),
            "estimated_cost_usd": result.attendees * 5,
            "category": "travel",
            "difficulty": "easy",
            "scope": 3,
        })

    # Catering switch
    if emissions.catering_tco2e > 0:
        meals = result.attendees * result.event_days * 2
        co2e_saved = meals * 2.1 / 1000
        suggestions.append({
            "action": "vegetarian_menu",
            "label": "Switch to fully vegetarian menu",
            "co2e_saved_tco2e": round(co2e_saved, 3),
            "estimated_cost_usd": -meals * 2.5,
            "category": "catering",
            "difficulty": "easy",
            "scope": 3,
        })
        suggestions.append({
            "action": "local_seasonal",
            "label": "Source local and seasonal ingredients",
            "co2e_saved_tco2e": round(emissions.catering_tco2e * 0.15, 3),
            "estimated_cost_usd": meals * 1.5,
            "category": "catering",
            "difficulty": "medium",
            "scope": 3,
        })

    # Renewable energy
    if emissions.venue_energy_tco2e > 0:
        suggestions.append({
            "action": "renewable_energy",
            "label": "Switch venue to 100% renewable energy tariff",
            "co2e_saved_tco2e": round(emissions.venue_energy_tco2e, 3),
            "estimated_cost_usd": result.attendees * result.event_days * 2,
            "category": "energy",
            "difficulty": "easy",
            "scope": 2,
        })

    # Equipment
    if emissions.equipment_tco2e > 0:
        suggestions.append({
            "action": "led_lighting",
            "label": "Switch to LED lighting (40% energy reduction)",
            "co2e_saved_tco2e": round(emissions.equipment_tco2e * 0.4, 3),
            "estimated_cost_usd": 500 * result.event_days,
            "category": "equipment",
            "difficulty": "easy",
            "scope": 2,
        })

    # Accommodation
    if emissions.accommodation_tco2e > 0:
        suggestions.append({
            "action": "eco_accommodation",
            "label": "Choose green-certified hotels (eco-lodge / green mark)",
            "co2e_saved_tco2e": round(emissions.accommodation_tco2e * 0.40, 3),
            "estimated_cost_usd": 0,
            "category": "accommodation",
            "difficulty": "medium",
            "scope": 3,
        })

    # Digital materials
    suggestions.append({
        "action": "digital_materials",
        "label": "Replace printed materials with digital (app/QR)",
        "co2e_saved_tco2e": round(result.attendees * 0.00025, 3),
        "estimated_cost_usd": -result.attendees * 2.0,
        "category": "waste",
        "difficulty": "easy",
        "scope": 3,
    })

    # Sustainable swag
    if emissions.swag_tco2e > 0:
        suggestions.append({
            "action": "sustainable_swag",
            "label": "Switch to recycled materials or digital-only swag",
            "co2e_saved_tco2e": round(emissions.swag_tco2e * 0.6, 3),
            "estimated_cost_usd": -result.attendees * 3,
            "category": "swag",
            "difficulty": "easy",
            "scope": 3,
        })

    # Zero waste
    suggestions.append({
        "action": "zero_waste",
        "label": "Zero-waste catering (compost + eliminate single-use)",
        "co2e_saved_tco2e": round(result.attendees * 0.0008 * result.event_days, 3),
        "estimated_cost_usd": result.attendees * 1.5,
        "category": "waste",
        "difficulty": "medium",
        "scope": 3,
    })

    # Carbon offsets (always last)
    suggestions.append({
        "action": "offset_residual",
        "label": "Offset residual emissions with Gold Standard credits",
        "co2e_saved_tco2e": round(emissions.total_tco2e * (target_pct / 100), 3),
        "estimated_cost_usd": round(emissions.total_tco2e * (target_pct / 100) * 15, 0),
        "category": "offsets",
        "difficulty": "easy",
        "scope": "all",
    })

    # Sort by CO2e saved descending
    suggestions.sort(key=lambda x: x["co2e_saved_tco2e"], reverse=True)
    return suggestions
