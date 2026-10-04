import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from app.config import settings
from app.models.schemas import ChatMessage
from app.services import openai_service as chat_service
from app.services import web_search_agent as fetch
from app.services.citations import remap_citations
from app.services.claims import sanitize_claim_language


def message(text, annotations=None):
    return NS(type="message", content=[NS(type="output_text", text=text, annotations=annotations or [])])


def response(items, text="", status="completed"):
    return NS(id="resp_test", status=status, output=items, output_text=text)


def mock_client(monkeypatch, module, responses):
    create = AsyncMock(side_effect=responses)
    monkeypatch.setattr(module, "get_client", lambda: NS(responses=NS(create=create)))
    return create


def test_refresh_deadline_preserves_completed_results_and_cancels_pending(monkeypatch):
    fast, slow = NS(name="fast"), NS(name="slow")
    cancelled, persisted = [], []
    async def run_task(agent, token, force, semaphore):
        if agent is fast:
            return {"status": "success", "updated_fields": ["grid.factor"]}
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(agent.name)
    async def persist(agent, token, status, **kwargs):
        persisted.append((agent.name, token, status))
        return []
    release = AsyncMock()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-only")
    monkeypatch.setattr(fetch, "REGISTERED_AGENTS", [fast, slow])
    monkeypatch.setattr(fetch, "REFRESH_TIMEOUT_S", 0.01)
    monkeypatch.setattr(fetch, "acquire_refresh_lease", AsyncMock(return_value="lease"))
    monkeypatch.setattr(fetch, "release_refresh_lease", release)
    monkeypatch.setattr(fetch, "_run_task", run_task)
    monkeypatch.setattr(fetch, "_persist_task", persist)
    result = asyncio.run(fetch.run_and_update())
    assert result["status"] == "partial"
    assert result["merge_summary"]["updated_fields"] == ["grid.factor"]
    assert result["agent_results"]["slow"]["status"] == "timeout"
    assert cancelled == ["slow"]
    assert persisted == [("slow", "lease", "timeout")]
    release.assert_awaited_once_with("lease")


def test_chat_responses_with_multiple_tools_and_zero_reduction(monkeypatch):
    call1 = NS(type="function_call", name="update_event_scenario", call_id="c1",
               arguments=json.dumps({"attendees": 100, "venue_kwh": 0}))
    call2 = NS(type="function_call", name="request_financial_analysis", call_id="c2",
               arguments=json.dumps({"region": "singapore", "reduction_pct": 0, "actions": []}))
    create = mock_client(monkeypatch, chat_service, [response([call1, call2]), response([message("Done")])])
    captured = []
    def financial(args):
        captured.append(args)
        return {"carbon_tax_savings": 0}
    result = asyncio.run(chat_service.chat([ChatMessage(content="Plan my event")], financial_provider=financial))
    assert result["extracted_data"] == {"attendees": 100, "venue_kwh": 0}
    assert captured == [{"region": "singapore", "reduction_pct": 0, "actions": []}]
    request = create.call_args_list[0].kwargs
    assert request["model"] == settings.OPENAI_MODEL == "gpt-6-luna"
    assert request["store"] is False
    assert "temperature" not in request and "max_output_tokens" in request
    assert any(tool["type"] == "web_search" for tool in request["tools"])
    outputs = [item for item in create.call_args_list[1].kwargs["input"] if isinstance(item, dict) and item.get("type") == "function_call_output"]
    assert {item["call_id"] for item in outputs} == {"c1", "c2"}


def test_chat_invalid_tool_data_is_reported_then_corrected(monkeypatch):
    bad = NS(type="function_call", name="update_event_scenario", call_id="bad", arguments='{"attendees":-1}')
    good = NS(type="function_call", name="update_event_scenario", call_id="good", arguments='{"attendees":20}')
    create = mock_client(monkeypatch, chat_service, [response([bad]), response([good]), response([message("20 guests")])])
    result = asyncio.run(chat_service.chat([ChatMessage(content="20 guests")]))
    assert result["extracted_data"] == {"attendees": 20}
    error = next(item for item in create.call_args_list[1].kwargs["input"] if isinstance(item, dict) and item.get("call_id") == "bad")
    assert "Invalid tool arguments" in error["output"]


@pytest.mark.parametrize("status", ["incomplete", "failed"])
def test_chat_incomplete_response_is_503_service_error(monkeypatch, status):
    mock_client(monkeypatch, chat_service, [response([], status=status)])
    with pytest.raises(chat_service.ChatServiceError):
        asyncio.run(chat_service.chat([ChatMessage(content="hi")]))


