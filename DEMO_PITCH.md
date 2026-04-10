# CutCarbon — Demo Pitch

## The Problem (30 seconds)

Event organizers are under growing pressure to report carbon emissions — from corporate ESG mandates, ISO 20121 compliance, and carbon pricing regulations in Singapore, the EU, and the UK. But today, calculating an event's footprint means spreadsheets, outdated government PDFs, and a sustainability consultant charging $5,000 to do math.

**The result**: Most events either skip reporting entirely, or report numbers that are months out of date.

---

## The Solution (30 seconds)

**CutCarbon** is an AI-powered event carbon accounting platform. In under 2 minutes, an event planner can:

1. **Describe** their event in plain English → AI extracts structured data
2. **Calculate** Scope 1/2/3 emissions using GHG Protocol methodology
3. **Reduce** — get ranked reduction suggestions with exact impact
4. **Offset** — purchase and retire verified carbon credits in-app
5. **Report** — export a compliance-ready PDF or Excel in one click

Emission factors update automatically via 10 live data agents pulling from EMA, DEFRA, EPA, ICAO, and other authoritative sources — so calculations are always current.

---

## Live Demo (3 minutes)

### Step 1 — Chat input (45s)
> Open the **AI Co-Pilot** tab and type:
>
> *"500-person tech conference in Singapore, 3 days. Half fly from the US in business class, half from Southeast Asia in economy. Marina Bay Sands venue, vegan catering options available."*

The AI extracts attendee counts, distances, travel classes, and catering preferences, runs the GHG Protocol math, and returns a full breakdown — **6,912 tCO₂e total, 2.76 tCO₂e/attendee**.

### Step 2 — Dashboard (30s)
> Switch to the **Dashboard** tab.

Show the pie chart (travel dominates at ~60%), the carbon tax liability card ($172k at Singapore rates), and the compliance score.

### Step 3 — Reduction suggestions (30s)
> Click **Get Suggestions** on the scenario.

Top suggestion: shift 20% of US attendees to virtual → saves 830 tCO₂e, $20k in tax. One click applies it and recalculates.

### Step 4 — Financial tab (30s)
> Open the **Financial** tab.

Show tax savings by region — the same event in the EU carries a $580k ETS liability. Show the green incentive match: a LEED-certified venue unlocks a $50k rebate.

### Step 5 — Offset & export (45s)
> Open **Carbon Credits**, purchase a recommended mix, retire the credits.

Event is marked **CARBON NEUTRAL**. Switch to **Data & Exports**, download the PDF report. Show the agent status panel — 10 data sources, all green, last refreshed 6 hours ago.

---

## Key Numbers

| Metric | Value |
|---|---|
| Time to first calculation | < 2 minutes |
| Emission categories covered | 7 (travel, venue energy, accommodation, catering, waste, equipment, merchandise) |
| Compliance frameworks | GHG Protocol, ISO 20121, SBTi, regional (SG/EU/UK/USA) |
| Live data agents | 10 (grid factors, carbon prices, aviation, food) |
| Export formats | PDF, Excel, JSON, CSV |

---

## Why Now

- Singapore carbon tax rises to $50/tCO₂e in 2026, $80 by 2030
- EU CSRD requires Scope 3 reporting for 50,000+ companies from 2025
- ISO 20121 is becoming a procurement requirement for major venues

The regulatory clock is running. Event organizers need a tool that keeps up — not a consultant with a spreadsheet from last year.

---

## Stack (for technical audiences)

FastAPI + Python backend · React 19 + TypeScript frontend · OpenAI function calling · TinyFish headless browser agents · SQLAlchemy async ORM (SQLite/Postgres) · GHG Protocol deterministic calculations
