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

## Running Tests

```bash
pytest
```

The suite lives in `tests/` (8 test modules, 81 tests) covering auth, chat, scenarios, financial, offsets, agents, exports, and the emissions engine. `tests/conftest.py` sets `RATE_LIMIT_ENABLED=false` so rate limits don't interfere.

## Environment Variables

Set in `.env` at project root (copy `.env.example` as a starting point):
- `OPENAI_API_KEY` — required for chat co-pilot
- `TINYFISH_API_KEY` — required for web agent data refresh
- `OPENAI_MODEL` — defaults to `gpt-4o-mini`
- `DATABASE_URL` — defaults to `sqlite+aiosqlite:///./cutcarbon.db`; swap to `postgresql+asyncpg://...` for Postgres
- `JWT_SECRET` — must be a random string ≥32 chars; if unset/placeholder/too short, an ephemeral per-process secret is generated (tokens won't survive a restart)
- `ADMIN_EMAILS` — comma-separated allowlist of emails permitted to trigger TinyFish agent runs; empty = nobody
- `RATE_LIMIT_ENABLED` — defaults to `true`; set `false` to disable per-IP rate limiting (used in tests)

## Architecture

**Backend**: FastAPI (async) with seven routers under `app/routers/`:
- `auth.py` — JSON register/login, `POST /api/auth/token` (form-encoded, so Swagger's Authorize flow works), `GET /api/auth/me`. JWT Bearer auth plus a `require_admin` gate driven by the `ADMIN_EMAILS` allowlist
- `chat.py` — `POST /api/chat` — AI co-pilot using OpenAI function calling to extract structured event data from natural language; when a scenario is selected, the `request_financial_analysis` tool is answered with real financial-engine output
- `scenarios.py` — CRUD, clone, recalculate-all, and reduction suggestions for emission scenarios
- `financial.py` — `POST /api/financial/savings` and `POST /api/financial/compliance` — carbon tax savings, green incentives, and compliance reports by region
- `offsets.py` — Offset project catalog, purchase/retire/cancel tracking, portfolio summary, and recommended offset mixes per scenario
- `agents.py` — Triggers TinyFish web agents to refresh emission factors from live sources (run endpoints admin-only; status/history for any authenticated user)
- `exports.py` — Per-scenario report packages (JSON/CSV/XLSX/PDF) plus bulk scenario, emission-factor, and agent-run downloads

**Services layer** (`app/services/`):
- `emissions_engine.py` — Deterministic GHG Protocol calculations across eight categories (travel, venue energy, accommodation, catering, materials/waste, equipment, swag, digital) with Scope 1/2/3 split. All emission factors loaded from `app/data/emission_factors.json`
- `financial_engine.py` — Carbon tax savings by region (SG, EU, UK, AU, USA), incentive matching, compliance scoring. Data from `app/data/tax_incentives.json`
- `openai_service.py` — Chat with function calling tools (`update_event_scenario`, `request_financial_analysis`) to convert plain text into structured `EventScenarioInput`
- `tinyfish_agent.py` — 10 TinyFish web agents that fetch live emission factors and carbon prices from EMA, DEFRA, EPA eGRID, EEA, Clean Energy Regulator AU, NEA, Ember Climate, UK Government, ICAO, and Our World in Data, then merge results back into `emission_factors.json` with provenance. See `TINYFISH_AGENTS.md` for full specifications.
- `scenario_serializer.py` — Single mapping between `ScenarioDB` rows and API payloads
- `regions.py` — Canonical region aliases shared across the financial and emissions code
- `data_files.py` — Shared loading of the JSON data files

Supporting modules: `app/rate_limit.py` (slowapi limiter honoring `RATE_LIMIT_ENABLED`) and `app/utils/time.py` (timezone-aware `utcnow`).

**Data flow**: Chat input -> OpenAI extracts structured data -> Emissions engine calculates -> Financial engine prices carbon -> Compliance engine scores against frameworks (GHG Protocol, ISO 20121, NZCE Measurement Methodology, event carbon-intensity benchmarks, SGX, EU CSRD)

**Database**: SQLAlchemy async ORM (`app/models/database.py`). Tables auto-created on startup via `init_db()`. Key models: `UserDB`, `ScenarioDB`, `ChatMessageDB`, `FinancialReportDB`, `EmissionFactorDB` (write-only audit log of TinyFish fetches — `emission_factors.json` remains the live source for calculations), `OffsetPurchaseDB`, `AgentRunDB`. SQLite locally; Postgres-ready.

**Schemas**: All Pydantic request/response models in `app/models/schemas.py`. Key enums: `TravelMode`, `TravelClass`, `AccommodationType`, `CateringType`, `GridRegion`.

**Frontend**: React 19 + TypeScript single-page app in `frontend/`, bundled with Vite.
- `frontend/src/App.tsx` — app shell, auth/session state, tab orchestration, API workflows
- `frontend/src/components/` — dashboard widgets, charts, tab views, and UI primitives
- `frontend/src/lib/api.ts` — typed fetch helpers for FastAPI endpoints
- `frontend/dist/` — production build served by FastAPI at `/`; if the build is missing, startup logs an error and no UI is served (there is no fallback UI)

**Static data files** (`app/data/`):
- `emission_factors.json` — Factor catalog with source URLs and methodology tags (ICAO, DEFRA, IEA, etc.)
- `tax_incentives.json` — Carbon tax rates, exchange rates, green incentives, and compliance framework penalties by region

## Key Design Decisions

- Emission calculations are fully deterministic (no LLM involvement) — the LLM only handles natural language extraction and suggestions
- Supports "basic" mode (proxy-heavy estimates from attendee count) and "advanced" mode (detailed supplier data)
- Data quality tracked per scenario ("estimated", "partial", or "verified") plus per-category flags (actual / proxy / not provided / not applicable) recorded in assumptions and rendered in all exports
- Digital/virtual is a first-class emissions category (streaming, livestream production, event app, email — NZCE category 9); virtual events no longer get physical travel/venue proxies
- ROI / payback-period / NPV metrics are deliberately omitted (`roi_months` is always null) — an annualized payback is misleading for a one-off event; likewise no dollar-quantified "compliance value" or voluntary-carbon-market savings line is added to the financial total
- SBTi is not scored — it is a corporate framework; an informational "Event carbon intensity (vs published event benchmarks)" check is reported instead
- Travel cabin-class factors apply only to flights; ground modes (rail, road, ferry) use a single factor. Equipment electricity factors embed a global-average grid (annotated `grid_basis` in `emission_factors.json`)
- `factors_snapshot` on each scenario is provenance-only — rendered in exports, never read back as calculation input. `emission_factors.json` carries a version (currently `2026.1`, recorded as `ef_version` in snapshots); after upgrading, run "Recalculate all" so stored scenarios pick up engine fixes
- TinyFish agents store provenance (source URL, fetch time, run_id) when updating factors; agent run triggers are admin-only (`ADMIN_EMAILS` allowlist) and rate-limited even for admins
- Rate limits (per-IP): 5/min register/login/token, 20/min chat, 2/hour agent runs; `RATE_LIMIT_ENABLED=false` disables them (used in tests)
- Registration requires a valid email address and an 8–72 character password
- CORS uses wildcard origins with `allow_credentials=False` — the SPA authenticates with a Bearer token from localStorage, not cookies, so credentialed CORS is unnecessary (and wildcard + credentials would be spec-invalid). To use cookies later, switch to an explicit env-driven origin allowlist and re-enable credentials
- No Alembic — the hand-rolled additive SQLite migrations in `init_db()` are deliberate (idempotent column additions only); a move to Postgres should introduce Alembic

## Documentation

| File | Audience | Contents |
|---|---|---|
| `CLAUDE.md` | Developers / AI assistants | Commands, env vars, architecture summary |
| `ARCHITECTURE.md` | Engineers | System diagram, data flows, auth flow, timelines |
| `USER_GUIDE.md` | End users | Complete usage manual, feature reference |
| `QUICK_START.md` | New users | 5-minute onboarding walkthrough |
| `TINYFISH_AGENTS.md` | Developers / Data auditors | Agent specs, sources, validation, caching, API |
