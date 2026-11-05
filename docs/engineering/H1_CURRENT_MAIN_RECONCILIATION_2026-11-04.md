# H1 current-main reconciliation — 4 November 2026

Status: **source-composed draft; exact-head hosted acceptance pending.** This is an engineering reconciliation receipt, not a clinical, production, PHI, deployment, or merge authorization.

## Frozen source identities

- Accepted current main at reconciliation start: `a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709` — merged #390 evidence/follow-through/current-main line.
- Fully verified combined H1 candidate: #413 at `e3259bb2986206e4a7edf8bc3a29546471077beb`.
- Common comparison base used for shared-path three-way merging: `f200dd107871d89703267ee0d1a14b2d1ca64d36`.
- Working branch: `integration/h1-current-main-reconciled-20261104`.
- The obsolete #401 path targeted the older #381-only candidate and was closed without merge. Draft #458 is the conflict-discovery PR for main→#413 and is superseded by this resolved branch once this branch is published.

## Tree inventory

#413 is a strict path superset of the frozen main:
- 145 candidate-only blob paths were added unchanged on top of main.
- 83 paths existed on both sides with different bytes.
- 81 of those 83 had a common file at the frozen merge base and were handled with bounded three-way comparison.
- Two files were independently added on both sides and required explicit owner decisions.

No main-only blob path was missing from #413, so no accepted-main file needed to be invented or reconstructed.

## Runtime/source-owner decisions

### Three-way merged

The following owner families were merged by applying only #413's delta from the common base onto current-main bytes, retaining already-present main changes and refusing ambiguous repeated hunks:

- H1 API access/app/authored-evidence/contracts/evidence-report/patient/request-limit/source owners.
- React evidence, continuity, registry, Review and source-reading owners.
- API packaging, dependency locks/notices and dependency inventory.
- PostgreSQL migration, evidence, review, follow-through, registry and authority regressions.
- Compose registry/source/review/follow-through/evidence recovery tools.
- H1 API/web/synthetic/UI-glance workflow changes.
- React regression and Chromium helper changes, including exact retries, draft retention, case boundaries and manual-passage/image continuity.
- Selected evidence/product/UX documentation that merged without historical status collision.

Repeated-line ambiguities in three browser helpers were resolved only with surrounding-base context; no assertion or negative control was removed.

### Source-specific owner import

`src/open_intelligence/store.py` did not use the broad #413 delta. It imports only the verified OI-009 fix from #397 head `41e0498bd5590b49cb0744c5cec547e514179135` against its own accepted-main parent `31509a6b83949f974e25b6913a6e30fc968be939`: new/amended source invalidates all current live/replay model investigations in the exact case while preserving source-specific human snapshots and original history. The matching `tests/test_investigation.py` delta is retained.

### Explicit H1-wins files

- `src/open_intelligence/document_intake.py`: preserve #405/#413's verified media-aware text/PDF intake and provenance superset. It retains the accepted text/manual-line flow while adding PDF extraction/rendition, immutable correction and exact page/citation provenance.
- `tests/test_case_switch_guards.py`: preserve the #405/#413 strict superset; current main has no lines absent from this candidate and the H1 version adds the verified 14-field guard/clear and post-submit sensitive-field regressions.

### Explicit current-main-wins files

- `web/app.js`: current main is a strict behavioral superset of the #413 copy for the compared divergence and adds same-case selection readiness preservation.
- `tests/patient_mission_browser_journey.py`: current main is a strict superset and adds explicit `readyCase()` workspace-readiness gating.
- Historical status-heavy `docs/EXECUTION_BACKLOG.csv`, `docs/project-state/INCOMPLETE_FEATURES.md`, `docs/project-state/INTEGRATION_INVENTORY.md`, and `docs/project-state/PROJECT_STATE.md`: keep current-main narratives rather than mechanically interleaving stale status receipts. This reconciliation document records the new integration evidence instead.

## Canonical H1 additions retained

The reconciliation retains #413's H1-only owners, including:
- reviewed text/PDF originals and immutable human-selected passage history;
- source images, archive/socket custody and DICOM integrity;
- canonical manual passage context on existing source-linked questions;
- report renderer/provenance and reassessment behavior;
- synthetic FHIR R4 laboratory preview and no-write/authorization tests;
- migration lineages through the two published 0012 heads → `0013_document_image_convergence` → `0014_question_passages` → `0015_manual_report_context`;
- all related recovery, rights and browser regressions.

Human-selected passages remain user-attributed/unreviewed context, not source-authored assertions or clinical approvals.

## Required exact-head acceptance

Before any merge/release decision:

1. Verify the final two-parent commit/tree and that frozen main + #413 are both ancestors.
2. Run H1 API/PostgreSQL full migration/contracts with no unexplained required skips.
3. Run all six actual restart/API restart/pg_dump/pg_restore/revocation recovery probes.
4. Run full H1 React suite, 13 rights controls, TypeScript/Vite build and actual PostgreSQL/FastAPI/Chromium patient journey.
5. Run current-main synthetic Python/HTTP, JavaScript and Chromium reference journeys including OI-009 and case-switch regression.
6. Verify migration graph has one current head and all published historical revisions remain reachable/unchanged.
7. Review wrong-patient/case/source, revocation, stale/late response, manual-vs-image ownership, exact retry, historical report bytes and restored-state denial.
8. Record run IDs, artifacts, failures, source SHA/tree and independent review. Do not inherit parent-green results onto the combined tree.

Synthetic independently fictional inputs only. No real PHI, clinical validation, autonomous diagnosis/treatment, external PACS qualification, unlicensed content, real identity/consent, production deployment or main merge is authorized by this receipt.
