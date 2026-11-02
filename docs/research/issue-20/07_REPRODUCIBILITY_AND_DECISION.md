# Issue #20 — Gate 7: reproducibility bundle outline + go/no-go decision

**Status:** research draft only, branch work. No runs happened, so there are no
positive findings to report. No clinical benefit is claimed, implied, or
inferable from this bundle.

## 1. Reproducibility bundle outline (to be frozen at run time)

1. `bundle_manifest.json`: pinned app commit, packet commit (`ISSUE20-GT/1`),
   Python version, every command + exit code, `git status` before/after (empty).
2. Frozen inputs: Gate-2 scenario bytes + SHA-256 per source/evidence version.
3. Cutoff declaration: `2026-10-15`, receipt order, out-of-cutoff exclusions.
4. Draft proposals + receipts: `ExperimentProposalDraft` / `EvaluationRunReceiptDraft`
   rows (or `denied`/`null` equivalents) with ids, versions, cutoff,
   hypothesis/falsifier, permissions, method ref, reviewer ≠ owner.
5. Answer sheets per arm (A/B) + score sheets vs GT/1 + burden logs (§3 Q1–Q10).
6. Failure-mode receipts F1–F9 (outputs or denials, each with cause).
7. Independence declarations (assessor/adjudicator, prior exposure, conflicts).
8. Decision record (§2) with negative results and unresolved limits.

Replay rule: a second reader reproduces every row from items 1–4 alone; any
mismatch voids the affected row, not the bundle's history.

## 2. Go / no-go decision section (actual findings at end of Pass 2)

**Decision: NO-GO for any core change, model use, or clinical claim.**
What exists is paper + isolated draft code, not evidence.

- Met: Gates 1–7 drafted in order; contracts mapped before any type design;
  scenarios prespecified with frozen GT + cutoff; draft types + ledger mapping
  isolated with no migrations; baseline designed with recordable quantities;
  rule-assisted prototype pure and ledger-free with model use explicitly
  deferred; nine failure modes drafted with denial receipts; this bundle
  outline + decision written without clinical-benefit language.
- Negative results: no baseline run, no measured burden/error, no replay, no
  independent review, no provider/rights qualification — so no comparison can
  favor the extension yet. The "go" criteria from the research note
  (zero bypasses, full replay, retained unknowns, improvement vs baseline) are
  all unmeasured.
- Unresolved limits: open-PR statuses unverified (no git/network); branch head
  uninspected; isolated draft module never executed (shell unavailable), so
  even its `DraftError` paths are unproven; no adjudicator recruited; no
  costed reviewer time; class-B consent semantics and class-C handoff format
  remain paper-only.

## 3. Comparison (not against an idealized chatbot)

- Against the existing OI-006/007/008/009 flow: the draft adds nothing the
  ledger does not already own (versioning, quarantine, staleness, review).
  Its only possible value is *proposing* version/identity/freshness checks
  earlier for human review — unproven until Gate 4 runs.
- Against OI-011/014 gates: the baseline design follows the merged
  `validation/iv01/BASELINE.md` arms and `ADJUDICATION.md` independence rules,
  but no gate is passed: no task contract approved, no governed packet run,
  no burden-vs-error measurement. Advancement requires those gates, plus the
  separate scoped decision the issue boundary mandates before ANY core touch.
