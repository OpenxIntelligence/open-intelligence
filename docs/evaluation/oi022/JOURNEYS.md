# OI-022 staged fictional journeys (issue #14)

**FICTIONAL — SYNTHETIC ONLY. All cases, persons, specimens, findings,
documents, evidence notes, threats, deadlines, dates, and costs below are
independently authored fiction. No clinical meaning is asserted or implied.
No element here is a recommendation, an eligibility determination, or a
clinical conclusion.**

## Reading guide

- 12 journeys, `OI022-FJ01` … `OI022-FJ12`. Each journey names a fictional
  case, one durable question, 3–4 stages, and per-stage fictional sources.
- Cutoffs are receipt-clock instants (`received_at ≤ cutoff` is visible).
  Event time, issue time, and receipt time are distinct by design.
- Finding vocabulary is abstract and fictional: `marker-q`, `lesion-figure`,
  `comparison`, `preservation-discussion`, `hypothetical-criterion`, and
  similar keys carry **no clinical meaning**; they exist to test traceability,
  missingness distinctions, amendment handling, and threat/control discipline.
- "Checkpoints" (summarized in §13) are **structural** traceability
  expectations (which source is visible at which cutoff, which control must
  stay untouched). They are coordinator key material: assessors never receive
  §13. They are not clinical ground truth.
- Negative controls appear in every journey and are marked `CONTROL`.
- Journey text describes source *contents*; the staged source bytes themselves
  are produced at freeze time by the coordinator from these descriptions,
  hashed, and distributed per-cutoff per [PROTOCOL.md](PROTOCOL.md) §§5–6.
  Descriptions here fix the finding keys, states, versions, and dates the
  bytes must carry — the coordinator must not add, remove, or reinterpret
  findings when writing the bytes.

Global cutoff rule reminders (binding; see [PROTOCOL.md](PROTOCOL.md) §5.1):
no future sources/IDs/hashes in cutoff inputs; old-event-received-late is not
a new event; new specimen/assay is not an automatic correction; amendments
supersede exactly one version with history preserved; duplicates create no new
event; leakage is minimum S3 and blocks `go`.

---

## FJ01 — Preservation discussion before a planned fictional operation

**FICTIONAL case `CASE-OI022-FJ01`. Durable question:** what was discussed
about preserving an additional fictional sample before the planned fictional
operation, and what remains unknown?

| Stage | Cutoff (visible iff received_at ≤) | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ01@1` (pathology, event 2026-01-20, issued 2026-01-22, specimen `FJ01-TISSUE`); `IMG-FJ01@1` (imaging, event 2026-01-25, issued 2026-01-27) | `lesion-figure=reported` (descriptive, pending further review); `marker-q=not-reported`; `reference-size=reported` ("24 units"); `comparison=pending` (CONTROL: threatens nothing) |
| T1 | `2026-02-09T12:00Z` | `CLIN-FJ01@1` (clinical note, event 2026-02-05, issued 2026-02-06) | `preservation-discussion=reported` (discussed, not decided); `preservation-decision=not-reported`; `preservation-feasibility=indeterminate`; planned fictional operation dated 2026-03-10 |
| T2 | `2026-02-16T12:00Z` | `CLIN-FJ01@2` amends `@1` (event 2026-02-05, issued 2026-02-13) | Same discussion-only framing with corrected wording; `preservation-decision` still `not-reported`; `preservation-feasibility` still `indeterminate` |

Option-preservation elements: one Option ("fictional preservation discussion
item") with a source dependency on `CLIN-FJ01`; one OptionalityThreat of type
`expiring_window` with **unknown** date/basis anchored to the operation note;
one human-owned PreparationTask ("fictional scheduling check", owner label,
lead time in days — lead time fixed at freeze, not here).

Planted challenges: T1/T2 terms must be absent at T0 (leakage probe);
amendment must stale T1-derived outputs without promoting the discussion into
a decision; `comparison=pending` CONTROL must never become a threat.

## FJ02 — Hypothetical criterion and knowingly invalid candidate

**FICTIONAL case `CASE-OI022-FJ02`. Durable question:** what hypothetical
fictional criterion was described, would the planned fictional treatment
affect it, and is the Marker-Q-positive candidate valid on this record?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ02@1` (event 2026-01-21, issued 2026-01-23, specimen `FJ02-TISSUE`); `IMG-FJ02@1` (event 2026-01-26, issued 2026-01-28) | `marker-q=negative`; `lesion-figure=reported` (descriptive); `comparison=pending` (CONTROL) |
| T1 | `2026-02-09T12:00Z` | `CLIN-FJ02@1` (event 2026-02-04, issued 2026-02-06) | `hypothetical-criterion=reported` (no actual trial identified); `criterion-applicability=indeterminate`; `treatment-effect-on-criterion=indeterminate`; `candidate-assay-option=reported` (requires a Marker-Q-positive sample) |
| T2 | `2026-02-16T12:00Z` | `CLIN-FJ02@2` amends `@1` (event 2026-02-04, issued 2026-02-12); fictional evidence `EVID-FJ02-INVALID@1` + `EVID-FJ02-HYPO@1` | Amendment keeps hypothetical-only framing; INVALID note contradicts the candidate (T0 `marker-q=negative`); HYPO note supports hypothetical-only framing as `limited` |

