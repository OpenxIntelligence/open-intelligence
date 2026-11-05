# Implementation status

Observed 2026-11-05. This is the current execution index for the founder's
post-audit mandate; existing backlog `docs/EXECUTION_BACKLOG.csv` retains work
package ownership. Historical PR receipts describe their exact revisions only.

| Deliverable | Status | Evidence and next gate |
|---|---|---|
| Repository/main/audit reconciliation | Implemented | Main inspected at f188aec; #481 already merged; current source and all six named donor PRs inspected |
| H1 EHR/laboratory/strict-anchor consolidation | In progress | Candidate preserves complete #536/#537/#540/#539 histories; strict-anchor regression and compatibility checks pass; full exact-head hosted acceptance and human merge remain open |
| PostgreSQL migration graph | Implemented | Published EHR/laboratory 0019 siblings join at 0020, then 0021 freshness and additive 0022 scope correction; no parent migration rewritten; populated hosted acceptance required |
| Current synthetic source custody | Tested on prior accepted revisions | Original text/PDF, manual passages, constrained DICOM, FHIR laboratory custody, source versions, saved questions, reports and tasks retained; combined candidate must rerun recovery/browser acceptance |
| Source-reported cancer episode attribution | Implemented | Existing v2 parser, exact source-line validation, World Model context and Journey grouping; no clinically reconciled episode master |
| Typed oncology episode master and relationships | Not started | Extend existing source evidence with append-only reconciliation and reviewed associations; see clinical model and Phase 1 plan |
| Conditions/medication/allergy/observation reconciliation | Not started | No complete H1 typed record; reference implementations are not migration acceptance |
| Pathology/biomarker extraction and authorized promotion | Not started | Deterministic baseline, exact spans, absence states and independent adjudication required |
| Chronology and staging | Not started | Source dates exist; episode-aware reviewed chronology and versioned staging content remain work |
| Clinical AI copilot | Not started | Existing bounded research/model adapters do not establish a qualified H1 clinical copilot |
| General FHIR/mCODE and terminology validation | Not started | Bounded synthetic laboratory support is implemented; profile validation, reconciliation, terminology rights/versioning and round trip remain open |
| Treatment management | Not started | Plans/orders/administration/dose rules and reviewed interfaces remain work |
| PACS/image interpretation/lesion response | Not started | Existing original custody is preserved; these clinical functions are separate |
| Tumor board/trial criteria/registry | Not started | Existing research adapters are not clinical eligibility or registrar acceptance |
| Reproducible patient bioinformatics/discovery workflows | Not started | Preserve research probes as research; pinned containers/references and independent validation remain work |
| Production identity, consent and clinical attestation | Not started | Current opt-in fixture credentials are synthetic access controls |
| Independent clinical validation | Blocked | Requires authorized independent clinical adjudication and an accepted protocol; software checks do not satisfy it |
| Production release | Blocked | Human release, operations, security, rights and clinical acceptance remain prerequisites |

## Named audit inputs

| PR | Disposition at inspection | Reuse decision |
|---|---|---|
| #481 | Merged, merge 62e218e | Already in main; no replay |
| #301 | Open draft, 611b86e | Shared encounter lifecycle/provenance; current #535/#537 adaptation retained. Extra note-kind/facility/department changes are not silently imported; check SQLite upgrade and request identity compatibility before separate reuse |
| #141 | Open draft, 429faf8 | Provider-neutral bounded model execution stays a research/reference contribution until an H1 task boundary and approved egress policy exist |
| #427 | Merged into a stacked branch, a106bfa | Compare existing FHIR kernel/metadata owner; no second FHIR clinical database or broad conformance claim |
| #476 | Open draft, 4f1c613 | Preserve local runner and separate public gold scorer as research; do not connect to clinical writes |
| #466 | Open draft, fbc26cb | Preserve extraction qualification experiments and original-byte/layout evidence; a completed measurement is not extraction accuracy |
| #152 | Open draft, conflicts, 4c6c21f | Historical composition evidence; no wholesale integration over newer main |

## Current increment

Strict text/FHIR source identity is now composed with encounter notes and the
database citation-freshness repair. The existing source, patient, question,
evidence, note, event and receipt owners remain canonical. No new dependencies,
patient database, clinical status promotion or external model execution is added.

For verification commands and limits, use `RELEASE_ACCEPTANCE.md` and the draft
candidate's exact-head CI. The next concrete engineering increment is the
episode identity/source-association save/read/amend path in
`MASTER_EXECUTION_PLAN.md`, after consolidation acceptance. Do not mark Phase 0
accepted while PostgreSQL, browser or restore gates are incomplete.

## Diagnostics and shared infrastructure, draft #546

The November 4 audit observed main at `a5a5482f` and assessed #481 as a draft. #481 subsequently merged. This increment starts from the repaired [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542) at `6c98111460df07412766624407199f3abcb6b24a`, which already joins the encounter/note, laboratory citation and strict anchor work. During this increment accepted main advanced to [aad241e5](https://github.com/OpenxIntelligence/open-intelligence/commit/aad241e5cce9a1bcff3e431d63cecd16e948d731) with deterministic reference-layer K checks from #538. Those checks and the proposed H1 source-brief worker in #529 have separate integration and validation status.

| Work | Candidate behavior | Scope and independent evidence |
|---|---|---|
| Lab intake and discovery | Accepts a final laboratory DiagnosticReport with the existing category or the exact v2-0074 service codes LAB, CH and HM. The underlying Observation must still satisfy the numeric/explicit-absence profile and independent patient/specimen binding. Journey filters by exact LOINC, report/specimen and result status, with 25 results per page. | Source-reported quantities and absence reasons, exact original and questions in one case. Other result types and general FHIR conformance remain open. [Parser](../../apps/api/src/oi_api/laboratory_fhir_r4.py), [browser](../../apps/web/src/laboratory-result-browser.tsx). |
| Imaging custody and navigation | Additive revision 0023 admits classic MR alongside CT under the existing size/pixel limits; populated MR custody blocks downgrade. Canonical source import checks ambiguity across images in a case. The report index verifies linked bytes and metadata before disclosure. Records groups originals by their study and series under the selected report. | Reuses bounded index integrity from [#423](https://github.com/OpenxIntelligence/open-intelligence/pull/423). Separately proposed CT pixel preview [#514](https://github.com/OpenxIntelligence/open-intelligence/pull/514), archive qualification, clinical viewing and lesion/response assessment remain separate. |
| Dependency evidence | Reuses the frontend CycloneDX gate, tests and workflow from [#545 at b91e7b9c](https://github.com/OpenxIntelligence/open-intelligence/commit/b91e7b9cd05cfa0d954745289b3ed737330d6e40). | Python wheels and installed npm packages have scoped inventories. Whole installation, commercial redistribution, all data/model terms and independent vulnerability disposition remain release work. |
| Parallel proposals | [#543](https://github.com/OpenxIntelligence/open-intelligence/pull/543) command admission, [#544](https://github.com/OpenxIntelligence/open-intelligence/pull/544) visit/note UI, [#547](https://github.com/OpenxIntelligence/open-intelligence/pull/547) purpose-bound acquisition and [#548](https://github.com/OpenxIntelligence/open-intelligence/pull/548) episode disagreements have distinct owners. | Compare against the eventual integration head and retain verified donor history. No capability is credited to this branch from its PR title. |

The exact proposed-head workflows and changes are tracked on [#546](https://github.com/OpenxIntelligence/open-intelligence/pull/546). Clinical use, institutional consent/authentication, broad LIS/PACS support and production release are outstanding.
