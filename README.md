# Odin Study Skill Advisor

Odin Study Skill Advisor is a full-stack AI-assisted study and project support application. It provides authenticated users with persistent conversations, usage controls, configurable AI advisors, and Google Docs-based prompt/grounding content delivered through OpenRouter.

The current implementation supports **multiple advisor personas**. Personas are configured through a Google Sheets registry, while the actual persona instructions remain in Google Docs.

## Current Features

- User authentication and protected chat routes
- Persistent conversations stored in PostgreSQL
- OpenRouter-backed AI responses
- Google Docs-based system prompts and grounding documents
- Google Sheets-based persona registry
- Multiple selectable personas for new conversations
- Conversation-level `persona_id` persistence
- Existing conversations retain their original advisor
- Daily message and token usage controls
- Daily usage boundary based on **00:00 UTC**
- Temporary chat mode
- Conversation search, rename, delete, and export
- Light and dark themes
- Responsive frontend built with React + Vite
- FastAPI backend
- Alembic database migrations
- Mocked credential-free persona tests

## Multi-Persona Architecture

```text
User
  ↓
React / Vite frontend
  ↓
Create conversation + selected persona_id
  ↓
FastAPI backend
  ↓
Conversation.persona_id
  ↓
Google Sheets persona registry
  ↓
prompt_doc_id + grounding_doc_id
  ↓
Google Docs
  ↓
LLM context assembly
  ↓
OpenRouter
  ↓
Assistant response
```

The Google Sheet is a configuration registry only. The full persona prompt remains in Google Docs.

## Persona Registry

The configured Google Sheet uses these columns:

| Column | Purpose |
| --- | --- |
| `persona_id` | Stable internal identifier, e.g. `odin` or `persona_2` |
| `display_name` | User-facing advisor name |
| `prompt_doc_id` | Google Doc containing the persona/system prompt |
| `grounding_doc_id` | Google Doc containing grounding/reference content |
| `enabled` | Whether the persona can be selected for new chats |
| `is_default` | Whether the persona is the default selection |

Example:

| persona_id | display_name | prompt_doc_id | grounding_doc_id | enabled | is_default |
| --- | --- | --- | --- | --- | --- |
| odin | Odin | `<odin-prompt-doc-id>` | `<shared-grounding-doc-id>` | TRUE | TRUE |
| persona_2 | Hela | `<hela-prompt-doc-id>` | `<shared-grounding-doc-id>` | TRUE | FALSE |

Only non-secret configuration belongs in the Sheet. Service-account credentials and API keys must stay outside the repository.

## Conversation Behavior

The persona selector applies to **new conversations only**.

Example:

```text
Advisor for next chat: Hela
        ↓
Create new conversation
        ↓
conversation.persona_id = persona_2
        ↓
Header shows Advisor: Hela
```

Changing the new-chat selector does **not** change an existing conversation. Existing chats keep the advisor that was stored when the conversation was created.

This prevents system prompts from changing halfway through a conversation.

## Repository Structure

```text
Odin-Study-Skill-Advisor/
├── backend/
│   ├── alembic/
│   ├── tests/
│   ├── unit_tests/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── docs_service.py
│   ├── personas_service.py
│   ├── llm_service.py
│   ├── usage_service.py
│   ├── limits.py
│   ├── config_service.py
│   ├── requirements.txt
│   ├── .env.example
│   └── DEPLOYMENT.md
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── README.md
├── docs/
├── scripts/
├── PRD.md
├── PRODUCT.md
└── README.md
```

## Prerequisites

- Python supported by the backend dependency set
- PostgreSQL or Supabase PostgreSQL
- Node.js + npm
- Google Cloud project
- Google Docs API enabled
- Google Sheets API enabled
- Google service account
- OpenRouter API key

## Backend Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
python -m pip install -r requirements.txt
```

Create:

```text
backend/.env
```

from:

```text
backend/.env.example
```

Never commit the real `.env`.

### Important environment variables

```env
ENVIRONMENT=development
FRONTEND_URL=http://localhost:5173
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

DATABASE_URL=postgresql://...

OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_SITE_URL=http://localhost:5173
OPENROUTER_SITE_NAME=Advisor Console

GOOGLE_DOCS_PROMPT_ID=<legacy-odin-prompt-doc-id>
GOOGLE_DOCS_GROUNDING_ID=<legacy-grounding-doc-id>

