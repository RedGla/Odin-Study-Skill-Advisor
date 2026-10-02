"""
OpenRouter integration for the Advisor Console.

Handles the real (non-stub) LLM call: takes a list of chat messages and
returns the model's reply plus token usage, so the caller can persist
cost/telemetry data.

The public ``generate_llm_response`` function adds the cached Google Docs
persona and grounding context before making the OpenRouter request.
"""

import os
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter uses these two headers for its public leaderboard attribution.
# Not secrets — safe to have sensible defaults.
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Advisor Console")

# Cost estimation — configurable per PRD §8 (est_cost on every persisted message).
# These are $ per 1,000,000 tokens (the standard provider convention — check
# https://openrouter.ai/models for your actual model's real current pricing)
# for whatever OPENROUTER_MODEL is currently set. Defaults below are placeholders.
PROMPT_COST_PER_1M = float(os.getenv("OPENROUTER_PROMPT_COST_PER_1M", "0.15"))
COMPLETION_COST_PER_1M = float(os.getenv("OPENROUTER_COMPLETION_COST_PER_1M", "0.60"))
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", "1024"))


def conservative_token_estimate(messages: list[dict]) -> int:
    """Upper-bound prompt tokens without depending on provider tokenization."""
    return max(1, sum(len(str(m.get("content", "")).encode("utf-8")) + 32 for m in messages) + 16)


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Rough $ cost estimate for one call, given token counts and the
    configured per-1M rates. Not exact billing — an estimate, as the name says."""
    return (
        (prompt_tokens / 1_000_000.0) * PROMPT_COST_PER_1M
        + (completion_tokens / 1_000_000.0) * COMPLETION_COST_PER_1M
    )

REQUEST_TIMEOUT_SECONDS = 30.0


def _grounding_chunks(document: str, max_words: int = 400) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document) if part.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        for start in range(0, len(words), max_words):
            chunks.append(" ".join(words[start:start + max_words]))
    return chunks


def _select_grounding(document: str, query: str, limit: int = 2) -> str:
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for chunk in _grounding_chunks(document):
        chunk_terms = set(re.findall(r"[a-z0-9]+", chunk.lower()))
        scored.append((len(query_terms & chunk_terms), chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for score, chunk in scored[:limit] if score > 0]
    return "\n\n".join(selected)


class LLMError(Exception):
    """Raised whenever the OpenRouter call fails, times out, or returns
    something we don't know how to parse. Callers should catch this and
    show the user a plain-language error instead of a raw stack trace."""
    pass


async def get_chat_completion(messages: list[dict], max_completion_tokens: int | None = None) -> dict:
    """
    Send a chat history to OpenRouter and return the reply.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": str},
                  in chronological order.

    Returns:
        {"content": str, "prompt_tokens": int, "completion_tokens": int}

    Raises:
        LLMError on any failure (missing key, timeout, non-2xx, bad shape).
    """
    if not OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_SITE_NAME,
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }
    if max_completion_tokens is not None:
        payload["max_tokens"] = max_completion_tokens

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(OPENROUTER_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMError("OpenRouter request timed out") from e
    except httpx.HTTPStatusError as e:
        raise LLMError(f"OpenRouter returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMError(f"OpenRouter request failed: {e}") from e

    try:
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected OpenRouter response shape: {data}") from e

    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


async def generate_llm_response(messages: list[dict], max_completion_tokens: int | None = None, *, persona=None, advisor_context=None) -> dict:
    """Generate a response using the configured persona and grounding docs.

    ``persona`` selects registry Docs; omitting it preserves legacy Odin.
    ``advisor_context`` reuses the exact context used for quota estimation.
    Returns the same dict as ``get_chat_completion`` plus two timing keys:
    ``docs_fetch_ms`` and ``llm_call_ms`` (wall-clock milliseconds).
    """
    import time as _time
    from docs_service import get_advisor_context

    t0 = _time.monotonic()
    context = advisor_context if advisor_context is not None else await get_advisor_context(persona)
    docs_fetch_ms = round((_time.monotonic() - t0) * 1000, 1)

    query = messages[-1]["content"] if messages else ""
    grounding = _select_grounding(context["grounding_document"], query)
    system_content = f"{context['system_prompt']}\n\n"
    if grounding:
        system_content += f"Relevant grounding context:\n{grounding}"

    t1 = _time.monotonic()
    result = await get_chat_completion(
        [{"role": "system", "content": system_content}, *messages],
        max_completion_tokens=max_completion_tokens,
    )
    llm_call_ms = round((_time.monotonic() - t1) * 1000, 1)

    result["docs_fetch_ms"] = docs_fetch_ms
    result["llm_call_ms"] = llm_call_ms
    return result