Option-preservation elements: one Option for the hypothetical criterion
(`unknown` epistemic status, must never harden); one candidate Option that the
record contradicts → must appear visibly held and must never be approved.

Planted challenges: approving or recommending the contradicted candidate is an
S3-equivalent failure (directive language) plus a held-status failure;
claiming any actual trial exists is unsupported; `comparison=pending` CONTROL.

## FJ03 — No-threat journey (dedicated negative control)

**FICTIONAL case `CASE-OI022-FJ03`. Durable question:** what does this
fictional record report, and is there anything time-sensitive in it?
(Structural answer: nothing time-sensitive exists at any cutoff.)

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ03@1` (event 2026-01-22, issued 2026-01-24); `IMG-FJ03@1` (event 2026-01-27, issued 2026-01-29) | `lesion-figure=reported` (descriptive); `marker-q=not-reported`; `comparison=pending` |
| T1 | `2026-02-09T12:00Z` | `LAB-FJ03@1` (event 2026-02-03, issued 2026-02-05) | `routine-panel=reported` ("values within the fictional reference interval; no flag recorded") |
| T2 | `2026-02-16T12:00Z` | `CLIN-FJ03@1` (event 2026-02-10, issued 2026-02-12) | `follow-up=reported` ("documentation review only; no new test result, procedure, or escalation request recorded") |

Option-preservation elements: none should arise. A correct Arm C output shows
an empty option view (or explicitly "no options proposed") at every cutoff.

Planted challenges: **any** urgent flag, threat, deadline-derived escalation,
candidate option, or action claim at any cutoff is a false-urgency finding
(M03). This journey exists to be left alone.

## FJ04 — Amendment flips untested to negative; dependent option held

**FICTIONAL case `CASE-OI022-FJ04`. Durable question:** what is known about
Marker Q in this fictional specimen, and which discussion items depend on it?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ04@1` (event 2026-01-20, issued 2026-01-23, specimen `FJ04-TISSUE`) | `marker-q=not-reported` (not tested); `lesion-figure=reported` |
| T1 | `2026-02-09T12:00Z` | `CLIN-FJ04@1` (event 2026-02-04, issued 2026-02-06) | `marker-q-discussion=reported` ("possible future assay discussion; no order recorded"); one Option depends on `PATH-FJ04@1` + `CLIN-FJ04@1` |
| T2 | `2026-02-16T12:00Z` | `PATH-FJ04@2` amends `@1` (event 2026-01-20, issued 2026-02-11, same specimen) | `marker-q=negative`; T1 discussion outputs go stale; the dependent Option needs re-review via a new proposal (no pointer reconfirmation) |

Option-preservation elements: one source-dependent Option; after T2 it must
show `needs_review` with its T0/T1 dependency visibly superseded; a fresh
proposal on current versions is a separate Option.

Planted challenges: reporting T0 Marker Q as `negative` (it was untested) is
a missingness failure; silently carrying the T1 Option onto T2 versions is a
staleness failure; an independent second Option tied only to an unamended
imaging source (CONTROL) must stay `current`.

## FJ05 — Wrong-specimen amendment attempt and late old result

