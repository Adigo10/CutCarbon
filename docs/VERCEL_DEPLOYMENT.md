# Vercel deployment

CutCarbon deploys a static frontend and a Python function from one project:

- `frontend`: Vite static assets at `/`
- `backend`: FastAPI Python function at `/api/*`

`vercel.json` explicitly builds `frontend/package.json` with
`@vercel/static-build` and `index.py` with `@vercel/python`. The API route runs
before the frontend catch-all and preserves the
request path, so FastAPI registers `/api/...` routes in every environment.
Both `/api/health` and the legacy `/health` endpoint reach the backend.

## One-time project setup

1. Import the repository into Vercel with the repository root as the Root Directory.
2. Keep build settings in `vercel.json`: the frontend builder runs
   `npm run vercel-build` from `frontend/`; the Python builder uses `index.py`
   from the repository root. Do not deploy this repository as a standalone FastAPI
   app: that builds only Python and leaves `/` without the frontend.
3. Add these variables to Production and Preview:
   - `DATABASE_URL`: Supabase transaction-pooler URL for the least-privilege app role.
   - `SUPABASE_URL`
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_PUBLISHABLE_KEY`
   - `OPENAI_API_KEY` if chat is enabled.
   - `OPENAI_MODEL` if overriding `gpt-4o-mini`.
   - `ADMIN_EMAILS` if admin-only features are enabled.
4. Keep `RUN_MIGRATIONS_ON_STARTUP=false`. Apply migrations once from a trusted
   runner using `MIGRATION_DATABASE_URL` before promoting a deployment.

Do not set `VITE_API_URL` on Vercel. The frontend uses same-origin `/api/*` requests,
so previews and production route to their matching backend function without CORS or
environment-specific URLs.

## Release flow

1. Install development dependencies and run checks:

   ```powershell
   pip install -r requirements-dev.txt
   python -m pytest
   npm --prefix frontend ci
   npm --prefix frontend run lint
   npm --prefix frontend run build
   ```

2. Apply `alembic upgrade head` using the direct or session-pooler migration URL.
3. Push a branch and validate its Vercel preview. Set the required variables in
   Preview too; Production-only backend variables do not apply to previews.
4. Verify `/`, `/api/health`, login, one authenticated scenario request, and one
   export before promoting the exact preview artifact.

## Runtime constraints

- SQLite is rejected on Vercel because function filesystems are ephemeral.
- TinyFish factor refresh endpoints return `503` on Vercel. They mutate the factor
  catalog and require a durable writable worker. Existing bundled factors, agent
  history, and scenario recalculation remain available.
- Rate limiting is process-local. Use Vercel Firewall or a shared rate-limit store
  before relying on it for abuse protection across function instances.
- Build the frontend with `npm --prefix frontend run build`, then run the API
  locally with `.carbon_venv\Scripts\python.exe -m uvicorn app.main:app`.
  Vercel CLI 62.2.0 local builds failed on this Windows host with
  `spawn cmd.exe ENOENT`; use a remote deployment for the final routing check.

## Diagnosed deployment failure (2026-10-04)

The production deployment used commit `d4aa8e8`, before the deployment setup was
added. Its build logs show only Python dependency installation and bytecode
compilation; there is no Vite build. `/health` returned 200 while `/` returned a
FastAPI 404, confirming the missing frontend rather than an API startup crash.

The Vercel project also lacked `VITE_SUPABASE_URL` and
`VITE_SUPABASE_PUBLISHABLE_KEY`. Both have now been configured for Production and
Preview from the existing local frontend configuration. A Vite configuration
check fails the build with the missing variable names instead of publishing a
frontend that crashes during Supabase client initialization.

A staged Services deployment built Vite but left `/` returning 404. The final
configuration uses explicit static and Python builders so the frontend output
is packaged independently. Filesystem dispatch must not run before the SPA
fallback: it resolves `/` to the `index.py` function instead of the frontend.
The configuration also removes the Vercel-only API-prefix stripping that would
make `/api/...` return 404.

Deploy the updated working tree; redeploying the older production artifact does
not include these changes. The connected Vercel tools can inspect deployments
and configure variables, but creating a deployment requires an authenticated
CLI or a Git push.

## Verified release (2026-10-04)

Deployment `dpl_8uYWrRjhM5ScwzvuAsnBfA7JRuim` was promoted to
`https://cut-carbon.vercel.app`. The live homepage and `/api/health` returned 200.
The staged app rendered the sign-in page with no browser console errors, and
`/api/scenarios` returned 401 without credentials. The six deployment regression
tests, frontend lint, TypeScript configuration check, and frontend build passed.
Authenticated login, database-backed scenario creation, and exports were not
tested in this release check. Commit and push the local source changes before
the next Git-triggered deployment so it retains the fix.

References: [Vercel Services](https://vercel.com/docs/services),
[FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), and
[Python runtime](https://vercel.com/docs/functions/runtimes/python).
