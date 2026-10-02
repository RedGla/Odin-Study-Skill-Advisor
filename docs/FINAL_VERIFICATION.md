# Final submission verification — October 2, 2026

## Subsequent template review

The original Google Docs PRD, Red & Neil copy and execution timeline have now been reviewed. `PRD.md` follows sections 0–9 and includes owner/version/deployment/stack, source-document links, flows, sample responses, schema and explicit feedback for Google OAuth. See `PRD_TEMPLATE_REVIEW.md` for comparison details. Full template acceptance is **not established**: current owner-facing message serialization includes estimated cost despite the original admin-only cost requirement; historical live-evaluation failures and manual deployment checks remain unresolved. This update changes documentation only and does not rerun or supersede the recorded application tests below.

The README identifies the owner-supplied sample-admin account, with role/login status unverified. The private reviewer ZIP includes its password in `DEMO_ACCESS.md`, explicitly excluded from Git. The owner subsequently authorized committing and pushing the documentation revision; the refreshed manifest records its commit and working-tree state.

This report supersedes the previous blanket PASS table. It describes the current local working files based on commit `a1203ec84598a7a3a3c2881e5421494799804db5`, including existing local changes and the submission documentation. Tests validate this source snapshot, not the deployed services.

## Executed checks

| Check | Command | Result |
| --- | --- | --- |
| Full backend and evaluator suite | `python -m pytest -q -p no:cacheprovider --tb=short --maxfail=3 --junitxml=test-results/submission-backend.xml` | **128 passed**, 49 deprecation warnings, 70.08 seconds |
| Evaluator harness independently | `python -m pytest eval/test_eval_harness.py -q -p no:cacheprovider --junitxml=test-results/submission-eval.xml` | **15 passed**, 1.11 seconds; also included in the 128 above |
| Evaluation report structure | `python eval/run_eval.py --dry-run --output test-results/submission-eval-dry-run.md` | Completed; not live model evidence |
| Frontend lint | `npm run lint` in `frontend/` | PASS |
| TypeScript and production bundle | `npm run build` in `frontend/` | PASS; 343 modules, Vite build 2.22 seconds |

JUnit reports, the passing test log and dry-run artifact are retained in [evidence/](evidence/). Backend tests used a disposable PostgreSQL 16 Docker container bound only to localhost:55432; migrations were applied by the fixture. Docs/provider calls were synthetic/mocked. No production database outage was induced.

Initial setup attempts found no pytest in `backend/venv` and then an unavailable local test database (113 setup errors, 15 evaluator passes). System Python supplied the installed test dependencies; starting the isolated PostgreSQL container resolved the setup problem. The final rerun above had no failures or skips. Warnings concern existing Python/Argon2/Starlette deprecations.

## Database-down evaluation — PASS

All three existing tests in `backend/tests/test_db_failure.py` executed successfully:

| Injected failure | Observed and asserted result |
| --- | --- |
| Database query fails while listing conversations | HTTP 503; detail mentions database; no `OperationalError` exposed |
| Database query fails while loading conversation messages | HTTP 503; friendly database detail; no raw exception exposed |
| Database commit fails after model completion during message send | HTTP 503, rather than provider-failure 502; friendly database detail; no raw exception exposed |

Expected user-visible message from the shared database handler: “The database is temporarily unavailable. Please try again in a moment.” Saved history cannot load until database service returns. If saving fails after the provider responds, the response is not reported as successfully persisted; the code retains the uncertain reservation. A pending turn/reservation may require reconciliation after recovery. Database telemetry may also be unavailable during the outage. These results prove the injected failure paths, not full infrastructure failover or automatic recovery from every outage.

## Requirements coverage

| Area | Automated evidence | Remaining deployment evidence |
| --- | --- | --- |
| Multi-turn/history/ownership | Long-history and ownership tests | Browser logout/login/reopen |
| Docs TTL, cold-cache/stale-cache failure, grounding | Docs-failure and grounding-edge-case tests | Actual document edits and factual source comparison |
| Quotas, reservation races, reset boundaries | Cap-race, quota-correctness, token-budget, migration and boundary tests | Deployment configuration |
| Rate limiting | Rate-limit-race and quota tests | Per-process constraint remains |
| Telemetry/admin controls | Telemetry, admin-console, admin-events tests | Target admin/operator review |
| Sessions/passwords/CSRF and Google OAuth feedback | Auth-session, account-security, CSRF-origin tests | Real Google consent/linking and email delivery |
| Temporary chat | Account-security tests | Browser flow review |
| Model quality and prompt secrecy | Harness checks and preserved historical live run | Current live grounding/extraction review and network inspection |

## Historical live evaluation

`eval/results.md` is preserved unchanged: September 23, commit `e4171aa`, eight quality rows, 2 PASS, 2 FAIL and 4 NEEDS_REVIEW. It reports $0.001188 for that run. No new live provider run was performed in this closeout: a dedicated evaluation account/configuration was not supplied. Dry-run rows remain NOT_EVALUATED and rubric values N/A. The two failures and four review states are not overwritten by the passing regression suite.

## Local and remote synchronization at initial preparation

A fresh `git ls-remote origin refs/heads/dev` returned `a1203ec84598a7a3a3c2881e5421494799804db5`, equal to local HEAD. **Committed dev history matches; the working folder is not fully synced**, because it contains existing uncommitted changes plus these submission files. No commit or push had been requested or performed at that initial check. The owner subsequently approved committing all submission changes and pushing to dev; publication is recorded by Git history, with the refreshed ZIP manifest identifying its exact commit and working-tree status. The ZIP includes current local source, not merely committed HEAD. Its manifest records status and hashes so this distinction is inspectable.

## Submission and remaining gates

Revised `PRD.md` explicitly records Google OAuth as feedback incorporated. Root and frontend READMEs now provide project-specific setup/execution guidance. `TIMELINE.md` records completion and outstanding deployment checks. The packaging script includes code, scripts, migrations, tests, dataset, existing visual artifacts/assets and documentation; it verifies ZIP contents/hashes and writes a checksum.

Real deployment migrations/configuration, OAuth/mail delivery, browser secrecy/history, live Docs refresh and current model review remain unverified here. The current mail source implements SMTP; existing Resend configuration notes do not establish a working HTTPS transport. No production data, private Docs text, keys or local environment secrets are included. No deliverables were emailed or uploaded.
