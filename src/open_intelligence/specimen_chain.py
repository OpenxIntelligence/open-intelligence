"""T3 specimen chain (program plan slice D1; Notion OI-09 section 5).

Deterministic code, not an agent: a specimen's chain of custody is the
parent-linked lineage of biological assets from the queried asset back
to its original (a block or aliquot with no parent). "Specimen identity
first" (OI-09): comparisons across specimens require an unbroken chain,
so this module walks the chain and reports every break as a typed
record -- never silent, and never a raised exception for a broken chain.
A broken chain is a finding about the ledger, not a crash.

Each link carries its assay/specimen context (kind, episode, specimen
id and state, observed date, and the anchor source version with its
document, version, and state), so a reader can see the basis of every
link -- the "SpecimenChain links with basis" of OI-09 section 5.3.

First live caller: the chain validator is the toolset D3's comparison
toolsets consult before comparing across specimens; the bio-assay
observation path already enforces specimen matching for a single block
at write time (``store.record_bio_assay_observation``). No route or
write gate is added here: chain breaks are typed records, not
rejections, per the D1 acceptance. Creation-time invariants
(same-episode parents, allowed parent kinds, current anchors) are
enforced by ``store.add_biological_asset``; this module also checks
them on read, so a break introduced after creation -- a superseded
anchor, a specimen recorded under a different id -- is caught here.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from .store import DERIVATIVE_PARENTS


@dataclass(frozen=True)
class ChainLink:
    """One asset in a specimen chain, with its assay/specimen context."""

    asset_pk: int
    asset_id: str
    kind: str
    episode_id: str
    specimen_id: str | None
    specimen_state: str
    observed_date: str
    anchor_source_version_id: int
    anchor_document_id: str | None
    anchor_version: int | None
    anchor_state: str | None


@dataclass
class ChainValidation:
    """Result of validating one specimen chain.

    ``links`` run from the original (root) to the queried asset.
    ``breaks`` holds one entry per break, each with a typed ``type``,
    the ``asset_pk`` it concerns, and a human-readable ``detail``.
    ``intact`` is True exactly when there are no breaks.
    """

    asset_pk: int
    links: list[ChainLink] = dc_field(default_factory=list)
    breaks: list[dict] = dc_field(default_factory=list)

    @property
    def intact(self):
        return not self.breaks


def _break(break_type, asset_pk, detail):
    return {"type": break_type, "asset_pk": asset_pk, "detail": detail}


def _link_from_row(store, row):
    anchor = store.db.execute(
        "SELECT document_id, version, state FROM source_versions WHERE id=?",
        (row["anchor_source_version_id"],)).fetchone()
    return ChainLink(
        asset_pk=int(row["id"]),
        asset_id=row["asset_id"],
        kind=row["kind"],
        episode_id=row["episode_id"],
        specimen_id=row["specimen_id"],
        specimen_state=row["specimen_state"],
        observed_date=row["observed_date"],
        anchor_source_version_id=int(row["anchor_source_version_id"]),
        anchor_document_id=anchor["document_id"] if anchor else None,
        anchor_version=anchor["version"] if anchor else None,
        anchor_state=anchor["state"] if anchor else None,
    )


def validate_specimen_chain(store, case_id, asset_pk):
    """Walk the parent chain of one biological asset in one case.

    Returns a :class:`ChainValidation` whose links run root-first and
    whose breaks are typed records: ``missing_asset`` (the queried asset
    is not in this case), ``missing_parent`` (a parent id has no row),
    ``cycle`` (an asset repeats in its own chain), ``unknown_specimen``
    (a link carries no recorded specimen), ``specimen_mismatch``
    (recorded specimen ids differ along the chain), ``anchor_missing``
    / ``anchor_superseded`` (a link's anchor source version is gone or
    no longer current), ``episode_mismatch`` (links span episodes), and
    ``kind_violation`` (a derivative's parent kind cannot derive it).
    """
    if type(asset_pk) is not int or asset_pk < 1:
        return ChainValidation(asset_pk, [], [_break(
            "invalid_asset_id", asset_pk,
            "Asset id must be a positive integer")])
    walked = []  # links in walk order: queried asset up to the root
    breaks = []
    seen = set()
    current = asset_pk
    while True:
        if current in seen:
            breaks.append(_break(
                "cycle", current,
                f"Asset {current} repeats in its own parent chain"))
            break
        seen.add(current)
        row = store.db.execute(
            "SELECT * FROM biological_assets WHERE id=? AND case_id=?",
            (current, case_id)).fetchone()
        if row is None:
            if not walked:
                breaks.append(_break(
                    "missing_asset", current,
                    f"Asset {current} is not in this case"))
            else:
                breaks.append(_break(
                    "missing_parent", current,
                    f"Parent asset {current} has no row in this case"))
            break
        link = _link_from_row(store, row)
        walked.append(link)
        if row["specimen_state"] == "unknown":
            breaks.append(_break(
                "unknown_specimen", current,
                f"Asset {row['asset_id']} has no recorded specimen"))
        if link.anchor_state is None:
            breaks.append(_break(
                "anchor_missing", current,
                f"Asset {row['asset_id']} anchors to a missing source version "
                f"{row['anchor_source_version_id']}"))
        elif link.anchor_state != "current":
            breaks.append(_break(
                "anchor_superseded", current,
                f"Asset {row['asset_id']} anchors to {link.anchor_document_id}"
                f"@{link.anchor_version}, which is {link.anchor_state}"))
        parent = row["parent_asset_id"]
        if parent is None:
            break
        current = parent
    links = list(reversed(walked))
    for parent_link, child_link in zip(links, links[1:]):
        if (parent_link.specimen_id is not None
                and child_link.specimen_id is not None
                and parent_link.specimen_id != child_link.specimen_id):
            breaks.append(_break(
                "specimen_mismatch", child_link.asset_pk,
                f"Asset {child_link.asset_id} carries specimen "
                f"{child_link.specimen_id}, its parent "
                f"{parent_link.asset_id} carries "
                f"{parent_link.specimen_id}"))
        if parent_link.episode_id != child_link.episode_id:
            breaks.append(_break(
                "episode_mismatch", child_link.asset_pk,
                f"Asset {child_link.asset_id} is in episode "
                f"{child_link.episode_id}, its parent "
                f"{parent_link.asset_id} is in "
                f"{parent_link.episode_id}"))
        if (child_link.kind in DERIVATIVE_PARENTS
                and parent_link.kind
                not in DERIVATIVE_PARENTS[child_link.kind]):
            breaks.append(_break(
                "kind_violation", child_link.asset_pk,
                f"Asset {child_link.asset_id} ({child_link.kind}) cannot "
                f"derive from {parent_link.asset_id} "
                f"({parent_link.kind})"))
    return ChainValidation(asset_pk, links, breaks)
