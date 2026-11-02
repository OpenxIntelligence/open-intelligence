# OI-022 decision memo template — go / pivot / stop (issue #14)

**FICTIONAL — SYNTHETIC ONLY. Blank memo. No decision recorded. Synthetic
staged-journey result; not clinical validation.**

Copy once at study close. Decide against the frozen threshold bands in
[PROTOCOL.md](PROTOCOL.md) §8.2 — never against retrofitted values.

## 1. Study identity

| Field | Entry |
| --- | --- |
| Evaluation ID / protocol version | `OI022` / TO RECORD (frozen version) |
| Preregistration freeze date + immutable location | TO RECORD |
| Packet commit / software revisions / vendor revisions | TO RECORD |
| Journeys executed (n/N of 12) with deviations | TO RECORD |
| Assessors / adjudicator (anonymous IDs) | TO RECORD |
| Study lead / accountable stop owner | TO RECORD |
| Memo author / date | TO RECORD |

## 2. Results summary (per metric, per arm — numerators and denominators)

| Metric | Arm A (ordinary) | Arm B (brief) | Arm C (graph) | Vendor arms | Frozen band hit |
| --- | --- | --- | --- | --- | --- |
| M01 early threat identification (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M02 missed threats (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M03 false urgent flags (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M04 source errors (n/N) + omissions (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M05 leakage (n/N, absolute) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M06 expert correction burden (median, range, N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M07 acquisition + coordination (median, range, N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M08 comprehension simulation (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M09 operating cost (per journey, N, buckets ref) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M10 unsupported claims (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M11 abstentions / unresolved (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M12 authorization/payer coverage (n/N, table ref) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M13 vendor comparability (n/N) | — | — | — | TO RECORD | TO RECORD |
| M14 severe findings (absolute + n/N + row IDs) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |
| M15 disagreement rate (n/N) | TO RECORD | TO RECORD | TO RECORD | TO RECORD | TO RECORD |

Evidence locations (worksheets, adjudication records, ledgers, hashes):
TO RECORD.

## 3. Falsification accounting (the point of the study)

- Strongest failed-probe statement supported: TO RECORD (e.g. "Arm C met the
  frozen M01 go band with no confirmed S3 per the frozen §8.3 incident rules
  across all executed journeys" — only if true).
- Successful falsifications (claim disproved on these journeys): TO RECORD
  with metric, band, and row evidence.
- Null / inconclusive dimensions (bands not discriminating, high
  disagreement, unresolved rows): TO RECORD — nulls are findings, not gaps.
- Negative controls: FJ03/FJ12/control-opportunity outcomes per arm:
  TO RECORD. Any false urgency here weighs directly against the claim.
- Dissenting reviewer opinions (attached, not averaged): TO RECORD.
- Limitations that bound every conclusion above: TO RECORD (synthetic-only,
  12 fictional journeys, no real workflow, no real patients — plus any
  study-specific limits).

## 4. Authorization, payer, and economics reading

- Authorization/payer table outcome (confirmed roles, cited bases, payers or
  "none identified"): TO RECORD with table reference.
- Fully loaded cost per reviewed journey per arm (M09 buckets): TO RECORD.
- Economic reading against the frozen M09 band: TO RECORD. No
  willingness-to-pay, procurement, or business-model claim beyond what the
  frozen band and the payer evidence support.

## 5. Vendor reading (if any vendor arm completed)

- Vendor arms completed/attempted with reasons for any shortfall: TO RECORD.
- Per-arm comparison on identical inputs: TO RECORD (reference §2 columns).
- Participation-is-not-endorsement restated: TO RECORD.

## 6. Decision

Select exactly one. Record the evidence for it; dissent attaches, it does not
veto silently.

- [ ] **GO** — falsification failed convincingly: all go-relevant frozen
  bands met, no confirmed S3 and no leakage per the frozen §8.3 incident
  rules, controls clean, dissent addressed. Permits: proceed to the next
  *separately authorized* evaluation
  step only. It is not clinical endorsement, regulatory approval, or
  permission for real patient use.
- [ ] **PIVOT** — repair / narrow / retest: state the exact repair or narrowed
  claim, the metrics that missed, the re-freeze required, and what will
  change before any retest. No retest on edited thresholds.
- [ ] **STOP** — falsified or unsafe to continue: state the falsifying
  evidence (metric, band, rows) or the incident. Preserve all evidence;
  route incidents per [PROTOCOL.md](PROTOCOL.md) §8.3.

Decision: TO SELECT. Rationale: TO RECORD. Accountable approver: TO RECORD.
Date: TO RECORD. Immutable evidence location: TO RECORD.

## 7. Interpretation ceiling (printed on every memo)

> This memo reports a synthetic staged-journey exercise on fictional inputs.
> It is engineering feedback for the stated falsification question — not
> clinical validation, not a real-world error rate, not evidence of patient
> benefit, and not authorization for clinical use, procurement, or deployment.
> Any broader claim requires separately governed evaluation.
