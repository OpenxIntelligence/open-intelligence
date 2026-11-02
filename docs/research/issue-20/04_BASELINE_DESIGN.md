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

## 2. Verbatim procedure

1. Create a clean directory; pin and record the application commit under test,
   Python version, and `git status --porcelain` (must be empty; else stop).
2. Import Gate-2 scenario sources in receipt order: A (v1, v1-dup, v2), B
   (`MOL-20B@1`, rejected specimen-changing amendment, `MOL-20B2@1`,
   wrong-subject delivery), C (`LAB-20C@1`, `EV-20C@1`, assessment on @1,
   draft citing it, `EV-20C@2`). Record every import result
   (`imported|duplicate|quarantined|rejected`) with ids.
3. Arm A: reviewer answers Q-A1/Q-B1/Q-C1 from sources only. Start a wall-clock
   timer at first source open; stop when the answer sheet is frozen. Log every
   source open, every re-read, and every correction.
4. Arm B: run the manifest script; record its stdout hash, wall time, and flags
   raised. Reviewer answers the same questions from manifest + sources with the
   same timer and logging rules.
5. An independent assessor (per `validation/iv01/ADJUDICATION.md` §2, recused
   if they built anything under test or saw GT early) scores both arms against
   `ISSUE20-GT/1` with the Gate-7 rubric (no peeking at GT during answering;
   GT opened only at scoring). Record per-question
   correct/incorrect/unsupported/omitted and uncertainty-preserved/overstated.
6. File the run record (commit, versions, commands, exit codes, hashes,
   answer sheets, score sheets, burden logs). Any unrecorded edit voids the run.

## 3. Quantities to record (both arms, per case + totals)

| # | Quantity | Definition |
|---|---|---|
| Q1 | Actionable signals | Count of review proposals that match a GT-expected affected item (amendment, specimen split, stale evidence) |
| Q2 | False alerts | Proposals/flags with no GT-expected target |
| Q3 | Missed criticals | GT-expected items with no proposal/flag |
| Q4 | False authority promotions | Citations of superseded/withdrawn/post-cutoff versions as current (must be zero) |
| Q5 | Review burden | End-to-end reviewer minutes (read + write + correct), plus correction count |
| Q6 | Source opens | Count of source/version opens per case |
| Q7 | Runtime | Wall-clock minutes per arm per case (timer rules in §2) |
| Q8 | Cost | Reviewer-minutes × agreed rate + compute/API spend (Arm B compute ≈ 0; record actual) |
| Q9 | Reproducibility | Second reader replays from frozen inputs; match/mismatch per question |
| Q10 | Abstentions | Count + reason for each explicit abstention (never scored as failure) |

Report denominators and raw counts; no claim of statistical superiority is
licensed by this small frozen set. Compare only against the existing
OI-006/007/008/009 flow and the OI-011/014 validation gates — never against
an idealized chatbot.
