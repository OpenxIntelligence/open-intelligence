# Rights-qualified evidence broker (issue #2)

## What exists already (not duplicated here)

- Synthetic evidence (PR #4, on main): independently authored fictional
  evidence versions, case/question-scoped human assessments, amendment and
  withdrawal invalidation.
- Crossref metadata-only adapter (`tools/crossref_metadata.py`, PR #6, on
  main): one validated public DOI, abstracts dropped, metadata separated
  from evidence. Bibliographic metadata alone is never evidence for a claim.
- Investigation templates (PR #9, not yet on main): fixed templates,
  validated claims, hypothesis/pending storage.

## What this slice adds

A deterministic, local-only rights gate for *external* sources — the
distinct milestone issue #2 was kept open for. It does not fetch external
content and does not verify that a rights record is legally true. It
enforces what the record says, failing closed.

- `src/open_intelligence/rights.py` — pure gate. Content items:
  metadata, abstract, full_text, figures, terminology, api_output. Uses:
  store, display, redistribute, ml_use. A permission counts only when
  explicitly "allowed" for that item and use on an active record;
  "unknown" and "denied" both mean no. Content modes: `full` (excerpt
  may be stored), `metadata_only` (title/identifier fields only),
  `citation_only` (source identity alone, no content).
- Store tables `rights_sources` (versioned, one row per version; old
  rows are kept as `superseded` or `revoked`, never overwritten),
  `rights_permissions` (every item/use cell recorded explicitly),
  `broker_links` (one case question + one rights row + a human-entered
  review: relation/applicability, unknown first-class),
  `snapshot_broker_links` (the immutable draft-to-link binding),
  `rights_events` (audit trail).
- Revocation and correction invalidate dependent drafts the same way
  withdrawal does for synthetic evidence: drafts go stale, their
  questions reopen, history is retained. New drafts must use the new
  rights row, under its own permissions.
- API routes: `POST /api/rights/sources`, `POST
  /api/rights/sources/<id>/revoke`, `POST
  /api/rights/sources/<id>/correct`, `POST
  /api/cases/<id>/broker-links`, `POST
  /api/cases/<id>/broker-links/<link>/review`, `GET
  /api/rights/sources`. Draft creation accepts optional `broker_link_ids`
  and rejects revoked, wrong-case, or wrong-question links, and
  supports + not_applicable combinations. Case state exposes
  `broker_links` and `rights_sources`.
- Four rules enforced after an adversarial review pass: a citation title
  needs its own metadata store permission even in full mode; link
  re-review is scoped to the link's own case and stales drafts already
  citing it (a re-review must not silently change a live draft's
  meaning); revoked or superseded content is redacted from case state
  while the link, mode, and rights row stay visible as provenance.

## Explicitly not done

- No external fetching, no live rights service, no clinical or legal
  clearance. A record that claims permission is not proof of permission.
- No UI panel for the broker (API + tests only); no model involvement
  in any broker decision — the gate is deterministic code, and link
  reviews are human-entered.
- No change to `docs/EXECUTION_BACKLOG.csv` in this PR (an open PR
  touches it; backlog status follows after merge order settles).
- No inference from citation metadata to efficacy, eligibility, or
  clinical relevance. Negative, contradictory, and unknown states are
  first-class throughout.
