# Implementation status

Observed 2026-11-05. This is the current execution index for the founder's
post-audit mandate; existing backlog `docs/EXECUTION_BACKLOG.csv` retains work
package ownership. Historical PR receipts describe their exact revisions only.

| Deliverable | Status | Evidence and next gate |
|---|---|---|
| Repository/main/audit reconciliation | Implemented | Main inspected at f188aec; #481 already merged; current source and all six named donor PRs inspected |
| H1 EHR/laboratory/strict-anchor consolidation | In progress | Candidate preserves complete #536/#537/#540/#539 histories; strict-anchor regression and compatibility checks pass; full exact-head hosted acceptance and human merge remain open |
| PostgreSQL migration graph | Implemented | Published EHR/laboratory 0019 siblings join at 0020, followed by 0021 freshness repair; no parent migration rewritten |
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
