# CutCarbon Architecture & User Flow

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    WEB BROWSER                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  React 19 + TypeScript Application               │   │
│  │  (Vite SPA + fetch-based API client)             │   │
│  │                                                  │   │
│  │  ├─ Auth: Login/Register view                   │   │
│  │  ├─ Dashboard: KPI cards, charts, benchmarks    │   │
│  │  ├─ AI Co-Pilot: Chat interface                 │   │
│  │  ├─ Scenarios: Form builder + results display   │   │
│  │  ├─ Financial: Tax savings calculator           │   │
│  │  ├─ Carbon Credits: Portfolio management        │   │
│  │  ├─ Compliance: Framework scoring               │   │
│  │  └─ Data & Exports: Downloads, agent status     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        ↕️  HTTP/JSON
┌─────────────────────────────────────────────────────────┐
│               FASTAPI BACKEND (Python)                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Routers (Request Handlers)                      │   │
│  │                                                  │   │
│  │  ├─ /api/auth/me   → Verify Supabase token + me │   │
│  │  ├─ /api/chat      → OpenAI function calling    │   │
│  │  ├─ /api/scenarios → CRUD, cloning, recalc-all  │   │
│  │  ├─ /api/financial → Tax savings + compliance   │   │
│  │  │                   (GHG, ISO20121, NZCE, EU)  │   │
│  │  ├─ /api/offsets   → Project browse, purchases  │   │
│  │  ├─ /api/agents    → Web scrapers (admin-only)  │   │
│  │  └─ /api/exports   → PDF/Excel/CSV/JSON reports │   │
│  └──────────────────────────────────────────────────┘   │
│                        ↕️                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Services (Business Logic)                       │   │
│  │                                                  │   │
│  │  ├─ emissions_engine.py                         │   │
│  │  │  └─ Deterministic GHG Protocol calculations  │   │
│  │  │     (8 categories incl. digital/virtual)     │   │
│  │  ├─ financial_engine.py                         │   │
│  │  │  └─ Tax savings, incentives, compliance      │   │
│  │  ├─ openai_service.py                           │   │
│  │  │  └─ Chat with function calling               │   │
│  │  ├─ tinyfish_agent.py                           │   │
│  │  │  └─ Web scraper orchestration                │   │
│  │  ├─ scenario_serializer.py                      │   │
│  │  │  └─ ScenarioDB row ↔ API payload mapping     │   │
│  │  ├─ regions.py → canonical region aliases       │   │
│  │  └─ data_files.py → shared JSON data loading    │   │
│  └──────────────────────────────────────────────────┘   │
│                        ↕️                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Database (SQLAlchemy ORM + Async)              │   │
│  │                                                  │   │
│  │  ├─ Users table                                 │   │
│  │  ├─ Scenarios table                             │   │
│  │  ├─ Chat messages                               │   │
│  │  ├─ Financial reports                           │   │
│  │  ├─ Offset purchases                            │   │
│  │  ├─ Emission factors (write-only audit log —    │   │
│  │  │   emission_factors.json is the live source)  │   │
│  │  └─ Agent run history                           │   │
│  └──────────────────────────────────────────────────┘   │
│    (Supabase Postgres via asyncpg; sqlite dev fallback) │
│    least-priv role `cutcarbon_app` @ IPv4 txn pooler;   │
│    RLS on + anon/authenticated grants revoked (no        │
│    PostgREST access). Ops: docs/DB_OPERATIONS.md         │
└─────────────────────────────────────────────────────────┘
                        ↕️  HTTPS
