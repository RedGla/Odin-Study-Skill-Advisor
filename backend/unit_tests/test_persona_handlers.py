"""Endpoint-handler behavior with mocked storage; real routing/auth lives in tests/."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import HTTPException
import main
import personas_service
import docs_service


def persona(enabled=True):
    return dict(personas_service.odin_fallback(), persona_id="persona_2", display_name="Hela", enabled=enabled)


async def test_discovery_and_creation(monkeypatch):
    config = persona()
    monkeypatch.setattr(personas_service, "get_personas", AsyncMock(return_value=[config]))
    assert await main.list_personas(SimpleNamespace(id="user")) == [
        {"persona_id": "persona_2", "display_name": "Hela", "is_default": True}]
    monkeypatch.setattr(main, "check_chat_enabled", lambda db: None)
    default = AsyncMock(return_value=config)
    resolve = AsyncMock(return_value=config)
    monkeypatch.setattr(personas_service, "get_default_persona", default)
    monkeypatch.setattr(personas_service, "get_persona", resolve)
    db = MagicMock()
    for payload in ({"title": "legacy"}, {"persona_id": "persona_2"}):
        result = await main.create_conversation(main.CreateConversationSchema(**payload), db, SimpleNamespace(id="user"))
        assert result["persona_id"] == "persona_2"
        assert db.add.call_args.args[0].persona_id == "persona_2"
    default.assert_awaited_once()
    resolve.assert_awaited_once_with("persona_2")
    resolve.return_value = None
    with pytest.raises(HTTPException) as error:
        await main.create_conversation(main.CreateConversationSchema(persona_id="off"), db, SimpleNamespace(id="user"))
    assert error.value.status_code == 400
    default.side_effect = personas_service.PersonasServiceError("no enabled rows")
    with pytest.raises(HTTPException) as error:
        await main.create_conversation(main.CreateConversationSchema(), db, SimpleNamespace(id="user"))
    assert error.value.status_code == 503


async def test_stored_disabled_persona_and_context_shared_with_generation(monkeypatch):
    config = persona(False)
    conv = SimpleNamespace(persona_id="persona_2")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = conv
    resolve = AsyncMock(return_value=config)
    monkeypatch.setattr(personas_service, "get_persona", resolve)
    monkeypatch.setattr(main, "check_chat_enabled", lambda db: None)
    monkeypatch.setattr(main.config_service, "get", lambda db: dict(rate_limit_requests=5, rate_limit_window_seconds=60, daily_token_cap=50000))
    monkeypatch.setattr(main.limits, "check_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(main.telemetry_service, "emit", lambda *a, **k: None)
    context = {"system_prompt": "Hela instructions", "grounding_document": "study reference"}
    advisor = AsyncMock(return_value=context)
    provider = AsyncMock(return_value={"content": "reply", "prompt_tokens": 1, "completion_tokens": 1})
    monkeypatch.setattr(docs_service, "get_advisor_context", advisor)
    monkeypatch.setattr(main, "generate_llm_response", provider)
    history = [{"role": "user", "content": "study"}]
    async def threadpool(function, *args, **kwargs):
        if function is main.prepare_reserved_turn:
            return object(), "assistant", history
        if function is main.usage_service.reserve_token_budget:
            return SimpleNamespace(completion_tokens=10)
        if function is main.finish_reserved_turn:
            return {"content": "reply", "est_cost": 0}
        raise AssertionError("Unexpected database operation")
    monkeypatch.setattr(main, "run_in_threadpool", threadpool)
    await main.post_message("chat", main.SendMessageSchema(content="study"), db, SimpleNamespace(id="user"))
    resolve.assert_awaited_once_with("persona_2", include_disabled=True)
    assert advisor.call_args.kwargs["persona"] is config
    assert provider.call_args.kwargs["persona"] is config
    assert provider.call_args.kwargs["advisor_context"] is context
    resolve.return_value = None
    provider.reset_mock()
    with pytest.raises(HTTPException) as error:
        await main.post_message("chat", main.SendMessageSchema(content="study"), db, SimpleNamespace(id="user"))
    assert error.value.status_code == 503
    provider.assert_not_awaited()
