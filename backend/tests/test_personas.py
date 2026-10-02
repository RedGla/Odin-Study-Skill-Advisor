from unittest.mock import AsyncMock
import docs_service
import personas_service
import main
import models
from tests.helpers import create_user, session_token


def test_creation_and_generation(client, db, monkeypatch):
    odin = personas_service.odin_fallback()
    hela = dict(odin, persona_id="persona_2", display_name="Hela", prompt_doc_id="hela", is_default=True)
    odin["is_default"] = False
    monkeypatch.setattr(personas_service, "_fetch_personas", lambda: [odin, hela])
    user = create_user(db)
    client.cookies.set("session_token", session_token(str(user.id)))
    choices = client.get("/personas").json()
    assert all(set(p) == {"persona_id", "display_name", "is_default"} for p in choices)
    for payload, expected in [({"title": "legacy client"}, "persona_2"), ({"persona_id": "persona_2"}, "persona_2"), ({"persona_id": "odin"}, "odin")]:
        response = client.post("/conversations", json=payload)
        assert response.status_code == 200
        assert response.json()["persona_id"] == expected
        assert db.get(models.Conversation, response.json()["id"]).persona_id == expected
    cid = client.post("/conversations", json={"persona_id": "persona_2"}).json()["id"]
    context = {"system_prompt": "Hela", "grounding_document": "study"}
    advisor = AsyncMock(return_value=context)
    provider = AsyncMock(return_value={"content": "hello", "prompt_tokens": 1, "completion_tokens": 1})
    monkeypatch.setattr(docs_service, "get_advisor_context", advisor)
    monkeypatch.setattr(main, "generate_llm_response", provider)
    assert client.post(f"/conversations/{cid}/messages", json={"content": "study"}).status_code == 200
    assert advisor.call_args.kwargs["persona"] == provider.call_args.kwargs["persona"] == hela
    assert provider.call_args.kwargs["advisor_context"] is context
    assert client.post("/conversations", json={"persona_id": "missing"}).status_code == 400


def test_legacy_creation_odin(client, db):
    user = create_user(db)
    client.cookies.set("session_token", session_token(str(user.id)))
    assert client.post("/conversations", json={"title": "Old client"}).json()["persona_id"] == "odin"


def test_disabled_persona_retained_and_empty_registry(client, db, monkeypatch):
    user = create_user(db)
    client.cookies.set("session_token", session_token(str(user.id)))
    odin = personas_service.odin_fallback()
    monkeypatch.setattr(personas_service, "_fetch_personas", lambda: [odin])
    cid = client.post("/conversations", json={"persona_id": "odin"}).json()["id"]
    odin["enabled"] = False
    personas_service._cache = None
    assert client.get("/personas").json() == []
    assert client.post("/conversations", json={"title": "default"}).status_code == 503
    assert client.post("/conversations", json={"persona_id": "odin"}).status_code == 400
    provider = AsyncMock(return_value={"content": "reply", "prompt_tokens": 1, "completion_tokens": 1})
    monkeypatch.setattr(main, "generate_llm_response", provider)
    assert client.post(f"/conversations/{cid}/messages", json={"content": "hello"}).status_code == 200
    assert provider.call_args.kwargs["persona"]["enabled"] is False
    personas_service._cache = None
    monkeypatch.setattr(personas_service, "_fetch_personas", lambda: [])
    provider.reset_mock()
    assert client.post(f"/conversations/{cid}/messages", json={"content": "hello"}).status_code == 503
    provider.assert_not_awaited()