┌─────────────────────────────────────────────────────────┐
│           EXTERNAL SERVICES (Async)                     │
│                                                         │
│  ├─ OpenAI API → function calling (gpt-4o-mini)       │
│  │  (Extracts event data from chat)                    │
│  │                                                      │
│  ├─ TinyFish Agents (10x Headless Browser)            │
│  │  ├─ EMA ← Singapore Electricity Market Authority   │
│  │  ├─ DEFRA ← UK Dept for Environment (GHG factors) │
│  │  ├─ EPA eGRID ← US grid emission factors           │
│  │  ├─ EEA ← EU European Environment Agency           │
│  │  ├─ Clean Energy Reg. ← Australia NGER             │
│  │  ├─ NEA ← Singapore National Environment Agency    │
│  │  ├─ Ember Climate ← EU ETS carbon price            │
│  │  ├─ UK Govt ← UK ETS carbon price                  │
│  │  ├─ ICAO ← International Aviation (flight factors) │
│  │  └─ Our World in Data ← Food/catering emissions    │
│  │                                                      │
│  └─ Data Files (JSON)                                 │
│     ├─ emission_factors.json → Updated by agents      │
│     ├─ tax_incentives.json → Regional rates           │
│     └─ carbon_offsets.json → Project catalog          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 👤 User Journey (Complete Flow)

```
                    START
                      ↓
        ┌─────────────────────────┐
        │  User Visits localhost  │
        │     http://8000/        │
        └─────────────────────────┘
                      ↓
        ┌─────────────────────────┐
        │  Check Supabase session │
        │  (supabase-js)          │
        └─────────────────────────┘
                    ↙   ↘
             NO SESSION  SESSION EXISTS
                ↙         ↘
        ┌────────────┐  ┌──────────────┐
        │   LOGIN    │  │  DASHBOARD   │
        │  / REGISTER│  │  (Load home) │
        └────────────┘  └──────────────┘
              ↓                ↓
        1. Enter email      View KPIs:
        2. Enter password   • Total emissions
        3. Click Register   • Tax liability
           or Login         • Compliance %
                ↓           • Offset coverage
        Request /auth       │
        endpoint       ┌─────────────────┐
                ↓      │  7 TAB OPTIONS  │
        JWT token  ────→│                 │
        created    ├──→ │• Dashboard      │
                ↓  │    │• AI Co-Pilot    │
        ┌──────────┘    │• Scenarios      │
        │               │• Financial      │
        └──────────────→│• Carbon Credits │
                        │• Compliance     │
                        │• Data & Exports │
                        └─────────────────┘
                              ↓
         ┌────────────────────────────────────┐
         │  USER CHOOSES: How to start?       │
         │                                    │
         │  OPTION A:     OPTION B:          │
         │  AI CO-PILOT   SCENARIOS TAB      │
         │  (Chat)        (Manual form)      │
         │                                    │
         │  OPTION C:     OPTION D:          │
         │  DASHBOARD     COMPLIANCE         │
         │  (Review data) (View frameworks)   │
         └────────────────────────────────────┘
                  ↙        ↙        ↙        ↘
        ┌─────────────┐  ┌──────────────────┐
        │   CHAT      │  │  CREATE SCENARIO │
        │ CO-PILOT    │  │  (Manual Input)  │
        └─────────────┘  └──────────────────┘
              ↓                      ↓
        Type description       Fill form fields:
        "500 person conf        • Event details
         Singapore,             • Travel segments
         2 days, flying         • Venue energy
         from US"               • Accommodation
                ↓               • Catering
        OpenAI extracts         • Waste
        structured data         • Equipment
                ↓               • Merchandise
        ┌──────────────────┐            ↓
        │ CALCULATION      │    Click [CALCULATE]
        │ (GHG Protocol)   │            ↓
        └──────────────────┘    ┌──────────────────┐
              ↓                  │ CALCULATION      │
        Result returned          │ (GHG Protocol)   │
                ↓                └──────────────────┘
        Display in                     ↓
        Chat bubble              Result displayed
        with JSON               in form / card
                ↓                      ↓
        Create scenario?         ┌───────────────────┐
        [Yes] [No]               │ SCENARIO CREATED  │
                ↓                └───────────────────┘
        Store in DB                    ↓
                ↓                View results:
        ┌──────────────────────┐ • Breakdown chart
        │ SCENARIO CREATED     │ • Scope analysis
        └──────────────────────┘ • Benchmark
              ↓                  • Data quality
        ┌──────────────────────────────────┐
        │  USER CHOOSES NEXT ACTION        │
        │                                  │
        │  [Edit]      [Clone]  [Compare]  │
        │  [Suggest]   [Financial] [Export]│
        └──────────────────────────────────┘
              ↙          ↓           ↘
        ┌────────┐ ┌──────────┐ ┌──────────┐
        │ EDIT   │ │GET IDEAS │ │FINANCIAL │
        │SCENARIO│ │(Reduction)│ │ANALYSIS  │
        └────────┘ └──────────┘ └──────────┘
             ↓           ↓            ↓
        Edit params AI suggests    View:
        Recalculate changes        •Tax savings
             ↓           ↓            •Incentives
        New results  3-5 ideas      •Cost savings
             ↓           ↓            •Offset cost
        Keep editing? Apply change?    ↓
        [Save] or    [Update]     ┌──────────┐
        [Discard]    or           │PURCHASED?│
             ↓        [Discard]    └──────────┘
        Continue...         ↓           ↓
                    New scenario    [YES][NO]
                         ↓            ↓
                    Continue...  ┌─────────────────┐
                                 │CARBON CREDITS   │
                                 │TAB              │
                                 └─────────────────┘
                                       ↓
                                 Browse projects
                                       ↓
                                 Select offset type
                                 • Renewable
                                 • Forestry
                                 • Cookstove
                                 • etc.
                                       ↓
                                 Enter quantity
                                       ↓
                                 [PURCHASE]
                                       ↓
                                 Add to portfolio
                                       ↓
                                 [RETIRE] credits
                                 for this scenario
                                       ↓
                                 Event marked:
                                 ✓ CARBON NEUTRAL
                                       ↓
                        ┌──────────────────────┐
                        │ COMPLIANCE TAB       │
                        │                      │
                        │ View scores:         │
                        │ • GHG Protocol: 92%  │
                        │ • ISO 20121: 50%     │
                        │ • NZCE: 60%          │
                        │ • Intensity: 80%     │
                        │ • Regional: 70%      │
                        └──────────────────────┘
                               ↓
                        [EXPORT REPORT]
                               ↓
                        Download as:
                        • PDF (stakeholder)
                        • Excel (analysis)
                        • JSON (API)
                               ↓
                        ┌──────────────────┐
                        │ COMPLETE!        │
                        │                  │
                        │ You have:        │
                        │ ✓ Calculated     │
                        │ ✓ Analyzed       │
                        │ ✓ Optimized      │
                        │ ✓ Financed       │
                        │ ✓ Offset         │
                        │ ✓ Reported       │
                        └──────────────────┘
```

