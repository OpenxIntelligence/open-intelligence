# Patient Mission Projection — Bounded Design

**Status:** proposed implementation contract for a synthetic-only engineering slice. This is a complementary capability within the existing Open Intelligence architecture. It does not replace the current case, source, assertion, evidence, question, investigation, review, event, or authority contracts.

## Intent

Create the first visible Patient Mission surface by projecting the existing, versioned synthetic case state into five practical questions:

1. Where is this case workflow now?
2. What do the current authored sources report?
3. What remains unresolved, stale, or quarantined?
4. What material source/evidence changes occurred?
5. What bounded workflow action comes next?

The projection is for workflow orientation. It is not a patient summary, diagnosis, treatment recommendation, evidence appraisal, clinical decision, or assertion of biological truth.

## Goals

- Reuse the canonical `CaseStore` state without adding a second ledger.
- Preserve exact source-version, line, question, investigation, amendment, and quarantine references.
- Distinguish current reported statements from pending, indeterminate, not-reported, not-assessed, and conflicting states.
- Surface amendment-driven stale investigations as material changes.
- Generate only deterministic workflow actions that the existing demo can actually perform.
- Give the browser portal a concise mission-control panel while retaining the detailed workspace below it.
- Keep every response explicitly synthetic-only and non-clinical.

## Non-goals

- No automated diagnosis, treatment selection, trial matching, prognosis, patient-specific advice, or evidence grading.
- No AI/LLM inference, free-text clinical extraction, or new model provider.
- No identity, consent, PHI, clinician credentialing, production authorization, or real patient use.
- No new persistence schema, duplicated graph store, task engine, or autonomous action.
- No claim that a displayed next step is medically appropriate.

## Approaches considered

### A. Add persistent Patient Mission tables

This would store mission status, summaries, blockers, and next actions separately. It was rejected for this slice because it duplicates canonical state, creates synchronization and amendment risks, and promotes a projection into a competing ledger.

### B. Derive the mission entirely in the browser

This would avoid backend work, but it would scatter workflow rules into presentation code, make other clients reimplement them, and make consistency and testing weaker.

### C. Deterministic server-side projection over one canonical state snapshot — selected

A pure function receives `CaseStore.state(case_id)` and returns a typed, read-only mission projection. A dedicated endpoint exposes it. The browser renders it without changing source, question, investigation, or review state.

This preserves one source of truth, is independently testable, and can later be replaced or extended without changing the ledger.

## Projection contract

```text
PatientMissionProjection
├── case
│   ├── case_id
│   ├── label
│   └── scope = synthetic_workflow_only
├── workflow_status
├── where_am_i
│   ├── current_source_documents
│   ├── reported_statements
│   ├── open_questions
│   ├── stale_investigations
│   ├── quarantined_deliveries
│   └── latest_source_event_date
├── what_we_know[]
│   ├── finding_key
│   ├── state
│   ├── statement
│   ├── source_version_id
│   └── source_line
├── what_remains_unresolved
│   ├── source_findings[]
│   ├── questions[]
│   ├── stale_investigation_ids[]
│   └── quarantined_delivery_ids[]
├── material_changes[]
│   ├── event_id
│   ├── kind
│   ├── occurred_at
│   └── summary
├── next_actions[]
│   ├── kind
│   ├── label
│   └── reason
└── guardrails[]
```

`workflow_status` is a workflow state, never a clinical state. Initial values are:

- `awaiting_sources`
- `ready_to_define_question`
- `investigation_in_progress`
- `review_required`
- `reviewed_in_demo`

## Deterministic rules

- Only current source-version assertions appear in `what_we_know`.
- `pending`, `indeterminate`, `not-reported`, `not-assessed`, and `conflicting` assertions also appear under unresolved source findings. `negative` remains a reported result and is not automatically unresolved.
- Open questions remain unresolved even if unrelated drafts exist.
- Stale investigations and quarantined deliveries force `review_required`.
- Material changes are limited to amendment/invalidation/quarantine events already present in the event ledger; event `details` are parsed defensively.
- Next actions are limited to existing demo operations: gather/import a source, review quarantine, define a question, create a source-bound draft, reconcile a stale investigation, acknowledge a current draft in demo mode, or monitor for changes.
- The projection must not create or mutate any persistent record.

## Browser surface

Add a `Patient Mission` panel near the top of the existing portal. It shows:

- workflow status and counts;
- source-grounded current statements;
- unresolved items;
- material changes;
- bounded next actions;
- an always-visible synthetic-only/non-clinical warning.

The panel must not hide the detailed source, assertion, question, evidence, and investigation views.

## Validation

Automated checks must prove:

- An empty case waits for sources without inventing state.
- A seeded case exposes exact current assertions and unresolved source statuses.
- An explicit amendment produces a material change and review-required state.
- Another case's data never appears in the projection.
- The HTTP endpoint rejects unknown cases through the existing boundary.
- The static portal exposes the Patient Mission section and its warning.
- Existing unit, HTTP, JavaScript syntax, and browser journey checks remain green.

## Stop conditions

Narrow or remove the projection if it loses exact source references, presents workflow status as medical status, invents actions not supported by existing capabilities, obscures uncertainty, increases cross-case leakage risk, or requires a second ledger.

## Relationship to the broader architecture

This slice implements one small portion of the complementary Patient Mission Portal annex. Identity, consent, goals, acute safety, medications, specimens, trials, therapeutic development, access, execution, outcomes, and learning remain separately bounded future capabilities. Passing synthetic tests does not promote any of them to implemented or clinically evaluated status.
