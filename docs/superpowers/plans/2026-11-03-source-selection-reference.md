# Source-owned selection reference implementation plan

> Execute inline under the existing founder mandate; use the existing source owner.

**Goal:** Resolve one immutable human-selected passage before connecting it to canonical questions.

**Architecture:** Extend ReviewedDocuments with a scoped read over its existing validated original, frozen extraction and annotation revision. No new persistence, assertions, review ledger or model execution.

**Tech stack:** Existing Python/FastAPI/PostgreSQL contracts and tests, no dependency changes.

## Bounded design

The saved annotation revision already owns exact quote/line and user-selected state.
Add GET `/v1/patients/{patient_id}/cases/{case_id}/documents/{source_id}/selections/{revision_id}/{selection_key}`.
Return a versioned source-selection envelope with an immutable, hashed anchor:
patient/case, source ID/version/original hash, extraction method/hash, revision
ID/number/review hash/actor/time, selected key/state/quote/line/physical PDF page.
Keep current source and latest revision status outside the immutable anchor so
correction/amendment changes freshness without rewriting historical provenance.
Text pages are null; PDF pages come only from the frozen extraction.

Require patient, source-read and original-read authority independently, including
fresh original-credential checks after serialization and audit persistence.
Use the existing binding lock, integrity loader, source-owned access event and
transaction. Missing/wrong-scope references disclose no content or receipt.
Historical selections remain inspectable but explicitly require reassessment.
No source-authored clinical assertion, question, report or clinical approval is
created. A future consumer must re-resolve this anchor under its own authority;
the hash is an identifier, not an authorization token or freshness proof.

Alternatives considered: copying document passages into another ledger loses
ownership; immediately changing Composer/World Model assertions risks silently
promoting human annotations. A source-owned resolver is the bounded prerequisite.

## Task 1 — exact reference, authorization and history

- [ ] Add pure reference and HTTP/PG tests first; observe intended failures.
- [ ] Extend existing source read owner and route; validate identifiers strictly.
- [ ] Check text/PDF page identity, missing selection, correction/amendment history,
      cross-patient denial, independent grants, encoding/audit-time revocation and
      integrity failure without disclosure or durable access receipt.
- [ ] Run full local API/reference suites; distinguish skipped PostgreSQL tests.
- [ ] Publish focused draft child of #380; require exact-head hosted API and web
      acceptance. Preserve donor/parent evidence separately.
- [ ] Review whole diff and update existing gate/backlog and project records.

## Review focus

- Corrected key reused with a new quote must not retarget an older reference.
- Original amendment keeps prior anchor bytes but invalidates its current status.
- A hash is not authority; all original-read permissions remain required.
- Revocation while preparing or auditing a response must roll back its receipt.
- Human-selected states and frozen PDF text are not clinician assessments.

## Execution ledger

Base: #380 `8dde8efac386c9d32ce3ca60d4173a1ef1ffc95b`.
Existing untracked files in the prior checkout were preserved; work is isolated.
No competing passage-reference implementation was found in the latest open PRs.

Local implementation checkpoint: six pure tests passed after the expected missing-resolver failures. Full local API: 449 discovered, 115 passed, 334 PG-dependent skips. Reference suite: 351 passed. No new package or migration; dependency lock/hash/notice verification and pip consistency passed. Independent read-only review found no runtime defect and identified missing integrity-fault route coverage; added copies-of-real-query-result original/rendition/receipt fault tests without disabling immutable table triggers. New PG and browser assertions require hosted execution. Existing route-inventory mismatch was corrected, not bypassed.
