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
the retained contributions. This revision requires `0018_laboratory_questions`
for [saved laboratory questions](docs/engineering/H1_DURABLE_LABORATORY_QUESTIONS.md).
The Python/SQLite application is retained as a separate reference implementation.

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

**Data-integration dimension (Slice D2, 5 November 2026):** live
interoperability on synthetic fixtures — FHIR R4 exchange, terminology,
and DICOM report-only. `src/open_intelligence/fhir_exchange.py`
builds a FHIR R4 Bundle from a case's current assertions and sources
(Patient, one Observation per assertion with the ledger certainty in a
synthetic extension, one DiagnosticReport per source, one Condition per
ICD-10-bound finding with verificationStatus unconfirmed) and validates
and translates inbound bundles back into anchored findings through the
one import path, so the A1 anchor checker, the amendment rules, and
the snapshot-invalidation cascade apply exactly as they do to report
imports; the original bundle bytes are the stored source. Terminology
(`src/open_intelligence/terminology.py`) is organized as modality
schema packs: LOINC and ICD-10 are available with pinned codes (three
lab analytes; histology → ICD-10 C80.1 on the oncology vertical),
RxNorm is registered with no pinned codes yet, and SNOMED CT is
blocked (license unresolved) — no SNOMED code is ever emitted or
accepted. DICOM (`src/open_intelligence/dicom.py`) is report-only by
construction: the table has no pixel column and any payload carrying
pixel fields is rejected. The patient-access adapter graduates from
library-only to a live HTTP path: bundle delivery goes through its
authorization, revocation, identity-binding, and loss-receipt
machinery. mCODE conformance is not claimed in this slice (its
profiles bind condition codes to SNOMED CT and no IG validation
exists here); a bundle claiming an mCODE profile is rejected. Routes:
`GET/POST /api/cases/{ID}/fhir/bundle`, `GET /api/cases/{ID}/fhir/terminology`,
`GET/POST /api/cases/{ID}/fhir/dicom`, plus a display-only Exchange
panel in the web app. Dimension modules never import each other (the
FHIR translator takes its terminology validator as an injected
callable); the import-graph tripwire now lists the three D2 modules
and stays green. Local suite at the slice branch: 1043
tests, with the same 17 pre-existing `test_pdf_intake` failures as
the branch baseline (1006 tests) and zero new failures. Unproven: no live system
is connected (all exchange is synthetic fixtures); no live model call
exists in the slice (Meta billing fix still pending); the HTTP adapter
is constructed per request, so its in-memory bindings do not persist
across requests — the durable guarantees are the ledger's duplicate
detection, patient-match quarantine, and the recorded adapter events.

