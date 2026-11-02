# Literature/trials discovery slice

Bounded slice on main. Maps to backlog OI-008 (metadata-only
discovery, labelled) and OI-017 (candidate screening stays distinct from
confirmed eligibility). The rights-linkage follow-up is implemented in
this doc's broker section; the format and guard below are unchanged.

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

- `GET /api/discovery` — all fictional discovery items, each with its
  rights linkage (`rights_source_id`, `rights_state` or `unlinked`).
- `POST /api/discovery/imports` — import one fixture text, with optional
  `rights_source_id` (see the broker section).
- `GET /api/cases/<CASE>/discovery` — that case's discovery links,
  including invalidated ones with their cause.
- `POST /api/cases/<CASE>/discovery-links` — link an item to a case question
  with human-entered applicability and rationale (15–800 characters),
  with optional `broker_link_ids` (see the broker section).
  Rejects unknown cases, questions outside the case, unknown items,
  items bound to a non-active rights row, and duplicate links.

## Link to the rights broker

Both halves of the recorded follow-up are implemented: discovery items
and links bind to rights rows, and revocation or correction invalidates
dependent discovery links the way it invalidates evidence drafts.

Linkage rule:

- `POST /api/discovery/imports` accepts an optional `rights_source_id`,
  stored on the item. The row must exist and be active. Keys and bindings
  are immutable: identical bytes re-import as a duplicate, changed bytes
  under an existing key are rejected, and a binding claim that differs
  from the stored one is rejected.
- `POST /api/cases/<CASE>/discovery-links` accepts optional
  `broker_link_ids`, validated like draft attachments: same case, same
  question, active rights row. New links also fail closed when the
  item's own bound row is no longer active.
- Unknown rights are first-class: an item with no rights row is reported
  as `unlinked` in `GET /api/discovery` and in link projections, never
  assumed permitted. Unlinked items stay listable and linkable.

Invalidation behavior:

- Revocation or correction of a rights row marks every dependent valid
  link `invalid`, with `invalidated_cause` (`revocation`/`correction`),
  the rights row id, and a timestamp. A link depends on the row when its
  item is bound to it or when it cites a broker link that is.
- Links are never deleted: rationale, applicability, broker bindings, and
  the item stay readable as history, the item stays in
  `GET /api/discovery`, and a per-case `discovery_invalidated` event is
  recorded. Unrelated links are untouched. Revoke/correct responses list
  `invalidated_discovery_links` alongside `invalidated_snapshots`.
- After a correction the item's binding still points at the superseded
  row as provenance, so new links fail closed rather than silently
  carrying the item forward under new terms; explicit re-attachment is
  out of scope for this slice.
- A permission record is explicitly NOT proof of permission: the broker
  language in `docs/RIGHTS_BROKER.md` governs. The gate enforces what
  the record says and fails closed; it never verifies legal truth. No
  external fetching, no model involvement in any gate.

## Deliberately not done

- No UI panel (API + tests only); no browser rendering to prove.
- No change to `docs/EXECUTION_BACKLOG.csv` (an open PR touches it; the
  backlog row mapping is recorded here instead: OI-008, OI-017).
- No Crossref live lookup in this slice; the existing bibliography path is
  the only live metadata route, and it stays operator opt-in.
- Broker-link re-review does not invalidate discovery links citing that
  broker link; only revocation and correction of a rights row do. Flag as
  a follow-up if re-review semantics need to propagate to discovery.