def test_tool_round_limit(monkeypatch):
    call = NS(type="function_call", name="unknown", call_id="c", arguments="{}")
    mock_client(monkeypatch, chat_service, [response([call])] * 3)
    with pytest.raises(chat_service.ChatServiceError, match="round limit"):
        asyncio.run(chat_service.chat([ChatMessage(content="hi")]))


def test_strict_schema_preserves_partial_updates():
    for tool in chat_service.RESPONSE_TOOLS:
        if tool["type"] != "function":
            continue
        schema = tool["parameters"]
        assert tool["strict"] is True and schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
    schema = chat_service.RESPONSE_TOOLS[0]["parameters"]
    assert "null" in schema["properties"]["attendees"]["type"]
    assert None in schema["properties"]["catering_type"]["enum"]


def test_citations_remap_after_redaction_and_unicode():
    original = "🌱 carbon neutral. The current tax is 45."
    start = original.index("The")
    cleaned, _ = sanitize_claim_language(original)
    citations = remap_citations(original, cleaned, [
        {"url": "https://www.nea.gov.sg/tax", "title": "NEA", "start_index": start, "end_index": len(original)},
        {"url": "javascript:alert(1)", "title": "bad", "start_index": start, "end_index": len(original)},
        {"url": "https://example.com", "title": "removed", "start_index": 2, "end_index": 16},
    ])
    assert len(citations) == 1
    assert citations[0]["start_index"] == len(cleaned[:cleaned.index("The")].encode("utf-16-le")) // 2


def test_fetch_search_then_structured_extraction_with_evidence(monkeypatch):
    agent = fetch.SingaporeGridFactorAgent()
    url = "https://www.ema.gov.sg/statistics/grid"
    search = NS(type="web_search_call", action=NS(sources=[NS(url=url)]))
    raw = {"factor": 0.402, "source_url": url, "source_date": None, "year": 2025,
           "unit": "kg_co2e_per_kwh", "methodology": "Singapore grid average", "currency": None}
    create = mock_client(monkeypatch, fetch, [response([search], "Grid average 0.402 in 2025"), response([], json.dumps(raw))])
    result = asyncio.run(agent.run())
    assert result["factor_value"] == 0.402
    assert result["_provenance"]["source_url"] == url
    assert result["_provenance"]["original_unit"] == raw["unit"]
    assert create.call_args_list[0].kwargs["tool_choice"] == "required"
    assert "Return ONLY" not in create.call_args_list[0].kwargs["input"]
    assert create.call_args_list[0].kwargs["tools"][0]["filters"]["allowed_domains"] == ["ema.gov.sg"]
    assert create.call_args_list[1].kwargs["text"]["format"]["strict"] is True


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, 2026])
def test_grid_rejects_invalid_values(value):
    assert fetch.SingaporeGridFactorAgent().extract({"factor": value, "unit": "kg_co2e_per_kwh"})["factor_value"] is None


def test_missing_units_and_incompatible_methodology_preserve_factors():
    assert fetch.SingaporeGridFactorAgent().extract({"factor": 0.4})["factor_value"] is None
    assert fetch.CateringEmissionFactorAgent().extract({"beef_kg_co2e_per_meal": 30, "unit": "kg_co2e_per_kg"}) == {}
    assert fetch.FlightEmissionFactorAgent().extract({"short_haul_economy": 0.15, "unit": "kg_co2e_per_passenger_km", "radiative_forcing": False}) == {}


def test_evidence_rejects_unretrieved_source_and_future_year():
    agent = fetch.SingaporeGridFactorAgent()
    raw = {"source_url": agent.url, "year": 2999, "methodology": "grid"}
    with pytest.raises(fetch.NoDataError, match="supporting URL"):
        agent._validate_evidence(raw, set())
    with pytest.raises(fetch.NoDataError, match="year"):
        agent._validate_evidence(raw, {agent.url})


def test_evidence_tracking_parameters_do_not_change_document_identity():
    agent = fetch.SingaporeGridFactorAgent()
    raw = {"source_url": agent.url, "year": 2024, "methodology": "grid average"}
    cited = agent.url + "?utm_source=openai"
    agent._validate_evidence(raw, {cited})
    assert raw["source_url"] == cited


def test_opened_pages_are_retrieved_sources():
    url = "https://www.ema.gov.sg/resources/singapore-energy-statistics/chapter2"
    opened = NS(type="web_search_call", action=NS(type="open_page", url=url))
    assert fetch._source_urls(response([opened])) == {url}