---

## 🔄 Data Flow: Chat → Calculation → Result

```
┌──────────────────────────────────────────────────────────┐
│ STEP 1: USER SENDS MESSAGE                               │
└──────────────────────────────────────────────────────────┘

User message:
"500-person tech conference in Singapore,
 3 days, 60% from USA (flights),
 40% from Asia (train/regional flights)"

Frontend (React SPA):
  1. Capture input text
  2. Create ChatRequest object
  3. POST /api/chat with:
     {
       "messages": [{"role": "user", "content": "..."}],
       "session_id": "session-abc123"
     }

┌──────────────────────────────────────────────────────────┐
│ STEP 2: OPENAI FUNCTION CALLING                          │
└──────────────────────────────────────────────────────────┘

Backend (routers/chat.py):
  1. Extract last user message
  2. Call openai_service.chat()
  3. Send to OpenAI with function definitions:
     [
       {
         "name": "update_event_scenario",
         "parameters": {
           "attendees": number,
           "event_type": string,
           "travel_segments": array,
           "venue": object,
           "catering": object,
           ...
         }
       },
       {
         "name": "request_financial_analysis",
         "parameters": { "scenario_id": string }
       }
     ]

OpenAI (default model gpt-4o-mini):
  1. Reads user message
  2. Identifies intent (create scenario, ask question, etc)
  3. Extracts key details:
     - 500 attendees
     - Singapore location
     - 3 days
     - Travel mix (60% USA, 40% Asia)
  4. Calls function: update_event_scenario()
  5. Returns structured data

OpenAI response:
{
  "reply": "Got it! I'm analyzing a 500-person
            tech conference in Singapore with
            diverse international travel...",
  "extracted_data": {
    "attendees": 500,
    "event_type": "conference",
    "location": "Singapore",
    "event_days": 3,
    "travel_segments": [
      {
        "mode": "long_haul_flight",
        "attendees": 300,
        "distance_km": 13600,
        "travel_class": "economy"
      },
      {
        "mode": "short_haul_flight",
        "attendees": 200,
        "distance_km": 3000,
        "travel_class": "economy"
      }
    ],
    ...
  },
  "suggestions": [
    "Switch 50 attendees to train via 'rail hub'",
    "Increase venue renewable energy to 80%",
    ...
  ]
}

┌──────────────────────────────────────────────────────────┐
│ STEP 3: EMISSIONS CALCULATION                            │
└──────────────────────────────────────────────────────────┘

Backend (services/emissions_engine.py):

Function: calculate_scenario(input: EventScenarioInput)

For each emission category:

  TRAVEL:
    For each travel segment:
      ├─ Lookup emission factor by mode + class
      │  (from emission_factors.json)
      ├─ Calculate: attendees × distance × factor
      ├─ Add RFI multiplier for flights (1.9x)
      └─ Accumulate to travel_tco2e
    Result: travel_tco2e = 1,245 tCO2e

  VENUE ENERGY:
    ├─ Regional grid factor (Singapore = 0.38 kg CO2/kWh)
    ├─ Calculate: kWh × grid_factor
    ├─ Apply renewable reduction:
    │  emissions × (1 - renewable_pct)
    ├─ Venue_energy_tco2e = 310 tCO2e
    └─ Scope 2 = 310 tCO2e

  ACCOMMODATION:
    ├─ Lookup factor by type (standard hotel)
    ├─ Calculate: room_nights × factor
    └─ Accommodation_tco2e = 126 tCO2e

  CATERING:
    ├─ Lookup meal type factor
    ├─ Calculate: meals × factor
    └─ Catering_tco2e = 210 tCO2e

  WASTE:
    ├─ Calculate disposal method emissions
    ├─ Factor in recycling + composting diversion
    └─ Waste_tco2e = 35 tCO2e

  EQUIPMENT & SWAG:
    ├─ Lookup stage/AV/lighting factors
    ├─ Generator emissions (if any)
    └─ Equipment_tco2e = 15 tCO2e

  DIGITAL (virtual/hybrid events):
    ├─ Streaming: virtual attendees × hours × factor
    ├─ Livestream production, event app, email campaigns
    ├─ Virtual attendees get NO physical travel/venue proxy
    └─ Digital_tco2e = 0 tCO2e (fully in-person event)

Aggregation:
  total = travel + venue + accommodation
          + catering + waste + equipment
          + swag + digital
        = 1,245 + 310 + 126 + 210 + 35 + 15 + 0 + 0
        = 1,941 tCO2e

Per-attendee:
  per_attendee = 1,941 / 500 = 3.88 tCO2e

Scope breakdown:
  Scope 1 = 0 (no on-site generators)
  Scope 2 = 310 (venue electricity)
  Scope 3 = 1,631 (travel, accommodation, catering, waste)

Result object:
{
  "total_tco2e": 1941,
  "per_attendee_tco2e": 3.88,
  "breakdown": {
    "travel_tco2e": 1245,
    "venue_energy_tco2e": 310,
    "accommodation_tco2e": 126,
    "catering_tco2e": 210,
    "waste_tco2e": 35,
    "equipment_tco2e": 15
  },
  "scopes": {
    "scope1_tco2e": 0,
    "scope2_tco2e": 310,
    "scope3_tco2e": 1631
  },
  "benchmark": {
    "your_per_attendee_day": 1.30,
    "industry_typical": 0.8,
    "percentile_rank": "above average"
  },
  "assumptions": {
    "flight_rfi_multiplier": 1.9,
    "singapore_grid_factor": 0.38,
    "standard_hotel_per_night": 15.2,
    ...
  }
}

┌──────────────────────────────────────────────────────────┐
│ STEP 4: RETURN TO FRONTEND & DISPLAY                     │
└──────────────────────────────────────────────────────────┘

ChatResponse:
{
  "reply": "Perfect! Here's what I calculated...",
  "extracted_data": { ... },
  "session_id": "…",
  "financial_analysis": { ... },   // real financial-engine output
                                   // when a scenario is selected and
                                   // the model requests an analysis
  "suggestions": [
    "Switch 100 attendees from flights to train (-180 tCO2e)",
    "Increase renewable to 80% (-60 tCO2e)",
    ...
  ]
}

Frontend (React SPA):
  1. Parse response
  2. Display in chat bubble
  3. Render chart with breakdown
  4. Show suggestions as clickable pills
  5. Offer to create scenario
  6. If [Create Scenario] clicked:
     → Save to DB
     → Redirect to Scenarios tab
     → Display full result card
```

