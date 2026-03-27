EventCarbon Co‑Pilot – Detailed Plan
User roles & core flows
Roles

Event organizer (primary): defines scenarios, collects data, reports results.

Sustainability lead/consultant: fine‑tunes assumptions, uploads precise data.

Sponsor/client: views “footprint + reduction + offset” reports.

Key user flows

Chat‑first event intake

Organizer opens a chat and types: “We’re planning a 3‑day tech conference in Singapore, 800 attendees, hybrid, mostly APAC audience.”

Chatbot asks clarifying questions (travel mix, catering style, hotels, exhibition booths, etc.), then generates an initial scenario from partial info using proxy factors (like atmosfair/myclimate calculators do).

Multi‑scenario comparison

Organizer asks: “What if we move it to Bangkok and push for more rail travel?”

Agent clones baseline, tweaks parameters, and shows scenario A vs B vs C: total tCO₂e, per‑attendee numbers, and category breakdowns (travel, venue energy, catering, waste).

Supplier data collection

Organizer says: “Ask our caterer and AV vendor for precise data.”

Platform generates shareable links / mini‑forms or structured email prompts the organizer forwards to suppliers (kWh, fuel, kg of materials, menu composition).

When suppliers respond, chatbot ingests their numbers and updates calculations.

Reduction & offset planning

User asks: “How can we cut 30% of emissions?”

Agent suggests measure sets (shift travel modes, change menu, consolidate logistics), and estimates impact and remaining emissions to offset.

Architecture overview
1. Frontend

Chat + form hybrid UI

Chat pane (OpenAI) for natural‑language data entry and Q&A.

Side panel with structured forms auto‑filled from chat: “Attendees by region/mode”, “Venue energy”, “Catering”, “Accommodation”, “Materials & waste”.

Scenario dashboard

Cards for each scenario (name, total tCO₂e, per‑attendee, % by category).

Comparison view: stacked bar chart per scenario; table of assumptions.

2. Backend services

Orchestrator API

Endpoints:

create_or_update_event(payload)

create_scenario(event_id, changes)

calculate_emissions(scenario_id)

get_recommendations(scenario_id, target_reduction)

Handles auth, DB access, and emissions engine calls.

Emissions engine

Deterministic layer implementing algorithms inspired by Green Events Tool, NetNada, myclimate, etc.

Modules:

Travel: participants × distance × emission factor (per mode/class).

Venue energy: kWh × grid factor (or proxy per m²/day where data is missing).

Accommodation: nights × room type × factor.

Catering: meals × menu type (meat/veg/vegan) × factor.

Materials & waste: mass/units × waste/emission factor.

Supports “basic” (proxy‑heavy) and “advanced” (detailed data) paths like Green Events Tool.

Chat/LLM service

OpenAI models for:

Natural‑language → structured activity data conversion (“70% fly from EU, 30% local by MRT” → structured breakdown).

Suggesting sensible defaults when data is missing (clearly flagged as estimates, similar to atmosfair and Green Events Tool basic modes).

Generating reduction/offset recommendations and plain‑language explanations of methodology and boundaries.

Web Agent (TinyFish) layer

Agents that:

Fetch updated emission factor tables from authoritative sources (e.g., national inventories, methodology PDFs, calculator docs) on schedule.

Look up venue‑specific or regional grid factors, and local transport options (rail vs air availability).

Results stored in an EmissionFactor catalog with provenance.

Data model (core entities)
Event: id, name, location, dates, type, organizer_id.

Scenario: id, event_id, name, description, assumptions (JSON), mode (basic/advanced).

ActivityGroup: type (travel, venue_energy, accommodation, catering, materials, waste), scope (1/2/3), scenario_id.

ActivityItem: group_id, quantity, unit, emission_factor_id, source (user_input/chat_inferred/supplier_form/default_proxy).

EmissionFactor: id, category, region, value, unit, source_url, last_updated, methodology_tag (e.g., IPCC2013, GHGProtocol).

Chatbot design and dynamics
Modes

Data collection mode

Uses structured prompts to progressively fill ActivityItems.

Confirms inferred assumptions: “I assumed 60% of your attendees will fly economy within 3h, ok to use that?”

Explanation mode

Answers “why is this number high?”, “what’s included/excluded?”, with references to scopes and boundaries, echoing guidance from climate calculators and methodology docs.

Design/what‑if mode

Supports commands like “clone baseline and switch all red‑meat meals to vegetarian” or “reduce long‑haul flights by 20% and recompute”.

Data‑rich & dynamic aspects

Factor catalog regularly refreshed via web agents from new or updated calculators/methodologies; stores version history for audit.

Scenarios versioned over time so organizers can compare year‑over‑year footprints and improvements.

Hackathon MVP vs stretch
MVP (24–36h)

One country/region (e.g., Singapore or generic EU factors).

Categories: travel + venue energy + catering; simple waste proxy.

Chat intake → structured scenario → deterministic calculation → comparison chart.

Stretch

Supplier forms + ingestion.

Multi‑event history and progress view.

Automatic offset suggestion block (linking to known offset providers via web agents)