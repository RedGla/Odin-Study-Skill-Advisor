# Testing Guide

## Backend

Activate the project virtual environment and run:

```powershell
cd backend
pytest
```

The multi-persona test coverage should include:

- Sheet row parsing
- enabled/disabled filtering
- default persona selection
- persona fallback behavior
- arbitrary Google Doc IDs
- document-ID-specific cache keys
- conversation `persona_id`
- `/personas`
- matching persona for quota context and generation
- Odin backward compatibility

## Frontend

```powershell
cd frontend
npm run lint
npm run build
```

## Database

```powershell
cd backend
alembic current
alembic upgrade head
```

Expected multi-persona head during this implementation:

```text
fa67bc89de01
```

## Live Persona Registry Test

```powershell
python -c "import asyncio, personas_service; print(asyncio.run(personas_service.get_personas(include_disabled=True)))"
```

Expected current registry includes Odin and Hela.

## Browser Test

1. Login.
2. Open DevTools Network.
3. Confirm `/personas` returns Odin and Hela.
4. Select Hela for the next chat.
5. Create a new conversation.
6. Confirm the header shows Advisor: Hela.
7. Create an Odin conversation.
8. Confirm the header shows Advisor: Odin.
9. Refresh.
10. Confirm each chat retains its stored advisor.

## Usage Test

`/usage/me` reports the current UTC day.

The daily reset boundary is:

```text
00:00 UTC
```

## Release Note

An earlier automated run on the feature branch reported 32 passing tests and successful frontend lint/build. Rerun all checks after the latest frontend UI modifications before submitting the final package.
