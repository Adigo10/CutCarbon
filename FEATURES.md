# CutCarbon Features Overview

## 📋 Features Matrix

### ✅ Core Emission Calculation

| Feature | Description | Data Inputs | Output |
|---------|-------------|-------------|--------|
| **Travel Emissions** | Flight, train, car, bus analysis | Mode, class, attendees, distance, km | tCO2e per segment + total |
| **Venue Energy** | Electricity consumption & grid mix | kWh, m², renewable %, days | tCO2e with renewable reduction |
| **Accommodation** | Hotel & lodging emissions | Type, room-nights, sharing rate | tCO2e per night + total |
| **Catering** | Meal type carbon footprint | Type (vegan/meat), meal count, beverages | tCO2e per meal + total |
| **Waste & Recycling** | Waste diversion & disposal | General waste kg, recycled %, composted % | tCO2e + diversion rate |
| **Equipment & Staging** | Generators, AV, lighting, freight | Stage size, days, generator hours, tonne-km | tCO2e total |
| **Merchandise/Swag** | T-shirts, bags, badges, materials | Item counts, material type | tCO2e per item + total |

### 🎓 Scope Classification

| Scope | Examples | Typical % | Your Control |
|-------|----------|-----------|--------------|
| **Scope 1 (Direct)** | On-site generators, company vehicles | 0-5% | ✓ High (use grid instead) |
| **Scope 2 (Purchased)** | Venue electricity, HVAC | 10-20% | ✓ High (renewable options) |
| **Scope 3 (Indirect)** | Travel, catering, waste, suppliers | 75-90% | ✓ High (modal shifts, menu) |

---

## 🤖 AI & Automation

### Chat Co-Pilot

**Capability**: Natural language event description → Structured scenario

```
Input:
  "500-person tech conf in Singapore, 3 days.
   50% fly from US (biz class), 50% from Asia (economy).
   Marina Bay venue, vegan options available."

Processing:
  • Extracts attendee count, location, duration
  • Interprets travel modes, distances, classes
  • Identifies catering preferences
  • Generates assumptions list

Output:
  • Structured EventScenarioInput object
  • Emissions calculation
  • 3-5 reduction suggestions
  • Optional: Auto-create scenario
```

**Languages supported**: English (primarily)

**Powered by**: OpenAI GPT-4 with function calling

**Smart features**:
- ✅ Context awareness (knows previous scenarios)
- ✅ Handles ambiguous inputs ("international attendees" → calculates mix)
- ✅ Suggests follow-ups ("Want to add accommodation?")
- ✅ Calculates on-the-fly (no need to create scenario first)

---

### TinyFish Web Scrapers (6 Agents)

**Auto-update emission factors daily:**

| Agent | Source | Frequency | Factors Updated |
|-------|--------|-----------|-----------------|
| **EMA** | European Environment Agency | Daily | EU travel, grid mix |
| **DEFRA** | UK Department for Environment | Daily | UK transport, emissions conversions |
| **ICAO** | International Civil Aviation | 2x weekly | Flight RFI multiplier, aviation factors |
| **NEA** | Singapore National Environment | Daily | Singapore grid carbon intensity |
| **Ember Climate** | Global electricity research | Daily | Grid intensity by country |
| **Our World in Data** | Academic datasets | Weekly | Food emissions, general statistics |

**Result**: Your calculations always use latest real-world data

---

## 📊 Dashboard & Visualization

### KPI Cards (Real-time)
- **Total Portfolio Emissions** (tCO2e)
- **Carbon Tax Liability** (USD by region)
- **Compliance Score** (% across frameworks)
- **Offset Coverage** (% of emissions offset)

### Charts (Interactive)
- **Pie chart**: Emissions by category (travel, venue, catering, etc.)
- **Bar chart**: Scenario comparison (baseline vs. optimized)
- **Line chart**: Emissions intensity trend over time
- **Scope breakdown**: Scope 1 vs. 2 vs. 3 stacked view
- **Opportunity chart**: Potential reduction by action (highest impact first)

### Benchmarking
- Per-attendee emissions vs. industry standard
- Per-attendee/day metric
- Percentile ranking (you vs. peers)
- Gap to "best practice" target
- Improvement roadmap

---

## 📋 Scenario Management

### Create Scenarios

**Two modes:**
1. **Basic** → Proxy estimates (fast, ~3 min)
2. **Advanced** → Detailed inputs (thorough, ~10 min)

**Input categories:**
- Event details (name, type, location, attendees, days)
- Travel segments (6+ transport modes, mixed attendee groups)
- Venue energy (region, consumption, renewable %)
- Accommodation (type, room-nights, sharing)
- Catering (meal type, beverage, alcohol, coffee)
- Waste (general, recycled, composted, printed materials)
- Equipment (stage, lighting, sound, AV, generators, freight)
- Merchandise (t-shirts, bags, badges, water bottles, material types)

