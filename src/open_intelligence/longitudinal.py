"""A2 Longitudinal: the deterministic longitudinal picture (program plan slice D3).

A2 turns the case ledger into a longitudinal picture — one ordered track
per finding key over the case's current sources — computed
deterministically, proposed by agents, never asserted by the toolset
itself. This module never calls a model, never writes to the ledger,
and never fetches external data.

What it reports, per finding key, from current source versions only
(superseded versions appear nowhere in the tracks):

* ``tracks``: the ordered points — occurred date, certainty, source
  version, specimen, verbatim quote, source line — in timeline order
  (occurred, then documented, then received, then document and version,
  the same ordering as ``timeline.case_timeline``).
* ``changes``: consecutive points whose certainty differs, with from/to.
  A change is a ledger fact (the certainty recorded differs); it is not
  a progression, response, or significance claim.
* ``same_date_conflicts``: one finding key asserted with different
  certainties on the same occurred date by different current sources.
  Reported as unknown, never resolved by picking a winner.
* ``gaps``: interior calendar days with no current-source coverage
  (the ``timeline.py`` rule: only between two consecutive covered
  occurred dates; leading/trailing unbounded periods are not gaps).

No clinical meaning is inferred here: no response, progression,
staging, grading, eligibility, efficacy, treatment-relevance,
significance, or benefit claim appears anywhere in this picture. Gaps
and conflicts are reported as unknown and are never filled by
inference. The first live caller is a future roster slice: A2 is the
deterministic machinery the longitudinal role agent calls when
parallel roster wiring lands (program plan C4 out of scope).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import date, timedelta

from .store import InvalidInput


def _order_key(row: dict) -> tuple:
    """Timeline ordering: occurred, documented, received, document, version, id."""
    return (row["event_date"], row["issued_at"], row["received_at"],
            row["document_id"], row["version"], row["id"])


@dataclass
class LongitudinalPicture:
    """One case's longitudinal picture, read from the ledger.

    ``tracks`` maps each finding key to its ordered points. ``changes``
    lists certainty changes between consecutive points. ``same_date_conflicts``
    lists keys asserted with different certainties on one occurred date.
    ``gaps`` lists interior uncovered day ranges.
    """

    case_id: str
    tracks: dict[str, list[dict]] = dc_field(default_factory=dict)
    changes: list[dict] = dc_field(default_factory=list)
    same_date_conflicts: list[dict] = dc_field(default_factory=list)
    gaps: list[dict] = dc_field(default_factory=list)


def _gaps(covered_dates: list[str]) -> list[dict]:
    """Interior calendar days with no current-source coverage.

    Same rule as ``timeline.case_timeline``: a gap exists only between
    two consecutive covered occurred dates with at least one uncovered
    day strictly between them.
    """
    covered = sorted(set(covered_dates))
    gaps = []
    for previous, following in zip(covered, covered[1:]):
        start = date.fromisoformat(previous) + timedelta(days=1)
        end = date.fromisoformat(following) - timedelta(days=1)
        if start <= end:
            gaps.append({
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "coverage": "unknown",
                "before_occurred": previous,
                "after_occurred": following,
            })
    return gaps


def longitudinal_picture(store, case_id: str) -> LongitudinalPicture:
    """Build the longitudinal picture for one case. Reads only; writes nothing."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        sources = [dict(row) for row in store.db.execute(
            """SELECT id,document_id,version,event_date,issued_at,received_at,
            specimen_id,state FROM source_versions
            WHERE case_id=? AND state='current'""", (case_id,)).fetchall()]
        sources.sort(key=_order_key)
        assertions = [dict(row) for row in store.db.execute(
            """SELECT a.finding_key,a.certainty,a.quote,a.source_line,
            a.source_version_id FROM assertions a
            JOIN source_versions s ON s.id=a.source_version_id
            WHERE a.case_id=? AND s.state='current'""", (case_id,)).fetchall()]
    source_by_id = {row["id"]: row for row in sources}
    tracks: dict[str, list[dict]] = {}
    for item in assertions:
        source = source_by_id.get(item["source_version_id"])
        if source is None:
            continue
        tracks.setdefault(item["finding_key"], []).append({
            "occurred": source["event_date"],
            "documented": source["issued_at"],
            "received": source["received_at"],
            "certainty": item["certainty"],
            "source_version_id": int(item["source_version_id"]),
            "document_id": source["document_id"],
            "version": int(source["version"]),
            "specimen_id": source["specimen_id"],
            "quote": item["quote"],
            "source_line": int(item["source_line"]),
        })
    changes = []
    same_date_conflicts = []
    for key in sorted(tracks):
        points = sorted(tracks[key], key=lambda p: (
            p["occurred"], p["documented"], p["received"],
            p["document_id"], p["version"], p["source_version_id"]))
        tracks[key] = points
        for earlier, later in zip(points, points[1:]):
            # Only cross-date differences are changes: two certainties on
            # the same occurred date are a conflict (below), not a change.
            if (earlier["occurred"] != later["occurred"]
                    and earlier["certainty"] != later["certainty"]):
                changes.append({
                    "finding_key": key,
                    "from_certainty": earlier["certainty"],
                    "to_certainty": later["certainty"],
                    "earlier": earlier,
                    "later": later,
                })
        by_date: dict[str, dict[str, list[dict]]] = {}
        for point in points:
            by_date.setdefault(point["occurred"], {}).setdefault(
                point["certainty"], []).append(point)
        for occurred in sorted(by_date):
            certainties = sorted(by_date[occurred])
            if len(certainties) > 1:
                same_date_conflicts.append({
                    "finding_key": key,
                    "occurred": occurred,
                    "certainties": certainties,
                    "status": "unknown",
                    "points": [point for certainty in certainties
                               for point in by_date[occurred][certainty]],
                })
    changes.sort(key=lambda c: (c["finding_key"], c["earlier"]["occurred"],
                                c["later"]["occurred"]))
    same_date_conflicts.sort(key=lambda c: (c["finding_key"], c["occurred"]))
    return LongitudinalPicture(
        case_id=case_id,
        tracks=tracks,
        changes=changes,
        same_date_conflicts=same_date_conflicts,
        gaps=_gaps([row["event_date"] for row in sources]),
    )
