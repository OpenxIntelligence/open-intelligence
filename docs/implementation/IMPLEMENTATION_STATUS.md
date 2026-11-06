# Implementation status

Observed 2026-11-05. This is the current execution index for the founder's
post-audit mandate; existing backlog `docs/EXECUTION_BACKLOG.csv` retains work
package ownership. Historical PR receipts describe their exact revisions only.

## Current construction candidate

Accepted main is now `1595dac65a26906ca2cf618dee819d7b7c95a80d` (#579).
This continuation joins its complete history with #570 at
`6e512a9d27f6c50cf0677c6e8d3da46419f4dcf1`, retaining #542/#556, encounter notes,
laboratory citations, disagreement grouping and durable source-linked episode
drafts in one H1 candidate. Published migrations are unchanged; head is
`0023_episode_drafts`. Separate event/operations and diagnostic branches still
need their own explicit convergence; this is not whole-core completion.

The five verification workflows now pin and check the proposed source revision.
A four-test real-Git regression suite rejects changed commits (even identical
trees), staged/unstaged modifications and invalid revision identifiers.
Reference main's reported PDF failures reproduce with unqualified pypdf 6.10.0;
the locked 6.21.4 runtime passes all 17 PDF tests and 1,043 baseline reference tests.
Local combined client/build/rights pass; hosted combined database/browser/recovery
acceptance remains required. See RELEASE_ACCEPTANCE.md for exact results.

The older rows below retain checkpoint evidence; later statements above govern
current revision and migration identity. No clinical qualification is implied.

The first Phase 1 candidate extends verified [#556](https://github.com/OpenxIntelligence/open-intelligence/pull/556) at `92257c2c`, which carried the five-file disagreement repair onto [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542). The candidate adds migration `0023_episode_drafts` on that line. Reconcile its named revision with the separate ownership/event integration branches before merging. The draft PR records hosted results for its own head.

| Deliverable | Status | Evidence and next gate |
|---|---|---|
| Repository/main/audit reconciliation | Implemented | Main inspected at f188aec; #481 already merged; current source and all six named donor PRs inspected |
| H1 EHR/laboratory/strict-anchor consolidation | In progress | Candidate preserves complete #536/#537/#540/#539 histories; strict-anchor regression and compatibility checks pass; full exact-head hosted acceptance and human merge remain open |
| PostgreSQL migration graph | Implemented | Published EHR/laboratory 0019 siblings join at 0020, then 0021 freshness and additive 0022 scope correction; no parent migration rewritten; populated hosted acceptance required |
| Current synthetic source custody | Tested on prior accepted revisions | Original text/PDF, manual passages, constrained DICOM, FHIR laboratory custody, source versions, saved questions, reports and tasks retained; combined candidate must rerun recovery/browser acceptance |
| Source-reported cancer episode attribution | Implemented | Existing v2 parser, exact source-line validation, World Model context and Journey grouping; no clinically reconciled episode master |
| Typed oncology episodes and relationships | In progress | Journey can explicitly save and reopen a draft from a reported primary line, with immutable identity and whole-snapshot reassessment. Adding a second source to an existing episode, adjudicating competing links and clinical confirmation remain open. |
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

Accepted main advanced during verification from f188aec to
`aad241e5cce9a1bcff3e431d63cecd16e948d731` (#538). The latest candidate preserves
that complete main history and its deterministic reference claim checks as a
real merge parent. The reference suite grows from 853 to 919 methods; final
combined tests must run on the reconciled head. These lexical/deterministic
checks are not general clinical entailment or an H1 model-execution feature.

Strict text/FHIR source identity is now composed with encounter notes and the
database citation-freshness repair. The existing source, patient, question,
evidence, note, event and receipt owners remain canonical. No new dependencies,
patient database, clinical status promotion or external model execution is added.

For verification commands and limits, use `RELEASE_ACCEPTANCE.md` and the draft
candidate's exact-head CI. The next concrete engineering increment is the
episode identity/source-association save/read/amend path in
`MASTER_EXECUTION_PLAN.md`, after consolidation acceptance. Do not mark Phase 0
accepted while PostgreSQL, browser or restore gates are incomplete.