---

## 🔐 Authentication Flow

```
┌──────────────────────────────────────────────────────────┐
│ REGISTRATION                                             │
└──────────────────────────────────────────────────────────┘

Authentication is delegated to Supabase Auth. Supabase owns credentials and mints
the JWTs; FastAPI only verifies them and keeps a local profile row.

User enters:
  Email: user@example.com
  Password: ••••••••

Frontend (lib/supabase.ts, supabase-js):
  supabase.auth.signUp({ email, password })   // or signInWithPassword({...})

Supabase Auth:
  1. Creates / authenticates the user in auth.users (UUID id)
  2. Returns a session: access_token (JWT) + refresh_token
  3. supabase-js persists the session in localStorage and refreshes it silently
  (If email confirmation is enabled, signUp returns no session until confirmed)

Frontend:
  1. onAuthStateChange fires → App.tsx stores session.access_token in `token`
  2. Calls GET /api/auth/me to load the profile, then renders the workspace

┌──────────────────────────────────────────────────────────┐
│ AUTHENTICATED REQUESTS                                   │
└──────────────────────────────────────────────────────────┘

All API requests include:
  Authorization: Bearer <supabase access_token>

Backend (routers/auth.py get_current_user → app/auth/supabase.py):
  1. Extract token from the Authorization header (401 if missing)
  2. verify_supabase_token():
     - read alg/kid from the header
     - RS256/ES256 → verify against the project JWKS
       ({SUPABASE_URL}/auth/v1/.well-known/jwks.json, cached)
     - HS256 → verify against SUPABASE_JWT_SECRET (legacy/test)
     - check audience ("authenticated"), issuer ({SUPABASE_URL}/auth/v1), exp
  3. JIT-provision: upsert public.users(id=<sub UUID>, email) and return it
  4. If verification fails: 401 Unauthorized

Example:
  GET /api/scenarios
  Headers: { "Authorization": "Bearer eyJ..." }

Backend:
  1. Verify token → current_user (UUID id)
  2. Query: SELECT * FROM scenarios WHERE user_id = <current_user.id>
  3. Return only this user's scenarios

require_admin: same chain, then checks current_user.email against ADMIN_EMAILS.

┌──────────────────────────────────────────────────────────┐
│ SESSION PERSISTENCE                                      │
└──────────────────────────────────────────────────────────┘

On page reload:
  1. supabase-js rehydrates the session from localStorage
  2. App.tsx reads it via supabase.auth.getSession() → sets `token`
  3. If no session: render the auth screen

Token refresh:
  1. supabase-js refreshes the access token before expiry automatically
  2. onAuthStateChange delivers the new token; App.tsx updates `token`
  3. A verification failure (e.g. revoked session) → 401 → clearSession + signOut

Swagger access:
  Paste a Supabase access token into the /docs "Authorize" dialog
  (FastAPI no longer exposes a password/token endpoint).
```

