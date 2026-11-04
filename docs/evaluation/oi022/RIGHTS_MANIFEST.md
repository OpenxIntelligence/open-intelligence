# OI-022 datasets and rights manifest (issue #14)

**FICTIONAL — SYNTHETIC ONLY. No real patient data, no copied licensed text,
no third-party dataset, model, or service is included in this packet.**

## 1. Dataset inventory (all original synthetic)

| Dataset / artifact | Location in packet | Authorship and provenance | Rights declaration |
| --- | --- | --- | --- |
| 12 staged fictional journeys (descriptions) | [JOURNEYS.md](JOURNEYS.md) §§1–12, §14 | Independently authored for OI-022; abstract finding keys (`marker-q`, `lesion-figure`, etc.) invented for this packet | Original synthetic text; no external content imported |
| Coordinator checkpoint summary | [JOURNEYS.md](JOURNEYS.md) §13 | Same authorship; structural traceability expectations, not clinical truth | Coordinator key material; never distributed to assessors or participants |
| Staged source bytes + SHA-256 manifest | Produced at freeze from [JOURNEYS.md](JOURNEYS.md) by the coordinator (location recorded in freeze record) | Coordinator-transcribed from the frozen journey descriptions; finding keys, states, versions, dates must match verbatim | Original synthetic; each fictional evidence note carries exactly one `Rights: original-synthetic` header |
| Preregistered protocol | [PROTOCOL.md](PROTOCOL.md) | Authored for OI-022 | Original synthetic / procedural text |
| Blinded reviewer worksheet + template | [REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md), [WORKSHEET_TEMPLATE.csv](WORKSHEET_TEMPLATE.csv) | Authored for OI-022 | Original; header-only, no observations |
| Adjudication record template | [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md) | Authored for OI-022 | Original; blank, no judgments |
| Metrics spec | [METRICS_SPEC.md](METRICS_SPEC.md) | Authored for OI-022 | Original; no thresholds set |
| Decision memo template | [DECISION_MEMO_TEMPLATE.md](DECISION_MEMO_TEMPLATE.md) | Authored for OI-022 | Original; blank, no decision |

## 2. What is NOT in this packet

- No real patient records, identifiers, images, specimens, or sequencing data.
- No retrospective clinical data, no EHR extracts, no registry data.
- No copied guideline passages, article text, or licensed terminology.
- No third-party code, model weights, prompts from other systems, or vendor
  materials (vendor arms, if any, are separately admitted per
  [PROTOCOL.md](PROTOCOL.md) §11 with their own recorded versions and terms).
- No reviewer identities, contact details, private correspondence, or
  institutional agreements (those live in an authorized restricted register).
- No results, scores, timings, or costs — observed or invented. The worksheet
  and memo templates are blank by design.

## 3. Provenance and derivation notes

- Journey *design patterns* (discussion-only preservation framing,
  hypothetical-only criterion framing, contradicted candidate, pending
  no-threat control, wrong-patient quarantine, amendment/supersession rules)
  follow the public OI-019 fixtures (`examples/synthetic/oi019-*`) and the
  IV-01 practice packet (`validation/iv01/cases.json`). No fixture text, ID,
  hash, or answer key is copied into OI-022; all OI-022 IDs (`OI022-FJ01`…,
  `CASE-OI022-*`, `PATH-FJ*`, `EVID-FJ*`) are new.
- Fictional finding keys and values are invented tokens. Any resemblance to a
  real assay, marker, trial, lesion classification, or person is coincidental
  and confers no meaning; under [PROTOCOL.md](PROTOCOL.md) §2 such
  resemblance is logged as a packet defect, not interpreted.
- Dates are fictional staging devices for the receipt clock, not real event
  dates.

## 4. Permitted use and redistribution

- Permitted use: offline synthetic evaluation exercises under the OI-022
  protocol (Gate 0/1). Nothing here authorizes real-data use, clinical
  pilots, outreach, procurement, or deployment.
- A `Rights: original-synthetic` header on a fictional evidence note declares
  packet authorship only. It is **not** proof of copyright ownership, lawful
  AI training rights, patient consent, clinical suitability, or fitness for
  any other purpose.
- The project's distribution license is undecided (see repository README).
  This manifest does not select a license, clear Python/CI/browser
  distributions, trademarks, clinical use, or third-party services.
- Redistribution of completed worksheets or memos must respect the approved
  sharing scope in [PROTOCOL.md](PROTOCOL.md) §1: anonymous reviewer IDs
  only, no personal data, and the mandatory header *"Synthetic
  staged-journey result; not clinical validation."*

## 5. Freeze-time manifest obligations (coordinator)

At freeze, the coordinator appends (in the immutable freeze record, not by
editing this file's history):

1. SHA-256 of every staged source file and of the source manifest itself.
2. The packet revision (commit) and the evaluated software/vendor revisions.
3. Confirmation that every fictional evidence note carries exactly one
   `Rights: original-synthetic` header and that no other rights declaration
   appears.
4. Confirmation that no real identifiers or restricted text were found on
   review, with the reviewer's anonymous ID and date.
5. The immutable location of the signed threshold table and freeze checklist.

Until these are recorded, the packet is `not_activated`.
