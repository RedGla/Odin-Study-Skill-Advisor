# Release and submission checklist

Updated October 2, 2026. Evidence: [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md).

## Submission preparation

- [x] Full automated suite: 128 passed, including evaluator and database-outage checks.
- [x] Frontend lint and TypeScript/production build passed.
- [x] Dry-run evaluator report generated separately from live results.
- [x] Preserve historical live results and their actual failure/review states.
- [x] Revised PRD includes Google OAuth feedback and final specifications.
- [x] Comprehensive root README and project-specific frontend README.
- [x] Timeline/closeout and test evidence retained.
- [x] Local HEAD compared with fresh remote dev SHA: equal; working tree changes remain unpushed.
- [x] Reproducible ZIP packager includes documentation, source, assets and dataset, with hashes.
- [ ] Owner uploads/sends final ZIP, PRD and README by the supplied deadline.

## Separate deployment acceptance

- [ ] Confirm all migrations on the actual target database (local test migrations passed).
- [ ] Confirm production cookie, frontend-origin, session and secret configuration.
- [ ] Confirm production admin caps and rate limits.
- [ ] Verify real Google OAuth consent, callback and account linking.
- [ ] Verify actual recovery/verification email delivery with the implemented mail transport.
- [ ] Inspect browser network traffic for internal prompt/grounding exposure.
- [ ] Log out/in and reopen a complete saved conversation in the deployed UI.
- [ ] Verify a live Google Doc edit becomes visible after cache expiry.
- [ ] Run current live quality/extraction evaluation with a dedicated account and human source review.

Database-outage behavior has passed controlled injected-failure tests; no real production shutdown or recovery drill is claimed.
