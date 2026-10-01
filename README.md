# Advisor Console

A web-based advisor console built with FastAPI, Vite + React, and Supabase Postgres.

## Tech Stack
* **Backend:** FastAPI, Python, SQLAlchemy 2.0, Alembic
* **Frontend:** Vite, React, TypeScript, Tailwind CSS v4, React Router
* **Database:** Supabase (PostgreSQL)
* **LLM:** OpenRouter (model routing layer — swap models via env var, no redeploy)
* **Prompt & grounding docs:** Google Docs (live-editable, zero-redeploy)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (Vite + React + TypeScript)                    │
│  AppShell · Admin · Settings · Login                    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS / REST (Axios)
┌──────────────────────▼──────────────────────────────────┐
│  FastAPI (Python)                                       │
│  ├── auth.py         — session-cookie login/logout      │
│  ├── main.py         — /conversations, /messages, /admin│
│  ├── llm_service.py  — OpenRouter completions + cost    │
│  ├── docs_service.py — Google Docs fetch + TTL cache    │
│  ├── limits.py       — daily cap + in-memory rate limit │
│  └── usage_service.py— write-through to usage_counters  │
└──────────┬─────────────────────┬───────────────────────┘
           │ SQLAlchemy 2.0      │ google-api-python-client
┌──────────▼──────────┐  ┌──────▼──────────────────────┐
│ Supabase (Postgres) │  │ Google Docs API (read-only) │
│ users, conversations│  │ System prompt + grounding   │
│ messages, usage_    │  │ documents                   │
│ counters            │  └─────────────────────────────┘
└─────────────────────┘
```

---

## How prompt & grounding editing works

The advisor's system prompt and grounding context are stored in two **Google Docs** (IDs set via env vars `GOOGLE_SYSTEM_PROMPT_DOCUMENT_ID` and `GOOGLE_GROUNDING_DOCUMENT_ID`).

* `docs_service.py` fetches each document with a **read-only** Google service account and caches the result in memory.
* The cache TTL is controlled by `GOOGLE_DOCS_CACHE_TTL_SECONDS` (default **300 s**).
* To update the prompt or grounding content: **edit the Google Doc** — no code change and no redeploy required.
* The new content is picked up automatically on the next cache expiry (within `GOOGLE_DOCS_CACHE_TTL_SECONDS` seconds).
* If the Google Docs API is unreachable, the service falls back to the last successfully cached version so conversations continue uninterrupted.

---

## Quickstart Guide

### 1. Repository Setup
```bash
git clone https://github.com/RedGla/Advisor-Console.git
cd Advisor-Console
git checkout dev
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv

# Activate Virtual Environment (Windows CMD)
.\venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:
```env
DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
```

Start the server:
```bash
uvicorn main:app --reload
```
Backend runs at: `http://localhost:8000/health`

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at: `http://localhost:5173`

---

## Project Structure
```text
Advisor-Console/
├── backend/          # FastAPI server, SQLAlchemy models, Alembic migrations
├── frontend/         # Vite + React + TypeScript application
├── eval/             # Automated evaluation scripts and results
├── docs/             # Project documentation (EVAL.md, etc.)
└── README.md
```

---

## Known Limitations

| # | Limitation | Detail |
|---|------------|--------|
| 1 | **Naive keyword grounding** | Document retrieval uses keyword/BM25-style matching — no vector embeddings. Synonyms or paraphrases may miss relevant context. |
| 2 | **In-memory rate limiter resets on restart** | The per-user rate-limit window lives in a plain Python dict inside the process. It resets on every `uvicorn --reload` or redeploy. This is an accepted trade-off per the project's Do-Not-Build list (no Redis). |
| 3 | **Single advisor persona** | There is one system prompt and one grounding document shared by all conversations. Per-user or per-session persona switching is not supported. |
| 4 | **Simple session-cookie auth** | Authentication uses server-side sessions (cookie + Argon2 password hash). Google OAuth, verified-email registration and recovery are supported. MFA is not implemented. See docs/AUTH_SETUP.md before deploying. |
| 5 | **Blocked-request logging via server logs (no in-DB events table)** | Blocked requests emit structured warnings (`request_blocked reason=... user_id=...`) to server logs rather than writing rows to a database events table. This intentional trade-off avoids DB write amplification under abusive bursts while remaining queryable via platform log sinks (e.g., Render/CloudWatch). |

Account security, Google sign-in and temporary-chat rollout: [setup guide](docs/AUTH_SETUP.md).
