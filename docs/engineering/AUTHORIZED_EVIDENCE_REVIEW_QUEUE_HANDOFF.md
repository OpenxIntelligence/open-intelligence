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

Only **`returned`** is permitted. The receipt's reviewer label is the actor from the existing synthetic policy callback, with reason; the item remains queued, its immutable history survives correction and source-evidence amendment changes its fingerprint. Neither the adapter nor a fictional receipt can issue `reviewed`, `acknowledged`, clinical signature, clinician clearance or treatment action. The queue is the existing single review owner; this feature does not mint another approval state.

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
