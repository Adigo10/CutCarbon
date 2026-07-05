from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.models.database import get_db, ChatMessageDB, ScenarioDB, UserDB
from app.models.schemas import ChatRequest, ChatResponse
from app.rate_limit import limiter
from app.services import openai_service
from app.services.financial_engine import build_scenario_financial_request, generate_financial_report
from app.routers.auth import get_current_user
from app.utils.time import utcnow

router = APIRouter()


def _valid_session_id(value) -> str:
    """Return value if it's a valid UUID string, else a fresh server-generated id."""
    if isinstance(value, str):
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError, TypeError):
            pass
    return str(uuid.uuid4())


@router.post("", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Send a chat message to the AI co-pilot and receive a reply with optional data extraction."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Build event context from DB if scenario_id provided
    event_context = req.event_context or {}
    scenario = None
    if req.scenario_id:
        result = await db.execute(
            select(ScenarioDB).where(ScenarioDB.id == req.scenario_id, ScenarioDB.user_id == current_user.id)
        )
        scenario = result.scalar_one_or_none()
        if scenario:
            event_context.update({
                "event_name": scenario.event_name,
                "attendees": scenario.attendees,
                "location": getattr(scenario, "location", None) or (scenario.input_payload or {}).get("location"),
                "current_tco2e": scenario.total_tco2e,
            })

    # When a scenario is selected, the LLM's request_financial_analysis tool call is
    # answered with real engine output rather than a stub the model would embellish.
    financial_provider = None
    if scenario is not None:
        scenario_row = scenario

        def financial_provider(args):
            args = args or {}
            try:
                reduction_pct = float(args.get("reduction_pct") or 30.0)
            except (TypeError, ValueError):
                reduction_pct = 30.0
            reduction_pct = min(max(reduction_pct, 0.0), 100.0)
            fin_req = build_scenario_financial_request(
                scenario_row,
                region=args.get("region") or "singapore",
                reduction_pct=reduction_pct,
                actions_taken=args.get("actions") or ["renewable_energy", "vegetarian_menu", "digital_materials"],
            )
            return generate_financial_report(fin_req).model_dump()

    # Validate the client-supplied session id (don't let the client write into
    # arbitrary buckets); fall back to a server-generated id.
    session_id = _valid_session_id((req.event_context or {}).get("session_id"))

    # Persist the user's message FIRST so a downstream LLM failure can't lose the turn.
    last_user = req.messages[-1]
    db.add(ChatMessageDB(
        session_id=session_id,
        role="user",
        content=last_user.content,
        created_at=utcnow(),
        user_id=current_user.id,
    ))
    await db.commit()

    # Call OpenAI (degraded 503 on upstream failure rather than a raw 500).
    try:
        result = await openai_service.chat(req.messages, event_context, financial_provider)
    except openai_service.ChatServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    db.add(ChatMessageDB(
        session_id=session_id,
        role="assistant",
        content=result["reply"],
        extracted_data=result.get("extracted_data"),
        created_at=utcnow(),
        user_id=current_user.id,
    ))
    await db.commit()

    return ChatResponse(
        reply=result["reply"],
        extracted_data=result.get("extracted_data"),
        suggestions=result.get("suggestions", []),
        session_id=session_id,
        financial_analysis=result.get("financial_analysis"),
    )


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Retrieve chat history for a session."""
    result = await db.execute(
        select(ChatMessageDB)
        .where(ChatMessageDB.session_id == session_id, ChatMessageDB.user_id == current_user.id)
        .order_by(ChatMessageDB.created_at)
    )
    messages = result.scalars().all()
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in messages
    ]
