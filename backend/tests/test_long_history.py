from tests.helpers import session_token
"""Long conversation history must be truncated rather than blowing up the
OpenRouter payload.  Validates the MAX_HISTORY_MESSAGES trim in main.py."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import limits
import models
from main import app
from tests.helpers import cleanup_user, create_user


@pytest.mark.asyncio
async def test_long_history_is_trimmed_and_request_succeeds(db, monkeypatch):
    """Build a conversation with 80 completed message pairs (160 messages total),
    then send a new message.  With MAX_HISTORY_MESSAGES=50, the history passed
    to the LLM should be trimmed and the request should complete with 200."""
    # Relax caps/rate limits so they don't interfere.
    monkeypatch.setattr(limits, "MAX_MESSAGES_PER_DAY", 500)
    monkeypatch.setattr(limits, "RATE_LIMIT_MAX_REQUESTS", 500)

    user = create_user(db)
    user_id = str(user.id)
    conv = models.Conversation(user_id=user_id, title="Long History")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    conversation_id = str(conv.id)

    # Insert 80 completed user+assistant pairs = 160 messages.
    for i in range(80):
        db.add(models.Message(
            conversation_id=conversation_id,
            sender="user",
            content=f"User message {i}",
            status=models.MessageStatus.COMPLETED.value,
        ))
        db.add(models.Message(
            conversation_id=conversation_id,
            sender="assistant",
            content=f"Assistant reply {i}",
            status=models.MessageStatus.COMPLETED.value,
        ))
    db.commit()
    db.close()

    captured_history: list[list[dict]] = []

    async def fake_llm(messages: list[dict]) -> dict:
        captured_history.append(messages)
        return {
            "content": "ok",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "docs_fetch_ms": 0.0,
            "llm_call_ms": 0.0,
        }

    try:
        with patch("main.generate_llm_response", new=AsyncMock(side_effect=fake_llm)):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={"Origin": "http://localhost:5173"}) as client:
                client.cookies.set("session_token", session_token(user_id))
                client.headers["Origin"] = "http://localhost:5173"
                resp = await client.post(
                    f"/conversations/{conversation_id}/messages",
                    json={"content": "new message"},
                )
    finally:
        cleanup_user(user_id)

    # The request itself must succeed.
    assert resp.status_code == 200, resp.text

    # The model context is bounded, while older information is summarized.
    # 80 pairs + 1 new user message = 161 completed messages, but only the
    # last MAX_HISTORY_MESSAGES (default 50) should be sent.
    assert len(captured_history) == 1
    sent_history = captured_history[0]
    assert len(sent_history) <= 50, (
        f"Expected at most 50 history messages but got {len(sent_history)}"
    )
    # The very last message should be the one we just sent.
    assert sent_history[-1]["content"] == "new message"
    assert sent_history[-1]["role"] == "user"
    assert any("User message 0" in item["content"] for item in sent_history)
