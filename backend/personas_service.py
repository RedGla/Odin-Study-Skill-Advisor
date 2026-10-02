"""Cached Sheet persona registry; credentials are loaded only on refresh."""
import asyncio
import logging
import os
import time
from googleapiclient.discovery import build
import docs_service

SHEET_ID = os.getenv("GOOGLE_PERSONAS_SHEET_ID", "1E2qwGqS6gM2retCLoGSVtvFcSOXodKR4_RQK7EwkOEM")
SHEET_RANGE = os.getenv("GOOGLE_PERSONAS_SHEET_RANGE", "Personas!A2:F")
CACHE_TTL_SECONDS = int(os.getenv("GOOGLE_PERSONAS_CACHE_TTL_SECONDS", "300"))
_cache = None
_cache_lock = asyncio.Lock()
logger = logging.getLogger("advisor_console.personas")

class PersonasServiceError(docs_service.DocsServiceError):
    """The registry is unavailable or invalid."""

def odin_fallback():
    return dict(persona_id="odin", display_name="Odin", prompt_doc_id=docs_service.SYSTEM_PROMPT_DOCUMENT_ID,
                grounding_doc_id=docs_service.GROUNDING_DOCUMENT_ID, enabled=True, is_default=True)

def parse_rows(rows):
    """Validate rows; an empty or fully disabled registry is an intentional state."""
    personas = []
    seen = set()
    for row in rows:
        if not any(str(value).strip() for value in row):
            continue
        values = [str(value).strip() for value in row] + [""] * max(0, 6 - len(row))
        persona_id, name, prompt, grounding, enabled, default = values[:6]
        if not persona_id or persona_id in seen or not name or not prompt or not grounding:
            raise PersonasServiceError("Persona rows require unique IDs, names and both document IDs")
        if enabled.upper() not in {"TRUE", "FALSE"} or default.upper() not in {"TRUE", "FALSE"}:
            raise PersonasServiceError("Persona boolean columns must be TRUE or FALSE")
        seen.add(persona_id)
        personas.append(dict(persona_id=persona_id, display_name=name, prompt_doc_id=prompt,
                             grounding_doc_id=grounding, enabled=enabled.upper() == "TRUE",
                             is_default=default.upper() == "TRUE"))
    if sum(p["enabled"] and p["is_default"] for p in personas) > 1:
        raise PersonasServiceError("Persona registry has multiple enabled defaults")
    return personas

def _fetch_personas():
    try:
        service = build("sheets", "v4", credentials=docs_service._credentials(), cache_discovery=False)
        result = service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=SHEET_RANGE).execute()
        return parse_rows(result.get("values", []))
    except Exception as exc:
        raise PersonasServiceError("Unable to read persona registry") from exc

async def get_personas(include_disabled=False):
    """Return copies of last-good rows, or legacy Odin only on cold fetch failure."""
    global _cache
    async with _cache_lock:
        if _cache is None or time.monotonic() - _cache[0] >= CACHE_TTL_SECONDS:
            try:
                personas = await asyncio.to_thread(_fetch_personas)
                _cache = (time.monotonic(), personas)
            except (PersonasServiceError, docs_service.DocsServiceError):
                logger.warning("Persona refresh failed; using %s", "stale registry" if _cache else "Odin compatibility fallback", exc_info=True)
                personas = _cache[1] if _cache else [odin_fallback()]
        else:
            personas = _cache[1]
        return [dict(p) for p in personas if include_disabled or p["enabled"]]

async def get_persona(persona_id, include_disabled=False):
    return next((p for p in await get_personas(include_disabled) if p["persona_id"] == persona_id), None)

async def get_default_persona():
    personas = await get_personas()
    if not personas:
        raise PersonasServiceError("Persona registry has no enabled personas")
    return next((p for p in personas if p["is_default"]), personas[0])
