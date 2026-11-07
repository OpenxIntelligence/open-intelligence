# Open Intelligence

Open Intelligence is building a patient-centered healthcare intelligence platform,
initially focused on oncology. The full product ambition and canonical architecture
remain in the [first-principles plan](docs/FIRST_PRINCIPLES_PLAN.md).

## Run the connected fictional application

Start with the [persistent demo guide](docs/H1_DEMO.md). The connected H1 application
uses React/Vite/TypeScript and FastAPI/PostgreSQL 16. It brings fictional records,
source-anchored questions, evidence comparisons, preserved reports and recorded
follow-up work into one patient workspace. Setup deliberately creates one fictional
patient/case/source; repeated setup and stop/resume retain its saved work.

[Consolidation and acceptance #481](https://github.com/OpenxIntelligence/open-intelligence/pull/481)
records the original integrated application and its acceptance results.
The [convergence record](docs/engineering/H1_ACCEPTED_DEMO_CONVERGENCE.md) identifies
the retained contributions. This integration candidate requires
`0028_source_delivery_retry`, extending the published `0027_source_event_purpose`
repair and `0026_integrated_core` join. The retry extends the existing source-event owner
with explicit authority and immutable receipts.
The [upgrade contract](docs/implementation/SOURCE_EVENT_PURPOSE_REPAIR.md)
covers fresh and published 0026 databases; older research-history adoption
remains held. It retains [encounters and draft notes](apps/api/README.md#connected-encounter-and-note-service),
[laboratory questions and citations](docs/engineering/H1_LABORATORY_CITATIONS.md),
and the [durable source-question brief worker](docs/engineering/H1_DURABLE_EXECUTION.md).
The [source-event worker](docs/engineering/H1_SOURCE_EVENT_DELIVERY.md) reconciles
pending runs after a source changes. The workspace can reopen an amended
question's existing run and show recorded follow-up beside the selected
laboratory result, through their existing authorized readers.

[Foundation #565](https://github.com/OpenxIntelligence/open-intelligence/pull/565)
remains the upstream owner. This dependent draft's PR records its exact combined
source, verification and landing status. Combined verification is pending at
this source-publication checkpoint; the verified
[#529 foundation](https://github.com/OpenxIntelligence/open-intelligence/pull/529)
and other donor receipts keep their original scope. The
[implementation status](docs/IMPLEMENTATION_STATUS.md#current-integrated-h1-checkpoint)
pins the retained inputs and remaining work. The Python/SQLite application
remains a separate reference implementation.

Use independently authored fictional data only. This application does not establish
production identity/consent, professional clinical approval, model qualification,
authorized external sharing, clinical deployment or distribution rights.

## Historical document/image checkpoint — #381

The checkpoint records below preserve their original scope and evidence. Their
draft, migration and test status describes the named earlier revision, not the
current application or acceptance status linked above.

The isolated [document/image candidate #381](https://github.com/OpenxIntelligence/open-intelligence/pull/381) composes the frozen #377 document/evidence/review candidate with #370 image/archive/report continuity, corrected #376 audit-tail tests, #373 fixture lifespan and verified #378/#379/#380/#382 frontend corrections. Its own hosted acceptance is pending. Historical owner receipts below do not qualify this composition.

Current runtime readiness requires the single `0013_document_image_convergence` head. Both published 0012 histories and their immutable originals, annotations, citations, reports and tasks remain intact. The new join has no DDL. The combined dependency inventory retains the existing 26 exact runtime artifacts, full notices and code-only pydicom boundary; no new component or permission is selected.

Tests-first source `ecda925d887c55e496dc3e6748337a8ddebd34ac`, tree `61f0bd922adafe0f6ef2d4711c7f0627d5710989`, ran 441 API/PostgreSQL test executions in [41711711965](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41711711965) and failed seven assertions solely in the five new route/graph/convergence methods. No test errors or skips were reported. The unchanged document browser baseline passed 415 client tests, 13 rights controls, build and actual browser execution in [41711711889](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41711711889). These are baseline results, not a final combined pass.

The pinned accepted-main input remains `c4798ae85004713593f83458abd2102be6729095` through #377. This does not claim reconciliation with a subsequently moving main. Main and owner branches are untouched. The source-only review identified a separate shared source/document audit-tail authority gap; a regression and repair must be verified before completion.

Draft, unmerged, undeployed and independently fictional only. Manual passage provenance in canonical investigations, amended-record reconciliation adoption, production identity/consent, qualified external archive access, clinical evaluation and distribution decisions remain explicit separate contracts. PACS adoption remains HOLD. See the [execution plan](https://github.com/OpenxIntelligence/open-intelligence/blob/integration/h1-document-image-continuity-20261103/docs/superpowers/plans/2026-11-03-document-image-convergence.md) for frozen inputs, rulings and acceptance.

## Preserved owner checkpoints

> **Pinned-main reconciliation:** #354 remains the document owner at `7b16a9a900737f07adb03e35362922c886424e9b`. This dependent source checkpoint preserves that concurrent update, includes accepted main `c4798ae` and records #374 ancestry. See the [convergence gate](docs/engineering/H1_EVIDENCE_CONVERGENCE_MERGE_GATE.md) for the exact composition and its separate verification requirements. The earlier checkpoint below retains its original scope.

**A patient-centered, clinically governed healthcare intelligence and operations platform, initially focused on oncology.**

Open Intelligence aims to help patients and care teams maintain an evolving understanding of a person's cancer, investigate important questions, and connect new findings to inspectable evidence.

The destination is a complete first-party healthcare ecosystem: EHR, oncology, laboratory, pathology, imaging/PACS, genomics, pharmacy, research, care coordination and institutional operations. Its first connected experience helps patients and authorized professionals organize information, investigate questions, inspect evidence, review interpretations and follow agreed work through to outcomes. Clinical authority remains with qualified professionals.

**Founding clarification — 2 November 2026:** Sid Sijbrandij's public narrative is one source of workflow requirements. His medical data is not a platform input, engineering dependency or evaluation corpus. There is no manual or ethics-note opt-in exception. All current engineering and evaluation uses independently authored synthetic patients; the capability we build must generalize across people, cancers and care circumstances. See [the existing plan](docs/FIRST_PRINCIPLES_PLAN.md) and [the data-boundary work package](docs/engineering/PATIENT_DATA_CI_BOUNDARY_2026-11-02.md).

Repository context: Meta Global AI Developer Hackathon, Indie track.

## Historical implementation checkpoints

**3 November 2026 checkpoint:** main was observed at
[`c4798ae85004713593f83458abd2102be6729095`](https://github.com/OpenxIntelligence/open-intelligence/commit/c4798ae85004713593f83458abd2102be6729095)
and remains the Python/SQLite reference. The current H1 work continues the
existing [draft #354](https://github.com/OpenxIntelligence/open-intelligence/pull/354):
reviewed text/PDF originals and recoverable comparisons are locally composed with
#368 review/evidence continuity, #369 strict task dates, #362 restored-document
HTTP acceptance and #367 shared CI coverage. **Local composition verified;
exact combined hosted acceptance pending.** The
[current candidate record](docs/engineering/H1_CONNECTED_RIGHTS_CONVERGENCE.md#current-candidate--reviewed-document-convergence-in-354)
pins every input and separates current acceptance from historical receipts.

The repository now contains an **original, local synthetic-only Python/SQLite research prototype**, alongside the product plan and execution backlog. Its bounded case-workspace features include source-preserving report versions, authored findings with source-line references, persistent investigation questions and review drafts, amendment-triggered staleness, an event chronology, fictional evidence/applicability records, and an optional DOI-only bibliographic metadata view. These are demonstration and engineering capabilities, **not a clinically validated application**.

The local prototype has local demo accounts, roles, and sessions (operator-created accounts only; no verified identity), but **no real-patient authorization, verified clinician identity, production access control, clinical inference, treatment recommendations, comprehensive EHR interoperability, or licensed full-text literature analysis**. Do not enter actual patient records or treat demo acknowledgments as clinical sign-off. Scientific model and production architecture choices remain under review.

**Historical main baseline (2 November 2026):** commit [`52ea683`](https://github.com/OpenxIntelligence/open-intelligence/commit/52ea683fbe3537b17a05066dceff2ba01f758c5d). That application baseline ran 236 synthetic tests successfully during its audit; this is not a new run of current main or the H1 candidate. Current implementation, proposed changes, unmerged domain work and verification limits are distinguished in [implementation status](docs/IMPLEMENTATION_STATUS.md). Test success is not independent clinical validation.

**Bounded implementation target:** Python/FastAPI/PostgreSQL with React/Vite/TypeScript; Next.js is excluded. This is the selected migration target, not the stack of the existing Python/SQLite prototype.

**H1 patient identity integration candidate:** [apps/api](apps/api/README.md)
connects the existing canonical patient registry to FastAPI/PostgreSQL 16.
Explicit migrations, idempotent synthetic creation, exact-patient/organization
read checks and immutable creation receipts/events are implemented. The default
denies patient access; the opt-in credential file is a synthetic fixture, not
account verification or clinical consent. This unmerged integration preserves
source owners #85/#148 and is stacked on #162/#137. Local verification passed
49 API/migration/gate tests and 245 prototype tests; hosted container/recovery
evidence belongs to the exact draft-PR head. Those counts describe the historical
identity milestone, before the subsequent connected workspace.

**Historical H1 convergence — #307:** [draft #307](https://github.com/OpenxIntelligence/open-intelligence/pull/307)
converges #298's metadata citations and follow-through with #300's case-owned
fictional originals, human-authored comparisons and immutable reports on the same
canonical question. Both rights boundaries and migration histories remain intact.
Its [bounded convergence and verification record](docs/engineering/H1_EVIDENCE_CONTINUITY.md)
distinguishes implementation, exact combined test evidence and remaining work.
Live biomedical retrieval, model execution, professional review, image viewing/
interpretation, general PDF/annotation support and production identity remain
separate capabilities. This is
an unmerged engineering candidate, with no clinical approval or deployment claim.

**Reviewed document continuation:** [draft #323](https://github.com/OpenxIntelligence/open-intelligence/pull/323) adds ordinary text/PDF preview, exact original custody, immutable passage corrections and Records downloads on #315. [Scope and verification](docs/engineering/H1_REVIEWED_DOCUMENTS.md) distinguish this implemented intake from the remaining manual-provenance integration into questions and reports.

**Document integration checkpoint — #349:** [draft #349](https://github.com/OpenxIntelligence/open-intelligence/pull/349) composes #323 with #335's source reading, evidence reports and follow-up. Text/PDF originals have a separate, initially collapsed Records control that retains local selections while collapsed. The [continuity record](docs/engineering/H1_EVIDENCE_CONTINUITY.md) and PR distinguish the tests-first failure, combined verification and remaining boundaries. Manual selections remain separately attributed and excluded from structured-source investigation snapshots.

**Preserved #354 foundation:** [draft #354](https://github.com/OpenxIntelligence/open-intelligence/pull/354) already combined that document workspace with #348/#359's recoverable in-memory comparison drafts and #339's dependency identity checks at `d9b81f08a97998e8f95d2a1cc7c43b4165e99862`. Drafts resume only after fresh matching access; uncertain submissions retain their exact retry intent. The current continuation above preserves those owners and adds the existing donor corrections. Manual-document provenance in structured questions/reports, clinical validation and production identity remain open.

## Project documents

| Document | Purpose |
|---|---|
| [First-principles plan](docs/FIRST_PRINCIPLES_PLAN.md) | Product direction, workflow, architecture, evidence, evaluation, and expansion |
| [Execution backlog](docs/EXECUTION_BACKLOG.csv) | Bounded work packages with dependencies and acceptance evidence |
| [Contributor instructions](AGENTS.md) | How humans and coding agents should work in this repository |

## Investigation workflow under development

The current synthetic-only demonstration exercises a bounded portion of the intended investigation loop. These are requirements for subsequent independent evaluation and controlled expansion, not claims that full clinical workflows have been established:

1. Import source documents and preserve their identity, original bytes, and versions.
2. Persist source-linked assertions, uncertainty, questions, and scoped review decisions.
3. Connect one question to permitted evidence whose content and limits can be inspected.
4. Produce a dated brief with source links and review status.
5. Receive an amended report, identify affected conclusions, preserve history, and prepare a reviewable update.

An incoming amendment marks affected outputs as requiring review. It does not automatically promote a replacement interpretation into a reviewed clinical conclusion.

**Provenance write contract (Slice 1, 5 November 2026):** every stored
investigation carries a per-agent write contract (program plan §5.4) —
`writeId`, `agentId`, `agentRole` (A1–A6), `agentVersion`, `promptVersion`,
`modelId`, `runId`, `routeId`, `snapshotAt` (L1 as-of), `inputs` (source
versions, assertions, and evidence assessments, each with a content hash),
and `toolCalls` — held in exactly one place, the `agent_writes` table
(`src/open_intelligence/agent_writes.py` is the single owner of the
contract). A write missing any contract field is rejected with a typed
reason; a stored run can be replay-checked from its route, snapshot, and
recorded inputs, and a superseded source version invalidates the replay.
Local suite at the slice branch: 796 tests, with the same 17 pre-existing
`test_pdf_intake` failures as main (missing local `pypdf`) and zero new
failures.

**Deterministic K-checks K1–K7 (Slice 2, 5 November 2026):** every kept
investigation claim runs the deterministic checks of program plan C2 —
K1 identifier format; K2 slot–field match against the cited facets;
K3 temporal (cite only versions recorded at or before the snapshot);
K4 contradiction (the later of two contradicting claims drops);
K5 staleness (superseded or out-of-snapshot citations drop); K6 scope
guard; K7 support (every number, identifier, and named-substance token
must appear in the cited evidence; low-tier support must carry the
fixed limits phrase); K7+ injection. The checker
(`src/open_intelligence/kchecks.py`) is domain-free — the vertical's
predicates arrive as parameters — and a test scans it for vertical
literals. Failures go to `dropped` with a typed reason, never silently
repaired. Local suite at the slice branch: 889 tests, with the same 17
pre-existing `test_pdf_intake` failures as main (823 tests) and zero
new failures.

**Skeptic (A6) + one repair round + T6 reconciliation (Slice 4,
5 November 2026):** every kept claim gets an independent machine
second opinion from the Skeptic (same `muse-spark-1.3`, separate
prompt `skeptic:1`, no shared context beyond the claim and its cited
evidence — it catches a planted misstatement the K-checks miss, such
as "31 cm" against evidence "31 mm"); a failing claim gets exactly
one repair round (only content failures a restatement can fix;
contradictions, scope, and tainted content are never repaired);
contradictions and gaps are grouped deterministically (T6) with both
sides listed and the resolving evidence named, never merged or voted
on; conflicts surface as typed `AB-CONFLICT` codes with an origin,
alongside `AB-STALE` (which leaves the question open), `AB-BUDGET`,
`AB-MODEL`, and `AB-ALL-DROPPED`. The verification record (Skeptic
verdicts, repair record, T6 groups, abstention codes) is stored with
each run and returned in the response. Local suite at the slice
branch: 947 tests, with the same 17 pre-existing `test_pdf_intake`
failures as main (916 tests) and zero new failures. Unproven: the live
Skeptic run — the Meta Model API returned HTTP 402 (billing issue on
the key's team), so the prompt is verified only through the
stub-driven test suite; a live run is pending that billing fix.
Not yet a clinical claim: the parallel role agents are a later slice;
the single existing model call writes as A1 until the roster is wired.

**Evaluation harness (Slice 5, 5 November 2026):** verification
quality is measured by code, not asserted in prose — a deterministic,
offline harness (`src/open_intelligence/evaluation.py`, no live model
call) runs the planted-defect fixtures from C2/C4 through the real
checks and computes the M-metrics of OI-09 §9.2 that are measurable
offline: M5 temporal-defect recall, M6 contradiction recall and
precision (surfaced as a T6 group plus `AB-CONFLICT`), M7 staleness
recall, M8 advice-language leakage (target 0), M10 hypothesis
support, M16 replay determinism (one intact run replayed three times,
identical, plus tamper probes that must fail replay), M27 routing
record completeness, and M28 hypothesis citation recall (a prose-
attribution check over numbers, substances, temporal words, relation
verbs, and entities — it catches what K7 cannot, such as an
unsupported relation verb on a supported number). Each metric is
reported with value, n, target, and pass/fail; the human spot-check
(≥30 items) is recorded, not performed; model-dependent metrics
(M25, M26, M29) are listed as not measured. The harness measures; it
never gates. Local suite at the slice branch: 972 tests, with the
same 17 pre-existing `test_pdf_intake` failures as the branch
baseline (947 tests) and zero new failures. Unproven: the live-model
half of the metrics (M25/M26/M29 need live runs; the Skeptic's live
proof is pending the same Meta billing fix).

**Vertical interface (Slice V1, 5 November 2026):** the core holds no
oncology knowledge — oncology lives behind a vertical interface
(`src/open_intelligence/vertical.py`: a registry; a vertical
registers its domain rules, scope patterns, ruleset version, and
evidence bindings). The oncology predicates moved verbatim out of
`investigation.py` into `vertical_oncology.py`; the live path and the
evaluation harness resolve them through the registry. A minimal
synthetic cardiology vertical (`vertical_cardiology.py`) proves the
core is domain-free: it runs the same pipeline — route, K-checks,
Skeptic, T6 — end to end, with the cardiology predicates selecting
different behavior (a cardiology synonym resolves where oncology's
does not; "you have heart failure" trips the scope guard under
cardiology and passes under oncology). A tripwire test scans core
imports and fails the suite if any core module imports a vertical
definition module. Local suite at the slice branch: 986 tests, with
the same 17 pre-existing `test_pdf_intake` failures as the branch
baseline (972 tests) and zero new failures. Unproven: the live-model
half is unchanged (Meta billing fix still pending); the cardiology
run uses stub verdicts.

**Data-integration dimension (Slice D1, 5 November 2026):** arriving
records become anchored, checkable evidence. A1 Intake & Extraction
(`src/open_intelligence/extraction.py`) is the one deterministic
anchor checker every extraction proposal passes before its fields
become stored assertions: the source version must exist, belong to
the case, and be current, and each field must name a valid finding
key, a known certainty, a verbatim quote, and an exact source line —
anything else drops with a typed reason, never stored. The
report-import path routes its parsed findings through the checker.
T3 specimen chain (`src/open_intelligence/specimen_chain.py`) is the
deterministic chain-of-custody walker: it walks a biological asset's
parent lineage root-first, each link carrying its assay/specimen
context and anchor basis, and reports every break as a typed record
(missing asset/parent, cycle, unknown specimen, specimen mismatch,
superseded anchor, episode mismatch, kind violation) — never silent,
never a crash. Dimension modules never import each other
(cross-dimension interaction happens only through the ledger and
`route.decided`); the import-graph tripwire now lists the two D1
modules and stays green. Local suite at the slice branch: 1006
tests, with the same 17 pre-existing `test_pdf_intake` failures as
the branch baseline (986 tests) and zero new failures. Unproven:
nothing in the slice needs a live model call (Meta billing fix
still pending); the first live caller of the chain validator is
D3's comparison toolsets.

## Development boundaries

- Use independently authored synthetic patient examples. Keep real patient records, credentials, and restricted clinical content out of this repository and its issues.
- Document third-party permissions, exact versions, and applicable obligations before integration. A promising repository license does not clear its dependencies, data, models, or services.
- Distinguish proposed capabilities, implemented behavior, test evidence, and clinical validation.
- Evaluate the complete workflow against manual and simpler software approaches. Count total acquisition, preparation, review, and correction effort.
- Keep specialist modalities extensible, and qualify each analysis or research function for its intended use.

## Licensing

The project's distribution license has not yet been selected. This initial foundation includes original project documentation and references to external sources; it does not vendor their code or datasets. A project license and any third-party notices will be added through an explicit licensing decision.

## Run the source-ledger prototype

See [README_IMPLEMENTATION.md](README_IMPLEMENTATION.md) for local setup, supported synthetic report format, tests, and explicit limitations. The first code slice is a local demonstration, not a deployable clinical application.
