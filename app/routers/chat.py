from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.models.database import get_db, ChatMessageDB, ScenarioDB, UserDB
from app.models.schemas import ChatRequest, ChatResponse
from app.services import openai_service
from app.routers.auth import get_current_user

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Send a chat message to the AI co-pilot and receive a reply with optional data extraction."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Build event context from DB if scenario_id provided
    event_context = req.event_context or {}
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

    # Call OpenAI
    result = await openai_service.chat(req.messages, event_context)

    # Persist messages to DB
    session_id = req.event_context.get("session_id", str(uuid.uuid4())) if req.event_context else str(uuid.uuid4())
    last_user = req.messages[-1]
    db.add(ChatMessageDB(
        session_id=session_id,
        role=last_user.role,
        content=last_user.content,
        created_at=datetime.utcnow(),
        user_id=current_user.id,
    ))
    db.add(ChatMessageDB(
        session_id=session_id,
        role="assistant",
        content=result["reply"],
        extracted_data=result.get("extracted_data"),
        created_at=datetime.utcnow(),
        user_id=current_user.id,
    ))
    await db.commit()

    return ChatResponse(
        reply=result["reply"],
        extracted_data=result.get("extracted_data"),
        suggestions=result.get("suggestions", []),
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
