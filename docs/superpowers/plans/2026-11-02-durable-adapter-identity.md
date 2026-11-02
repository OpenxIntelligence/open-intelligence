# Durable Synthetic Adapter Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make synthetic adapter subject bindings and receipt revocations survive SQLite restart and prevent concurrent/conflicting deliveries using the existing canonical case/source/event ledger.

**Architecture:** Extend the existing `CaseStore` with two narrowly scoped adapter-gate tables and a transactional adapter import method, while keeping original bytes and clinical assertions in `source_versions`. Preserve `PatientAccessAdapter`'s public contract; actual `CaseStore` uses the durable transactional path, while existing isolated test doubles can retain their in-memory mechanics. Avoid a new patient ledger, external authorization service, new dependencies, schema reset or Next.js.

**Tech Stack:** Python 3.11+, standard-library sqlite3, unittest; existing synthetic-only CaseStore.
**Spec:** `docs/research/FULL_SYSTEM_DOMAIN_CONTRACTS.md` (DC-01, DC-05, DC-07) in founder PR #49 and the existing `docs/research/OI017_PATIENT_ACCESS_BOUNDARIES.md`; prior identity fix PR #51.

## Global Constraints

- All data is independently authored synthetic fiction; no real records or credentials.
- Preserve original source bytes and current amendment/invalidation semantics.
- No additional third-party dependencies, Next.js, new canonical patient store, medical inference or clinical approval.
- Keep product authority, human decisions and actual consent management unclaimed; adapter receipts are synthetic test envelopes.
- Preserve other branches; PR is draft pending review, not merged.

## Review Focus

1. Two CaseStore connections opening the same SQLite file must not accept a conflicting qualified subject into two cases.
2. Rejected/quarantined/failed imports must never persist a successful binding.
3. Revocations must apply after closing and reopening the adapter/store and cannot be bypassed by a fresh adapter.
4. A failure after source insertion but before the accepted receipt must roll back the source, binding and receipt together.
5. A duplicate unchanged source must be idempotent and preserve the first binding without a second accepted event.

---

### Task 1: Write the durable-state regression tests

**Files:** Create `tests/test_durable_adapter_identity.py`.

**Interfaces:**
- Consumes `CaseStore(path)`, `PatientAccessAdapter(store)`, `AdapterEnvelope`, `AuthorizationReceipt`, `CaseStore.state()`, `CaseStore.source_text()`.
- Produces tests for fresh-adapter restart, two-connection conflict, revocation recovery, invalid import rollback, a forced event failure rollback, duplicate stability and valid namespace reuse.

- [ ] Write tests against the actual CaseStore (no stubs).
- [ ] Verify they fail against PR #51 with missing durability/transactional guarantee; preserve the failing result.

### Task 2: Add durable registry tables and store-level transactional import

**Files:** Modify `src/open_intelligence/store.py`.

**Interfaces:**
- Add `adapter_identity_bindings` indexed by `(source_organization,source_system,source_subject_ref)` and unique by `(case_id,source_organization,source_system)`, plus `adapter_receipt_revocations` keyed by `(case_id,receipt_id)`.
- Add `CaseStore.import_adapter_report(case_id, raw, *, source_organization, source_system, source_subject_ref, receipt_id, adapter_id, retrieved_at, loss_receipt=None) -> dict`.
- Add `CaseStore.revoke_adapter_receipt(case_id,receipt_id,reason) -> dict`.
- Refactor `import_report` transaction wrapper to reuse a private `_import_report_in_transaction`; source versioning, invalidation and event behavior MUST remain byte-for-byte equivalent in semantics.

- [ ] Add version-safe `CREATE TABLE IF NOT EXISTS` tables; preserve existing DB on reopen.
- [ ] Add atomic `BEGIN IMMEDIATE` identity, revocation, import, binding and accepted-receipt path; existing `import_report` remains usable.
- [ ] Rejected conflicts go to existing quarantine; no binding. Revocation retains historical source but blocks further gated imports.
- [ ] Prove forced receipt failure rolls back source and binding.

### Task 3: Route real CaseStore adapter path through durability

**Files:** Modify `src/open_intelligence/patient_access.py`.

**Interfaces:** `PatientAccessAdapter.deliver(envelope,raw)` and `revoke(case_id,receipt_id,reason)` keep existing signatures.

- [ ] Ensure input validation, date checks and transform-loss checks are unchanged.
- [ ] For actual CaseStore, delegate to `CaseStore.import_adapter_report` and `revoke_adapter_receipt`.
- [ ] Preserve existing fake-ledger tests as explicitly labeled test-only fallback; never treat fallback as production durability.

### Task 4: Verify and document

**Files:** Modify existing `docs/research/FULL_SYSTEM_DOMAIN_CONTRACTS.md` in PR #49 only through a separate coordinating review, or add a targeted note in this branch's plan. Do not rewrite canonical Notion or duplicate source ledgers.

- [ ] Run `PYTHONPATH=src python -m unittest discover -s tests -v`.
- [ ] Run Python compilation and existing browser journeys on a merge candidate; independently inspect GitHub Actions exact commit and log.
- [ ] Record what is **not** built: authenticated issuer proof, durable real-world grant issuance, multi-tenant production ACL, licensed healthcare assets, real PHI, clinical review authority.
- [ ] Open a draft PR dependent on PR #51; do not merge automatically.
