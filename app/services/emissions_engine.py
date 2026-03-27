"""
Deterministic emissions calculation engine.
Implements GHG Protocol Scope 1/2/3 methodology for events.
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.models.schemas import (
    EventScenarioInput, ScenarioResult, EmissionBreakdown,
    TravelMode, TravelClass, GridRegion, ScenarioMode
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


def _venue_energy_emissions(venue_energy, attendees: int, event_days: int) -> tuple[float, dict]:
    """Returns venue energy kg CO2e."""
    notes = {}

    if venue_energy is None:
        # Proxy: 2.8 kg CO2e/m2/day for conference, assume 2m2 per attendee
        proxy_area = attendees * 2.0
        total_kg = proxy_area * event_days * EF["venue_energy"]["proxy_factors"]["conference_centre_per_m2_day"]
        notes["venue"] = f"Proxy: {proxy_area}m² at 2.8 kg CO2e/m²/day"
        return total_kg, notes

    grid_key = venue_energy.grid_region.value
    grid_ef = EF["venue_energy"]["grids"].get(grid_key, EF["venue_energy"]["grids"]["global_average"])["factor"]

    if venue_energy.kwh_consumed:
        kwh = venue_energy.kwh_consumed
        notes["venue"] = f"Actual kWh: {kwh:.0f}"
    elif venue_energy.venue_area_m2:
        # Proxy: 30 kWh/m2/day for conference
        kwh = venue_energy.venue_area_m2 * event_days * 30
        notes["venue"] = f"Proxy kWh from area: {kwh:.0f}"
    else:
        kwh = attendees * 2.0 * event_days * 30
        notes["venue"] = f"Proxy kWh from attendees: {kwh:.0f}"

    # Apply renewable offset
    effective_ef = grid_ef * (1 - venue_energy.renewable_pct / 100)
    total_kg = kwh * effective_ef

    if venue_energy.renewable_pct > 0:
        notes["venue"] += f" ({venue_energy.renewable_pct}% renewable, grid: {grid_key})"

    return total_kg, notes


def _accommodation_emissions(accom, attendees: int, event_days: int) -> tuple[float, dict]:
    notes = {}

    if accom is None:
        # Proxy: 80% staying standard hotel, avg 1 night per day
        room_nights = (attendees * 0.8 / 1.5) * event_days
        ef = EF["accommodation"]["standard_hotel"]["factor"]
        total_kg = room_nights * ef
        notes["accommodation"] = f"Proxy: 80% attendees, standard hotel, {room_nights:.0f} room-nights"
        return total_kg, notes

    ef_key = accom.accommodation_type.value
    ef = EF["accommodation"].get(ef_key, EF["accommodation"]["standard_hotel"])["factor"]
    total_kg = accom.room_nights * ef
    notes["accommodation"] = f"{accom.room_nights} room-nights × {ef} kg CO2e"

    return total_kg, notes


def _catering_emissions(catering, attendees: int, event_days: int) -> tuple[float, dict]:
    notes = {}

    if catering is None:
        # Proxy: mixed buffet, 2 meals per day
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

    notes["catering"] = f"{catering.meals} {catering.catering_type.value} meals"
    return total_kg, notes


def _waste_emissions(waste, attendees: int) -> tuple[float, dict]:
    notes = {}

    if waste is None:
        # Proxy: 0.5 kg printed + 0.3 kg general waste per attendee
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

    notes["waste"] = f"Actual waste data provided"
    return total_kg, notes


def calculate_scenario(scenario: EventScenarioInput) -> ScenarioResult:
    """Main entry point: calculate all emissions for a scenario."""
    attendees = scenario.attendees
    days = scenario.event_days
    assumptions = {}

    travel_kg, t_notes = _travel_emissions(scenario.travel_segments, attendees)
    energy_kg, e_notes = _venue_energy_emissions(scenario.venue_energy, attendees, days)
    accom_kg, a_notes = _accommodation_emissions(scenario.accommodation, attendees, days)
    catering_kg, c_notes = _catering_emissions(scenario.catering, attendees, days)
    waste_kg, w_notes = _waste_emissions(scenario.waste, attendees)

    assumptions.update(t_notes)
    assumptions.update(e_notes)
    assumptions.update(a_notes)
    assumptions.update(c_notes)
    assumptions.update(w_notes)

    total_kg = travel_kg + energy_kg + accom_kg + catering_kg + waste_kg
    total_tco2e = total_kg / 1000
    per_attendee = total_tco2e / attendees if attendees > 0 else 0

    # Data quality flag
    has_actual_data = any([
        scenario.travel_segments,
        scenario.venue_energy and scenario.venue_energy.kwh_consumed,
        scenario.accommodation,
        scenario.catering,
    ])
    quality = "partial" if has_actual_data else "estimated"

    emissions = EmissionBreakdown(
        travel_tco2e=round(travel_kg / 1000, 4),
        venue_energy_tco2e=round(energy_kg / 1000, 4),
        accommodation_tco2e=round(accom_kg / 1000, 4),
        catering_tco2e=round(catering_kg / 1000, 4),
        materials_waste_tco2e=round(waste_kg / 1000, 4),
        total_tco2e=round(total_tco2e, 4),
        per_attendee_tco2e=round(per_attendee, 4),
        data_quality=quality,
    )

    return ScenarioResult(
        name=scenario.name,
        event_name=scenario.event_name,
        attendees=attendees,
        event_days=days,
        emissions=emissions,
        assumptions=assumptions,
        created_at=datetime.utcnow().isoformat(),
    )


def get_reduction_suggestions(result: ScenarioResult, target_pct: float = 30.0) -> list[dict]:
    """Generate ranked reduction suggestions to hit target % reduction."""
    emissions = result.emissions
    target_kg = emissions.total_tco2e * (target_pct / 100) * 1000
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
        })
        suggestions.append({
            "action": "shift_to_rail",
            "label": "Shift short-haul flights to rail (where <4h journey)",
            "co2e_saved_tco2e": round(emissions.travel_tco2e * 0.15, 3),
            "estimated_cost_usd": -result.attendees * 0.2 * 15,
            "category": "travel",
            "difficulty": "hard",
        })

    # Catering switch
    if emissions.catering_tco2e > 0:
        meals = result.attendees * result.event_days * 2
        co2e_saved = meals * 2.1 / 1000  # switch mixed to vegetarian
        suggestions.append({
            "action": "vegetarian_menu",
            "label": "Switch to fully vegetarian menu",
            "co2e_saved_tco2e": round(co2e_saved, 3),
            "estimated_cost_usd": -meals * 2.5,
            "category": "catering",
            "difficulty": "easy",
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
        })

    # Digital materials
    suggestions.append({
        "action": "digital_materials",
        "label": "Replace printed materials with digital (app/QR)",
        "co2e_saved_tco2e": round(result.attendees * 0.00025, 3),
        "estimated_cost_usd": -result.attendees * 2.0,
        "category": "waste",
        "difficulty": "easy",
    })

    # Sort by CO2e saved descending
    suggestions.sort(key=lambda x: x["co2e_saved_tco2e"], reverse=True)
    return suggestions
