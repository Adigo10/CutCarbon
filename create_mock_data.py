#!/usr/bin/env python3
"""
Create detailed mock data for 5 diverse scenarios.
Run: python create_mock_data.py
"""

import asyncio
import os
import sys
from datetime import datetime
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.models.database import (
    AsyncSessionLocal, ScenarioDB, EventDB, FinancialReportDB,
    ChatMessageDB, init_db, UserDB
)
from app.models.schemas import (
    EventScenarioInput, EventType, TravelMode, TravelClass,
    AccommodationType, CateringType, GridRegion, ScenarioMode,
    TravelSegment, VenueEnergy, AccommodationGroup, CateringGroup,
    WasteGroup, EquipmentGroup, SwagGroup
)
from app.services.emissions_engine import calculate_scenario


async def clear_data(db: AsyncSession):
    """Delete all scenarios, events, and reports for demo accounts."""
    print("🧹 Clearing existing data...")

    # Delete in order of dependencies
    await db.execute(delete(FinancialReportDB))
    await db.execute(delete(ChatMessageDB))
    await db.execute(delete(ScenarioDB))
    await db.execute(delete(EventDB))

    await db.commit()
    print("✓ Database cleared")


async def create_scenario_in_db(
    db: AsyncSession,
    payload: EventScenarioInput,
    user_id: int
) -> dict:
    """Calculate and save a scenario."""
    result = calculate_scenario(payload)
    scenario_id = str(uuid.uuid4())[:8]

    db_obj = ScenarioDB(
        id=scenario_id,
        name=payload.name,
        event_name=payload.event_name,
        event_type=payload.event_type.value,
        attendees=payload.attendees,
        event_days=payload.event_days,
        mode=payload.mode.value,
        travel_tco2e=result.emissions.travel_tco2e,
        venue_energy_tco2e=result.emissions.venue_energy_tco2e,
        accommodation_tco2e=result.emissions.accommodation_tco2e,
        catering_tco2e=result.emissions.catering_tco2e,
        materials_waste_tco2e=result.emissions.materials_waste_tco2e,
        total_tco2e=result.emissions.total_tco2e,
        per_attendee_tco2e=result.emissions.per_attendee_tco2e,
        data_quality=result.emissions.data_quality,
        scope1_tco2e=result.emissions.scopes.scope1_tco2e if result.emissions.scopes else 0,
        scope2_tco2e=result.emissions.scopes.scope2_tco2e if result.emissions.scopes else 0,
        scope3_tco2e=result.emissions.scopes.scope3_tco2e if result.emissions.scopes else 0,
        assumptions=result.assumptions,
        input_payload=payload.model_dump(),
        created_at=datetime.utcnow(),
        user_id=user_id,
    )

    db.add(db_obj)
    await db.commit()

    return {
        "scenario_id": scenario_id,
        "name": payload.name,
        "total_tco2e": result.emissions.total_tco2e,
        "per_attendee": result.emissions.per_attendee_tco2e,
    }


