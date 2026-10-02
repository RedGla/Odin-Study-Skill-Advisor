"""Fetch persona prompts and grounding Docs with caches isolated by document ID."""

import asyncio
import json 
import base64
import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger("advisor_console.docs")

GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
GOOGLE_DOCS_SCOPE = "https://www.googleapis.com/auth/documents.readonly"
SYSTEM_PROMPT_DOCUMENT_ID = os.getenv(
    "GOOGLE_SYSTEM_PROMPT_DOCUMENT_ID",
    os.getenv("GOOGLE_DOCS_PROMPT_ID", "1ujFrCT7jG7PzeVcQIsunTXUDa9keuamYY-55k_lkl_4"),
)
GROUNDING_DOCUMENT_ID = os.getenv(
    "GOOGLE_GROUNDING_DOCUMENT_ID",
    os.getenv("GOOGLE_DOCS_GROUNDING_ID", "17rH7oJj3XwwVGZMk_T5JnK-efpiKB-Vi1Z-yXf_y3Lk"),
)
CACHE_TTL_SECONDS = int(os.getenv("GOOGLE_DOCS_CACHE_TTL_SECONDS", "300"))

_cache: dict[str, tuple[float, str]] = {}
_cache_lock = asyncio.Lock()


class DocsServiceError(Exception):
    """Raised when Google Docs credentials or document retrieval fails."""


def _credentials() -> Any:
    """Load Google service-account credentials from the environment.

    Accepts two env-var formats so the same codebase works in both contexts:

    * ``GOOGLE_SERVICE_ACCOUNT_JSON_B64`` — base64-encoded JSON (preferred for
      production / Render, where newlines inside private keys can corrupt plain
      env vars).  Set this on Render's dashboard.

    * ``GOOGLE_SERVICE_ACCOUNT_JSON`` — raw JSON string (convenient for local
      development where the shell can handle embedded newlines).  Set in
      ``backend/.env``.

    Base64 credentials take precedence when both formats are set.
    If neither is set a ``DocsServiceError`` is
    raised with an actionable message so the misconfiguration is obvious.
    """
    b64_val = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "").strip()
    plain_val = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    if b64_val:
        try:
            info = json.loads(base64.b64decode(b64_val))
        except Exception as exc:
            raise DocsServiceError(
                "GOOGLE_SERVICE_ACCOUNT_JSON_B64 is set but could not be decoded; "
                "ensure it is valid base64-encoded JSON."
            ) from exc
    elif plain_val:
        try:
            # Strip optional surrounding single-quotes added by some shells
            info = json.loads(plain_val.strip("'"))
        except Exception as exc:
            raise DocsServiceError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is set but could not be parsed as JSON; "
                "check for unescaped characters in backend/.env."
            ) from exc
    else:
        raise DocsServiceError(
            "No Google service-account credentials found.  "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON_B64 (production) or "
            "GOOGLE_SERVICE_ACCOUNT_JSON (local dev) in your environment."
        )

    return service_account.Credentials.from_service_account_info(
        info, scopes=[GOOGLE_DOCS_SCOPE, GOOGLE_SHEETS_SCOPE]
    )


def extract_text_from_doc(document: dict[str, Any]) -> str:
    parts: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            text_run = value.get("textRun")
            if isinstance(text_run, dict) and text_run.get("content"):
                parts.append(text_run["content"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document.get("body", {}).get("content", []))
    return "".join(parts).strip()


def _extract_text(document: dict[str, Any]) -> str:
    return extract_text_from_doc(document)


def _fetch_document(document_id: str) -> str:
    try:
        service = build("docs", "v1", credentials=_credentials(), cache_discovery=False)
        document = service.documents().get(documentId=document_id).execute()
        content = _extract_text(document)
    except DocsServiceError:
        raise
    except Exception as error:
        raise DocsServiceError(f"Unable to fetch Google Doc {document_id}") from error

    if not content:
        raise DocsServiceError(f"Google Doc {document_id} is empty")
    return content


async def _get_document(document_id: str, cache_key: str, *, user_id=None, conversation_id=None) -> str:
    now = time.monotonic()
    async with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            logger.info("prompt_cache_hit key=%s", cache_key)
            _emit_telemetry("prompt_cache_hit", user_id=user_id, conversation_id=conversation_id)
            return cached[1]

    logger.info("prompt_cache_miss key=%s", cache_key)
    _emit_telemetry("prompt_cache_miss", user_id=user_id, conversation_id=conversation_id)
    try:
        content = await asyncio.to_thread(_fetch_document, document_id)
    except DocsServiceError:
        if cached:
            logger.warning("prompt_cache_miss fallback=stale key=%s", cache_key)
            return cached[1]
        raise

    async with _cache_lock:
        _cache[cache_key] = (time.monotonic(), content)
    return content


async def get_document(document_id: str, user_id=None, conversation_id=None) -> str:
    return await _get_document(document_id, f"document:{document_id}", user_id=user_id, conversation_id=conversation_id)


async def get_system_prompt(*, user_id=None, conversation_id=None) -> str:
    return await get_document(SYSTEM_PROMPT_DOCUMENT_ID, user_id=user_id, conversation_id=conversation_id)

def _emit_telemetry(event: str, **kwargs):
    try:
        from telemetry_service import emit
        emit(event, **kwargs)
    except Exception:
        logger.exception("telemetry_write_failed event=%s", event)


async def get_grounding_document(*, user_id=None, conversation_id=None) -> str:
    return await get_document(GROUNDING_DOCUMENT_ID, user_id=user_id, conversation_id=conversation_id)


async def get_advisor_context(persona=None, *, user_id=None, conversation_id=None) -> dict[str, str]:
    """Load a registry persona, or legacy Odin Docs when no persona is supplied."""
    if persona is not None:
        system_prompt, grounding_document = await asyncio.gather(
            get_document(persona["prompt_doc_id"], user_id=user_id, conversation_id=conversation_id),
            get_document(persona["grounding_doc_id"], user_id=user_id, conversation_id=conversation_id),
        )
        return {"system_prompt": system_prompt, "grounding_document": grounding_document}
    system_prompt, grounding_document = await asyncio.gather(
        get_system_prompt(user_id=user_id, conversation_id=conversation_id),
        get_grounding_document(user_id=user_id, conversation_id=conversation_id),
    )
    return {
        "system_prompt": system_prompt,
        "grounding_document": grounding_document,
    }
