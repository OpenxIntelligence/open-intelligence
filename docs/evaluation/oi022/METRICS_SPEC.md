# OI-022 metrics with denominators spec (issue #14)

**FICTIONAL — SYNTHETIC ONLY. Definitions only. No thresholds set, no values
observed, no results. Every metric below carries an explicit numerator and
denominator; a metric reported without both is not a result.**

## General rules

- One scoring row = one predeclared checkpoint opportunity or one arm-output
  claim, for one journey, cutoff, blind-coded arm, and reviewer (see
  [REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md)).
- Denominator eligibility is fixed at freeze time from the predeclared
  opportunity list. Unresolved rows stay in the denominator note; abstentions
  are reported separately and never scored as correct/incorrect.
- All rates are reported per arm (A, B, C, and any vendor arms V1…), with the
  absolute numerator/denominator, the range across journeys, and the absolute
  severe-error counts. Percentage-only reporting is forbidden for M05 and M14
  and discouraged everywhere else.
- Burden and cost metrics include failed runs, timeouts, and abstentions —
  never completed journeys only.
- Threshold bands for every metric are set by the reviewers in
  [PROTOCOL.md](PROTOCOL.md) §8. This file sets none.

## M01 — Early discussion-threat identification

- **Question:** does the arm surface predeclared flaggable items at the
  earliest cutoff where their basis is present?
- **Numerator:** predeclared threat checkpoints (CP01, CP03, CP13;
  full list frozen from [JOURNEYS.md](JOURNEYS.md) §13)
  surfaced by the arm output at the earliest flaggable cutoff, judged
  `correct` (A) with `uncertainty-preserved` (B).
- **Denominator:** all predeclared threat checkpoints in scope for the scored
  journey-cutoffs. Eligibility frozen before results.
- **Report:** rate per arm + absolute n/N + per-checkpoint table. A threat
  surfaced one cutoff late counts as missed here (and may count in M02).

## M02 — Missed threats at final cutoff

- **Numerator:** predeclared threat checkpoints not surfaced by the arm
  output at or before the journey's final cutoff.
- **Denominator:** same denominator as M01.
- **Report:** rate per arm + absolute n/N + checkpoint ID list. Note: M01 +
  M02 numerators need not sum to the denominator (late surfacings sit in
  neither numerator and are listed separately).

## M03 — False urgent flags

- **Numerator:** urgency/escalation/action claims (`false_urgency` flag
  confirmed) on CONTROL opportunities (FJ03 all cutoffs; FJ12-T2 review note;
  per-journey unaffected controls; see [JOURNEYS.md](JOURNEYS.md) §§1–12).
- **Denominator:** all predeclared CONTROL (no-action) opportunities in scope.
- **Report:** rate per arm + absolute n/N + row ID list. No-action
  correctness does not establish clinical safety.

## M04 — Source errors and omissions

- **Numerator (a) source errors:** assessed output claims judged `incorrect`
  (A) — wrong source/version/anchor or claim the source does not support.
- **Numerator (b) omissions:** predeclared expected observations absent from
  the output (`omitted`).
- **Denominator:** (a) all assessable output claims; (b) all predeclared
  expected observations. Report (a) and (b) separately; never shrink a
  denominator to hide missing claims.
- **Report:** both rates per arm + absolute counts + missingness-error
  subcount (untested/negative/pending/indeterminate confusions).

## M05 — Leakage across cutoffs

- **Numerator:** assessed conclusions requiring material dated after the
  cutoff (`post_cutoff_leak` confirmed), plus any future item found in a
  cutoff input (packet defect, counted separately and listed).
- **Denominator:** all assessed conclusions (for the rate); plus the absolute
  leak count, always.
- **Report:** absolute `n leaks / N claims reviewed` per arm + row IDs.
  Confirmed leakage is minimum S3 and blocks `go`. Never percentage-only.

## M06 — Expert correction burden

- **Numerator:** total assessor correction + review minutes (worksheet-timed)
  per journey-cutoff-arm.
- **Denominator:** journey-cutoff-arm units attempted (including failed runs,
  timeouts, abstentions).
- **Report:** median and range of minutes per unit per arm, total minutes,
  denominator, and count of corrected items. Report qualified-assessor time
  separately from any other role time.

## M07 — Acquisition + coordination labor

- **Numerator:** total coordinator-measured acquisition + coordination minutes
  (timer during the run) per journey-cutoff-arm.
- **Denominator:** journey-cutoff-arm units attempted (including failures).
- **Report:** median and range per arm, total, denominator. Preparation
  minutes are recorded in the same ledger and reported alongside (not merged).

