# FHIR Laboratory Custody Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist strict synthetic FHIR R4 laboratory bundles in canonical source custody and project typed observations longitudinally without clinical interpretation.

**Architecture:** Add immutable dependent FHIR tables under `clinical_source`; keep raw bytes/versioning in `source_versions`. A modality adapter validates/replays/amends atomically, while source integrity and the existing World Model read the dependent rows.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL 16.

**Spec:** `docs/superpowers/specs/2026-11-04-fhir-laboratory-custody-design.md`

## Global Constraints
- No second patient/source ledger.
- Exact source bytes preserved.
- Explicit amendment lineage and exact request-key replay.
- No clinical interpretation or unit conversion.
- Existing H1 authority and recovery boundaries remain mandatory.

## Review Focus
- Same request key with changed bytes must not create a new version.
- Changed report bytes without the exact current predecessor must fail.
- Mid-request grant loss must roll back source, typed rows, command and event.
- Stored typed rows must match reparsing of the immutable original.
- Superseded laboratory versions must remain history while only current observations project.

### Task 1: Forward schema and contracts
- [ ] Add failing migration/head assertions.
- [ ] Add `0016_fhir_laboratory_sources` dependent tables and immutable guards.
- [ ] Advance `SCHEMA_REVISION`.
- [ ] Verify migration and populated downgrade refusal.

### Task 2: Canonical FHIR persistence adapter
- [ ] Add failing HTTP tests for import, replay, amendment and revocation.
- [ ] Implement `PostgresLaboratoryFHIR.import_bundle(...)`.
- [ ] Store raw bytes only in `source_versions`; dependent rows reference `source_id`.
- [ ] Reuse final authority callback and prepare-response-before-commit pattern.

### Task 3: Source integrity and exact original
- [ ] Add regression proving generic source original returns byte-identical FHIR JSON.
- [ ] Validate FHIR source rows by reparsing raw bytes and comparing dependent metadata/observations.
- [ ] Keep text-report validation unchanged.

### Task 4: World Model longitudinal projection
- [ ] Add failing empty and populated typed-lab projection assertions.
- [ ] Add `laboratory_observations`, `laboratory_timeline`, and summary count.
- [ ] Include current typed labs in the World Model fingerprint; never infer clinical meaning.

### Task 5: Exact-head verification
- [ ] Run full PostgreSQL/API suite with no relevant skips.
- [ ] Run all six recovery probes.
- [ ] Run React/rights/build/Chromium and reference UI suites.
- [ ] Preserve exact-head artifacts and record synthetic-only limits.
