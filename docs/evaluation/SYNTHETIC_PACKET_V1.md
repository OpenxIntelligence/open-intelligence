# Open Intelligence — Synthetic evaluation packet v1

**Status: development fixture and evaluation preparation, not an independent study.**
This implements the software/preparation portion of [issue #22](https://github.com/OpenxIntelligence/open-intelligence/issues/22), aligned to existing OI-003/004/009/010/011. It complements the existing architecture; no stack, model, data-access or product direction changes. The broader independent-evaluation protocol in draft PR #18 remains proposed.

## What is included

Two entirely fictional subjects, ten original authored source deliveries, three simulated cutoff rounds, an offline packet projector, coordinator expectations and a blank reviewer worksheet. Cases use existing OI-SYNTHETIC-REPORT/1 and OI-SYNTHETIC-EVIDENCE/1 formats. Repeated source bytes retain the same SHA-256; every simulated arrival keeps its own identifier and availability time. The authored time is not proof of when a real record was known.

These are **development cases**, not held-out clinical cases or a representative oncology sample. The same assistant authored implementation and fixtures. Public coordinator keys mean this repository is not a secure blinded study. Future independent reviewers must not have authored/tuned the cases; use separately controlled and prospectively frozen held-out packets for actual evaluation. No independent reviewer or clinical result is recorded here.

## Run

From the repository root (Python standard library only):

```sh
python -m tools.evaluation_packet evaluation/synthetic_v1/fixture.json --round R1 > packet-r1.json
python -m tools.evaluation_packet evaluation/synthetic_v1/fixture.json --round R2 > packet-r2.json
python -m tools.evaluation_packet evaluation/synthetic_v1/fixture.json --round R3 > packet-r3.json
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python tests/browser_journey.py
```

Do not give the fixture manifest, later-round packets, this coordinator-facing document or the answer key to an evaluator claiming blindness. Give only the selected packet and the neutral worksheet. Keep the full manifest and key under coordinator control in any future held-out evaluation. The packet preserves corrupt/misdirected arrivals as challenges, not as accepted patient facts. Existing CaseStore handles their validation/quarantine.

The exporter filters by **simulated availability**, not the event/issued date inside source text. It does not implement `as_known_at` queries in the production CaseStore. Receipt and computation times in the running application remain actual execution times; the fixture is a staged input exercise. No medical state is inferred by the exporter.

## Reproducibility and integrity

The fixture records the pre-change baseline commit `769295bb06400c98057435c1a178621c05be4412`. Record the exact tested feature/merge SHA separately using `git rev-parse HEAD`; do not claim the new exporter exists at the pre-change commit. Freeze source/packet hashes, Python version, commands, result logs and reviewer method before a comparative evaluation. Hashes detect changes relative to this manifest, not malicious alteration of both file and manifest, source authenticity or legal rights.

No third-party article, medical terminology corpus, patient record or model is bundled. Original authorship is declared by this project; the schema is not an automated rights verifier. This work does not change the undecided project distribution license.

## Three comparisons, no fabricated scores

A. Manual source review of the selected time-frozen packet using the blank worksheet.
B. Simple source ordering and structured source-linked review, with no model assistance.
C. Existing Open Intelligence case/evidence workflow using the same available source bytes.

Use equivalent case/time exposure. Record cold-start and update tasks separately. Count acquisition, preparation, source lookup, review, correction and coordination minutes for every participant, plus source omissions, unsupported assertions and action errors. Do not report a time saving when work was merely moved to another person. If reviewer knowledge of earlier conditions affects results, report that limitation and use a controlled assignment plan.

## Proposed reviewer rubric — not clinical thresholds

| Dimension | What to record |
|---|---|
| Source fidelity | Source ID, line, version, quoted statement, whether the output preserves it |
| Time | Available at selected cutoff? Event vs issue vs receipt distinguished? |
| Identity | Intended case, declared patient, specimen; quarantine/rejection handled? |
| Uncertainty | Negative, unknown, pending, not-assessed and conflicting kept distinct? |
| Authority | Ordered is not administered; review is not clinical authorization |
| Correction | Dependent output flagged, original retained, replacement not auto-approved |
| Burden | All participant minutes, errors/corrections, incomplete work and abstentions |

For this *software challenge only*, any future-source leak, wrong-case/wrong-specimen accepted link, altered source bytes or silent promotion of a stale conclusion is a stop-and-repair defect. These are engineering invariants, not established clinical success thresholds. Qualified independent reviewers must pre-specify clinical severity, denominators, acceptance thresholds and disagreement handling before any clinical evaluation; those fields remain unapproved.

## Remaining issue #22 work

This is a prepared development packet, not completion of IV-01–03 external evaluation. Still needed: independently authored/controlled held-out cases; expert plausibility review; independent reviewer/conflict records; prospective severity and success thresholds; adjudicated reference standards; measured manual/simple/product results; signed go/repair/stop decision. No outreach, real records, retrospective study, patient enrollment or wet-lab work is authorized or performed.
