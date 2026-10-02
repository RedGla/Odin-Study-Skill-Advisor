# Product Requirements Document — Advisor Console

## 0) Meta

- **Feature Name:** Advisor Console — Odin - Study Skill Advisor
- **Doc Owner:** Red & Neil
- **Date / Version:** October 2, 2026 / v0.1
- **Timeline:** 3 weeks
- **Deployment:** Vercel frontend — https://advisor-console-nine.vercel.app; Render backend — https://advisor-console.onrender.com; Supabase PostgreSQL persistence. These are the documented deployment targets, not a fresh uptime certification.
- **Stack:** React 19, TypeScript, Vite 8, Tailwind CSS 4; Python/FastAPI, SQLAlchemy 2.0, Alembic; PostgreSQL; Google Docs API (read-only); one configurable LLM through OpenRouter; session-cookie authentication and Google OAuth.
- **Repository:** `RedGla/Odin-Study-Skill-Advisor`, branch `dev` (formerly `RedGla/Eskwelabs-Advisor-Console`).
- **Submission deadline:** October 2, 2026, 5:00 PM, interpreted in Asia/Manila.

### Source template and feedback

Compared with the original [PRD - Advisor Console](https://docs.google.com/document/d/19m6SnxDl5IxTXJUodXn5XnuNfw88dRhVYEg3zdTmVZw/edit), the [Red & Neil copy](https://docs.google.com/document/d/15gySlEU5WYKf5NEamyXkpKmEiAcmfgd4POkDHAtAoDg/edit), and the [execution timeline](https://docs.google.com/document/d/1Jqz4TxpsNRnNgX05y1PLt_j-xQXMLQeV/edit). This revision follows the template's sections 0–9 and replaces its metadata placeholders with project details.

**Feedback incorporated: Google OAuth was added.** Users can sign in with Google; existing password users can explicitly link their Google identity from Settings. OAuth credentials stay on the server, and Google identity does not grant administrator privileges. Implementation: `backend/google_oauth.py`, routes in `backend/main.py`, and Login/Settings UI. Automated coverage: `backend/tests/test_account_security.py`. Real consent/callback verification remains deployment-specific.

Other additions include the Odin workspace design, temporary chat, account settings and stronger session controls. Registration/login no longer require email verification. See [template comparison](docs/PRD_TEMPLATE_REVIEW.md) for coverage, deviations and outstanding acceptance evidence.

## 1) Problem, Goals & Non-Goals

### 1.1 Problem

The original brief describes EIF mentoring through third-party GPTs/Gems with limited central control over prompts, conversation records, cost and quality. Odin provides a small, internally controlled advisor console with an externally editable persona, document grounding, persisted conversations, usage limits and administrator review.

### 1.2 Goals

1. Provide one web-based study/project advisor for a small group of users.
2. Keep prompt/reference content server-side and editable in Google Docs without redeployment.
3. Save and resume conversations across sessions.
4. Enforce daily message/token caps and basic request rate limits.
5. Ground responses through simple keyword matching.
6. Give administrators conversation, usage, cost and operational visibility.

### 1.3 MVP success metrics

| Metric | Target | Evidence status |
| --- | --- | --- |
| Completed turns persisted | At least 99% | Persistence/failure regression tests pass; production percentage not measured |
| Doc edit becomes live | Within cache TTL, no redeploy | Cache tests pass; live edit demonstration still required |
| Over-cap requests blocked | 100% | Quota/concurrency tests pass |
| Internal prompt/grounding disclosure | Zero | Current live extraction/network verification still required |
| Stored conversations reopen | 100% with full stored history | API/history tests pass; deployed browser check still required |

### 1.4 Non-goals

No vector search/embeddings, multiple advisor personas, in-app prompt editor, enterprise SSO, MFA, billing, distributed rate-limit infrastructure or production uptime SLA. The original template excludes multi-admin support; current role-based administration is an extension, not a required multi-admin management product.

## 2) Users & Use Cases

Primary users sign in, ask study/project questions, continue a thread and reopen saved history. Red & Neil administer persona/reference Docs, usage controls, conversations and operational events. Operators manage deployment credentials and integrations.

Core flows: start/resume a conversation; receive grounded follow-up advice; see clear quota/rate-limit feedback; update Docs without redeployment; review usage/cost as an admin. Settings supports account controls and explicit Google linking. Temporary chat is an added opt-in mode: content is not saved, but quota totals and content-free operational metadata remain.

### 2.1 Constraints

Three-week pair project; favor simple services. Backend secrets belong in environment configuration. Google Docs is the prompt control plane. Model/provider access is configurable. The original brief says end users must not receive cost data; current message serialization includes `est_cost`, an unresolved implementation deviation documented in section 9.

### 2.2 Functional requirements

| ID | Requirement and user outcome | Priority | Acceptance criterion | Dependencies |
| --- | --- | --- | --- | --- |
| FR-01 | User has coherent multi-turn chat | Must | Later replies reflect prior turns | Provider integration, history |
| FR-02 | Admin edits a hidden server-side prompt via Google Docs | Must | Edit is used after TTL without redeploy; raw prompt absent from client | Read-only Docs access |
| FR-03 | User receives grounded, on-persona advice | Could in source; included | Relevant query retrieves reference passages and answer reflects them | FR-02, keyword retrieval |
| FR-04 | User reopens and resumes owned conversations | Must | Full stored history renders; new turn uses bounded context; other users denied | Persistence, ownership |
| FR-05 | Admin controls per-user daily usage | Must | Over-cap requests blocked before provider call with clear feedback and event | Transactional counters/reservations |
| FR-06 | Admin controls request bursts | Should | Excess request receives 429 and retry guidance | Per-user limiter, FR-05 |
| FR-07 | Admin reviews turn/event records | Must | Completed/blocked/error events contain relevant status, timestamps, tokens and cost; saved chat contains user input/response | Persistence, telemetry |
| FR-08 | Admin reviews usage and spend | Must | Role-guarded usage/conversation/event views show correct aggregates | FR-07 |
| FR-09 | Pair evaluates quality and controls | Must | 8–10 prompts/scenarios run with expected/actual results and rubric; quality and cap/rate checks distinguished | FR-03, FR-05, FR-06 |
| FR-10 | User manages secure account/session | Added | Login/logout, password controls, expiring sessions and origin checks behave correctly | Auth and mail for recovery |
| FR-11 | User signs in/links Google after feedback | Added | Verified Google identity is safely linked without role elevation | OAuth client/callback configuration |
| FR-12 | User selects temporary chat | Added | Message content absent from saved history; usage still counted | Auth, quotas, provider |

The source labels FR-03 Could, but its pass-criteria paragraph includes FR-01–FR-05 and FR-09 depends on grounding. Grounding is included here and remains an acceptance target.

### 2.3 Non-functional requirements

Security: server-only internal prompt/grounding payloads and credentials; HttpOnly cookies, production cookie flags, origin checks and ownership enforcement. Reliability: clear provider/Docs/database error states without raw exceptions. Observability: queryable events and cost estimates, with database-outage limitations stated. Maintainability: Docs edits need no deployment; source separates integrations, authentication, quotas and telemetry; schema changes use Alembic. Usability: responsive navigation, theme preference and clear saved/temporary states.

## 3) Data & Knowledge Sources

- [Persona/system-prompt Doc](https://docs.google.com/document/d/1ujFrCT7jG7PzeVcQIsunTXUDa9keuamYY-55k_lkl_4/edit): advisor role, study/project scope and behavior rules.
- [Grounding/reference Doc](https://docs.google.com/document/d/17rH7oJj3XwwVGZMk_T5JnK-efpiKB-Vi1Z-yXf_y3Lk/edit): voice, facts and guidance.
- `eval/prompts.json`: submitted evaluation dataset; regression tests use synthetic context/provider responses.

Use read-only service-account access. Cache each configured document in memory for 300 seconds by default (`GOOGLE_DOCS_CACHE_TTL_SECONDS`). During a fetch failure, use last-good cached content; without it, return a friendly error rather than calling the model with missing persona context. The implementation keys the cache by document ID rather than the template's advisor-ID suggestion; this supports the single persona's two documents.

Links identify the configured source documents; private contents, service-account keys, production database dumps and user sessions are not bundled. The owner-supplied demonstration login is documented separately in the README for reviewer access.

## 4) Prompting & Model Configuration

Red & Neil maintain the persona and grounding documents; Google Doc revisions provide their editing history. The backend assembles the persona prompt, selected keyword-matched grounding excerpts and conversation context. No embeddings are used. Responses are returned through the API; streaming is not required.

OpenRouter model is configured with `OPENROUTER_MODEL` (source default `openai/gpt-4o-mini`). Provider prices used for cost estimates are configurable, not guaranteed billing values. The default model-history limit is 50 messages with a bounded summary of older turns; full stored history remains available to reopen. Default daily controls are 50 messages, 50,000 tokens and 5 requests per 60 seconds. These bound a small learning deployment and can be changed through configuration/admin controls; no measured production cost ceiling is claimed.

## 5) Flow

1. User signs in with password/session or configured Google OAuth, then starts/resumes chat.
2. Backend checks authentication, ownership, chat availability and request limits.
3. Server loads cached/fetched Docs and relevant reference excerpts; prepares bounded context.
4. Daily quota/token reservations are checked transactionally before the provider call.
5. Model returns a response; backend finalizes saved turn status, usage and estimated cost.
6. User receives content or a plain-language error; administrators can review applicable records/events.

Temporary chat follows the same access/usage controls but does not store message content. Unknown provider spend or a post-provider database failure may retain a reservation for later reconciliation.

## 6) Sample Inputs & Outputs

Input: “I'm falling behind on my project — how should I prioritize this week?”

Illustrative expected response, not a captured model result: “Which milestone is closest, and what is blocking it? Pick the smallest task that unlocks that milestone, schedule a focused work block, and ask for help on the blocker. Review progress before adding more tasks.” The actual answer should reflect the configured reference, ask useful diagnostic questions and avoid revealing internal instructions.

| Case | Expected behavior | Evidence |
| --- | --- | --- |
| Daily cap exceeded | Hard block with clear feedback; no new provider call | Quota/race tests pass |
| Rate limit exceeded | 429 with retry guidance | Rate-race tests pass |
| Docs unreachable, no cache | Friendly 503; no ungrounded provider call | Docs failure tests pass |
| Docs unreachable, previous cache | Use last-good context | Warm-cache failure test passes |
| User asks for internal prompt/reference | Decline disclosure; server never serializes raw Docs | Live extraction review remains outstanding |
| Provider timeout/error | Friendly 502 and applicable error event | Provider failure tests pass |
| Database drops during list/history/save | Friendly 503; no raw database exception; do not claim save succeeded | All three database-outage tests pass |

## 7) Evaluation

### 7.1 Rubric

Use 1 = poor, 3 = acceptable and 5 = excellent. Evaluate source accuracy and secrecy with human review; keyword matches and HTTP success alone are insufficient.

| Criterion | Weight | Poor → acceptable → excellent |
| --- | ---: | --- |
| Task success/relevance | 20% | Off-role → mostly useful → consistently on-role/useful |
| Grounding fidelity | 20% | Ignores reference → generally on-tone → reliable source facts/voice |
| Guardrail enforcement | 20% | Bypassable → mostly enforced → adversarially verified |
| Robustness | 15% | Crashes → common failures handled → all listed edge cases graceful |
| Architecture/code quality | 15% | Brittle → reasonable → clear, documented structure |
| Evaluation rigor/writeup | 10% | Missing → present → traceable results and reflection |

### 7.2 Pass criteria and actual evidence

Required: Must FRs work end-to-end; grounding and secrecy withstand review/adversarial checks; caps/rates are enforced; live Doc edits appear within TTL; complete stored conversations reopen; the evaluation set is executed and documented.

October 2 regression evidence: **128 tests passed**, including 15 evaluator-harness tests and all three database-outage cases. Frontend lint and production build passed. See `docs/FINAL_VERIFICATION.md` and `docs/evidence/`.

`eval/results.md` retains the September 23 live quality run: **2 PASS, 2 FAIL, 4 NEEDS_REVIEW**. This does not certify the current prompt dataset/deployment. The structural dry run is NOT_EVALUATED, not a live pass. Current live grounding/extraction review, deployed browser secrecy/history and live Doc-edit demonstration remain outstanding. These documentation edits do not change those verdicts.

## 8) Telemetry & Minimal Schema

Required event vocabulary: `message_sent`, `llm_call_completed`, `request_blocked` (cap/rate), prompt cache hit/miss, `doc_fetch_error`, `provider_error`. Implementation uses telemetry records and structured service logs. Internal system/reference text and provider credentials must not be logged. Logging saved user input is distinct from logging the internal system prompt.

| Entity | Implemented fields / purpose |
| --- | --- |
| conversations | `id`, `user_id`, `title`, `created_at`, `updated_at` |
| messages | `id`, `conversation_id`, `sender` (template role), `content`, `status`, `created_at`, `prompt_tokens`, `completion_tokens`, `est_cost` |
| usage_counters | `user_id`, `date_str` (day), `messages_today`, `tokens_today`, `reserved_tokens_today`, `est_spend_today`; unique user/day |
| users / sessions | Account identity, password hash, role, active state and hashed expiring session tokens |
| telemetry_events | Event, user/conversation linkage, status/reason, applicable content, usage/cost and timing fields |
| app_config / auth tables | Runtime controls, single-use tokens and authentication throttles |

During a database outage, durable database event writes cannot be guaranteed. Temporary-chat records deliberately omit message content. These are explicit exceptions to the original “log every conversation/every failure” wording.

## 9) Open Questions, Risks & Delivery

- **Cost visibility mismatch:** `serialize_message` returns `est_cost` to the owner-facing message endpoint. The original user persona says cost data is admin-only. Documentation cannot certify compliance until this is resolved or accepted as a specification change.
- **Grounding and secrecy:** keyword retrieval can miss nuance. Historical quality failures and extraction review remain open; regression passes are not model-quality certification.
- **Recovery:** a database failure after provider completion can leave a pending turn/reservation; durable outage logging and automatic reconciliation are not guaranteed by the tests.
- **Scope deviations:** Google OAuth is requested feedback; temporary chat intentionally does not log content; role-based administration extends the baseline. These must not silently replace the original saved-chat requirements.
- **Deployment:** real OAuth callback/consent, recovery email, target migrations/cookies/origins and live browser/Docs checks need environment-specific evidence. Current source implements SMTP; existing Resend notes alone do not implement HTTPS email delivery.
- **Timeline:** retain the requested three-week metadata. The original execution plan is September 5–22; the source PRD's risk table separately says four weeks. See `docs/TIMELINE.md` for the original plan versus observed completion.

Deliver revised PRD and comprehensive README separately and inside the ZIP, with complete source, scripts, migrations, tests, dataset/results and assets. The archive manifest identifies the exact local snapshot. The owner subsequently authorized committing and pushing this documentation revision. The demo password is distributed only in the private reviewer ZIP, not Git; publication does not establish deployment acceptance.
