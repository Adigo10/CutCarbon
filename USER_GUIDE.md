# CutCarbon EventCarbon Co-Pilot — Complete User Guide

**Version**: 2.0
**Last Updated**: March 2026

---

## 📚 Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Core Features](#core-features)
4. [User Journey](#user-journey)
5. [Feature Deep-Dives](#feature-deep-dives)
6. [Compliance & Standards](#compliance--standards)
7. [FAQs & Troubleshooting](#faqs--troubleshooting)

---

## Overview

**CutCarbon** is an AI-powered event carbon accounting platform that helps planners, sustainability teams, and corporate hosts:
- **Calculate** precise carbon emissions for events (travel, venue, accommodation, catering, waste, equipment)
- **Reduce** emissions with smart suggestions aligned to GHG Protocol standards
- **Finance** carbon reductions with tax savings, incentives, and ROI analysis
- **Offset** residual emissions through verified carbon credit projects
- **Report** on compliance with frameworks like GHG Protocol, ISO 20121, SBTi, and regional regulations

The app combines **three power sources**:
- 🔬 **Deterministic emissions calculations** (GHG Protocol methodology)
- 🤖 **OpenAI function calling** for natural language event data extraction
- 🌐 **TinyFish web agents** for live emission factor updates from authoritative sources

---

## Getting Started

### 1. Access the Platform

- **URL**: `http://localhost:8000`
- **Swagger API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

### 2. Create an Account

Navigate to the **Login/Register** screen:

```
┌─────────────────────────────┐
│   EventCarbon Co-Pilot      │
├─────────────────────────────┤
│ Email:        ___________   │
│ Password:     ___________   │
│                             │
│    [Register]  [Login]      │
└─────────────────────────────┘
```

- **Register**: Enter email & password. Account is created instantly.
- **Login**: Existing users log in with email & password.
- **Token**: JWT tokens are stored in `localStorage` for session persistence.

### 3. Your Dashboard Loads

After login, you see the **Dashboard** tab with:
- Portfolio overview (all your scenarios at a glance)
- Carbon footprint breakdown by source
- Savings opportunities
- Compliance scores
- Reduction pathway over time

---

## Core Features

CutCarbon is organized into **7 tabs** in the main navigation:

| Tab | Icon | Purpose | Key Actions |
|-----|------|---------|-------------|
| **Dashboard** | 📊 | Portfolio overview | View aggregate metrics, charts, trends |
| **AI Co-Pilot** | 🤖 | Chat-based scenario builder | Describe events in plain English; AI extracts data |
| **Scenarios** | 📋 | Manage emission scenarios | Create, edit, clone, compare scenarios side-by-side |
| **Financial** | 💰 | Carbon pricing & ROI | View tax savings, incentives, payback periods |
| **Carbon Credits** | 🏆 | Offset management | Browse projects, track purchases, retire credits |
| **Compliance** | 🛡️ | Regulatory reporting | GHG Protocol, ISO 20121, SBTi, regional scores |
| **Data & Exports** | 📤 | Download & agent status | Excel/JSON exports, web scraping history |

---

## User Journey

### 🎯 Typical Workflow

```
1. CREATE EVENT
   └─> Use Chat OR Scenarios tab to input event details

2. CALCULATE EMISSIONS
   └─> System auto-calculates based on inputs
   └─> Breakdown by source: travel, venue, catering, etc.

3. ANALYZE RESULTS
   └─> View Dashboard charts & benchmarks
   └─> Compare to industry standards

4. FIND REDUCTIONS
   └─> Get AI-powered suggestions
   └─> Adjust travel mode, catering, renewables, etc.

5. CALCULATE FINANCIAL IMPACT
   └─> See carbon tax savings by region
   └─> View green incentives & ROI

6. OFFSET RESIDUALS
   └─> Select verified carbon credit projects
   └─> Track purchases & retirements

7. REPORT & COMPLY
   └─> Export reports for stakeholders
   └─> Score against compliance frameworks
```

### 📍 Example: Plan a 3-Day Tech Conference

**Step 1: Open AI Co-Pilot**
```
You:  "I'm planning TechConf Asia, 2,500 attendees from
       USA, Europe, Asia over 3 days in Singapore.
       What's the carbon footprint?"

Co-Pilot: "Let me analyze that. I see:
  • International travel mix (flights + train options)
  • Singapore venue with 45,000 m²
  • 3 days of catering for 2,500 people

  Would you like me to create an advanced scenario
  or use basic mode?"
```

**Step 2: Review Calculations**
- Co-Pilot extracts structured data and calculates emissions
- You see breakdown: Travel (60%), Venue (15%), Catering (20%), Other (5%)
- Total: 6,912 tCO2e | Per-attendee: 2.77 tCO2e

**Step 3: Find Reductions**
```
Suggestions:
✓ Switch 200 attendees from flights to train → -45 tCO2e
✓ Increase renewable venue energy by 20% → -180 tCO2e
✓ Vegan meals for 30% of catering → -120 tCO2e
✓ Digital-first materials (no printed programs) → -15 tCO2e
```

**Step 4: Financial Analysis**
```
Baseline: 6,912 tCO2e → $412k tax liability (Singapore)
After reductions: 5,552 tCO2e → $333k liability
Savings: $79k USD + tax incentives
ROI: 4.2 months
```

**Step 5: Offset Remaining Emissions**
```
Offset portfolio:
• 5,000 tCO2e → Renewable energy projects (India)
  Cost: $45k USD (Gold Standard, $9/tCO2e)
• 500 tCO2e → Forestry/reforestation (Indonesia)
  Cost: $6.5k USD (VCS, $13/tCO2e)

Total offset cost: $51.5k USD
```

**Step 6: Export Report**
```
✓ Download scenario as PDF
✓ Share compliance scorecard (GHG Protocol: 92%)
✓ Generate stakeholder presentation
```

---

## Feature Deep-Dives

### 🤖 AI Co-Pilot (Chat Tab)

**What it does:**
- Understands natural language descriptions of events
- Extracts structured data (attendees, travel, venue, catering, dates)
- Generates reduction suggestions
- Refines scenarios based on follow-up questions

**How to use:**

```
Start suggestions (click any):
→ "Plan a 3-day tech conference in Singapore, 500 attendees, hybrid"
→ "Estimate emissions for 200 delegates flying from Europe to London"
→ "What is the carbon impact of switching our gala dinner to vegan?"
```

Type your own description:
```
"We're hosting a 500-person corporate retreat in London
for 2 days. Half are flying from NYC (business class),
half from European cities via train. We want vegan catering
and carbon-neutral accommodation."
```

**AI outputs:**
1. **Extracted Data** — Structured event parameters
2. **Reply** — Plain English confirmation + clarifying questions
3. **Suggestions** — 3-5 reduction options with impact estimates
4. **Updated Scenario** — Ready to view in Scenarios tab

**Key Functions:**
- ✅ Extracts event details from text descriptions
- ✅ Suggests transport mode changes
- ✅ Recommends meal switches (red meat → vegan)
- ✅ Identifies equipment minimization
- ✅ Estimates renewable energy potential

---

### 📋 Scenarios Tab

**Create a Scenario (Manual)**

Click **+ New Scenario** → Fill form:

```
EVENT BASICS
├─ Event Name: TechConf 2025
├─ Event Type: Conference
├─ Location: Singapore
├─ Attendees: 2,500
├─ Duration: 3 days
└─ Mode: Advanced (detailed) vs Basic (estimates)

TRAVEL (Add segments)
├─ Long-haul flights: 600 attendees, 13,600 km, business class
├─ Short-haul flights: 400 attendees, 2,500 km, economy
├─ Train/rail: 100 attendees, 1,200 km
└─ Local transport: 500 attendees, MRT, 25 km

VENUE
├─ Grid region: Singapore
├─ Energy consumed: 22,500 kWh over 3 days
├─ Area: 45,000 m²
└─ Renewable %: 65% (solar, wind)

ACCOMMODATION
├─ Type: Standard hotel
├─ Room nights: 5,000
└─ Sharing: 1 person/room

CATERING
├─ Type: Local organic
├─ Meals: 12,500 (3 days × 2,500 attendees × 1.67 meals/day)
├─ Beverages: Yes
├─ Alcohol: Yes
└─ Coffee/tea cups: 5,000

WASTE & MATERIALS
├─ General waste: 3,750 kg
├─ Recycled: 6,250 kg
├─ Composted: 2,500 kg
├─ Printed materials: No (digital-first)
└─ Exhibition booths: 5,000 m²

EQUIPMENT & STAGING
├─ Stage: 500 m²
├─ Lighting: 3 days
├─ Sound system: 3 days
├─ LED screens: 200 m²
├─ Projectors: 12
├─ Generators: 0 hours (grid-powered)
└─ Freight: 45 tonne-km

MERCHANDISE
├─ T-shirts: 2,500 (organic cotton)
├─ Tote bags: 2,500
├─ Badges: 2,500 (recycled plastic)
├─ Notebooks: 0
└─ Water bottles: 0 (refill stations)
```

**Results Display:**

```
┌─ SCENARIO: TechConf 2025 ────────────────────┐
│                                               │
│  Total Emissions: 6,912.32 tCO2e              │
│  Per Attendee: 2.77 tCO2e                     │
│  Per Attendee/Day: 0.92 tCO2e                 │
│                                               │
│  Breakdown:                                   │
│  ├─ Travel: 4,147 tCO2e (60%)  [🔵]          │
│  ├─ Venue Energy: 1,035 tCO2e (15%)  [🟢]    │
│  ├─ Accommodation: 385 tCO2e (6%)  [🟠]      │
│  ├─ Catering: 1,230 tCO2e (18%)  [🔴]        │
│  ├─ Waste: 95 tCO2e (1%)  [🟣]               │
│  └─ Equipment & Swag: 20 tCO2e (<1%)  [🩷]   │
│                                               │
│  Scope 1 (Direct): 0 tCO2e                   │
│  Scope 2 (Electricity): 1,035 tCO2e          │
│  Scope 3 (Indirect): 5,877 tCO2e             │
│                                               │
│  Benchmark: Above average (high travel)      │
│  Data Quality: Estimated (could verify)      │
│                                               │
│  [Edit] [Clone] [Compare] [Get Suggestions]  │
└──────────────────────────────────────────────┘
```

**Scenario Actions:**

- **Edit** — Modify parameters and recalculate
- **Clone** — Create a copy for "what-if" analysis
- **Compare** — Side-by-side view with other scenarios
- **Suggestions** — AI-generated reduction strategies
- **Financial Analysis** — Tax savings for this scenario
- **Compliance Report** — Score against frameworks
- **Export** — Download as PDF, Excel, JSON

**Scenario Comparison:**

```
┌─────────────────────────┬──────────┬──────────┐
│ Metric                  │ Baseline │ Optimized│
├─────────────────────────┼──────────┼──────────┤
│ Total Emissions         │ 6,912    │ 4,865    │
│ Per Attendee            │ 2.77     │ 1.95     │
│ Travel (% of total)     │ 60%      │ 42%      │
│ Renewables %            │ 65%      │ 85%      │
│ Vegan meals %           │ 0%       │ 35%      │
│ Offset cost @ $12/tCO2e │ $82.9k   │ $58.4k   │
│ Tax savings (SG)        │ -$412k   │ -$291k   │
└─────────────────────────┴──────────┴──────────┘
```

---

### 💰 Financial Tab

**Calculate Carbon Tax Savings**

Select a scenario → Click **Get Financial Analysis**:

```
REGIONAL TAX SCHEMES
├─ Singapore (Carbon Tax)
│  └─ Rate: $25/tCO2e (as of 2026)
│  └─ Baseline tax: 6,912 × $25 = $172.8k
│  └─ After reduction: 4,865 × $25 = $121.6k
│  └─ Tax savings: $51.2k
│
├─ EU ETS (Emissions Trading System)
│  └─ Effective rate: $85-95/tCO2e
│  └─ Baseline: 6,912 × $90 = $621.1k
│  └─ After reduction: 4,865 × $90 = $437.8k
│  └─ Tax savings: $183.3k
│
├─ UK Carbon Price Floor
│  └─ Rate: $28-32/tCO2e + VAT
│  └─ Baseline: $216.9k
│  └─ After reduction: $155.7k
│  └─ Tax savings: $61.2k
│
└─ USA (Regional initiatives)
   └─ California CARB: $30/tCO2e
   └─ Northeastern RGGI: $15/tCO2e
   └─ Federal IRA incentives: up to $180/tCO2e
```

**Green Incentives & ROI**

```
AVAILABLE INCENTIVES (Singapore)
├─ Green Mark Certification (Building)
│  └─ Rebate: $50k-150k (if venue is Green Mark Gold+)
│
├─ Carbon Neutral Event Badge
│  └─ Marketing value: $25k-75k (brand lift, PR)
│
├─ Sustainability Reporting Credits
│  └─ ESG points: Counts toward corporate targets
│  └─ Value: $15-30 per basis point
│
└─ Renewable Energy Premium
   └─ Solar offset: $5-8k for 85%+ renewable mix

COST BREAKDOWN
├─ Emission reduction actions: $45k
│  └─ Venue upgrade to renewable: $20k
│  └─ Catering supplier switch: $8k
│  └─ Travel incentives (train subsidies): $12k
│  └─ Digital materials conversion: $5k
│
├─ Carbon credit purchases: $58.4k
│  └─ 4,865 tCO2e @ $12/tCO2e average
│
└─ Total event carbon cost: $103.4k

FINANCIAL IMPACT
├─ Gross carbon tax avoided: $51.2k
├─ Incentive rebates: $75k
├─ ESG valuation uplift: $30k
├─ Brand reputation (PR): $40k
└─ NET BENEFIT: $92.8k saved vs. baseline

ROI: 6.2 months (payback period)
```

**Energy Cost Savings** (if applicable)

```
If switching to renewable/efficient venue:
├─ Original venue: 22,500 kWh @ $0.25/kWh = $5,625
├─ Efficient venue: 15,000 kWh @ $0.22/kWh = $3,300
└─ Savings: $2,325 + ~500 kg CO2e reduced
```

**Compliance Value**

```
Reporting frameworks often require carbon accounting.
Showing proactive emission reductions:
├─ GHG Protocol Scope 3 coverage: +15 points
├─ ISO 20121 compliance: +20 points
├─ SBTi science-based target progress: +25 points
└─ ESG score improvement: ~5-10% lift
```

---

### 🏆 Carbon Credits Tab

**Browse Offset Projects**

Available project types (with pricing & co-benefits):

```
RENEWABLE ENERGY (Solar, Wind, Hydro)
├─ Average price: $8-12 per tCO2e
├─ Permanence: Ongoing energy displaced
├─ Co-benefits: Rural electrification, job creation
├─ Registries: Gold Standard, VCS, ACR
├─ Best for: Large-scale offsets, quick deployment
├─ Example: India solar farm project
│  └─ Price: $9/tCO2e
│  └─ Volume: 5,000+ tCO2e available
│  └─ Verified until: 2045

FORESTRY & AFFORESTATION
├─ Average price: $10-20 per tCO2e
├─ Permanence: 20-40 years (replanting cycles)
├─ Co-benefits: Biodiversity, water retention, jobs
├─ Registries: Verra, Gold Standard, Plan Vivo
├─ Best for: Long-term commitments, branding
├─ Example: Indonesian reforestation project
│  └─ Price: $13/tCO2e
│  └─ Volume: 2,000+ tCO2e available
│  └─ Verified until: 2050

REDD+ (Reducing Emissions from Deforestation)
├─ Average price: $5-15 per tCO2e
├─ Permanence: Prevented forest loss (30+ years)
├─ Co-benefits: Indigenous rights, biodiversity
├─ Registries: VCS, Verra, Gold Standard
├─ Best for: High-impact, low-cost options
├─ Example: Amazon forest protection (Brazil)
│  └─ Price: $8/tCO2e
│  └─ Volume: 10,000+ tCO2e available

COOKSTOVE REPLACEMENT (Sub-Saharan Africa)
├─ Average price: $3-8 per tCO2e
├─ Permanence: Cookstoves last 5-10 years
├─ Co-benefits: Health (reduced indoor air pollution)
├─ Registries: Gold Standard, VCS
├─ Best for: Community impact, social value
├─ Example: Rwanda cookstove distribution
│  └─ Price: $5/tCO2e
│  └─ Volume: 1,000+ tCO2e available

METHANE CAPTURE (Landfill, Livestock)
├─ Average price: $2-10 per tCO2e
├─ Permanence: Immediate, ongoing
├─ Co-benefits: Energy generation, pollution control
├─ Registries: Gold Standard, ACR
├─ Best for: Quick wins, cost efficiency
├─ Example: Mexico landfill gas-to-energy
│  └─ Price: $4/tCO2e
│  └─ Volume: 5,000+ tCO2e available

BLUE CARBON (Coastal wetlands, mangroves)
├─ Average price: $12-25 per tCO2e
├─ Permanence: Long-term sediment storage
├─ Co-benefits: Coastal protection, fisheries
├─ Registries: Gold Standard, Verra
├─ Best for: Premium branding, ecosystem restoration
├─ Example: Indonesia mangrove restoration
│  └─ Price: $18/tCO2e
│  └─ Volume: 500+ tCO2e available

DIRECT AIR CAPTURE (Industrial Carbon Removal)
├─ Average price: $150-300+ per tCO2e
├─ Permanence: Permanent storage (geological)
├─ Co-benefits: Tech innovation, scalability
├─ Registries: Puro.earth, Carbon Trust
├─ Best for: Premium, technology-focused brands
├─ Example: Swiss DAC facility
│  └─ Price: $200/tCO2e
│  └─ Volume: 100+ tCO2e available
```

**Track Your Portfolio**

```
┌─ CARBON OFFSET PORTFOLIO ────────────────┐
│                                          │
│ Total Purchased: 15,000 tCO2e            │
│ Total Retired: 8,500 tCO2e (57%)         │
│ Total Pending: 6,500 tCO2e (43%)         │
│ Total Spent: $156,200 USD                │
│                                          │
│ BY PROJECT TYPE                          │
│ ├─ Renewable Energy: 8,000 tCO2e @ $72k  │
│ ├─ Forestry: 4,500 tCO2e @ $58.5k        │
│ ├─ REDD+: 1,500 tCO2e @ $12k             │
│ └─ Cookstove: 1,000 tCO2e @ $4.2k        │
│                                          │
│ BY REGISTRY                              │
│ ├─ Gold Standard: 8,000 tCO2e            │
│ ├─ VCS/Verra: 5,000 tCO2e                │
│ └─ ACR: 2,000 tCO2e                      │
│                                          │
│ COVERAGE RATIO                           │
│ ├─ TechConf Asia 2025: 68% covered       │
│ ├─ AusFest 2025: 45% covered             │
│ └─ Portfolio target: 75% by Dec 2026     │
│                                          │
│ [Add Purchase] [Retire Credits] [Guidance]
└──────────────────────────────────────────┘
```

**Purchase Workflow**

1. Click **+ Add Purchase**
2. Select project type & registry
3. Enter quantity & vintage year
4. Confirm price & total cost
5. Credits tracked in portfolio

**Retire Credits**

Retiring = Claiming the offset benefit for a specific event.

```
Event: TechConf Asia 2025 (6,912 tCO2e)
┌─────────────────────────────────────────┐
│ Offset with:                            │
│ ├─ 4,000 tCO2e: India solar farm        │
│ │  Registry: Gold Standard               │
│ │  Vintage: 2025                         │
│ │  Serial: GS-2025-001234                │
│ │  Cost: $36k                            │
│ │                                        │
│ ├─ 2,000 tCO2e: Indonesia reforestation│
│ │  Registry: Verra                       │
│ │  Vintage: 2025                         │
│ │  Serial: VCS-2025-005678               │
│ │  Cost: $26k                            │
│ │                                        │
│ └─ 912 tCO2e: Rwanda cookstove          │
│    Registry: Gold Standard               │
│    Vintage: 2024                         │
│    Serial: GS-2024-009012                │
│    Cost: $4.5k                           │
│                                          │
│ Total Retired: 6,912 tCO2e               │
│ Total Cost: $66.5k                       │
│ Status: CARBON NEUTRAL ✓                 │
│                                          │
│ [Confirm & Issue Certificate]            │
└─────────────────────────────────────────┘
```

---

### 🛡️ Compliance Tab

**Framework Overview**

CutCarbon evaluates your scenarios against 4 major frameworks:

#### 1. **GHG Protocol** (Most Common)

```
Framework: GHG Corporate Accounting & Reporting Standard

Scope Coverage:
├─ Scope 1 (Direct): Company-owned equipment, generators
├─ Scope 2 (Purchased): Venue electricity
└─ Scope 3 (Indirect): Travel, catering, accommodation, waste

Your Score: 92/100 ✓

Strengths:
✓ Comprehensive travel emissions captured
✓ Venue energy with renewable calculation
✓ Catering & waste included
✓ All Scope 3 categories covered

Gaps:
⚠ Need verified supplier data for catering carbon factors
⚠ Equipment freight (Scope 3.9) requires clarification

Recommendations:
→ Request carbon footprint from venue operator
→ Engage catering supplier for verified food emissions data
→ Conduct Scope 3 assessment per GHG Protocol guidance
```

#### 2. **ISO 20121** (Event Sustainability)

```
Framework: ISO 20121:2012 Event Sustainability Management

Key Requirements:
├─ Environmental impact identification
├─ Stakeholder engagement
├─ Resource efficiency (energy, water, waste)
├─ Supply chain management
└─ Stakeholder satisfaction monitoring

Your Score: 85/100

Compliance Checklist:
✓ Environmental policy documented
✓ Energy consumption tracked
✓ Waste management plan
✓ Supplier code of conduct
✓ Post-event review process
⚠ Water consumption not tracked (event may not require)
⚠ Stakeholder feedback system needs formalization

Recommendations:
→ Implement water metering if venue allows
→ Formalize stakeholder feedback survey
→ Create waste diversion target (>75%)
→ Develop green procurement policy
```

#### 3. **Science-Based Targets Initiative (SBTi)**

```
Framework: SBTi - Net Zero Event Standard

Net Zero Pathway Requirement:
├─ 50% emissions reduction by 2030 (baseline 2025)
├─ 100% emissions reduction by 2050
├─ 100% offset of residual emissions

Your Progress: 68% aligned

2025 Baseline: 6,912 tCO2e
├─ 2026 Target: 6,912 tCO2e (maintain/reduce)
├─ 2028 Target: 5,735 tCO2e (-17%)
├─ 2030 Target: 3,456 tCO2e (-50%)
└─ 2050 Target: 0 tCO2e (or fully offset)

Recommended Actions:
→ Set annual reduction targets (5-7% per year)
→ Shift travel mode: 25% fewer flights by 2027
→ 100% renewable venue energy by 2028
→ Net Zero through offsets + reductions by 2030
```

#### 4. **Regional Regulations**

```
SINGAPORE (Carbon Tax from 2024)
├─ Scope: Direct & indirect emissions
├─ Rate: $25/tCO2e (escalating to $50-80 by 2030)
├─ Reporting: Annual mandatory for >25k tCO2e
├─ Your status: ✓ COMPLIANT

EU (Carbon Border Adjustment Mechanism)
├─ Scope: Goods imported into EU
├─ Rate: Variable (indexed to ETS)
├─ Applicability: If catering/materials sourced from outside EU
├─ Your status: ? REQUIRES ASSESSMENT

UK (Carbon Price Floor)
├─ Scope: UK operations
├─ Rate: £19.53 + VAT = ~$25/tCO2e
├─ Applicability: If event is in UK
├─ Your status: N/A (event in Singapore)

USA (IRA & Regional Schemes)
├─ Scope: Renewable energy tax credits
├─ Incentive: 30% investment tax credit
├─ Applicability: Venue renewable upgrade
├─ Your status: $6k potential savings (if applicable)
```

**Compliance Export**

```
[Generate Compliance Report]
├─ Overall Score: 88/100 ✓
├─ Frameworks aligned: 4/4
├─ Next audit date: Q2 2026
├─ Export as: PDF | JSON | Excel
```

---

### 📤 Data & Exports Tab

**Download Scenarios**

```
Export formats:
├─ PDF (Stakeholder report)
│  └─ Includes: Summary, charts, assumptions, methodology
├─ Excel (Detailed data)
│  └─ Includes: All inputs, calculations, benchmarks
├─ JSON (API integration)
│  └─ Includes: Full scenario payload for re-import
└─ CSV (Quick analysis)
   └─ Includes: Key metrics only
```

**Web Scraping Agent Status**

CutCarbon runs **6 autonomous agents** to keep emission factors up-to-date:

```
AGENT STATUS
├─ EMA (European Environment Agency)
│  ├─ Last run: 2 hours ago ✓
│  ├─ Status: Completed
│  ├─ Factors updated: Travel modes (EU)
│  └─ Next run: 24h
│
├─ DEFRA (UK Department for Environment)
│  ├─ Last run: 15 hours ago ✓
│  ├─ Status: Completed
│  ├─ Factors updated: UK travel, electricity
│  └─ Next run: 12h
│
├─ ICAO (International Civil Aviation)
│  ├─ Last run: 4 hours ago ✓
│  ├─ Status: Completed
│  ├─ Factors updated: Flight emissions calculator
│  └─ Next run: 48h
│
├─ NEA (Singapore National Environment)
│  ├─ Last run: 8 hours ago ✓
│  ├─ Status: Completed
│  ├─ Factors updated: Singapore grid mix
│  └─ Next run: 24h
│
├─ Ember Climate (Electricity data)
│  ├─ Last run: 6 hours ago ✓
│  ├─ Status: Completed
│  ├─ Factors updated: Global grid intensity
│  └─ Next run: 24h
│
└─ Our World in Data (Food, general stats)
   ├─ Last run: 12 hours ago ✓
   ├─ Status: Completed
   ├─ Factors updated: Catering emissions
   └─ Next run: 48h

[Trigger Manual Refresh] [View Full History]
```

**Agent Run History**

```
View detailed logs of what each agent fetched:

Run ID: agent-run-2026-03-28-14:23
├─ Agent: ICAO
├─ Source: https://www.icao.int/environmental-protection/...
├─ Data fetched: Flight RFI multiplier (1.9)
├─ Status: Success
├─ Timestamp: 2026-03-28 14:23:45 UTC
├─ Notes: Updated long-haul flight factors
│
Run ID: agent-run-2026-03-28-12:45
├─ Agent: DEFRA
├─ Source: https://www.gov.uk/government/publications/ghg-conversion-factors-for-company...
├─ Data fetched: Train & road transport factors
├─ Status: Success
├─ Timestamp: 2026-03-28 12:45:22 UTC
├─ Notes: Train factors decreased by 2% (grid improvement)
```

---

## Compliance & Standards

### 📋 GHG Protocol Scope Definitions

Your events typically cover all three scopes:

**Scope 1 (Direct)**
- Generators run at venue
- Company-owned vehicles
- Fossil fuel combustion on-site
- *Usually small for events*

**Scope 2 (Purchased Energy)**
- Venue electricity
- Heating/cooling
- Lighting
- AV equipment power
- *Reduced with renewable%*

**Scope 3 (Indirect)**
- **Category 6**: Employee commuting
- **Category 7**: Employee business travel (flights, trains, cars)
- **Category 9**: Upstream transportation of goods
- **Category 11**: Use of products sold (catering waste decomposition)
- **Category 12**: End-of-life treatment of waste
- *Largest scope for events*

### 🎯 Data Quality Levels

Scenarios are marked as:

| Level | Definition | Example |
|-------|-----------|---------|
| **Estimated** | Derived from proxy data | "500 attendees from USA → assume average 13,600 km flight" |
| **Partial** | Mix of supplier data + estimates | "Venue energy verified, catering from menu estimates" |
| **Verified** | Primary data from suppliers | "Actual kWh consumption, invoiced travel, certified organic catering" |

To improve data quality:
1. Request emissions reports from venue, caterer, transport providers
2. Use actual consumption data (energy meters, travel bookings)
3. Engage suppliers with ISO 14064 certification

### 📊 Benchmark Comparisons

Your per-attendee/day emissions are scored:

```
INDUSTRY BENCHMARKS (per attendee/day)
├─ Tech conference: 0.4-1.2 tCO2e/attendee/day
├─ Trade show: 0.8-2.0 tCO2e/attendee/day
├─ Music festival: 0.6-1.5 tCO2e/attendee/day
├─ Corporate retreat: 0.3-0.8 tCO2e/attendee/day
└─ Gala dinner: 0.1-0.3 tCO2e/attendee/day

Your Score: 0.92 tCO2e/attendee/day
Category: Tech Conference
Percentile: 75th (above average due to international travel)

Gap to Best Practice (0.4): +130%
→ Opportunity: Reduce flights by 25%, switch 40% to vegan
→ Potential reduction: 0.55 tCO2e/attendee/day (40% lower)
```

---

## FAQs & Troubleshooting

### ❓ General Questions

**Q: What does "carbon footprint" mean?**
A: Total greenhouse gas emissions (in CO2 equivalent) caused by your event. Includes CO₂, CH₄, N₂O, F-gases, all expressed as tCO2e (tonnes CO2 equivalent).

**Q: Why is my travel emissions so high?**
A: Long-haul flights dominate event emissions. A single transatlantic flight (US ↔ Europe) generates ~1 tCO2e per person. If 50% of attendees fly long-haul, that's easily 40-60% of total emissions.

**Q: How much does it cost to offset my event?**
A: Depends on emission reduction amount + offset project type:
- Best case: $3-5 per tCO2e (cookstove, methane capture)
- Mid-range: $8-15 per tCO2e (renewable energy, forestry)
- Premium: $20-300 per tCO2e (blue carbon, DAC)

**Q: Can my event be "carbon neutral"?**
A: Yes, through:
1. Reducing emissions as much as possible
2. Offsetting 100% of remaining emissions with verified credits

Example: 6,912 tCO2e event → Reduce to 5,000 → Offset remaining 5,000 = Carbon Neutral ✓

**Q: Is data automatically updated?**
A: Yes! TinyFish agents refresh emission factors from official sources 1-2x daily. Your calculations always use the latest data.

---

### 🛠️ Troubleshooting

**Q: Chat AI doesn't understand my event description.**
A: Try being more specific:
- ❌ "International conference"
- ✓ "500-person tech conference in London, 2 days, 200 from US (flights), 200 from EU (train), 100 local"

**Q: Emissions seem too high/low. Why?**
A: Check these factors:
- Travel: How many attendees flew? What distance? Business class increases by 2x.
- Venue: Renewable % changes emissions by 30-40%.
- Catering: Red meat is 2-3x higher than vegan.
- Duration: Longer events = more accommodation energy.

**Q: Can I edit a scenario after creation?**
A: Yes! Click **Edit** on any scenario. Recalculations are instant.

**Q: How do I know my offset project is legitimate?**
A: Check:
- ✓ Registry: Gold Standard, VCS/Verra, ACR, Plan Vivo, Puro.earth
- ✓ Vintage year: Credits must be from current/recent years
- ✓ Verification date: Should be ≤2 years old
- ✓ Serial number: Unique per credit batch

**Q: Can I export scenarios to share with colleagues?**
A: Yes! Download as:
- PDF (best for stakeholders)
- Excel (for analysis)
- JSON (for developers)

---

### 🔐 Data Privacy & Security

- **Authentication**: JWT tokens, secure password hashing
- **Storage**: Encrypted database (SQLite locally, Postgres-ready for production)
- **Calculations**: All deterministic (no external API calls except OpenAI for chat)
- **Agent data**: Emission factors are public sources, no PII collected
- **User scenarios**: Private to authenticated user account

---

### 📞 Support & Feedback

- **Docs**: This guide + inline tooltips throughout app
- **API Docs**: `/docs` endpoint (Swagger/OpenAPI)
- **Feedback**: Report issues or suggest features via GitHub
- **Contact**: sustainability@cutcarbon.co

---

## Quick Reference Card

```
WORKFLOW CHECKLIST

□ Register & login
□ Open Dashboard → Get oriented
□ Create first scenario (Chat OR Manual)
□ View emissions breakdown
□ Get reduction suggestions
□ Compare baseline vs. optimized
□ Calculate financial impact
□ Select offset projects
□ Retire offsets to claim carbon neutral
□ Export report for stakeholders
□ Review compliance score
```

---

**Happy carbon accounting! 🌍🌱**

*CutCarbon — EventCarbon Co-Pilot v2.0*
*Deterministic emissions. Intelligent reduction. Verified offsets.*
