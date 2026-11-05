# Architecture decisions for the integration candidate

Updated 2026-11-05. This is the implementation crosswalk for the
[master execution plan](MASTER_EXECUTION_PLAN.md), not a replacement for the
first-principles plan or historical decision records.

## Revision and acceptance boundary

Accepted main was inspected at `f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9`.
It includes merged #481, laboratory R4 source custody and durable questions,
source-reported oncology context, and the reference application's agent-write
contract. Its required API migration is `0018_laboratory_questions`.

Candidate code was inspected at `3dd9811738e222274aa2c9e03edeff8104d64d53`:
#539 `917cc14bdc0f298bc33d06b09125cd4658205eec` joined with #540
`299cfb54df8259c6d72ddd88f3e0c08ca3dda3f4`, preserving #536/#537.
It adds the connected encounter/draft-note service, laboratory citation work,
database citation-freshness enforcement and shared strict question anchors.
Its required head is `0021_lab_citation_freshness`.

The focused integration comparison produced 38 failing assertions/subtests
before adding the strict owner; the joined candidate passed all 25 anchor test
methods. These results establish that bounded regression, not complete combined
acceptance. Final commands, skips, PostgreSQL/recovery/browser evidence and
review belong in [release acceptance](RELEASE_ACCEPTANCE.md). Neither this file
nor donor CI approves a merge, deployment or clinical use.

## Decisions and implementation owners

| Decision | Direction to preserve | Current owner / implementation boundary |
|---|---|---|
| Product scope | Patient-centered longitudinal intelligence, initially oncology, within the complete first-party healthcare ecosystem | [First-principles plan](../FIRST_PRINCIPLES_PLAN.md); the initial workspace does not reduce EHR/LIS/pathology/imaging/genomics/pharmacy/research scope |
| Canonical application | FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL with React/TypeScript/Vite; Next.js excluded | `apps/api`, `apps/web`; Python/SQLite remains a separate reference |
| One patient identity | Extend the existing registry and qualified patient/case bindings | `src/open_intelligence/postgres_registry.py`; `apps/api/src/oi_api/case_bindings.py`; no second patient master |
| One original-source owner | Preserve bytes, digests, immutable versions, source identity, specimen context and amendment edges | `sources.py`, `source_integrity.py`, `laboratory_fhir_store.py`; source-reported facts remain distinct from reviewed meaning |
| Strict question identity | Explicit text-line versus FHIR Observation variants; strict strings/integers; reject coercion and mixed variants | Candidate `question_anchors.py`, used by existing preflight/question/follow-through owners; no new tables, wire payloads or request fingerprints |
| Existing owners retain authority | An anchor is identity only; resolving it requires current patient/case grants, original integrity and freshness | `composer_preflight.py`, `source_questions.py`, `question_followthrough.py`, `laboratory_questions.py` |
| Encounter workflows | Reuse one clinical state machine with PostgreSQL persistence hooks | Candidate `src/open_intelligence/clinical_encounters.py`, `postgres_encounters.py`, API `encounter_routes.py`; HTTP exposes draft-note operations, not professional attestation |
| Transactional writes | Domain state, command receipt and event share a transaction; prepare complete disclosure before final authority checks where implemented | Registry and route owners; preserve retry intent, rollback on denied grants or response-preparation failure |
| Laboratory citation freshness | New links require the complete case source snapshot to remain current | Candidate `0021_lab_citation_freshness` trigger; new laboratory inserts require READ COMMITTED; old history/receipt replay remains inspectable under current access |
| Oncology semantics | Keep current reported episode labels; introduce typed episode identity/source associations in the next accepted increment | `sources.py`, `source_world_model.py`, `source-oncology-label.tsx`; reported labels do not establish clinically reconciled primaries/metastases |
| Models | Inspectable proposals behind deterministic task/authority contracts | Reference `investigation.py` and `agent_writes.py`; a connected H1 copilot and parallel role-agent execution remain future work |
| Infrastructure | Modular owners and relational contracts first; qualify added infrastructure for a demonstrated task | No new runtime dependency in this consolidation; research catalogs do not adopt a broker, vector store, graph store, agent runtime or vendor |

Paths without a prefix in this table refer to `apps/api/src/oi_api`, except
`source-oncology-label.tsx`, which is in `apps/web/src`.

## Reconciled related pull requests

