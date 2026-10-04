# OpenAI data refresh

Chat and all ten refresh tasks use `OPENAI_MODEL=gpt-6-luna` through the Responses
API. `OPENAI_API_KEY` powers both. Chat can search public information but cannot
update shared factors.

## Tasks and evidence

| Task | Source | Destination |
| --- | --- | --- |
| sg_grid_factor | EMA Singapore | Singapore grid factor |
| uk_grid_factor | UK DEFRA/DESNZ | UK location-based grid factor |
| au_grid_factor | DCCEEW Australia | Australian grid factor |
| usa_grid_factor | EPA eGRID | US grid factor |
| eu_grid_factor | EEA | EU average grid factor |
| sg_carbon_tax | NEA Singapore | Current SGD carbon tax |
| eu_ets_price | Ember Climate | Recent EUR allowance price |
| uk_ets_price | UK government / ICE | Recent GBP allowance price |
| icao_flight_factors | UK DEFRA/DESNZ | Passenger-km factors with radiative forcing |
| food_emission_factors | Our World in Data | Explicitly supported meal factors |

The legacy aviation task name stays stable for existing history. Its source is
DEFRA, not ICAO. Search finds the latest compatible publication rather than a
fixed year. Each task requires live search restricted to its source domains,
then schema-constrained extraction from retrieved evidence.

Validation requires a retrieved source URL, reporting year or source date,
methodology, finite values, explicit units and numeric bounds. Prices require
the correct currency and effective date; ETS quotes must be at most 31 days old.
Flight factors must include radiative forcing. Food emissions per kilogram are
never treated as emissions per meal. Missing evidence produces `no_data`,
preserving previous factors. Automated values remain `is_verified=false`.

## Storage and consistency

`factor_catalog` stores the active catalog. Startup seeds it from the packaged
`app/data/emission_factors.json` baseline; refreshes never rewrite that file.
Each calculation request uses one catalog snapshot, including exports and
financial calculations, across multiple processes and Vercel instances.

Successful task results and catalog patches commit together. The revision
advances when numeric factors change. Existing scenario and report snapshots
retain their versions; use Recalculate all to update working scenarios.
`agent_runs.result_json` retains source URLs, dates, original units and values,
methodology, model, response IDs and fetch time. Historical audit rows remain.

A database lease expires after 300 seconds and prevents overlapping refreshes.
Concurrency is five, with individual 110-second and overall 240-second deadlines.
Completed tasks persist even if others fail. Successful results are cached for
12 hours with their original provenance.

## API and UI

- Both `POST /api/agents/run` and `POST /api/agents/run/sync` await completion.
- `force=false` respects caching; `force=true` bypasses it.
- Refresh requires an email on `ADMIN_EMAILS` and remains rate-limited.
- Overall status is `completed`, `partial` or `failed`; tasks report `success`,
  `cached`, `no_data`, `error` or `timeout`, with applied fields.
- Missing credentials or failed persistence returns 503; an active lease returns
  409. No fire-and-forget task continues after the request.
- Authenticated users can read `/api/agents/status` and `/api/agents/history`.
- Partial-failure messages distinguish applied updates from retained factors.

Chat citations contain URL, title and UTF-16 offsets. They persist in history
and render as clickable inline links. Citations on text removed by the
green-claims guardrail are dropped instead of reassigned.

## Deployment and validation

Apply `alembic upgrade head` using `MIGRATION_DATABASE_URL` before deployment.
The migration creates the catalog and adds nullable chat citations. Runtime
access stays limited to `cutcarbon_app`; browser Data API roles have no catalog
access. Vercel requires persistent Postgres and out-of-band migrations. SQLite
development bootstraps the catalog and optional citations column.

Run `python -m pytest` through the local virtual environment with an isolated
Postgres test database/schema, then `npm run build` and `npm run lint` in
`frontend`. Live validation requires OpenAI credentials and model access.