---

## 📊 Emission Factor Data Flow

For full per-agent specifications, validation bounds, unit conversions, caching behavior, and the developer guide for adding new agents, see `TINYFISH_AGENTS.md`.

```
┌──────────────────────────────────────────────────────────┐
│ DATA SOURCES (Updated by TinyFish Agents, 12h TTL cache) │
└──────────────────────────────────────────────────────────┘

┌─────────────────────┐         ┌─────────────────────┐
│ EMA Website         │         │ DEFRA Gov.uk        │
│ (SG grid factor)    │         │ (UK factors)        │
└─────────────────────┘         └─────────────────────┘
          ↓                               ↓
    ┌─────────────────────────────────────┐
    │ TinyFish Headless Browser Agent     │
    │ (admin-triggered via /api/agents,   │
    │  2 runs/hour limit, 12h TTL cache)  │
    └─────────────────────────────────────┘
          ↓                    ↓
    Parse HTML           Parse HTML
    Extract rows         Extract rows
          ↓                    ↓
    ┌────────────────────────────────────┐
    │ Validate & Transform                │
    │ (Per-region min/max bounds; out-of- │
    │  range values discarded, previous   │
    │  good value kept)                   │
    └────────────────────────────────────┘
          ↓
    ┌────────────────────────────────────┐
    │ app/data/emission_factors.json      │
    │ (Updated file)                      │
    │                                     │
    │ {                                   │
    │   "travel": {                       │
    │     "short_haul_flight": {          │
    │       "economy": 0.255,             │
    │       "source": "ICAO 2025",        │
    │       "fetched_at": "2026-03-28"    │
    │     }                               │
    │   }                                 │
    │ }                                   │
    └────────────────────────────────────┘
          ↓
    ┌────────────────────────────────────┐
    │ AgentRunDB (Database)              │
    │                                     │
    │ {                                   │
    │   "agent_name": "sg_grid_factor",  │
    │   "status": "success",             │
    │   "fetched_at": "2026-03-28...",   │
    │   "num_steps": 7,                  │
    │   "run_id": "<tinyfish-run-id>"    │
    │ }                                   │
    └────────────────────────────────────┘
          ↓
    Next calculation uses updated factors
```