**Data quality tracking:**
- Estimated (proxy data)
- Partial (mix of supplier + estimate)
- Verified (primary data)

### Edit & Iterate

- **Click Edit** → Modify any parameter
- **Instant recalculation** (< 1 second)
- **Version tracking** (old calculations preserved)
- **Undo/redo** (local browser history)

### Clone & Compare

- **Clone scenario** → Create "what-if" variant
- **Side-by-side comparison** → View metric differences
- **Highlight deltas** → See which changes matter most
- **Export comparison** → Share with team

---

## 💰 Financial Analysis

### Carbon Tax Savings by Region

**Supported regions:**
- 🇸🇬 Singapore (Carbon Tax, $25/tCO2e as of 2026)
- 🇪🇺 EU (ETS - Emissions Trading System, $85-95/tCO2e)
- 🇬🇧 UK (Carbon Price Floor, ~$28/tCO2e)
- 🇦🇺 Australia (ACCUs, ~$65/tCO2e)
- 🇺🇸 USA (Regional + Federal IRA incentives)

**Calculations**:
- Baseline tax liability = total emissions × regional rate
- Reduced tax = reduced emissions × regional rate
- Tax savings = baseline - reduced

### Green Incentives

**Identified automatically** based on:
- Venue green certification (LEED, Green Mark, etc.)
- Renewable energy % (solar, wind, hydro)
- Sustainable catering (organic, local, vegan)
- Material reductions (digital-first, minimal print)
- Carbon neutral claims (if offset 100%)

**Examples**:
- Green Mark certification rebate: $50-150k
- Renewable energy tax credit: 30% of capex
- Carbon neutral event badge: $10-30k brand value
- ESG score improvement: +5-10 percentile points

### ROI Calculator

**Inputs**:
- Cost of reduction actions (venue upgrade, supplier switch, travel incentives)
- Cost of offsets ($3-300/tCO2e depending on project)
- Tax savings
- Incentive rebates
- Brand value (ESG improvement, PR, marketing)

**Output**:
- Payback period (months)
- NPV over 3-5 year horizon
- Cost per tCO2e reduced vs. offset

---

## 🏆 Carbon Offset Portfolio

### Browse Projects

**10+ offset project types**:
1. **Renewable Energy** (solar, wind, hydro) — $8-12/tCO2e
2. **Forestry & Afforestation** — $10-20/tCO2e
3. **REDD+** (avoided deforestation) — $5-15/tCO2e
4. **Cookstove Replacement** — $3-8/tCO2e
5. **Methane Capture** (landfill, livestock) — $2-10/tCO2e
6. **Blue Carbon** (mangroves, wetlands) — $12-25/tCO2e
7. **Direct Air Capture** — $150-300+/tCO2e
8. **Biochar** — $15-40/tCO2e
9. **Enhanced Weathering** — $50-120/tCO2e
10. **Community Energy** — $10-20/tCO2e

**For each project:**
- ✅ Project description & location
- ✅ Carbon price & availability
- ✅ Permanence period (how long offsets are valid)
- ✅ Co-benefits (biodiversity, health, economic)
- ✅ Registries (Gold Standard, VCS, ACR, etc.)
- ✅ Verification date & serial numbers
- ✅ UN Sustainable Development Goals (SDGs) alignment

### Track Portfolio

**Dashboard shows:**
- Total purchased (tCO2e)
- Total retired (tCO2e)
- Total cost (USD)
- Breakdown by project type
- Breakdown by registry
- Coverage ratio (% of emissions offset)

### Purchase & Retire

**Purchase workflow:**
1. Select project type
2. Enter quantity & vintage year
3. Choose registry & price
4. Confirm total cost
5. Credits added to portfolio

**Retire workflow:**
1. Select scenario
2. Choose which credits to apply
3. Confirm retirement (irreversible)
4. Certificate issued (serial number + date)
5. Event marked as "CARBON NEUTRAL ✓"

---

## 🛡️ Compliance & Reporting

### Framework Coverage

#### 1. GHG Protocol
- Scope 1/2/3 and category-level accounting
- Documented assumptions and methodology
- Score: 0-100 (completeness)

#### 2. ISO 20121
- Event sustainability planning and controls
- Resource and supply-chain checks
- Score: 0-100 (framework compliance)

#### 3. SBTi
- 2030/2050 decarbonization pathway checks
- Progress tracking and action guidance
- Score: 0-100 (1.5C alignment)

