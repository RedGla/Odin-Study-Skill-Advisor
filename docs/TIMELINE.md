# Project 1 timeline and closeout

Updated October 2, 2026 (Asia/Manila). Due: Friday, October 2, 5:00 PM, using the user's local timezone for the supplied email's deadline.

The original [Advisor Console execution timeline](https://docs.google.com/document/d/1Jqz4TxpsNRnNgX05y1PLt_j-xQXMLQeV/edit) has now been reviewed through Google Drive. It plans September 5–22, 2026 as a 2.5-week sprint; the PRD metadata calls the overall timeline **3 weeks**. The original PRD risk row also says four weeks, an inconsistency resolved here in favor of the requested three-week metadata. Planned dates below are not claims of actual completion on those dates.

## Original planned sequence

| Planned milestone | Date/window |
| --- | --- |
| Foundation: infrastructure, authentication, persisted chat shell | September 5–7 |
| First check-in | September 9 |
| Core advisor: Docs, model, grounding, persistence | Before the September 15 feature-complete check-in |
| Controls and admin | September 13–14 |
| Feature-complete check-in | September 15 |
| Hardening: extraction, authorization/quotas, service failures | September 16–18 |
| Live evaluation and writeup | September 19–20 |
| Demo freeze, deployment verification and rehearsal | September 21 |
| Final demo | September 22 |
| Updated submission deadline from the supplied email | October 2, 5:00 PM |

The source contains inconsistent core-advisor day/date labels; the sequence above preserves its milestone intent without inventing a single corrected daily schedule.

## Observed closeout evidence

| Milestone | Evidence/date | Status |
| --- | --- | --- |
| Regression/CI baseline and isolated test database | `BASELINE.md`, September 23 | Recorded historical baseline |
| Evaluation harness and live model evaluation | `e4171aa`, `eval/results.md`, September 23 | Completed run; mixed results and human review remain |
| Odin workspace and conversation UX | `1909a77`, `5c30f78`, September 23 | Implemented |
| Account security, Google OAuth feedback, settings/admin improvements | `b2da475`, October 2 | Implemented; real provider consent is a deployment check |
| Remove mandatory verification for login | `a1203ec`, October 2 | Implemented and regression-tested |
| Submission regression checks | October 2, `FINAL_VERIFICATION.md` | 128 tests passed; lint/build passed |
| Database-outage evaluation | October 2, three injected-failure tests | PASS; exact outcomes in verification report |
| Revised PRD, comprehensive README and frontend README | October 2 | Prepared; Google OAuth feedback explicitly included |
| Source/assets/dataset/documentation ZIP and checksum | October 2, `scripts/package_submission.py` | Produced and integrity-checked by packaging script |
| Upload/send deliverables | By October 2, 5:00 PM | Owner submission required; no recipient/upload destination provided |

## Remaining deployment acceptance checks

- Run current live model evaluation with a dedicated account and compare grounding/extraction responses with their sources. Historical failures are retained, not converted into passes.
- Verify actual Google consent and callback, account linking and email recovery delivery on the target deployment.
- Confirm target migration revision, cookie/origin configuration and secret injection.
- Check browser network secrecy, saved-history reopen and live Google Doc changes within the cache TTL.

These do not prevent preparing the requested deliverable files. The submission distinguishes completed implementation/regression work from deployment acceptance still needing external access.
