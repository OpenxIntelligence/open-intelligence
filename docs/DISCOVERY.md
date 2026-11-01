# Literature/trials discovery slice

Bounded, standalone slice on main. Maps to backlog OI-008 (metadata-only
discovery, labelled) and OI-017 (candidate screening stays distinct from
confirmed eligibility).

## What it is

- Fixture format `OI-SYNTHETIC-DISCOVERY/1`, parsed strictly by
  `src/open_intelligence/discovery.py`. Only independently authored fictional
  text with `Rights: original-synthetic` is accepted.
- Trials carry a `Registry-Id` and a fixed `Status: not-verified`. A registry
  listing never confirms recruitment availability.
- Literature carries a DOI as an identifier only. The DOI syntax check is the
  same conservative pattern as the Crossref metadata-only path, but this slice
  performs no lookup: bibliographic metadata for a DOI is served separately by
  the existing `/api/bibliography/lookup` (operator opt-in, metadata-only).
- No `Abstract` field exists in the format: any unknown field is rejected, so
  copyrighted article text cannot enter through this path.

## What it never does

- No eligibility, efficacy, or treatment-relevance inference. A fail-closed
  language guard rejects titles, summaries, and link rationales containing
  eligible/eligibility, effective/efficacy, recommended, proven, or benefit.
  The guard rejects; it never repairs text.
- No model involvement in any gate decision. Parsing, validation, and storage
  are deterministic.
- No live fetching, no real patient data, no unlicensed content.
- Applicability links (`applicable` / `limited` / `not_applicable` /
  `unknown`) are human-entered assessment labels, exactly like the existing
  evidence assessments — never determinations. `unknown` is first-class.
- Every listed item carries `fictional: true` and the disclaimer, and the
  projection never contains an abstract key.

## Routes

- `GET /api/discovery` — all fictional discovery items.
- `POST /api/discovery/imports` — import one fixture text.
- `GET /api/cases/<CASE>/discovery` — that case's discovery links.
- `POST /api/cases/<CASE>/discovery-links` — link an item to a case question
  with human-entered applicability and rationale (15–800 characters).
  Rejects unknown cases, questions outside the case, unknown items, and
  duplicate links.

## Link to the rights broker (after PR #42 merges)

This slice deliberately does not depend on PR #42's rights broker: it is
standalone on main. After #42 merges, the follow-up is to attach discovery
items to rights rows — the import path should accept an optional rights
reference, and the link endpoint should accept optional broker link ids —
so a revocation or correction can invalidate dependent discovery links the
way it invalidates evidence drafts. That follow-up is not in this PR; the
rights state of every item here is `original-synthetic` fictional content
only, which needs no external permission.

## Deliberately not done

- No UI panel (API + tests only); no browser rendering to prove.
- No change to `docs/EXECUTION_BACKLOG.csv` (an open PR touches it; the
  backlog row mapping is recorded here instead: OI-008, OI-017).
- No Crossref live lookup in this slice; the existing bibliography path is
  the only live metadata route, and it stays operator opt-in.
