# OI-022 adjudication record template (issue #14)

**FICTIONAL — SYNTHETIC ONLY. Blank record. No judgments recorded, no
adjudication performed. Copy once per journey-cutoff-arm combination
scored.**

## A. Record identity (coordinator completes before adjudication)

| Field | Entry |
| --- | --- |
| Evaluation ID / protocol version | `OI022` / TO RECORD (frozen version) |
| Journey / cutoff / arm blind code | TO RECORD / TO RECORD / TO RECORD |
| Packet commit / software revision | TO RECORD / TO RECORD |
| Assessor IDs (anonymous) + qualifications | TO RECORD |
| Adjudicator ID (anonymous) | TO RECORD |
| Worksheet locations + SHA-256 (both assessors) | TO RECORD |
| Cutoff input hash / arm output hash / baseline brief hash | TO RECORD |
| Adjudication date | TO RECORD |

## B. Per-row adjudication (one block per disagreement or flagged row)

Copy this block once per row needing adjudication. Rows where both assessors
agree and no flag is raised are tallied in §D without a block.

```text
Row: <opportunity_id / claim_id>
Assessor 1 (<id>): A=<outcome> B=<outcome> severity=<S0-S3> flags=<list>
  reason: <verbatim>
Assessor 2 (<id>): A=<outcome> B=<outcome> severity=<S0-S3> flags=<list>
  reason: <verbatim>
Checkpoint mapping (coordinator, post-freeze): <CP id or "unmapped output claim">
Adjudicator outcome: <resolved A / resolved B / resolved severity /
  explicitly unresolved>
Adjudicator rationale (cited source/version/anchor): <text>
Dissent preserved: <yes — attached below / no dissent>
```

Rules:

- Both assessments are preserved verbatim. The adjudicator either resolves
  with a cited rationale or marks the row **explicitly unresolved** with a
  reason. Unresolved rows are excluded from numerators but retained in the
  denominator note — never silently dropped.
- Disagreement never silently downgrades an S3. A disputed S3 resolved as
  non-S3 requires documented rationale with dissent preserved, and the row is
  still listed in the S3-review appendix (§E).
- Applicability disputes that turn on genuine clinical judgment (not packet
  traceability) resolve to Rubric B `not-assessable-from-synthetic-packet`
  with the reason recorded — the packet cannot settle them.

## C. Leakage and directive-language findings (list every instance)

```text
Finding <n>: journey=<id> cutoff=<id> claim=<id>
  class: <post-cutoff-leak / directive-language / wrong-subject /
    unauthorized-action>
  post-cutoff source (if leak): <source id + date>
  quoted wording (if directive): <verbatim quote>
  assessors: <agree / disagree — see §B block>
  severity: S3 (fixed for this class)
  resolution: <confirmed / resolved-non-S3 with rationale / unresolved>
```

Confirmed leakage and confirmed directive language each block `go`
independently. Report absolute counts `n/N` alongside any rate.

## D. Tally for this record (counts, not judgments)

| Item | Count |
| --- | --- |
| Rows scored (both assessors) | TO RECORD |
| Agreements / disagreements | TO RECORD / TO RECORD |
| Resolved / explicitly unresolved | TO RECORD / TO RECORD |
| Abstentions (reported separately from omissions) | TO RECORD |
| Omissions (audit the review process if nonzero pattern) | TO RECORD |
| Rubric A `correct` (post-adjudication) | TO RECORD |
| Rubric B `uncertainty-preserved` (post-adjudication) | TO RECORD |
| S0 / S1 / S2 / S3 (post-adjudication absolute counts) | TO RECORD |
| Leakage findings (n/N) | TO RECORD |
| False-urgency flags raised / confirmed | TO RECORD |
| Missed-threat flags raised / confirmed | TO RECORD |
| Directive-language flags raised / confirmed (each confirmed instance is S3, see §C) | TO RECORD |
| Discussion-deadline labelling flags raised / confirmed | TO RECORD |
| Null/negative rows preserved (must equal predeclared null count) | TO RECORD |

## E. S3-review appendix (every S3 raised, even if resolved otherwise)

| Row | Class | Raised by | Final status | Rationale location |
| --- | --- | --- | --- | --- |
| TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |

## F. Study-level adjudication summary (one per completed study)

| Item | Entry |
| --- | --- |
| Journeys-cutoffs-arms adjudicated (n/N planned) | TO RECORD |
| Overall disagreement rate (disagreed rows / scored rows) | TO RECORD |
| Unresolved rows (count + row ID list) | TO RECORD |
| Abstention count + rate with denominator | TO RECORD |
| S3 absolute count + row ID list | TO RECORD |
| Leakage absolute count (n/N) | TO RECORD |
| Dissenting opinions attached (count + locations) | TO RECORD |
| Adjudicator signature (restricted register ref) + date | TO RECORD |

## G. Attestation (copy into the study record, sign at close)

> We certify: synthetic-only scope; denominators and thresholds frozen before
> any scored output was opened; Rubrics A and B scored and reported
> separately, never merged; nulls, negatives, false positives, abstentions,
> disagreements, and leakage counts fully preserved; directive-language and
> wrong-subject findings listed individually; no claim of independent
> evaluation beyond what the filed reviewer evidence actually shows; and no
> clinical conclusion drawn from synthetic material.
>
> Adjudicator: TO SIGN. Date: TO RECORD.
