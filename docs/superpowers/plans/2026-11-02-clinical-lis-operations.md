# First-party Clinical Order → LIS Accession and QC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add actual synthetic first-party operational commands and persisted transitions from an EHR lab request through specimen accession, laboratory quality control and an original-source-linked result release, without misrepresenting these as hospital-integrated or clinically validated.

**Architecture:** One first-party bounded-context module operating on the *existing* CaseStore SQLite connection, case identity, source version table, assertions and events. Own small clinical_order/laboratory state tables; do not create a second patient record, source version store, fabricated scientific measurements or separate agent runtime.

**Tech Stack:** Python 3.11+ stdlib sqlite3 + unittest; existing `src/open_intelligence/store.py`; no Next.js, no new vendor package, no PHI.
**Spec:** `docs/research/FULL_SYSTEM_DOMAIN_CONTRACTS.md` in PR #49, DC-02/DC-03/DC-04/DC-05/DC-07.

## Global Constraints

- Founder full-system first-party mandate; this is the first *working operational* clinical–LIS slice inside that whole architecture, not a redefinition of product scope.
- Independently authored synthetic text and asserted source records only. Lab results must be anchored to a current real `source_versions` row and `assertions` row in the local example ledger; do not invent an observation.
- Commands are **synthetic and uncredentialed**; never label them clinician-authorized orders, real specimen intake, actual laboratory QC, or medical interpretation.
- Owner of patient and original source remains existing CaseStore. The new module owns only operational order/accession/QC/release records, no second patient or source table.
- Every command uses case scoping, explicit idempotency keys, SQLite atomic transactions, event receipts and a stable read model.
- No new third-party dependencies, Next.js, live models, external connections, real patients, deployment or automatic PR merge.

## Review Focus

1. An order alone must not imply specimen received, assay performed, result available, treatment administered or clinical approval.
2. A wrong-case or mismatched-specimen laboratory source must never release a result.
3. A failed/pending QC or pending/not-assessed assertion must never be promoted as a released report claim.
4. An amended source must make prior release visibly stale and require new assessment without deleting earlier release history.
5. Duplicate command keys must be idempotent for identical payloads and rejected for conflicting payloads; event-write failure must roll back the operation.

---

### Task 1: Test operational contract on actual canonical store

**Files:** Create `tests/test_clinical_lab_operations.py`.
**Interfaces:**
- `ClinicalLabOperations(store: CaseStore)`
- `request_lab_order(case_id, order_key, source_version_id, test_label, requested_by) -> dict`
- `accession_specimen(case_id, order_key, accession_key, specimen_id, received_by) -> dict`
- `record_quality_check(case_id, accession_key, qc_key, lab_source_version_id, outcome, checked_by) -> dict`
- `release_observation(case_id, accession_key, release_key, lab_source_version_id, finding_key, released_by) -> dict`
- `cancel_order(case_id, order_key, reason) -> dict`
- `case_state(case_id) -> dict`

- [ ] Write scenario tests for order→accession→passed QC→released fictional observation.
- [ ] Write refusal tests for mismatched source, duplicate conflicts, failed/pending QC, missingness, cross-case data and cancelled orders.
- [ ] Write amendment/restart/replay and atomic event failure tests.
- [ ] Run tests and preserve expected red result before implementation.

### Task 2: Implement bounded first-party operation store

**Files:** Create `src/open_intelligence/clinical_lab.py`.
**Interfaces:** As above; use `CaseStore.db` and `CaseStore._event` only, no new source ledger.
- [ ] Create `clinical_lab_orders`, `clinical_lab_accessions`, `clinical_lab_qc`, `clinical_lab_releases` tables in same CaseStore SQLite DB, preserving all existing tables.
- [ ] Enforce case and current-source linkage, expected laboratory report/specimen, allowed assertion states, and unique idempotent command keys.
- [ ] Require latest QC=passed for the *same current lab source version* as the claimed release.
- [ ] Compute release freshness on read from current source+QC state without overwriting historical releases.
- [ ] Record each new accepted transition in existing case event log atomically.
- [ ] Re-run focused tests; then entire unit/HTTP and browser suite.

### Task 3: Hand off a tested, accurate scope

**Files:** Extend this plan with exact implementation SHA and CI evidence; existing Notion/Drive owners receive concise links/limitations.
- [ ] Distinguish operational synthetic records from imported report narratives and from real hospital/LIS integration.
- [ ] Require review of PR #51, then #53, then this PR; no auto-merge.
- [ ] Record tests, known missing production capabilities, and next product interface/API work.
