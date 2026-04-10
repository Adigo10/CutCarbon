"""
OpenAI service: chat co-pilot with function calling for structured data extraction.
Converts natural language event descriptions into EventScenarioInput objects.
"""
import json
from typing import Optional, List, Dict, Any

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import ChatMessage, EventScenarioInput

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are EventCarbon Co-Pilot, an AI assistant that helps event organizers
calculate, understand, and reduce the carbon footprint of their events.

Your capabilities:
1. Extract structured event data from natural language descriptions
2. Estimate missing values using industry proxy factors (clearly flag as estimates)
3. Explain emissions methodology in plain language
4. Suggest practical, ranked reduction actions with cost implications
5. Calculate financial savings from carbon tax, incentives, and cost reductions
6. Assess compliance with GHG Protocol, ISO 20121, SBTi, and regional regulations

When users describe their event, extract:
- Attendee count, event duration, location
- Travel modes and distances
- Venue type and energy info
- Accommodation details
- Catering preferences
- Waste/materials approach

Always confirm inferred assumptions. Be concise, data-driven, and actionable.
Use tCO₂e as the unit throughout. Format numbers clearly."""

# Function definitions for structured data extraction
EXTRACTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_event_scenario",
            "description": "Update the event scenario with extracted structured data from the user's message",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string", "description": "Name of the event"},
                    "location": {"type": "string", "description": "City/country where event is held"},
                    "attendees": {"type": "integer", "description": "Total number of attendees"},
                    "event_days": {"type": "integer", "description": "Number of event days"},
                    "travel_segments": {
                        "type": "array",
                        "description": "Travel segments by mode",
                        "items": {
                            "type": "object",
                            "properties": {
                                "mode": {
                                    "type": "string",
                                    "enum": ["short_haul_flight", "long_haul_flight", "private_jet",
                                             "train_europe", "train_asia", "train_uk", "train_high_speed",
                                             "car_petrol", "car_diesel", "car_hybrid", "car_ev",
                                             "bus_coach", "shuttle_bus", "mrt_metro", "taxi_rideshare",
                                             "ferry", "e_scooter", "cycling"]
                                },
                                "travel_class": {"type": "string", "enum": ["economy", "business", "first"]},
                                "attendees": {"type": "integer"},
                                "distance_km": {"type": "number"},
                                "label": {"type": "string"}
                            },
                            "required": ["mode", "attendees", "distance_km"]
                        }
                    },
                    "venue_grid_region": {
                        "type": "string",
                        "enum": ["singapore", "eu_average", "uk", "australia", "usa", "china", "india",
                                 "japan", "south_korea", "canada", "brazil", "uae", "south_africa",
                                 "germany", "france", "nordics", "global_average"]
                    },
                    "venue_kwh": {"type": "number", "description": "Total kWh consumed at venue"},
                    "venue_area_m2": {"type": "number", "description": "Venue floor area in m²"},
                    "renewable_pct": {"type": "number", "description": "% of venue energy from renewables (0-100)"},
                    "accommodation_type": {
                        "type": "string",
                        "enum": ["budget_hotel", "standard_hotel", "luxury_hotel", "serviced_apartment",
                                 "airbnb_shared", "eco_lodge", "hostel", "no_accommodation"]
                    },
                    "room_nights": {"type": "integer"},
                    "catering_type": {
                        "type": "string",
                        "enum": ["red_meat_meal", "white_meat_meal", "vegetarian_meal", "vegan_meal",
                                 "mixed_buffet", "seafood_meal", "local_organic", "finger_food"]
                    },
                    "meals": {"type": "integer"},
                    "general_waste_kg": {"type": "number"},
                    "recycled_kg": {"type": "number"},
                    "has_printed_materials": {"type": "boolean"},
                    "exhibition_booths_m2": {"type": "number"},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_financial_analysis",
            "description": "Trigger financial savings and compliance analysis for a scenario",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string"},
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Actions taken: renewable_energy, vegetarian_menu, digital_materials, hybrid_event, etc."
                    }
                },
                "required": ["region"]
            }
        }
    }
]


def _build_context_message(event_context: Optional[Dict]) -> str:
    if not event_context:
        return ""
    parts = ["Current event context:"]
    if event_context.get("event_name"):
        parts.append(f"  Event: {event_context['event_name']}")
    if event_context.get("attendees"):
        parts.append(f"  Attendees: {event_context['attendees']}")
    if event_context.get("location"):
        parts.append(f"  Location: {event_context['location']}")
    if event_context.get("current_tco2e"):
        parts.append(f"  Current estimate: {event_context['current_tco2e']:.2f} tCO₂e")
    return "\n".join(parts)


async def chat(
    messages: List[ChatMessage],
    event_context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Send messages to OpenAI and return reply + any extracted structured data.
    """
    context_str = _build_context_message(event_context)

    system_content = SYSTEM_PROMPT
    if context_str:
        system_content += f"\n\n{context_str}"

    openai_messages = [{"role": "system", "content": system_content}]
    for msg in messages:
        openai_messages.append({"role": msg.role, "content": msg.content})

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=openai_messages,
        tools=EXTRACTION_TOOLS,
        tool_choice="auto",
        temperature=0.3,
    )

    choice = response.choices[0]
    extracted_data = None
    financial_trigger = None

    # Handle tool calls
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tool_results = []
        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "update_event_scenario":
                extracted_data = args
            elif tc.function.name == "request_financial_analysis":
                financial_trigger = args
            tool_results.append({
                "tool_call_id": tc.id,
                "role": "tool",
                "content": json.dumps({"status": "ok", "received": args}),
            })

        # Get final reply after tool use
        openai_messages.append(choice.message)
        openai_messages.extend(tool_results)

        follow_up = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=openai_messages,
            temperature=0.3,
        )
        reply = follow_up.choices[0].message.content or ""
    else:
        reply = choice.message.content or ""

    # Generate contextual suggestions
    suggestions = _generate_suggestions(reply, extracted_data, event_context)

    return {
        "reply": reply,
        "extracted_data": extracted_data,
        "financial_trigger": financial_trigger,
        "suggestions": suggestions,
    }


def _generate_suggestions(
    reply: str, extracted: Optional[Dict], context: Optional[Dict]
) -> List[str]:
    """Quick-reply suggestions based on conversation state."""
    suggestions = []
    if not extracted and not context:
        return [
            "Plan a 500-person tech conference in Singapore",
            "Estimate emissions for a 2-day workshop, 100 attendees",
            "What's the carbon impact of flying 300 guests from Europe?",
        ]

    if extracted and extracted.get("attendees"):
        suggestions.extend([
            "Show me the breakdown by category",
            "How can I cut 30% of emissions?",
            "What are the financial savings from going vegetarian?",
        ])

    if context and context.get("current_tco2e", 0) > 0:
        suggestions.extend([
            "Calculate carbon tax savings",
            "Compare with a fully virtual event",
            "Generate compliance report",
        ])

    return suggestions[:3]


async def generate_scenario_from_chat(raw_text: str) -> Optional[Dict]:
    """One-shot: extract a full scenario from a single text description."""
    messages = [ChatMessage(role="user", content=raw_text)]
    result = await chat(messages)
    return result.get("extracted_data")