#### 4. Regional Regulations
- Singapore, EU, UK, and USA carbon policy checks
- Score: 0-100 (regulatory compliance)

### Export Capabilities

**PDF Report**
- Executive summary (key metrics + top actions)
- Emissions and scope breakdown
- Reduction and offset plan
- Compliance status + methodology notes

**Excel Workbook**
- Inputs, calculations, charts, and benchmarks
- Financial and compliance sheets

**JSON Export**
- Re-importable scenario payload + calculations
- API-ready machine-readable format

**CSV Export**
- Key metrics only for quick analysis

---

## 📤 Data & Integration

### Web Scraper Management

**View status of all 6 agents:**
- Last run time
- Status (success/error/skipped)
- Factors updated
- Next scheduled run
- Full error logs (if failed)

**Manual triggers:**
- Force refresh any agent on-demand
- View raw fetched data
- Check data source URLs
- Historical run logs

### API Exports

**REST endpoints** for:
- Creating scenarios via API
- Fetching scenario calculations
- Posting custom emission factors
- Retrieving compliance reports
- Managing offset portfolio

**Authentication**: JWT bearer tokens

**Rate limiting**: 100 req/min per user

---

## 🔐 Authentication & Access Control

### User Management

- **Registration** with email/password
- **Login** with JWT token persistence
- **Password reset** (if configured)
- **Account settings** (profile, preferences)
- **Session timeout** (12 hours default)

### Data Isolation

- **User-specific scenarios** (private by default)
- **User-specific offsets** (private portfolio)
- **No cross-user data leakage**
- **Admin features** (if applicable for multi-tenant)

---

## 🎯 Feature Completeness

### ✅ Implemented

- [x] Emission calculations (all 7 categories)
- [x] Chat AI (OpenAI function calling)
- [x] Scenario CRUD (create, read, update, clone, delete)
- [x] Comparison view (2+ scenarios)
- [x] Financial analysis (tax savings, incentives)
- [x] Compliance scoring (GHG, ISO 20121, SBTi, regional)
- [x] Offset portfolio management (browse, purchase, retire)
- [x] Dashboard visualizations (charts, KPIs, benchmarks)
- [x] Data exports (PDF, Excel, JSON, CSV)
- [x] Web scraper agents (6 sources updating daily)
- [x] Authentication (JWT-based login/register)
- [x] Database persistence (SQLite/Postgres)

### 🟡 Partial / Future

- [ ] Real-time collaboration (multi-user editing)
- [ ] Advanced water footprint (separate from carbon)
- [ ] Biodiversity impact assessment
- [ ] Social impact metrics (jobs created, local community)
- [ ] Blockchain-based carbon credit verification
- [ ] Mobile app (currently web-only)
- [ ] Integration with event management tools (Splash, Splash, Eventbrite)
- [ ] Custom emission factor upload
- [ ] Predictive ML (forecast future event emissions based on history)

---

## 📊 Data Models

### Scenario

```json
{
  "scenario_id": "abc12345",
  "event_name": "TechConf 2025",
  "event_type": "conference",
  "location": "Singapore",
  "attendees": 2500,
  "event_days": 3,
  "mode": "advanced",
  "total_tco2e": 6912.32,
  "per_attendee_tco2e": 2.765,
  "breakdown": {
    "travel": 4147,
    "venue_energy": 1035,
    "accommodation": 385,
    "catering": 1230,
    "waste": 95,
    "equipment": 15,
    "swag": 5
  },
  "scopes": {
    "scope1": 0,
    "scope2": 1035,
    "scope3": 5877
  },
  "assumptions": { /* detailed assumptions */ },
  "data_quality": "estimated",
  "created_at": "2026-03-28T14:30:00Z"
}
```

### Offset Purchase

```json
{
  "id": 1,
  "scenario_id": "abc12345",
  "project_type": "renewable_energy",
  "registry": "gold_standard",
  "quantity_tco2e": 5000,
  "price_per_tco2e_usd": 9.0,
  "total_cost_usd": 45000,
  "vintage_year": 2025,
  "serial_number": "GS-2025-001234",
  "status": "purchased",
  "retired_at": null,
  "created_at": "2026-03-28T15:00:00Z"
}
```

---

## 🎓 Training & Documentation

- **USER_GUIDE.md** → Comprehensive manual (all features explained)
- **QUICK_START.md** → 5-minute intro (essentials only)
- **FEATURES.md** → This file (feature inventory)
- **In-app tooltips** → Hover over `?` icons throughout
- **API Swagger docs** → `/docs` endpoint
- **Chat help** → Ask Co-Pilot directly

---

**CutCarbon — Deterministic. Intelligent. Verified. 🌍**
