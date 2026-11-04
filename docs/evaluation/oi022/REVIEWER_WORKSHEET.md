# OI-022 blinded reviewer worksheet (issue #14)

**FICTIONAL — SYNTHETIC ONLY. Scoring instrument. No observations recorded.
Assessors score traceability to cutoff sources — never clinical truth.**

## 1. Who uses this and under what masking

- Two independent assessors per journey-cutoff-arm, blind to arm identity
  (blind codes re-randomized per journey) and blind to each other's scores.
- Assessors receive, per scoring unit: the cutoff input (cutoff sources only),
  the journey question wording, the blind-coded arm output, and this
  worksheet. They never receive: the coordinator checkpoint key
  ([JOURNEYS.md](JOURNEYS.md) §13), later cutoffs, other arms' outputs, the
  Arm A baseline brief for that journey-cutoff (until their own scoring for
  that unit is frozen), or any pilot score.
- At least one assessor per journey must hold the recorded oncology review
  qualification when any applicability judgment is in scope; pure
  traceability rows record which qualification applied. See
  [PROTOCOL.md](PROTOCOL.md) §3.

## 2. Scoring unit and outcome vocabulary

One row = one predeclared checkpoint opportunity or one arm-output claim, for
one journey, cutoff, blind-coded arm, and reviewer.

**Rubric A — claim-level source correctness** (does the output claim match a
cited source version and anchor as it existed at the cutoff?):

- `correct` — faithful to the cited source version and anchor; the anchor is
  locatable in the cutoff input.
- `incorrect` — mismatch with the cited source, wrong version, or a claim
  about a source that does not support it.
- `unsupported` — no packet source at the cutoff supports the claim.
- `omitted` — a predeclared expected observation is absent from the output.
- `abstain` — reviewer formally abstains (packet defect, cutoff ambiguity,
  conflict, or prior exposure discovered mid-review; cite reason, notify the
  lead without revealing a provisional score).
- `not_applicable` — the opportunity does not apply to this
  journey/cutoff/arm.
- `not_scored` — the row was excluded before scoring for a recorded reason.

Unknown is never forced into false: if the cutoff input does not settle a
point, the outcome is `unsupported` or `omitted` as applicable — never
`incorrect` by default, never `correct` by inference from a later source.

**Rubric B — applicability and uncertainty** (scored separately, never merged
with A, never averaged, no combined column):

- `uncertainty-preserved` — the output keeps the packet's distinctions
  (untested vs negative, pending vs indeterminate, order vs administration,
  old-event-received-late vs new event, discussion vs decision, hypothetical
  vs actual) and claims no more than the sources support.
- `overstated` — the output upgrades uncertainty into a firmer claim or draws
  an efficacy, eligibility, urgency, or action inference the packet does not
  support.
- `not-assessable-from-synthetic-packet` — the default for any genuine
  clinical-applicability judgment: a synthetic packet cannot settle it.
- `abstain`, `not_scored` — as in Rubric A.

## 3. Flags recorded on every row (booleans, even when Rubric A is `correct`)

- `missingness_error` — untested/negative/pending/indeterminate collapsed or
  mislabelled.
- `identity_error` — wrong-case or wrong-specimen attachment or citation.
- `post_cutoff_leak` — names the post-cutoff source if the claim requires
  one; empty otherwise. A leak is a finding, not a footnote.
- `unsupported_claim` — patient-specific efficacy/eligibility/urgency/action
  conclusion without adequate support.
- `false_urgency` — urgency/escalation/action claim on a CONTROL opportunity.
- `missed_threat` — a predeclared flaggable item the output does not surface
  (assessor judges surfacedness from the output alone; mapping to
  checkpoints happens after freeze).
- `directive_language` — recommendation/eligibility/order/instruction wording
  (automatic S3; quote the wording in `reason`).
- `deadline_labelling_error` — potential discussion deadline shown without
  "not a clinical deadline" labelling, or discussion-deadline arithmetic
  wrong (quote both values in `reason`).

## 4. Severity (per row, independent of rubrics)

- **S0** — no consequential discrepancy (cosmetic only).
- **S1** — presentation/traceability inconvenience, meaning retained.
- **S2** — wrong source/chronology/missingness or unsupported interpretation
  with potential to mislead review.
- **S3** — wrong-subject attribution, hidden cutoff leakage, unauthorized
  disclosure/action, unreviewed clinical instruction, or any directive
  clinical language. **S3 findings are never averaged away**: each confirmed
  S3 is listed individually and blocks `go`. A deliberate wrong-patient test
  input is not itself an incident; failure to handle it correctly is.

## 5. Burden entries (assessor-timed, this worksheet)

Assessors record their own `review_minutes` and `correction_minutes` per
scoring unit, timed during scoring. All other burden buckets and all cost
entries are coordinator-measured. Never estimate retroactively, never
fabricate. Record 0 where a bucket does not apply; missing timing makes the
worksheet incomplete.

## 6. Column rules

- `denominator_eligible` is set at freeze time from the predeclared
  opportunity list — not after seeing outputs.
- Negative and null findings are rows, not absences: a correct null ("no
  packet support at this cutoff"), a correct negative, and a false positive
  (an output claim with no source) are all preserved. Dropping nulls to
  inflate precision is a protocol violation. False positives are preserved
  and counted, never deleted as "noise".
- `reason` cites source IDs/versions/lines for every non-`correct` outcome
  and every raised flag. `evidence_location` points to the frozen artifact
  (cutoff input hash, output hash, line/anchor).
- The template [WORKSHEET_TEMPLATE.csv](WORKSHEET_TEMPLATE.csv) is
  header-only. Any nonblank distributed "example row" would be fabricated
  data and is forbidden.

## 7. Disagreements and abstentions

- The two assessors' rows are compared by the coordinator after both freeze.
  On any disagreement about Rubric A, Rubric B, severity, or any flag, both
  assessments are preserved verbatim and routed to the dispute adjudicator
  per [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md).
- Abstentions are reported separately from omissions and are never scored as
  correct or incorrect. An abstention rate above the frozen limit triggers
  `pivot (repair)`; omissions trigger an audit of the review process itself.
