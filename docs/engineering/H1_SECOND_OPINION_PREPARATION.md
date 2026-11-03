# H1 second-opinion preparation

Status: implementation candidate, synthetic-only, stacked on draft #383.

This increment composes existing H1 patient context into a preparation checkpoint for a second-opinion discussion. It intentionally does not port the old SQLite second-opinion ledger from draft #86. That donor demonstrated useful product semantics: preserve original conclusions, pin shared materials to exact versions, and reopen dependent work after amendment. It predates the current PostgreSQL patient/source/question/evidence owners.

The new projection is read-only. It requires the same successfully selected patient/case as Overview, a case-scoped source-index read, and case-scoped saved-question history. It counts current versus historical source versions, current versus reassessment questions, and open recorded coordination. Any reassessment question blocks the prepared-inputs state. Missing or unchecked reads remain unknown rather than becoming zero.

No referral, recipient, disclosure, export, clinical approval, eligibility conclusion or appointment is created. The next server-backed milestone should add a first-party second-opinion request record only after recipient identity/authorization and deliberate record-selection contracts are defined.


## First hosted attempt

Run 41716729175 passed the inherited synthetic boundary and dependency-rights setup, then executed 409 client-test entries with 408 passes and one harness failure. The new test file could not import `.test-dist/second-opinion-preparation.js` because `tsconfig.client.json` compiled only the registry-client entrypoint. The production feature source itself was not reported as a TypeScript error. The test compiler now includes the new pure projection explicitly; no runtime behavior, permission contract or product boundary is relaxed.
