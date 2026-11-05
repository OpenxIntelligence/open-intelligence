# AI evaluation plan

Current repair: additive `0022_lab_citation_source_scope` now aligns the database
guard with the existing structured-source snapshot and preserves published 0021.
The reviewed-document mismatch was reproduced in hosted PostgreSQL run
42096046609 before repair. The earlier source inspection below records the
pre-repair boundary; final repaired-head PostgreSQL/browser/recovery acceptance
is tracked in draft [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542).

Updated 2026-11-05. This executes OI-011/OI-014 in the
[existing backlog](../EXECUTION_BACKLOG.csv) and the
[master execution plan](MASTER_EXECUTION_PLAN.md). Current work uses independently
authored synthetic cases only. This document authorizes no provider call,
external data egress, model installation or clinical use.

## What exists and what remains proposed

| Owner | Observed implementation | Evaluation boundary |
|---|---|---|
| Reference `src/open_intelligence/investigation.py` | Fixed-template Meta transport and clearly labeled human-authored replay; validates claims, citations, uncertainty and language | Code presence is not a live run, qualified clinical reasoning or H1 copilot. Record replay separately from inference |
| Reference `agent_writes.py` / `store.py` | Per-write agent/model/prompt/run/route/input-hash provenance and replay checking; present in pinned main and candidate | Existing writer maps to A1; parallel A1–A6 agents, toolsets and full pipeline are not implemented by the metadata contract. This is a reference-store owner, not proof of an H1 model-write API |
| H1 question/evidence/source owners | Permission-checked source context, authored comparisons, citations, follow-through and freshness | Candidate integration adds strict anchors and database freshness repair; it does not connect an autonomous model or clinically authorize outputs |
| [#141](https://github.com/OpenxIntelligence/open-intelligence/pull/141), `429faf8982dc3737482d4166d19adb7ec0ba06e0` | Draft provider-neutral `execute_bounded_model` child of existing Composer; synthetic prompts, hypothesis-only effects, server-selected adapters and existing validator | Adapter absent from candidate. Two simulated adapters do not demonstrate other live providers. Reconcile with current agent-write contract before any port |
| [#476](https://github.com/OpenxIntelligence/open-intelligence/pull/476), `4f1c613abe1f90c185e1f2f9edb816e3bf81fa3c` | Draft local-only 72-question semantic runner plus separately executed public-label scorer; no patient records/SQL/tools in the packet | Harness absent from candidate. Hosted evidence uses a scripted loopback server, not a NVIDIA/Nemotron model. Declared model ID/hashes are unsigned and unverified |
| [#466](https://github.com/OpenxIntelligence/open-intelligence/pull/466), `fbc26cb6bfb2f6127aee9fbe91ee12248f46a1a4` | Draft extraction qualification harness: 16 authored intake cases and two controlled PDF layout challenges | Harness absent from candidate. Reported 16/16 expected intake outcomes and 1/2 preserved table orders are a counterexample and contract check, not population accuracy or clinical qualification |

Accepted-main comparison is `f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9`;
candidate code comparison is `3dd9811738e222274aa2c9e03edeff8104d64d53`.
Related PR statuses and ownership are indexed in
[architecture decisions](ARCHITECTURE_DECISIONS.md). No model was executed or
independent clinical validation performed by this consolidation.

## Task contract before an experiment

Each experiment needs a versioned task card containing intended user/output,
allowed synthetic input classes and snapshot cutoff, source/rights filters,
provider/model/weights identity and exact artifact permissions, prompt/schema
versions, permitted tools/effects, output bounds, reviewer and stop rules.
Models cannot select patient scope, grants, database queries, clinical writes or
their own authority. No model or retrieved text may override the host contract.

Record the source/prompt/code/model identifiers, input hashes, tool calls,
structured output, validation/refusal reason, latency, failures and measured
compute/cost where available. Never replace missing provenance with a model's
self-reported identity. Preserve source/review state and invalidation edges;
deterministic authority/freshness checks run again before saving or disclosing.

## Staged evaluations

| Stage / task | Baseline and test material | Required result before expansion |
|---|---|---|
| 0. Combined deterministic foundation | Final candidate API/reference/client checks plus real PostgreSQL, migration/recovery and browser paths | Repair the `0021` reviewed-document/source-snapshot mismatch; prove typed identity, wrong-patient isolation, original integrity, exact retry, late revocation and amendment invalidation; a skipped DB check is not a pass |
| 1. Document/pathology extraction proposals | Manual exact transcription and current parser; independently authored varied layouts and pathology reports | Exact value/unit/specimen/negation/uncertainty/anchor fidelity; omissions and invented associations counted separately; measured correction and inspection effort |
| 2. Semantic field mapping research | Existing deterministic mapping baseline and simple lookup; #476 question-only packet | Correct mappings, useful abstention, false joins, unsafe outputs, malformed/truncated output and transport errors reported separately. Keep proposals unreviewed |
| 3. Typed oncology links and chronology | Deterministic/source-search baseline after episode registry acceptance; two primaries, metastases, recurrence, amendments and uncertain dates | Source attribution and cutoff fidelity; proposed links distinct from reviewed reconciliation; no invented dates/stage or cross-specimen equivalence |
| 4. Permission-filtered copilot | Simple source search/structured timeline versus AI-assisted workflow on held-out authored cases | Claim-by-claim support, contradictions, rights filtering, useful abstention and patient comprehensibility; visible source/version and review state in every consequential answer |
| 5. Governed clinical evaluation | Separately authorized representative retrospective packets and independently held-out adjudicated references | Prespecified intended use, consequential-error limits and burden endpoints; independent reviewers, disagreement resolution and governance readiness before real data |

For #476 specifically, keep the runner isolated from scorer/reference labels.
Its public author-labeled 72 questions are not blinded or independently
adjudicated, and the repository contains their answers. A later approved model
experiment needs a separate process/environment with only the permitted question
packet mounted and independently held-out references. Its current exact numeric
loopback endpoint restriction, no-proxy/no-redirect behavior and bounded I/O do
not establish model/provider authenticity or a clinical sandbox.

For #466, preserve the two distinct fixture digests and measurement-completion
checks. Default CLI success means intake expectations and completed layout
measurement; `--require-layout-order` intentionally fails its difficult pair.
Missing workers/fixtures are execution errors, not layout-fidelity findings.
Do not globally switch extraction modes from this small experiment.

## Measures, adjudication and stopping

| Dimension | Record separately |
|---|---|
| Fidelity | Wrong patient/specimen/episode, exact values/units, omitted facts, negation/missingness, source-version/anchor errors, hallucinations and layout association errors |
| Evidence | Supported/unsupported/contradictory claims, relevance, applicability limits, citations that actually support the assertion, and justified abstention |
| Longitudinal behavior | Amendments and independent new sources, stale proposals, inappropriate invalidation, cutoff leakage, prior version recoverability |
| Safety/authority | Cross-patient or forbidden-content exposure, prompt injection, forbidden tools/actions and attempts to promote a proposal or bypass review |
| Human burden | Total acquisition, preparation, inspection, correction, review and follow-through time for both initial case and update; identify who bears each cost |
| Reliability and cost | Completed/partial runs, parse/transport/runtime failures, retries, host-observed latency, actual resource use and total cost per reviewed output |

Author reference answers before viewing model results; hold out by patient/case
and source version, deduplicate near copies, and preserve historical cutoff.
Use matched/counterbalanced comparisons where human learning would bias timing.
Report denominators, exclusions, disagreements and limitations with every result.
Do not count malformed output or transport errors as deliberate abstention.

Block experiment promotion on an unauthorized disclosure/action or broken
patient/source identity. For the #476 research scorer, retain its conservative
stop flags for unsafe/false-join mappings, wrong positive mappings, malformed
output and transport error. Clinical thresholds must be prespecified by the
evaluation lead and independent reviewers for the intended function; this plan
does not invent a universal accuracy threshold. Revise or stop when unsupported
claims persist or review consumes the proposed time saving.

The evaluation owner publishes a frozen manifest, reproducible commands,
per-case error taxonomy, aggregate results, correction burden and explicit
decision. Engineering reviewers assess contract/recovery integrity; independent
domain reviewers assess clinical meaning. A future Skeptic agent or model
self-review cannot supply independent clinical adjudication.
