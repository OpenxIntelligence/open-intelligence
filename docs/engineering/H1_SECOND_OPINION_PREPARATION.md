# H1 second-opinion preparation

Status: implementation candidate, synthetic-only, stacked on draft #383.

This increment composes existing H1 patient context into a preparation checkpoint for a second-opinion discussion. It intentionally does not port the old SQLite second-opinion ledger from draft #86. That donor demonstrated useful product semantics: preserve original conclusions, pin shared materials to exact versions, and reopen dependent work after amendment. It predates the current PostgreSQL patient/source/question/evidence owners.

The new projection is read-only. It requires the same successfully selected patient/case as Overview, a case-scoped source-index read, and case-scoped saved-question history. It counts current versus historical source versions, current versus reassessment questions, and open recorded coordination. Any reassessment question blocks the prepared-inputs state. Missing or unchecked reads remain unknown rather than becoming zero.

No referral, recipient, disclosure, export, clinical approval, eligibility conclusion or appointment is created. The next server-backed milestone should add a first-party second-opinion request record only after recipient identity/authorization and deliberate record-selection contracts are defined.


## First hosted attempt

Run 41716729175 passed the inherited synthetic boundary and dependency-rights setup, then executed 409 client-test entries with 408 passes and one harness failure. The new test file could not import `.test-dist/second-opinion-preparation.js` because `tsconfig.client.json` compiled only the registry-client entrypoint. The production feature source itself was not reported as a TypeScript error. The test compiler now includes the new pure projection explicitly; no runtime behavior, permission contract or product boundary is relaxed.


## Verified implementation checkpoint — draft PR #391

The implementation/test head is `ef11d1fc865412e2c4e44b34e192e87e1031ab88`, tree `9aaa8f96678fd3d32396793bd97623011e943ed6`. Hosted run 41717010608 completed successfully against the actual H1 web gate.

Observed results:
- 413 client tests passed with zero failures.
- 13 installed-package rights tests passed; 18 installed packages were inspected and two omitted optional packages remained explicitly uninspected.
- npm audit reported no vulnerabilities.
- TypeScript/Vite production build passed.
- Existing backend wheel/dependency gate passed.
- The actual PostgreSQL 16 / FastAPI / built React / Chromium journey passed, including the inherited records, questions, review, evidence, follow-through, import, case-switch and session-boundary flows.
- The new browser assertion ran after a real source amendment and required the second-opinion preparation card to show `needs_reassessment`, to state that it does not create a referral or confirm an appointment, and to warn that earlier preparation is not current.

Verification artifact 13269773470 has SHA-256 `8af2832e57e92f2ef470f1ea98416428006b32724c36b6f3ddb9bf06eee0b32b` and expires 10 November 2026.

The first hosted attempt, run 41716729175 on `d77ff5f05bf74c71acbe440abd4a8371a5b66e2c`, is retained as negative evidence. It executed 409 test entries with 408 passes; only the new test-file process failed because the new projection had not been emitted by the test TypeScript config. The repair explicitly added the projection to the test compiler. No runtime, authorization, clinical or external-action behavior changed.

Status remains synthetic-only, draft, unmerged and undeployed. This checkpoint establishes preparation-state composition, not a completed second-opinion request/transfer workflow, clinician identity, consent, record-completeness proof or clinical validation.
