# Backend Deployment Guide

## 1. Prerequisites

- PostgreSQL or Supabase PostgreSQL
- Python environment compatible with project dependencies
- Google Cloud project
- Google Docs API enabled
- Google Sheets API enabled
- Google service account
- OpenRouter API key
- frontend deployment URL

## 2. Environment

Create a deployment environment using the variables documented in `.env.example`.

Do not commit production secrets.

Important persona values:

```env
GOOGLE_PERSONAS_SHEET_ID=<sheet-id>
GOOGLE_PERSONAS_SHEET_RANGE=Sheet1!A2:F
GOOGLE_PERSONAS_CACHE_TTL_SECONDS=300
GOOGLE_DOCS_CACHE_TTL_SECONDS=300
```

Use the exact worksheet name in the range.

## 3. Google Cloud

Enable:

- Google Sheets API
- Google Docs API

Create a service account and share:

- persona master Sheet
- Odin prompt Doc
- Hela prompt Doc
- grounding Docs

with its `client_email`.

## 4. Credentials

For deployment platforms, Base64-encoded service-account JSON is recommended:

```env
GOOGLE_SERVICE_ACCOUNT_JSON_B64=<base64-json>
```

Never commit the downloaded service-account JSON.

## 5. Database

Configure:

```env
DATABASE_URL=postgresql://...
```

Apply migrations before starting the new release:

```powershell
alembic upgrade head
```

Current multi-persona revision:

```text
fa67bc89de01
```

Rollback should follow the project's normal Alembic downgrade procedure after confirming the correct previous revision.

## 6. Backend Start

Typical local command:

```powershell
uvicorn main:app --reload
```

Production process settings should follow the hosting provider's recommended ASGI configuration.

## 7. Frontend

Configure the frontend to call the deployed backend and ensure the deployed frontend origin is included in backend CORS configuration.

For local development:

```text
FRONTEND_URL=http://localhost:5173
```

## 8. Post-Deploy Verification

Verify:

1. authentication
2. `/usage/me`
3. `/personas`
4. Odin appears
5. Hela appears
6. new Odin conversation
7. new Hela conversation
8. stored persona survives refresh
9. prompt loading works for both advisors
10. OpenRouter responses succeed
11. usage limits still operate on UTC day boundaries

## 9. Common Persona Setup Failures

### `/personas` returns only Odin

Possible causes:

- service-account credential failure
- Sheets API disabled
- wrong environment-variable names
- wrong worksheet/range
- Sheet not shared with service account

### `Unable to parse range`

Check the actual worksheet name.

Example:

```env
GOOGLE_PERSONAS_SHEET_RANGE=Sheet1!A2:F
```

### `SERVICE_DISABLED`

Enable Google Sheets API in the same Google Cloud project that owns the service account.

## 10. Security Checklist

- `.env` excluded from Git
- service-account JSON excluded
- OpenRouter key stored only in secrets
- database credentials stored only in secrets
- Google OAuth client secret stored only in secrets
- Resend key stored only in secrets
