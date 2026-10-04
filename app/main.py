import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.models.database import init_db
from app.rate_limit import limiter
from app.routers import chat, scenarios, financial, agents, auth, offsets, exports

logger = logging.getLogger(__name__)
IS_VERCEL = os.getenv("VERCEL") == "1"
# Vercel forwards the original request path, including /api, to the function.
API_PREFIX = "/api"


def _validate_runtime_config() -> None:
    if os.getenv("VERCEL") != "1":
        return
    if "sqlite" in settings.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL must point to persistent Postgres on Vercel; "
            "the SQLite fallback is ephemeral and unsupported"
        )
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        raise RuntimeError(
            "RUN_MIGRATIONS_ON_STARTUP must be false on Vercel; apply Alembic "
            "migrations once, before deployment"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    _validate_runtime_config()
    await init_db()
    logger.info("EventCarbon Co-Pilot v2.0 started — http://localhost:8000")
    yield


app = FastAPI(
    title="EventCarbon Co-Pilot",
    description="AI-powered carbon footprint calculator for events with financial savings, compliance tracking, and carbon offset management",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# The SPA authenticates with a Supabase-issued Bearer token (managed by supabase-js
# in localStorage, not a cookie), so we do NOT need credentialed CORS. Wildcard
# origin + allow_credentials=True is both spec-invalid and unsafe, so credentials are
# disabled here. To use cookies later, replace "*" with an explicit env-driven origin
# allowlist and re-enable credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix=f"{API_PREFIX}/auth",      tags=["Auth"])
app.include_router(chat.router,      prefix=f"{API_PREFIX}/chat",      tags=["Chat"])
app.include_router(scenarios.router, prefix=f"{API_PREFIX}/scenarios", tags=["Scenarios"])
app.include_router(financial.router, prefix=f"{API_PREFIX}/financial", tags=["Financial"])
app.include_router(offsets.router,   prefix=f"{API_PREFIX}/offsets",   tags=["Carbon Offsets"])
app.include_router(agents.router,    prefix=f"{API_PREFIX}/agents",    tags=["TinyFish Agents"])
app.include_router(exports.router,   prefix=f"{API_PREFIX}/exports",   tags=["Data Exports"])
app.include_router(exports.reports_router, prefix=API_PREFIX,           tags=["Report Snapshots"])

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"


@app.get("/health")
@app.get(f"{API_PREFIX}/health")
async def health():
    return {"status": "ok", "service": "EventCarbon Co-Pilot", "version": "2.0.0"}


if IS_VERCEL:
    logger.info("Vercel serves the frontend as static Vite assets")
elif (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    logger.error(
        "frontend/dist/index.html not found — the SPA will not be served. "
        "Build it first: cd frontend && npm install && npm run build"
    )