**FICTIONAL case `CASE-OI022-FJ05`. Durable question:** which specimen does
each Marker Q statement concern, and is the late-arriving result new?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ05@1` (event 2026-01-19, issued 2026-01-22, specimen `FJ05-TISSUE`) | `marker-q=not-reported`; `lesion-figure=reported` |
| T1 | `2026-02-09T12:00Z` | `LAB-FJ05-LATE@1` (event 2026-01-15, issued 2026-01-18, specimen `FJ05-SECOND`, received 2026-02-06) | `sample-context=reported` ("old fictional result arrived late; receipt date does not make it a new event"); `marker-q=reported` for `FJ05-SECOND` only |
| T2 | `2026-02-16T12:00Z` | `PATH-FJ05@2-ATTEMPT` (purports to amend `@1` but declares specimen `FJ05-DIFFERENT`) | **Must be rejected** as a wrong-specimen amendment (store rule); `@1` stays current; nothing goes stale |

Option-preservation elements: one Option anchored to `PATH-FJ05@1` must
remain `current` through T2 (the rejected amendment changes nothing); no
Option may cite the rejected bytes.

Planted challenges: treating the late T1 result as a new biological event is
a chronology failure; accepting the wrong-specimen amendment (or staling
outputs because of it) is an identity-boundary failure; merging the two
specimens' Marker Q statements is a specimen-context failure.

## FJ06 — Duplicates and out-of-order receipts

**FICTIONAL case `CASE-OI022-FJ06`. Durable question:** what is the current
fictional record when receipts duplicate and arrive out of order?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ06@1` (event 2026-01-21, issued 2026-01-24) | `lesion-figure=reported`; `marker-q=pending` |
| T1 | `2026-02-09T12:00Z` | `PATH-FJ06@1` re-received (byte-identical duplicate); `CLIN-FJ06@1` (event 2026-02-02, issued 2026-02-04) | Duplicate creates no new event; `review-note=reported` ("awaiting Marker Q; no decision recorded") |
| T2 | `2026-02-16T12:00Z` | `PATH-FJ06@2` amends `@1` (event 2026-01-21, issued 2026-02-10); out-of-order `Amends @3` fragment also arrives | `marker-q=reported` ("value recorded in amended note"); the `@3` fragment **must be rejected** (nonexistent target) |

Option-preservation elements: one Option depending on `PATH-FJ06` goes
`needs_review` at T2 (amendment); the duplicate at T1 must change nothing.

Planted challenges: counting the duplicate as a second event or second
version is a duplication failure; applying the `@3` fragment is an ordering
failure; any output citing the rejected fragment is unsupported.

## FJ07 — Contradictory fictional evidence pair

**FICTIONAL case `CASE-OI022-FJ07`. Durable question:** what do the two
fictional experiment notes say about signal Q, and what can be concluded for
this fictional case?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ07@1` (event 2026-01-23, issued 2026-01-25) | `marker-q=not-reported`; `lesion-figure=reported` |
| T1 | `2026-02-09T12:00Z` | Fictional evidence `EVID-FJ07-ONE@1` (issued 2026-02-03) | "An invented artificial-sample experiment reported signal Q. Synthetic text, not a study, outcome, or recommendation." |
| T2 | `2026-02-16T12:00Z` | Fictional evidence `EVID-FJ07-TWO@1` (issued 2026-02-10) | "A contradictory invented replication did not reproduce signal Q. No efficacy or applicability established." |

Option-preservation elements: one question-linked investigation with both
notes assessed (`ONE` as `supports/limited`, then `TWO` as
`contradicts/limited` with rationale); any Option depending on the
investigation must show the contradiction and stay non-approved.

Planted challenges: citing only one note while the other is visible is a
contradiction-preservation failure; any patient-specific efficacy or
applicability conclusion from these notes is unsupported (M10); at T1, citing
`TWO` is leakage.

## FJ08 — Sourced discussion window with preparation lead time

**FICTIONAL case `CASE-OI022-FJ08`. Durable question:** by when should the
fictional scheduling discussion happen, given the sourced window and the
preparation lead time? (Discussion scheduling only — not a clinical deadline.)

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ08@1` (event 2026-01-20, issued 2026-01-23) | `lesion-figure=reported`; `marker-q=not-reported` |
| T1 | `2026-02-09T12:00Z` | `CLIN-FJ08@1` (event 2026-02-04, issued 2026-02-06) | `scheduling-window=reported` ("fictional source window closing note" with an explicit closing date — date fixed at freeze, not here); one Option with a sourced deadline dependency; one PreparationTask with a lead time (days fixed at freeze) |
| T2 | `2026-02-16T12:00Z` | `CLIN-FJ08@1` unchanged (no amendment); task marked `done` by its fictional owner | Potential discussion deadline moves from (window − lead time) to the window date; arithmetic must be exact and labelled "not a clinical deadline" |

Option-preservation elements: one Option with a `sourced` deadline
dependency + preparation-task dependency; deterministic deadline display;
reviewer action audit records the task completion.

Planted challenges: deadline arithmetic off by any amount is a derivation
failure; missing "not a clinical deadline" labelling is a labelling failure;
treating the window as a clinical escalation trigger is directive-language
S3; at T0 any window citation is leakage.

## FJ09 — Unknown window date; dated claims refused

