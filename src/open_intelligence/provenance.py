"""Read-only source provenance and amendment-history projection.

This module never writes to the ledger, never calls a model, and never
fetches external data. It reports ledger facts only: per source document,
the ordered version chain from the original to each amendment, with exact
anchors, receipt dates, current/superseded state, the review state of
saved investigations citing each version, and the import events that
recorded each link.

The projection reads live ledger state on every call. It keeps no cache,
so an amendment is visible as a new chain link and chain event the moment
its import transaction commits. Superseded versions stay retrievable
through the existing source-text route; this projection only references
them, never deletes or rewrites them.

No clinical meaning is inferred here: no response, progression, staging,
eligibility, efficacy, treatment-relevance, or benefit claim appears
anywhere in this projection. Review states are quoted verbatim from the
existing snapshot ledger (draft, reviewed_in_demo, stale).
"""

from __future__ import annotations

import json

from .store import CaseStore, InvalidInput

DISCLAIMER = (
    "Fictional synthetic data only. This projection reports source version "
    "chains, receipt order, and the review state of saved investigations "
    "citing each version; it does not interpret clinical meaning, "
    "significance, or relevance. Superseded versions are kept for history. "
    "A new reviewed conclusion requires a separately scoped review."
)


def _safe_details(raw: object) -> dict:
    """Return a JSON object or an empty mapping; never guess at damage."""
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [item for item in value if type(item) is int]


def case_provenance(store: CaseStore, case_id: str) -> dict:
    """Build the provenance projection for one case. Reads only; writes nothing."""
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)
        ).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        source_rows = [
            dict(row)
            for row in store.db.execute(
                """SELECT id,document_id,version,kind,event_date,issued_at,
                received_at,specimen_id,state,supersedes_id,sha256
                FROM source_versions WHERE case_id=?
                ORDER BY document_id,version,id""",
                (case_id,),
            ).fetchall()
        ]
        snapshot_rows = {
            int(row["id"]): dict(row)
            for row in store.db.execute(
                """SELECT id,question_id,state,created_at FROM snapshots
                WHERE case_id=? ORDER BY id""",
                (case_id,),
            ).fetchall()
        }
        citing: dict[int, list[dict]] = {}
        for row in store.db.execute(
            """SELECT ss.snapshot_id,ss.source_version_id FROM snapshot_sources ss
            JOIN snapshots s ON s.id=ss.snapshot_id WHERE s.case_id=?""",
            (case_id,),
        ).fetchall():
            snapshot = snapshot_rows.get(int(row["snapshot_id"]))
            if snapshot is None:
                continue
            citing.setdefault(int(row["source_version_id"]), []).append(
                {
                    "snapshot_id": int(snapshot["id"]),
                    "question_id": int(snapshot["question_id"]),
                    "state": str(snapshot["state"]),
                    "created_at": str(snapshot["created_at"]),
                }
            )
        for versions in citing.values():
            versions.sort(key=lambda item: item["snapshot_id"])
        events = [
            dict(row)
            for row in store.db.execute(
                """SELECT id,kind,details,occurred_at FROM events
                WHERE case_id=? ORDER BY id""",
                (case_id,),
            ).fetchall()
        ]
        import_event_by_source: dict[int, dict] = {}
        for event in events:
            if event.get("kind") != "source_imported":
                continue
            details = _safe_details(event.get("details"))
            source_id = details.get("source_id")
            if type(source_id) is not int or source_id in import_event_by_source:
                continue
            amends_source_id = details.get("amends_id")
            if amends_source_id is not None and type(amends_source_id) is not int:
                amends_source_id = None
            import_event_by_source[source_id] = {
                "event_id": event.get("id"),
                "occurred_at": event.get("occurred_at"),
                "amends_source_id": amends_source_id,
                "invalidated_snapshots": _safe_int_list(
                    details.get("invalidated_snapshots")
                ),
            }
        grouped: dict[str, list[dict]] = {}
        for row in source_rows:
            grouped.setdefault(str(row["document_id"]), []).append(row)
        documents: list[dict] = []
        current_count = 0
        superseded_count = 0
        for document_id in sorted(grouped):
            versions = sorted(
                grouped[document_id], key=lambda row: (row["version"], row["id"])
            )
            by_id = {int(row["id"]): row for row in versions}
            next_by_previous: dict[int, int] = {}
            for row in versions:
                previous = row["supersedes_id"]
                if previous is not None and int(previous) in by_id:
                    next_by_previous[int(previous)] = int(row["id"])
            chain: list[dict] = []
            chain_events: list[dict] = []
            for row in versions:
                source_id = int(row["id"])
                version = int(row["version"])
                state = str(row["state"])
                if state == "current":
                    current_count += 1
                elif state == "superseded":
                    superseded_count += 1
                received_at = str(row["received_at"])
                event = import_event_by_source.get(source_id)
                import_event = None
                if event is not None:
                    import_event = {
                        "event_id": event["event_id"],
                        "occurred_at": event["occurred_at"],
                        "invalidated_snapshots": list(
                            event["invalidated_snapshots"]
                        ),
                    }
                    chain_events.append(
                        {
                            "event_id": event["event_id"],
                            "occurred_at": event["occurred_at"],
                            "version": version,
                            "source_id": source_id,
                            "amends_source_id": event["amends_source_id"],
                            "invalidated_snapshots": list(
                                event["invalidated_snapshots"]
                            ),
                        }
                    )
                chain.append(
                    {
                        "source_id": source_id,
                        "document_id": document_id,
                        "version": version,
                        "anchor": f"{document_id}@{version}",
                        "state": state,
                        "kind": str(row["kind"]),
                        "event_date": str(row["event_date"]),
                        "issued_at": str(row["issued_at"]),
                        "received_at": received_at,
                        "received_date": received_at[:10],
                        "sha256": str(row["sha256"]),
                        "supersedes_source_id": (
                            int(row["supersedes_id"])
                            if row["supersedes_id"] is not None
                            else None
                        ),
                        "superseded_by_source_id": next_by_previous.get(source_id),
                        "import_event": import_event,
                        "citing_snapshots": list(citing.get(source_id, [])),
                    }
                )
            current_versions = [
                link["version"] for link in chain if link["state"] == "current"
            ]
            first = versions[0]
            documents.append(
                {
                    "document_id": document_id,
                    "kind": str(first["kind"]),
                    "event_date": str(first["event_date"]),
                    "specimen_id": (
                        str(first["specimen_id"])
                        if first["specimen_id"] is not None
                        else None
                    ),
                    "chain_length": len(chain),
                    "current_version": (
                        current_versions[0] if len(current_versions) == 1 else None
                    ),
                    "chain": chain,
                    "chain_events": chain_events,
                }
            )
        latest = events[-1] if events else None
        return {
            "case_id": case_id,
            "synthetic": True,
            "disclaimer": DISCLAIMER,
            "as_of": (
                {"event_id": latest["id"], "occurred_at": latest["occurred_at"]}
                if latest
                else {"event_id": None, "occurred_at": None}
            ),
            "counts": {
                "documents": len(documents),
                "versions": len(source_rows),
                "current": current_count,
                "superseded": superseded_count,
            },
            "documents": documents,
        }
