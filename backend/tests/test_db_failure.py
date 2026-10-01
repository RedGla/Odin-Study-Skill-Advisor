from tests.helpers import session_token
"""
DB connection-drop graceful-degradation tests.

Mirrors the pattern of test_docs_failure.py and test_provider_failure.py:
patch the lowest-level DB call to raise sqlalchemy.exc.OperationalError and
assert that every affected endpoint returns 503 with a plain-language message
-- never a 500 stack trace.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError

from tests.helpers import create_user, cleanup_user


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_user(db):
    user = create_user(db)
    yield user
    cleanup_user(str(user.id))


# ---------------------------------------------------------------------------
# Helper -- construct an OperationalError the way SQLAlchemy does internally
# ---------------------------------------------------------------------------

def _make_op_error() -> OperationalError:
    """Minimal OperationalError that exercises the except branch in main.py."""
    return OperationalError(
        "connection lost",
        params=None,
        orig=Exception("server closed the connection unexpectedly"),
    )


# ---------------------------------------------------------------------------
# Test 1 -- GET /conversations returns 503 when the DB is down
# ---------------------------------------------------------------------------

def test_db_connection_drop_on_list_conversations(client, test_user):
    """If the DB drops while listing conversations the response is 503, not 500."""
    with patch("main.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session.query.side_effect = _make_op_error()
        mock_session_local.return_value = mock_session

        response = client.get(
            "/conversations",
            cookies={"session_token": session_token(str(test_user.id))},
        )

    assert response.status_code == 503
    body = response.json()
    assert "detail" in body
    # Must be a plain-language string, not a raw exception repr
    assert "database" in body["detail"].lower()
    assert "OperationalError" not in response.text


# ---------------------------------------------------------------------------
# Test 2 -- GET /conversations/{id}/messages returns 503 when the DB is down
# ---------------------------------------------------------------------------

def test_db_connection_drop_on_get_messages(client, db, test_user):
    """If the DB drops while fetching messages the response is 503, not 500."""
    import models

    # Create the conversation in the real DB first
    conv = models.Conversation(user_id=str(test_user.id), title="Test")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    conv_id = str(conv.id)

    with patch("main.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session.query.side_effect = _make_op_error()
        mock_session_local.return_value = mock_session

        response = client.get(
            f"/conversations/{conv_id}/messages",
            cookies={"session_token": session_token(str(test_user.id))},
        )

    assert response.status_code == 503
    assert "OperationalError" not in response.text
    assert "database" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 3 -- POST /conversations/{id}/messages returns 503 when DB drops
#           after the LLM call (can not persist result row)
# ---------------------------------------------------------------------------

def test_db_connection_drop_on_message_send(client, test_user):
    """
    Simulates a DB dropout after the assistant-pending row is written but
    during the LLM result commit.  The endpoint must return 503 (not 502,
    which is for LLM failures) so the client can distinguish the two modes.
    """
    from unittest.mock import AsyncMock

    # Create a real conversation first
    response = client.post(
        "/conversations",
        json={"title": "DB-drop test"},
        cookies={"session_token": session_token(str(test_user.id))},
    )
    assert response.status_code == 200, response.text
    conv_id = response.json()["id"]

    llm_reply = {"content": "ok", "prompt_tokens": 5, "completion_tokens": 5,
                 "docs_fetch_ms": 0.0, "llm_call_ms": 0.0}

    # Fail the completion transaction, after the provider has returned.
    from sqlalchemy.orm import Session as SASession
    orig_commit = SASession.commit

    provider_completed = {"value": False}

    async def completed_reply(history):
        provider_completed["value"] = True
        return llm_reply

    def patched_commit(self, *args, **kwargs):
        if provider_completed["value"]:
            raise _make_op_error()
        return orig_commit(self, *args, **kwargs)

    with patch("main.generate_llm_response", new=AsyncMock(side_effect=completed_reply)):
        with patch("sqlalchemy.orm.Session.commit", patched_commit):
            response = client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": "Hello, will this persist?"},
                cookies={"session_token": session_token(str(test_user.id))},
            )

    # 503 distinguishes DB dropout from LLM failure (502) or bad request (4xx)
    assert response.status_code == 503, response.text
    assert "OperationalError" not in response.text
    assert "database" in response.json()["detail"].lower()