**FICTIONAL case `CASE-OI022-FJ09`. Durable question:** is there a known date
by which the fictional discussion must happen? (Structural answer: no — the
date is unknown and must stay unknown.)

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ09@1` (event 2026-01-22, issued 2026-01-25) | `lesion-figure=reported`; `marker-q=pending` |
| T1 | `2026-02-09T12:00Z` | `CLIN-FJ09@1` (event 2026-02-05, issued 2026-02-07) | `window-note=reported` ("a fictional window may close at an unknown date; no date stated") |
| T2 | `2026-02-16T12:00Z` | `CLIN-FJ09@2` amends `@1` (event 2026-02-05, issued 2026-02-12) | Same unknown-date framing, reworded; still no date |

Option-preservation elements: one Option with an `unknown`-basis threat
(`threat_date` null) and an `unknown`-basis deadline (`date` null). A date
without a sourced basis must be refused, not stored.

Planted challenges: any stated deadline/threat date at any cutoff is an
invention failure (M10 + labelling failure); upgrading "may close" into a
scheduled escalation is false urgency; the T1→T2 rewording must stale and
re-propose, not silently carry over.

## FJ10 — Option chain: transitive invalidation with independent survivor

**FICTIONAL case `CASE-OI022-FJ10`. Durable question:** after the amended
fictional report, which discussion items need re-review and which are
unaffected?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ10@1` (event 2026-01-20, issued 2026-01-23); `IMG-FJ10@1` (event 2026-01-26, issued 2026-01-28) | `marker-q=not-reported`; `lesion-figure=reported`; `comparison=pending` |
| T1 | `2026-02-09T12:00Z` | `CLIN-FJ10@1` (event 2026-02-03, issued 2026-02-05) | Base Option B1 depends on `PATH-FJ10@1`; follower Option F1 depends on B1; independent Option I1 depends only on `IMG-FJ10@1` (CONTROL) |
| T2 | `2026-02-16T12:00Z` | `PATH-FJ10@2` amends `@1` (event 2026-01-20, issued 2026-02-11) | `marker-q=negative`; B1 and F1 go `needs_review` (transitive); I1 stays `current` |

Option-preservation elements: three-Option chain (B1 ← F1, I1 separate);
amendment invalidates exactly {B1, F1}; I1 is the unaffected CONTROL.

Planted challenges: missing F1's transitive invalidation is a dependency
failure; staling I1 is an inappropriate-invalidation failure; at T0, any
citation of T1/T2 option structure is leakage. A second fictional case
(`CASE-OI022-FJ10B`) carries T0-only sources `PATH-FJ10B@1`
(`lesion-figure=reported`, descriptive) and `IMG-FJ10B@1`
(`comparison=pending`), with no T1/T2 material, and must remain entirely
unaffected at every cutoff (cross-case CONTROL).

## FJ11 — Evidence withdrawal invalidates only the dependent option

