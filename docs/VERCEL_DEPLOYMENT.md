# Vercel deployment

CutCarbon deploys as two Vercel Services from one project:

- `frontend`: Vite static assets at `/`
- `backend`: FastAPI Fluid Compute service at `/api/*`

## One-time project setup

1. Import the repository into Vercel with the repository root as the Root Directory.
2. In **Project Settings -> Build & Deployment**, set **Framework Preset** to
   **Services**.
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
so previews and production route to their matching backend service without CORS or
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
3. Push a branch and validate its Vercel preview.
4. Verify `/`, `/api/health`, login, one authenticated scenario request, and one
   export before promoting the exact preview artifact.

## Runtime constraints

- SQLite is rejected on Vercel because function filesystems are ephemeral.
- TinyFish factor refresh endpoints return `503` on Vercel. They mutate the factor
  catalog and require a durable writable worker. Existing bundled factors, agent
  history, and scenario recalculation remain available.
- Rate limiting is process-local. Use Vercel Firewall or a shared rate-limit store
  before relying on it for abuse protection across function instances.
- Vercel CLI local multi-service emulation currently generates an invalid unescaped
  Windows path under `C:\Users\...`. Use a Linux CI runner or a linked preview for the
  final end-to-end check until the CLI fixes that issue.

References: [Vercel Services](https://vercel.com/docs/services),
[FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), and
[Python runtime](https://vercel.com/docs/functions/runtimes/python).
