# Product Requirements Document
## Odin Study Skill Advisor

**Document status:** Revised for multi-persona implementation  
**Current implementation branch:** `feature/multi-persona`

## 1. Product Summary

Odin Study Skill Advisor is an AI-assisted study and project support application that helps users plan work, resolve blockers, study more effectively, and maintain persistent conversations with configurable AI advisors.

The revised product supports multiple advisor personas. A Google Sheet acts as the persona registry, while Google Docs store each advisor's prompt and grounding content.

## 2. Product Goals

The product should:

- Provide authenticated, persistent AI-assisted conversations.
- Support multiple advisor personas without duplicating backend architecture.
- Allow non-developers or authorized operators to add or disable advisors through configuration rather than code changes.
- Preserve the original Odin advisor behavior.
- Prevent an existing conversation from silently changing advisors.
- Keep prompt content editable in Google Docs.
- Keep persona configuration readable from one Google Sheets master file.
- Maintain usage controls, observability, authentication, and deployment safety.

## 3. User Problem

A single global advisor prompt limits the product to one interaction style and makes specialization difficult. Adding new advisors directly in code would require repeated deployments and increase maintenance overhead.

Users need specialized advisors while project administrators need a low-friction way to configure those advisors.

## 4. Revised Solution

Use:

```text
Google Sheet = persona registry
Google Docs = persona instructions and grounding
PostgreSQL = persistent conversation/persona assignment
FastAPI = persona resolution and LLM orchestration
React = new-chat advisor selection
OpenRouter = model provider
```

## 5. Personas

Each persona is configured using:

| Field | Requirement |
| --- | --- |
| `persona_id` | Required stable unique identifier |
| `display_name` | Required user-facing name |
| `prompt_doc_id` | Required Google Doc prompt |
| `grounding_doc_id` | Required Google Doc grounding source |
| `enabled` | Controls availability for new chats |
| `is_default` | Marks the preferred default advisor |

Current configured examples:

- Odin
- Hela (`persona_2`)

Both personas may share the same grounding document while using different prompt documents.

## 6. Functional Requirements

### FR-1: Persona registry loading

The backend shall load persona configuration from the configured Google Sheet.

The Sheet ID and range shall be configurable by environment variables.

### FR-2: Persona caching

The backend shall cache the persona registry for a configurable TTL, defaulting to approximately 300 seconds.

### FR-3: Document loading

The Google Docs service shall support loading arbitrary document IDs.

Prompt/document cache keys must include the document ID so that one persona cannot receive another persona's cached prompt.

### FR-4: Conversation persona persistence

Each persistent conversation shall store a `persona_id`.

Existing/legacy conversations shall receive an Odin-compatible default through the migration.

### FR-5: New conversation advisor selection

The frontend shall allow the user to select an enabled advisor before creating a new persistent conversation.

### FR-6: Existing conversation stability

Changing the new-chat advisor selector shall not change the persona of an existing conversation.

### FR-7: Active advisor display

The frontend shall display the current conversation's stored advisor in the chat header.

### FR-8: Persona endpoint

The backend shall expose an authenticated endpoint:

```http
GET /personas
```

The endpoint shall return only frontend-safe fields.

Example:

```json
[
  {
    "persona_id": "odin",
    "display_name": "Odin",
    "is_default": true
  }
]
```

Google Doc IDs must remain server-side.

### FR-9: Persona-aware LLM generation

The conversation's persona must be used for:

- system prompt selection
- grounding document selection
- quota/token estimation context
- actual LLM generation

The system must not estimate with one persona and generate with another.

### FR-10: Backward compatibility

The application shall preserve the existing Odin Docs integration as compatibility/fallback behavior where defined by the implementation.

Existing clients that do not send a persona ID should continue to work through the default-persona path.

### FR-11: Disabled personas

Disabled personas shall not be selectable for new conversations.

Existing conversations must not be silently reassigned to a different advisor.

### FR-12: Daily usage controls

The product shall preserve daily message/token quota behavior.

The quota day is based on UTC date boundaries:

```text
00:00 UTC
```

## 7. Non-Functional Requirements

### Security

