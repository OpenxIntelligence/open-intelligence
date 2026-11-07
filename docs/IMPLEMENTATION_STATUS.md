# Implementation slice 01 — source and investigation ledger

## Source-relay elapsed admission budget — November 7, 2026

Continuation of #626 at `a398f2401091b130fec0c38824b00511c7866abd`,
under OI-013 / PF-06. The existing `--drain` command accepts optional
`--max-seconds 1..3600` alongside its batch budget. A monotonic deadline stops
new admissions; active transactions retain their normal completion, leases,
receipts and authority checks. Failure results are preserved rather than hidden
by a budget stop. No migration, grant, dependency or additional state owner.

Tests first reproduced argparse's rejection of the new flag. After construction,
21 worker/schema tests and 31 architecture tests pass locally, as do the ownership
and independently fictional-data gates. The new real-PostgreSQL test exercises a
committed delivery, expiry before another claim, and actual CLI resume with one
receipt per delivery. PostgreSQL/Docker are unavailable locally; that test and
the complete inherited PostgreSQL/browser/recovery workflows require exact-source
hosted acceptance. Parent results are not substituted. Published source and
workflow results belong to the dependent draft's receipt; no merge or deployment.

**Current connected application:** use the [persistent fictional demo](H1_DEMO.md).
This dependent draft's PR records its combined revision, verification receipts
and landing status; [foundation #565](https://github.com/OpenxIntelligence/open-intelligence/pull/565)
remains the upstream owner.
[Consolidation #481](https://github.com/OpenxIntelligence/open-intelligence/pull/481)
records the original accepted application; the
[convergence record](engineering/H1_ACCEPTED_DEMO_CONVERGENCE.md) maps retained
contributions. The dated slices below are historical checkpoints; their old
draft labels, schema heads and test counts are not current acceptance claims.

**Stage:** local experimental synthetic-only code. **Not released for clinical use.**

## Current integrated H1 checkpoint

The recovery candidate in [#626](https://github.com/OpenxIntelligence/open-intelligence/pull/626)
builds on #613 at `6dc77e52342bee6928866bbda7680319600baf77` and retains
#625's bounded worker and isolated authority fixtures at
`8749cfa59622c36732a8604841b86bf8f8dd36cb`.
It adds `0028_source_delivery_retry` after the published 0027, preserving all
42 upstream migration files. Readiness requires 0028. An explicit current
`source_delivery_retry` grant authorizes recovery of one exact eligible failed
revision, with an immutable audit link; processing then rechecks authority and
current source context through the existing Composer consumer. The PR records
combined-source acceptance, including failures and skips. This candidate is
unmerged and undeployed; the full foundation and domain scope remains open.

### Preserved upstream composition checkpoint

This dependent draft composes the published #565 foundation frozen at
`462e6c25f805089fadcb290567045447e6d627b7`, the documentation-only successor of
`14a189a949510c67903eaf354250223a2c587a8f`, and preserves its 42 migration files,
including the original `0020_source_event_delivery` and the published
`0027_source_event_purpose`. That upstream composition introduced no 0028
migration; the recovery successor above now does. The canonical
clinical, laboratory, source, question, Composer, evidence, review and
follow-through owners remain intact.

| Input | Pinned source | Retained contribution |
| --- | --- | --- |
| Upstream #565 | `462e6c25f805089fadcb290567045447e6d627b7` | Clinical/laboratory convergence, encounter receiver and backup, evidence review, published 0027 purpose repair and owner receipts |
| #529 | `79960c49f356e7a4259484f5d1523f9bda365887` | Verified execution/event contribution and purpose-validation semantics; its edited historical 0020 file is not adopted |
| #559 | `adca9b8cacdbd2fe8b7ad82813d3e32a142841e8` | Latest-run recovery after amendment and the interrupted-relay browser journey |
| #569 | `d28f8dcb4124ccb52b42be28f996cc9e99a29c92` | Read-only assigned follow-up beside the exact selected laboratory result |
| Accepted main | `16fa42781aa40e3899e36b5b441de8d920fced8e` | Reference Skeptic/reconciliation, evaluation harness, vertical interface and data-integration modules |

At this upstream checkpoint the application required `0027_source_event_purpose`, whose single parent is
`0026_integrated_core`. The existing no-DDL 0026 join retains
`0025_clinical_source_events`, `0023_composer_clinical_join`, and
`0023_ehr_lab_ownership_join`. The published 0027 installs a binding resolver
and replaces capture/outbox guard functions: new operations and research events
undergo canonical lineage validation, then only operations creates a Composer
obligation. It rewrites no historical rows and performs no historical rescan or
backfill. Downgrade restores the earlier functions and removes the helper;
existing custody remains, while later research imports can fail until re-upgrade.

Compatibility is bounded to fresh databases and published 0026 installations.
Pre-0020 research journal history remains held by the original backfill, with
atomic rollback and preserved rows/sequence state. A separate legacy adoption
path remains open. The clinical receiver retains its separate event contract;
no service or dependency is added. The preserved published-owner checkpoint
below and [construction contract](implementation/SOURCE_EVENT_PURPOSE_REPAIR.md)
record that boundary.

**Evidence is source-specific.** The pinned #529 source passed
[878 API tests and all seven recovery gates](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42112478756)
and [155 focused execution/event tests](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42112478630),
with zero failures or skips. The focused suite is part of the full API suite;
these counts are not additive. Its populated delivery restore coverage is in
that focused suite, distinct from the complete recovery fixture's restored
outbox and empty delivery tables. The earlier #565 source `acf736082467ef5416f47951e3469090919be045`
ran [989 API tests with one research-import error](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42108825811);
the subsequent reference/browser/recovery stages within that full API run did
not execute. The separate tests-first purpose-repair failure below also remains
preserved. Neither donor nor earlier failed results qualify this composition.

Before adopting the concurrent published repair, local assembly `02f40eb84b3aedbcf25719fce55e06d8e0a2db38`
passed 1,036 reference tests, 704 client tests, 13 dependency-rights tests,
the client production build and 31 architecture tests. The ownership gate
reported 61 H1 modules, 10 owners and 86 declared legacy imports. Final checks
had no failures or skips; the initial optional-package notice failure was
resolved by matching CI's existing `--omit=optional` acquisition setting without
changing dependencies, lockfiles or rights controls. These are pre-reconciliation
receipts, not PostgreSQL or hosted acceptance of the current combined tree.

Combined migration/authority/execution, historical upgrade/rollback,
research-custody restore, built-browser journeys and all seven recovery gates
remain pending at this source-publication checkpoint. The isolated branch is
`integration/h1-workspace-event-continuation-20261106`; this dependent draft's PR
is the living ledger for its exact source/tree and artifacts. #565 retains the
upstream foundation and its separate acceptance history. Review, merge and
deployment remain separate. The entire PF-01–PF-10 / PD-01–PD-16 scope,
including #104's further workflow and mission-state contracts, remains open.

**Reference-only audit.** An exact archive of accepted main `16fa42781aa40e3899e36b5b441de8d920fced8e`
passed 1,006 local reference tests with zero failures, errors or skips. A separate
probe nevertheless confirmed that `record_extraction_proposal` can store a quote
absent from its original and a line beyond the original's length: its new checker
validates presence/shape, not exact text/location binding. The normal reference
report import obtains findings from `parse_report`; H1 uses unchanged
`open_intelligence.store` parsing helpers and does not call the proposal writer.
This is a scoped reference finding for its existing owner, not an H1 extraction
capability or resolved acceptance item. The live-model and full-vertical limits
in the preserved slice records below remain applicable.

## Shared foundation purpose repair — 6 November 2026

The current construction lane is [#565](https://github.com/OpenxIntelligence/open-intelligence/pull/565),
preserving its existing event, execution, laboratory, encounter and evidence
owners and accepted main `16fa42781aa40e3899e36b5b441de8d920fced8e`.
Its prior full API run failed one of 989 methods and skipped all seven recovery
stages: valid research source custody attempted an operations-only outbox write.

The tests-first source `dbb0bbb7f0a88b3d4f9b6ae283b8acb63cfca30b`
reproduces that exact failure on actual PostgreSQL 16 in
[run 42136266769](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42136266769):
five focused tests, one assertion failure and three lineage errors. The
pre-capture research-history upgrade hold passes with all owner rows and exact
sequence state preserved. This failed run establishes the regression; it does
not qualify the candidate for landing.

Repaired source `14a189a949510c67903eaf354250223a2c587a8f` passes all five
focused PostgreSQL methods in
[run 42136932694](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42136932694),
including the original research HTTP regression and populated upgrade/downgrade.
The earlier repaired run 42136728853 stopped at an incorrectly wrapped exception
assertion in the new downgrade test; the assertion now requires the raw pg8000
exception and exact lineage marker. Production function semantics are unchanged.
Full exact-head acceptance is recorded in #565 as it completes; the focused pass
alone does not establish full API or seven-stage recovery acceptance.

The repair uses a new `0027_source_event_purpose` successor to the published
`0026_integrated_core`. It validates every selected journal event before
filtering delivery to operations purpose. All published migrations remain
unchanged. The source recovery probe adds research original-byte custody,
dump/restore, exact retry and purpose-only denials through the existing HTTP API.
Exact repaired-head PostgreSQL, full API, browser and seven-stage recovery
acceptance must execute before this lane is qualified.

Compatibility is bounded to fresh databases and published 0026 databases.
Pre-0020 research history remains held at the historical backfill with atomic
rollback; a separate legacy adoption path is still required. See the
[active construction contract](implementation/SOURCE_EVENT_PURPOSE_REPAIR.md).
The PF-01–PF-10 / PD-01–PD-16 construction scope remains open. The next domain
increment extends the existing episode draft owner in #570 after the foundation
dependency is qualified.

## H1 source-event delivery — source-publication checkpoint, 5 November 2026

The existing [PR #529](https://github.com/OpenxIntelligence/open-intelligence/pull/529)
continues PF-06 / WS-08 / CMP-11 construction under
[#104](https://github.com/OpenxIntelligence/open-intelligence/issues/104). The
implemented candidate adds `0020_source_event_delivery` after `0019_composer_runs`:
canonical source-import journal events publish immutable reference obligations
atomically, and a separately invoked current-authority worker asks the existing
Composer owner to stale outdated queued/running work in batches of at most 100.
Transport owns no domain effects; current/terminal runs and human tasks retain
their owners. The existing source-freshness guards remain authoritative while
event delivery is idle, delayed or dead-lettered.

The construction baseline joins verified worker source
`2312755dc52260c3632c5801b1b7b68041671833` with accepted main
`aad241e5cce9a1bcff3e431d63cecd16e948d731` at
`cd10a828e499bf65dbbe8eb4ca77207710a5f2b7`. That lineage does not establish a
passing event-delivery candidate. Exact combined PostgreSQL, process-kill,
populated-restore and hosted regression acceptance remains pending at this
source-publication checkpoint; PR #529 records subsequent exact-source receipts.
See [the operating guide](engineering/H1_SOURCE_EVENT_DELIVERY.md) and
[implementation plan](superpowers/plans/2026-11-05-source-event-delivery.md).

This is foundation progress toward the entire PF-01–PF-10 / PD-01–PD-16 scope.
It adds no scheduler, broker, service-delegated authority, production database
roles, clinical effect or deployment. The dated execution and provenance
receipts below remain unchanged historical evidence.

## H1 execution foundation — accepted-main reconciliation, 5 November 2026

[PR #529](https://github.com/OpenxIntelligence/open-intelligence/pull/529)
continues foundation construction toward the entire Open Intelligence core.
It implements independent source/question contracts and one durable PostgreSQL
source-brief worker with current actor authority, exact source pins, bounded
leases/retries and immutable execution history. This is concrete foundation
progress, not completion of the PF/PD portfolio or the specialist engines.
See [the execution guide](engineering/H1_DURABLE_EXECUTION.md) for scope.

The candidate cleanly incorporates accepted main
`f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9` and accepted
[#527](https://github.com/OpenxIntelligence/open-intelligence/pull/527), preserving
its 13-file contribution and SQLite reference per-agent provenance writer.
The join introduces no migration and retains the existing H1 owners.

Pre-join source `24ebf806befa1f10ac0a4e78a13f7cd1a8e28a2f` passed
[43/43 focused PostgreSQL tests with zero skips](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42090201333),
including process-kill recovery, populated restore and security edge cases.
The merged candidate needs its own exact-source CI; this earlier result is not
a combined pass. This is a source-publication checkpoint. PR #529 maintains
current source/test receipts and landing status; no deployment or clinical
qualification follows from this increment.

## Provenance write contract (Slice 1) — 5 November 2026

Branch `program/slice1-write-contract`, from main `4b13bc2`. Implements
program-plan §5.4 (Notion OI-09 §5.4): the per-agent write contract, so
every agent/model write is attributable and replayable, or it is rejected.

New `src/open_intelligence/agent_writes.py` is the single owner of the
contract: `writeId`, `agentId`, `agentRole` (A1–A6), `agentVersion`,
`promptVersion`, `modelId`, `runId`, `routeId`, `snapshotAt` (L1 as-of:
ledger event anchor plus timestamp), `inputs` (source versions,
assertions, evidence assessments, each with a content hash), and
`toolCalls`. `CaseStore.save_investigation` stores no write without a
complete, validated contract bound to the same route and model, and
records it in the new `agent_writes` table in the same transaction;
`get_investigation` returns the full contract and `list_investigations`
carries `write_id`/`agent_role`/`route_id`. Pre-slice rows keep reading
with a null contract. `check_replay` re-reads every recorded input,
requires exact content-hash matches with source versions still current,
and re-validates the stored claims against the recorded input ids; a
superseded source version, changed input, missing input, route mismatch,
or tampered contract makes the replay not reproducible with a typed
reason. The HTTP investigation route builds the contract from the
ledger state the run read. New `tests/test_agent_writes.py` (24 tests):
rejection on every missing field, full contract stored, replay
reproduces the run, stale snapshot invalidates the replay.

Slice-1 mappings recorded in the module, provisional until later
slices: the single existing model call writes as A1 for every template;
`routeId` is deterministic (`route:<case>:<template>:<question>`) because
no `route.decided` record exists yet; `evidenceSnapshotId` carries an
evidence-assessment id; `toolCalls` is empty (no toolsets exist yet).
The case-packet builder does not yet surface the contract, and K-checks,
the Skeptic, and parallel role agents are later slices.

Local suite on the slice branch: 796 tests, FAILED with 9 failures and
8 errors — the same 17 `test_pdf_intake` failures (12 test names) as the
main baseline run on the same clone, caused by the missing local `pypdf`
installation; zero new failures. The pre-slice guard
`tests/test_case_switch_guards.py` passes on main (6 tests), confirming
the guard gap is closed with no guard slice needed. This is fictional-only
engineering, draft and undeployed.

## Deterministic K-checks K1–K7 (Slice 2) — 5 November 2026

Branch `program/c2-kchecks`, from main `f188aecc`. Implements
program-plan C2 (Notion OI-09 §4.6): the verification dimension's
deterministic half. New `src/open_intelligence/kchecks.py` is
domain-free — all vertical knowledge arrives as parameters — and
checks the claims the structural validator already kept: K1
identifier format (registry numbers, publication ids, object ids);
K2 slot–field match against the cited facets after normalisation,
plus the condition-scope sub-check (unrelated drops, broader/narrower
keeps with a limits note); K3 temporal (citing a version recorded
after the snapshot drops; internal version date order and slot range
order are run-level findings, not drops); K4 contradiction over the
survivors (same subject and field, different normalised value,
overlapping valid time, no supersession — the later claim drops;
different specimens or assays never auto-supersede); K5 staleness
(citing a superseded version drops with `k5_stale` instead of
`unresolved_citation`; citing a version outside the snapshot drops;
a changed snapshot hash or ruleset is a run-level finding); K6 scope
guard (the vertical's extra scope patterns beyond the language
guard); K7 support (every number, identifier, and named-substance
token must appear in the cited evidence; low-tier, case-report-only,
or preclinical support must carry the fixed limits phrase); K7+
injection (instruction-shaped markers in the claim or the cited
evidence drop the claim). Failures go to `dropped` with a typed
reason, never silently repaired.

Slot assertion is derived lexically: a claim asserts a (field, value)
pair when it names a derived field and, within two words, a value word
from the case's own value vocabulary after synonym normalisation.
The vertical wiring lives in `investigation.py`
(`ONCOLOGY_SYNONYMS`, `K6_SCOPE_PATTERNS`, `CONDITION_TERMS`) and is
passed into `validate_output` as an optional fourth argument — without
a context the behaviour is exactly as before. `store.source_version_facts`
supplies all versions (current and superseded); `__main__.py` builds
the context at both the live and replay call sites, and the HTTP
response carries the run-level findings as `kcheck_findings`
(returned, not persisted — persisting them is a schema change and a
follow-up). The condition-scope, named-substance, and evidence-tier
sub-checks are interface-complete but data-pending live (no relation,
tier, or substance data exists in the runtime yet), so they skip in
the live path and run in tests; no run snapshot is pinned yet, so the
snapshot-hash comparison is not supplied live either. K7+ atomic
statement (per-sentence derived-from ids) needs a schema and prompt
change and is out of this slice; free-text entity invention outside
the number/identifier/substance classes is not deterministically
detectable without a vocabulary and is the Skeptic's job (slice C4).

New `tests/test_kchecks.py` (66 tests): planted-defect fixtures per
check written from the Notion spec — K3 has three planted temporal
defects plus an as-of probe and partial-date probes; K4 has two
planted contradictions plus specimen, assay, supersession, and
valid-time fixtures; K5 has stale-version, hash-change, and
ruleset-change fixtures; K6 fixtures use only patterns the language
guard does not cover; K7 has invented-number, invented-id, tier, and
preclinical fixtures; K7+ has tainted-claim and tainted-evidence
fixtures; plus a vertical-leakage tripwire test that scans
`kchecks.py` for forbidden vertical literals.

Local suite on the slice branch: 889 tests, FAILED with 9 failures and
8 errors — the same 17 `test_pdf_intake` failures (12 test names) as
the main baseline run (823 tests) on the same machine, verified by
diffing the two failure sets; zero new failures. This is
fictional-only engineering, draft and undeployed.

## Deterministic orchestrator: assignment + roster (Slice 3) — 5 November 2026

Branch `program/c3-orchestrator`, from main `aad241e5`. Implements
program-plan C3 (Notion OI-09 §4): the coordination dimension's
assignment half — work is assigned to named agents by deterministic
policy, with a lease, before any agent event, and the roster (who is
doing what, busy/idle) is a queryable record. New
`src/open_intelligence/orchestrator.py` is code, not a model: it
decides routes, enforces assignments, and answers the roster; it
never calls a model and never writes to any ledger but the case's own
events table.

A route is decided by `decide_route` and recorded as a `route.decided`
event carrying `{templateId, agents[], reason, budget, authority,
scope, decidedAt, leaseUntil, policyVersion}`. Route policy v1
(`route-policy:1`) assigns A1 and only A1 for every template — the
single-writer bridge carried over from slice 1, since the one existing
model call still writes as A1; the policy function is the single place
that changes when parallel role agents land. Scope is derived from the
assigned roles' dimensions (A1 data-integration; A2/A3 analysis;
A4/A5 hypothesis-generation; A6 verification). Authority is the
account role that authorized the run — clinician or operator only
(#515 role permissions: a patient reads only their own bound case, an
auditor works no case route). The lease defaults to one hour and
bounds the run's execution window, not the historical record. The
budget records `{"maxModelCalls": 1}` and is not enforced on call
counts: the repair round in C4 will need a second call.

Enforcement: `save_investigation` rejects a write whose role is not
among the route's agents (`unassigned_agent`) or whose lease has
expired (`lease_expired`) — but only when a route record exists for
the route. A write whose route was never decided is not rejected at
save time (the pre-C3 grandfather path); the replay is the check that
catches it: `check_replay` now fails such a run with
`missing_route`, and fails a run whose stored role was tampered
post-hoc with `unassigned_agent`. The run path in `__main__.py`
decides the route before any agent event (model call in live mode,
fixture validation in replay mode), with the current account's role as
authority. The roster reads the ledger: an agent is busy while it
holds a live assignment — latest `route.decided` per route, lease
unexpired, no investigation stored for the route since the decision;
a re-decision supersedes, an expired lease lapses without completing.

New `tests/test_orchestrator.py` (25 tests): route decisions
(policy, authority, lease, supersession, scope validation);
assignment enforcement (assigned write accepted, unassigned rejected,
expired lease rejected, missing route allowed at save time,
route.decided precedes investigation_created); replay (with route
reproduces, without route fails, tampered role fails, expired lease
does not fail a replay); roster (all idle, busy on decision, idle
after completion, idle on expiry, busy again on re-decision, busy on
two routes). `tests/test_agent_writes.py` now decides a route in its
`save_run` helper and adds a missing-route replay test plus an HTTP
test that the run path decides the route before the investigation
event. Out of scope, per the plan: parallel execution of A1–A5 and
any model judgment in assignment.

Local suite on the slice branch: 916 tests (889 on main plus 27 new:
25 in the new file, 2 added to the write-contract tests),
FAILED with 9 failures and 8 errors — the same 17 `test_pdf_intake`
failures as the main baseline run on the same machine, verified by
diffing the two failure sets; zero new failures. This is
fictional-only engineering, draft and undeployed.

## Skeptic (A6) + one repair round + T6 reconciliation (Slice 4) — 5 November 2026

Branch `program/c4-skeptic`, from main `d1730c1d`. Implements
program-plan C4 (Notion OI-09 §4.6): the verification dimension's
agent half — a kept claim that cites a real source but misstates its
content gets a machine second opinion, a failing claim gets exactly
one chance to be repaired, and conflicts become typed, visible,
blocking records instead of silently merged.

New `src/open_intelligence/skeptic.py` is the Skeptic (role A6,
"Skeptic"): an independent model pass over the kept claims, same
model (`muse-spark-1.3`), separate prompt and prompt version
(`skeptic:1`), and no shared context beyond the claims under review
and their cited evidence — the prompt never sees the template, the
question, the other claims, or the author's reasoning, so it cannot
inherit the author's mistake. Verdicts are `supported` (kept),
`challenged` (held: moved to `dropped` with reason
`skeptic_challenged` — the claim text and the challenge are preserved
in the record, nothing is erased — and the run gets `AB-CONFLICT`
with origin `skeptic_challenge`), and `uncertain` (kept with
uncertainty raised to high and the reason appended to limits). The
model calls are injectable, so the test suite runs offline
deterministically; the live path is one bounded Meta Model API call
with one retry.

One repair round, live mode only, exactly once per run (one model
call for all repairable drops): only content failures a restatement
can fix are repairable (`k1_citation_format`, `k2_no_cited_facet`,
`k2_slot_mismatch`, `k7_unsupported_token`, `k7_tier_limits`). Not
repairable, by design: structural drops, `k4_contradiction`
(restating one side to match the other would be merging by rewrite),
`k6_scope` (rephrasing advice changes what the claim means), and
`k7plus_injection`. A repaired claim is re-validated end to end
(structural validation + K-checks); still failing, it is dropped with
the new check and reason. The repair record (original text, failure
reason, repaired text, re-check result) is stored visibly, never
silently.

T6 deterministic contradiction and gap grouping lives in
`src/open_intelligence/synthesis.py` (`group_run_contradictions`,
`group_source_contradictions`, `group_timeline_gaps`,
`group_timeline_conflicts`): the run's K4 drops, source-vs-source
disagreements over the case's assertion slots (same subject and
field, different normalised values, both versions current, neither
superseding the other, same specimen), timeline coverage gaps, and
timeline specimen/document date conflicts. A group lists both sides
and the evidence that would resolve it; it never merges dissent,
never re-labels a value, and never picks a winner. A superseded
version never joins a group (its disagreement is resolved by
supersession); different specimens never join a group.

Abstention codes, computed by `compute_abstention_codes` with one
firing rule each: `AB-CONFLICT` with origin `agent_divergence` (an
unresolved K4 contradiction between the run's own claims),
`source_disagreement` (a T6 source group intersecting the run's cited
sources), or `skeptic_challenge`; `AB-STALE` (a K5 finding or a
`k5_stale` drop — a stale run leaves the question open:
`save_investigation` does not mark it addressed); `AB-BUDGET` (the
verification call budget — one Skeptic call, one repair call per run
— was spent before a pass ran); `AB-MODEL` (a verification model call
failed or was schema-invalid after one retry); `AB-ALL-DROPPED`
(every attempted claim was dropped after repair and review).

Two deliberate decisions: a failed Skeptic or repair call does not
fail the run — the K-checked claims are still stored, with `AB-MODEL`
attached, so the gap is visible and blocking instead of losing the
whole run. And the run status is recomputed from the final kept set:
a repair can resurrect a run `validate_output` abstained, and the
Skeptic can hold a run's last kept claim (flipping it to abstained).
Replay mode skips both model passes and records the skip; T6
grouping and abstention codes still run, because they are
deterministic.

Persistence follows the C1 precedent: a new `verification_records`
table (one row per investigation, holding the Skeptic verdicts, the
repair record, the T6 groups, and the abstention codes as JSON); the
`investigations` table is unchanged, so pre-slice rows keep reading
with a null record. The run path in `__main__.py` runs verification
after K-checks and before storage, in live and replay mode, and the
record is stored in the same transaction as the investigation and
returned in the response alongside `kcheck_findings`.

New `tests/test_skeptic.py` (31 tests): the Skeptic prompt contains
only the claim and its cited evidence (independence); the planted
misstatement "31 cm" against evidence "31 mm" passes K1–K7 and is
caught by the Skeptic; supported/uncertain verdicts keep the claim
with the right uncertainty and limits; Skeptic failure records
`AB-MODEL` and keeps the claims; budget exhaustion records
`AB-BUDGET`; the repair round fixes a fixable claim, never runs
twice, drops an unfixable claim and a restatement that still fails,
and is never attempted for K4/K6/K5 drops; the full abstention-code
set; replay skips the model passes but still reconciles; T6 groups
never merge or vote; the verification record persists and a stale run
keeps its question open.

Local suite on the slice branch: 947 tests (916 on main plus 31 new),
FAILED with 9 failures and 8 errors — the same 17 `test_pdf_intake`
failures as the main baseline run on the same machine, verified by
diffing the two failure sets; zero new failures. This is
fictional-only engineering, draft and undeployed.

Unproven: the live Skeptic run. Two live calls against the Meta Model
API (the planted "31 cm" misstatement and the "31 mm" control) both
returned HTTP 402 "Billing verification failed" from api.meta.ai — the
key's team has a billing issue to resolve at dev.meta.ai/billing, so
no live model call could run. The prompt is verified only through the
stub-driven test suite; a live run proving the real model catches the
planted misstatement is pending that billing fix, and no substitute
model was used. No spend was incurred on the Meta budget.

## Evaluation harness: planted-defect suites + M-metrics (Slice 5) — 5 November 2026

Branch `program/c5-evaluation`, from main `cc713bd`. Implements
program-plan C5 (Notion OI-09 §9): the evaluation primitive —
verification quality is measured by code, not asserted in prose.

New `src/open_intelligence/evaluation.py` is a deterministic,
offline harness (no live model call anywhere; every report carries
`model_calls: 0`). It runs the planted-defect fixtures from C2/C4
through the real pipeline code — structural validation, the
deterministic K-checks, the Skeptic wiring, T6 grouping, and the
replay check — and computes the M-metrics of OI-09 §9.2 that are
measurable offline: M5 planted temporal-defect recall (five planted
defects: cite-after-snapshot, specimen-after-report,
report-after-received, range-start-after-end, partial-date violation
at coarser precision); M6 contradiction recall/precision (two
planted same-specimen contradictions plus five negative controls —
different specimens, different assays, supersession,
non-overlapping valid time, same value); M7 staleness recall
(superseded citation, out-of-snapshot version, changed snapshot
hash, changed ruleset); M8 advice-language leakage (eight planted
scope violations, target 0 kept); M10 hypothesis support (six
hypothesis probes: invented number, invented registry id, invented
substance, low tier with and without the limits phrase, supported
number); M16 replay determinism (one intact run replayed three
times, identical, plus three tamper probes — missing route, amended
source, tampered assertion — that must each fail replay with a typed
reason); M27 routing record completeness (exactly one
`route.decided` before the run's agent events); M28 hypothesis
citation recall (a deterministic prose-attribution check over
numbers, named substances, temporal words, relation verbs, and
hyphenated entities — it catches what K7 cannot, such as an
unsupported relation verb on a supported number: "The lesion
increased to 31 mm" passes K7 and fails M28). Each metric is
reported with value, n, target, and pass/fail against the Proposed
targets; failures are listed as limits, never hidden. The Skeptic
wiring probe drives `run_verification` with injected stub verdicts
(the planted "31 cm" misstatement held with AB-CONFLICT origin
`skeptic_challenge`; "31 mm" kept on a supported verdict) — it
proves the wiring, not the model. The human spot-check (≥30 items)
remains a manual protocol: the harness records the spot-check set
built from its own probe items (51 items, complete, labels pending)
and does not perform it. Model-dependent metrics (M25 model-judged
entailment, M26 Skeptic challenge precision, M29 citation
precision) are listed under `not_measured` with their reason. The
harness measures; it never gates — nothing in it decides whether a
run, claim, or hypothesis is accepted.

Two mappings are documented in the module because the Notion
labels and the codebase differ: `SOURCES_DISAGREE` has no literal
in the codebase, and is surfaced as a T6 contradiction group plus
AB-CONFLICT with origin `agent_divergence`; and the §9.2 metric
definitions are written for live runs, so the harness scores the
same check as judgment accuracy over planted supported/unsupported
probes — the planted-defect reading M5/M6 already use. The
fixture context mirrors the C2/C4 fixture shapes (same version ids,
dates, quotes, and slot values), and the vertical wiring (synonyms,
scope patterns, condition terms, substance names) arrives as
parameters to `fixture_context` — the check logic holds no vertical
knowledge, and the parameters are the seam the V1 vertical
interface will use. A `main()` runner prints the JSON report and
exits 0 only when every metric meets its target.

New `tests/test_evaluation_harness.py` (25 tests): every metric at
its target on healthy code; the sensitivity tests (a weakened K3
fails M5 and the suite; a weakened K4 fails M6; a weakened K7 fails
M10 — the harness is proved able to fail); M28 catching the
relation verb, temporal word, and unknown entity K7 misses; the
spot-check threshold (30 complete, 29 incomplete); the report shape
and the live-model gap recorded as a note.

Local suite on the slice branch: 972 tests (947 on the C4 branch
head plus 25 new), FAILED with 9 failures and 8 errors — the same
17 `test_pdf_intake` failures as the baseline run on the same
machine, verified by diffing the two failure sets; zero new
failures. This is fictional-only engineering, draft and undeployed.

Unproven: the live-model half of the metrics. M25, M26, and M29
need live runs (and, for M25, human labels); the Skeptic's live
proof is pending the same Meta billing fix as slice C4 (HTTP 402).
No live call was attempted here and no substitute model was used.

## Vertical interface: the oncology boundary (Slice V1) — 5 November 2026

Branch `program/v1-cardiology`, from main `004a5cd`. Implements
program-plan V1: the core holds no oncology knowledge; oncology lives
behind the vertical interface. This is the slice that makes
"multi-vertical" real instead of aspirational.

New `src/open_intelligence/vertical.py` is the interface and the
registry: a `Vertical` dataclass (synonyms, condition terms, scope
patterns, line-of-therapy ruleset version label, evidence kinds and
link templates, toolsets, substance names); `register_vertical`,
`get_vertical` (which lazy-loads a built-in definition module by
name — the core never imports a vertical definition module by name),
`default_vertical`, `list_verticals`; and `build_scope_patterns`, the
one place the nine K6 patterns are assembled from a vertical's own
condition terms, so every vertical's guard has the same shape.

New `src/open_intelligence/vertical_oncology.py` is the oncology
vertical: content moved verbatim from `investigation.py` (slice C2)
— the synonyms map, the condition terms, the scope patterns via the
builder — plus the ruleset version label `lot-rules-1` and the
evidence kinds and link templates (the same values as
`evidence_catalog.py`). No rule's content changed, only its location.

New `src/open_intelligence/vertical_cardiology.py` is the minimal
synthetic cardiology vertical — V1's stub vertical, made concrete:
cardiology-distinctive synonyms ("not performed", "seen",
"identified"), cardiology condition terms, the therapy-ruleset label
`therapy-rules-1`, and ECG / echocardiogram / cardiac-lab evidence
kinds. No guideline text is ingested; no real cardiology data is
used. The full cardiology vertical (domain toolsets, the
investigation dimensions against cardiology fixtures, the care loop)
remains slice V2, after the dimensions exist.

Core rewiring: `investigation.py` no longer defines the predicates
(a comment points at the interface); `__main__.py` resolves the
default vertical and passes its predicates — plus its ruleset label
as both the facts-time and validation-time ruleset — at the single
K-check-context call site shared by the live and replay paths;
`evaluation.py`'s `fixture_context` defaults resolve through the
registry. `kchecks.py` is untouched: it was already domain-free.

What did not move, and why: the structural language guard stays in
`investigation.py` — it is domain-free advice language (no vertical
literal appears in it) and the vertical's own language contribution
is its K6 scope patterns; the model prompt still names the synthetic
oncology case (prompt templating per vertical is future work);
`store.py`'s oncology report format is a data-format concern,
untouched; the evidence catalog still validates against its own
constants — the oncology vertical declares the same kinds and
templates, and the boundary test binds the two, while per-vertical
catalog resolution is V2 work. Cases carry no vertical yet, so
`default_vertical()` is the documented pre-V2 default; a
case-vertical field is the follow-up that retires it.

Brief discrepancy, recorded honestly: the task brief described V1
as "synthetic cardiology end-to-end, zero core files changed". That
is the plan's V2 acceptance, not V1's. V1's defined work is the
interface, which necessarily touches core files (the interface
module itself, the rewiring, the oncology relocation). The
addability falsifier did not fire: the cardiology vertical itself
landed with zero additional core changes beyond the interface — one
new module plus its tests. The full V2 proof (zero core changes for
the whole slice) still follows after D1–D9.

New `tests/test_vertical_boundary.py` (14 tests): the import-graph
tripwire (no core module imports a vertical definition module; the
dimension checker is proved against a fake graph while the dimension
list is still empty); registry tests (resolution, legacy content,
duplicate/invalid/unknown names, a runtime stub vertical, the
default); the scope-pattern shape test (the eight generic patterns
identical, only "you have" differing by condition terms);
cross-vertical discriminators (a cardiology synonym resolves where
oncology's does not; "you have heart failure" drops under
cardiology and passes under oncology, and the reverse for "you have
cancer"); and the cardiology end-to-end (route decided, K-checks,
stub Skeptic holding the planted "31 cm" misstatement against "31%"
evidence, T6 source group on rhythm, AB-CONFLICT origins
`skeptic_challenge` and `source_disagreement`). `test_kchecks.py`
and `test_skeptic.py` now resolve the oncology wiring through the
registry (import lines only; no fixture changed), and the tripwire
comment in `test_kchecks.py` points at the new location.

Local suite on the slice branch: 986 tests (972 on the post-C5 main
baseline plus 14 new), FAILED with 9 failures and 8 errors — the
same 17 `test_pdf_intake` failures as the baseline run on the same
machine, verified by diffing the two failure sets; zero new
failures. The evaluation harness runner still passes all 8 metrics
at target with `model_calls: 0`. This is fictional-only
engineering, draft and undeployed.

Unproven: the live-model half is unchanged from C4/C5 — the Meta
billing fix (HTTP 402) is still pending, so the cardiology
end-to-end uses stub verdicts and proves wiring, not the model. No
live call was attempted here and no substitute model was used.

## Data-integration dimension: A1 Intake & Extraction + T3 specimen chain (Slice D1) — 5 November 2026

Branch `program/d1-data-integration`, from main `97e2be7`. Implements
program-plan D1: the data-integration dimension as its own modules
with its own tests and acceptance bar, against the vertical interface
V1 defined. Domain rules come through the interface, never hard-coded
in the core: the A1 certainty set and finding-key pattern are the
ledger's own (domain-free), and the T3 chain rules are the ledger's
asset rules; no vertical module is imported by either new module.

New `src/open_intelligence/extraction.py` is A1, the deterministic
anchor checker (Notion OI-09 section 5: "one anchor checker").
`validate_extraction_proposal` takes a proposal — a list of fields,
each naming a finding key, a certainty, a verbatim quote, and the
exact source line — and returns kept/dropped with typed reasons in
the same shape as the structural validator. The source version is
proposal-level: it must exist, belong to the case, and be `current`,
or every field drops with `unknown_source_version`,
`wrong_case_source_version`, or `superseded_source_version`. Each
field is then checked on its own: `invalid_finding_key`,
`invalid_certainty`, `missing_quote`, `quote_too_long`,
`invalid_source_line`, `malformed_field`, `duplicate_finding_key`,
`finding_already_asserted`. `record_extraction_proposal` validates
and stores the kept fields as assertions, joining the caller's
transaction when one is open and opening its own otherwise. The
report-import path (`store._import_report_in_transaction`) routes its
parsed findings through the checker, so the checker is on the live
arrival path; a drop there fails the import instead of silently
dropping a finding (unreachable while `parse_report` holds the same
rules). PDF, C-CDA, and FHIR arrivals route through it as their
import paths land.

New `src/open_intelligence/specimen_chain.py` is T3, the deterministic
specimen chain (Notion OI-09 section 5: "SpecimenChain links with
basis"). `validate_specimen_chain` walks the parent-linked lineage of
one biological asset from the queried asset back to its original and
returns the links root-first, each carrying its assay/specimen
context (kind, episode, specimen id and state, observed date, and the
anchor source version with its document, version, and state), plus
every break as a typed record — never silent, never a raised
exception for a broken chain: `missing_asset`, `missing_parent`,
`cycle`, `unknown_specimen`, `specimen_mismatch`,
`anchor_missing` / `anchor_superseded`, `episode_mismatch`, and
`kind_violation`. Creation-time invariants (same-episode parents,
allowed parent kinds, current anchors) are enforced by
`add_biological_asset`; the validator also checks them on read, so a
break introduced after creation — a superseded anchor, a specimen
recorded under a different id — is caught here. No route or write
gate is added: chain breaks are typed records, not rejections, per
the D1 acceptance. The first live caller is D3's comparison
toolsets, which consult the validator before comparing across
specimens; the bio-assay observation path already enforces specimen
matching for a single block at write time.

Orthogonality: the import-graph tripwire in
`tests/test_vertical_boundary.py` now lists the two D1 modules in
`DIMENSION_MODULES`, and the tripwire is green. One correction was
needed to make the rule mean what it says: as written, the checker
flagged *any* module importing a dimension module, which would have
made the dimension unusable — the shared core must be able to call
it (that is how the A1 checker reaches the live import path). The
checker now constrains only dimension modules themselves: it flags
a dimension module importing another dimension module, which is what
the orthogonality rule forbids. The fake-graph proof still passes
unchanged.

What did not move, and why: no vertical predicates were moved or
added (the certainty set and key pattern are domain-free ledger
rules); modality schema packs are out of scope (they arrive with
D2); the K-checks, route, Skeptic, and evaluation harness are
untouched; no live model call exists anywhere in the slice.

Local suite on the slice branch: 1006 tests (986 on the post-V1 main
baseline plus 20 new), FAILED with 9 failures and 8 errors — the
same 17 `test_pdf_intake` failures as the baseline run on the same
machine, verified by diffing the two failure sets; zero new
failures. This is fictional-only engineering, draft and undeployed.

Unproven: the live-model half is unchanged from C4/C5 — the Meta
billing fix (HTTP 402) is still pending, so no live call was
attempted here and no substitute model was used. The dimension is
deterministic code; nothing in it needs a model call.

## Connected patient preparation — 3 November 2026

Draft [#288](https://github.com/OpenxIntelligence/open-intelligence/pull/288)
continues [#287](https://github.com/OpenxIntelligence/open-intelligence/pull/287)
at `247705700080052705817fee9e8f7b54afa8ffaa`, retaining its API, recovery,
source and review owners unchanged. It brings #286's Overview onto that shared
workflow and fixes a hosted-browser-reproduced contextual-navigation defect:
prepared packet/brief views must clear when leaving a section through any link.
The authored draft and exact uncertain-return intent remain intact.

The combined browser acceptance resumes one authored question through Overview,
inspects its original source, records a nonterminal verification return and
performs a fresh authorized download. Current/unreviewed and source-reassessment
counts retain their last-read and clinical limitations. This advances OI-007,
OI-009 and OI-010; it does not complete biomedical investigation or clinical review.

Local candidate checks: 178 client tests and locked build pass; the notice gate
passes. API discovery runs 301 methods, with 51 passing and 250 explicitly skipped
because PostgreSQL is unavailable locally. Final hosted exact-head acceptance,
review and artifact inspection belong in #288's verification receipt. See
[patient continuity behavior and evidence](engineering/H1_PATIENT_CONTINUITY.md)
and the existing [shared project assessment](project-state/PROJECT_STATE.md).
This remains fictional-only, draft, unmerged and undeployed.

## Historical audit — 2 November 2026

### H1 source intake and record receipt final authority — draft #265

This continuation uses verified canonical source/question owner #244 at
`3b6c466950852c20f99d57a70dd196fd2862571a`. The existing source-import and
record-receive methods now prepare their JSON receipt and refresh the original
bearer's independent grants under their original transactions. Denied imports,
amendments, quarantine and received-pointer writes roll back; duplicate/history
paths also refresh authority before returning their source identity. No source,
request, evidence or review owner is duplicated, and no migration/dependency is
added. The separate active review and source-brief owners remain #262 and #264.

Twelve new actual PostgreSQL/HTTP regression methods supplement the existing
gates. Hosted tests-first runs reproduced missing final checks and response
preparation after commit. A generic renderer-hook mistake was corrected using
the pinned FastAPI serializer's actual path; the failure history remains recorded.
Local checks execute 42 API tests and explicitly skip 162 database executions;
they are not PostgreSQL acceptance. Final exact-head API/migration/recovery and
built React/Chromium evidence belongs to
[PR #265's verification receipt](https://github.com/OpenxIntelligence/open-intelligence/pull/265).
See the [existing source receipt documentation](engineering/H1_CANONICAL_RECORD_SOURCE_RECEIPT.md)
for behavior and limits. This is fictional-only engineering, draft and undeployed;
external grant revocation and network delivery are not atomically coupled to PostgreSQL.

### H1 canonical patient identity integration — issue #112

The audited default main was
[24519839aa8ac1ea3aff88a956349ba72798a72a](https://github.com/OpenxIntelligence/open-intelligence/commit/24519839aa8ac1ea3aff88a956349ba72798a72a).
Existing domain work remains spread across unmerged drafts. Passing a source
branch does not establish that its behavior is on main or combined with other
branches.

The [apps/api integration](../apps/api/README.md) is based on #162 head
62d2ad0dd2c2d581f9d13d7659f888265838a4f0, which itself depends on #137's
synthetic-only safety correction. Its source-owned identity port comes unchanged
from #148 at 19b1c1319ba543fd0e93744ea3425bd861b0f233. The API shell owner's
concurrent network/startup corrections were retained; an overlapping local draft
was discarded. No source branch is replaced or self-merged.

| Capability | Source / ownership | Actual state and verification | Remaining gap |
|---|---|---|---|
| Canonical patient registry | #85; unchanged patient_registry.py blob 7edade0e13d81eebc4ffeac1a19beeb6c241cb3e | Existing first-party domain reused, not reimplemented | Merge/review dependency remains |
| PostgreSQL identity persistence | #148 at 19b1c131; original port and receipt SQL retained | Identity-only Alembic migration tested on PostgreSQL 16.15, including immutable receipts, atomic failure, downgrade/re-upgrade and collision refusal | Broader experimental #145 schema is not promoted |
| H1 patient HTTP | New integration/h1-pg16-patient-registry-20261102 branch, stacked on #162 | 49/49 API/migration/gate tests, zero skips; create/retry/read, org/grant denial, expiry/revocation, bounded inputs, concurrent retries and connection-loss cleanup | Synthetic fixture authority only; no verified accounts, consent, RLS or production service-role qualification |
| Existing source/evidence/investigation prototype | Preserved Python/SQLite application on #137 safety base | 245/245 existing tests passed on combined local checkout | These contracts are not yet mounted on H1 PostgreSQL |
| EHR / LIS / event / clinical spine | #74 / #56 / #70 / #89 / #95 | Active source owners preserved; separately implemented/unmerged candidates | No claim of this H1 patient API being connected through encounters, orders, specimens, results or PWM |
| Biomedical rights / Composer / source corrections / review | Existing #93 and integration branches | Existing implementations and research retained | No new live knowledge retrieval, model execution or clinical review through H1 |
| Container persistence/recovery | H1 workflow and verify_registry_compose.py | Acceptance implements real HTTP, API + DB restart, dump/restore and revocation; hosted exact-head result must be read before claiming success | Docker/Chromium unavailable locally |
| React/Vite workspace | #119 and existing UI candidates | Accepted frontend target; no new UI in this bounded backend integration | Bind existing UI to canonical patient/source APIs |
| Artifact rights | Unchanged inventory, lock, notices and gate | 24 exact wheels checked; 99 supplier native and 13 embedded-runtime entries recorded as separate evidence scopes | Full image/distribution, Mako inherited label and native link-map holds remain |

The source shell's final [hosted run #41530234376](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41530234376)
passed its 26 API tests, 245 prototype tests, both Chromium journeys and
health-only Compose/API-restart checks. Those results belong to #162; the new
patient/restore acceptance requires its own exact-head run.

Independent review reproduced two defects before correction: a same-name weaker
identity schema could be silently adopted, and rollback failure could bypass
explicit connection release. The new migration preflight stops for reconciliation;
nested cleanup guarantees close. Both meaningful regressions passed, and the
reviewer confirmed the fixes. A Dockerfile-specific ignore also bounds build
context after its move to the repository root.

### Audit coverage and next connection

GitHub remains the source of code/CI truth; the accepted Notion/Drive H1 decisions
select PostgreSQL 16 and React/Vite/TypeScript. The #148 PostgreSQL 17/18 matrix
is research evidence, not approval to change that H1 target. No new stack,
patient ledger, task system or model gateway is introduced.

This is bounded audit coverage. Historical patient-data artifacts were not
opened or reproduced. Existing #137 safety controls and the static CI
data-boundary scanner were retained. A passing scanner does not prove every
historical artifact or arbitrary network behavior is safe. No identifiable
patient record was acquired for this integration.

The four rights registers remain separate. CIViC curated content, NLM/PubMed
metadata/abstract distinctions, ClinicalTrials.gov access terms and NCI reuse
rules are active research records, not implemented connectors or automatic
commercial clearance. NCCN content remains disabled pending specific rights.

**Next executable work:** reconcile canonical patient IDs and source bindings
with #89/#95/#148, mount one scoped source acquisition/version contract in H1,
and prove correct-patient binding, original/version preservation and bounded
amendment invalidation before connecting the #119 React workspace. Existing
EHR/LIS/events, PWM, evidence, Composer and review owners supply subsequent
interfaces. Full M-H1-0, MRT-01, MVP, deployment and clinical validation remain
incomplete.

The dated slice reports below are preserved as history; their absence statements and next-step lists are not a current inventory. The inspected application baseline was main [`52ea683`](https://github.com/OpenxIntelligence/open-intelligence/commit/52ea683fbe3537b17a05066dceff2ba01f758c5d): **236 synthetic application tests passed locally**, with loopback HTTP servers and mocked/fixture external transports. Subsequent main [`24519839`](https://github.com/OpenxIntelligence/open-intelligence/commit/24519839) adds the no-personal-case-data policy and CI blocking changes; those changes do not establish a newly passing application baseline.

Inspected code includes `CaseStore` source/evidence versions, questions, snapshots, discovery/rights links, options/preparation tasks, biological assets/inventory, bounded model-investigation receipts, and mission/timeline/change projections. `patient_access` supplies a synthetic gate with in-memory bindings, not production authorization. Replay exercises the investigation contract; this audit did not reverify live model operation. Current runtime is Python/SQLite and vanilla JavaScript; the accepted H1 target is Python/FastAPI/PostgreSQL plus React/Vite/TypeScript, excluding Next.js.

**Unmerged draft candidate [#136](https://github.com/OpenxIntelligence/open-intelligence/pull/136):** `save_investigation()` preserves question state instead of automatically marking even an abstained or unreviewed attempt addressed. Four focused tests passed after first reproducing the failure, including restart, mission/HTTP visibility and preserved scoped demo acknowledgment. The isolated lifecycle branch passed **240 application tests** at [`94176658`](https://github.com/OpenxIntelligence/open-intelligence/commit/94176658fe126647aaeea83886bff1ccf776aae8). Existing addressed history is unchanged. This is not a merged capability or clinical review system.

**Data-policy integration candidate:** current main plus reconciled CI/runtime retirement passed **245 application tests** and **204 research tests (191 passed, 13 optional HDF5 tests skipped locally)**. CI retains current main's pinned scientific dependencies to exercise those optional helpers. The static guard and receipt have nine regression tests; they do not prove arbitrary runtime network behavior. These counts belong to the isolated candidates, not to a tested combined platform. See the [bounded work-package record](engineering/PATIENT_DATA_CI_BOUNDARY_2026-11-02.md); hosted run evidence belongs in its review PR.

### Integration sequence: reuse unmerged candidates

These are integration candidates, not a verified combined product. Check each current head and dependencies before adoption; retain one canonical identity/source/evidence history.

1. Integrate the reviewed main-based data-policy cleanup, preserving the founder prohibition without manual overrides. Re-run the applicable offline suites at the resulting exact commit.
2. Review durable access bindings in [#53](https://github.com/OpenxIntelligence/open-intelligence/pull/53) alongside registry/EHR/LIS integration in [#95](https://github.com/OpenxIntelligence/open-intelligence/pull/95), reusing their constituent domains. Prove restart, revocation, case binding and source-version integrity before widening access.
3. Reconcile Composer/integration candidates [#126](https://github.com/OpenxIntelligence/open-intelligence/pull/126), [#130](https://github.com/OpenxIntelligence/open-intelligence/pull/130) and [#132](https://github.com/OpenxIntelligence/open-intelligence/pull/132) against those contracts. Preserve source-bound run receipts and reviewable proposals; test interruption and retries without duplicate mutations.
4. Review the question-lifecycle fix in [#136](https://github.com/OpenxIntelligence/open-intelligence/pull/136) alongside existing review/staleness work (#82/#91), then goals/follow-through (#80/#84). Project accepted state through Patient Mission rather than adding another ledger.
5. Exercise the [eight-circumstance portfolio](FIRST_PRINCIPLES_PLAN.md#workflow-crosswalk-and-synthetic-portfolio--2-november-2026) through import, domain event, question, proposed investigation, explicit review and subsequent correction. Record each supported boundary and failure; passing separate PR suites is not combined-workflow validation.

## Historical slice scope — 31 October 2026

**Backlog coverage:** Part of OI-003, OI-006, OI-007, OI-009 and OI-010. Does not complete the broader investigation/evidence stage (OI-008), identity/governance (OI-012–013), or clinical evaluation (OI-014 onward).

## Behaviors built

- Strict import of independently authored `OI-SYNTHETIC-REPORT/1` UTF-8 bytes; explicit report identifier, subject, event date, issued date, specimen, finding quotation, and status.
- SQLite persistence of original source bytes and SHA-256, per-document version history, source-line anchors, atomic amendment invalidation, and idempotent same-bytes import.
- Wrong-subject quarantine; no assertions created for the requested case or the declared other case.
- Persistent questions, source-version-bound human-authored investigation drafts, demo-only acknowledgment, stale-on-amendment, and Markdown export including full source versions.
- Deterministic, read-only Patient Mission projection over the canonical case state, exposed at `GET /api/cases/{CASE-ID}/mission` and rendered in the existing portal.
- Patient Mission workflow status, source-linked reported statements, unresolved source states/questions, amendment/invalidation/quarantine changes, and only those next actions supported by the current demo.
- Local browser UI, served on `127.0.0.1` only, with no external assets or network-based research integrations.
- Plain Python `unittest` coverage for evidence and case boundaries, amendments, duplicate bytes, source recovery, the local HTTP surface, the Patient Mission projection, and static UI contracts.
- Two dependency-free headless Chromium journeys: the full synthetic source/evidence workflow and the Patient Mission case-switch/amendment workflow.

## Important unproven areas

- Local demo accounts, roles, and sessions now exist (operator / clinician / patient read-only on their own case / auditor; operator-created accounts only; 24-hour server-side sessions; case routes require a live grant plus role permission; access decisions are logged and readable by operator/auditor). These are local demo labels, not verified identities — there is still no authenticated identity, consent, delegation, production access control, auditing suitable for real patients, or full security assessment. The safety packet still needs a refresh for this change.
- No PDF/OCR, automated clinical assertion extraction, FHIR/mCODE exchange, biological or imaging analysis, medical literature appraisal, trial searching, model inference, or provider integration.
- No independent professional review; demo acknowledgments are explicitly labeled and do not establish clinical correctness.
- The Patient Mission panel is a workflow projection, not a patient summary, diagnostic assessment, treatment plan, safety monitor, trial matcher, care coordinator, or clinical decision-support system.
- The source format is deliberately artificial to make deterministic boundaries testable. It must not be described as a general clinical importer.
- The application has no user-selectable release license yet. Before licensing or distribution, select a license and audit dependencies/assets (none intentionally incorporated beyond the Python standard library in this slice).

## Next bounded work

1. Establish a reviewed real-world workflow contract without using real patient data, including identity, consent, authority, and correction semantics.
2. Add source-to-assertion extraction as explicitly reviewable proposals from a specified document type while maintaining exact spans and amendment propagation.
3. Expand the Patient Mission projection only through separately specified capabilities such as goals, medications, specimens, safety escalation, access, execution, and outcomes; do not turn the projection into a second ledger.
4. Implement an evidence item with true source content, permission metadata, applicability review, and immutable retrieval receipts. Keep publisher rights separate from discovery metadata.
5. Compare the local case-domain implementation with the candidate Medplum/FHIR boundary using the same amendment, quarantine, case-isolation, and stale-response tests.

No milestones should be marked complete solely because an interface displays the correct-looking data.

## Independent verification — 31 October 2026

This verification covers the local synthetic-only source-ledger slice, **not** clinical fitness, privacy compliance, external evidence, or a public deployment.

- Regression hardening: repeat wrong-case submissions are idempotent; Markdown source content remains contained in safe export fences; the HTTP server rejects non-loopback Host values to limit DNS-rebinding risk; the browser discards stale responses following case switches.
- Mobile layout: the navigation rail's intrinsic track size caused horizontal overflow at 390 px; constrained the outer grid and its rail/main children. This was a real defect caught by the browser test.
- [GitHub Actions run #41221419037](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41221419037), commit `17f249ec085a08769a3386c454de18e3442b7883`: **pass**, Python compile, 18 unit/HTTP tests, and dependency-free headless Chromium journey.
- Browser journey verified: fictional Alpha source drilldown, switch to independent Beta and back, create a question, save source-linked draft, demo-only review acknowledgment, import amended pathology, stale previous snapshot and reopened question, preserve original source in export, and 390 px responsive containment.
- Tooling: Python 3.13 standard library, Chromium on GitHub's Ubuntu runner; no new runtime packages, medical data, services, scripts from vendors, or AI model weights incorporated.

**Remaining open evidence:** keyboard-only focus/operation and assistive technology testing, actual mobile-device testing, robust source-review and concurrency adversarial review, realistic ingestion, authentication and patient permissions, legal/build artifact clearance, clinical adjudication. Headless Chromium is not a substitute for clinical validation or a formal security audit. PR #1 should remain unmerged until the tracked review requirements have been resolved.

## Patient Mission projection verification — 31 October 2026

This verification covers one complementary Patient Mission Portal slice. It does not establish the broader Open Intelligence patient portal, diagnostic system, therapeutic-development system, care-realization system, or clinical safety.

- Test-first proof: run `41269640207` failed because the projection module did not yet exist; run `41269841287` failed because the mission endpoint did not yet exist; run `41270022603` failed because the mission renderer did not yet exist.
- Pure projection verification: empty cases do not invent state; current synthetic assertions retain source version and line; unresolved source states remain explicit; malformed event JSON is ignored rather than guessed; amendment-driven staleness is limited to dependent investigations; Alpha data does not leak into Beta.
- HTTP verification: the case-scoped mission endpoint returns the deterministic projection, unknown cases follow the existing `422 Unknown case` boundary, and unexpected Host values are rejected before case access.
- Portal verification: the Patient Mission surface shows workflow status, counts, current source statements, unresolved items, material changes, bounded next actions, and guardrails without mutating the ledger.
- Browser verification: the panel follows Alpha → Beta → Alpha case selection, discards stale responses, avoids cross-case source text, and moves to `Review required` after an explicit source amendment invalidates a bound investigation.
- [GitHub Actions run #41270150297](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41270150297), commit `8f6d915c1e92c8250c3e236663aa329157fc258d`: **pass**, Python compile, JavaScript syntax for both renderers, 49 unit/HTTP tests, the original browser journey, and the Patient Mission browser journey.
- No new database table, third-party dependency, model provider, network service, real patient datum, clinical assertion, treatment recommendation, or autonomous side effect was added.

**Remaining open evidence:** real identity and consent, PHI-grade access controls, realistic clinical ingestion, professional adjudication, uncertainty calibration, medication and acute-safety workflows, care-team collaboration, trials and access, therapeutic development, longitudinal outcomes, causal learning, and regulatory evaluation. Draft PR #38 must remain unmerged until review is complete.

## Local UI redesign candidate — 31 October 2026

This is a local pull-request review candidate. The synthetic-only and non-clinical release status above is unchanged. Hallmark has no clinical-site template: its Console theme is for research and audit-trail interfaces; its Dose theme is a medication organizer, not a clinic. The app screen uses Console's light Paper colorway.

- Promoted the source-derived event timeline to the primary full-width view and grouped source review, investigation, evidence, bibliography, and import tools beneath it.
- Applied the user's 8 px spacing grid and 4 px type grid, visible surface boundaries, 44 px controls, explicit primary and secondary button states, selected section navigation, compact copy, and a collapsible narrow-screen menu.
- Kept all eight hash destinations, existing form IDs and handlers, source lineage, safety language, synthetic-only local case behavior, and the explicit opt-in for public DOI lookups. Named the two source/evidence checkbox groups with fieldset legends. Added exact-path local serving and HTTP coverage for the token/base stylesheets.
- Python suite: **38 tests pass**. Hallmark `sloplint`: **0 failures, 0 reflex issues, 0 warnings**; `--kept` confirms **8/8 links** retained (baseline 94 failures and 64 reflex issues).
- Reviewed the rendered page in the in-app browser at 390 px, the default 892 px, and 1440 px; at 390 px the document width remained 375 px with no horizontal overflow. Verified the mobile menu opens, closes after section selection, the current link is marked, and checkbox groups are exposed by name.
- Limits: the repository's headless browser journey could not run because Chrome/Chromium is unavailable here. Hallmark's render automation could not run because `puppeteer-core` is unavailable; the page was instead inspected directly in the in-app browser. No physical-device or screen-reader testing was done.

This interface work is supporting evidence for OI-010 only; it does not satisfy end-to-end workflow acceptance or complete any clinical, security, privacy, or release milestone. It has not been deployed and uses no real patient data.

## Patient-centered investigation workbench refinement — 31 October 2026

This second local iteration makes the question-driven case review the main workflow after the longitudinal timeline. It treats the larger patient intelligence environment as the direction while keeping the current app honest about its capabilities: the saved synthesis is human-authored and no model is called.

- Added a direct action from the case overview to the investigation workbench, a keyboard skip link, and clearer navigation names. The timeline remains the entry point for source history.
- Composed case questions and reviewable drafts side by side. The interface labels the synthesis as human-authored with no AI call. Draft content now stores separate headings for reported observations, a working hypothesis or mechanism, and assumptions, contradictions, and gaps, while preserving the existing server snapshot contract and source/evidence bindings.
- The hypothesis and uncertainty fields are optional; reported observations remain required. This allows an explicit lack of a supported hypothesis instead of forcing a speculative answer.
- Preserved all eight destinations and existing behavior. Updated the browser journey to cover the structured fields and their case-switch protection.
- Verification: all **38 Python tests pass**; JavaScript syntax and browser-journey Python syntax checks pass. Hallmark app-scope lint reports **0 FAIL, 0 REFLEX, 0 WARN**. The local preview accessibility tree confirms the skip link, all eight destinations, and named reasoning fields. Whitespace-only reported observations are rejected before submission.
- Limits: the browser journey itself could not run because Chrome/Chromium is unavailable. Hallmark's render tier is unavailable because `puppeteer-core` is absent. Responsive CSS stacks the workbench below 60rem, but this iteration has not had a new narrow-width visual review, physical-device test, or screen-reader test.

This remains a synthetic-only workflow refinement, not the AI research copilot or a clinically validated system. It does not call the model API or change provider configuration. No deployment or real-data use is part of this change.
