# Deterministic temporal reasoning

`src/open_intelligence/timeline.py` is a small, pure, read-only projection
over the existing case/source ledger (`CaseStore`). It follows the
`changes_since_review` pattern: it reads inside one SQLite read
transaction and never writes. It calls no model, fetches nothing
external, and works only on independently authored fictional data.

## Time taxonomy

Six facets are kept distinct on every payload; they are never collapsed
into a single date:

| Facet | Ledger source | Meaning |
|---|---|---|
| occurred | `source_versions.event_date` | When the reported event concerns the patient. Primary timeline order. |
| documented | `source_versions.issued_at` | When the source was finalized. First tiebreak, shown as context. |
| received | `source_versions.received_at` | When the ledger received the bytes. Second tiebreak; an ingest fact, not a clinical time. |
| known | coverage state | A covered date is `known`; a gap or unresolved conflict is `unknown`. Unknown is reported, never filled. |
| amended | `supersedes_id` / `state` | Supersession linkage. Superseded versions appear only in `history`. |
| as-of | latest `events` row | Ledger position the projection reflects (`event_id`, `occurred_at`). Read time, not event time. |

Entries order by `(occurred, documented, received, document_id, version,
source_id)`, so output is fully deterministic for an unchanged ledger.
`as_of` is derived from the ledger, not the wall clock, so two calls over
the same state return identical payloads.

Workflow-ledger rows (`question_created`, `draft_created`, …) are not
timeline entries: their `occurred_at` values are system timestamps, not
patient event times. They contribute only the `as_of` ledger position.

## Rules

- **Ordering** reports occurred time; documented/received supply tiebreak
  context only.
- **Gaps**: consecutive covered occurred dates with at least one
  uncovered calendar day strictly between them produce one gap
  (`coverage: unknown`) bounded by the neighboring covered dates.
  Leading/trailing unbounded periods are not reported: without a
  declared observation window there is nothing deterministic to bound
  them. A gap invents no entries.
- **Conflicts**: the same recorded specimen with different occurred
  dates across current sources, or the same document with different
  occurred dates across versions, is flagged `status: unknown` with
  every asserted date and asserting source listed. The projection never
  picks a winner and never drops an assertion. (The import contract
  already blocks in-document date changes; the document rule is
  defensive.)
- **Amendment supersession**: `entries` holds only `state='current'`
  sources; every superseded version appears only in `history` with its
  time facets preserved and a `superseded_by_source_id` pointer.
- Every payload carries `synthetic: true` and the fictional-data
  disclaimer.

## Deliberate refusals

The module reports ordering, coverage, and conflict — never clinical
meaning. It refuses to infer response, progression, staging, grading,
eligibility, efficacy, treatment relevance, significance, or benefit, and
none of that vocabulary appears in any payload outside the disclaimer's
explicit negation. Gaps and conflicts stay `unknown`; no interpolation,
no guessing, no model involvement at runtime.

## Contract mapping

- Source identity, versions, receipts, and event/report dates: the
  OI-006 source/assertion contract (`store.py`).
- Amendment supersession and history preservation: the OI-009
  second-time-point contract (`import_report`, `superseded` state).
- Read-only projection discipline: `changes.py` (`changes_since_review`).
- HTTP: `GET /api/cases/<CASE-ID>/timeline` (`__main__.py`), returning
  422 `{"error": …}` for an unknown case, like the neighboring routes.

## Verification

`tests/test_timeline.py` covers ordering and tiebreaks, facet
separation, gap detection (including the adjacent-date no-gap case),
specimen and document conflicts resolving to `unknown`, amendment
history-only behavior, absence of clinical-inference vocabulary,
purity (two calls identical, ledger unchanged), the empty-case
projection, and fictional labeling. `tests/test_timeline_http.py`
covers the route and its unknown-case 422.
