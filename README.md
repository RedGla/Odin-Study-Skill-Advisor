# Odin — Advisor Console

Project 1 submission, revised October 2, 2026. Odin is an authenticated AI advisor workspace for study and project support, with saved and temporary conversations, Google Docs grounding, usage limits, account settings and an administrator dashboard. Google OAuth sign-in and account linking were added in response to feedback.

Read [PRD.md](PRD.md), [the timeline](docs/TIMELINE.md) and [submission verification](docs/FINAL_VERIFICATION.md). All three and this README are included in the submission ZIP.

## Architecture and dependencies

React browser → FastAPI REST API → PostgreSQL. The backend calls OpenRouter for completions and reads the persona and reference context through the Google Docs API. Credentials and document retrieval stay on the server; Axios sends session cookies for API requests.

Use Python 3.12, Node.js 24 with npm, and PostgreSQL 16. Docker is optional for the isolated test database. The frontend uses React 19, TypeScript, Vite 8, Tailwind 4, React Router, Axios and react-markdown. Backend dependencies include FastAPI, SQLAlchemy, Alembic, psycopg2, Argon2, httpx and Google's API/auth libraries. Exact declared versions are in `backend/requirements.txt` and `frontend/package.json`; npm versions are locked in `frontend/package-lock.json`. Python transitive dependencies are not fully locked.

## Get the project

Extract the submission ZIP and open its `Advisor-Console` directory, or clone:

```sh
git clone --branch dev https://github.com/RedGla/Eskwelabs-Advisor-Console.git
cd Eskwelabs-Advisor-Console
```

The ZIP contains current working files. After committing, rebuild it to record the submission commit and clean working state. `SUBMISSION_MANIFEST.json` inside it records the base commit, dirty state, packaging time and file hashes. It does not imply every file has been pushed to GitHub.

## Backend setup

From the project root:

```sh
python -m venv .venv
```

Activate with `.\.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on macOS/Linux. Then:

```sh
python -m pip install -r backend/requirements.txt
```

Copy `backend/.env.example` to `backend/.env` (`Copy-Item backend/.env.example backend/.env` in PowerShell or `cp backend/.env.example backend/.env` on macOS/Linux). Configure your own development values:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL; percent-encode password characters |
| `ENVIRONMENT` | `development` locally |
| `FRONTEND_URL` | `http://localhost:5173` locally; exact allowed frontend origin |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | `false`, `lax` for local HTTP; secure cookies for HTTPS deployment |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Server-only provider key and model |
| `GOOGLE_SYSTEM_PROMPT_DOCUMENT_ID` | Your system-prompt Google Doc ID |
| `GOOGLE_GROUNDING_DOCUMENT_ID` | Your reference Google Doc ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service-account JSON with read access to both Docs |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Alternative base64 credentials; configure one credential format |
| `GOOGLE_DOCS_CACHE_TTL_SECONDS` | Cache lifetime, default 300 seconds |

Legacy aliases `GOOGLE_DOCS_PROMPT_ID` and `GOOGLE_DOCS_GROUNDING_ID` also work. Enable Google Docs API for your service-account project and share both documents with its email as a reader. Private document text and credentials are not distributed. Editing these Docs updates context after cache expiry; an outage uses a previous cached copy when available.

Create an empty development database with your PostgreSQL administration tool, configure its URL, then migrate and start:

```sh
cd backend
python -m alembic upgrade head
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Use an account permitted to create/alter the schema. Migrations include privilege hardening; consult [deployment notes](backend/DEPLOYMENT.md) before migrating an existing hosted database. `http://localhost:8000/health` checks API liveness, not database/provider readiness. Interactive API docs are at `http://localhost:8000/docs`.

## Frontend setup and execution

In a second terminal, from the project root:

```sh
cd frontend
npm ci
```

Copy `.env.example` to `.env.local`, set `VITE_API_URL=http://localhost:8000`, then run:

```sh
npm run dev
```

Open `http://localhost:5173`. Register with a real email address and a 15–128 character password, then sign in. Registration/login do not require email delivery or verification in this revision. Start a saved conversation, send follow-up messages and reopen it from the sidebar. Temporary chat does not store message content, but usage and operational metadata remain. Account controls are in Settings. The admin dashboard requires a role assigned by a trusted database administrator; public registration cannot grant admin access.

