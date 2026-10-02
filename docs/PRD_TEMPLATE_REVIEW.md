# Original PRD comparison — October 2, 2026

Sources reviewed: [original PRD](https://docs.google.com/document/d/19m6SnxDl5IxTXJUodXn5XnuNfw88dRhVYEg3zdTmVZw/edit), [Red & Neil copy](https://docs.google.com/document/d/15gySlEU5WYKf5NEamyXkpKmEiAcmfgd4POkDHAtAoDg/edit), and [execution timeline](https://docs.google.com/document/d/1Jqz4TxpsNRnNgX05y1PLt_j-xQXMLQeV/edit). Only relevant requirements were incorporated; unrelated tabs and API credentials were not copied.

## Verdict

The revised `PRD.md` now covers the original template's sections and project metadata. **Full implementation/acceptance compliance is not yet demonstrated.** Documentation coverage, passing regression tests and end-to-end product acceptance are different claims.

| Template section | Revision |
| --- | --- |
| 0 Meta | Feature name, Red & Neil, October 2 / v0.1, three weeks, concrete deployment and stack |
| 1 Problem/goals/non-goals | Original mentoring-control problem, six goals, five measurable targets and exclusions |
| 2 Users/use cases/FRs/NFRs | Original FR-01–FR-09 IDs and priorities, acceptance/dependencies, added auth/OAuth/temporary-chat requirements |
| 3 Sources | Actual prompt and grounding Doc links, dataset and cache/failure rules |
| 4 Prompt/model configuration | Pair ownership, server assembly, model, context/cost/limit configuration |
| 5 Flow | Sign-in, checks, context, reservation, provider, persistence and review |
| 6 Samples/edge cases | Illustrative input/output and expected failure outcomes, separated from actual evidence |
| 7 Evaluation | Six weighted criteria, 1/3/5 anchors, pass criteria, actual regression and historical live results |
| 8 Telemetry/schema | Required events, actual table fields and outage/temporary-chat exceptions |
| 9 Risks | Model quality, cost visibility, recovery, scope, deployment and schedule discrepancies |

## Gaps and deviations requiring attention

1. **Admin-only cost requirement:** the source's end-user persona excludes cost data. `backend/main.py::serialize_message` includes `est_cost`, and the owner-facing conversation-message endpoint uses that serializer. This is an actual implementation mismatch, even if the UI does not display it. No code was changed in this documentation task.
2. **Current live evaluation:** the retained September 23 quality run has 2 PASS, 2 FAIL and 4 NEEDS_REVIEW outcomes and is tied to an older commit. Current grounding/extraction results and live cap/rate evidence are not established by the 128 passing mocked/local regression tests.
3. **Manual acceptance evidence:** live Google Doc edits within TTL, browser network secrecy, complete deployed history reopening and actual OAuth consent/linking still need deployment evidence. The original timeline also calls for rehearsals and a backup recording; this review does not certify those occurred.
4. **Logging exceptions:** database outages can prevent durable event writes. Temporary chat intentionally omits message content, unlike the original saved-chat “log every conversation” scope. Both exceptions are explicit in the revision.
5. **Scope changes:** Google OAuth is documented as requested feedback. Temporary chat, expanded account controls and role-based administration extend the baseline; they do not replace the original Must requirements.
6. **Source inconsistencies:** FR-03 is Could in the table but included in the pass paragraph's FR-01–FR-05 range; grounding remains included. Metadata says three weeks, the risk row says four, and the timeline spans September 5–22. The revised metadata uses the user's requested three weeks and distinguishes plan from completion.

## Sample reviewer account

The README identifies the sample-admin account supplied by the owner and points reviewers to ZIP-only `DEMO_ACCESS.md` for the password. Its actual admin role and current login availability have not been checked, and no role escalation/account mutation was performed. The password is excluded from Git and included only in the requested private reviewer handoff.

## Verification scope

This follow-up updates Markdown documentation and the packager's explicit option for ZIP-only demo access. Existing application regression evidence remains unchanged; archive integrity/content checks confirm that revised documents are packaged. No Google Doc or application code was edited. The owner subsequently authorized a Git commit and push of the credential-free source/documentation changes.