- No private service-account keys in source control.
- No API keys in tracked files.
- Prompt/grounding document IDs remain backend configuration.
- Frontend receives only safe persona metadata.
- Auth-protected persona and chat routes remain protected.

### Reliability

- Persona registry failures must not corrupt stored conversations.
- Document caching must be isolated per document ID.
- Database migration must preserve legacy conversation data.

### Maintainability

- Persona registry logic is isolated in `personas_service.py`.
- Google document loading remains centralized in `docs_service.py`.
- LLM orchestration remains centralized in `llm_service.py`.
- Persona addition should not require code changes when the schema remains unchanged.

### Performance

- Persona registry is cached.
- Google Docs remain cached.
- Only necessary persona metadata is returned to the frontend.

## 8. UX Requirements

The sidebar shall expose a clear advisor selector for new chats.

Recommended wording:

```text
Advisor for next chat
[ Hela ▼ ]
```

Supporting copy should explain:

```text
Existing chats keep their original advisor.
```

The active conversation header shall show:

```text
Advisor: Odin
```

or:

```text
Advisor: Hela
```

The sidebar must remain usable at 100% browser zoom on common laptop displays.

Only the conversation-list section should need vertical scrolling under normal desktop conditions.

## 9. Technical Architecture

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL / Supabase PostgreSQL
- Alembic
- Google Docs API
- Google Sheets API
- OpenRouter
- Google service-account authentication

### Frontend

- React
- TypeScript
- Vite
- authenticated API client
- responsive advisor/chat interface

## 10. Database Changes

Conversation model includes:

```text
persona_id VARCHAR NOT NULL DEFAULT 'odin'
```

Migration revision used during implementation:

```text
fa67bc89de01
```

Migration command:

```powershell
alembic upgrade head
```

## 11. Environment Configuration

Required persona configuration:

```env
GOOGLE_PERSONAS_SHEET_ID=<sheet-id>
GOOGLE_PERSONAS_SHEET_RANGE=Sheet1!A2:F
GOOGLE_PERSONAS_CACHE_TTL_SECONDS=300
GOOGLE_DOCS_CACHE_TTL_SECONDS=300
```

Service-account credentials may be supplied using the credential mechanism supported by the backend, with Base64 recommended for deployment/local robustness.

## 12. Acceptance Criteria

The multi-persona feature is accepted when:

1. `/personas` returns all enabled persona choices.
2. Odin appears as an available advisor.
3. Hela appears as an available advisor.
4. Selecting Hela and creating a new chat stores `persona_2`.
5. A Hela chat loads the Hela prompt Doc.
6. An Odin chat loads the Odin prompt Doc.
7. Both can use their configured grounding Doc.
8. Refreshing/reopening a conversation retains its stored advisor.
9. Changing the new-chat selector does not change an existing chat.
10. Invalid persona IDs fail safely.
11. Disabled personas do not appear for new chats.
12. Google Docs cache entries do not mix persona prompts.
13. Database migration succeeds against the intended database.
14. Daily quota behavior remains unchanged.
15. Frontend works at normal browser zoom without hiding core sidebar controls.

## 13. Validation Status

Verified during current development:

- expected database connection works
- Alembic multi-persona migration applied
- Google service-account credentials parse and authenticate
- Google Sheets API enabled and reachable
- live Sheet registry returns Odin and Hela
- frontend receives both personas
- advisor selector renders in the sidebar

Earlier automated branch validation reported:

- 32 tests passed
- Python syntax compilation passed
- frontend lint passed
- TypeScript/production build passed
- `git diff --check` passed
- one Alembic head

Because subsequent UI-only work was performed, final release validation should rerun these commands.

## 14. Remaining Release Verification

Before production release:

- rerun backend tests
- rerun frontend lint/build
- run PostgreSQL-backed suite
- create a new Odin conversation and verify live prompt behavior
- create a new Hela conversation and verify live prompt behavior
- reload both chats and verify persona persistence
- verify production Google Docs access
- verify production OpenRouter behavior
- verify production environment variables and secrets

## 15. Out of Scope for This Revision

- Switching personas inside an existing conversation
- Editing persona rows through the application UI
- Persona-specific model selection
- Persona-specific usage caps
- Dynamic user-created personas
- Replacing Google Docs as the prompt source

These can be evaluated in future iterations.
