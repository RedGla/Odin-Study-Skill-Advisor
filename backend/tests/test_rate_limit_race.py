from tests.helpers import session_token
"""Concurrent POST /messages must not all pass when the user is at rate-limit minus one.

Mirrors test_cap_race.py but targets the in-memory per-user fixed-window
rate limiter in limits.py instead of the DB-backed daily cap.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import limits
import models
from main import app
from tests.helpers import cleanup_user, create_user


@pytest.mark.asyncio
async def test_only_one_of_concurrent_requests_succeeds_at_rate_limit(db, monkeypatch):
    # Tiny window so all requests fall inside the same window.
    monkeypatch.setattr(limits, "RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(limits, "RATE_LIMIT_WINDOW_SECONDS", 120)
    # Set daily cap high so it never interferes.
    monkeypatch.setattr(limits, "MAX_MESSAGES_PER_DAY", 500)

    user = create_user(db)
    user_id = str(user.id)
    conversation = models.Conversation(user_id=user_id, title="RateRace")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    conversation_id = str(conversation.id)
    db.close()

    # Pre-fill the in-memory request log to MAX - 1 so the user has exactly
    # one slot remaining before the next request would be blocked.
    import time

    now = time.monotonic()
    limits._request_log[user_id] = [now] * (limits.RATE_LIMIT_MAX_REQUESTS - 1)

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

                # Fire 3 concurrent requests; only 1 slot is open.
                statuses = await asyncio.gather(
                    send_message(), send_message(), send_message()
                )
    finally:
        # Clean up in-memory state so other tests aren't affected.
        limits._request_log.pop(user_id, None)
        cleanup_user(user_id)

    successes = [s for s in statuses if s == 200]
    blocked = [s for s in statuses if s == 429]

    assert len(successes) == 1, (
        f"Expected at most 1 success but got {len(successes)}: {statuses}"
    )
    assert len(blocked) == 2, (
        f"Expected at least 2 blocked but got {len(blocked)}: {statuses}"
    )
