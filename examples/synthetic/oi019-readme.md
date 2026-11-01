# OI-019 synthetic cases for option-preservation evaluation

All files prefixed `oi019-` are independently authored, fictional, and NOT
advice, NOT a treatment recommendation, and NOT a clinical appraisal. No real
patient data, no copied medical source content, no real trial or guideline is
referenced. These fixtures exercise only the existing case / source /
evidence / investigation models in `src/open_intelligence/store.py`; they
change no contract, schema, or stored state shape.

## The two cases

| Case | T0 (baseline) | T1 (new information) | T2 (amendment) |
| --- | --- | --- | --- |
| `CASE-OI019-A` | `oi019-a-t0-pathology.txt`, `oi019-a-t0-imaging.txt` | `oi019-a-t1-clinical.txt` | `oi019-a-t2-clinical-amended.txt` (amends `CLIN-OI019-A@1`) |
| `CASE-OI019-B` | `oi019-b-t0-pathology.txt`, `oi019-b-t0-imaging.txt` | `oi019-b-t1-clinical.txt` | `oi019-b-t2-clinical-amended.txt` (amends `CLIN-OI019-B@1`) |

Staging is by file import, not by a new cutoff field: a T0 replay imports
only the T0 files, so T1/T2 document IDs, findings, and wording are absent
from that store. T2 files are amendments of the T1 clinical documents only
(same type and event date, as the store requires); the T0 documents are never
amended here.

## The four evaluation elements (and where each lives)

1. **Suspected specimen/tissue preservation DISCUSSION before a planned
   operation** — Case A, T1/T2: `preservation-discussion` is `reported`,
   `preservation-decision` is `not-reported`, and
   `preservation-feasibility` is `indeterminate`. It is a discussion
   candidate only: no decision was recorded and feasibility is unknown,
   before and after the T2 amendment.
2. **HYPOTHETICAL trial criterion potentially affected by planned
   treatment** — Case B, T1/T2: `hypothetical-criterion` is `reported` but
   no actual trial is identified, `criterion-applicability` is
   `indeterminate`, and `treatment-effect-on-criterion` is `indeterminate`.
   Nothing in the record says the criterion applies or that treatment
   affects it.
3. **Knowingly invalid candidate option** — Case B: the candidate option
   requires a Marker A-positive sample (`candidate-assay-option`), while the
   T0 pathology reports Marker A `negative`. It is invalid on the face of
   the record, assessed as `contradicts` / `not_applicable` against
   `oi019-evidence-invalid.txt`.
4. **No-threat control** — Both cases: the imaging `comparison` finding
   stays `pending` at every cutoff. It threatens no option and is never
   promoted to a candidate; assessed as `context` against
   `oi019-evidence-control.txt`.

## Supporting / contradicting sources, for a reviewer

- Discussion framing: `EVID-OI019-DISCUSSION` (`oi019-evidence-discussion.txt`),
  assessed `supports` / `limited` on the Case A discussion question.
- Hypothetical framing: `EVID-OI019-HYPOTHETICAL`
  (`oi019-evidence-hypothetical.txt`), assessed `supports` / `limited` on
  the Case B criterion question.
- Invalid option: `EVID-OI019-INVALID` (`oi019-evidence-invalid.txt`),
  assessed `contradicts` / `not_applicable` on the Case B validity question,
  contradicted by the T0 `marker-a = negative` assertion.
- Control: `EVID-OI019-CONTROL` (`oi019-evidence-control.txt`), assessed
  `context` on the control question.

## Explicit unknowns (not gaps to be filled by inference)

- Case A: whether preservation is feasible; what quantity could be
  preserved; whether any future fictional testing exists or would use it.
- Case B: whether any actual trial exists; whether any hypothetical
  criterion would apply; whether planned treatment would affect it;
  whether the Marker A-positive candidate could ever become valid
  (nothing in the record makes it valid).
- Both cases: the pending imaging comparison; the descriptive lesion
  classification, which remains pending further review.

## Baseline output

The "ordinary case brief" is the T0-only snapshot in
`tests/test_option_preservation.py`: it lists only T0 findings and contains
no treatment recommendation wording at any cutoff. The full-timeline
snapshots are the head-to-head comparison input, not a replacement brief.

## Guard files

- `oi019-wrong-patient.txt` declares `CASE-OI019-B` and must quarantine
  when imported into `CASE-OI019-A`; a byte-identical re-import is a noop.
- Out-of-order import (a T2 amendment before its T1 original, or an
  `Amends` pointing at the wrong version) must be rejected by the store.
- Cross-case snapshot sources must be rejected by the store.
