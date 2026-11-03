# Patient-journey research integration crosswalk — 3 November 2026

This is an additive execution crosswalk for the **Patient Journey and Capability Research Report, Technology Evaluation, and First-Party Modular Architecture**. It maps research findings to existing contracts and work. It does not create a replacement roadmap, approve candidates, change intended use, or mark the full platform complete.

## Audited baseline

- `main` at `24519839aa8ac1ea3aff88a956349ba72798a72a` remains the Python standard-library/SQLite/browser-JavaScript prototype.
- The adopted H1 target is React/Vite/TypeScript and Python/FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL 16. H1 excludes vector search and Next.js. Desktop, laptop and workstation workflows are the product scope; accessibility and narrow-window checks do not establish a mobile-product commitment.
- This bounded contribution starts from [draft PR #328](https://github.com/OpenxIntelligence/open-intelligence/pull/328), commit `5a188d4e18e4d80bc2ba1d662c966abc3096301f`. Its [web workflow run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666427184) was independently read as completed/success at that commit. This is software evidence on a draft stack, not merged migration or clinical validation.
- Keep [the existing source-pinned technology atlas](https://github.com/OpenxIntelligence/open-intelligence/blob/1bb4ff06a5ab222d3561145e757226f671dbf3ea/docs/research/TECHNOLOGY_ATLAS_VERIFICATION_2026-11-02.md) and exact H1 inventories as evidence owners. The new research catalog is supplemental. Pgvector, Qdrant, HAPI, OHIF, new RAG libraries and model fleets do not enter H1 because of a research recommendation.
- Read [AGENTS.md](../../AGENTS.md), [the first-principles plan](../FIRST_PRINCIPLES_PLAN.md) and [the existing backlog](../EXECUTION_BACKLOG.csv) for precedence. All present engineering inputs are independently authored synthetic data.

## Patient needs mapped to existing work

These are capability hypotheses from public structural narratives, not inferred private histories or proof of clinical benefit. Each extension needs its own acceptance evidence. Roles below describe accountability; no person or clinical partner has been assigned.

| Need and patient setting | Existing contract / tracker | Next concrete acceptance evidence | Human authority |
|---|---|---|---|
| Advanced solid tumor across local care and distant research sites | Source receipts, patient context, question and follow-up ownership; OI-006–010; #81, #115, #119, #295 | Two fictional institutions, missing original, amended result and named follow-up; show source receipt and incomplete handoff separately | Treating team manages treatment and symptoms; coordinator confirms arrangements |
| Rare cancer and expertise/trial search | Evidence catalog, criteria unknowns, investigation/review; OI-008, OI-017; #102, #117, #118, #120 | A candidate study with unmet and unknown criteria; dated registry evidence; no eligibility or open-slot claim | Specialist diagnosis and site eligibility/consent |
| Molecular second opinion | Specimen/assay identity, temporal PWM, source-linked questions; OI-006–009; #100, #116, #295 | Conflicting reports remain inspectable; missing versus negative preserved; source amendment makes affected conclusions stale | Molecular/pathology interpretation and treatment selection |
| Rural/local-care continuity | Patient workspace, source acquisition, delegated task ownership; OI-002, OI-007, OI-013; #98, #106, #119 | Printable low-bandwidth packet; explicit local/distant visit needs; revocation hides delegated content | Patient priorities, clinician suitability and navigator coordination |
| Financial/disability constraints | Patient-entered needs, practical tasks, referrals, confirmation state; OI-002, OI-007, OI-012; #106, #107 | Fictional assistance request can fail or remain pending without becoming approved; accessibility and human escalation assessed | Navigator/social worker/benefits agency; no automated entitlement decision |
| Exceptional self-directed investigation methods | Existing question/evidence/review lifecycle; OI-001–003, OI-008; #128, #122 | Abstract work patterns mapped to multiple settings; no identifiable medical files, copied profiles or public-patient-derived fixtures | Clinical/research oversight and patient preference |

A public story is discovery evidence, not an evaluation dataset. Study unsuccessful and under-resourced pathways through separately authorized research rather than assuming public success stories represent all patients.

## All 30 domains mapped to existing owners

The domain numbering comes from the founding mandate. These mappings are architectural responsibility assignments, not implementation-completion claims or a proposal for 30 services.

| Domains | Existing contracts / workstreams | Existing tracking |
|---|---|---|
| 1 Identity and access; 2 Patient registry | WS-02 scoped authority; issuer-aware patient mapping | #98, #114; OI-013 |
| 3 Patient record; 4 Patient World Model | WS-03 immutable sources; WS-04 temporal projection; WS-05 missing/conflicting states | #99–101, #115–116; OI-006, OI-009 |
| 5 EHR and encounters; 6 Oncology operations | First-party domain commands and professional review | #81, #87, #107; OI-007, OI-012 |
| 7 Laboratory and specimen management; 8 Pathology | Accession/specimen/result provenance; released versus proposed results | #87, #99–100; OI-006, OI-016 |
| 9 Imaging and PACS; 10 Genomics and molecular diagnostics | Specialist adapters anchored to patient/specimen/source versions | #100, #108; OI-016 |
| 11 Medication and pharmacy; 12 Radiation oncology | Domain-owned orders and professional authority | #87, #107, #110; OI-012, OI-016 |
| 13 Biomedical knowledge; 14 Scientific publications; 15 Clinical guidelines | WS-06 evidence/rights registry; article and asset-specific permissions | #102, #117; OI-004, OI-008, OI-018 |
| 16 Clinical trial intelligence | Criterion evidence, unknowns and coordinator review | #102, #107; OI-017 |
| 17 Evidence and provenance | Source identity, claim support and derived-output lineage | #99, #102, #295; OI-006, OI-008–009 |
| 18 AI and ML execution | WS-07 typed proposals and allowed tools | #103; OI-011 |
| 19 Investigation orchestration | WS-08 durable execution; WS-09 Composer | #104–105, #118, #295; OI-008–010 |
| 20 Patient workspace; 21 Caregiver workspace; 22 Clinician workspace; 23 Researcher workspace | WS-10 distinct task flows over common authorization and source contracts | #98, #106–107, #119–120; OI-007, OI-013 |
| 24 Care coordination; 25 Scheduling and referrals; 26 Patient support; 27 Notifications and communications | Task ownership, consent, requests, receipts and authoritative confirmations | #104, #106–107; OI-002, OI-007, OI-012 |
| 28 Enterprise administration; 29 Security and audit | WS-13 security/operations; WS-14 intended use | #109–110; OI-012–013 |
| 30 Integration infrastructure | WS-12 adapters; transactional outbox/inbox and versioned contracts | #87, #104, #108; OI-005, OI-009 |

The Patient World Model stays a versioned projection of source records and reviewed interpretations. It does not replace originals or become a second patient master. Shared contracts preserve source and receipt time, effective time, provenance, uncertainty, rights, patient/tenant scope and reviewer state.

## Concrete rights-gate contribution

**Existing owner:** OI-004 and #59. Reuse `apps/web/tools/license-gate.mjs`, the existing lockfile and `.licenses/inventory.json`; add no dependency or competing inventory.

**Problem reproduced:** the original gate accepted a substituted installed package with an unchanged version/license, accepted different allowed lock/installed license declarations, normalized a traversal-shaped lock path, followed package/scope/manifest/notice symlinks, and treated an installed optional package without a manifest as absent. Eight negative cases failed against the original code; five positive controls passed.

**Behavior established:** match installed identity (including npm aliases), version and exact declared license to the lock; require canonical package locations and non-symlink directory ancestors; inspect regular manifest/notice files without following symbolic links; distinguish an absent optional package from a malformed installed one. Do not copy outside notice bytes into evidence.

**Verification:** 13 filesystem-based tests passed locally after the fix. The existing H1 web workflow runs `npm run rights` before audit, compile and browser checks, retains test output, and preserves the existing evidence schema and `commercial_release_cleared: false`. Full installed-package/browser evidence must come from the exact child commit's hosted run; the selected-file local snapshot cannot establish it.

**Limits:** this is static installed-tree evidence checking, not a hostile concurrent-filesystem sandbox. npm's locked acquisition remains responsible for tarball integrity; this script does not prove every installed byte still matches a tarball. Optional artifacts remain uninspected. Container, native/WASM linkage, model, data, asset, service and commercial-distribution review remain separate.

The backend inventory at the audited H1 commit covers 24 exact CPython 3.12/Linux x86_64 wheels, 99 supplier-declared all-target Rust entries and 13 embedded-runtime evidence entries, approved only for local synthetic H1 development. Do not restate those 99 supplier entries as proof that all were linked into a particular binary. The frontend lock has 20 package entries; actual installed/omitted counts belong to each run.

## Execution order and acceptance ownership

| Order | Existing work to complete | Evidence required to advance | Status of this contribution |
|---|---|---|---|
| 1 | Reconcile research with accepted architecture and existing inventories | Exact main/H1 baseline and no contradictory adoption claim | Audited and documented here |
| 2 | Harden rights evidence under OI-004/#59 | Negative controls, compatible real lock, full CI at child commit, reviewed diff | Implemented; publish exact run evidence with the PR |
| 3 | Converge the existing source → question → evidence → report → review → amendment workflow, #295/#121 | Common source head, PostgreSQL/API/client/browser/recovery results and preserved history | Existing active PR owners; not completed by a report or this gate |
| 4 | Validate practical navigation and all five access settings, OI-002/#128/#106 | Independent fictional scenarios plus separately authorized human workflow evaluation | Research crosswalk prepared; no outreach or outcome claim |
| 5 | Qualify new specialist/content/model integrations, OI-011–018 | Demonstrated need, exact artifact rights, authorization, deterministic failure cases and intended-use evaluation | Held until each bounded gate is satisfied |

No treatment, diagnostic sign-off, medication/radiation change, clinical order, result release, patient merge, trial enrollment, benefit award or access grant is an AI-only action. AI can prepare inspectable proposals; deterministic authority and appropriately qualified humans control consequential transitions. No clinical release, merge, deployment, provider contract or real patient-data acquisition is established by this contribution.
