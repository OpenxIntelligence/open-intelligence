# Issue #16 — buyer/role/workflow hypotheses and wedge comparison

**Tracker:** [#16](https://github.com/OpenxIntelligence/open-intelligence/issues/16)
**Date:** 2026-11-02
**Status:** Complementary strategic research. **Not** a product decision, wedge
selection, demand claim, or authorization for engineering, outreach, or
procurement.
**Headline:** no wedge selected — every demand, win, and readiness rating is
UNKNOWN (or LOW where the plan itself records unreadiness), and every wedge
evidence rating is NONE. Content coverage of issue wedges A–E still awaits
readable sources (matrix row F-06, DEFERRED).
**Decision rule:** missing proof means UNKNOWN, not a positive rating. No
forced wedge choice on an arithmetic score — no scores are computed here.

## 0. Rating vocabulary (shared with the coverage matrix)

| Symbol | Meaning | Allowed values here |
| --- | --- | --- |
| A | Attractiveness of the wedge/market | UNKNOWN only (no demand measured) |
| W | Right-to-win with this architecture/team | UNKNOWN only (no comparative win measured) |
| E | Readiness to execute now | UNKNOWN, or LOW where in-repo evidence shows a missing prerequisite |
| K | Evidence quality behind this row | NONE / STATED (hypothesis text exists in-repo) — never above STATED in this pass |

A, W, E, and K are kept distinct in every row: a well-stated hypothesis
(K = STATED) says nothing about its attractiveness (A = UNKNOWN).

## 1. What counts as evidence here (and what does not)

**Measured evidence admitted:** observed workflow timings, recorded procurement
outcomes with named budget owners, delivered reviewer/data commitments,
comprehension measurements, costed case preparation. **None of these exists
yet** — backlog OI-002, OI-014, OI-015 are unexecuted.

**Explicitly not demand evidence:**

- Synthetic capability tests (`docs/IMPLEMENTATION_STATUS.md`: unit/HTTP
  tests, headless Chromium journeys) prove bounded demo behavior only. A
  passing synthetic journey is not a user, a buyer, or a willingness to pay.
- The plan's stated hypotheses (`docs/FIRST_PRINCIPLES_PLAN.md` §§3, 13) are
  hypotheses, not findings. The plan itself marks demand assumptions
  unestablished (§3: "None of these demand assumptions has yet been
  established").
- Prior research addenda in `docs/research/` establish no demand, willingness
  to pay, or procurement outcome.
- Unaccessed Notion pages (audit pointers P-02, P-03, P-07) are not evidence:
  an unread pointer contributes no rating in any direction.

## 2. Buyer / role / workflow hypotheses (in-repo statements, all unmeasured)

| # | Hypothesis (source) | Status | A | W | E | K |
| --- | --- | --- | --- | --- | --- | --- |
| H-1 | Daily operator: oncology nurse, navigator, coordinator, or clinician preparing the case (plan §3) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-2 | Accountable interpreter: qualified treating/reviewing clinician (plan §3) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-3 | Patient/caregiver role: access/coordination, attributed history, goals, questions, corrections (plan §3) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-4 | Buyer: the organization operating the review workflow (plan §3, §13) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-5 | Alternative buyer: patient subscription with different economics (plan §13; different hypothesis from H-4) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-6 | Launch setting: adult oncology consultation / referral / second-opinion / case-review service (plan §3, provisional) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-7 | Reviewable brief + evidence-linked question + amendment re-review reduces total burden within error limits (plan §§3, 11) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | STATED |
| H-8 | Patient record coordination viable at sustainable acquisition burden (plan §3 row 1; named difficulty: burden dominates) | UNKNOWN | UNKNOWN | UNKNOWN | LOW (plan names acquisition burden and adoption as the dominating difficulty) | STATED |
| H-9 | Specialist molecular / tumor-board design partnership viable (plan §3 row 3; named difficulties: specialist time, assay context, data access, validation) | UNKNOWN | UNKNOWN | UNKNOWN | LOW (four named difficulties unmeasured and unaddressed) | STATED |

H-8 and H-9 carry E = LOW rather than UNKNOWN because the plan itself records
concrete unreadiness reasons; that is a negative readiness signal from a
stated source, not a measurement. H-7 carries no plan-recorded unreadiness
reason (the plan recommends that workflow), so it stays E = UNKNOWN.
Everything else stays UNKNOWN.

Source lines: launch setting `docs/FIRST_PRINCIPLES_PLAN.md:56`; role/buyer
hypotheses `:58`; patient entry-point row `:50`; clinician entry-point row
`:51`; specialist entry-point row `:52`; business hypotheses `:260`;
evaluation dimensions and stop list `:213-228`.

## 3. Wedge comparison at equal depth

Issue wedges A–E are not readable in-repo (matrix row F-06, DEFERRED), so no
A–E comparison can be honestly computed here. The table below compares the
three in-repo candidate entry points (plan §3) against their best
existing/manual alternatives **at equal depth** — each row gets the same
treatment: named alternative, costed honestly, evidence status stated.

| Wedge or layer (in-repo) | Best existing/manual alternative | What would have to be true | Evidence status | A | W | E | K |
| --- | --- | --- | --- | --- | --- | --- | --- |
| W-α Clinician-supported consultation investigation (plan §3 row 2; FP-1) | Partner's current manual preparation; simple source-search/timeline workflow | Total burden falls within error limits; reviewer owns follow-up | No timings measured; OI-002/OI-014 unexecuted | UNKNOWN | UNKNOWN | UNKNOWN | NONE |
| W-β Patient-owned record coordination (plan §3 row 1; FP-3) | Unaided gathering; navigator-assisted gathering without workspace | Acquisition burden sustainable; questions usable; comprehension holds | No burden/comprehension measured; acquisition difficulty named but unquantified | UNKNOWN | UNKNOWN | LOW (see H-8) | NONE |
| W-γ Specialist molecular / tumor-board research (plan §3 row 3; FP-4) | Manual specialist prep; institutional resources the partner names at preregistration (none nameable here without a partner) | Reviewer time + data/assay access sustained; validation bar reachable | No commitments delivered; all four difficulties unmeasured | UNKNOWN | UNKNOWN | LOW (see H-9) | NONE |
| Buyer layer over all wedges: organization pays for workflow change (plan §13; FP-2) | Status quo staffing; cheapest buyer-named adequate substitute | Named budget owner; repeat paid use; sustainable unit cost | No procurement conversations recorded; OI-015 unexecuted | UNKNOWN | UNKNOWN | UNKNOWN | NONE |

**No wedge is selected.** Selecting on this evidence would require treating
UNKNOWN as positive or inventing an arithmetic score — both prohibited. The
E = LOW rows are *less ready*, not *rejected*: readiness is one dimension,
and rejection requires a falsification outcome from the protocols in
[ISSUE_16_FALSIFICATION_PROTOCOLS.md](ISSUE_16_FALSIFICATION_PROTOCOLS.md),
not a column comparison.

Why wedge rows carry K = NONE while hypothesis rows carry K = STATED: K on
a wedge row rates demand/burden/willingness evidence (timings, procurement,
commitments — none measured, so NONE), whereas K = STATED on an H-row rates
only that the hypothesis text exists in-repo. A well-stated hypothesis with
zero measurements is exactly STATED-text plus NONE-evidence.

## 4. Mapping owed to issue wedges A–E (DEFERRED)

| Issue wedge | In-repo analogue (withheld — do not guess) | Mapping status |
| --- | --- | --- |
| A | Unknown | DEFERRED — definition not readable (matrix F-06) |
| B | Unknown | DEFERRED — definition not readable (matrix F-06) |
| C | Unknown | DEFERRED — definition not readable (matrix F-06) |
| D | Unknown | DEFERRED — definition not readable (matrix F-06) |
| E | Unknown | DEFERRED — definition not readable (matrix F-06) |

The analogue column is intentionally empty: mapping in-repo wedges onto
unread issue wedges by name similarity would fabricate alignment. When wedge
definitions become readable in-repo, replace this table with verbatim
definitions and re-run §§2–3 per wedge.

## 5. What would change these ratings

- OI-002 executed: observed workflow map + effort record → H-1/H-2/H-3/H-6/H-7
  move from K = STATED toward measured K, and W-α evidence status updates.
- FP-1 executed under OI-014 governance / FP-2–FP-4 under OI-015-equivalent
  governance, each with preregistered thresholds and OI-012/OI-013 clearance
  where applicable → specific hypotheses move to ANSWERED (survived) or
  falsified; failures recorded, not rescored.
- Wedge A–E definitions + 68 questions + VI sections readable in-repo →
  DEFERRED rows in [ISSUE_16_COVERAGE_MATRIX.csv](ISSUE_16_COVERAGE_MATRIX.csv)
  become mappable; this document's §§2–4 get a per-wedge revision.
- Until then: no engineering priority, no outreach, and no buyer conversation
  may cite this document as support. It records the absence of evidence.
