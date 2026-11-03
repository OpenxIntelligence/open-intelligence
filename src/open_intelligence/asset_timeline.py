"""Biological asset timeline projection, issue 116 (WS-04).

This is a pure, tested projection contract for the timeline/genomic
specimen slice of issue 116: it lists a case's biological assets
with their specimen, episode, parent, and anchor freshness, so a
reviewer can see which assets are still current and which went stale
when their anchor source was amended.

It is NOT a new asset store: assets are already registered by
CaseStore.add_biological_asset on main, with kind, specimen, episode,
derivative parent, and pointer-label rules. This module only reads
that store and projects it. It does NOT change any asset, source, or
timeline entry, and it does NOT claim assay or genome build results:
a genomics_data_pointer carries only a descriptive label, never
genome bytes, exactly as the store already enforces.

Rules, fail closed:
- Unknown case is denied (InvalidInput from the store, propagated).
- An asset whose anchor source version is current is current.
- An asset whose anchor source version is superseded is stale.
  Stale does not mean deleted: the asset row, its parent, and its
  history remain visible, and the projection says so explicitly.
- A derivative asset whose parent asset is missing from the case
  is flagged orphan. The store normally prevents this at write time,
  so an orphan in a projection is a data-integrity flag, not a
  normal state, and it is never silently dropped.
- Output carries only asset identity, kind, episode, specimen,
  parent, anchor, and freshness. No bytes, no images, no genome
  data, no treatment, diagnosis, or prognosis content.
"""

from __future__ import annotations


def asset_projection(store, case_id):
    """Return the asset projection for one case.

    Returns a dict with case_id, synthetic True, disclaimer, assets
    (list, ordered by id), and counts (total, current, stale, orphan).
    """
    state = store.state(case_id)
    assets = state.get("biological_assets", [])
    by_id = {a["id"]: a for a in assets}
    # Anchor freshness comes from the source versions in the same state.
    source_state = {}
    for source in state.get("sources", []):
        source_state[source["id"]] = source.get("state")
    entries = []
    for asset in sorted(assets, key=lambda a: a["id"]):
        anchor_id = asset.get("anchor_source_version_id")
        anchor_state = source_state.get(anchor_id, "unknown")
        stale = anchor_state == "superseded"
        parent_id = asset.get("parent_asset_id")
        orphan = parent_id is not None and parent_id not in by_id
        entries.append(
            {
                "asset_id": asset["asset_id"],
                "kind": asset["kind"],
                "episode_id": asset["episode_id"],
                "specimen_id": asset.get("specimen_id"),
                "specimen_state": asset.get("specimen_state"),
                "parent_asset_id": parent_id,
                "parent_kind": by_id[parent_id]["kind"] if parent_id in by_id else None,
                "anchor_source_version_id": anchor_id,
                "anchor_state": anchor_state,
                "freshness": "stale" if stale else "current",
                "orphan": orphan,
            }
        )
    return {
        "case_id": case_id,
        "synthetic": True,
        "disclaimer": "Fictional synthetic case data only. Not clinically reviewed.",
        "assets": entries,
        "counts": {
            "total": len(entries),
            "current": sum(1 for e in entries if e["freshness"] == "current"),
            "stale": sum(1 for e in entries if e["freshness"] == "stale"),
            "orphan": sum(1 for e in entries if e["orphan"]),
        },
    }