---

## 🎬 End-to-End Example Timeline

```
TIME    ACTION                          SYSTEM
────────────────────────────────────────────────────────
14:30   User visits http://localhost:8000
        Sees login form                 Frontend loads

14:31   User registers                  JWT issued
        Redirects to dashboard

14:32   User clicks AI Co-Pilot tab     Chat interface opens

14:33   User types event description    Message sent to API
        "500 person conference..."

14:33   OpenAI function calling         LLM extracts data
        Backend calls openai_service    Structured output

14:34   Emissions calculated            GHG Protocol math
                                        1,941 tCO2e computed

14:34   Chat response returned          Frontend displays
        Shows breakdown + suggestions   Pie chart renders

14:35   User clicks "Create Scenario"   ScenarioDB saved
        Scenario stored                 ID: abc12345

14:36   User views scenario card        Results displayed
        Clicks "Get Suggestions"        AI ideas shown

14:37   User clicks suggestion          Scenario updated
        "Switch 100 to train"           Recalculation: 1,761 tCO2e

14:38   User clicks Financial tab       Financial report loaded
        Sees tax savings for SG         $48.5k liability reduction

14:39   User clicks Carbon Credits      Project catalog loads
        Selects "India Solar"           Selection panel shows

14:40   User enters offset quantity     5,000 tCO2e @ $9 = $45k
        Clicks Purchase                 OffsetPurchaseDB created

14:41   User clicks Compliance tab      Compliance scores load
        Sees GHG Protocol: 92%          Gaps identified

14:42   User exports PDF                PDF generated & download
        Shares with stakeholder         Report sent

────────────────────────────────────────────────────────
Total time: 12 minutes from login to complete offset package
```

---

**CutCarbon System Design — Deterministic. Scalable. Integrated. 🌍**
