# OI-022 — Option-preservation falsification packet (issue #14)

**FICTIONAL — SYNTHETIC ONLY. Preregistration draft. NOT ACTIVATED. No reviewers
recruited, no thresholds set, no evaluation run, no results.**

This directory holds the preregistered evaluation deliverable set for
[Open Intelligence issue #14](https://github.com/OpenxIntelligence/open-intelligence/issues/14)
(optional E6 option-preservation falsification). Its objective is to **try to
disprove** that option preservation adds clinically and economically meaningful
value — not to confirm it.

## Status

- Protocol version: `OI022-DRAFT` (unfrozen; frozen version requires reviewer
  sign-off per [PROTOCOL.md](PROTOCOL.md) §9).
- Study state: **planned**. No independent oncology adjudicator has been
  recruited, no numerical threshold has been set, no journey has been executed,
  no vendor has been tested. Every threshold cell in this packet is blank by
  design; see [PROTOCOL.md](PROTOCOL.md) §8.
- All journeys, cases, sources, findings, evidence notes, threats, deadlines,
  costs, and worksheet rows in this packet are **independently authored
  fiction**. Nothing here is a clinical claim, a treatment recommendation, an
  eligibility determination, or evidence of patient benefit. See
  [RIGHTS_MANIFEST.md](RIGHTS_MANIFEST.md).
- No real patient acquisition, no retrospective real-record use, and no
  clinical pilot is authorized by this packet. See [PROTOCOL.md](PROTOCOL.md)
  §2.

## Contents

| File | Deliverable | Contract coverage |
| --- | --- | --- |
| [PROTOCOL.md](PROTOCOL.md) | Preregistered protocol: falsification objective, three arms, roles, masking, cutoff rules, authorization/payer confirmation procedure, vendor comparison procedure, threshold-setting procedure + blank threshold table, stop rules, freeze checklist | Full contract scaffold |
| [JOURNEYS.md](JOURNEYS.md) | 12 staged fictional journeys with per-stage sources, cutoff datetimes, structural checkpoints, and negative controls | Pre-register 10–20 journeys, negative controls, cutoff rules |
| [RIGHTS_MANIFEST.md](RIGHTS_MANIFEST.md) | Datasets/rights manifest: provenance, authorship, redistribution limits | Datasets/rights manifest |
| [REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md) + [WORKSHEET_TEMPLATE.csv](WORKSHEET_TEMPLATE.csv) | Blinded reviewer worksheet instructions and header-only scoring template | Blinded reviewer worksheet |
| [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md) | Adjudication record template: dual assessment, disagreement handling, severity, attestation | Adjudication record template |
| [METRICS_SPEC.md](METRICS_SPEC.md) | Metrics with denominators spec: every metric carries an explicit numerator and denominator | Metrics with denominators spec |
| [DECISION_MEMO_TEMPLATE.md](DECISION_MEMO_TEMPLATE.md) | Decision memo template: go / pivot / stop | Decision memo template |

## Relationship to existing material

- This packet is **supplementary** to the existing architecture and evaluation
  program. It creates no new canonical state, source ledger, competing
  roadmap, or product claim. See [AGENTS.md](../../../AGENTS.md) and the
  [first-principles plan](../../FIRST_PRINCIPLES_PLAN.md) §11.
- It follows the [Independent Evaluation & Collaboration Playbook](../../INDEPENDENT_EVALUATION_COLLABORATION.md)
  (lane D / E6), the [blank packet template](../PACKET_TEMPLATE.md), and the
  merged IV-02/IV-03 contracts
  ([ADJUDICATION.md](../../../validation/iv01/ADJUDICATION.md),
  [BASELINE.md](../../../validation/iv01/BASELINE.md),
  [SCORING.md](../../../validation/iv01/SCORING.md)). Where this packet differs
  (three E6 arms, staged journeys, authorization/payer confirmation, vendor
  comparison), the difference is stated explicitly in [PROTOCOL.md](PROTOCOL.md)
  §4 and does not amend those contracts.
- The option/dependency/threat vocabulary (Option, OptionDependency,
  OptionalityThreat, PreparationTask, potential discussion deadline) is the
  existing OI-021 derived projection over the investigation ledger. A
  potential discussion deadline is **not** a clinical deadline.
- Prior synthetic fixtures that inform journey design (not reused verbatim):
  `examples/synthetic/oi019-*` (OI-019 option-preservation evaluation cases)
  and `validation/iv01/cases.json` (IV-01 practice packet). This packet authors
  its own journeys; fixture IDs from those sets never appear as inputs here.

## How to use this packet

1. Recruit independent reviewers under [PROTOCOL.md](PROTOCOL.md) §3. Do not
   proceed without them.
2. Run the threshold-setting procedure in [PROTOCOL.md](PROTOCOL.md) §8.
   Thresholds stay null until signed; the study stays `not_activated`.
3. Freeze the protocol, journeys, worksheet, metrics, and software/vendor
   revisions per [PROTOCOL.md](PROTOCOL.md) §9.
4. Execute journeys per arm under masking, score with
   [REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md), adjudicate with
   [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md), and record the
   outcome in [DECISION_MEMO_TEMPLATE.md](DECISION_MEMO_TEMPLATE.md).
5. A synthetic result — positive, negative, or null — is engineering feedback
   only. It is never clinical validation. See [PROTOCOL.md](PROTOCOL.md) §2.

## Completion accounting (fill at freeze / close)

- Preregistration freeze date and location: **TO COMPLETE BEFORE RESULTS**
- Independent reviewers recruited: **NONE — TO RECRUIT**
- Thresholds set: **NONE — BLANK BY DESIGN**
- Evaluation runs executed: **NONE**
- Results observed: **NONE**
- Decision recorded: **NOT STARTED**
