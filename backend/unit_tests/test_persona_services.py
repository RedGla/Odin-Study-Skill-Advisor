import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
import pytest
import docs_service as docs
import personas_service as personas
import llm_service as llm

FETCH_PERSONAS = personas._fetch_personas

ROWS = [["odin", "Odin", "odin-doc", "ground", "TRUE", "FALSE"],
        ["persona_2", "Hela", "hela-doc", "ground", "TRUE", "TRUE"],
        ["off", "Disabled", "off-doc", "ground", "FALSE", "FALSE"]]

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    docs._cache.clear()
    personas._cache = None
    monkeypatch.setattr(docs, "_cache_lock", asyncio.Lock())
    monkeypatch.setattr(personas, "_cache_lock", asyncio.Lock())
    monkeypatch.setattr(docs, "_emit_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(personas, "_fetch_personas", lambda: personas.parse_rows(ROWS))

async def test_registry():
    parsed = personas.parse_rows(ROWS)
    assert parsed[0]["enabled"] is True
    assert parsed[0]["is_default"] is False
    assert parsed[2]["enabled"] is False
    assert [p["persona_id"] for p in await personas.get_personas()] == ["odin", "persona_2"]
    assert (await personas.get_default_persona())["persona_id"] == "persona_2"
    assert await personas.get_persona("off") is None
    assert (await personas.get_persona("off", True))["enabled"] is False

async def test_stale_and_cold_fallback(monkeypatch):
    await personas.get_personas()
    personas._cache = (time.monotonic() - 1000, personas._cache[1])
    def fail():
        raise personas.PersonasServiceError("offline")
    monkeypatch.setattr(personas, "_fetch_personas", fail)
    assert (await personas.get_default_persona())["persona_id"] == "persona_2"
    personas._cache = None
    assert (await personas.get_default_persona())["persona_id"] == "odin"
    assert await personas.get_persona("persona_2") is None

async def test_document_ids_and_cache(monkeypatch):
    fetch = MagicMock(side_effect=lambda document_id: document_id)
    monkeypatch.setattr(docs, "_fetch_document", fetch)
    for persona in personas.parse_rows(ROWS)[:2]:
        assert (await docs.get_advisor_context(persona))["system_prompt"] == persona["prompt_doc_id"]
    assert "document:odin-doc" in docs._cache and "document:hela-doc" in docs._cache
    assert fetch.call_count == 3
    assert await docs.get_system_prompt() == docs.SYSTEM_PROMPT_DOCUMENT_ID
    assert await docs.get_grounding_document() == docs.GROUNDING_DOCUMENT_ID

async def test_docs_api_id(monkeypatch):
    service = MagicMock()
    service.documents.return_value.get.return_value.execute.return_value = {"body": {"content": [{"textRun": {"content": "Prompt"}}]}}
    monkeypatch.setattr(docs, "build", lambda *a, **k: service)
    monkeypatch.setattr(docs, "_credentials", lambda: object())
    assert docs._fetch_document("arbitrary") == "Prompt"
    service.documents.return_value.get.assert_called_once_with(documentId="arbitrary")

async def test_llm_persona_and_reused_context(monkeypatch):
    context = {"system_prompt": "Hela prompt", "grounding_document": "study advice"}
    get_context = AsyncMock(return_value=context)
    completion = AsyncMock(return_value={"content": "reply", "prompt_tokens": 1, "completion_tokens": 1})
    monkeypatch.setattr(docs, "get_advisor_context", get_context)
    monkeypatch.setattr(llm, "get_chat_completion", completion)
    persona = personas.parse_rows(ROWS)[1]
    await llm.generate_llm_response([{"role": "user", "content": "study"}], persona=persona)
    get_context.assert_awaited_once_with(persona)
    get_context.reset_mock()
    await llm.generate_llm_response([], persona=persona, advisor_context=context)
    get_context.assert_not_awaited()
    assert completion.call_args.args[0][0]["content"].startswith("Hela prompt")

@pytest.mark.parametrize("rows", [[ROWS[0], ROWS[0]], [["id", "name", "prompt", "ground", "maybe", "FALSE"]]])
def test_invalid_registry(rows):
    with pytest.raises(personas.PersonasServiceError):
        personas.parse_rows(rows)


async def test_stale_document_cache(monkeypatch):
    docs._cache["document:hela"] = (time.monotonic() - 1000, "cached Hela")
    def fail(document_id):
        raise docs.DocsServiceError("offline")
    monkeypatch.setattr(docs, "_fetch_document", fail)
    assert await docs.get_document("hela") == "cached Hela"
    with pytest.raises(docs.DocsServiceError):
        await docs.get_document("odin")


def test_sheet_api(monkeypatch):
    service = MagicMock()
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {"values": ROWS}
    monkeypatch.setattr(personas, "build", lambda *a, **k: service)
    monkeypatch.setattr(docs, "_credentials", lambda: object())
    assert len(FETCH_PERSONAS()) == 3
    service.spreadsheets.return_value.values.return_value.get.assert_called_once_with(
        spreadsheetId=personas.SHEET_ID, range=personas.SHEET_RANGE)


def test_missing_credentials_are_lazy(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64", raising=False)
    with pytest.raises(docs.DocsServiceError):
        docs._credentials()


async def test_no_marked_default_uses_first_enabled(monkeypatch):
    rows = personas.parse_rows(ROWS)
    for row in rows:
        row["is_default"] = False
    monkeypatch.setattr(personas, "_fetch_personas", lambda: rows)
    assert (await personas.get_default_persona())["persona_id"] == "odin"


@pytest.mark.parametrize("rows", [[], [ROWS[2]]])
async def test_empty_or_disabled_registry_does_not_enable_odin(monkeypatch, rows):
    monkeypatch.setattr(personas, "_fetch_personas", lambda: personas.parse_rows(rows))
    assert await personas.get_personas() == []
    with pytest.raises(personas.PersonasServiceError):
        await personas.get_default_persona()
    assert await personas.get_persona("odin") is None
    if rows:
        assert (await personas.get_persona("off", True))["enabled"] is False


def test_multiple_enabled_defaults_rejected():
    rows = [list(row) for row in ROWS[:2]]
    rows[0][5] = "TRUE"
    with pytest.raises(personas.PersonasServiceError):
        personas.parse_rows(rows)


def test_credentials_include_both_readonly_scopes(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64", raising=False)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{}')
    factory = MagicMock()
    monkeypatch.setattr(docs.service_account.Credentials, "from_service_account_info", factory)
    docs._credentials()
    factory.assert_called_once_with({}, scopes=[docs.GOOGLE_DOCS_SCOPE, docs.GOOGLE_SHEETS_SCOPE])
