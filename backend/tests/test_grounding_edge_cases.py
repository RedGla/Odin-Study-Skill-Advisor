from tests.helpers import session_token
"""Edge cases for _select_grounding: empty and whitespace-only documents."""

import pytest
from unittest.mock import AsyncMock, patch
import time

import docs_service
from llm_service import _select_grounding
from tests.helpers import create_user, cleanup_user


# ---------------------------------------------------------------------------
# Unit tests — _select_grounding returns "" gracefully, never raises
# ---------------------------------------------------------------------------

class TestSelectGroundingUnit:
    def test_empty_document_returns_empty_string(self):
        assert _select_grounding("", "some query") == ""

    def test_whitespace_only_document_returns_empty_string(self):
        assert _select_grounding("   \n\n\t  \n  ", "some query") == ""

    def test_normal_document_with_empty_query_returns_empty_string(self):
        # No query terms → no overlap → score 0 → nothing selected
        assert _select_grounding("This is real grounding content.", "") == ""

    def test_normal_document_with_matching_query(self):
        doc = "Eskwelabs offers data science bootcamps."
        result = _select_grounding(doc, "data science")
        assert "data" in result.lower()


# ---------------------------------------------------------------------------
# Integration test — chat endpoint succeeds when grounding doc is empty
# ---------------------------------------------------------------------------

@pytest.fixture
def test_user(db):
    user = create_user(db)
    yield user
    cleanup_user(str(user.id))


def test_chat_succeeds_with_empty_grounding_document(client, test_user):
    """The endpoint must still return 200 when the grounding document is empty
    (cache returns an empty string), i.e. the system message is just the persona
    with no grounding block appended."""
    # Pre-warm the cache: valid system prompt, but empty grounding doc
    docs_service._cache.clear()
    docs_service._cache["system_prompt"] = (time.monotonic(), "You are an advisor.")
    docs_service._cache["grounding_document"] = (time.monotonic(), "")

    response = client.post(
        "/conversations",
        json={"title": "Grounding Edge"},
        cookies={"session_token": session_token(str(test_user.id))},
    )
    conv_id = response.json()["id"]

    llm_reply = {
        "content": "Sure, I can help!",
        "prompt_tokens": 10,
        "completion_tokens": 5,
    }

    with patch("llm_service.get_chat_completion", new_callable=AsyncMock, return_value=llm_reply):
        resp = client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Hello"},
            cookies={"session_token": session_token(str(test_user.id))},
        )

    assert resp.status_code == 200
    assert resp.json()["content"] == "Sure, I can help!"


def test_chat_succeeds_with_whitespace_only_grounding_document(client, test_user):
    """Same as above but with a whitespace-only grounding doc."""
    docs_service._cache.clear()
    docs_service._cache["system_prompt"] = (time.monotonic(), "You are an advisor.")
    docs_service._cache["grounding_document"] = (time.monotonic(), "   \n\n  \t  ")

    response = client.post(
        "/conversations",
        json={"title": "Whitespace Grounding"},
        cookies={"session_token": session_token(str(test_user.id))},
    )
    conv_id = response.json()["id"]

    llm_reply = {
        "content": "Understood!",
        "prompt_tokens": 8,
        "completion_tokens": 3,
    }

    with patch("llm_service.get_chat_completion", new_callable=AsyncMock, return_value=llm_reply):
        resp = client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Hi"},
            cookies={"session_token": session_token(str(test_user.id))},
        )

    assert resp.status_code == 200
    assert resp.json()["content"] == "Understood!"
