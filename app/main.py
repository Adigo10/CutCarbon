import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.models.database import init_db
from app.rate_limit import limiter
from app.routers import chat, scenarios, financial, agents, auth, offsets, exports

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
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

# The SPA authenticates with a Bearer token in localStorage (not a cookie), so we
# do NOT need credentialed CORS. Wildcard origin + allow_credentials=True is both
# spec-invalid and unsafe, so credentials are disabled here. To use cookies later,
# replace "*" with an explicit env-driven origin allowlist and re-enable credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["Chat"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["Scenarios"])
app.include_router(financial.router, prefix="/api/financial", tags=["Financial"])
app.include_router(offsets.router,   prefix="/api/offsets",   tags=["Carbon Offsets"])
app.include_router(agents.router,    prefix="/api/agents",    tags=["TinyFish Agents"])
app.include_router(exports.router,   prefix="/api/exports",   tags=["Data Exports"])

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"


@app.get("/health")
async def health():
    return {"status": "ok", "service": "EventCarbon Co-Pilot", "version": "2.0.0"}


if (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    logger.error(
        "frontend/dist/index.html not found — the SPA will not be served. "
        "Build it first: cd frontend && npm install && npm run build"
    )