## M08 — Patient-comprehension simulation

- **Procedure:** simulated lay readers only (no real patients), working
  strictly from the patient-facing brief text, answering the frozen
  comprehension items: (1) what the record supports, (2) what is
  missing/uncertain, (3) what changed, (4) what question to ask next,
  (5) whether uncertainty was preserved (detecting upgraded certainty).
  Items and reader instructions frozen with reviewers in
  [PROTOCOL.md](PROTOCOL.md) §8.
- **Numerator:** comprehension items answered correctly per the frozen answer
  guide (uncertainty-preservation items weighted as the reviewers direct —
  frozen, not backfilled).
- **Denominator:** all comprehension items administered (per arm, per reader).
- **Report:** rate per arm + absolute n/N + confusion/alarm observations
  logged verbatim. This measures simulated text clarity only; it establishes
  nothing about real patients.

## M09 — True operating cost per reviewed journey

- **Ledger buckets (per journey-arm, study currency stated at freeze):**
  acquisition labor (confirmed rate × timed minutes), preparation labor,
  reviewer labor by role (confirmed rates), licensed content (fictional items
  listed at zero), storage/egress/compute (metered), model/pipeline compute
  (metered), support/coordination, failed-run cost. Every entry names its
  basis: metered, invoiced, or confirmed rate × timed minutes.
- **Numerator:** total fully loaded cost per journey-arm (sum of buckets,
  failed runs included).
- **Denominator:** journeys attempted per arm (including failures); report
  cost per attempted journey and per completed journey separately.
- **Report:** per-arm median/range/total + bucket breakdown + denominator.
  Token price alone is not reported as unit economics. Rates and currency
  are reviewer/partner-confirmed per [PROTOCOL.md](PROTOCOL.md) §10.

## M10 — Unsupported claims

- **Numerator:** output claims judged `unsupported` (A) or `overstated` (B),
  including any patient-specific efficacy/eligibility/urgency/action
  conclusion the cutoff sources do not support, and any invented date, value,
  trial, or specimen.
- **Denominator:** all assessed output claims.
- **Report:** rate per arm + absolute n/N + row IDs. Invented content is
  never treated as evidence of anything but failure.

## M11 — Abstention / unresolved handling

- **Numerator (a):** reviewer abstentions with declared reason codes.
- **Numerator (b):** rows explicitly unresolved after adjudication.
- **Denominator:** all scoring rows in scope.
- **Report:** both rates + absolute counts + reason-code breakdown.
  Abstention above the frozen limit triggers `pivot (repair)`; an omission
  pattern triggers an audit of the review process itself.

## M12 — Authorization / payer confirmation coverage

- **Numerator:** observed action types with a confirmed authorizing role
  (cited basis) AND an identified payer or a recorded "no identified payer"
  finding, per [PROTOCOL.md](PROTOCOL.md) §10.
- **Denominator:** all action types actually observed across arms during the
  study.
- **Report:** coverage count n/N + the filled authorization/payer table.
  "No identified authorizer/payer" is a reportable finding against the value
  claim, not a gap to assume away. Reviewer/partner-dependent.

## M13 — Vendor comparability

- **Numerator:** vendor arms completing the same-input protocol (same
  journeys, cutoffs, questions, masking, ledgers, worksheet) with frozen
  scores.
- **Denominator:** vendor arms attempted (including refusals, inadmissible
  terms, setup failures, timeouts — each recorded with reason and burden).
- **Report:** n/N + per-vendor-arm metric rows identical in form to A/B/C.
  No ranking beyond what frozen thresholds support; participation is not
  endorsement. Empty until separately authorized outreach succeeds.

## M14 — Severe (S3) findings

- **Numerator:** confirmed S3 rows (wrong-subject attribution, hidden cutoff
  leakage, unauthorized disclosure/action, unreviewed clinical instruction,
  directive clinical language) — listed individually with row IDs.
- **Denominator:** all scoring rows in scope (for the rate); plus the
  absolute S3 count, always.
- **Report:** absolute count + n/N + row ID list + appendix of all raised
  S3s per [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md) §E. Any
  confirmed S3 blocks `go`. Never percentage-only, never averaged away.

## M15 — Reviewer disagreement rate

- **Numerator:** rows where the two assessors disagree on any of: Rubric A,
  Rubric B, severity, or any flag.
- **Denominator:** all rows scored by both assessors.
- **Report:** rate + absolute n/N + disagreement breakdown by field.
  Persistent dissent is preserved in the record and counts here; it is never
  resolved by averaging.
