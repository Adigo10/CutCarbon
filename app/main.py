from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from app.models.database import init_db
from app.routers import chat, scenarios, financial, agents, auth, offsets

app = FastAPI(
    title="EventCarbon Co-Pilot",
    description="AI-powered carbon footprint calculator for events with financial savings, compliance tracking, and carbon offset management",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["Chat"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["Scenarios"])
app.include_router(financial.router, prefix="/api/financial", tags=["Financial"])
app.include_router(offsets.router,   prefix="/api/offsets",   tags=["Carbon Offsets"])
app.include_router(agents.router,    prefix="/api/agents",    tags=["TinyFish Agents"])

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "EventCarbon Co-Pilot", "version": "2.0.0"}


@app.on_event("startup")
async def startup():
    await init_db()
    print("EventCarbon Co-Pilot v2.0 started — http://localhost:8000")
