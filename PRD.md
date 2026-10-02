# Odin — Revised Product Requirements Document

Version: Project 1 final submission revision, October 2, 2026 (Asia/Manila).
Repository: `RedGla/Eskwelabs-Advisor-Console`, branch `dev`.
Deadline: Friday, October 2, 2026, 5:00 PM, interpreted in the user's Asia/Manila timezone.

## 1. Purpose and revision basis

Deliver an authenticated AI advisor workspace for study goals, project milestones and blockers, with administrator control over access and usage. This revision consolidates the implemented specifications in source, `PRODUCT.md`, existing verification/evaluation documentation, and the submission email.

**Feedback incorporated: Google OAuth was added.** Users can sign in with Google, and existing password users can explicitly link their Google identity from Settings. Google OAuth configuration is server-side; provider identity does not grant administrator privileges. The implementation is in `backend/google_oauth.py`, authentication routes in `backend/main.py`, and the Login/Settings UI. Automated coverage is in `backend/tests/test_account_security.py`; live consent/callback configuration remains deployment-specific.

Other consolidated changes include the Odin workspace design, saved and temporary chat, account settings, sessions, quotas, operational telemetry and clearer evaluation evidence. Registration/login no longer require email verification. No separate original PRD, instructor feedback file or original timeline was available in the checkout; this document does not claim to incorporate unseen feedback.

## 2. Users and workflows

- Signed-in users ask questions, continue/reopen saved conversations, choose temporary chat, manage their account and inspect usage.
- Administrators review usage, conversations and events, manage account access and sessions, configure limits and enable/disable registration or chat.
- Operators maintain server-side persona/reference Docs and configure database, model, Google OAuth and account email delivery.

## 3. Scope

Included: responsive web frontend, REST backend, PostgreSQL persistence and migrations, server-side Google Docs context, OpenRouter completions, authentication/authorization, quotas/rate limits, administrator tools, automated tests, evaluation dataset/scripts/results and setup documentation.

Excluded: native apps, vector search, per-user personas, billing, distributed chat throttling/Redis, MFA and production data exports. Model factual correctness is evaluated rather than guaranteed. Live deployment checks remain distinct from source-level regression tests.

## 4. Functional requirements

| ID | Final specification | Acceptance coverage |
| --- | --- | --- |
| FR-01 | Authenticated multi-turn advisor chat with clear completion/error responses. | Provider-failure and long-history tests; browser two-turn check |
| FR-02 | Server-only system/grounding Docs retrieval with TTL and stale-cache fallback. | Docs failure/cache tests; live edit within TTL |
| FR-03 | Keyword grounding; do not return raw internal prompt/grounding payloads through serializers. | Grounding tests; factual/extraction review and browser network inspection |
| FR-04 | Persist, list, rename, delete and reopen owned conversations; deny cross-user access. | Ownership/history tests; browser logout/login/reopen |
| FR-05 | Transactional daily message/token quotas with reservations and reconciliation. | Cap-race, reset-boundary, quota, token-budget and migration tests |
| FR-06 | Per-user, per-process rate limiting with HTTP 429 feedback. | Rate-race and quota-correctness tests |
| FR-07 | Turn status, tokens, estimated cost and operational events without secret prompt logging. | Telemetry, admin-events and failure tests |
| FR-08 | Admin-only usage, conversation, event, account, session and configuration controls. | Admin-console, admin-events and authorization tests |
| FR-09 | Repeatable quality/enforcement evaluation suites and auditable prompt dataset/results. | Evaluator harness tests, structural dry run and separate live evidence |
| FR-10 | Hashed passwords, expiring server sessions, logout, password changes/recovery and optional email verification. | Auth-session, account-security and CSRF-origin tests; live mail delivery |
| FR-11 | Google OAuth sign-in and explicit account linking, added in response to feedback. | Account-security tests; live Google consent/callback check |
| FR-12 | Temporary chat does not persist message content, while usage and content-free operational metadata remain. | Account-security tests and browser flow review |

## 5. Non-functional requirements

- Security: server-only secrets, HttpOnly session cookies, production cookie/origin configuration, ownership enforcement, least-privilege database access and no self-assigned admin role.
- Reliability: covered database operational failures return 503, provider failures return 502, and missing uncached context returns 503. Unsaved results are not presented as persisted. Uncertain provider spend retains reservations conservatively.
- Usability: cohesive responsive navigation, readable messages, theme preference and explicit saved/temporary chat behavior.
- Maintainability: separated auth, Docs, model, quota/config and telemetry services; versioned Alembic migrations and documented setup.
- Observability: useful timings, state and cost estimates without secrets. Database outages may prevent durable event writes.
- Bounded resources: default 50-message model history with bounded older-history summary, completion budget and 300-second Docs cache. No measured production latency guarantee is claimed.

## 6. Configuration and data

Defaults are 50 messages/day, 50,000 tokens/day and 5 requests/60 seconds, subject to administrator/runtime configuration. Model and estimated cost rates are configurable. Entities include users, sessions, auth tokens/throttles, conversations, messages, daily usage counters, app configuration and telemetry.

`eval/prompts.json` is the submitted evaluation dataset; regression tests use synthetic provider/Docs content. Persona/reference documents are private external Google Docs configured by ID. They must be provisioned by the operator and are not bundled as public datasets. Production users, sessions, conversations, database dumps and credentials are excluded.

## 7. Evaluation and success criteria

| Criterion | Weight | Assessment |
| --- | ---: | --- |
| Task success/relevance | 20% | 1 = does not meet; 3 = partially meets; 5 = fully meets |
| Grounding fidelity | 20% | Compare to reference source; keywords alone cannot prove factual fidelity |
| Guardrail enforcement | 20% | Ownership, quotas, throttling and extraction checks |
| Robustness | 15% | Provider, Docs and database failure behavior |
| Architecture/code quality | 15% | Source review and automated checks |
| Evaluation rigor/writeup | 10% | Prompt isolation, metadata, usage/cost/latency and explicit verdicts |

Carried-forward targets: at least 99% of completed turns persisted, all cap violations blocked, zero internal prompt/grounding disclosure, complete stored history reopening and ordinary Doc changes visible after cache expiry. These are targets, not measured production guarantees.

October 2 automated verification: **128 tests passed**, including all 15 evaluation-harness tests and all three database-outage tests; frontend lint and production build passed. Detailed evidence is in `docs/FINAL_VERIFICATION.md` and `docs/evidence/`.

The September 23 live quality artifact has 2 PASS, 2 FAIL and 4 NEEDS_REVIEW rows. It remains historical evidence rather than full acceptance of this revision. Source-level factual review, extraction review and deployment browser checks are outstanding; dry-run output is not live model evidence.

## 8. Delivery acceptance

Source acceptance: regression checks, frontend lint/build, included migrations, documented dependencies/setup and verified ZIP contents. Deployment acceptance additionally requires target migration status, cookie/origin/secrets configuration, real OAuth and mail flows, browser secrecy/history, live Docs refresh and live model review.

Deliver revised `PRD.md`, comprehensive `README.md`, and a ZIP with complete source, scripts, tests, dataset/results, documentation and assets. Both Markdown files must also be inside the ZIP. Include a file manifest and separate archive checksum. See `docs/TIMELINE.md` for milestones and outstanding checks. Packaging does not send email, deploy or push changes.
