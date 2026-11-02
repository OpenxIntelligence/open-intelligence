# Issue #15 — DerivedTimelineCandidate contract (specification)

**Status:** PROPOSED SPEC / EVALUATE; not implemented, not adopted, not clinical validation.
**Date:** 2026-11-02
**Tracker:** [Issue #15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)
**Parent:** [HL7 crosswalk](ISSUE15_HL7_CROSSWALK.md) (gap G-5)
**Boundary:** a projection layer over existing assertion/event entities; never a second canonical timeline, never a source ledger, never clinical truth. All data fictional, labeled everywhere. No clinical-inference vocabulary appears in any candidate.

## 1. Purpose

Give model- or tool-derived chronology proposals a typed home that is visibly *not* the canonical timeline. The deterministic projection in [`timeline.py`](../../src/open_intelligence/timeline.py) reports only current ledger facts and must stay that way; candidates live beside it as reviewable proposals until a scoped human review accepts, corrects, or rejects each one. This closes crosswalk gap G-5.

## 2. What already exists (extended, not replaced)

- Canonical timeline: `case_timeline` — read-only, deterministic, gaps/conflicts stay `unknown` ([TEMPORAL_REASONING.md](../TEMPORAL_REASONING.md)).
- Source anchors: `assertions` rows (`source_version_id`, `finding_key`, `certainty`, `quote`, `source_line`).
- Review pattern: draft → scoped human decision → reviewed state (`create_snapshot` / `acknowledge_demo_review` / `review_option`).

A DerivedTimelineCandidate references these rows. It copies no source bytes beyond the already-stored verbatim quote pointer (source id + line), and it can never appear in `case_timeline` output.

## 3. Contract

### 3.1 Epistemic levels (closed set, never collapsed)

Every candidate carries exactly one level. No level other than `clinician_reviewed` may be displayed as a finding, and *no model output, confidence score, or validation success may set `clinician_reviewed`* — only a scoped human review action using the existing review machinery may do so.

| Level | Meaning |
|---|---|
| `reported_text` | Verbatim span from a source version (reference + line anchor). The model adds nothing. |
| `extracted_candidate` | A mechanical normalization of reported text (e.g., date placed on the occurred axis, finding key attached). Deterministic rules only. |
| `derived_interpretation` | A model-proposed reading that goes beyond mechanical normalization (e.g., resolving which of two conflicting dates orders first *as a proposal*). Always carries its alternatives (see §3.4). |
| `hypothesis` | A model-proposed gap-fill or connection with explicit uncertainty. Never displayed without its abstention alternatives. |
| `clinician_reviewed` | A human reviewer, through the scoped review path, has accepted a lower-level candidate. Set by human action only. |

### 3.2 Required fields

| Field | Type | Meaning |
|---|---|---|
| `candidate_id` | string | `candidate:<run_id>:<index>` — bound to exactly one [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md). |
| `run_id` | string | The producing run's receipt id. |
| `epistemic_level` | enum | One of the §3.1 levels. |
| `source_ref` | object | Exact `source_version_id`, `document_id`, `version`, and `source_line` anchor. Must resolve to a current version at creation; a superseded anchor fails creation. |
| `episode_context` | object | `episode_id`, `lesion_id` (or `unknown`), `specimen_id` (or `unknown`), `assay_ref` (or `unknown`). Unknown is recorded, never guessed. |
| `polarity` | enum | Verbatim from the source assertion's `certainty` (`reported`, `negative`, `pending`, `indeterminate`, `not-reported`, `not-assessed`, `conflicting`). Never reinterpreted. |
| `certainty` | enum | `low`, `moderate`, or `high` — the model's stated uncertainty about its own proposal, not a clinical confidence. |
| `occurred` | string or null | Proposed occurred date (`YYYY-MM-DD`) or null with an abstention reason. Partial dates are not representable (crosswalk G-4); a partial-date input abstains. |
| `documented` | string | Copied from the source version's `issued_at`. Never model-supplied. |
| `received` | string | Copied from the source version's `received_at`. Never model-supplied. |
| `units_reference` | string or `unknown` | Units/reference as stated in the source, or `unknown`. |
| `validity` | enum | `current` or `stale` (see §3.5). |
| `review_state` | enum | `pending` at creation; transitions only via scoped human review. |
| `synthetic` | boolean | Always `true`. |
| `disclaimer` | string | Fictional-data disclaimer naming the candidate as an unreviewed proposal. |

### 3.3 Forbidden content

Candidates must not contain clinical-inference vocabulary: no response, progression, staging, grading, eligibility, efficacy, treatment relevance, significance, benefit, recommendation, prescription, dosing, or diagnosis language. The mock adapter enforces this with a closed pattern list mirroring the [`timeline.py`](../../src/open_intelligence/timeline.py) refusals and the [investigation.py](../../src/open_intelligence/investigation.py) language guard. A candidate that cannot be expressed without such vocabulary is not produced; an abstention is recorded instead.

### 3.4 Competing interpretations

A `derived_interpretation` or `hypothesis` candidate must list every competing reading the run considered (`alternatives`), each with its own source anchor and certainty. Dropping a competitor to present a single clean answer is a contract violation. Source conflicts are preserved, never resolved by the run.

### 3.5 Staleness and invalidation

- Each candidate depends on exactly one source version (its `source_ref`) plus the run's `input_fingerprint`.
- Amendment superseding that version stales the candidate (`validity: stale`) through the same anchor-exact mechanism that stales snapshots; staleness never deletes the candidate row.
- Regeneration after amendment produces *new* candidates under a *new* receipt; the stale ones remain inspectable history. See the [amendment flow](ISSUE15_AMENDMENT_FLOW.md).

### 3.6 Display rules

- Candidates render in a visually separate "proposed" region, never interleaved with canonical timeline entries.
- Every rendered candidate shows its epistemic level, source anchor, certainty, review state, and fictional label.
- Exports during a stale interval show version, date, and stale/review-pending status, per the plan's update rules.

## 4. Worked shape (illustrative, fictional)

```json
{
  "candidate_id": "candidate:<run_id>:0",
  "run_id": "sha256:<hex>",
  "epistemic_level": "extracted_candidate",
  "source_ref": {"source_version_id": 3, "document_id": "PATH-FIXA",
                 "version": 1, "source_line": 8},
  "episode_context": {"episode_id": "EPISODE-FIXA-1", "lesion_id": "unknown",
                      "specimen_id": "SPECIMEN-FIXA-1", "assay_ref": "unknown"},
  "polarity": "reported",
  "certainty": "low",
  "occurred": "2026-05-03",
  "documented": "2026-05-04",
  "received": "<ledger received_at, copied>",
  "units_reference": "unknown",
  "alternatives": [],
  "validity": "current",
  "review_state": "pending",
  "synthetic": true,
  "disclaimer": "Fictional synthetic demonstration data only. Unreviewed proposal, not a finding."
}
```

## 5. Relation to the mock adapter

The branch-only [mock adapter](../../tools/mock_specialist_adapter.py) emits `extracted_candidate`-level candidates only (mechanical normalization of caller-supplied statements onto the occurred/documented/received facets). It never emits `derived_interpretation` or `hypothesis`, demonstrating that higher levels require a separately qualified run.

## 6. Open checks

- [ ] Reviewer confirms the level taxonomy cannot be confused with canonical timeline entries in any current or planned view.
- [ ] Decide, in a separately scoped proposal, whether candidates persist as rows or as receipt-attached projections. This spec requires no decision here.
- [ ] Human-review transition mechanics reuse the existing snapshot/option review path; no new authority is defined here.
