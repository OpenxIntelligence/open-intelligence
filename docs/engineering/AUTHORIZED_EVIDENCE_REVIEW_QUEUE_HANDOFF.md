# First-party evidence review handoff — existing review queue integration

**Status:** draft synthetic integration, requires owner review and exact-head CI before acceptance. **This is not clinical signoff, licensed publication ingestion or real-patient use.**

## Implemented, not duplicated

Extends [PR #143](https://github.com/OpenxIntelligence/open-intelligence/pull/143)'s original `EvidenceReviewPacket`, which itself stacks on #132/#130/#95 and #93. Reuses **the source-owned append-only review queue code** from [PR #82](https://github.com/OpenxIntelligence/open-intelligence/pull/82), including original `review_receipts` table and `review_queue` / `add_review_receipt` methods. The upstream unchanged schema/method sections were copied into the same existing `CaseStore` code; do not merge them twice. The original upstream store blob was `0f93ba705156e8a75b4db999a5ff47103c0cb97e`. The current integration code's only *new behavior* is the `AuthorizedEvidenceReviewHandoff` adapter and its tests. No second patient registry, source ledger, research provider, reviewer ledger, notification queue or model runtime was created.

The integration is deliberately limited to **independently authored fictional** research evidence previously ingested into the *existing* synthetic evidence ledger. Before a review handoff, validate:
1. Canonical patient/case/actor/purpose via existing clinical Composer/knowledge preflight.
2. Exact source-quoted packet, patient source version/hash/line, rights-qualified fictional provider declaration and current-source status.
3. Identical version, date, original text, relation and applicability between the provider record and the **persisted original fictional `evidence_versions` and `evidence_assessments`**. A metadata-only literature link or external publication cannot be silently converted into a fake synthetic source.
4. An unresolved queue item `evidence-assessment:<id>` already derived by the source-owned queue.
5. A second fresh preflight and source-quote recheck before issuing a nonterminal return receipt.

A separate **`evidence.review_return` write-action authorizer** is required, distinct from patient-source read permission. It is denied by default, checked before the two preflights and immediately again before appending the effect. A test-only policy callback may grant this action, but its textual actor label is not real authenticated professional identity. Revoking the write grant during preflight prevents receipt creation.

Only **`returned`** is permitted. The receipt's reviewer label is the actor from the existing synthetic policy callback, with reason; the item remains queued, its immutable history survives correction and source-evidence amendment changes its fingerprint. Neither the adapter nor a fictional receipt can issue `reviewed`, `acknowledged`, clinical signature, clinician clearance or treatment action. The queue is the existing single review owner; this feature does not mint another approval state.

## Strict Boolean write-policy enforcement

The independent `evidence.review_return` policy callback now grants permission **only when its return value is exactly the Boolean `True`**. Truthy objects, numbers and strings are rejected, including when a non-Boolean result appears only on the final effect-boundary recheck. Policy exceptions also fail closed. The negative regressions explicitly assert rejection occurs **before any evidence packet read** when the initial policy result is invalid and that no review receipt survives when permission changes at the final check. This is a review-owner source repair motivated by the composed report/review work in [PR #165](https://github.com/OpenxIntelligence/open-intelligence/pull/165), not a new authorization service. A test callback is still not a verified professional credential.

## Transaction-bound preview freshness (additional repair)

The review handoff now passes its previously authorized `queue_fingerprint` to the **existing** `CaseStore.add_review_receipt(..., expected_fingerprint=...)` API. The review owner recomputes the current queue item *inside* its `BEGIN IMMEDIATE` transaction and rejects a mismatch before appending either a receipt or event. Without this condition, a corrected evidence version arriving just after the last external-rights preflight could have caused a receipt to be recorded against a different queue state than the one inspected. Existing callers not supplying a preview fingerprint preserve their original API behavior; a production action must supply a version-bound precondition.

Regression tests intentionally amend a fictional evidence source **between preview and write**, verify no stale receipt or event, then test a successful exact-fingerprint return. This closes the same-DB queue-version race, **not** the separate-rights-provider or authenticated-grant races; no distributed transaction or clinical approval is claimed.

## Append-only database enforcement

The existing `review_receipts` source-owner schema now has SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers that reject rewriting or erasing historical receipts. This is an additive migration-safe rule for the existing table, not another audit store. Regression tests exercise direct SQL attempts to turn a returned receipt into `reviewed` or delete it, verify both are rejected and the original receipt remains. Database administrators, offline copies, privileged backups and full audit retention still need independent controls; triggers are not a tamper-proof production audit service.

## Non-atomic external-rights boundary

The external rights provider and review receiver are not part of one distributed transaction. Rechecks narrow but cannot eliminate races with independently stored permissions. Therefore a nonterminal `returned` receipt is safe as a review request; promoting to a terminal approved item requires a separate transactional, authenticated, version/authority-bound clinical-review API. Do not incorrectly call a textual actor label verified clinician identity.

Literal quotes provide citation traceability, not semantic entailment or clinical applicability. The source provider's `permission_receipt` is a *fictional claim*, not licensed NCCN/ASCO/ESMO rights. No models or third-party services are contacted. The current test EHR/clinical/LIS pipeline still uses independently invented synthetic fixtures. Do not incorporate Sid's case data.

## Tests and ownership

The new cross-domain regression runs actual PatientRegistry/EHR/LIS/source/Composer/source-rights and unchanged review owner code. It covers:
- Exact versioned patient assertion plus fictional evidence quote reaches the existing review queue, then appends one `returned` receipt, leaving the item pending.
- External revoked rights or metadata-only evidence fail closed.
- Mismatched source key/version/date/text, wrong assessment, wrong case/actor/purpose and source amendment fail closed.
- Original fictional evidence amendment preserves the prior return receipt but changes the queue fingerprint and reopens the item for review.
- No new database, clinical decision, model execution or synthetic case derived from a real patient.

**Dependencies:** #82 owns review queue, #143 owns quote validation, #132/#130/#95 own patient/clinical/Composer, #93 owns source rights. Coordinate base and code conflict before merge. The exact-head tests and hosted UI/HTTP suites must pass and be independently inspected; no automatic merge or production deployment is authorized.
