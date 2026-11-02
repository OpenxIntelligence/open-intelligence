# Issue #20 — Gate 4: deterministic/manual baseline DESIGN (runnable verbatim)

**Status:** procedure only, **not run**. No results exist. This design must be
executed exactly as written by a future authorized run; any deviation voids
that run's record. All material is the frozen fiction from Gate 2
(`ISSUE20-GT/1`, cutoff **2026-10-15**). No clinical inference is in scope.

## 1. Arms (equal information, equal burden recording)

- **Arm A — manual source reading.** Reviewer reads the cutoff sources directly,
  writes answers to Q-A1/Q-B1/Q-C1, and records every quantity in §3.
- **Arm B — deterministic manifest sort + link list.** A stdlib-only script (to
  be authored at run time, no model, no new dependency) sorts the cutoff
  manifest by `(event_date, document_id, version)`, lists source/evidence
  version links, and flags: superseded versions cited, specimen-id mismatches
  across same-document versions, and evidence versions newer than the citing
  assessment. No summarization, no inference. The reviewer then answers from
  the sorted manifest plus sources, recording §3 quantities.

No model arm in this baseline. Arms share identical sources, frozen question
wording, identical cutoff, and identical burden forms.

Arm mapping (loop cycle 1 addition, to stop arm-label drift): the research
note's Arm A (deterministic/manual) is this Arm A; the research note's
optional Arm C (deterministic rules) is this Arm B; the research note's Arm B
(model-assisted) is deferred to Gate 5's revisit conditions and has no arm
here. Against `validation/iv01/BASELINE.md`: this Arm A/B match its Arm A/B;
its Arm C (the current application on the same inputs) is out of scope for
this issue-20 run because the comparator here is manual-vs-manifest, not an
application-output review — the OI-006/007/008/009 flow is the surrounding
system under which both arms' imports execute, not a third arm.

## 2. Verbatim procedure

1. Create a clean directory; pin and record the application commit under test,
   Python version, and `git status --porcelain` (must be empty; else stop).
2. Import Gate-2 scenario sources in receipt order: A (`PATH-20A@1`,
   `RAD-20A@1`, `RAD-20A@1` byte-identical duplicate, `PATH-20A@2`), B
   (`MOL-20B@1`, rejected specimen-changing amendment, `MOL-20B2@1`,
   wrong-subject delivery), C (`LAB-20C@1`, `EV-20C@1`, assessment on @1,
   draft citing it, `EV-20C@2`). Record every import result
   (`imported|duplicate|quarantined|rejected`) with ids. (Loop cycle 1 fix:
   the earlier shorthand omitted `RAD-20A@1` and mislabeled the duplicate.)
3. Arm A: reviewer answers Q-A1/Q-B1/Q-C1 from sources only. Start a wall-clock
   timer at first source open; stop when the answer sheet is frozen. Log every
   source open, every re-read, and every correction.
4. Arm B: author the manifest script ONLY from the §1 spec (sort, link list,
   three flag rules — no case-specific logic), freeze and hash the script file
   before GT is opened, then run it; record the script hash, stdout hash, wall
   time, and flags raised. Reviewer answers the same questions from manifest +
   sources with the same timer and logging rules. (Loop cycle 2 fix: a
   run-time-authored script frozen after seeing GT would be a retrofitting
   vector under `ADJUDICATION.md` §5.)
5. Two independent assessors score both arms against `ISSUE20-GT/1` using
   `validation/iv01/ADJUDICATION.md` Rubric A (claim-level source
   correctness) and Rubric B (uncertainty preserved/overstated), in separate
   columns, blind to each other's scores, with a dispute adjudicator for
   disagreements per §6 (loop cycle 1 fix: the earlier step cited a
   nonexistent "Gate-7 rubric" and a single assessor). Independence per §2
   (recused if they built anything under test or saw GT early). No peeking
   at GT during answering; GT opened only at scoring. Record per-question
   Rubric A outcomes (`correct|incorrect|unsupported|omitted|abstain|
   not_applicable|not_scored` — O-C4 is `not_applicable` under GT/1) plus
   Rubric B (`uncertainty-preserved|overstated|not-assessable-from-synthetic-
   packet|abstain|not_scored`), with severity (S0–S3), disagreement, and
   adjudicator outcome. (Loop cycle 3 fix: the full outcome vocabulary,
   including the O-C4 `not_applicable` case, was previously abbreviated.)
6. File the run record (commit, versions, commands, exit codes, hashes,
   answer sheets, score sheets, burden logs). Any unrecorded edit voids the run.
7. Pre-run freeze gate (loop cycle 1 addition, per `ADJUDICATION.md` §5): no
   scored output is opened until frozen in writing — evaluation/packet/app
   commits, case list, cutoff, arm definitions, opportunity list (O-A1..O-C4
   as applicable under GT/1; GT/2 items stay out), worksheet schema,
   denominators, thresholds (Q4 false-authority count zero; all other
   thresholds set to explicit values, never null-at-scoring), stopping
   authority, and the no-prior-viewing attestation. Unknown thresholds keep
   the run `not_activated`.

## 3. Quantities to record (both arms, per case + totals)

| # | Quantity | Definition |
|---|---|---|
| Q1 | Actionable signals | Count of review proposals that match a GT-expected affected item (amendment, specimen split, stale evidence) |
| Q2 | False alerts | Proposals/flags with no GT-expected target |
| Q3 | Missed criticals | GT-expected items with no proposal/flag |
| Q4 | False authority promotions | Citations of superseded/withdrawn/post-cutoff versions as current (must be zero) |
| Q5 | Review burden | Five `BASELINE.md` §4 buckets per case/arm (acquisition, preparation, correction, review, coordination) via timer, plus total and correction count (loop cycle 1 fix: buckets replace the earlier read/write/correct lump) |
| Q6 | Source opens | Count of source/version opens per case |
| Q7 | Runtime | Wall-clock minutes per arm per case (timer rules in §2) |
| Q8 | Cost | Reviewer-minutes × agreed rate + compute/API spend (Arm B compute ≈ 0; record actual) |
| Q9 | Reproducibility | Second reader replays from frozen inputs; match/mismatch per question |
| Q10 | Abstentions | Count + reason for each explicit abstention (never scored as failure) |

Measure mapping to the research note §6 (loop cycle 1 addition): correct
source lineage → per-claim Rubric A `correct` rate (Q1 counts proposals, not
lineage — lineage is scored claim-by-claim); actionable-vs-noisy → Q1/Q2;
missed criticals → Q3; false authority promotions → Q4 (zero); replay
reproducibility → Q9; correction burden → Q5 correction bucket + count;
end-to-end effort → Q5 total + Q7; compute/API cost → Q8;
invalidated-result propagation → Q1's stale-evidence/amendment items plus the
frozen staleness expectations (D-C1 stale; D-A1/D-B1 pending GT/2);
clinically consequential hallucinations → Q2 false alerts + Q4 + S3 severity
(an invented source or an efficacy/eligibility/urgency inference from fiction
is S3). Null/unknown retention is scored via Rubric B, never collapsed.

Report denominators and raw counts. No confidence intervals: n is three
questions per arm, far too small for meaningful intervals, so no claim of
statistical superiority is licensed by this frozen set. Compare only against
the existing OI-006/007/008/009 flow and the OI-011/014 validation gates —
never against an idealized chatbot.
