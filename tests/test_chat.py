import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models.database as database
from app.models.database import ChatMessageDB
from app.services import openai_service

from helpers import create_scenario, register_user


def _mock_chat(monkeypatch, reply="Mocked reply", extracted=None, capture=None):
    async def fake_chat(messages, event_context=None, financial_provider=None):
        if capture is not None:
            capture["messages"] = messages
            capture["event_context"] = event_context
            capture["financial_provider"] = financial_provider
        financial = financial_provider({"region": "singapore"}) if financial_provider else None
        return {
            "reply": reply,
            "extracted_data": extracted,
            "financial_analysis": financial,
            "suggestions": ["Show me the breakdown"],
        }

    monkeypatch.setattr(openai_service, "chat", fake_chat)


def _load_messages(session_id: str):
    async def _runner():
        async with database.AsyncSessionLocal() as session:
            result = await session.execute(
                select(ChatMessageDB).where(ChatMessageDB.session_id == session_id).order_by(ChatMessageDB.created_at)
            )
            return result.scalars().all()

    return asyncio.run(_runner())


def test_chat_roundtrip_and_session_adoption(client: TestClient, monkeypatch):
    headers = register_user(client, email="chatter@example.com")
    _mock_chat(monkeypatch, extracted={"attendees": 300})
    session_id = str(uuid.uuid4())

    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Plan a 300-person conference"}],
            "event_context": {"session_id": session_id},
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Mocked reply"
    assert body["extracted_data"] == {"attendees": 300}
    # A valid client UUID is honored so history accrues under the client's id.
    assert body["session_id"] == session_id

    # Second turn on the same session accumulates history.
    client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Make it hybrid"}],
            "event_context": {"session_id": session_id},
        },
        headers=headers,
    )
    history = client.get(f"/api/chat/history/{session_id}", headers=headers)
    assert history.status_code == 200
    roles = [m["role"] for m in history.json()]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_invalid_session_id_replaced_with_server_uuid(client: TestClient, monkeypatch):
    headers = register_user(client, email="badsession@example.com")
    _mock_chat(monkeypatch)

    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "event_context": {"session_id": "session-abc123"},
        },
        headers=headers,
    )
    returned = response.json()["session_id"]
    assert returned != "session-abc123"
    uuid.UUID(returned)  # server-minted valid UUID


def test_llm_failure_returns_503_but_persists_user_turn(client: TestClient, monkeypatch):
    headers = register_user(client, email="outage@example.com")

    async def failing_chat(messages, event_context=None, financial_provider=None):
        raise openai_service.ChatServiceError("AI service unavailable: APITimeoutError")

    monkeypatch.setattr(openai_service, "chat", failing_chat)
    session_id = str(uuid.uuid4())

    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "important question"}],
            "event_context": {"session_id": session_id},
        },
        headers=headers,
    )
    assert response.status_code == 503

    persisted = _load_messages(session_id)
    assert len(persisted) == 1
    assert persisted[0].role == "user"
    assert persisted[0].content == "important question"


def test_financial_provider_wired_for_selected_scenario(client: TestClient, monkeypatch):
    headers = register_user(client, email="chatfin@example.com")
    scenario = create_scenario(client, headers)
    capture = {}
    _mock_chat(monkeypatch, capture=capture)

    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "What are my tax savings?"}],
            "scenario_id": scenario["scenario_id"],
        },
        headers=headers,
    )
    assert response.status_code == 200
    analysis = response.json()["financial_analysis"]
    assert analysis is not None
    assert analysis["total_co2e_reduced"] == pytest.approx(scenario["emissions"]["total_tco2e"] * 0.30, rel=1e-3)
    assert "carbon_tax_savings" in analysis

    # Without a scenario, no provider is passed.
    client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "savings?"}]},
        headers=headers,
    )
    assert capture["financial_provider"] is None


def test_history_scoped_per_user(client: TestClient, monkeypatch):
    headers_a = register_user(client, email="hist-a@example.com")
    headers_b = register_user(client, email="hist-b@example.com")
    _mock_chat(monkeypatch)
    session_id = str(uuid.uuid4())

    client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "secret"}], "event_context": {"session_id": session_id}},
        headers=headers_a,
    )

    assert client.get(f"/api/chat/history/{session_id}", headers=headers_b).json() == []
    assert len(client.get(f"/api/chat/history/{session_id}", headers=headers_a).json()) == 2
