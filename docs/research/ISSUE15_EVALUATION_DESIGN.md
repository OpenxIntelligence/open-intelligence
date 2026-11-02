# Issue #15 — Specialist-model evaluation design (deterministic baseline vs generic model vs Nano-if-available)

**Status:** DRAFT DESIGN / EVALUATE; no evaluation has been run and no result is claimed here.
**Date:** 2026-11-02
**Tracker:** [Issue #15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)
**Parent:** [HL7 crosswalk](ISSUE15_HL7_CROSSWALK.md); companion [addendum](HL7_NANO_MODEL_FABRIC_ADDENDUM.md) §6
**Boundary:** design artifact only. All histories are independently authored fictional synthetic cases, labeled everywhere. Do not run this design against real data, and do not cite it as validation of any kind.

## 1. Question under test

Does a specialist-model run, producing reviewable [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md) records under [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) coverage, reduce total human review burden or improve proposal quality relative to the deterministic baseline — enough to justify its added complexity, rights surface, and operational cost?

A generic model or Nano must outperform the deterministic baseline on predefined *total review burden or quality* to justify adoption. Model-vs-model ranking alone answers nothing.

## 2. Arms

| Arm | Description | Availability precondition |
|---|---|---|
| A — Deterministic baseline | Existing deterministic machinery: `OI-SYNTHETIC-REPORT/1` parsing, `case_timeline` projection, `changes_since_review`, plus the [mock adapter](../../tools/mock_specialist_adapter.py) run in `local_only` mode as the candidate-shape harness. No model calls. | Available now (branch only for the mock harness). |
| B — Generic model | One permissible general model under the decided Meta-only provider boundary, called through a typed task contract with citation validation and the language guard. | Requires cleared [ModelCapabilityRegistry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md) record, per-use rights provenance, and operator key handling per [META_MODEL_API.md](../META_MODEL_API.md). Not available until those are recorded. |
| C — Nano, if available | Nano as a specialist candidate for chronology extraction, timeline reconciliation, contradiction/missingness detection, and context preparation. | Requires a runnable Nano version, documented license, recorded provider approval, and per-use rights provenance. None of these exists today; every Nano precondition is UNVERIFIED. Arm C does not run until all are recorded. |

All arms consume the same frozen source inputs and produce outputs in the same receipt/candidate shapes, so measurements are comparable. No arm's run has tool permission to approve its own results.

## 3. Fixture set (independently authored synthetic histories)

Authored separately from the adapter and specs, with adjudication labels written blind to all arm outputs. Required coverage, carried over from the addendum §6 with the issue-#15 additions:

1. Multiple institutions and two primaries (episode attribution stress).
2. Distinct specimens across documents (specimen linkage stress).
3. Negative vs untested variant (polarity: `negative` vs `not-assessed`/`not-reported`).
4. Uncertain/partial dates (must abstain; partial dates are unrepresentable per crosswalk G-4).
5. Reissued pathology finding (amendment supersession).
6. Duplicated import and out-of-order delivery (idempotence, ordering by occurred time).
7. Conflicting staging across documents (conflict preserved, no winner picked).
8. Withdrawn evidence item (evidence invalidation path).
9. Cross-case isolation probe (a second fictional case that must remain untouched).
10. Revocation probe (a rights revocation that must block dependent use and leave a denial receipt).
11. Wrong-subject import (quarantine path).
12. Indeterminate assay and unit mismatch (abstention and `unknown` handling).

Fixture hygiene: frozen bytes with recorded sha256; adjudication labels versioned with the fixtures; train/eval segregation by fictional patient and time if any arm involves learning (none currently does); no fixture text reused from the adapter's own tests.

## 4. Metrics (all reported with raw counts; confidence intervals where sample size permits)

No invented performance claims. No universal clinical accuracy threshold. Thresholds below are illustrative design placeholders marked [PLACEHOLDER]; reviewers set final values before results are examined.

| Metric | Definition | Direction |
|---|---|---|
| Exact source-anchor precision / recall | Candidate anchors resolving to the correct current source version + line vs adjudicated anchors | Higher better |
| Event extraction F1 | Correctly proposed occurred-date placements vs adjudicated events | Higher better |
| Pairwise chronological ordering accuracy | Correctly ordered event pairs over all adjudicated pairs | Higher better |
| Polarity preservation rate | Candidates whose polarity matches the source certainty verbatim | Higher better; wrong-polarity is a consequential error |
| Uncertainty preservation rate | Uncertainty/abstention preserved where the source is pending/indeterminate/unknown | Higher better |
| Specimen/episode attribution accuracy | Correct specimen + episode linkage per candidate | Higher better; wrong-specimen linkage is a hard failure |
| Contradictions retained rate | Adjudicated conflicts still visible as conflicts (not silently resolved) in arm output | Higher better |
| Valid abstention rate | Adjudicated must-abstain inputs that produced abstentions rather than guesses | Higher better |
| Cross-tenant isolation | Probes with zero cross-case reads/writes (binary per probe) | Must be perfect |
| Selective invalidation precision / recall | Staled artifacts exactly equal the adjudicated dependent set after amendment (see the [amendment flow](ISSUE15_AMENDMENT_FLOW.md)) | Higher better |
| Human correction time | Minutes for a reviewer to correct arm output to the adjudicated state, per case | Lower better |
| End-to-end review burden | Total preparation + correction + re-review minutes per case and per update | Lower better; primary burden metric |
| Latency and full cost | Wall time plus setup, verification, compute, and reviewer cost per reviewed case/update | Lower better; reported, not optimized silently |

## 5. Pass/fail scenarios (all must pass for the arm to justify adoption)

1. No output lacking a valid authorized source/version/anchor can enter the reviewed projection.
2. Negative, absent, untested, and indeterminate remain distinct; wrong-specimen linkage is a hard failure.
3. The T0 snapshot remains replayable after a T1 report amendment; only dependent derived objects become stale.
4. The unrelated case and unaffected evidence remain unchanged; retries and duplicate imports are idempotent.
5. Egress without explicit authorization/terms fails closed and leaves an inspectable denial receipt.
6. A specialist-model result is registered only as a derived candidate until a properly scoped human decision.
7. Arm B or C outperforms Arm A on predefined total review burden or quality to justify its added complexity.

## 6. Sequence

1. Schema inventory (done for the cited entities in the [crosswalk](ISSUE15_HL7_CROSSWALK.md) §3).
2. Fixture + gold-label authorship (independent author, blind adjudication).
3. Deterministic baseline measurement (Arm A, including the mock adapter path).
4. Local mock-adapter gate tests (branch only; authored in [tests](../../tests/test_mock_specialist_adapter.py), not yet run — see §8).
5. Amendment/invalidation measurement (Arm A + mock path, per the [amendment flow](ISSUE15_AMENDMENT_FLOW.md)).
6. Arm B / Arm C comparison — only if available and cleared (§2 preconditions).
7. Rights and clinical-validation decision (separate review; this design approves nothing).

Do not reprioritize the existing first implementation milestone for this evaluation.

## 7. Analysis and reporting rules

- Report raw counts for every metric, per case and aggregate; no hidden denominators.
- Pre-register failure thresholds before examining results; changing a threshold after results requires a recorded reason and re-review.
- Report all arms attempted, including blocked runs and denial receipts — a blocked run is a finding, not a missing value.
- Adjudication disagreements are recorded with the disagreement and the resolution, not averaged away.
- Cost accounting includes setup, fixture authorship, verification, reviewer time, compute, and failed runs. Token price alone is not the unit economics.

## 8. Current state (2026-11-02)

- Design drafted; fixtures not yet authored; no arm measured; no result exists.
- The mock-adapter tests exist but were not run in this session (sandboxed shell cannot mount proc; no shell verification attempted). Reviewer run command from the repository root: `PYTHONPATH=src python -m unittest tests.test_mock_specialist_adapter -v`.
- Nano preconditions (§2, Arm C) are entirely UNVERIFIED: no runnable, no license, no terms, no approval.
