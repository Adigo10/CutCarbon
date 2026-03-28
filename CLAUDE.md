# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Backend API + production-style frontend serving
pip install -r requirements.txt

# Build React frontend so FastAPI can serve it at /
cd frontend
npm install
npm run build
cd ..

# Run backend (auto-reload)
uvicorn app.main:app --reload --port 8000

# Access points
# FastAPI-served frontend: http://localhost:8000/
# Swagger docs: http://localhost:8000/docs
# Health check: http://localhost:8000/health

# Frontend development server (optional, for React work)
cd frontend
npm run dev
# React dev UI: http://localhost:5173/
```

## Environment Variables

Set in `.env` at project root:
- `OPENAI_API_KEY` — required for chat co-pilot
- `TINYFISH_API_KEY` — required for web agent data refresh
- `OPENAI_MODEL` — defaults to `gpt-4o-mini`
- `DATABASE_URL` — defaults to `sqlite+aiosqlite:///./cutcarbon.db`; swap to `postgresql+asyncpg://...` for Postgres

## Architecture

**Backend**: FastAPI (async) with four routers under `app/routers/`:
- `chat.py` — `POST /api/chat` — AI co-pilot using OpenAI function calling to extract structured event data from natural language
- `scenarios.py` — CRUD, clone, and reduction suggestions for emission scenarios
- `financial.py` — Carbon tax savings, green incentives, and compliance reports by region
- `agents.py` — Triggers TinyFish web agents to refresh emission factors from live sources

**Services layer** (`app/services/`):
- `emissions_engine.py` — Deterministic GHG Protocol calculations (travel, venue energy, accommodation, catering, waste). All emission factors loaded from `app/data/emission_factors.json`
- `financial_engine.py` — Carbon tax savings by region (SG, EU, UK, AU, USA), incentive matching, compliance scoring. Data from `app/data/tax_incentives.json`
- `openai_service.py` — Chat with function calling tools (`update_event_scenario`, `request_financial_analysis`) to convert plain text into structured `EventScenarioInput`
- `tinyfish_agent.py` — 6 headless browser agents that fetch live emission factors from EMA, DEFRA, NEA, Ember Climate, ICAO, and Our World in Data, then merge results back into `emission_factors.json` with provenance

**Data flow**: Chat input -> OpenAI extracts structured data -> Emissions engine calculates -> Financial engine prices carbon -> Compliance engine scores against frameworks (GHG Protocol, ISO 20121, SBTi, SGX, EU CSRD)

**Database**: SQLAlchemy async ORM (`app/models/database.py`). Tables auto-created on startup via `init_db()`. Key models: `EventDB`, `ScenarioDB`, `ChatMessageDB`, `FinancialReportDB`, `EmissionFactorDB`. SQLite locally; Postgres-ready.

**Schemas**: All Pydantic request/response models in `app/models/schemas.py`. Key enums: `TravelMode`, `TravelClass`, `AccommodationType`, `CateringType`, `GridRegion`.

**Frontend**: React 19 + TypeScript single-page app in `frontend/`, bundled with Vite.
- `frontend/src/App.tsx` — app shell, auth/session state, tab orchestration, API workflows
- `frontend/src/components/` — dashboard widgets, charts, tab views, and UI primitives
- `frontend/src/lib/api.ts` — typed fetch helpers for FastAPI endpoints
- `frontend/dist/` — production build served by FastAPI at `/` when present
- `static/` — legacy fallback UI kept for compatibility while the React app becomes the default

**Static data files** (`app/data/`):
- `emission_factors.json` — Factor catalog with source URLs and methodology tags (ICAO, DEFRA, IEA, etc.)
- `tax_incentives.json` — Carbon tax rates, exchange rates, green incentives, and compliance framework penalties by region

## Key Design Decisions

- Emission calculations are fully deterministic (no LLM involvement) — the LLM only handles natural language extraction and suggestions
- Supports "basic" mode (proxy-heavy estimates from attendee count) and "advanced" mode (detailed supplier data)
- Data quality tracked per scenario: "estimated", "partial", or "verified"
- TinyFish agents store provenance (source URL, fetch time, run_id) when updating factors
- CORS is wide open (`allow_origins=["*"]`) — tighten for production
- No test suite currently exists
- No Alembic migrations in use — tables auto-created on startup
