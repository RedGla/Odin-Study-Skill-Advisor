# Product Overview
## Odin Study Skill Advisor

Odin Study Skill Advisor is a configurable AI support workspace for study, project work, and guided problem solving.

The product combines persistent conversations, project-aware guidance, usage controls, and multiple specialized advisors in one interface.

## Current Product Direction

The system originally relied on one global Odin system prompt. The current implementation expands that model to support multiple advisor personas without removing the original Odin workflow.

The core design is:

- Google Sheets for persona configuration
- Google Docs for persona prompts and grounding
- PostgreSQL for persistent conversations and advisor assignment
- FastAPI for backend orchestration
- React for the user interface
- OpenRouter for model access

## Current Advisor Experience

Users choose an advisor for the **next new conversation**.

The selected advisor becomes part of the conversation record and remains attached to that chat.

This means:

```text
Select Hela
→ create chat
→ Hela chat remains Hela
```

Changing the selector later does not alter the existing chat.

## Why This Matters

This approach supports specialization while protecting conversation consistency.

It also lets administrators introduce new advisors through the master Sheet and Google Docs without hardcoding each persona into the application.

## Current Personas

The current registry includes:

- Odin
- Hela

The architecture is designed to support additional enabled personas using the same schema.

## Product Principles

- Preserve conversation consistency.
- Keep configuration separate from application code.
- Keep sensitive credentials server-side.
- Make the default experience work for legacy clients.
- Avoid exposing prompt document IDs to the frontend.
- Make advisor selection understandable at normal browser zoom.
- Treat Google Docs as editable content sources, not code.

## Current Release State

The multi-persona registry and frontend discovery flow are working locally.

The live Google Sheet has returned both Odin and Hela through the authenticated `/personas` endpoint.

Database migration and service-account configuration have also been exercised locally.

Final production release should still include end-to-end prompt-response verification for both advisors.
