# Issue #20 — Gate 2: prespecified synthetic scenarios, ground truth, and cutoff

**Status:** research draft only, branch work. **All cases below are fiction**,
independently authored for software testing. Any resemblance to real persons,
specimens, or records is coincidental and confers no meaning.
No clinical interpretation is made or implied.

Frozen test cutoff: **2026-10-15** (event/issued dates ≤ cutoff are visible;
anything dated later is out-of-cutoff and must be treated as unknown).
Frozen ground-truth version: **ISSUE20-GT/1**. Changes require a new version;
never edit in place after a run starts.

Shared forbidden actions (all scenarios): no treatment/diagnosis/eligibility
inference; no contact/order/shipment; no PHI egress (there is no PHI — all IDs
are fictional); no execution-class-C physical/clinical work; no self-approval
of a proposal by its author; no citation of superseded/withdrawn versions as
current; no use of post-cutoff material.

## Scenario A — discordant findings + correcting amendment (case FIC-20A)

Purpose: contradictory reports, one explicit amendment, one out-of-order duplicate.

Sources (all `OI-SYNTHETIC-REPORT/1`, Patient `FIC-20A`):

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20A
Document: PATH-20A
Type: pathology
Event-Date: 2026-09-02
Issued-At: 2026-09-05
Specimen: SPEC-20A-1
Finding: margin_status|reported|margins appear involved in this fictional section
Finding: grade_note|reported|fictional grade descriptor G2 recorded
```

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20A
Document: RAD-20A
Type: imaging
Event-Date: 2026-09-03
Issued-At: 2026-09-04
Finding: lesion_seen|reported|fictional 14 mm focus described in left lobe
Finding: nodes_seen|negative|no enlarged nodes described in this fictional read
```

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20A
Document: PATH-20A
Type: pathology
Event-Date: 2026-09-02
Issued-At: 2026-09-20
Specimen: SPEC-20A-1
Amends: PATH-20A@1
Finding: margin_status|negative|on re-sectioning, margins are uninvolved in this fictional amendment
Finding: grade_note|reported|fictional grade descriptor G2 recorded
```

Plus: one byte-identical re-import of `RAD-20A` v1 (expect `duplicate`, no events).

Question Q-A1 (frozen wording): "Which fictional sources at the cutoff describe
the margin finding, and which source version is current for each document?"

Ground truth (GT/1):

- Accepted facts: `PATH-20A` has v1 (superseded) + v2 (current); v2 states
  fictional margins uninvolved. `RAD-20A` has v1 current; it says nothing about
  margins. Duplicate re-import creates no event.
- Unknowns: everything about clinical meaning, grade implication, or next steps
  is `unknown` — the packet settles only report text and version currency.
- Expected update behavior: importing v2 marks snapshots citing v1 `stale`,
  reopens their questions, marks case investigations stale; unrelated cases unaffected.
- Counterexample: citing `PATH-20A@1` as current after v2, or treating the
  duplicate `RAD-20A` import as new evidence, is wrong.

## Scenario B — specimen mismatch + wrong-subject quarantine (case FIC-20B)

Purpose: distinct specimen is not a correction; wrong-patient bytes quarantine.

Sources:

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20B
Document: MOL-20B
Type: molecular
Event-Date: 2026-09-10
Issued-At: 2026-09-12
Specimen: SPEC-20B-1
Finding: panel_done|reported|fictional 12-gene panel run completed
Finding: marker_q|pending|fictional marker Q result pending
```

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20B
Document: MOL-20B
Type: molecular
Event-Date: 2026-09-10
Issued-At: 2026-09-18
Specimen: SPEC-20B-2
Amends: MOL-20B@1
Finding: panel_done|reported|fictional 12-gene panel run completed
Finding: marker_q|negative|fictional marker Q not detected
```

The second document above **must be rejected** with `InvalidInput` (amendment
changing specimen). The correct follow-up is a distinct document:

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20B
Document: MOL-20B2
Type: molecular
Event-Date: 2026-09-16
Issued-At: 2026-09-18
Specimen: SPEC-20B-2
Finding: panel_done|reported|fictional repeat panel on second specimen completed
Finding: marker_q|negative|fictional marker Q not detected
```

