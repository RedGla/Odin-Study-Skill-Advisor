# Release Checklist

## Code
- [ ] Feature branch is clean
- [ ] Intended changes are committed
- [ ] No secrets are tracked
- [ ] Pull Request is ready for review

## Backend
- [ ] Backend tests pass
- [ ] Database connection succeeds
- [ ] `alembic current` is correct
- [ ] `alembic upgrade head` succeeds
- [ ] `/usage/me` succeeds for an authenticated user
- [ ] `/personas` returns enabled personas

## Google
- [ ] Sheets API enabled
- [ ] Docs API enabled
- [ ] Persona Sheet shared with service account
- [ ] Odin prompt shared
- [ ] Hela prompt shared
- [ ] Grounding Docs shared
- [ ] Production Sheet range is exact

## Frontend
- [ ] `npm run lint` passes
- [ ] `npm run build` passes
- [ ] Persona selector visible at 100% zoom
- [ ] Odin can be selected
- [ ] Hela can be selected
- [ ] Existing conversation does not change when selector changes
- [ ] New Hela conversation shows Advisor: Hela
- [ ] New Odin conversation shows Advisor: Odin

## End-to-End
- [ ] Odin prompt behavior verified
- [ ] Hela prompt behavior verified
- [ ] Conversation persona persists after refresh
- [ ] OpenRouter call succeeds
- [ ] Daily usage counter increments
- [ ] UTC reset wording matches backend behavior

## Handoff
- [ ] Revised PRD included
- [ ] Revised README included
- [ ] Complete code ZIP generated from committed branch
- [ ] Documentation included
- [ ] `.env` excluded
- [ ] service-account JSON excluded
