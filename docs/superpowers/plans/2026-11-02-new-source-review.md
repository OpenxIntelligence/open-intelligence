# Open Intelligence: explicit new-source impact review

Continuation of the user's approved next step. This is a bounded addition to existing source/snapshot/question/option objects, not architecture replacement.

## Design
A source correction already invalidates bound drafts. A distinct new report does not. Add an explicit human/demo request linking an existing investigation snapshot to an exact finding line in a later-received, current first-version source of the same case. This is a claim that review is needed, not a determination of clinical relevance or a clinical sign-off. Import alone never infers that relation.

Keep the two source documents current and preserve summary, source bindings, review history and specimen inventory. Atomically mark only the selected snapshot stale, reopen its question and reuse the existing dependent-option traversal. Store source hash, exact quote, source/creation event IDs, reviewer label and reason in the existing events ledger. No new tables. Identical retries return the original receipt; changed retry payloads fail. A valid event already recorded remains replayable even after its source is superseded.

A fresh report for an older event can qualify if received after the draft. Use ledger event order, not second-resolution wall-clock equality. Reject amendments, wrong-case references, existing-bound or previously available sources, header/nonexistent lines and invalid types. An updated interpretation is a separate draft; no clinical order or automatic promotion.

## Tasks
1. Write failing tests for domain request, exact-line binding, narrow invalidation, rollback, restart, idempotence/concurrency and rejection boundaries.
2. Implement source_review.py over the existing database/event helper; no changes to CaseStore schema or import.
3. Test and add GET context and POST request endpoints and a new-source-request cause in changes_since_review. Context lists later first-version sources as unranked review inputs, not clinically relevant matches.
4. Ensure user-facing stale copy does not say every cause is an amendment; no new UI design or adoption decision.
5. Run focused tests, baseline suites by isolated modules as necessary, syntax checks; publish draft, inspect exact source CI, update existing project records. Never merge.

## Overlap
PR #91 concerns model investigation freshness on source-set/evidence changes. Do not duplicate/modify its model behavior. This work is explicit impact review for human-authored snapshots. Reconcile shared HTTP/changes/UI integration during review.
