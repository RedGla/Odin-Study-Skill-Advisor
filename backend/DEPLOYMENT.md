# Deployment guide

## Local development sequence

1. Install Python dependencies with `python -m pip install -r backend/requirements.txt`
   in an activated virtual environment. Install Node dependencies with `npm ci`
   from `frontend`. See the root README for environment activation.
2. Create an empty PostgreSQL database and a backend role able to run migrations.
   Set `DATABASE_URL`; percent-encode password characters. Never use the live
   application database for tests.
3. Copy `backend/.env.example` to `backend/.env` and replace placeholders. Use
   `ENVIRONMENT=development`, `FRONTEND_URL=http://localhost:5173`,
   `COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax`. Configure the OpenRouter key/model.
   Google credentials are loaded on fetch, not import; missing credentials still
   prevent live Docs generation. DATABASE_URL is required at backend import.
4. Enable the **Google Docs API** in the service-account project.
5. Enable the **Google Sheets API** in the same project.
6. Create/configure a service account and set either `GOOGLE_SERVICE_ACCOUNT_JSON`
   (raw JSON) or `GOOGLE_SERVICE_ACCOUNT_JSON_B64` (base64 JSON) in private config.
   Base64 takes precedence if both are set. GOOGLE_APPLICATION_CREDENTIALS file
   loading is not implemented. The backend requests Docs and Sheets readonly scopes.
7. Share the master persona Sheet with that service-account email as Viewer.
8. Share every prompt and grounding Doc referenced by its rows as Viewer. Grounding
   Docs can be shared by personas. Preserve the original Odin fallback Doc variables.
9. Set `GOOGLE_PERSONAS_SHEET_ID` to your registry (omit to use the built-in project
   master ID), `GOOGLE_PERSONAS_SHEET_RANGE=Personas!A2:F` or `Sheet1!A2:F`, and
   optional `GOOGLE_PERSONAS_CACHE_TTL_SECONDS=300`. Populate the six columns as
   described in the [README](../README.md#persona-configuration-and-conversation-behavior).
10. From `backend`, run `python -m alembic upgrade head` **before starting the new backend**.
11. Start locally with `python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000`
    from `backend`, or use `python backend/run.py` from the root.
12. Copy `frontend/.env.example` to `frontend/.env.local`, set
    `VITE_API_URL=http://localhost:8000`, then run `npm run dev` from `frontend`.
    `npm run build` produces `dist`; `npm run preview` previews it locally.
13. Sign in as a regular user and verify `GET /personas` using the browser's
    authenticated session. Expected fields are persona_id, display_name, is_default;
    there must be no Doc IDs. Admin accounts cannot access chat routes.
14. Select Odin and create a saved conversation. Confirm the response stores `odin`.
15. Select Hela/your second enabled persona and create a second conversation.
16. Confirm each prompt is used, with relevant shared or separate grounding.
17. Change the new-chat selector, reopen the first chat, and confirm it retains its
    stored persona. Check Doc edits after cache expiry. These are live acceptance
    steps, not guarantees established by mocked tests.

## Production: Render backend and Vercel frontend

Use the same dependency, Google sharing and migration sequence with production
secret configuration. Verify the intended repository, branch and service before
deploying. Backend root is `backend`; build with `pip install -r requirements.txt`,
run `python -m alembic upgrade head` as a release step, and start with
`uvicorn main:app --host 0.0.0.0 --port $PORT` on Render's Linux runtime.

| Backend variable | Production value |
| --- | --- |
| ENVIRONMENT | production |
| DATABASE_URL | Private target PostgreSQL URL |
| FRONTEND_URL | Exact HTTPS frontend origin, without a path |
| COOKIE_SECURE | true |
| COOKIE_SAMESITE | none for separate Vercel/Render sites; lax for same-site hosting |

Configure the OpenRouter, Google credentials, registry and fallback Doc variables
from the shared backend template. Keep secrets in deployment settings. In Vercel,
use root `frontend`, build `npm run build`, output `dist`, and set public
`VITE_API_URL` to the HTTPS backend URL before building. Redeploy after changing it.
The committed `vercel.json` supplies SPA routing. `/health` tests liveness only.

Cross-site cookies also depend on browser policy; SameSite=none does not override
third-party cookie blocking. Prefer same-site custom domains where needed. Keep
CORS/origin checks enabled. Test login, session persistence and allowed-origin
mutations on the actual deployment. Check request URLs and cookies in DevTools.

Google OAuth uses a separate Web client with the exact `/auth/google/callback`
redirect URI. SMTP is the only implemented recovery/verification mail transport;
Resend variables have no effect. Registration/login do not require email delivery.
See [authentication setup](../docs/AUTH_SETUP.md) for these optional integrations.

## Persona migration and rollback

Revision `fa67bc89de01` follows `ef56ab78cd90`. It adds
`conversations.persona_id VARCHAR NOT NULL DEFAULT 'odin'`. Existing rows receive
Odin; IDs, titles, messages and ownership are preserved. This is additive, but
PostgreSQL schema changes can acquire table locks, so schedule deployment normally.
Earlier migrations also include auth and Supabase privilege hardening; inspect the
current revision and resolve migration errors rather than stamping over them.

To roll back just this migration, coordinate an application rollback and run
`python -m alembic downgrade ef56ab78cd90` from `backend`. The downgrade drops the
persona column and loses stored persona selections. Back up first; the new backend
requires the column and must not run against the downgraded schema.

## Failure behavior and validation

- Sheet fetch/validation failure: log and use last-good cached rows, or legacy Odin
  on a cold cache. Non-Odin chats without resolvable registry data return 503.
- Empty/all-disabled valid Sheet: return no selectable personas; default creation
  returns 503, explicit unknown/disabled IDs return 400. Existing disabled rows
  remain usable by saved chats. Missing enabled default uses the first enabled row.
- Docs fetch failure: use that document's stale cache; without it, message generation
  returns 502 and does not call OpenRouter. Caches are per process and lost on restart.
- Stored persona_id is immutable through the chat API; Docs/row configuration may
  change after refresh. No private Doc IDs are exposed by persona discovery.

Run `python -m pytest backend/unit_tests eval -q` for service/evaluator checks without
PostgreSQL. Run the full suite with disposable PostgreSQL as described in
[TESTING](../docs/TESTING.md), plus frontend lint/build. Live Google Sheets, Docs,
OpenRouter, OAuth/mail and target database checks require configured environments.