These are GitHub observations from 2026-11-05, pinned to the revisions below.
An open branch may contain useful work already carried through another owner.
Compare individual blobs and contracts before importing it again.

| PR and observed head | State | Reuse decision for this candidate |
|---|---|---|
| [#301](https://github.com/OpenxIntelligence/open-intelligence/pull/301), `611b86e3f0fefd61d0937216141e05262d2b55a9` | Open draft; child of #290; shares #291/#148 clinical lineage | Preserve shared encounter integrity, final access checks and per-version facility/department/note-kind attribution already present through the candidate encounter owner. Its research SQL `004_note_provenance.sql` is absent here; candidate Alembic `0019_ehr_encounters` owns these fields. Do not run the research script as an additional application migration. |
| [#141](https://github.com/OpenxIntelligence/open-intelligence/pull/141), `429faf8982dc3737482d4166d19adb7ec0ba06e0` | Open draft; child of #126 | Reusable `execute_bounded_model` boundary in the reference Composer investigation. It is absent from main/candidate. Port only after reconciling existing citation validation and agent-write provenance; it does not establish alternate live-provider qualification. |
| [#427](https://github.com/OpenxIntelligence/open-intelligence/pull/427), `a106bfaf2419d46300916c20f8eb6751a89817a1` | Merged into `integration/h1-evidence-reading-export-20261103`, merge `aa1edf59700bcab84a5725abff5e3a8fd92e1361` | Generic `fhir_kernel.py` / `fhir_routes.py` are absent from both inspected main and candidate. Preserve this separate standards owner as a future reconciliation input; its merge status does not prove presence in accepted main. Existing laboratory FHIR custody remains canonical. |
| [#476](https://github.com/OpenxIntelligence/open-intelligence/pull/476), `4f1c613abe1f90c185e1f2f9edb816e3bf81fa3c` | Open draft; #474 → #451 → #448 → #399 research stack | Local question-only runner and separate public-label scorer are absent from candidate. Reuse for isolated synthetic evaluation; no production semantic service, clinical SQL access or NVIDIA inference adoption. |
| [#466](https://github.com/OpenxIntelligence/open-intelligence/pull/466), `fbc26cb6bfb2f6127aee9fbe91ee12248f46a1a4` | Open draft; child of #461 | Extraction qualification harness is absent from candidate. Reuse its tests/counterexample when qualifying existing document/PDF owners; do not replace them or infer clinical extraction accuracy from its authored corpus. |
| [#152](https://github.com/OpenxIntelligence/open-intelligence/pull/152), `4c6c21fe5f7d92a23b0ff3789429746d47bce266` | Open draft, conflicting with its main base; #95/#130/#126 integration lineage | Reuse read-only clinical-to-Composer gate requirements. Its `clinical_composer_context.py` is absent here; the 34-file historical reconciliation must not replace newer registry/source/question/domain owners wholesale. |

Current-head workflow metadata showed successful runs for #301, #141, #427,
#476 and #466. No PR-triggered run was returned for #152's current head; its
description cites older `d052700...` code. Workflow conclusions are evidence for
those donor revisions only. This review did not rerun or independently establish
their reported test counts or clinical validity.

## Migration and preservation rules

1. Keep every published migration byte unchanged. `0020_ehr_lab_convergence`
   is a no-DDL join of both published 0019 parents; `0021` follows that join.
   Test populated upgrades from both parents, restart, restore and retry before
   accepting the combined application.
2. Preserve immutable notes, original source bytes, command hashes, receipt IDs,
   qualified bindings and audit/event order. Missing legacy provenance stays
   NULL/unknown; labels are descriptors, not clinician/facility credentials.
3. Keep the SQLite reference migration question separate: #301 changes fresh
   schema creation but supplies no SQLite ALTER path for a populated older note
   table. Any supported upgrade of that reference needs a preservation migration
   and a populated-database regression; do not rebuild histories to make it pass.
4. Phase 1 extends the registry/source owners with bounded episode identity and
   source associations. Recheck the live candidate and competing migrations
   before selecting the next revision. Clinician confirmation requires an
   accepted credential/attestation boundary.

See [interoperability](INTEROPERABILITY_MATRIX.md),
[AI evaluation](AI_EVALUATION_PLAN.md) and
[security/governance](SECURITY_GOVERNANCE_PLAN.md) for the corresponding gates.
No independent clinical validation is established.