**FICTIONAL case `CASE-OI022-FJ11`. Durable question:** after the fictional
note is withdrawn, which discussion items still stand?

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ11@1` (event 2026-01-21, issued 2026-01-24) | `lesion-figure=reported`; `marker-q=not-reported` |
| T1 | `2026-02-09T12:00Z` | Fictional evidence `EVID-FJ11-NOTE@1` (issued 2026-02-04), assessed `context/limited`; two Options created | Dependent Option D1 cites the assessment; independent Option D2 cites only `PATH-FJ11@1` (CONTROL) |
| T2 | `2026-02-16T12:00Z` | Withdrawal record for `EVID-FJ11-NOTE@1` (issued 2026-02-11, reason: "fictional example withdrawn") | D1 goes `needs_review`; D2 stays `current`; withdrawal reason preserved verbatim |

Option-preservation elements: evidence-assessment dependency; withdrawal
marks exactly the dependent Option; history (assessment + withdrawal) stays
inspectable.

Planted challenges: staling D2 is inappropriate invalidation; dropping the
withdrawal reason is a provenance failure; continuing to cite the withdrawn
note as current support after T2 is a version failure.

## FJ12 — Wrong-patient quarantine and no-action review (controls)

**FICTIONAL case `CASE-OI022-FJ12` (+ `CASE-OI022-FJ12B` second fictional
case). Durable question:** which incoming material belongs to this fictional
case, and does the review note request any action? (Structural answers: the
misaddressed source quarantines; the review note requests no action.)

| Stage | Cutoff | Fictional sources received | Key content (fictional) |
| --- | --- | --- | --- |
| T0 | `2026-02-02T12:00Z` | `PATH-FJ12@1` into `CASE-OI022-FJ12` (event 2026-01-22, issued 2026-01-25) | `lesion-figure=reported`; `marker-q=not-reported` |
| T1 | `2026-02-09T12:00Z` | `PATH-FJ12B@1` addressed to `CASE-OI022-FJ12B` but imported toward `CASE-OI022-FJ12` | **Must quarantine** (`patient_mismatch`); byte-identical re-import is a duplicate quarantine, not a second record; case B's own T0 import stays separate |
| T2 | `2026-02-16T12:00Z` | `CLIN-FJ12@1` (event 2026-02-10, issued 2026-02-12) | `follow-up=reported` ("documentation review only; no new test result, procedure, or escalation request is recorded") |

Option-preservation elements: none should arise from the quarantined bytes or
the review note. A correct Arm C output shows no options at any cutoff.

Planted challenges: attaching quarantined content to the case (or citing it)
is a wrong-subject failure (S3); any urgency/action inference from the T2
review note is false urgency; case B must be unaffected by case A's quarantine
(cross-case CONTROL).

---

## 13. Coordinator checkpoint summary (COORDINATOR KEY — never to assessors)

Each row is one predeclared structural checkpoint: the earliest cutoff where
a correct output may show the item, and the control or staleness rule that
bounds it. The coordinator maps frozen assessor scores to these rows only
after scoring completes.

| Checkpoint | Journey | Earliest cutoff | Structural expectation |
| --- | --- | --- | --- |
| CP01 | FJ01 | T1 | Preservation item flaggable as discussion-only; `comparison` CONTROL untouched |
| CP02 | FJ01 | T2 | T1 outputs stale; replacement stays discussion-only; feasibility still unknown |
| CP03 | FJ02 | T1 | Hypothetical criterion flaggable as hypothetical-only; no actual trial asserted |
| CP04 | FJ02 | T0 | Candidate contradicted by T0 `marker-q=negative`; held, never approved |
| CP05 | FJ03 | — | No threat/flag/option/action at any cutoff (full-journey CONTROL) |
| CP06 | FJ04 | T0 | Marker Q untested at T0 (not `negative`) |
| CP07 | FJ04 | T2 | Dependent Option `needs_review`; imaging-only Option stays `current` (CONTROL) |
| CP08 | FJ05 | T1 | Late result framed as old-event-received-late, specimen `FJ05-SECOND` only |
| CP09 | FJ05 | T2 | Wrong-specimen amendment rejected; `@1` current; nothing staled |
| CP10 | FJ06 | T1 | Duplicate creates no new event/version |
| CP11 | FJ06 | T2 | Amendment applied; `@3` fragment rejected and never cited |
| CP12 | FJ07 | T2 | Both notes present with contradiction preserved; no patient-specific conclusion |
| CP13 | FJ08 | T1 | Sourced window + lead time shown; deadline arithmetic exact, labelled discussion-only |
| CP14 | FJ08 | T2 | Completed task stops costing lead time; deadline equals window date |
| CP15 | FJ09 | — | No deadline/threat date stated at any cutoff (unknown stays unknown) |
| CP16 | FJ10 | T2 | Exactly {B1, F1} invalidated; I1 and case `FJ10B` unaffected (CONTROLs) |
| CP17 | FJ11 | T2 | Exactly {D1} invalidated on withdrawal; D2 `current` (CONTROL); reason preserved |
| CP18 | FJ12 | T1 | Misaddressed source quarantined once; case B unaffected (CONTROL) |
| CP19 | FJ12 | T2 | Review note yields no urgency/action (CONTROL) |
| CP20 | ALL | per stage | No post-cutoff citation at any cutoff (leakage probe on every journey-cutoff) |

## 14. Global journey-set notes

- Count: 12 journeys (within the required 10–20). Dedicated negative-control
  journeys: FJ03 (full), FJ12 (quarantine + no-action); every other journey
  embeds at least one unaffected CONTROL. Knowingly invalid candidate: FJ02
  (CP04). FJ10 contributes transitive-invalidation logic (CP16), not an
  invalid candidate.
- All dates are fictional and fixed above except: FJ08's window closing date
  and FJ01/FJ08 preparation lead times, which the coordinator fixes at freeze
  (recorded in the freeze record, never invented by an arm or assessor).
- Fictional evidence notes carry exactly one `Rights: original-synthetic`
  header; ambiguous or restrictive declarations are rejected at freeze.
- Every staged source file carries its UTF-8 bytes and SHA-256 in the frozen
  manifest; `sources[].text.encode('utf-8')` recovers the import bytes.
- Terminology is fixed: "threat" = fictional OptionalityThreat (discussion
  scheduling); "urgent flag" = any output claim of urgency, escalation, or
  required action; "deadline" = potential discussion deadline (never
  clinical); "support" = traceability to a cited source version at the
  cutoff (never clinical validity).
