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
- [x] Verify the new actual-database regressions on the unchanged runtime in hosted CI; keep the failed baseline.

## Task 2 — close the interval in the existing owner

- [x] Add final checks in `apps/api/src/oi_api/images.py` after image audit append; keep the preceding check and shared source helper unchanged.
- [x] Update the existing ordering assertions to include the additional final check and run the complete focused module.
- [x] Preserve all owner models, schemas, permissions, archived originals and package locks.

## Task 3 — verify and deliver

- [x] Independently review the complete bounded delta.
- [x] Publish a draft child of #370, using exact source-tree identity and a leased update.
- [ ] Require passing full API/PostgreSQL, reference, browser and six recovery gates at the final head; inspect retained evidence.
- [ ] Append the actual result and limits to the existing continuity and canonical project records.

## Observed local baseline

The code-only pydicom runtime already available from the earlier image owner was
reused read-only: pydicom 3.0.2, FastAPI 0.162.0, pg8000 1.31.6 and Pydantic
2.14.1. The new ordering test ran one method with three failing subcases on the
unchanged owner. This establishes the response-ordering defect, not PostgreSQL
rollback. Local socket creation is denied; PostgreSQL and Docker are unavailable.
The actual network/database evidence must come from hosted acceptance.

## Local repair and initial independent review

The complete ordering module runs six methods. Before the repair, its five
existing methods passed and the new method failed for import, index and original
operations because no denial was raised. With the three image-owned tail checks,
all six methods pass. The known personal-case acquisition entrypoint scanner also
passes; that scanner is not an exhaustive historical data audit.

An independent reviewer confirmed that each tail check is inside the owning
transaction and before return. New original imports and amendment links can roll
back their writes and event together; index and original reads can roll back their
receipt. Identical imports append no event and retain the existing fresh check.
Whole-contribution review also inspected the five new actual-database tests,
their inherited fixtures, and the documentation. It found no blocking issue.
The hooks run the real event append before changing the fictional credential;
status and durable-state equality are checked together. Only four local methods
and one joined-history socket method are collected. Syntax/import/collection
passed in the existing local runtime; those checks do not execute PostgreSQL.

## Published tests-first checkpoint

Draft [#376](https://github.com/OpenxIntelligence/open-intelligence/pull/376)
starts with `4bf76a2e3dc822269e72124443f4d2986d5f7323`, tree
`bf29012b306ace6633312d0111d5e9632362d361`. That tree matches the staged local
tree and contains only tests/spec/plan changes over #370; production code is
unchanged. The [API baseline](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41707309666)
and [web baseline](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41707309729)
are retained separately from the subsequent production repair.

The completed API baseline executed 621 methods in 464.730 seconds and failed
with exactly 13 assertion failures, all in the new regressions: ten actual
PostgreSQL/HTTP scenarios plus the three ordering subcases. There were no test
errors or skipped test methods. Each database scenario observed a successful
response and changed durable rows, rather than the required denial and unchanged
custody/history. Import and relink returned `(201, False)`; index, local original
and the actual Unix-socket original returned `(200, False)` when compared as
`(HTTP status, durable rows unchanged)`. Required denials were 404 for lost
grants/context, 401 for expired/removed credentials and 503 for missing authority
provider. The remaining inherited contract tests passed. Later recovery steps
were skipped because this intentionally failing baseline stopped the job.

The baseline web workflow passed. Its result is not a substitute for rerunning
both workflows with the production repair. The five actual-database test methods
were byte-identical at the first repaired candidate,
`319e68b1445cb4547db56bb82d173ce47f88274b`; only the two successful ordering
expectations changed to include the new check. A later test-only error-contract
correction is recorded below.

## Initial repaired candidate and test-expectation correction

The [first repaired API run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41709538488/job/126173678131)
executed 621 methods in 714.711 seconds with four assertion failures, no errors
and no skipped test methods. The status/unchanged-rows checks passed for all ten
new database scenarios. Four then failed an incorrect exact-detail expectation:
missing import, patient, patient-read or image-original grants return the existing
`{"detail":"Patient unavailable"}` envelope through `records_authorized`.
The tests had assumed the `Image unavailable` envelope used for actor,
organization and purpose drift. The three ordering subcases passed.

The test-only correction supplies the actual grant-denial envelope to the helper
and socket assertion. It retains every status, unchanged-row, no-store,
no-receipt, no-sensitive-content and positive-retry assertion. The production
fix remains unchanged. The failing baseline stopped at the earlier status/row
assertion, so this later expected-detail correction does not remove the original
defect detector. Retry assertions after the four failing checks, reference
regressions, and all recovery gates were not completed by that failed run and
must pass at the corrected final head.

The first repaired [web run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41709538769)
passed 297 client tests, build and actual PostgreSQL/FastAPI/Chromium acceptance.
Artifact 13266047502 was downloaded and its SHA-256 recomputed as
`0b428ab36b8cffbdf8253f6f45dcd924ae96d4a7c10ffc32e6a0759e999da87b`.
Its commit marker and all 465 source blobs matched that candidate. It is retained
as an earlier checkpoint; the corrected final head requires its own verification.

The final tested commit, completed workflow results, artifact hashes and
canonical readback belong in the PR verification receipt and the existing
Engineering Roadmap, Integration Contracts and Engineering Progress records.
Parent or tests-first results must never substitute for final-head verification.
