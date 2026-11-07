# Implementation status — 5 November 2026

## Paired episode report reassessment — integration validation pending

The current continuation integrates the existing paired-attribution review owner from #548 and amendment comparison from #566 into the verified episode/worker chart (#601 and #607). A reviewer can preserve two conflicting source-reported episode attributions with a reason, then compare each recorded original with its latest document version. Moved lines follow their original finding key; removed, untyped and unassigned findings stay distinct. Comparison does not resolve the attribution or approve a clinical conclusion.

The integration preserves worker/evidence return receipts alongside paired-source receipts. Their command digests include the appropriate original provenance. No new schema, source registry, model, external service or clinical action is added. Local checks pass 719 client tests, production build and 14 focused API/parser/contract tests. Hosted PostgreSQL, Chromium and restore checks must qualify this combined head; donor checks alone do not.

## Source-linked oncology episode drafts — verified synthetic integration

The integration carries [#570](https://github.com/OpenxIntelligence/open-intelligence/pull/570) from its source-reporting owner onto the clinical worker application from [#567](https://github.com/OpenxIntelligence/open-intelligence/pull/567). An authorized operator in Journey can save two distinct, unreviewed episode IDs from two source-reported primary findings, reopen the original statements and see when an amendment requires reassessment. Independent source-original permission is required to include a superseded quotation. The draft carries no staging or treatment authority.

The published episode-draft migration and the integrated clinical/worker history are both preserved. A subsequent guard checks creation-journal continuity and refuses a direct TRUNCATE that would orphan existing episode identities. Use the actual branch checks to qualify populated upgrades, recovery, correction, concurrent retries and withdrawals. The next clinical construction task is a separately reviewed additional source association on the same durable ID.

[PR #601](https://github.com/OpenxIntelligence/open-intelligence/pull/601), source `e6eed7c721ef5322a800be7022952c1cc3cd3754`, passed 1,017 API/PostgreSQL tests, all seven recovery checks, 136 worker tests, 706 client tests, production build, the real Chromium journey and 927 reference tests. Source-purpose repair, populated episode upgrades, orphan-history rejection and restored episode custody are qualified on that revision. This remains draft, unmerged and synthetic-only.

The direct-original continuation adds an inspection button to each saved episode. It refreshes the source index, verifies the selected version/hash, and opens the exact original under the existing separate source-original permission. Scope changes or dismissal cancel the transition. Seven new client cases and the full 713-test client suite pass locally; actual browser acceptance for this continuation is recorded in its draft PR.

## Durable patient brief and source-event integration

The patient can queue a deterministic brief for a saved source question, leave Investigations, and reopen the latest run after a fresh patient, case, actor, purpose and grant check. An amended source can make a run stale while the patient is away. The patient can inspect that historical status. Opening a result requires a current source context and a separate authorized read. A review return still requires the matching completed brief, assessed evidence report and independent review-queue permission.

[Draft #567](https://github.com/OpenxIntelligence/open-intelligence/pull/567) builds on [#565](https://github.com/OpenxIntelligence/open-intelligence/pull/565) at `703eebf4`, carries [#559](https://github.com/OpenxIntelligence/open-intelligence/pull/559) at `ba76452e` into the same patient workspace, and preserves the command, recovery and verified-build controls from [#555](https://github.com/OpenxIntelligence/open-intelligence/pull/555) at `1b1f31ee`. This historical worker checkpoint used `0026_integrated_core`. The current episode integration requires `0029_episode_history_guard`, joining episode custody with the research-source compatibility repair. No new model, broker or external service is added.

Two [PostgreSQL regressions](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42106387753) reproduced a run being published after the original lease expired during final source auditing, and an exhausted third attempt being reported as idle. The worker now checks the database deadline after recording the source-read audit and before committing the result. An expired operation rolls back its result and receipt together. An authorized retry obtains a new attempt. A restarted worker with a revoked grant cannot claim or disclose a result. The final expired attempt reports failure, and a later invocation can process the next eligible run.

[The draft's checks](https://github.com/OpenxIntelligence/open-intelligence/pull/567/checks) identify the tested revision for the actual worker, API, browser and restore runs. The typed oncology episode/source-association contract is the next clinical construction task after synthetic acceptance. Institutional identity/consent, clinical adjudication and scientific pipeline qualification are separate milestones.

## Historical #552 and #555 foundation record

**What can be exercised:** the merged H1 application supports a fictional patient, immutable originals and amendments, laboratory observations and questions, exact-source reading, reports and follow-through. This **draft integration candidate** adds shared ingress and build verification to the combined encounter/note and laboratory code from #542. Its single schema head, `0023_ehr_lab_ownership_join`, requires both the published clinical ownership guard and the laboratory citation freshness repair. The first-party clinical system, production governance, clinical AI validation, scientific execution and discovery program each have substantial work ahead.

## Build evidence on the integrated core

The [build verification change](https://github.com/OpenxIntelligence/open-intelligence/pull/555) extends [#552](https://github.com/OpenxIntelligence/open-intelligence/pull/552) at `57556e4`. In a reproduced case, the intake accepted a frontend BOM with a substituted archive hash when its adjacent receipt was updated to match. The verifier now compares each installed location, upstream name, resolved archive and SHA-512 with the independent package lock. The draft also adds a [193-project source index](TECHNOLOGY_SOURCE_EVIDENCE.json) to the existing comparison tables. Its PR records the exact source revision and test results.

## Audit reconciliation

| November 4 benchmark | State observed on November 5 | Evidence or next acceptance |
|---|---|---|
| The audit inspected main at `a5a5482`; consolidation #481 was unmerged. | Current inspected [main f188aecc](https://github.com/OpenxIntelligence/open-intelligence/commit/f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9) has 720 tracked files. [#481](https://github.com/OpenxIntelligence/open-intelligence/pull/481) merged. Ordinary text/PDF passages, narrow synthetic DICOM and lab workflows must now be reconciled against main itself. | [Recorded audit and source index](../project-state/oncology-audit-20261104/README.md); [accepted demo history](../engineering/H1_ACCEPTED_DEMO_CONVERGENCE.md). |
| Laboratory FHIR persistence and episode-specific chronology were partial. | [#526](https://github.com/OpenxIntelligence/open-intelligence/pull/526) and [#520](https://github.com/OpenxIntelligence/open-intelligence/pull/520) merged. Main has source-declared episode/role attribution and durable laboratory observation questions at schema 0018. | No master of clinically adjudicated episode, stage or progression is implied. [#541](https://github.com/OpenxIntelligence/open-intelligence/pull/541) separately proposes fuller disagreement inspection. |
| First-party encounters and note versions were on a branch. | [#535](https://github.com/OpenxIntelligence/open-intelligence/pull/535) connects scheduling, progress transitions and immutable draft notes. [#536](https://github.com/OpenxIntelligence/open-intelligence/pull/536), [#537](https://github.com/OpenxIntelligence/open-intelligence/pull/537), [#539](https://github.com/OpenxIntelligence/open-intelligence/pull/539) and [#540](https://github.com/OpenxIntelligence/open-intelligence/pull/540) contribute to the [combined clinical candidate #542](https://github.com/OpenxIntelligence/open-intelligence/pull/542). | This branch builds on #542 at `6c98111460df07412766624407199f3abcb6b24a`. These are candidate capabilities. Routine EHR notes have no clinical attestation or order execution. |
| Composer preflight was deterministic and source-bound. | [#527](https://github.com/OpenxIntelligence/open-intelligence/pull/527) merged provenance enforcement for the reference agent writer. [#529](https://github.com/OpenxIntelligence/open-intelligence/pull/529) proposes durable PostgreSQL execution of a deterministic brief; [#538](https://github.com/OpenxIntelligence/open-intelligence/pull/538) proposes deterministic claim checks. | Neither is integrated into this pinned candidate. During the session #538 merged to [newer main aad241e5](https://github.com/OpenxIntelligence/open-intelligence/commit/aad241e5cce9a1bcff3e431d63cecd16e948d731); #529 remains a separate candidate. The H1 app has no clinically validated model execution. [#524](https://github.com/OpenxIntelligence/open-intelligence/pull/524) is a separate model experiment. |
| Dependency and access controls existed in separate owners. | API wheel/notice and web dependency gates both remain. [#543](https://github.com/OpenxIntelligence/open-intelligence/pull/543) adds the cross-stack verifier and default patient command policy on main. This candidate applies those changes to #542. | Existing source reviews [#127](https://github.com/OpenxIntelligence/open-intelligence/pull/127), [#134](https://github.com/OpenxIntelligence/open-intelligence/pull/134), [#135](https://github.com/OpenxIntelligence/open-intelligence/pull/135) and [#532](https://github.com/OpenxIntelligence/open-intelligence/pull/532) remain traceable research, separate from adopted runtime packages. |

## What this increment establishes

- New patient POST, PUT, PATCH and DELETE operations default to a 16 KiB body limit before downstream parsing. Only named supported POST transports get a larger envelope. A configurable per-process budget refuses excess commands with HTTP 429 and a retry delay. Health/read routes retain their independent behavior.
- Applying the main-based policy unchanged to #542 rejected a valid 20,000-character encounter note (HTTP 413). The fix preserves 242,000 bytes **only** on the note-version POST. On loopback, both UTF-8 and Unicode-escaped maximum-size inputs now reached the existing authentication check. Focused tests also rejected near-match URLs, wrong methods and over-limit chunks.
- The offline build-input generator and the connected web workflow now reconcile the existing API and npm gate outputs. The local inventory identified 26 runtime wheels, a distinct DICOM preparation wheel and 20 npm locations (18 installed, 2 optional and absent). It does not establish image-layer or model/data rights.
- The 14 requested implementation records and three technology studies link domain responsibilities, maintained package inputs and platform-level acceptance gates. Proposed clinical and scientific domains have acceptance conditions rather than delivery credit.

## Verification by revision

| Revision and boundary | Result |
|---|---|
| Baseline `f188aecc` | Locally: 823 reference Python tests, 70 JS checks, 633 React client tests, 13 web rights tests, API wheel gate and frontend build passed. Full local API discovery ran 785 cases and reported 75 environment-denied Unix socket errors and 477 database skips. Exact-main hosted [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42085075497) and [Crossref](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42085075416) passed. |
| Main-based #543, `c84bc4cf` | Nine new admission tests, five build-input tests and all 828 reference tests passed locally. The two package gate receipts matched. Full local API discovery ran 794 with the same 75 environment errors and 477 skips. [Hosted PostgreSQL and recovery](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42097155472) and [connected browser/build](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42097155551) belong to this revision only. |
| Integrated clinical plus admission runtime | Before the documentation update, the combined runtime tree was `17cc946a0176d8507ad26526f43b3b0462cb07f2`. Of 68 targeted checks, 62 passed and six that require PostgreSQL skipped locally. The rehearsal compared 495 route/capacity cases against the #542 base and exercised 33 command and 28 read OpenAPI operations. The final branch's hosted workflows remain the acceptance record for its exact commit. |

**Post-baseline verification and adjacent work.** The [clinical-parent API run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42096660696) ran 833 tests and reported 29 migration-test errors. The two disposable fixture cleanup owners left the 0021 citation guard function in the investigation schema after dropping its trigger table. This candidate now removes that exact test-owned function in both teardown paths. Unexpected dependencies still block schema removal. Production migrations and clinical authorization are unchanged by the test fix.

Locally on the combined runtime, 858 reference and 676 client tests passed, the web compiled, and both installed dependency receipts reconciled. Full local API discovery included 843 cases, 75 Unix-socket permission errors and 494 database skips. Use [the integrated PR](https://github.com/OpenxIntelligence/open-intelligence/pull/552) to inspect the tested commit and its hosted evidence. The follow-up here integrates the frozen [#545](https://github.com/OpenxIntelligence/open-intelligence/pull/545) web CycloneDX and OCI pin work at `1c918c1`. The npm owner creates the BOM, the package verifier checks its byte digest against the installed-notice receipt, and CI consumes a single API BOM. The package and image declarations now hash 14 source inputs. OS-layer inspection and distribution rights remain open.

The exact published migration from [#549](https://github.com/OpenxIntelligence/open-intelligence/pull/549) at `7c82bf6` is retained. It refuses historical ownership mismatches and prevents changing a patient or encounter owner directly in SQL. A no-DDL join preserves both published 0022 histories. The tests exercise upgrades from each populated parent, refusal of contaminated history, A/B note separation and two direct reassignment attempts after restore. Use the final [#552 workflow results](https://github.com/OpenxIntelligence/open-intelligence/pull/552/checks) to determine which of these database tests and recovery checks passed on its current commit.

For the governing distinction between source code, witnessed execution, scientific performance and clinical release, use [release acceptance](RELEASE_ACCEPTANCE.md). For the next decision and sequence use [the execution plan](MASTER_EXECUTION_PLAN.md).

## Clinical base checkpoint, #542 at 6c981114

The following record belongs to the pinned clinical base. Its named revisions, gates and donor observations are retained for traceability. The current platform increment and its own acceptance are described above.

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

The connected laboratory path in draft #557 extends Records → saved Observation
question → citation inspection → recorded follow-up. Tasks retain the exact
source version, SHA-256, Observation and question fingerprints through assignment
and acknowledgment. An amendment leaves the earlier history readable and blocks
new work or completion against the stale laboratory question. Follow-up and its
task-event log remain the existing coordination owner. Independent clinical
review, evidence appraisal, and a reconciled decision on an amended result
remain separate work. See the [patient walkthrough](../H1_DEMO.md#record-follow-up-work-for-the-same-laboratory-question)
and [the integration checks](https://github.com/OpenxIntelligence/open-intelligence/pull/557/checks).

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