**Analysis dimension (Slice D3, 6 November 2026):** A2 Longitudinal,
A3 Molecular, T1 imaging comparison, T2 lab/marker series, and T4
line of therapy — five deterministic toolsets, each its own module
with its own fixture suite, no model calls anywhere (an AST test pins
that none of them imports the model-call path). A2
(`src/open_intelligence/longitudinal.py`) builds one ordered track
per finding key over current sources, with certainty changes,
same-date conflicts reported as unknown (never resolved by picking a
winner), and interior coverage gaps. T2
(`src/open_intelligence/lab_series.py`) turns laboratory assertions
into numeric series: strict single-number quote parsing
(unparseable/ambiguous points are typed, never guessed), unit-matched
deltas only, LOINC codings attached through an injected callable
(unbound keys are listed, never fabricated), and no trend words. T1
(`src/open_intelligence/imaging.py`) compares consecutive
same-modality imaging studies as finding-key set diffs
(persisting/changed-state/added/removed); it is report-only by
construction and never touches pixels. A3
(`src/open_intelligence/molecular.py`) links variant identities
(finding keys on current molecular sources) to pinned CIViC/ClinVar
ledger evidence — current versions only, with a case assessment, token-exact
gene matching — plus genomic delta tables; unassessed and
unrecognized-prefix records are listed, never linked, and no variant
interpretation is ever stated. T4 (`src/open_intelligence/therapy.py`)
counts therapy lines under a versioned ruleset (`lot-rules-1` /
`lot-rules-2`, synthetic fixture rules from the vertical's ruleset
label, not guideline content); computed lines are recorded in the new
`therapy_lines` table with their ruleset version, and a ruleset
change marks earlier rows stale. T4 is not a RECIST calculator: it
counts regimen lines only. T1 and T2 consult the D1 specimen-chain
validator through an injected callable before comparing across
specimens (the D1 note's first live caller); chain breaks are typed
records on the comparison, never silent blocks. Dimension modules
never import each other; the import-graph tripwire now lists the
five D3 modules and stays green. Local suite at the slice branch:
1076 tests, with the same 17 pre-existing `test_pdf_intake` failures
as the branch baseline (1043 tests) and zero new failures. Unproven:
no live caller wires the toolsets yet — they are the deterministic
machinery the A2/A3 role agents call when parallel roster wiring
lands; no live model call exists in the slice (Meta billing fix
still pending).

**Analysis dimension (Slice D4, 6 November 2026):** patient analytics
— lab-trend views, symptom progression, record-completeness
analytics, and outcomes tracking — as read-only derivations of
stored data in `src/open_intelligence/patient_analytics.py`, with a
read-only `GET /api/cases/{id}/analytics` route and a display-only
Analytics panel in the web app. Lab trends build on the T2 series
(passed in as a plain mapping, never imported, so the import-graph
tripwire stays green): one trend per analyte over the longest run of
consecutive parseable same-unit points, with unparseable, ambiguous,
and unit-changed points listed as excluded with their reason, never
silently dropped; the trend word is direction only
(rising/falling/stable, |percent| under a pinned 1% band reads as
stable), and no improvement or worsening is ever claimed. Symptom
progression lists the patient's own symptom notes verbatim in
noted-date order, marking exact-text repeats and amended wording
(earlier versions preserved); no severity is scored and none is
inferred. Record completeness is a pinned checklist of what the
record holds and what it lacks, each item naming what it enables; a
missing item is listed as missing, never filled in. Outcomes tracking
assembles recorded states only — current vs stale therapy lines by
ruleset, patient-goal statuses with version history, and
follow-through tasks by status (overdue only when the caller supplies
a date) — with no response, progression, benefit, or eligibility
claim anywhere. No model call exists in the slice (an AST test pins
that the module imports neither the model-call path nor any other
dimension module). Local suite at the slice branch: 1106 tests, with
the same 17 pre-existing `test_pdf_intake` failures as the branch
baseline (1076 tests) and zero new failures. Unproven: the analytics
route is the first live caller of the D3 toolsets (via the T2 series
it builds per request); no live model call exists in the slice (Meta
billing fix still pending).

**Hypothesis generation dimension (Slice D5, 6 November 2026):** A4
Literature, A5 Trials, T5 report assembly, and HYPOTHESIS
composition per REQ-09-10 — as deterministic code in
`src/open_intelligence/literature.py`,
`src/open_intelligence/trials.py`, and
`src/open_intelligence/hypothesis.py`, with a read-only
`GET /api/cases/{id}/hypothesis-report` route and a display-only
Hypothesis generation panel in the web app. Literature records are
bibliographic metadata only (six pinned synthetic records standing
in for Europe PMC, Crossref, and OpenAlex — no live fetch, no full
text, no findings; a record carrying findings is rejected). Trial
listings are registry metadata only (four pinned synthetic listings
in the reserved NCT9 block — no live lookup); listings are never
eligibility, enforced in code: eligibility language is detected and
rejected, and every rendered listing carries the fixed label
"Registry listing — not an eligibility determination." HYPOTHESIS
composition enforces REQ-09-10: at most 280 characters, resting only
on kept claims (deterministic claim ids `inv{id}:c{index}`), each
sentence citing at least one claim id, with no new number,
identifier, or drug — a token absent from its cited claims rejects
the composition — plus the scope guard (no advice or eligibility
language) and the fixed limits phrase when all cited claims are
low-tier. T5 assembles the report deterministically (fixed section
order, lists sorted by id): kept claims, composed hypothesis,
literature, trials, abstentions; an empty input produces an empty
section, never invented content. No model call exists in the slice
(an AST test pins that none of the three modules imports the
model-call path or any other dimension module, including each
other). Local suite at the slice branch: 1161 tests, with the same
17 pre-existing `test_pdf_intake` failures as the branch baseline
(1106 tests) and zero new failures. Unproven: no composed
hypothesis is stored yet — the report section reports
`not_composed` and persistence is a follow-up (it needs a store
table and write-contract treatment); the pinned literature and trial
fixtures are not matched to the case; no live registry lookup
exists; no live model call exists in the slice (Meta billing fix
still pending).

**Care coordination dimension (Slice D6, 6 November 2026):**
Appointments — the patient can know appointment times and changes —
as deterministic code in `src/open_intelligence/appointments.py`,
with `appointments` + `appointment_events` tables and
`create_appointment`, `change_appointment`, and `list_appointments`
in the store, three routes (`GET /api/cases/{id}/appointments`,
`POST /api/cases/{id}/appointments`,
`POST /api/cases/{id}/appointments/{n}/change`), and an Appointments
panel in the web app. An appointment is a fictional, case-scoped
record of a planned meeting: title, optional purpose, scheduled
date (required) and optional time (HH:MM), optional location, and a
status — recording it records the plan, it books nothing and sends
nothing. `scheduled` is the only open status: a reschedule changes
the date and/or time and keeps the status (a reschedule that
changes neither is rejected), while cancellation and completion are
terminal — further work is a new appointment. Every change appends
one event row (who, when, why, previous and new values) and history
is never edited. Role gates come from the existing generic case gate
(patient reads only their own bound case; writes are
operator/clinician only; auditors hold no case grants). Appointment
text carries the same narrow guard as follow-through tasks (reused,
not forked): no recommendation, order, eligibility claim, diagnosis,
or dose. The list view sorts by scheduled date, derives status
counts, and flags past due dates when a caller supplies `today`
(the route does not — the server date is not the patient's date).
No model call exists in the slice (an AST test pins that the module
imports neither the model-call path nor any other dimension module).
Local suite at the slice branch: 1182 tests, with the same 17
pre-existing `test_pdf_intake` failures as the branch baseline
(1161 tests) and zero new failures. Unproven: no reminder or
notification delivery exists yet (that is D7); appointments carry
no link to a follow-through task and no link to a source version;
no live model call exists in the slice (Meta billing fix still
pending).

**Care coordination dimension (Slice D7, 6 November 2026):**
Notifications — the patient and team learn of changes and due items —
as deterministic code in `src/open_intelligence/notifications.py`,
with a `notification_clears` table and `clear_notification` /
`list_notification_clears` in the store, two routes
(`GET /api/cases/{id}/notifications`,
`POST /api/cases/{id}/notifications/clear`), and a Notifications
panel in the web app. A notification is a derived, in-app-only
record: one per trigger, computed from the ledger at read time, and
nothing is ever sent anywhere. The pinned trigger kinds are overdue
and due-soon follow-through tasks, past-due appointments, follow-through
tasks needing a re-check (anchored source superseded), open re-review
tasks, and stale snapshots whose question is still open. Each trigger
produces exactly one notification per source record, keyed stably
(the key carries the due date, scheduled date, or source version,
so a changed date or reschedule is a new occurrence). The patient
sees due kinds only on their own bound case; operator and clinician
see all kinds; auditors hold no case grants. Clearing is explicit
and per-role — a clear records who cleared which key, for which
role, and when, is idempotent, and never touches the underlying
task, draft, or review item. Patients may clear only via the
notifications-clear route on their own bound case (a single narrow,
tested carve-out in the role check: clearing writes only an
acknowledgment row, never case content). No model call exists in the
slice (an AST test pins that the module imports neither the
model-call path nor any other dimension module). Local suite at the
slice branch: 1206 tests, with the same 17 pre-existing
`test_pdf_intake` failures as the branch baseline (1182 tests) and
zero new failures. Unproven: no external delivery of any kind; no
reminder scheduling; no C5 evaluation-harness probes for
notifications yet; no live model call exists in the slice (Meta
billing fix still pending).

**Care coordination dimension (Slice D8, 6 November 2026):**
referrals — a fictional, case-scoped record of a request to send a
case question to another team for input (question + specialty
label + reason + 1–50 pinned materials), with lifecycle
`requested` → `acknowledged` → `outcome_recorded` (terminal;
further work is a new referral), exactly one outcome per referral
(pinned kinds accepted/declined/completed, anchored to one current
source version), full status history, and the second-opinion
review/audit treatment (`pending` / `reviewed_in_demo` /
`needs_review`, reopened on amendment of a pinned material or the
outcome anchor). Recording a referral records the request — it
sends nothing, contacts no one, books nothing, and performs no
handoff outside the product; the specialty is a plain label, never
a real destination. Role-gated through the generic case gate
(patient reads own case only, writes are operator/clinician only);
the follow-through text guard is reused for all referral text.
Five routes, a Referrals panel (02g), and 19 new tests in
`tests/test_referrals.py` (+1 guard test). The module is registered
in `DIMENSION_MODULES` (an AST test pins that the module imports
neither the model-call path nor any other dimension module). Local
suite at the slice branch: 1226 tests, with the same 17
pre-existing `test_pdf_intake` failures as the branch baseline
(1206 tests) and zero new failures. Unproven: no message or
handoff leaves the product; no link to a follow-through task or an
appointment; no per-referral snapshot link; no C5
evaluation-harness probes for referrals yet; no live model call
exists in the slice (Meta billing fix still pending).

**Care coordination dimension (Slice D9, 6 November 2026):**
care-team collaboration — shared updates and handoffs the patient
and team read in the product, not outside it. A shared update is a
short dated note posted by the operator or clinician, visible to
the whole team including the patient on their own bound case (the
author role comes from the session account, never free text); a
handoff records a transfer of responsibility for a case question
(question + from/to actor labels + reason + 1–50 pinned
materials), with lifecycle `open` → `acknowledged` → `closed`
(terminal; further work is a new handoff), full status history,
and the second-opinion review/audit treatment (`pending` /
`reviewed_in_demo` / `needs_review`, reopened on amendment of a
pinned material). Recording either sends nothing, books nothing,
and contacts no one; the patient sees the same shared record as
the clinician — the role boundary is write access, not
visibility. Role-gated through the generic case gate (patient
reads own case only, writes are operator/clinician only); the
follow-through text guard is reused for all care-team text. Seven
routes, a Care team panel (02h), and 22 new tests in
`tests/test_team_collaboration.py` (+1 guard test). The module is
registered in `DIMENSION_MODULES` (an AST test pins that the
module imports neither the model-call path nor any other dimension
module). Local suite at the slice branch: 1249 tests, with the same
17 pre-existing `test_pdf_intake` failures as the branch baseline
(1226 tests) and zero new failures. Unproven: no message or
handoff leaves the product; no link to a follow-through task or an
appointment; no per-record snapshot link; no C5
evaluation-harness probes for care-team collaboration yet; no live
model call exists in the slice (Meta billing fix still pending).

**Second vertical (Slice V2, 6 November 2026):** the capstone —
a full synthetic cardiology end-to-end (CASE-CARDIO) through the
same coordination core + ledger + dimensions as the oncology path,
with zero core changes. The cardiology vertical
(`vertical_cardiology.py`) now carries its own terminology
bindings, pinned only from the publishers' own listings (LOINC
`10230-1` "Left ventricular Ejection fraction" for
`ejection-fraction`; ICD-10 `I50.9` "Heart failure, unspecified"
for `heart-failure`), and its own substance vocabulary
(`metoprolol`, `lisinopril`, `atorvastatin`, `furosemide`) for the
K7 substance arm. The one domain toolset is the line-of-therapy
equivalent: `therapy-rules-1` in the T4 table counts one line per
therapy class in first-occurrence order (a re-appearing regimen
resumes its earlier line; class is the regimen key minus its final
hyphen-delimited segment), so the two beta-blockers share a line
and the ACE inhibitor starts a new one. The end-to-end test
(`tests/test_cardiology_end_to_end.py`) runs route → K-checks →
Skeptic → T6 → D1 extraction and T3 specimen chain → D2
terminology and FHIR exchange (the ejection-fraction Observation
carries LOINC 10230-1, the heart-failure Condition carries ICD-10
I50.9 unconfirmed) → D3 longitudinal / lab series / imaging
comparison / therapy lines → D4 patient analytics → D5 HYPOTHESIS
composition and T5 assembly → the D6–D9 care loop, all against
CASE-CARDIO. The K-check context is built from the ledger, as the
live route does. Core-change accounting: no core module changed;
the single dimension-module touch is the `therapy-rules-1` entry
in `therapy.py`'s own fixture table, reported transparently in
the V2 section of `docs/IMPLEMENTATION_STATUS.md`. Local suite at
the slice branch: 1251 tests, with the same 17 pre-existing
`test_pdf_intake` failures as the branch baseline (1249 tests)
and zero new failures; the C5 harness still passes all 8 measured
metrics with `model_calls: 0`. Unproven: the live-model half of
the end-to-end (Skeptic over muse-spark-1.3, Meta billing fix
still pending — stub verdicts prove wiring only); per-case
vertical selection via a case-vertical field; per-vertical
evidence-catalog resolution; no C5 cardiology probes yet.

**K7/K2 keep-rate fix (post-program fix slice, 6 November
2026):** the Haiku interim live proof showed a live investigation
keeping only 1 in 5–6 claims: K7 dropped prose carrying "Source
version N" numbers and K2 dropped cross-source disagreement
claims. K7 was fixed by a prompt change, not a checker carve-out
— `build_prompt` (and the repair prompt in `skeptic.py`) now
instructs the model to attribute through the citations array
only and never write source version numbers in claim text. K2
gained a narrow carve-out: a claim with support `"contradicts"`
whose cited facets genuinely disagree skips slot-equality and
goes to T6 grouping instead; single-value assertions still go
through K2. Live re-probe through Haiku 5.5 keeps **6 of 6
claims** (was 1 of 6), with no "version" phrasing in any claim.
Local suite at the slice branch: 1258 tests, with the same 17
pre-existing `test_pdf_intake` failures as the branch baseline
(1251 tests) and zero new failures. See the K7/K2 section of
`docs/IMPLEMENTATION_STATUS.md`. Unproven: the Meta-only live
proof (muse-spark-1.3, Meta billing fix still pending).

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
