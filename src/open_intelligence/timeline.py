"""Deterministic, read-only case timeline projection over the case ledger.

This module never writes to the ledger, never calls a model, and never
fetches external data. It reports ledger facts only: current sources
ordered by occurred time, periods with no source coverage (gaps),
conflicting occurred-date assertions, and superseded versions as history.

Time taxonomy — six facets, never collapsed into one date:

- occurred: source_versions.event_date, when the reported event concerns
  the patient. Primary timeline ordering.
- documented: source_versions.issued_at, when the source was finalized.
  First tiebreak; shown as context, never merged with occurred.
- received: source_versions.received_at, when the ledger received the
  bytes. Second tiebreak; an ingest fact, not a clinical time.
- known: coverage state explicitly recorded in the ledger. A covered
  date is "known"; a gap or an unresolved conflict is "unknown".
  Unknown is reported, never filled by inference.
- amended: supersession linkage (supersedes_id / superseded state). A
  superseded version appears only in history, never in the current view.
- as-of: the ledger position this projection reflects (latest event id
  and its ledger timestamp). Read time, not event time.

No clinical meaning is inferred here: no response, progression, staging,
grading, eligibility, efficacy, treatment-relevance, significance, or
benefit claim appears anywhere in this projection.
"""

from __future__ import annotations

from datetime import date, timedelta

from .store import CaseStore, InvalidInput

DISCLAIMER = (
    "Fictional synthetic data only. This projection reports ledger ordering, "
    "coverage, and date conflicts; it does not interpret clinical meaning, "
    "significance, progression, response, or relevance of any entry. Gaps and "
    "conflicts are reported as unknown and are never filled by inference."
)


def _order_key(row: dict) -> tuple:
    """Occurred time first; documented/received break ties as context."""
    return (row["event_date"], row["issued_at"], row["received_at"],
            row["document_id"], row["version"], row["id"])


def _source_ref(row: dict) -> dict:
    """One source's time facets, kept distinct."""
    return {
        "source_id": row["id"],
        "document_id": row["document_id"],
        "version": row["version"],
        "state": row["state"],
        "occurred": row["event_date"],
        "documented": row["issued_at"],
        "received": row["received_at"],
    }


def _gaps(entries: list[dict]) -> list[dict]:
    """Interior calendar days with no current-source coverage.

    A gap exists only between two consecutive covered occurred dates with
    at least one uncovered day strictly between them. Leading or trailing
    unbounded periods are not reported: without a declared observation
    window there is nothing deterministic to bound them.
    """
    covered = sorted({entry["occurred"] for entry in entries})
    by_date: dict[str, list[str]] = {}
    for entry in entries:
        by_date.setdefault(entry["occurred"], []).append(entry["document_id"])
    gaps = []
    for previous, following in zip(covered, covered[1:]):
        start = date.fromisoformat(previous) + timedelta(days=1)
        end = date.fromisoformat(following) - timedelta(days=1)
        if start <= end:
            gaps.append({
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "coverage": "unknown",
                "before": {"occurred": previous,
                           "document_ids": sorted(set(by_date[previous]))},
                "after": {"occurred": following,
                          "document_ids": sorted(set(by_date[following]))},
            })
    return gaps


def _specimen_conflicts(current: list[dict]) -> list[dict]:
    """Same recorded specimen, different occurred dates: flag unknown."""
    by_specimen: dict[str, list[dict]] = {}
    for row in current:
        if row["specimen_id"] is not None:
            by_specimen.setdefault(row["specimen_id"], []).append(row)
    conflicts = []
    for specimen_id in sorted(by_specimen):
        rows = by_specimen[specimen_id]
        asserted = sorted({row["event_date"] for row in rows})
        if len(asserted) > 1:
            conflicts.append({
                "conflict_key": f"specimen:{specimen_id}",
                "kind": "specimen_occurred_conflict",
                "status": "unknown",
                "asserted_occurred_dates": asserted,
                "sources": [_source_ref(row) for row in sorted(rows, key=lambda r: r["id"])],
            })
    return conflicts


def _document_conflicts(all_rows: list[dict]) -> list[dict]:
    """Same document, different occurred dates across versions: flag unknown.

    The import contract blocks this for new writes; the projection still
    flags it rather than guessing if such rows ever exist.
    """
    by_document: dict[str, list[dict]] = {}
    for row in all_rows:
        by_document.setdefault(row["document_id"], []).append(row)
    conflicts = []
    for document_id in sorted(by_document):
        rows = by_document[document_id]
        asserted = sorted({row["event_date"] for row in rows})
        if len(asserted) > 1:
            conflicts.append({
                "conflict_key": f"document:{document_id}",
                "kind": "document_occurred_conflict",
                "status": "unknown",
                "asserted_occurred_dates": asserted,
                "sources": [_source_ref(row) for row in sorted(rows, key=lambda r: r["id"])],
            })
    return conflicts


def case_timeline(store: CaseStore, case_id: str) -> dict:
    """Build the timeline projection for one case. Reads only; writes nothing."""
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute("SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        rows = [dict(row) for row in store.db.execute(
            """SELECT id,document_id,version,kind,event_date,issued_at,received_at,
            specimen_id,state,supersedes_id FROM source_versions WHERE case_id=?""",
            (case_id,)).fetchall()]

        def findings_for(source_id: int) -> list[dict]:
            return [dict(row) for row in store.db.execute(
                "SELECT finding_key,certainty FROM assertions WHERE source_version_id=? ORDER BY finding_key",
                (source_id,)).fetchall()]

        current = sorted((row for row in rows if row["state"] == "current"), key=_order_key)
        entries = [{
            "source_id": row["id"],
            "document_id": row["document_id"],
            "version": row["version"],
            "kind": row["kind"],
            "specimen_id": row["specimen_id"],
            "occurred": row["event_date"],
            "documented": row["issued_at"],
            "received": row["received_at"],
            "coverage": "known",
            "state": "current",
            "supersedes_source_id": row["supersedes_id"],
            "reported_findings": [
                {"finding_key": item["finding_key"], "reported_state": item["certainty"]}
                for item in findings_for(row["id"])
            ],
        } for row in current]
        current_id_by_document = {row["document_id"]: row["id"] for row in current}
        history = [{
            "source_id": row["id"],
            "document_id": row["document_id"],
            "version": row["version"],
            "kind": row["kind"],
            "specimen_id": row["specimen_id"],
            "occurred": row["event_date"],
            "documented": row["issued_at"],
            "received": row["received_at"],
            "state": "superseded",
            "superseded_by_source_id": current_id_by_document.get(row["document_id"]),
        } for row in sorted((row for row in rows if row["state"] == "superseded"),
                            key=lambda r: (r["document_id"], r["version"], r["id"]))]
        gaps = _gaps(entries)
        conflicts = sorted(_specimen_conflicts(current) + _document_conflicts(rows),
                           key=lambda c: c["conflict_key"])
        latest = store.db.execute(
            "SELECT id,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (case_id,)).fetchone()
        as_of = ({"event_id": latest["id"], "occurred_at": latest["occurred_at"]}
                 if latest else {"event_id": None, "occurred_at": None})
        return {
            "case_id": case_id,
            "synthetic": True,
            "disclaimer": DISCLAIMER,
            "as_of": as_of,
            "counts": {
                "entries": len(entries),
                "gaps": len(gaps),
                "conflicts": len(conflicts),
                "superseded_versions": len(history),
            },
            "entries": entries,
            "gaps": gaps,
            "conflicts": conflicts,
            "history": history,
        }
