# OI-020 — Biological-asset provenance within the existing case model

**Scope:** GitHub issue #12. Optional extension only. It does not replace the
existing architecture, does not select a new first product, and does not
reorder the OI-001–018 roadmap. No second ledger, no parallel canonical state:
assets and inventory assertions live in the same SQLite case store, keyed by
the same `case_id`, anchored to the same `source_versions` rows, and
invalidated by the same amendment path that marks snapshots stale.

**Comparison with the existing implementations.** The source model versions
immutable bytes per document and marks dependent snapshots stale when a
version is superseded; the evidence model versions immutable items, logs
amendment/withdrawal in `evidence_changes`, and marks only snapshots citing
the exact version stale. Biological assets follow both: asset rows are
immutable (no update path exists, so kind/parent/episode can never be grafted
across cases or episodes after creation), and inventory assertions are
separate rows that go stale anchor-exactly on source amendment.

## Model

- `biological_assets`: one row per asset, unique per `(case_id, asset_id)`.
  Kinds: `ffpe_block`, `fresh_frozen_aliquot` (originals, no parent),
  `slide`, `digital_wsi`, `genomics_data_pointer` (derivatives).
  Each asset records `episode_id` (the patient/cancer episode), an optional
  specimen reference, a required `observed_date`, and
  `anchor_source_version_id` — creation provenance only, never a liveness
  claim. The anchor must be a *current* source version in the same case at
  creation; after amendment the anchor row stays as history.
- Derivative rules, enforced in code at creation: a derivative requires a
  parent in the same case with the same `episode_id` and an allowed kind —
  `slide` from `ffpe_block`, `digital_wsi` from `slide`,
  `genomics_data_pointer` from `ffpe_block` or `fresh_frozen_aliquot`.
  A derivative whose parent is unknown cannot be registered as a derivative;
  it is rejected rather than recorded with a guessed lineage.
- `biological_inventory_assertions`: separately attributed rows
  (`asserted_by` label) per asset, each anchored to one exact current source
  version in the same case. Location, remaining quantity, custody, consent,
  and rights each carry an explicit `known`/`unknown` state; `unknown`
  forces a NULL value, `known` requires a 1–200 character value. UNKNOWN is
  stored state, never treated as absent. An asset with no assertion row is
  reported as "no inventory assertion recorded", which is visibly distinct
  from an all-unknown assertion.
- No rollup is ever computed: readers always see each assertion with its own
  anchor, attributor, and state, so multiple assertions for one asset never
  silently mix into one composite inventory view.
- No bytes are stored for WSI or genomics data: only a short pointer label,
  which may not be a URL or filesystem path. No tissue release, shipment,
  outside service, or real biopsy file/clinical record exists in this code.
  Rights/consent values are descriptive only; nothing gates, releases, or
  ships on them, so no query can fail open through them.

## Staleness — deliberate scope boundary

When a source is amended, only inventory assertions anchored to the exact
superseded version become `stale`; assertions on other versions, the assets
themselves, and all historic source versions are preserved, and a fresh
assertion must be made explicitly against the current version. Staleness
does **not** propagate transitively to derivative assets: a child's own
assertion anchor and parent chain stay visible, so a reader can see that a
parent's assertions went stale. This follows the issue's "only its dependent
inventory assertions" wording; transitive confidence is a reader judgment
from the visible chain, not a silent cascade. Assertion staleness is also
per-assertion, matching snapshot granularity: amending one field's source
stales the whole assertion row, and re-assertion carries the fields forward
explicitly rather than by cross-version merging.

## HTTP and UI

- `POST /api/cases/<id>/biological-assets` and
  `POST /api/cases/<id>/biological-assets/<pk>/inventory-assertions`;
  both are case-scoped and reject cross-case asset, parent, or source
  references. Assets and assertions are included in `GET /api/cases/<id>/state`
  and rendered read-only in the demo UI, one card per asset — tumors and
  time points are never merged in display.
- Wrong-case access is rejected at the store layer (`InvalidInput`), the
  same pattern as `source_text` and snapshot creation.

## What is NOT proved

Browser rendering is not verified here (no Chromium on this machine); the
repo PR workflow runs headless Chromium. No clinical claim, treatment,
diagnosis, or progression inference is made or enabled by this extension.
