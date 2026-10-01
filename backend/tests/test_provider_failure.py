from tests.helpers import session_token
import pytest
import httpx
from unittest.mock import patch, AsyncMock, Mock
from llm_service import LLMError
from tests.helpers import create_user, cleanup_user

@pytest.fixture
def test_user(db):
    user = create_user(db)
    yield user
    cleanup_user(str(user.id))

def test_llm_provider_timeout(client, test_user):
    response = client.post("/conversations", json={"title": "Test"}, cookies={"session_token": session_token(str(test_user.id))})
    conv_id = response.json()["id"]

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")) as provider:
        response = client.post(f"/conversations/{conv_id}/messages", json={"content": "Hello"}, cookies={"session_token": session_token(str(test_user.id))})
        assert response.status_code == 502
        provider.assert_awaited_once()
        messages = client.get(f"/conversations/{conv_id}/messages", cookies={"session_token": session_token(str(test_user.id))}).json()
        assert messages[1]["status"] == "error"
        assert messages[1]["content"] == "Sorry, I couldn't reach the advisor model right now. Please try again in a moment."

def test_llm_provider_500(client, test_user):
    response = client.post("/conversations", json={"title": "Test"}, cookies={"session_token": session_token(str(test_user.id))})
    conv_id = response.json()["id"]

    mock_response = httpx.Response(500, request=httpx.Request("POST", "url"), text="Internal Server Error")
    with patch("httpx.AsyncClient.post", side_effect=httpx.HTTPStatusError("500 Error", request=mock_response.request, response=mock_response)) as provider:
        response = client.post(f"/conversations/{conv_id}/messages", json={"content": "Hello"}, cookies={"session_token": session_token(str(test_user.id))})
        assert response.status_code == 502
        provider.assert_awaited_once()
        messages = client.get(f"/conversations/{conv_id}/messages", cookies={"session_token": session_token(str(test_user.id))}).json()
        assert messages[1]["status"] == "error"

def test_llm_provider_malformed_body(client, test_user):
    response = client.post("/conversations", json={"title": "Test"}, cookies={"session_token": session_token(str(test_user.id))})
    conv_id = response.json()["id"]

    mock_post = AsyncMock()
    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock(return_value=None)  # httpx calls this synchronously
    mock_response.json = Mock(return_value={"not_choices": "some data"})  # also synchronous
    mock_post.return_value = mock_response

    with patch("httpx.AsyncClient.post", mock_post):
        response = client.post(f"/conversations/{conv_id}/messages", json={"content": "Hello"}, cookies={"session_token": session_token(str(test_user.id))})
        assert response.status_code == 502
        mock_post.assert_awaited_once()
        messages = client.get(f"/conversations/{conv_id}/messages", cookies={"session_token": session_token(str(test_user.id))}).json()
        assert messages[1]["status"] == "error"
