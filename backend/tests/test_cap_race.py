from tests.helpers import session_token
"""Concurrent POST /messages must not both pass when the user is at cap-minus-one."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import limits
import models
import usage_service
from main import app
from tests.helpers import cleanup_user, create_user


@pytest.mark.asyncio
async def test_only_one_of_two_concurrent_messages_succeeds_at_cap_minus_one(db, monkeypatch):
    monkeypatch.setattr(limits, "MAX_MESSAGES_PER_DAY", 2)
    monkeypatch.setattr(limits, "RATE_LIMIT_MAX_REQUESTS", 50)

    user = create_user(db)
    user_id = str(user.id)
    conversation = models.Conversation(user_id=user_id, title="Race")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    conversation_id = str(conversation.id)

    counter = usage_service.get_or_create_today_counter(db, user_id)
    setattr(counter, "messages_today", limits.MAX_MESSAGES_PER_DAY - 1)
    db.commit()
    db.close()

    llm_reply = {
        "content": "ok",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "docs_fetch_ms": 0.0,
        "llm_call_ms": 0.0,
    }

    try:
        with patch("main.generate_llm_response", new=AsyncMock(return_value=llm_reply)):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={"Origin": "http://localhost:5173"}) as client:
                client.cookies.set("session_token", session_token(user_id))
                client.headers["Origin"] = "http://localhost:5173"

                async def send_message() -> int:
                    response = await client.post(
                        f"/conversations/{conversation_id}/messages",
                        json={"content": "hello"},
                    )
                    return response.status_code

                statuses = await asyncio.gather(send_message(), send_message())
    finally:
        cleanup_user(user_id)

    successes = [status for status in statuses if status == 200]
    blocked = [status for status in statuses if status == 429]
    assert len(successes) == 1, statuses
    assert len(blocked) == 1, statuses