GOOGLE_PERSONAS_SHEET_ID=<google-sheet-id>
GOOGLE_PERSONAS_SHEET_RANGE=Sheet1!A2:F
GOOGLE_PERSONAS_CACHE_TTL_SECONDS=300
GOOGLE_DOCS_CACHE_TTL_SECONDS=300

GOOGLE_SERVICE_ACCOUNT_JSON_B64=<base64-encoded-service-account-json>
```

The implementation also preserves the original Odin Google Docs settings as compatibility/fallback configuration.

## Google Setup

1. Create or select a Google Cloud project.
2. Enable:
   - Google Sheets API
   - Google Docs API
3. Create a service account.
4. Create a JSON key for local/deployment use.
5. Share the following with the service account email as Viewer:
   - Persona master Sheet
   - Odin prompt Doc
   - Hela prompt Doc
   - Grounding Doc(s)
6. Configure the Sheet ID and exact worksheet range.

For local development, Base64 credentials are recommended to avoid private-key newline parsing problems.

Example generation:

```powershell
python -c "import base64; print(base64.b64encode(open(r'C:\path\to\service-account.json','rb').read()).decode())"
```

Then place the output in:

```env
GOOGLE_SERVICE_ACCOUNT_JSON_B64=...
```

## Database Migration

The multi-persona feature adds `persona_id` to conversations.

Apply migrations:

```powershell
cd backend
alembic upgrade head
```

The multi-persona migration revision used during implementation is:

```text
fa67bc89de01
```

Existing rows receive an Odin-compatible default.

Check current migration:

```powershell
alembic current
```

## Running the Backend

```powershell
cd backend
uvicorn main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Running the Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

## Persona API

Authenticated users can request:

```http
GET /personas
```

Example response:

```json
[
  {
    "persona_id": "odin",
    "display_name": "Odin",
    "is_default": true
  },
  {
    "persona_id": "persona_2",
    "display_name": "Hela",
    "is_default": false
  }
]
```

Google Doc IDs are kept server-side and are not returned to the frontend.

### Create conversation with persona

```json
{
  "title": "New Conversation",
  "persona_id": "persona_2"
}
```

Clients that omit `persona_id` continue to use the configured default behavior.

## Daily Usage Reset

The backend defines the current quota day using:

```python
datetime.now(timezone.utc).date().isoformat()
```

Therefore the daily usage boundary is:

```text
00:00 UTC
```

In Philippine Standard Time, that corresponds to **08:00 PHT**.

The frontend currently reports the reset in UTC.

## Testing

Run backend tests:

```powershell
cd backend
pytest
```

Run frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

The feature branch previously reported:

- 32 credential-free tests passing
- Python syntax compilation passing
- Frontend lint passing
- TypeScript/production build passing
- `git diff --check` passing
- Single Alembic head at `fa67bc89de01`

Because UI-only changes were made after that validation, rerun the checks before final handoff.

### Live integration verified during development

- Database connection established using the intended database
- Alembic persona migration applied successfully
- Google service-account credentials loaded successfully
- Google Sheets API enabled
- Live `/personas` response returned both Odin and Hela
- Frontend received both personas and rendered the new-chat advisor selector

### Still recommended before production release

- Run full PostgreSQL-backed test suite in the intended deployment environment
- Verify live Odin response behavior
- Verify live Hela response behavior in a newly created Hela conversation
- Confirm reloading each conversation retains the stored advisor
- Verify production Google Docs prompt access
- Verify production OpenRouter request flow

## Security

Do not commit:

```text
.env
service-account.json
credentials.json
private keys
OpenRouter API keys
database passwords
OAuth client secrets
Resend API keys
```

Commit only safe templates such as `.env.example`.

## Development Workflow

For feature work:

```powershell
git switch feature/multi-persona
git status
```

Before review:

```powershell
git add .
git commit -m "finalize multi-persona integration"
git push
```

Use a Pull Request for review before merging to the primary branch.

## Current Multi-Persona Status

The multi-persona architecture is implemented on the feature branch and includes:

- Google Sheets persona registry
- Google Docs prompt/grounding lookup per persona
- document-ID-specific caching
- stored `persona_id` on conversations
- persona-aware quota estimation and LLM generation
- `/personas` endpoint
- new-chat persona selector
- current-conversation advisor badge
- Odin compatibility behavior
- updated database migration and tests

The remaining work is release verification rather than core implementation.
