# Image Audit Final Authority Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the owner change and independently review the whole delta.

**Goal:** Deny image responses when authority changes during their audit append.
**Architecture:** Preserve the canonical image/source transaction and existing authority callback; add a final image-owned check after event persistence.
**Tech Stack:** Existing Python/FastAPI/PostgreSQL; no new dependencies.
**Spec:** `docs/superpowers/specs/2026-11-03-image-audit-final-authority.md`.

## Global constraints

Base #370 at `cc624fe3b258e39a3b833a0053ed9e9f2ced57be`. Synthetic only. No
shared source helper, schema, permission, dependency or frontend changes. Preserve
existing before-audit checks and exact response encoding. Draft contribution;
no merge, deployment, real-patient processing or clinical approval.

## Review focus

- Failed final authority must roll back new originals, amendment links and receipts.
- Idempotent imports without a new event must retain their existing fresh check.
- Separate image-read/import/original grants must not substitute for each other.
- Archive success must not bypass the same final transaction boundary.
- Credential provider failures and context changes must expose no prepared data.

## Task 1 — reproduce and cover the boundary

- [x] Add the focused existing-fixture regression in `apps/api/tests/test_image_preparation.py`.
- [x] Run it on unchanged production code; all three import/index/original subcases fail because denial is not raised.
- [x] Add `apps/api/tests/test_image_audit_authority.py` with real HTTP/PostgreSQL audit-tail changes, rollback and authorized retry; collect only its new methods.
- [ ] Verify the new actual-database regressions on the unchanged runtime in hosted CI; keep the failed baseline.

## Task 2 — close the interval in the existing owner

- [ ] Add final checks in `apps/api/src/oi_api/images.py` after image audit append; keep the preceding check and shared source helper unchanged.
- [ ] Update the existing ordering assertions to include the additional final check and run the complete focused module.
- [ ] Preserve all owner models, schemas, permissions, archived originals and package locks.

## Task 3 — verify and deliver

- [ ] Independently review the complete bounded delta.
- [ ] Publish a draft child of #370, using exact source-tree identity and a leased update.
- [ ] Require passing full API/PostgreSQL, reference, browser and six recovery gates at the final head; inspect retained evidence.
- [ ] Append the actual result and limits to the existing continuity and canonical project records.

## Observed local baseline

The code-only pydicom runtime already available from the earlier image owner was
reused read-only: pydicom 3.0.2, FastAPI 0.162.0, pg8000 1.31.6 and Pydantic
2.14.1. The new ordering test ran one method with three failing subcases on the
unchanged owner. This establishes the response-ordering defect, not PostgreSQL
rollback. Local socket creation is denied; PostgreSQL and Docker are unavailable.
The actual network/database evidence must come from hosted acceptance.
