# Issue #20 — Gate 2: prespecified synthetic scenarios, ground truth, and cutoff

**Status:** research draft only, branch work. **All cases below are fiction**,
independently authored for software testing. Any resemblance to real persons,
specimens, or records is coincidental and confers no meaning.
No clinical interpretation is made or implied.

Frozen test cutoff: **2026-10-15** (event/issued dates ≤ cutoff are visible;
anything dated later is out-of-cutoff and must be treated as unknown).
Frozen ground-truth version: **ISSUE20-GT/1**. Changes require a new version;
never edit in place after a run starts.

Byte-exactness: each `text` block below is the exact report/evidence bytes
(UTF-8, LF line endings, no CR/NUL, one trailing newline, ≤64 KiB reports /
≤32 KiB evidence). SHA-256 hashes are computed at run time from those bytes
and recorded; they are not prespecified here. Source-line anchors are 1-based
line numbers within each block (header = line 1).

Valid scope (what IS settled): report/evidence text per version, version currency
(current vs superseded/withdrawn), specimen identity per version, quarantine
reason, and which drafts must be stale after each amendment. Nothing else.

Shared forbidden actions (all scenarios): no treatment/diagnosis/eligibility
inference; no contact/order/shipment; no PHI egress (there is no PHI — all IDs
are fictional); no execution-class-C physical/clinical work; no self-approval
of a proposal by its author; no citation of superseded/withdrawn versions as
current; no use of post-cutoff material.

GT/1 contains no post-cutoff versions; all scenario dates are ≤ 2026-10-15.
A leakage probe (citing a future version) requires a separately frozen GT/2
addition; it must not be improvised during scoring.

## Scenario A — temporal discordance + correcting amendment (case FIC-20A)

Purpose: one explicit amendment reversing a finding, one negative-control
document saying nothing about that finding, one byte-identical duplicate.
Discordance here is temporal (PATH v1 `involved` vs v2 `uninvolved`), not
cross-document contradiction; RAD-20A is the control that must not be cited
for margins. Event order ≠ receipt order: PATH-20A v2 (event 2026-09-02,
issued 2026-09-20) arrives after RAD-20A (event 2026-09-03).

Frozen receipt order: `PATH-20A@1` → `RAD-20A@1` → `RAD-20A@1` duplicate →
`PATH-20A@2`. Expected import results: `imported`, `imported`, `duplicate`
(no event), `imported` with invalidation.

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

Question Q-A1 (frozen wording): "Which fictional sources at the cutoff describe
the margin finding, and which source version is current for each document?"

Ground truth (GT/1):

- Accepted facts: `PATH-20A` has v1 (superseded) + v2 (current); v2 states
  fictional margins uninvolved. `RAD-20A` has v1 current; it says nothing about
  margins. Duplicate re-import returns `duplicate` with the original source id
  and creates no event. Anchors: PATH v1 `margin_status` line 8, `grade_note`
  line 9; RAD v1 `lesion_seen` line 7, `nodes_seen` line 8; PATH v2
  `margin_status` line 9, `grade_note` line 10.
- Unknowns: everything about clinical meaning, grade implication, or next steps
  is `unknown` — the packet settles only report text and version currency.
- Expected update behavior: importing v2 marks snapshots citing v1 `stale`,
  reopens their questions to `open`, reopens dependent options
  (`needs_review`), stales anchor-exact inventory assertions on v1, and — only
  if ≥1 snapshot invalidated — marks all case investigations `stale=1`;
  unrelated cases unaffected.
- Opportunities: O-A1 version currency per document; O-A2 margin text per
  version with line anchor; O-A3 duplicate-is-no-event; O-A4 amendment fan-out
  (stale + reopen + history preserved).
- Counterexample: citing `PATH-20A@1` as current after v2, citing RAD-20A for
  margins, or treating the duplicate `RAD-20A` import as new evidence, is wrong.

## Scenario B — specimen mismatch + wrong-subject quarantine (case FIC-20B)

Purpose: distinct specimen is not a correction; wrong-patient bytes quarantine.

Frozen receipt order: `MOL-20B@1` → rejected specimen-changing amendment
(`InvalidInput`, no version, no event) → `MOL-20B2@1` → wrong-subject
`NOTE-20X` into `FIC-20B` (`quarantined`, `patient_mismatch`). A repeated
wrong-subject delivery of identical bytes returns `quarantined` with
`duplicate: true` and the original quarantine id, with no new event (loop
cycle 1 pre-run clarification: the earlier wording "`duplicate` quarantine"
mismatched the ledger's `result: quarantined` + `duplicate` flag; no frozen
bytes or expectations change).

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

- Accepted facts: `MOL-20B@1` current on `SPEC-20B-1` with `marker_q=pending`
  (line 9); `MOL-20B2@1` current on `SPEC-20B-2` with `marker_q=negative`
  (line 9); the two specimens coexist and neither supersedes the other; the
  rejected amendment creates no version and no event, leaving `MOL-20B` at v1
  current; the `FIC-20X` delivery is quarantined with reason `patient_mismatch`
  and yields no assertions for `FIC-20B` or `FIC-20X`.