For a production frontend bundle and local preview:

```sh
npm run build
npm run preview
```

Set the deployed API URL before building. Vite variables are public; never put secrets in them.

## Google OAuth and email

Google sign-in and explicit account linking implement the requested feedback. Configure `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` and `GOOGLE_OAUTH_REDIRECT_URI` only on the backend. Register the exact callback URL with the Google OAuth Web client (`http://localhost:8000/auth/google/callback` locally). Existing password users link Google from Settings; matching email alone does not link accounts or grant an administrator role. See [AUTH_SETUP.md](docs/AUTH_SETUP.md).

Current source uses SMTP for account verification/recovery: configure `SMTP_HOST`, `SMTP_FROM`, optional `SMTP_USERNAME`/`SMTP_PASSWORD`, and `SMTP_PORT` (587 by default). Existing Resend template/documentation entries describe proposed configuration; the current `auth_security.py` does not implement that transport. Real OAuth consent and inbox delivery require deployment testing.

## Repository structure

```text
backend/                  API, authentication, model/Docs services, quotas
  alembic/                Database migrations
  tests/                  API, security, failure and concurrency tests
frontend/                 React app, build configuration and npm lockfile
  src/App.tsx             Chat workspace
  src/pages/              Login, Settings and Admin
  public/                 Fonts, font license, icons and favicon
  src/assets/             Images

eval/                     Prompt dataset, evaluator, harness tests and live results
docs/                     Setup, design decisions, timeline and verification
scripts/                  Submission packaging script
.github/workflows/ci.yml   Backend, frontend lint/build checks
.impeccable/               Design configuration and visual review artifacts
PRD.md                    Revised requirements and acceptance criteria
README.md                 Setup and execution guide
```

## Tests and evaluation

Follow [TESTING.md](docs/TESTING.md) to start disposable local PostgreSQL. With the Python environment active, from the root:

```sh
python -m pytest -q -p no:cacheprovider
python -m pytest eval/test_eval_harness.py -q -p no:cacheprovider
python eval/run_eval.py --dry-run
```

Run `npm run lint` and `npm run build` from `frontend/`. The test database must be local with both username and database named `advisor_test`; its tables are reset. Never use the application database. Tests mock model/Docs calls. The October 2 submission run passed all 128 tests (including 15 evaluator tests and all three database-outage tests), plus frontend lint/build. See [verification](docs/FINAL_VERIFICATION.md) for evidence.

[eval/prompts.json](eval/prompts.json) is the included dataset. [eval/results.md](eval/results.md) preserves the earlier live run, including failures and review requirements. Dry runs validate structure only. For live evaluation, configure a dedicated account and follow [EVAL.md](docs/EVAL.md). Live model acceptance is not established by mocked regression tests.

## Failure behavior and limitations

- Covered database failures return 503 with a friendly retry message. A failure after model completion may leave an uncertain reservation/pending turn; the API does not claim the result was saved.
- Provider failures return 502. Docs failure without cached context returns 503; previously cached Docs can be used during an outage.
- Grounding uses keyword matching, not embeddings. Factual accuracy and extraction resistance need source comparison and human review.
- Chat rate limiting is per process and resets on restart; daily quotas are persisted. Distributed rate coordination and MFA are outside scope.
- Model history is bounded, while stored history remains available. All users share one persona and grounding document. Costs are estimates using configured rates.
- Database outage can prevent durable telemetry writes. Historical tests are not proof of the current deployment's OAuth, email, browser secrecy, live Docs refresh or recovery behavior.

## Submission packaging

Run `python scripts/package_submission.py` from the root. It creates the ZIP and checksum in `submission/`, includes source, migrations, scripts, tests, dataset, documentation and assets, and validates all included hashes. Submit the ZIP plus `PRD.md` and `README.md`; both documents also appear inside the ZIP.

Private environment files, keys, production data, `.git`, virtual environments, `node_modules`, caches and generated builds are excluded. Recreate dependencies using the setup instructions. The manifest records precisely what was included.
