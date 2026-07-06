# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Backend API + production-style frontend serving
pip install -r requirements.txt

# Apply the database schema (Supabase Postgres). Point MIGRATION_DATABASE_URL (or
# DATABASE_URL) at the session pooler / direct connection first. Skipped for the
# sqlite dev fallback, which creates tables directly on startup.
alembic upgrade head

# Build React frontend so FastAPI can serve it at /
# Set frontend/.env: VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY (+ optional VITE_API_URL)
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

The suite lives in `tests/` covering auth, chat, scenarios, financial, offsets, agents, exports, and the emissions engine. `tests/conftest.py` sets `RATE_LIMIT_ENABLED=false` and test `SUPABASE_*` values, then runs each test against a **fresh Postgres schema** (a new `test_<uuid>` schema per test via a `NullPool` asyncpg engine). Provide `TEST_DATABASE_URL` (a direct/session Postgres connection, not the 6543 pooler) or install Docker so testcontainers can start `postgres:17` (matches Supabase prod); DB-backed tests **skip** if neither is available. Tests authenticate by minting HS256 tokens the verifier accepts (see `tests/helpers.py`), exercising the real `get_current_user` + JIT-provisioning path — no live Supabase needed.

## Environment Variables

Set in `.env` at project root (copy `.env.example` as a starting point):
- `OPENAI_API_KEY` — required for chat co-pilot
- `TINYFISH_API_KEY` — required for web agent data refresh
- `OPENAI_MODEL` — defaults to `gpt-4o-mini`
- `DATABASE_URL` — Supabase Postgres via the transaction pooler (`postgresql+asyncpg://postgres.<ref>:<pw>@...pooler.supabase.com:6543/postgres`); defaults to `sqlite+aiosqlite:///./cutcarbon.db` as a local dev fallback
- `MIGRATION_DATABASE_URL` — used by Alembic if set, else `DATABASE_URL`; point at the session pooler (5432) or direct connection (migrations need prepared statements the 6543 pooler forbids)
- `RUN_MIGRATIONS_ON_STARTUP` — `false` by default; when `true`, the app runs `alembic upgrade head` on startup (single-instance dev/demo only)
- `SUPABASE_URL` — base project URL (e.g. `https://<ref>.supabase.co`); used to derive the JWKS endpoint and expected token issuer
- `SUPABASE_JWT_AUD` — audience on Supabase user tokens (default `authenticated`)
- `SUPABASE_JWT_SECRET` — optional HS256 shared secret; empty = asymmetric-only (RS256/ES256 via JWKS)
- `ADMIN_EMAILS` — comma-separated allowlist of emails permitted to trigger TinyFish agent runs; empty = nobody
- `RATE_LIMIT_ENABLED` — defaults to `true`; set `false` to disable per-IP rate limiting (used in tests)

Frontend env (`frontend/.env`, read by Vite): `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (browser-safe, RLS-protected), and optional `VITE_API_URL`.

## Architecture

**Backend**: FastAPI (async) with seven routers under `app/routers/`:
- `auth.py` — `GET /api/auth/me` plus the shared `get_current_user` / `require_admin` dependencies. Signup/login are handled client-side by Supabase Auth (supabase-js); FastAPI only **verifies** Supabase-issued access tokens (`app/auth/supabase.py`: JWKS for RS256/ES256, HS256 fallback), then JIT-provisions a `public.users` profile row keyed by the Supabase UUID. `require_admin` gates on `current_user.email` against the `ADMIN_EMAILS` allowlist
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

**Database**: SQLAlchemy async ORM (`app/models/database.py`) on Supabase Postgres via asyncpg (a sqlite dev fallback is still supported). Schema is owned by **Alembic** (`alembic/`); `init_db()` only creates tables directly on the sqlite fallback. The engine runs behind Supabase's transaction pooler (IPv4, port 6543) with prepared statements disabled + `NullPool` (see `_make_engine`); migrations use the session pooler/direct connection. Runtime connects as the least-privilege **`cutcarbon_app`** role (DML-only, no DDL/bypassrls/`auth` access); Alembic uses the elevated `postgres` role. Key models: `UserDB` (UUID PK = the Supabase auth uid, FK to `auth.users` `ON DELETE CASCADE`, JIT-provisioned; no password column), `ScenarioDB`, `ChatMessageDB`, `FinancialReportDB`, `EmissionFactorDB` (write-only audit log of TinyFish fetches — `emission_factors.json` remains the live source for calculations), `OffsetPurchaseDB`, `AgentRunDB`. User-owned tables carry a `NOT NULL` UUID `user_id` FK `ON DELETE CASCADE`; JSON columns are JSONB on Postgres.

**Data-API lockdown**: the app never uses PostgREST — every table has RLS enabled and all `anon`/`authenticated` grants revoked (migrations `a1b2c3d4e5f6` / `b2c3d4e5f6a7`; helper `app/models/db_security.py`), so the browser-embedded publishable key cannot reach any table. `cutcarbon_app` works via a permissive `FOR ALL` policy; ownership is still enforced in Python. See `docs/DB_OPERATIONS.md` for role passwords, `pg_cron` keep-alive/retention, and backups (free tier has none).

**Schemas**: All Pydantic request/response models in `app/models/schemas.py`. Key enums: `TravelMode`, `TravelClass`, `AccommodationType`, `CateringType`, `GridRegion`.

**Frontend**: React 19 + TypeScript single-page app in `frontend/`, bundled with Vite.
- `frontend/src/App.tsx` — app shell, auth/session state, tab orchestration, API workflows
- `frontend/src/components/` — dashboard widgets, charts, tab views, and UI primitives
- `frontend/src/lib/api.ts` — typed fetch helpers for FastAPI endpoints (Bearer token threaded from the Supabase session held in `App.tsx`)
- `frontend/src/lib/supabase.ts` — supabase-js client; owns signup/login/session + token refresh
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
- Rate limits (per-IP): 20/min chat, 2/hour agent runs; `RATE_LIMIT_ENABLED=false` disables them (used in tests). Login/registration are no longer FastAPI endpoints — Supabase Auth handles (and rate-limits) them
- Authentication is delegated to Supabase Auth: supabase-js signs users up/in and holds the session; FastAPI verifies the access token and JIT-provisions a `public.users` profile keyed by the Supabase UUID. Passwords never reach FastAPI (bcrypt/`hashed_password` removed); user identity is a UUID, not an integer
- CORS uses wildcard origins with `allow_credentials=False` — the SPA authenticates with a Supabase-issued Bearer token (managed by supabase-js in localStorage), not cookies, so credentialed CORS is unnecessary (and wildcard + credentials would be spec-invalid). To use cookies later, switch to an explicit env-driven origin allowlist and re-enable credentials
- Alembic owns the Postgres schema (`alembic/versions/`); regenerate with `alembic revision --autogenerate` after model changes and verify with `alembic check`. The old hand-rolled `init_db()` ALTER-TABLE migrations were removed in the Supabase move

## Documentation

| File | Audience | Contents |
|---|---|---|
| `CLAUDE.md` | Developers / AI assistants | Commands, env vars, architecture summary |
| `ARCHITECTURE.md` | Engineers | System diagram, data flows, auth flow, timelines |
| `USER_GUIDE.md` | End users | Complete usage manual, feature reference |
| `QUICK_START.md` | New users | 5-minute onboarding walkthrough |
| `TINYFISH_AGENTS.md` | Developers / Data auditors | Agent specs, sources, validation, caching, API |
| `docs/DB_OPERATIONS.md` | Ops / DBAs | Supabase roles, RLS/Data-API lockdown, pg_cron keep-alive/retention, backups & restore |
