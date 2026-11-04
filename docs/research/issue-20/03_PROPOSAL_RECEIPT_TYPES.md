# Issue #20 — Gate 3: draft proposal/receipt types + ledger mapping

**Status:** research draft only, branch work. **No migrations.**
`src/open_intelligence/store.py` `SCHEMA` is untouched. All types live in
[tests/research_issue20_draft.py](../../../tests/research_issue20_draft.py),
which is deliberately **not** `test_*`-prefixed (no unittest discovery, no CI
effect), imports nothing from `src/`, touches no database, and must never be
imported by core modules. A separate scoped decision is required before any of
this touches core. (Self-critique fix, Pass 2: corrected the relative link to
the code module.)

## 1. Minimal draft types (fields match the code module exactly)

`ExperimentProposalDraft` (immutable; revisions are new ids): `id`, `case_id`
(`FIC-*` or None), `question_id`, `hypothesis_ids`, `kind`,
`stated_prediction`, `falsifier` (required negative control),
`input_refs_and_versions` (e.g. `PATH-20A@2`), `as_known_at` cutoff,
`intended_decision_relevance`, `method_ref`, `run_environment`,
`permission_scope`, `rights_status`, `expected_signal`, `measurement_plan`,
`uncertainty_limits`, `estimated_budget`, `effect_class`, `owner`,
`proposal_state` (default `draft`).

`EvaluationRunReceiptDraft` (one immutable row per attempt, including denials
and nulls): `proposal_id`, `attempt_id`, `actual_execution_state`
(`executed|denied|failed|null|simulation_only`), `input_digests`,
`source_and_code_versions`, `environment`, `parameters_seeds`,
`started_ended`, `cost_record`, `observed_metrics`, `uncertainty`,
`comparator`, `reproduction_status`, `independent_verification`,
`invalidation_dependencies`, `reviewer`, `review_decision`.

Guards enforced in `validated()`: fictional `FIC-*` cases only; clinical
language rejected in prediction/falsifier/relevance — exactly the code regex:
`recommend*|prescrib*|eligible|diagnos*`, `should (receive|undergo|get|start|
take)`, `must (receive|undergo)`, `best (treatment|therapy|option|drug)`,
`order (this|the) (treatment|therapy|procedure)`, `start treatment` (loop
cycle 1 correction: the earlier shorthand omitted the must/get/start/take
variants); at least one hypothesis id; non-empty versioned inputs; cutoff
`202\d-\d\d-\d\d` (2020s `YYYY-MM-DD`, matching the frozen 2026 cutoff;
generalization deferred); class C has no automatic execution environment
(`auto*` environment rejected); reviewer must differ from owner (forced
self-approval raises `DraftError`); denied runs record `not-started (denied)`.

## 2. State machine (draft-local, not an orchestration engine)

`draft → scoped → authorized → queued → running → result-ready →
independently-checked → human-review → accepted-as-evidence | rejected |
inconclusive`, plus terminal `quarantined | canceled | budget-exhausted |
superseded`. Transitions are allow-listed in `PROPOSAL_TRANSITIONS`; anything
else raises. Terminal states re-enter only via a new proposal id. Every
non-terminal state also transitions to `superseded` (loop cycle 1 fix,
matching the code change): an invalidation event never auto-rebases a draft
onto new inputs; the author starts a new proposal id instead. The earlier
table wrongly left `superseded` reachable only from `authorized`, which made
the "supersede result-ready drafts" mapping dead.

## 3. Mapping to the existing investigation ledger (no ledger writes)

| Draft state | Ledger effect |
|---|---|
| `draft` … `independently-checked` | None. Questions stay `open`; no snapshot exists. |
| `human-review` | None by itself; a human may then use the **existing** `create_snapshot` + `acknowledge_demo_review` path. |
| `accepted-as-evidence` | Metadata label only; `addressed` / `reviewed_in_demo` happen **only** through the existing human review path. |
| `rejected` / `inconclusive` / `canceled` / `budget-exhausted` | None; null/unknown retained, never collapsed into negative. |
| `quarantined` | Draft-side only; wrong-subject bytes remain owned by the existing `quarantine` table. |
| `superseded` | Draft-side; snapshot staleness remains owned by existing amendment/evidence/rights invalidation. |

Invalidation triggers that supersede drafts (pure mapping in
`invalidate_on_event()`): source amendment, evidence amendment/withdrawal,
rights revocation/correction, consent revocation (class B → quarantined, no
further runs), tool/model revision, specimen reassignment, cutoff change.
Two triggers have no current ledger counterpart and are paper-only (loop
cycle 1 note): no ledger operation reassigns a specimen (amendments cannot
change it; assets are immutable), and no case-consent table exists (inventory
consent values are descriptive only). They fire only if a future scoped
decision introduces such events; until then they must not be scored as
observed invalidations.

## 4. What was deliberately not done

No `ALTER TABLE`, no new core table, no migration helper, no import of these
drafts from `src/`, no graph store, no agent runtime, no background worker.
The conceptual "hypothesis graph" remains a view over versioned assertions,
tasks, runs, and provenance already owned by Open Intelligence.
