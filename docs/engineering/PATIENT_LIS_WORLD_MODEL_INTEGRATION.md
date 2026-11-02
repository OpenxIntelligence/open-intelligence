# Canonical patient → synthetic case/LIS → domain event → review-pending observation

**Status:** isolated, stacked integration candidate under [issue #87](https://github.com/OpenxIntelligence/open-intelligence/issues/87); **not merge-ready, not a medical system.** This document supplements (does not replace) the current Open Intelligence architecture.

## Source ownership and integration approach

- Integration base: [PR #89](https://github.com/OpenxIntelligence/open-intelligence/pull/89): opaque canonical patient registry, actual clinical encounters, transactional outbox/inbox.
- LIS: exact original blob for `src/open_intelligence/clinical_lab.py` from [PR #56](https://github.com/OpenxIntelligence/open-intelligence/pull/56); untouched owner branch. The LIS still requires the existing `CaseStore` source and assertion records.
- New `clinical_lab_bridge.py` joins these worlds on one SQLite connection using an **explicit reviewed case binding**, not names or patient labels. `identity_patients` alone owns canonical patient IDs. `cases` retains a **synthetic case/source workspace**, not identity authority. Never treat case ID as canonical patient ID. A human-entered review reference is an auditable *synthetic test input*, not a qualified identity/consent verification.
- `LinkedLabCaseStore` adds a narrow command-event hook. Real LIS command state and CaseStore event are written in the LIS-owned transaction; the hook simultaneously enqueues `oi.domain-event/1` with references only. On outbox failure, the LIS operation is rolled back.
- `CanonicalLabBridge.command` gates the existing original LIS commands through a trusted injected test authorizer and active canonical patient/case mapping. Direct lab-command bypass under `LinkedLabCaseStore` fails closed when it reaches an LIS event. No public API exposes these objects.
- The receiver checks *its own* trusted actor/purpose policy, active mapping, event issuer, patient/case, receipt, source ID, accession/specimen, QC and most recent QC, current source version and linked assertion before it creates **only** a pending review candidate.

## Tested operational stages

```text
canonical patient (identity owner)
  -> explicit source-organization/system/subject binding -> synthetic case workspace
  -> EHR encounter
  -> authored synthetic clinical order source
  -> actual LIS order
  -> actual specimen accession
  -> laboratory source import
  -> passed QC
  -> source-linked result release
  -> same-transaction outbox record
  -> receiving inbox/ordered revision
  -> patient-scoped pending evidence-review candidate
```

The clinical order must be a genuine `ClinicalLabOperations.request_lab_order` state transition backed by a reported synthetic source assertion. An EHR encounter does **not** automatically establish a real clinician's order, and an accession is **not** a laboratory result. The test fixture intentionally exercises those distinct states.

## Identity and provenance invariants

1. No auto-match. One explicit `identity_case_bindings` row links `case_id` to canonical `patient_id`, qualified by source organization/system/subject and a review reference. Conflicting rebinds and duplicate qualified source subjects fail; revocation leaves the historical binding but blocks future commands and consumption.
2. Neither `review_ref`, `actor`, nor the synthetic LIS `requested_by`/`released_by` labels proves clinician identity, consent, or authority; all events contain `authorization_decision_ref: null`.
3. The outbox has no raw patient narrative, source report bytes, clinical finding text, or case-label demographic data. The receiving observation candidate contains only durable references and a reported certainty/status.
4. A released result must have a current laboratory source, matching accession specimen, passed QC tied to the same source, current original order source, matching assertion, and most-recent QC when consumed. A source amendment before projection refuses stale evidence.
5. Consumer idempotency and order are enforced by the original platform outbox/inbox contract. The projection is a *review inbox candidate*, not an accepted Patient World Model belief, verified clinical result, or clinician approval.

## Deliberate incompleteness / review gates

- **Critical:** Reconcile this synthetic `identity_case_bindings` integration table with issuer-qualified durable source-adapter bindings and revocation semantics from [PRs #51/#53](https://github.com/OpenxIntelligence/open-intelligence/pull/53). Avoid a lasting duplicate mapping system; this table is an interim bridge pending contract owner review.
- EHR encounter to laboratory order must establish the authentic ordered-by/encounter relationship with trusted authorized order metadata. The demonstration runs both real modules but has **not yet implemented a foreign-key relation** from clinical lab orders to an EHR encounter.
- Source amendments after projection need an explicit **retraction/invalidation event** to downstream review projections; the current contract rejects stale releases at consume time, but it does not retroactively invalidate a previously consumed candidate.
- The receiver must ultimately use independently authenticated issuer and source reads, not only access to the same local SQLite database. Cross-DB read and consume are **not** an atomic distributed transaction here.
- Production guards remain unimplemented: verified identity matching, treating-clinician credentials, patient/surrogate consent and scope, organizational tenant isolation, PHI security, specimen chain of custody, regulatory lab certification, laboratory interface/FHIR integration, real-world clinical validation, deployment controls, and PostgreSQL/broker consistency.
- No synthetic source should be entered as medical advice, real diagnostic evidence, or patient care. No new dependency, Next.js, or licensed data was added.

## Evidence

`tests/test_patient_lis_world_model_integration.py` exercises order→accession→QC→release→review, mismatched binding, untrusted actor, revocation, duplicate, stale amended source, transport rollback and restart. Hosted CI status must be verified before reporting this slice as passing. Existing [PR #89](https://github.com/OpenxIntelligence/open-intelligence/pull/89) and LIS [PR #56](https://github.com/OpenxIntelligence/open-intelligence/pull/56) remain separate reviews; this new branch must not be merged independently of ownership reconciliation.
