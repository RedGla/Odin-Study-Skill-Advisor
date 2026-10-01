# Odin interface refresh — 2026-09-23

## Design direction

Warm red accents, cream surfaces, dark ink, an editorial welcome heading,
and consistent navigation across chat, sign-in, registration, settings, and admin.
The document title is `Odin - Study Skills Advisor`; the favicon uses the same red mark.

Research references (inspiration only; no repository code or assets copied):
- [Twenty](https://github.com/twentyhq/twenty): compact workspace navigation and clear information hierarchy; GitHub showed 57.3k stars during research.
- [Dub](https://github.com/dubinc/dub): restrained dashboard styling and grouped navigation.

## Functional additions

- Daily message progress, remaining allowance, and UTC reset explanation.
- Authenticated `GET /usage/me` returns only the signed-in user's current daily counter and message cap.
- Four EIF/study starter questions, also accessible through the Ideas control.
- Conversation search, response copying, and Markdown conversation export.
- Mobile navigation drawer with accessible conversation and usage controls.
- Themed rename dialog replaces browser prompts and supports keyboard entry.
- Consistent light/dark styling, associated form labels, and reduced-motion support.
- Conversation selection ignores stale responses; chat initialization no longer repeatedly creates/fetches conversations.

## Verification

- Frontend production build and TypeScript: PASS.
- Frontend ESLint: PASS.
- `backend/tests/test_my_usage.py`: 3 passed using disposable PostgreSQL on localhost.
  Covers authentication, zero usage for a new account, and isolation between users.
- Local browser: sign-in, chat, settings, admin, dark theme, 390px phone drawer,
  daily progress (synthetic fixture: 12/50), conversation search, and response copy observed.
- Local rename dialog saved `Rename test` as `Weekly study plan` and updated navigation.
- Markdown export implementation builds, but the in-app browser did not expose a download event;
  download behavior still requires a regular-browser check.

Local synthetic data is UI test evidence only. It does not replace authenticated
production verification or mark Phase 5 complete.