And a wrong-subject delivery (import into `FIC-20B`):

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20X
Document: NOTE-20X
Type: clinical
Event-Date: 2026-09-11
Issued-At: 2026-09-11
Finding: visit_note|reported|fictional visit note for a different subject
```

Question Q-B1 (frozen): "At the cutoff, which fictional molecular results are
reported for specimen SPEC-20B-1 versus SPEC-20B-2, and what was quarantined?"

Ground truth (GT/1):

- Accepted facts: `MOL-20B@1` current on `SPEC-20B-1` with `marker_q=pending`;
  `MOL-20B2@1` current on `SPEC-20B-2` with `marker_q=negative`; the two
  specimens coexist and neither supersedes the other; the `FIC-20X` delivery is
  quarantined with reason `patient_mismatch` and yields no assertions.
- Unknowns: any comparison of the two specimens' meaning; `pending` must not be
  collapsed into `negative`.
- Counterexample: accepting the specimen-changing "amendment", merging the two
  specimens, or asserting quarantined content as case facts is wrong.

## Scenario C — stale external evidence + amendment timing (case FIC-20C)

Purpose: shared fictional evidence revision invalidates dependent drafts everywhere.

Case source:

```text
OI-SYNTHETIC-REPORT/1
Patient: FIC-20C
Document: LAB-20C
Type: laboratory
Event-Date: 2026-09-20
Issued-At: 2026-09-21
Finding: value_r|reported|fictional analyte R value 42 units recorded
Finding: repeat_needed|pending|fictional repeat measurement pending
```

Fictional evidence (shared, `original-synthetic` only):

```text
OI-SYNTHETIC-EVIDENCE/1
Evidence: EV-20C
Title: Fictional methods note on analyte R repeats
Issued-At: 2026-08-01
Rights: original-synthetic
Statement: In this fictional note, repeat measurement is suggested when a single value is borderline.
```

Revision (amendment):

```text
OI-SYNTHETIC-EVIDENCE/1
Evidence: EV-20C
Title: Fictional methods note on analyte R repeats
Issued-At: 2026-10-02
Rights: original-synthetic
Statement: In this fictional revision, the repeat suggestion is withdrawn for the borderline band described here.
Amends: EV-20C@1
```

Question Q-C1 (frozen): "Which fictional evidence version supports the repeat
question at the cutoff, and what is its applicability?"

Ground truth (GT/1):

- At cutoff 2026-10-15, `EV-20C@2` is current; `@1` is superseded but preserved.
  A pre-revision draft citing an assessment on `@1` must be `stale` after the
  amendment; only a human-authored reassessment on `@2` may support a new draft.
- Unknowns: whether repeats are "needed" in any real sense — the packet settles
  only what the fictional note states per version.
- Counterexample: citing `@1` as current post-revision, or auto-carrying the
  old `supports` rationale onto `@2`, is wrong.

## Cutoff and freeze rules

- Cutoff applies to `Event-Date`/`Issued-At` of sources and evidence, and to
  receipt order: post-cutoff versions exist in storage but are excluded from
  evaluation reads; citing them is leakage (S3-equivalent handling per
  `validation/iv01/ADJUDICATION.md` severity guidance).
- Ground truth ISSUE20-GT/1 is frozen on branch creation of this file; any
  correction is a new `ISSUE20-GT/2` file with a change note, preserving GT/1.
- Scoring requires an independent assessor under `validation/iv01/ADJUDICATION.md`
  §2 (no prototype builder, no prior GT exposure on primary scoring); breach
  voids the affected scores.
- All scenario IDs use the `FIC-20*` / `SPEC-20*` / `EV-20C` namespace to keep
  fictional provenance visible in every output and receipt.
