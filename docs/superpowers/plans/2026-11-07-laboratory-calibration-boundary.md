# Laboratory Calibration Boundary Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this bounded
> continuation, with test-driven implementation and an independent final review.

**Goal:** Reserve calibration cases outside the current fitting and validation
selection paths while retaining exact historical v1 record semantics.

**Architecture:** Extend the existing offline artifact contracts, registry and
executor. Keep the canonical H1 patient/source/PostgreSQL owners unchanged.

**Tech Stack:** Existing Python standard library, unittest and SQLite artifact log.

**Spec:** `docs/superpowers/specs/2026-11-07-laboratory-calibration-boundary-design.md`

## Global Constraints

- Starting parent revision: `539705d0741e8192c027c250a2bb016b13d2dca9` from draft #596.
- Integrated parent revision: `f43df38fe230f7dcd05042baf6d7f7b549dd24f7`; retain
  its budget accounting and atomic candidate completion changes. Historical
  compatibility fixtures retain their original producing revision.
- No real patient data, new dependencies, new domain owner, deployment or clinical claim.
- V1 remains `oi.synthetic-laboratory-evaluation/1`; v2 is
  `oi.synthetic-laboratory-evaluation/2`.
- V1's omitted run scope always means train, validation, test.
- V2 runs always store explicit scope. Calibration is never training eligible.
- No calibration fitting, coverage guarantee or unseen-holdout access claim.

## Review Focus

- Historical implicit and validation-only v1 records retain identical JSON/hashes.
- V1 rejects the new role; malformed v2 freezes leave no partial records.
- Calibration identity cannot cross another split through a name/version change.
- Workers and selection do not consume calibration inputs or missing reviews.
- Manual calibration scoring is distinct from the executor and has correct scope.

## Task 1: Versioned roles and immutable record compatibility

**Files:** `apps/api/src/oi_api/laboratory_evaluation.py`,
`apps/api/tests/test_laboratory_calibration.py`,
`validation/laboratory-evaluation/legacy-v1-receipts.json`.

**Interfaces:** Existing `freeze`, `record_run`, `run`, `baseline`, `score`, and
`training_examples` retain their signatures. Contract-specific roles determine
admission and new record scope; historical defaults remain fixed.

- [x] Capture canonical v1 run/review/score payloads with the unchanged parent code.
- [x] Add tests for version boundaries, explicit v2 scope, eligibility, atomic
  cross-role rejection, manual scoring, and retries against the captured payloads.
- [x] Run the new test file before implementation and retain the observed failures.
- [x] Add contract-specific role handling and preserve old serialized shapes.
- [x] Run the focused tests and inspect actual reports and record counts.

## Task 2: Executor exclusion and complete verification

**Files:** `apps/api/src/oi_api/laboratory_experiments.py`, the same test file,
`.github/workflows/laboratory-evaluation.yml`,
`validation/laboratory-evaluation/README.md`, `docs/EXECUTION_BACKLOG.csv`.

**Interfaces:** Existing plan/execute/lineage/compare paths continue using train
and validation only. V2 plans/receipts additionally declare calibration unused.

- [x] Add actual-worker tests with unreviewed calibration cases and compare two
  experiments whose training/validation evidence is identical while calibration differs.
- [x] Observe RED, implement declarations, and verify unchanged selection and exclusion.
- [x] Add the test file to the existing focused CI workflow; update the existing
  usage and OI-011 records with the bounded capability and limitations.
- [x] Run all five focused modules, both existing practice scripts, the synthetic
  data-boundary audit, compilation and whitespace/backlog checks.
- [x] Reopen the actual parent-created v1 databases and compare run/score and
  completed-experiment evidence without rerunning workers.
- [x] Obtain an independent review, address material findings, and retain a draft
  branch/PR without merging or deploying.

The focused command uses unittest discovery for the existing four workflow modules
plus `test_laboratory_calibration.py`, requires a nonzero test count, zero failures
and zero skips. This does not claim a complete API/PostgreSQL or browser run.

## Completed verification

The initial implementation passed 71 focused checks and both practice scripts.
Reconciliation onto `f43df38` passed **77 focused checks, zero skips**, and both
practice scripts on clean commit `e1c9c9bde5247faddb4cfad84fae3e8b335df6ee`.
The workflow source-boundary audit, Python syntax, CSV shape/unique IDs and
whitespace checks passed. Independent review found no material issues, including
a targeted follow-up on the new parent's transactions and budget handling.
That follow-up exercised five additional temporary version 2 failure/interrupt
cases without adding them to the focused-suite count. Publishing this work as a
draft does not qualify broader application integration, calibration quality,
clinical performance, merge or deployment.
