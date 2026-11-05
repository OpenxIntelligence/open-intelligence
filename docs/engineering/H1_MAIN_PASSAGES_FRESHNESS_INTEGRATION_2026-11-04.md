# Open Intelligence — H1 combined patient-journey candidate
Date: 2026-11-04
Status: DRAFT. New combined tree is unverified at creation; not approved to merge, deploy, or process real patients.

## Exact frozen Git sources
- Accepted main: `31509a6b83949f974e25b6913a6e30fc968be939`
- H1 document/image base (#381): `924008266d741b2494df41112e2da446b526f920`
- First parent: main + H1 patient workspace (#405), `0dbbb1a70bf831ea14185a2d4a58e4db5c37f35d`.
- Second parent: canonical questions + immutable text/PDF passage sets and report v3 (#410), `877dbbfc34a605e6a6f4be896d3b31922107a529`.
- Third parent: model-context freshness fix (#397), `41e0498bd5590b49cb0744c5cec547e514179135`.

## Source merge
All 37 files changed by #410 were compared against #381's exact Git blob IDs and found unchanged in #405: they may be copied losslessly, retaining file modes. The two #397 files were likewise unchanged from main in #405 and can be copied losslessly. Every other #405 file is retained; this decision document is the only additional file. All three histories are parents of the new candidate commit. The target source owners remain first-party; no parallel EHR, report or review ledger is created.

## Product journey being tested
Fictional text/PDF original → immutable user-selected quote (not source-authored or clinically reviewed) → canonical source-linked question → versioned passage-set context → governed evidence/report with frozen bytes → human Review → assigned follow-through → correction/amendment and explicit historical reassessment. Image archive and independent read/export rights must remain intact.

Reference-model freshness is distinct: its model prompt sees case-wide assertions, so final claim citations cannot prove independence from an amended/new source. Source import must invalidate affected case model runs without requiring an independent human snapshot. Human-authored snapshots stay source-specific.

## Mandatory acceptance on the **combined** tree
1. Alembic single joined head through `0013_document_image_convergence` and `0014_question_passages` → `0015_manual_report_context`, with populated migration/restart/restore checks.
2. Full PostgreSQL/FastAPI/API suite and six actual recovery probes. Verify exact original bytes, page, passage, annotation revision, question/report/review and authorization lineage, no unexplained skips or failures.
3. Full React tests, 13 dependency-rights controls, TypeScript/Vite production build, real PostgreSQL/FastAPI/Chromium journey and negative authority/retry/race cases.
4. Full accepted-main Python/HTTP reference tests, source-reader Node tests, browser journeys and five OI-009 regressions.
5. Pin exact head/tree/run numbers, report any failures/cancellations, and require independent clinical-boundary, rights, source-owner and human release/merge review. **Individual parent CI successes are not combined proof.**

Synthetic data only. No PHI, verified clinician identity/consent, AI clinical execution, recommendations, real orders or deployment. No new dependency/vendor/model is introduced by this composition.
