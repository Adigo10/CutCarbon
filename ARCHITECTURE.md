# CutCarbon Architecture & User Flow

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    WEB BROWSER                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Alpine.js Single-Page Application               │   │
│  │  (HTML + CSS + JS)                               │   │
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
│  │  ├─ /auth          → Login/register/JWT tokens  │   │
│  │  ├─ /api/chat      → OpenAI function calling    │   │
│  │  ├─ /api/scenarios → CRUD, comparison, cloning  │   │
│  │  ├─ /api/financial → Tax savings, ROI calc      │   │
│  │  ├─ /api/offsets   → Project browse, purchases  │   │
│  │  ├─ /api/compliance→ GHG, ISO20121, SBTi,EU    │   │
│  │  ├─ /api/agents    → Trigger web scrapers       │   │
│  │  └─ /api/exports   → PDF, Excel, JSON downloads │   │
│  └──────────────────────────────────────────────────┘   │
│                        ↕️                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Services (Business Logic)                       │   │
│  │                                                  │   │
│  │  ├─ emissions_engine.py                         │   │
│  │  │  └─ Deterministic GHG Protocol calculations  │   │
│  │  ├─ financial_engine.py                         │   │
│  │  │  └─ Tax, incentives, ROI by region           │   │
│  │  ├─ openai_service.py                           │   │
│  │  │  └─ Chat with function calling               │   │
│  │  └─ tinyfish_agent.py                           │   │
│  │     └─ Web scraper orchestration                │   │
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
│  │  ├─ Emission factors (cached)                   │   │
│  │  └─ Agent run history                           │   │
│  └──────────────────────────────────────────────────┘   │
│         (SQLite local / Postgres production)            │
└─────────────────────────────────────────────────────────┘
                        ↕️  HTTPS
┌─────────────────────────────────────────────────────────┐
│           EXTERNAL SERVICES (Async)                     │
│                                                         │
│  ├─ OpenAI API → GPT-4 function calling               │
│  │  (Extracts event data from chat)                    │
│  │                                                      │
│  ├─ TinyFish Agents (6x Headless Browser)             │
│  │  ├─ EMA ← European Environment Agency               │
│  │  ├─ DEFRA ← UK Department for Environment          │
│  │  ├─ ICAO ← International Aviation                   │
│  │  ├─ NEA ← Singapore National Environment            │
│  │  ├─ Ember Climate ← Global electricity              │
│  │  └─ Our World in Data ← Food emissions              │
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
        │  Check JWT Token        │
        │  (localStorage)         │
        └─────────────────────────┘
                    ↙   ↘
              NO TOKEN  TOKEN EXISTS
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
        New results  3-5 ideas      •ROI
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
                        │ • ISO 20121: 85%     │
                        │ • SBTi: 68%          │
                        │ • Regional: 95%      │
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

Frontend (app.js):
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

OpenAI (GPT-4):
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

Aggregation:
  total = travel + venue + accommodation
          + catering + waste + equipment
        = 1,245 + 310 + 126 + 210 + 35 + 15
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
  "updated_scenario": { ... },
  "suggestions": [
    "Switch 100 attendees from flights to train (-180 tCO2e)",
    "Increase renewable to 80% (-60 tCO2e)",
    ...
  ]
}

Frontend (app.js):
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

User enters:
  Email: user@example.com
  Password: ••••••••

Frontend:
  POST /auth/register
  {
    "email": "user@example.com",
    "password": "plaintext_password"
  }

Backend (routers/auth.py):
  1. Hash password with bcrypt
  2. Create UserDB record
  3. Generate JWT token (HS256, expires 24h)
  4. Return TokenWithUser response

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "created_at": "2026-03-28T14:30:00Z"
  }
}

Frontend:
  1. Extract token
  2. Save to localStorage: cc_token
  3. Redirect to Dashboard

┌──────────────────────────────────────────────────────────┐
│ LOGIN                                                    │
└──────────────────────────────────────────────────────────┘

User enters:
  Email: user@example.com
  Password: ••••••••

Frontend:
  POST /auth/login
  {
    "email": "user@example.com",
    "password": "plaintext_password"
  }

Backend:
  1. Find user by email
  2. Verify password hash against stored hash
  3. If match:
     → Generate JWT token
     → Return TokenWithUser
  4. If mismatch:
     → Return 401 Unauthorized

Frontend:
  1. Save token to localStorage
  2. Redirect to Dashboard

┌──────────────────────────────────────────────────────────┐
│ AUTHENTICATED REQUESTS                                   │
└──────────────────────────────────────────────────────────┘

All API requests include:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

Backend middleware (get_current_user):
  1. Extract token from header
  2. Decode JWT (verify signature)
  3. Extract user_id from payload
  4. Load UserDB from database
  5. If valid: proceed with request
  6. If invalid: return 401 Unauthorized

Example:
  GET /api/scenarios
  Headers: {
    "Authorization": "Bearer eyJ..."
  }

Backend:
  1. Verify token
  2. Query: SELECT * FROM scenarios WHERE user_id = ?
  3. Return only this user's scenarios

┌──────────────────────────────────────────────────────────┐
│ SESSION PERSISTENCE                                      │
└──────────────────────────────────────────────────────────┘

On page reload:
  1. Frontend checks localStorage for cc_token
  2. If present: Include in all API requests
  3. If absent: Redirect to login

Token expiry (24 hours):
  1. Backend includes exp claim in JWT
  2. Upon expiry: 401 response
  3. Frontend redirects to login
  4. User must re-authenticate
```

---

## 📊 Emission Factor Data Flow

```
┌──────────────────────────────────────────────────────────┐
│ DATA SOURCES (Updated by TinyFish Agents Daily)          │
└──────────────────────────────────────────────────────────┘

┌─────────────────────┐         ┌─────────────────────┐
│ EMA Website         │         │ DEFRA Gov.uk        │
│ (EU factors)        │         │ (UK factors)        │
└─────────────────────┘         └─────────────────────┘
          ↓                               ↓
    ┌─────────────────────────────────────┐
    │ TinyFish Headless Browser Agent     │
    │ (Scrapes daily @ 2:00 UTC)          │
    └─────────────────────────────────────┘
          ↓                    ↓
    Parse HTML           Parse HTML
    Extract rows         Extract rows
          ↓                    ↓
    ┌────────────────────────────────────┐
    │ Validate & Transform                │
    │ (Compare with previous version)     │
    │ (Flag if >5% change = outlier)     │
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
    │   "agent_name": "EMA",             │
    │   "status": "success",             │
    │   "fetched_at": "2026-03-28...",   │
    │   "num_updates": 12,               │
    │   "notes": "EU train factors..."   │
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

14:33   OpenAI function calling         GPT-4 extracts data
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