async def main():
    # Initialize database
    await init_db()

    async with AsyncSessionLocal() as db:
        # Clear existing data
        await clear_data(db)

        # Create or get demo user
        demo_user = await db.execute(
            __import__('sqlalchemy').select(UserDB).where(UserDB.email == "demo@cutcarbon.com")
        )
        demo_user = demo_user.scalars().first()

        if not demo_user:
            demo_user = UserDB(
                email="demo@cutcarbon.com",
                hashed_password="$2b$12$fake_hash_for_demo",  # Dummy hash
                is_active=True
            )
            db.add(demo_user)
            await db.commit()
            print(f"✓ Created demo user: {demo_user.email}")

        user_id = demo_user.id
        print(f"📝 Using user_id: {user_id}\n")

        # ============================================================================
        # SCENARIO 1: Large Tech Conference in Singapore
        # ============================================================================
        print("📍 SCENARIO 1: TechConf Asia 2025 - Singapore")
        print("   Diverse attendee travel, renewable venue, advanced catering\n")

        scenario1 = EventScenarioInput(
            name="TechConf Asia 2025 - Main Conference",
            event_name="TechConf Asia 2025",
            event_type=EventType.CONFERENCE,
            location="Marina Bay Sands, Singapore",
            attendees=2500,
            event_days=3,
            mode=ScenarioMode.ADVANCED,

            # Diverse travel mix: international + local
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.BUSINESS,
                    attendees=600,  # From USA
                    distance_km=13600,
                    label="USA (Business Class)"
                ),
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=700,  # From Europe
                    distance_km=10800,
                    label="Europe (Economy)"
                ),
                TravelSegment(
                    mode=TravelMode.SHORT_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=400,  # From South Asia
                    distance_km=2500,
                    label="South Asia (Economy)"
                ),
                TravelSegment(
                    mode=TravelMode.SHORT_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=300,  # From East Asia
                    distance_km=3200,
                    label="East Asia (Economy)"
                ),
                TravelSegment(
                    mode=TravelMode.MRT_METRO,
                    travel_class=TravelClass.ECONOMY,
                    attendees=500,  # Local attendees
                    distance_km=25,
                    label="Local Singapore (MRT)"
                ),
                TravelSegment(
                    mode=TravelMode.TRAIN_HIGH_SPEED,
                    travel_class=TravelClass.ECONOMY,
                    attendees=100,  # From nearby
                    distance_km=1200,
                    label="Regional Train"
                ),
            ],

            # Modern venue with renewable energy
            venue_energy=VenueEnergy(
                grid_region=GridRegion.SINGAPORE,
                venue_area_m2=45000,
                kwh_consumed=22500,  # 0.5 kWh/m2/day * 45000 m2 * 1 day equivalent
                event_days=3,
                renewable_pct=65,  # Marina Bay has green building cert + solar
            ),

            # Premium accommodation mix
            accommodation=AccommodationGroup(
                accommodation_type=AccommodationType.STANDARD,
                room_nights=5000,  # 2500 attendees * 2 nights avg
                attendees_sharing=1.0,
            ),

            # Premium catering (mix of local, sustainable options)
            catering=CateringGroup(
                catering_type=CateringType.LOCAL_ORGANIC,
                meals=12500,  # 2500 attendees * 3 days * 1.67 meals/day
                include_beverages=True,
                include_alcohol=True,
                coffee_tea_cups=5000,
            ),

            # Waste management
            waste=WasteGroup(
                general_waste_kg=3750,
                recycled_kg=6250,
                composted_kg=2500,
                printed_materials_per_attendee=False,  # Digital-first
                exhibition_booths_m2=5000,
            ),

            # Equipment: large conference setup
            equipment=EquipmentGroup(
                stage_m2=500,
                lighting_days=3,
                sound_system_days=3,
                led_screen_m2=200,
                projectors=12,
                generator_hours=0,  # Grid powered
                freight_tonne_km=45,  # Materials transport
            ),

            # Swag: sustainable materials
            swag=SwagGroup(
                tshirts=2500,
                tshirt_type="organic",
                tote_bags=2500,
                lanyards=2500,
                badges=2500,
                badge_type="recycled",
                notebooks=0,  # Digital agenda
                water_bottles=0,  # Refill stations
            ),
        )

        result1 = await create_scenario_in_db(db, scenario1, user_id)
        print(f"   ✓ Created: {result1['name']}")
        print(f"     Total: {result1['total_tco2e']:.2f} tCO2e")
        print(f"     Per attendee: {result1['per_attendee']:.3f} tCO2e\n")

        # ============================================================================
        # SCENARIO 2: Hybrid Corporate Meeting - Frankfurt, EU
        # ============================================================================
        print("📍 SCENARIO 2: EURail Corporate Summit - Frankfurt")
        print("   Train-focused attendance, energy-efficient venue, vegan catering\n")

        scenario2 = EventScenarioInput(
            name="EURail Corporate Summit 2025 - Sustainability Track",
            event_name="EURail Corporate Summit 2025",
            event_type=EventType.CORPORATE_MEETING,
            location="Messeturm Convention Center, Frankfurt",
            attendees=480,
            event_days=2,
            mode=ScenarioMode.ADVANCED,

            # Train-heavy European attendance
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.TRAIN_HIGH_SPEED,
                    travel_class=TravelClass.ECONOMY,
                    attendees=200,  # From Paris, Lyon, Switzerland
                    distance_km=800,
                    label="France/Switzerland (Rail)"
                ),
                TravelSegment(
                    mode=TravelMode.TRAIN_EUROPE,
                    travel_class=TravelClass.ECONOMY,
                    attendees=150,  # From Netherlands, Belgium, Germany
                    distance_km=350,
                    label="Benelux/Germany (Rail)"
                ),
                TravelSegment(
                    mode=TravelMode.SHORT_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=80,  # From UK, Nordic
                    distance_km=1200,
                    label="UK/Nordic (Flight)"
                ),
                TravelSegment(
                    mode=TravelMode.CAR_EV,
                    travel_class=TravelClass.ECONOMY,
                    attendees=50,  # Local EV carpooling
                    distance_km=120,
                    label="Local (EV Car Share)"
                ),
            ],

            # Modern EU energy standard venue
            venue_energy=VenueEnergy(
                grid_region=GridRegion.GERMANY,
                venue_area_m2=8500,
                kwh_consumed=2125,  # 0.25 kWh/m2/day * 8500 m2
                event_days=2,
                renewable_pct=85,  # German grid + venue renewables
            ),

            # Eco-lodge accommodation focus
            accommodation=AccommodationGroup(
                accommodation_type=AccommodationType.ECO_LODGE,
                room_nights=480,  # 480 attendees * 1 night
                attendees_sharing=1.5,
            ),

            # Vegetarian/vegan focus
            catering=CateringGroup(
                catering_type=CateringType.VEGAN,
                meals=1920,  # 480 attendees * 2 days * 2 meals/day
                include_beverages=True,
                include_alcohol=False,
                coffee_tea_cups=1440,
            ),

            # Minimal waste
            waste=WasteGroup(
                general_waste_kg=96,
                recycled_kg=240,
                composted_kg=180,
                printed_materials_per_attendee=False,
                exhibition_booths_m2=500,
            ),

            # Modest equipment
            equipment=EquipmentGroup(
                stage_m2=150,
                lighting_days=2,
                sound_system_days=2,
                led_screen_m2=50,
                projectors=4,
                generator_hours=0,
                freight_tonne_km=8,
            ),

            # Digital-first swag
            swag=SwagGroup(
                tshirts=480,
                tshirt_type="organic",
                tote_bags=480,
                lanyards=0,
                badges=480,
                badge_type="recycled",
                notebooks=0,
                water_bottles=480,
            ),
        )

        result2 = await create_scenario_in_db(db, scenario2, user_id)
        print(f"   ✓ Created: {result2['name']}")
        print(f"     Total: {result2['total_tco2e']:.2f} tCO2e")
        print(f"     Per attendee: {result2['per_attendee']:.3f} tCO2e\n")

        # ============================================================================
        # SCENARIO 3: Large Music Festival - Melbourne, Australia
        # ============================================================================
        print("📍 SCENARIO 3: AusFest Music Festival - Melbourne")
        print("   Large diverse audience, varied accommodations, high catering\n")

        scenario3 = EventScenarioInput(
            name="AusFest 2025 - Main Event",
            event_name="AusFest 2025",
            event_type=EventType.MUSIC_FESTIVAL,
            location="Yarra Park, Melbourne",
            attendees=8500,
            event_days=4,
            mode=ScenarioMode.ADVANCED,

            # Diverse festival audience travel
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=1500,  # From Asia
                    distance_km=5500,
                    label="Asia (Long-haul)"
                ),
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=800,  # From Europe
                    distance_km=17000,
                    label="Europe (Long-haul)"
                ),
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=600,  # From USA
                    distance_km=14900,
                    label="USA (Long-haul)"
                ),
                TravelSegment(
                    mode=TravelMode.SHORT_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=2500,  # Domestic Australia
                    distance_km=1800,
                    label="Domestic Australia"
                ),
                TravelSegment(
                    mode=TravelMode.CAR_PETROL,
                    travel_class=TravelClass.ECONOMY,
                    attendees=1800,  # Regional road trip
                    distance_km=850,
                    label="Regional Car (Petrol)"
                ),
                TravelSegment(
                    mode=TravelMode.BUS_COACH,
                    travel_class=TravelClass.ECONOMY,
                    attendees=800,  # Festival shuttles
                    distance_km=120,
                    label="Festival Bus Service"
                ),
            ],

            # Festival outdoor venue (no climate control)
            venue_energy=VenueEnergy(
                grid_region=GridRegion.AUSTRALIA,
                venue_area_m2=60000,  # Large outdoor park
                kwh_consumed=3000,  # Mostly lighting/sound
                event_days=4,
                renewable_pct=40,  # Mixed grid
            ),

            # Budget accommodation mix (camping + hostels + budget hotels)
            accommodation=AccommodationGroup(
                accommodation_type=AccommodationType.HOSTEL,
                room_nights=20400,  # 8500 attendees * 2.4 nights avg
                attendees_sharing=3.0,  # Higher sharing for festivals
            ),

            # High-volume casual catering
            catering=CateringGroup(
                catering_type=CateringType.MIXED,
                meals=51000,  # 8500 attendees * 4 days * 1.5 meals/day (food stalls)
                include_beverages=True,
                include_alcohol=True,
                coffee_tea_cups=8500,
            ),

            # Festival waste (higher)
            waste=WasteGroup(
                general_waste_kg=8500,
                recycled_kg=6800,
                composted_kg=2550,
                printed_materials_per_attendee=True,
                exhibition_booths_m2=2000,
            ),

            # Major stage equipment
            equipment=EquipmentGroup(
                stage_m2=1200,
                lighting_days=4,
                sound_system_days=4,
                led_screen_m2=400,
                projectors=8,
                generator_hours=96,  # Backup generators, 24h x 4 days
                freight_tonne_km=120,
            ),

            # Festival merchandise (high volume, basic)
            swag=SwagGroup(
                tshirts=8500,
                tshirt_type="cotton",
                tote_bags=5000,
                lanyards=0,
                badges=0,
                badge_type="plastic",
                notebooks=0,
                water_bottles=8500,
            ),
        )

        result3 = await create_scenario_in_db(db, scenario3, user_id)
        print(f"   ✓ Created: {result3['name']}")
        print(f"     Total: {result3['total_tco2e']:.2f} tCO2e")
        print(f"     Per attendee: {result3['per_attendee']:.3f} tCO2e\n")

        # ============================================================================
        # SCENARIO 4: Boutique Sustainability Summit - UK
        # ============================================================================
        print("📍 SCENARIO 4: GreenLeaders Summit - London")
        print("   Small, sustainable-focused, carbon-neutral targeting\n")

        scenario4 = EventScenarioInput(
            name="GreenLeaders Sustainability Summit 2025",
            event_name="GreenLeaders Summit 2025",
            event_type=EventType.CONFERENCE,
            location="Somerset House, London",
            attendees=200,
            event_days=2,
            mode=ScenarioMode.ADVANCED,

            # Sustainability-conscious travel choices
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.TRAIN_UK,
                    travel_class=TravelClass.ECONOMY,
                    attendees=100,  # UK attendees (train)
                    distance_km=400,
                    label="UK (Rail)"
                ),
                TravelSegment(
                    mode=TravelMode.TRAIN_EUROPE,
                    travel_class=TravelClass.ECONOMY,
                    attendees=60,  # France/Belgium (Eurostar)
                    distance_km=600,
                    label="Continental Europe (Eurostar)"
                ),
                TravelSegment(
                    mode=TravelMode.SHORT_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=30,  # Scandinavia
                    distance_km=1500,
                    label="Scandinavia (Flight)"
                ),
                TravelSegment(
                    mode=TravelMode.CYCLING,
                    travel_class=TravelClass.ECONOMY,
                    attendees=10,  # Local cycling
                    distance_km=8,
                    label="Local London (Cycling)"
                ),
            ],

            # Historic venue, energy efficient
            venue_energy=VenueEnergy(
                grid_region=GridRegion.UK,
                venue_area_m2=3500,
                kwh_consumed=525,  # Modest 0.15 kWh/m2 (efficient old building)
                event_days=2,
                renewable_pct=75,  # UK national grid improvement
            ),

            # Eco-lodge preference
            accommodation=AccommodationGroup(
                accommodation_type=AccommodationType.ECO_LODGE,
                room_nights=200,  # 200 attendees * 1 night
                attendees_sharing=1.0,
            ),

            # Premium plant-based catering
            catering=CateringGroup(
                catering_type=CateringType.VEGAN,
                meals=600,  # 200 attendees * 2 days * 1.5 meals/day
                include_beverages=True,
                include_alcohol=False,
                coffee_tea_cups=600,
            ),

            # Minimal waste
            waste=WasteGroup(
                general_waste_kg=20,
                recycled_kg=60,
                composted_kg=40,
                printed_materials_per_attendee=False,
                exhibition_booths_m2=0,
            ),

            # Minimal equipment
            equipment=EquipmentGroup(
                stage_m2=50,
                lighting_days=2,
                sound_system_days=2,
                led_screen_m2=20,
                projectors=2,
                generator_hours=0,
                freight_tonne_km=2,
            ),

            # Minimal, premium swag
            swag=SwagGroup(
                tshirts=200,
                tshirt_type="organic",
                tote_bags=200,
                lanyards=0,
                badges=200,
                badge_type="recycled",
                notebooks=0,
                water_bottles=200,
            ),
        )

        result4 = await create_scenario_in_db(db, scenario4, user_id)
        print(f"   ✓ Created: {result4['name']}")
        print(f"     Total: {result4['total_tco2e']:.2f} tCO2e")
        print(f"     Per attendee: {result4['per_attendee']:.3f} tCO2e\n")

        # ============================================================================
        # SCENARIO 5: Large Trade Show - Las Vegas, USA
        # ============================================================================
        print("📍 SCENARIO 5: TechTrade Expo - Las Vegas")
        print("   Large trade show, international travel, heavy equipment/setup\n")

        scenario5 = EventScenarioInput(
            name="TechTrade Expo 2025 - Main Show",
            event_name="TechTrade Expo 2025",
            event_type=EventType.TRADE_SHOW,
            location="Las Vegas Convention Center",
            attendees=5000,
            event_days=5,
            mode=ScenarioMode.ADVANCED,

            # International trade show audience
            travel_segments=[
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.BUSINESS,
                    attendees=1200,  # USA domestic (business)
                    distance_km=3200,
                    label="USA Domestic (Business)"
                ),
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=1800,  # USA domestic (economy)
                    distance_km=3000,
                    label="USA Domestic (Economy)"
                ),
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=600,  # Europe
                    distance_km=9000,
                    label="Europe"
                ),
                TravelSegment(
                    mode=TravelMode.LONG_HAUL_FLIGHT,
                    travel_class=TravelClass.ECONOMY,
                    attendees=800,  # Asia
                    distance_km=10500,
                    label="Asia"
                ),
                TravelSegment(
                    mode=TravelMode.CAR_PETROL,
                    travel_class=TravelClass.ECONOMY,
                    attendees=400,  # Regional drives
                    distance_km=800,
                    label="Regional (Car)"
                ),
                TravelSegment(
                    mode=TravelMode.BUS_COACH,
                    travel_class=TravelClass.ECONOMY,
                    attendees=200,  # Shuttle buses from airport
                    distance_km=40,
                    label="Airport Shuttle"
                ),
            ],

            # Large convention venue with heavy AC
            venue_energy=VenueEnergy(
                grid_region=GridRegion.USA,
                venue_area_m2=120000,  # Large convention center
                kwh_consumed=36000,  # 0.3 kWh/m2/day * 120000 m2
                event_days=5,
                renewable_pct=15,  # Vegas grid mix (low renewables)
            ),

            # Standard luxury hotel accommodation
            accommodation=AccommodationGroup(
                accommodation_type=AccommodationType.LUXURY,
                room_nights=20000,  # 5000 attendees * 4 nights
                attendees_sharing=1.0,
            ),

            # Casual trade show food
            catering=CateringGroup(
                catering_type=CateringType.MIXED,
                meals=30000,  # 5000 attendees * 5 days * 1.2 meals/day
                include_beverages=True,
                include_alcohol=True,
                coffee_tea_cups=12500,
            ),

            # Substantial trade show waste
            waste=WasteGroup(
                general_waste_kg=5000,
                recycled_kg=3000,
                composted_kg=500,
                printed_materials_per_attendee=True,
                exhibition_booths_m2=8000,
            ),

            # Massive trade show equipment footprint
            equipment=EquipmentGroup(
                stage_m2=800,
                lighting_days=5,
                sound_system_days=5,
                led_screen_m2=600,
                projectors=25,
                generator_hours=120,  # Backup power
                freight_tonne_km=500,  # Booth materials, equipment
            ),

            # Branded merchandise (high volume)
            swag=SwagGroup(
                tshirts=5000,
                tshirt_type="cotton",
                tote_bags=5000,
                lanyards=5000,
                badges=5000,
                badge_type="plastic",
                notebooks=2500,
                water_bottles=5000,
            ),
        )

        result5 = await create_scenario_in_db(db, scenario5, user_id)
        print(f"   ✓ Created: {result5['name']}")
        print(f"     Total: {result5['total_tco2e']:.2f} tCO2e")
        print(f"     Per attendee: {result5['per_attendee']:.3f} tCO2e\n")

        # ============================================================================
        # Summary
        # ============================================================================
        print("=" * 80)
        print("✅ MOCK DATA CREATED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nScenarios created:")
        print(f"  1. {result1['name']:<45} {result1['total_tco2e']:>8.2f} tCO2e")
        print(f"  2. {result2['name']:<45} {result2['total_tco2e']:>8.2f} tCO2e")
        print(f"  3. {result3['name']:<45} {result3['total_tco2e']:>8.2f} tCO2e")
        print(f"  4. {result4['name']:<45} {result4['total_tco2e']:>8.2f} tCO2e")
        print(f"  5. {result5['name']:<45} {result5['total_tco2e']:>8.2f} tCO2e")

        total_emissions = (
            result1['total_tco2e'] +
            result2['total_tco2e'] +
            result3['total_tco2e'] +
            result4['total_tco2e'] +
            result5['total_tco2e']
        )

        print(f"\n{'TOTAL PORTFOLIO EMISSIONS':<45} {total_emissions:>8.2f} tCO2e")
        print("\n✨ Ready to explore these scenarios in the dashboard!")


if __name__ == "__main__":
    asyncio.run(main())
