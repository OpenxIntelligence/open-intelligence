# PACSNode retained-store lifecycle implementation plan

> **For agentic workers:** Use the existing task delegation for independent
> tests/review; root owns protocol, runner, workflow and remote branch writes.

**Goal:** Measure original preservation and source freshness across orderly
restart, identical replay and conflicting SOP upload.

**Architecture:** Build on PR #219. Keep the existing smoke/security evaluation
unchanged and run a second, isolated lifecycle experiment using its compiled
binary and confinement helpers. Reuse CaseStore and source-bound WADO.

**Tech stack:** Python standard library; existing pinned pydicom 3.0.2;
unchanged pinned Rust PACSNode; GitHub Actions and Linux network namespace.

**Spec:** `docs/superpowers/specs/2026-11-02-pacsnode-lifecycle-design.md`

## Global constraints

- Synthetic-only; no product dependencies, identity/source schema or H1 changes.
- Exact upstream `e9b4334477a66967d290add9e0b9afa068f59dc0`; uncompressed
  transfer syntax `1.2.840.10008.1.2.1`.
- Same configuration and retained storage across restart; no reseeding.
- Preserve negative receipts and `HOLD_NOT_APPROVED` regardless of CI success.

## Review focus

- Empty/corrupted retained store must fail before another STOW can hide loss.
- Duplicate QIDO rows or overwritten originals cannot pass inventory/integrity.
- A rejecting STOW response does not prove absence of a write.
- Process timeout or wrong PID/namespace cannot be called a successful restart.
- An amended source stays invalid after reopening; upstream errors stay bounded.

## Tasks

### 1. Lifecycle protocol and adversarial controls

- [ ] Add `tests/test_pacsnode_lifecycle.py`; observe failure before implementation.
- [ ] Implement `tools/imaging/pacsnode_lifecycle_evaluation.py` using real
  CaseStore and existing transport/guard; test injection only at HTTP/restart.
- [ ] Verify retrieve-only restart, replay, conflicting overwrite/rejection,
  duplicate inventory, ledger change, amendment and bounded failure evidence.

### 2. Actual backend process lifecycle

- [ ] Add a process driver that waits for both owned confined listeners,
  stops with SIGINT, waits for successful exit, restarts the same store and
  captures distinct process identities in the same test namespace.
- [ ] Extend `run_confined_pacsnode.sh` with an optional lifecycle mode;
  preserve the existing security mode and use distinct artifact filenames.
- [ ] Extend existing workflow with focused controls and real lifecycle run.
  Record acceptance exit status; permit completed negative evidence only when
  its bounded receipt proves the specified conflict, never on an exception.

### 3. Review and exact-head evidence

- [ ] Run application/imaging tests, static data-boundary and workflow checks.
- [ ] Independently review the full diff; fix concrete findings.
- [ ] Publish a draft stacked branch/PR on verified #219; run hosted exact-head
  workflow, inspect actual lifecycle receipt and retain any failed criterion.
- [ ] Update existing project records and report measured outcomes and limits.