- Unknowns: any comparison of the two specimens' meaning; `pending` must not be
  collapsed into `negative`; quarantined bytes are unread for case facts.
- Opportunities: O-B1 specimen-identity per document; O-B2 pending-vs-negative
  preserved; O-B3 rejected-amendment-is-no-version; O-B4 quarantine with reason
  and no assertions.
- Counterexample: accepting the specimen-changing "amendment", merging the two
  specimens, collapsing `pending` into `negative`, or asserting quarantined
  content as case facts is wrong.

## Scenario C — stale external evidence + amendment timing (case FIC-20C)

Purpose: shared fictional evidence revision invalidates dependent drafts everywhere.

Frozen receipt order: `LAB-20C@1` → `EV-20C@1` → human-authored assessment
A-C1 on `EV-20C@1` → draft D-C1 citing `LAB-20C@1` + A-C1 → `EV-20C@2`.
Evidence invalidation fans out across ALL cases sharing the version.

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

Frozen assessment A-C1 (human-authored, on `EV-20C@1`, for Q-C1):
relation `supports`, applicability `limited`, rationale (138 chars):
"Fictional note suggests repeat for borderline single values; LAB-20C value 42
units lacks a stated band, so applicability is limited to the described case."

Frozen draft D-C1 (human-authored, for Q-C1): summary (10–3000 chars) citing
`LAB-20C@1` + A-C1, e.g. "Fictional LAB-20C reports value 42 with repeat
pending; fictional EV-20C@1 discusses repeats with limited applicability."
Pre-revision D-C1 is `draft`; post-`EV-20C@2` it must be `stale` with its
question reopened to `open`.

Question Q-C1 (frozen): "Which fictional evidence version supports the repeat
question at the cutoff, and what is its applicability?"

Ground truth (GT/1):

- At cutoff 2026-10-15, `EV-20C@2` is current; `@1` is superseded but preserved
  (Statement line 6 in both versions). D-C1 citing A-C1 on `@1` must be `stale`
  after the amendment; only a human-authored reassessment on `@2` may support a
  new draft. LAB-20C anchors: `value_r` line 7, `repeat_needed` line 8.
- Unknowns: whether repeats are "needed" in any real sense — the packet settles
  only what the fictional note states per version.
- Opportunities: O-C1 evidence version currency; O-C2 assessment currency
  (A-C1 stale-bound); O-C3 draft staleness + question reopen; O-C4 global fan-out
  (any other case citing `@1` also stales).
- Counterexample: citing `@1` as current post-revision, auto-carrying the old
  `supports/limited` rationale onto `@2` without human reassessment, or leaving
  D-C1 `draft` after the amendment, is wrong.

## GT/1 coverage gaps → GT/2 requirements (loop cycle 1, no run started)

GT/1's frozen scenario bytes, text blocks, anchors, questions, and
opportunity IDs above are preserved unchanged. The loop review found
structural gaps that cannot be fixed by rewording; they require a separately
frozen `GT/2` addition (new file, change note, GT/1 retained). One pre-run
wording clarification was applied inline (the Scenario B duplicate-quarantine
return shape, flagged in place; no run started, no bytes changed) and must be
ratified verbatim in the GT/2 change note. Until GT/2 exists:

- **G2-a — no cross-document contradiction among current versions.** Scenario
  A is temporal (v1 vs superseded v2), explicitly not cross-document; B's
  specimens coexist; C's sources agree structurally. The research note asks
  for "contradictory reports". GT/1 covers temporal discordance only; a
  current-vs-current disagreement probe is uncovered. GT/2 must add one
  frozen pair (two current documents, same case and event window, disagreeing
  on one fictional finding) with its own question, or the evaluation must
  record cross-document contradiction as out of scope with rationale.
- **G2-b — weak out-of-order coverage.** A's event/receipt skew is an
  amendment delay (PATH v2, same event date as v1, arriving after RAD), not
  a new earlier-event document arriving late. GT/2 must add one delayed new
  document (event date earlier than a previously received document) or record
  the narrower coverage explicitly.
- **G2-c — O-C4 global fan-out is untestable in GT/1.** No second frozen case
  cites `EV-20C@1`, so "any other case citing @1 also stales" has no frozen
  witness. GT/2 must add a minimal second case (e.g. `FIC-20D` with one
  question, one assessment on `EV-20C@1`, one draft) with expected staleness,
  or O-C4 must be scored as not-applicable until then.
- **G2-d — no frozen drafts for A/B staleness.** Only C has a frozen
  assessment (A-C1) and draft (D-C1). GT/2 must add: D-A1 (pre-amendment
  draft citing `PATH-20A@1`, expected `stale` after v2 with question
  reopened) and D-B1 (draft citing `MOL-20B@1`, expected to stay current —
  the rejected amendment creates no version and must stale nothing).
- **Leakage probe.** GT/1 holds no post-cutoff versions by design; a
  future-version citation probe still requires the GT/2 addition already
  noted at the top of this file.

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
