# Open Intelligence — First-party domain-event transport contract

Status: implementation PR; not adopted/merged. Founder mandate: full first-party clinical and biomedical platform, not hackathon demo. This is one reusable engineering component within existing Open Intelligence architecture, not a replacement patient ledger or new healthcare service topology.

## Implemented in this branch

`src/open_intelligence/platform_events.py` implements a standard-library-only SQLite transactional outbox and a strict `oi.domain-event/1` reference envelope. It can operate on the existing `CaseStore.db` connection without replacing or cloning its source, patient, evidence, or clinical-domain tables.

- **Transactional enqueue:** callers append their authoritative domain state and `enqueue(conn, event)` in the **same caller-controlled transaction**. This API performs no commit; rollback removes both changes.
- **Strict envelope:** rejects unexpected/inline payload fields, missing or incompatible domain/type, weak identifiers, naive `recorded_at` timestamps and invalid time precisions. Stores only event metadata and artifact references, never clinical source content.
- **Idempotency:** event ID + canonical SHA-256 serialization; exact retries do not duplicate, conflicting reuse raises a deterministic error.
- **Delivery:** SQLite `BEGIN IMMEDIATE` lease claims; crashed-worker lease expiration permits at-least-once redelivery. Acknowledgment records broker acceptance, not clinical completion or downstream consumer execution.
- **Failure:** opaque error-code retry/dead-letter states; no real patient data or free-text failure details in the transport journal.
- **Consumer receipt:** `consume_once(conn, consumer, event, apply_effect)` writes a domain projection plus an idempotent, content-hashed inbox receipt in the same caller-owned transaction. Identical redelivery is a no-op; changed content with the same event ID fails. Consumer callback must separately enforce trusted permissions and aggregate/version/subject checks.
- **Tests:** full original `CaseStore` database co-location, rollback, conflicting ID, restart/lease recovery, worker-isolated ack, dead-letter, and schema validation.

## Not implemented / never claim otherwise

- No new EHR/LIS/PACS/genomics/pharmacy *operational* records or patient-facing routes are created by this module.
- No real identity verification, consent evaluation, policy/authority resolution or external delivery is performed; an `authorization_decision_ref` is **not** proof of approval.
- No PostgreSQL implementation, HA broker, real multitenancy, PHI-ready controls, deployed event processor, outbox/consumer observability, encrypted object store, recovery procedures, or clinical validation.
- The inbox primitive does not automatically enforce event ordering, expected aggregate revisions, consent or subject resolution; a bounded domain consumer must verify these before invoking the callback.
- `complete` signifies transport broker acceptance only. Actual recipient processing must establish an independent versioned, idempotent receipt.
- No stack selection or external runtime dependency is introduced; distribution license and clinical deployment remain undecided.

## Required first-party integration sequence

1. Review the current domain contract proposal [PR #49](https://github.com/OpenxIntelligence/open-intelligence/pull/49), especially DC-04 / DC-05 / DC-06 / DC-07 / DC-08, before changing event schemas.
2. Integrate through a reviewed adapter that writes to the same transaction as each originating authoritative domain state transition. Begin with the stacked first-party [clinical/LIS PR #56](https://github.com/OpenxIntelligence/open-intelligence/pull/56) after dependent identity branches are merged/reconciled. Do not force this branch to merge first.
3. Add a consumer-inbox table with atomic accepted effects, cross-domain aggregate version checks, patient/specimen isolation, and revocation propagation. Test retries, duplicates, out-of-order corrections, event-chain causality and replay from source custody.
4. Implement a production persistence adapter after a documented PostgreSQL vs alternative technology choice, with real tenant and purpose-bound authorization, encryption, backups, migrations, audit, monitoring and idempotent recovery.
5. Expose status/receipt views only through authenticated services, never directly from worker state into a clinical decision.

## Non-negotiable acceptance for production qualification

| Category | Required evidence |
|---|---|
| Correctness | Atomic operational write and outbox; duplicate safe; aggregate revision fencing; fail and replay tests |
| Authority | Trusted identity, consent, purpose-based authorization at command, delivery, read and export |
| Data quality | Patient/episode/specimen-qualified routing and provenance of original source/versions |
| Safety | No AI hypothesis becomes a signed assessment or treatment action without authorized clinical review |
| Operations | Recoverable backup/replay, measured delivery latency, dead-letter handling, HA and monitoring |
| Security & rights | Threat model, penetration/security assessment, exact dependency/SBOM/asset clearance |
| Validation | Independent functional, clinical and regulatory qualification before real patient use |

The full product encompasses first-party EHR/oncology, LIS, pathology, RIS/PACS, genomics, treatment/pharmacy, patient/professional services, scientific research, intelligence, and institutional operations. The durable event boundary is foundational for integrating them; it does not, by itself, deliver them.

Existing canonical references:
- [Open Intelligence Notion team dashboard](https://app.notion.com/p/40a3866f77ef81eb91a9c696198ed71b)
- [Full healthcare domain-contract draft PR #49](https://github.com/OpenxIntelligence/open-intelligence/pull/49)
- [Clinical/LIS operational PR #56](https://github.com/OpenxIntelligence/open-intelligence/pull/56)
- [OI-17 licensing and commercial rights policy](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9)
