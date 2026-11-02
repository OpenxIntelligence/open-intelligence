# What changed since last review — read-only projection

## Endpoint

`GET /api/cases/{CASE-ID}/changes-since-review[?since_event_id=N]`

No UI panel ships with this change. The endpoint is the integration surface;
the panel is deferred until the lead's merge queue settles, so no `web/`
file is touched here.

## Anchor rule

- Default anchor: the case's latest `demo_review_acknowledged` event.
- No acknowledgment yet: the anchor is the case-creation event, so the
  projection lists everything recorded for the case so far.
- Explicit anchor: `?since_event_id=N` anchors at that event, which must
  belong to the case; otherwise the endpoint returns 422.
- Only events with an id strictly greater than the anchor's id are listed.

## What is reported (ledger facts only)

- `new_sources`: first versions of documents imported after the anchor, with
  kind, event/issued/received dates, and finding keys with their reported
  states quoted verbatim from the fictional source text.
- `amendments`: new versions that supersede an earlier version, with the
  superseded version, a mechanical finding-key diff (added keys, removed
  keys, keys whose reported state differs, with old and new reported
  states), and the snapshot ids the amendment invalidated.
- `stale_investigations`: drafts marked stale after the anchor, each with
  its current state, its question and the question's current state, and the
  causing events (source amendment or evidence change). A question reopened
  by invalidation appears here with `question_state: "open"`.
- `new_questions`: questions created after the anchor, with current state.

## What is never claimed

This projection does not interpret clinical meaning, significance, or
relevance of any change. A finding-key diff is a ledger comparison, not a
statement that anything improved, worsened, or became more or less
significant. Every payload carries `synthetic: true` and the fictional-data
disclaimer. The projection writes nothing: calling it twice returns the
same result and leaves the ledger (including the events table) unchanged.

## Exact panel integration point (for the deferred UI work)

When a panel is built, it calls only this endpoint — no new backend route
is needed — and renders its four sections in order:

1. New sources → each source id links to the existing source-detail route
   `GET /api/cases/{CASE-ID}/sources/{SOURCE-ID}`.
2. Amendments → each amendment links to both the new and the superseded
   source detail routes, and renders `finding_key_diff` as added / removed /
   reported-state-changed keys, with no significance wording.
3. Stale investigations → each snapshot id links to the existing export
   route `GET /api/cases/{CASE-ID}/snapshots/{SNAPSHOT-ID}/export`; the
   panel shows `current_state` and `question_state` verbatim.
4. New questions → plain list with current state.

Suggested placement: the case workspace Updates section, below the source
list, so a reviewer sees what arrived since their last acknowledgment
before opening any single source. The panel must reuse the fictional-data
labeling already present in the workspace and must not add free-text
prompts, model calls, or writes.
