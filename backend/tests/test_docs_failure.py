from tests.helpers import session_token
import pytest
from unittest.mock import patch, AsyncMock
import time
import docs_service
from tests.helpers import create_user, cleanup_user

@pytest.fixture
def test_user(db):
    user = create_user(db)
    yield user
    cleanup_user(str(user.id))

def test_docs_service_failure_no_cache(client, test_user):
    docs_service._cache.clear()
    response = client.post("/conversations", json={"title": "Test"}, cookies={"session_token": session_token(str(test_user.id))})
    conv_id = response.json()["id"]

    with patch("docs_service._fetch_document", side_effect=docs_service.DocsServiceError("Google Docs down")):
        response = client.post(f"/conversations/{conv_id}/messages", json={"content": "Hello"}, cookies={"session_token": session_token(str(test_user.id))})
        
        assert response.status_code == 502
        assert response.json()["detail"] == "LLM generation failed"
        assert "DocsServiceError" not in response.text
        
        messages = client.get(f"/conversations/{conv_id}/messages", cookies={"session_token": session_token(str(test_user.id))}).json()
        assert len(messages) == 2
        assert messages[1]["sender"] == "assistant"
        assert messages[1]["status"] == "error"
        assert messages[1]["content"] == "Sorry, I couldn't reach the advisor model right now. Please try again in a moment."

def test_docs_service_failure_warm_cache(client, test_user):
    docs_service._cache.clear()
    docs_service._cache["system_prompt"] = (time.monotonic(), "Cached System Prompt")
    docs_service._cache["grounding_document"] = (time.monotonic(), "Cached Grounding")

    response = client.post("/conversations", json={"title": "Test"}, cookies={"session_token": session_token(str(test_user.id))})
    conv_id = response.json()["id"]

    with patch("docs_service._fetch_document", side_effect=docs_service.DocsServiceError("Google Docs down")):
        with patch("llm_service.get_chat_completion", new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = {"content": "Response from LLM", "prompt_tokens": 10, "completion_tokens": 10}
            
            response = client.post(f"/conversations/{conv_id}/messages", json={"content": "Hello"}, cookies={"session_token": session_token(str(test_user.id))})
            
            assert response.status_code == 200
            assert response.json()["content"] == "Response from LLM"
