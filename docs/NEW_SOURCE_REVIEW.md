# Open Intelligence — explicit new-source review

**Complementary implementation proposal, 2 November 2026. Synthetic-only.**

This adds a bounded review action to the existing case/source/investigation workflow. It does not replace the architecture, select a stack, establish clinical relevance or introduce a second patient ledger. It follows the remaining new-event boundary identified during PR #76 replay and maps to OI-007, OI-009 and OI-018.

## Behavior

A correction to a bound source already propagates staleness through the existing amendment workflow. A distinct newly received record is not necessarily a correction, and its arrival alone does not establish which prior interpretation it affects.

An operator can now open **Review newer source** on an existing human-authored investigation, select one later-received first-version source and its exact finding line, and record why the earlier investigation should be reconsidered. The source list is receipt-ordered, not clinically ranked. The operator's statement is attributed, not validated by software.

The transaction marks only the selected snapshot stale, reopens its question, and reuses existing option-dependency invalidation. It preserves both source records, the earlier summary and source bindings, prior demo review acknowledgment, and the original specimen inventory. No replacement interpretation is accepted automatically. A stale card exposes **View review requests**; the existing changes projection identifies a new-source request separately from an amendment.

## Contract and implementation

- `source_review.py` reads/writes the existing SQLite connection, snapshots, questions, assertions, option dependencies and events. No new schema or tables.
- GET `/api/cases/{case}/snapshots/{snapshot}/new-source-review` is read-only and returns eligible sources plus historical request receipts.
- POST to the same route requires exactly `source_version_id`, `source_line`, `reviewer_label`, `rationale`.
- Only positive integer IDs (not booleans), same-case records, current first-version sources received after snapshot creation, and exact assertion lines are allowed. Amendments, headers, previously available/bound sources and stale snapshots are rejected.
- Ordering uses ledger event IDs, not second-resolution timestamps or clinical event dates. An older clinical event received later can be a review input.
- The receipt captures the exact source hash/quote/line, source-import and snapshot-creation event IDs, actor label, rationale and affected IDs.
- Identical normalized snapshot/source retries return the original receipt; different retry payloads fail. Historical duplicate receipts remain readable after source supersession.
- An immediate transaction contains invalidation and the audit event; a failed audit write rolls back state changes. Concurrent identical requests produce one receipt.
- Native form text uses text nodes; no untrusted HTML. Case and refresh-epoch guards discard obsolete responses, including A→B→A navigation. A failed context load offers a retry.

## Scope limits

This is **explicit operator-directed reconsideration**, not automatic semantic impact discovery. It does not find every affected interpretation, determine clinical relevance, rank therapies, verify professional identity, or authorize orders. A replacement draft remains a separately authored action; the feature does not enforce clinical adequacy of that replacement.

Existing model-investigation freshness is a distinct concern covered by open Composer PR #91/#68; this contribution does not modify those models or claim those branches are integrated. Shared HTTP/UI integration must be reconciled before merge. All operation remains within the current unauthenticated, local, synthetic-only demonstration. Do not enter real patient records.

## Test evidence and reproduction

Base: `52ea683fbe3537b17a05066dceff2ba01f758c5d`, tree `a7cb00f67182369372b338f447c2e030d02fa328`, reconstructed from authenticated CI artifact 13170859059. The archive SHA-256 was verified as `1f59f1d32f2e6522f051ed398bc814559c6c845b11ddde9cba91b6482d85a952`.

Fourteen domain tests were first observed failing because the command was absent; four actual HTTP tests first failed on missing routes. Eight JavaScript interaction tests include observed red tests for the missing UI, A→B→A response race, and absent retry control. The resulting local focused suite passes all 18 Python and eight new Node checks. All 31 Python test modules completed successfully when run separately, totaling 254 tests: one module timed out under concurrent execution and subsequently passed alone. This is not reported as a completed local single-process full-suite run. The new plus existing Node suites passed 47 tests. Compile, JavaScript syntax and diff whitespace checks passed.

Local Chromium initially refused root startup; running under the ordinary non-root account retained the browser sandbox, but navigation returned an organization-policy block for localhost. That is not a browser pass, and the policy was not bypassed. A dedicated Chromium journey is included in existing hosted CI; inspect its result for the exact PR source before claiming browser verification.

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_new_source_review*.py' -v
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/test_new_source_review_ui.js tests/test_source_dialogs.js tests/test_source_line_diff.js tests/test_text_changes.js
PYTHONPATH=src python tests/browser_new_source_review.py
```

No independent clinical reviewer, clinical validation, PHI authorization, treatment decision, deployment or architecture adoption is established. Keep the contribution draft and unmerged pending review.
