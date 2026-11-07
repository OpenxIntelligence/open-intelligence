# Open Intelligence mandate reconciliation — 4 November 2026

This directory is an evidence view for the existing audit PR #459, not a new backlog, replacement architecture or adoption register. The existing execution backlog, first-principles plan, source/identity/evidence owners and rights inventories retain precedence. Open Intelligence remains separate from DevX and Meridian; H1 remains Python/FastAPI/PostgreSQL and React/Vite/TypeScript, with vector search and Next.js excluded.

## Baseline and engineering result

- Observed main: `a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709`. Main includes H1 foundations as well as the reference SQLite application; older SQLite-only summaries are stale.
- Draft #463: `eb944c0ab88e38630404b920c5aadcc445658125`. All five applicable workflows passed. The API run establishes 704 API/PostgreSQL tests, 765 reference tests and six recovery/revocation probes; the web run establishes 483 client tests, 13 rights controls, build and real-browser acceptance. All 647 archived source blobs matched its immutable GitHub tree.
- Draft #469: bounded repair of native FHIR source custody at `8ff6e9e5a0389a1142ca479a6705c599cbda88e7`. The repair fixes nullable-side SQL locking, duplicate route/contracts, a missing original-hash receipt, old projection interception signatures and a historical migration assertion. Authorization expectations remain in place; no dependency was added. All 652 archived source blobs matched its immutable tree.

### Verified FHIR repair — exact source head

Both applicable workflows completed **SUCCESS** at `8ff6e9e5a0389a1142ca479a6705c599cbda88e7`:

| Acceptance | Result | Evidence |
| --- | --- | --- |
| API/PostgreSQL contracts and migrations | 709 passed; no skips reported | [API run 41883746990](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41883746990) |
| Inherited Python/HTTP regression | 765 passed; no skips reported | Same API run; full job log inspected |
| Client contracts | 484 passed; zero failures/skips | [Browser run 41883747065](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41883747065) |
| Frontend rights controls | 13 passed; 18 installed / 2 optional uninspected | Matching browser artifact; optional entries are not cleared |
| Build and real browser journey | Passed | TypeScript/Vite and actual PostgreSQL/FastAPI/Chromium; inherited patient/source/document/image/question/evidence/review/follow-through flows |
| Seven recovery stages | Passed | Patient, source, FHIR laboratory, image, review, follow-through and evidence; restart, pg_dump/pg_restore and revocation checks |

The FHIR-specific recovery driver passed exact raw JSON custody, immutable typed observations, explicit amendment, API/database restart, full backup/restore, exact retry and restored binding revocation. This is backend/FHIR custody evidence; no dedicated new FHIR import UI journey or clinical interpretation is claimed.

The 7,792,902-byte browser archive independently hashes to `a3356bdd8f19f904928de90e220a691e9c650fddfc84b0f40c87a215033ef026`. Its commit receipt matches the source head and all **652 archived source blobs** match GitHub's immutable tree, with no missing/mismatched blobs. The build retains a non-failing chunk-size warning. Draft status, migration convergence with sibling work, independent review and the merge decision remain separate.



The parent API artifact and child browser artifact were downloaded and independently hashed. See `Open_Intelligence_Verification_Receipt.json` for immutable source/run/artifact evidence. No synthetic result establishes clinical validation, production identity/consent, complete FHIR conformance, commercial distribution clearance, merge approval or deployment.

## Machine-readable views

| File | Scope | Limit |
| --- | --- | --- |
| `Open_Intelligence_30_Domain_Matrix.csv` | 30 founding-mandate domains, observed implementation, remaining work and existing owners | Domain-level status does not mean complete test coverage |
| `Open_Intelligence_Technology_Catalog.csv` / `.json` | 35 official repository/license inspections, exact license blob SHA, maintenance signal and recommendation | Default-branch evidence is not release, transitive, model, data or service qualification |
| `Open_Intelligence_Validation_Scenarios.csv` | 20 required failure scenarios mapped to existing evidence and remaining acceptance | Operational review is not a signed clinical approval workflow |
| `Open_Intelligence_Observed_Runtime_BOM.csv` / `.json` | 26 exact Python wheel entries from the #463 canonical inventory | Does not replace native/WASM/container/content/model/service BOMs |
| `Open_Intelligence_Verification_Receipt.json` | Immutable heads, run IDs, downloaded artifact hashes and source-blob comparison | Only the stated software scope is verified |

The current 30-domain judgment is 17 partial, 12 planned and one blocked for guideline-content rights. These are categorical assessments of the full platform vision, not a completion percentage. Preserve the existing 70-area technical crosswalk as the more detailed architecture view.

## Decisions and next acceptance

1. Reconcile verified #469 and #463 against any newly moved main/PR heads. The separate #457/#462 migration lineage requires an explicit populated upgrade/merge plan; do not rewrite published migrations.
2. Converge preparation packet, second-opinion overview, navigation and accessibility work (#447/#449/#450/#461/#468) into one patient workflow with source-linked evidence and amended-source reassessment.
3. Extend internal follow-through to distinct request, delivery, acknowledgement and confirmed-outcome states. An internal task is not proof of an external referral, booking or benefit award.
4. Qualify production identity, consent/delegation, governance and recovery under OI-012/013 before real-data use. No production identity provider or legal/clinical partner is established by this report.
5. Benchmark extraction and model execution only after representative held-out cases, task-specific critical errors and safe failure/cancellation behavior are defined. Existing small synthetic baselines do not establish clinical accuracy.
6. Preserve the adopted runtime. Evaluate identity, BOM and telemetry mechanics for concrete gaps; hold vector frameworks, model fleets and additional services until they earn their operational cost and have exact-purpose rights.

Patient-journey research covers advanced fragmented care, rare-cancer expertise, molecular navigation, rural/local continuity, and practical financial/disability support. It separates public documented actions from product inferences. Narratives are not clinical evidence, representative outcome samples or evaluation fixtures. Independently authored synthetic data remains the engineering boundary.

The [complete A–O assessment](https://chatgpt.com/library?file_id=libfile_0f39563dbccc8191bf3b6179b990c4ef&account_id=personal) covers the product audit, vision comparison, competitors, five patient archetypes, all 30 domains, 35 technology candidates, infrastructure, separate BOM/rights categories, first-party contracts, AI governance, gaps, roadmap and completion criteria. Access follows the assessment file's existing account permissions.

Existing owners: [execution backlog](../../EXECUTION_BACKLOG.csv), [first-principles plan](../../FIRST_PRINCIPLES_PLAN.md), [vision/reality matrix](../VISION_TO_REALITY_MATRIX_2026-11-04.md), [70-area crosswalk](../CAPABILITY_ARCHITECTURE_CROSSWALK_2026-11-04.csv), [patient-journey crosswalk](../../research/PATIENT_JOURNEY_CAPABILITY_CROSSWALK_2026-11-03.md).
