# Post-audit engineering plan

Checkpoint of 5 November 2026. Use the [first-principles plan](../FIRST_PRINCIPLES_PLAN.md) for architecture and [execution backlog](../EXECUTION_BACKLOG.csv) for work ownership. This directory records implementation and acceptance of the November mandate. All scenarios use independently authored fictional patients.

## Phase 0 — consolidate the accepted H1 application

Use main `f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9` as the reproducible starting revision. The [decision register](ARCHITECTURE_DECISIONS.md) accounts for #481, its successors and the six named donors. Freeze a new base whenever main advances. Do not apply a historical stack as a unit.

| Order | Files and work | Completion evidence |
|---|---|---|
| 1 | Inspect `apps/api/migrations/versions/`, `apps/api/src/oi_api/app.py`, `patients.py` in that package and `apps/web/src/main.tsx`. Retain both 0016 branches, the 0017 join and 0018 laboratory questions. | One Alembic head. Preserved originals and source, image, document, question and task owners on the same patient and case. |
| 2 | Repair the disagreement check in `apps/web/src/source-world-model.ts` and show exact quoted statements in `world-model-view.tsx`. Exercise `apps/web/tests/world-model-client.test.mjs`, `apps/api/tests/test_source_world_model.py` and `apps/web/tools/oncology_episode_journey.py`. | A deliberately incomplete group is withheld. Valid groups show every current contributing source and line. Reassigning a finding in an amendment removes the obsolete conflict. |
| 3 | Execute `.github/workflows/h1-api.yml` and `h1-web.yml` on the candidate. Retain evidence for the same head and identify any environment exclusions. | Populated upgrades, real PostgreSQL, HTTP, Chromium, both browser entry points, stop/resume, restore and revocation. See [release acceptance](RELEASE_ACCEPTANCE.md). |
| 4 | Reconcile #536 and its sibling children #537 and #539, plus #540 on #537. Compare their migration parents, readiness predicates, question anchors, immutable citations, and populated restore assertions against current main. Review #529's independent migrations before allocating a new revision. | One reviewed integration head. Every previously published migration retained by identity and content. Exact-head acceptance before merge decision. |

## Phase 1 — typed oncology record

Proposed paths below identify new work. Select the next free migration ID only after Phase 0 reconciliation. Each increment crosses the database, API and working patient surface. Keep the original source projection readable for older records.

| Order | Proposed or existing files | First acceptance case |
|---|---|---|
| 1. Episode identity and source links | Add one migration in `apps/api/migrations/versions/` and an episode service in `apps/api/src/oi_api/oncology_episodes.py`. Extend the patient router, scoped contracts and `apps/web/src/world-model-view.tsx`. Reuse `sources.py`, `source_integrity.py` and case locking. | Create two independent episodes for one patient, including a historical primary. Attach a source/version/line explicitly. An unassigned suspected metastasis stays unresolved. No conversion of existing EP labels by string equality. |
| 2. Relationships and adjudication | Extend that service and migration chain with versioned relationship claims, review events and idempotent commands. Add `apps/api/tests/test_oncology_episodes.py`, HTTP/PostgreSQL tests and an amended-source browser scenario. | A qualified synthetic reviewer can record a disposition on an exact anchored version. Concurrent amendment, actor change or revocation aborts the command and event together. Repeated commands reproduce the original receipt. |
| 3. Typed conditions, history, medications, allergies and observations | Introduce contracts under the existing patient router for each bounded domain. Extend the record-reading UI and use the existing laboratory reader where appropriate. Add separate review and historical retrieval tests per domain. | Patient-level conditions and medication/allergy histories can span episodes. Context-specific observations retain units, source attribution, status and dates. Unknown and absent items stay distinct. |

Subsequent work follows mandate order: document/pathology extraction, episode chronology/staging, clinical AI, interoperability, treatment management, imaging, tumor board/trials/registry, then reproducible discovery. Each requires its own scoped evidence, rights review and release decision. No later phase is accepted by this checkpoint.
