"""Deterministic, read-only whole-journey timeline projection.

This module never writes to the ledger, never calls a model, and never
fetches external data. It lists ledger events oldest-first in plain
language: fictional source imports, amendments, questions, drafts,
demo reviews, quarantine, and other status changes.

Design notes:

- Entries follow the ``events`` ledger (``ORDER BY id``), so history is
  never hidden. Each import/amendment is its own entry; a superseded
  import stays visible with ``status=superseded`` and a pointer to the
  newer entry.
- ``case_created`` is not a journey entry. An empty case (no imports,
  questions, drafts, or reviews) therefore yields zero entries and an
  honest empty state, never invented entries.
- Current freshness is shown: an import that was later amended reports
  ``superseded``; a draft later invalidated reports ``stale``. The
  description records what happened at the time; ``status`` reports the
  current ledger state.
- No clinical meaning is inferred: no response, progression, staging,
  grading, eligibility, efficacy, treatment-relevance, significance, or
  benefit claim appears anywhere in this projection.
"""

from __future__ import annotations

import json

from .store import CaseStore, InvalidInput

DISCLAIMER = (
    "Fictional synthetic data only. This whole-journey view lists ledger "
    "events in the order recorded; it does not interpret clinical meaning, "
    "significance, progression, response, or relevance. Superseded versions "
    "stay visible as history and are never deleted."
)


def _safe_details(raw: object) -> dict:
    """Return event details as a dict, never guessing at damaged rows."""
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [item for item in value if type(item) is int]


def case_journey(store: CaseStore, case_id: str) -> dict:
    """Build the whole-journey projection for one case. Reads only."""
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)
        ).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        events = [
            dict(row)
            for row in store.db.execute(
                "SELECT id,kind,details,occurred_at FROM events "
                "WHERE case_id=? ORDER BY id ASC",
                (case_id,),
            ).fetchall()
        ]
        sources = {
            int(row["id"]): dict(row)
            for row in store.db.execute(
                "SELECT id,document_id,version,kind,event_date,issued_at,"
                "received_at,state,supersedes_id FROM source_versions "
                "WHERE case_id=?",
                (case_id,),
            ).fetchall()
        }
        questions = {
            int(row["id"]): dict(row)
            for row in store.db.execute(
                "SELECT id,question,state,created_at FROM questions "
                "WHERE case_id=?",
                (case_id,),
            ).fetchall()
        }
        snapshots = {
            int(row["id"]): dict(row)
            for row in store.db.execute(
                "SELECT id,question_id,state,created_at FROM snapshots "
                "WHERE case_id=?",
                (case_id,),
            ).fetchall()
        }
        snapshot_sources: dict[int, list[int]] = {}
        for row in store.db.execute(
            "SELECT ss.snapshot_id,ss.source_version_id FROM snapshot_sources ss "
            "JOIN snapshots s ON s.id=ss.snapshot_id WHERE s.case_id=?",
            (case_id,),
        ).fetchall():
            snapshot_sources.setdefault(int(row["snapshot_id"]), []).append(
                int(row["source_version_id"])
            )
        evidence_state = {
            int(row["id"]): dict(row)
            for row in store.db.execute(
                "SELECT id,evidence_key,version,state FROM evidence_versions"
            ).fetchall()
        }
        investigations = {
            int(row["id"]): dict(row)
            for row in store.db.execute(
                "SELECT id,question_id,template,status,mode,stale,created_at "
                "FROM investigations WHERE case_id=?",
                (case_id,),
            ).fetchall()
        }

        # Map each source import to its journey event, so supersession can
        # point from the older entry to the newer entry and back.
        import_event_by_source: dict[int, int] = {}
        for event in events:
            if event["kind"] != "source_imported":
                continue
            details = _safe_details(event.get("details"))
            source_id = details.get("source_id")
            if type(source_id) is int:
                import_event_by_source[source_id] = int(event["id"])

        # For each document, the current source id (if any) determines which
        # older entries are superseded and where they point.
        current_by_document: dict[str, int] = {}
        for source_id, row in sources.items():
            if row["state"] == "current":
                current_by_document[str(row["document_id"])] = source_id

        # For stale snapshots, find the invalidating event (amendment or
        # evidence/rights change) so the older entry points at the newer one.
        invalidated_by: dict[int, int] = {}
        for event in events:
            details = _safe_details(event.get("details"))
            for snapshot_id in _int_list(details.get("invalidated_snapshots")):
                if snapshot_id not in invalidated_by:
                    invalidated_by[snapshot_id] = int(event["id"])

        def source_ref(source_id: int | None) -> str | None:
            if source_id is None:
                return None
            row = sources.get(int(source_id))
            if not row:
                return None
            return f"{row['document_id']}@{row['version']}"

        def snapshot_refs(snapshot_id: int) -> tuple[list[int], list[str]]:
            ids = sorted(snapshot_sources.get(int(snapshot_id), []))
            refs = [r for sid in ids if (r := source_ref(sid)) is not None]
            return ids, refs

        entries: list[dict] = []
        for event in events:
            event_id = int(event["id"])
            kind = str(event.get("kind") or "")
            occurred_at = event.get("occurred_at")
            details = _safe_details(event.get("details"))
            # Case creation is not a journey milestone. Skipping it keeps an
            # empty case honestly empty instead of inventing a milestone.
            if kind == "case_created":
                continue
            entry: dict = {
                "event_id": event_id,
                "occurred_at": occurred_at,
                "event_kind": kind,
                "kind": "status_change",
                "description": f"Fictional ledger event {kind} was recorded.",
                "source_version_id": None,
                "source_ref": None,
                "source_version_ids": [],
                "source_refs": [],
                "status": "recorded",
                "supersedes_event_id": None,
                "superseded_by_event_id": None,
                "fictional": True,
            }
            if kind == "source_imported":
                document_id = details.get("document_id")
                version = details.get("version")
                source_id = details.get("source_id")
                amends_id = details.get("amends_id")
                invalidated = _int_list(details.get("invalidated_snapshots"))
                row = sources.get(int(source_id)) if type(source_id) is int else None
                doc = str(document_id) if isinstance(document_id, str) else "unknown document"
                ver_text = str(int(version)) if type(version) is int else "unknown version"
                if type(amends_id) is int:
                    prev = sources.get(int(amends_id))
                    prev_ver = prev["version"] if prev else "?"
                    entry["kind"] = "amendment"
                    text = (
                        f"Fictional report {doc} was amended to version {ver_text}, "
                        f"replacing version {prev_ver}. The earlier version "
                        "stays visible as history."
                    )
                    supersedes_event = import_event_by_source.get(int(amends_id))
                    if supersedes_event is not None:
                        entry["supersedes_event_id"] = supersedes_event
                else:
                    entry["kind"] = "import"
                    event_date = row["event_date"] if row else "unknown date"
                    report_kind = row["kind"] if row else "report"
                    text = (
                        f"Fictional {report_kind} report {doc} version {ver_text} "
                        f"was imported. Event date {event_date}."
                    )
                if invalidated:
                    ids = ", ".join(f"#{i}" for i in sorted(invalidated))
                    text += f" Fictional investigation(s) {ids} were marked stale."
                else:
                    text += " No fictional investigation was marked stale."
                entry["description"] = text
                if type(source_id) is int:
                    entry["source_version_id"] = int(source_id)
                    entry["source_ref"] = source_ref(int(source_id))
                    entry["source_version_ids"] = [int(source_id)]
                    if entry["source_ref"] is not None:
                        entry["source_refs"] = [entry["source_ref"]]
                entry["status"] = row["state"] if row else "recorded"
                # Point a superseded import at its current replacement.
                if row and row["state"] == "superseded":
                    current_id = current_by_document.get(str(row["document_id"]))
                    if current_id is not None:
                        newer = import_event_by_source.get(int(current_id))
                        if newer is not None and newer != event_id:
                            entry["superseded_by_event_id"] = newer
                entry["invalidated_snapshot_ids"] = sorted(invalidated)
            elif kind == "source_quarantined":
                quarantine_id = details.get("quarantine_id")
                reason = details.get("reason")
                entry["kind"] = "quarantine"
                entry["status"] = "quarantined"
                qid = f"#{quarantine_id}" if type(quarantine_id) is int else "unknown delivery"
                why = str(reason) if isinstance(reason, str) else "an unrecorded reason"
                entry["description"] = (
                    f"Fictional source delivery {qid} was quarantined ({why}). "
                    "No statements were imported from it."
                )
                if type(quarantine_id) is int:
                    entry["quarantine_id"] = int(quarantine_id)
            elif kind == "question_created":
                question_id = details.get("question_id")
                entry["kind"] = "question"
                row = questions.get(int(question_id)) if type(question_id) is int else None
                entry["status"] = row["state"] if row else "recorded"
                if type(question_id) is int:
                    entry["question_id"] = int(question_id)
                    # The question text itself lives in the case ledger and may
                    # contain arbitrary author wording; the journey lists the
                    # fact of the question without echoing it, so this
                    # projection never inherits clinical-sounding phrasing.
                    entry["description"] = (
                        f"Fictional question Q{int(question_id)} was recorded."
                    )
            elif kind == "draft_created":
                snapshot_id = details.get("snapshot_id")
                question_id = details.get("question_id")
                entry["kind"] = "draft"
                row = snapshots.get(int(snapshot_id)) if type(snapshot_id) is int else None
                entry["status"] = row["state"] if row else "recorded"
                if type(snapshot_id) is int:
                    entry["snapshot_id"] = int(snapshot_id)
                    ids, refs = snapshot_refs(int(snapshot_id))
                    entry["source_version_ids"] = ids
                    entry["source_refs"] = refs
                    if len(ids) == 1:
                        entry["source_version_id"] = ids[0]
                        entry["source_ref"] = refs[0] if refs else None
                    qid = f"Q{question_id}" if type(question_id) is int else "an unknown question"
                    entry["description"] = (
                        f"Fictional investigation draft #{int(snapshot_id)} was saved "
                        f"for {qid}. It stays visible even if a later amendment marks it stale."
                    )
                    if row and row["state"] == "stale" and int(snapshot_id) in invalidated_by:
                        entry["superseded_by_event_id"] = invalidated_by[int(snapshot_id)]
            elif kind == "demo_review_acknowledged":
                snapshot_id = details.get("snapshot_id")
                entry["kind"] = "review"
                row = snapshots.get(int(snapshot_id)) if type(snapshot_id) is int else None
                entry["status"] = row["state"] if row else "recorded"
                if type(snapshot_id) is int:
                    entry["snapshot_id"] = int(snapshot_id)
                    ids, refs = snapshot_refs(int(snapshot_id))
                    entry["source_version_ids"] = ids
                    entry["source_refs"] = refs
                    if len(ids) == 1:
                        entry["source_version_id"] = ids[0]
                        entry["source_ref"] = refs[0] if refs else None
                    entry["description"] = (
                        f"Fictional investigation #{int(snapshot_id)} was acknowledged "
                        "in demo. This is not credentialed clinical review."
                    )
                    if row and row["state"] == "stale" and int(snapshot_id) in invalidated_by:
                        entry["superseded_by_event_id"] = invalidated_by[int(snapshot_id)]
            elif kind == "synthetic_evidence_assessed":
                assessment_id = details.get("assessment_id")
                evidence_id = details.get("evidence_version_id")
                entry["kind"] = "assessment"
                row = evidence_state.get(int(evidence_id)) if type(evidence_id) is int else None
                entry["status"] = row["state"] if row else "recorded"
                if type(assessment_id) is int:
                    entry["assessment_id"] = int(assessment_id)
                if type(evidence_id) is int:
                    entry["evidence_version_id"] = int(evidence_id)
                    if row:
                        entry["evidence_ref"] = f"{row['evidence_key']}@{row['version']}"
                entry["description"] = (
                    "A fictional evidence assessment was recorded. "
                    "Relationships are human-labelled and not clinical appraisal."
                )
            elif kind == "evidence_invalidated":
                evidence_id = details.get("evidence_version_id")
                reason = details.get("reason")
                invalidated = _int_list(details.get("invalidated_snapshots"))
                entry["kind"] = "status_change"
                why = str(reason) if isinstance(reason, str) else "a recorded change"
                ev_label = f"#{evidence_id}" if type(evidence_id) is int else "unknown version"
                entry["description"] = (
                    f"Fictional evidence version {ev_label} changed ({why}). "
                    + (
                        f"Fictional investigation(s) "
                        f"{', '.join(f'#{i}' for i in sorted(invalidated))} "
                        "were marked stale."
                        if invalidated
                        else "No fictional investigation was marked stale."
                    )
                )
                entry["invalidated_snapshot_ids"] = sorted(invalidated)
            elif kind == "investigation_created":
                investigation_id = details.get("investigation_id")
                template = details.get("template")
                mode = details.get("mode")
                entry["kind"] = "investigation"
                row = investigations.get(int(investigation_id)) if type(investigation_id) is int else None
                if row and int(row.get("stale") or 0) == 1:
                    entry["status"] = "stale"
                elif row:
                    entry["status"] = str(row.get("status") or "recorded")
                if type(investigation_id) is int:
                    entry["investigation_id"] = int(investigation_id)
                inv_label = f"#{investigation_id}" if type(investigation_id) is int else "unknown id"
                allowed_templates = {"evidence-summary", "timeline-gaps", "evidence-applicability"}
                allowed_modes = {"live", "replay"}
                label_template = template if template in allowed_templates else "bounded template"
                label_mode = mode if mode in allowed_modes else "recorded mode"
                entry["description"] = (
                    f"Fictional model-assisted investigation {inv_label} "
                    f"({label_template}, {label_mode}) was stored as a hypothesis "
                    "pending review, never a validated conclusion."
                )
            elif kind == "broker_invalidated":
                invalidated = _int_list(details.get("invalidated_snapshots"))
                entry["description"] = (
                    "A fictional rights change was recorded. "
                    + (
                        f"Fictional investigation(s) "
                        f"{', '.join(f'#{i}' for i in sorted(invalidated))} "
                        "were marked stale."
                        if invalidated
                        else "No fictional investigation was marked stale."
                    )
                )
                entry["invalidated_snapshot_ids"] = sorted(invalidated)
            elif kind == "discovery_invalidated":
                invalidated = _int_list(details.get("invalidated_snapshots"))
                invalidated_links = _int_list(details.get("invalidated_discovery_links"))
                entry["description"] = (
                    "A fictional discovery-rights change was recorded. "
                    + (
                        f"Fictional investigation(s) "
                        f"{', '.join(f'#{i}' for i in sorted(invalidated))} "
                        "were marked stale. "
                        if invalidated
                        else "No fictional investigation was marked stale. "
                    )
                    + (
                        f"Fictional discovery link(s) "
                        f"{', '.join(f'#{i}' for i in sorted(invalidated_links))} "
                        "were marked invalid."
                        if invalidated_links
                        else "No fictional discovery link was marked invalid."
                    )
                )
                entry["invalidated_snapshot_ids"] = sorted(invalidated)
                entry["invalidated_discovery_link_ids"] = sorted(invalidated_links)
            elif kind == "broker_link_created":
                entry["kind"] = "assessment"
                entry["description"] = (
                    "A fictional rights-gated source link was recorded for one question. "
                    "It carries no verified permission claim."
                )
            elif kind == "discovery_linked":
                entry["kind"] = "assessment"
                entry["description"] = (
                    "A fictional discovery item was linked to one question with a "
                    "human-entered applicability label."
                )
            elif kind in (
                "option_created",
                "option_dependency_added",
                "preparation_task_created",
                "preparation_task_status_changed",
                "optionality_threat_added",
                "option_reviewed",
                "option_review_reopened",
            ):
                entry["description"] = (
                    f"Fictional discussion option ledger event {kind} was recorded. "
                    "Discussion only; not a clinical recommendation."
                )
            elif kind in ("biological_asset_created", "biological_inventory_asserted"):
                entry["description"] = (
                    f"Fictional biological-asset ledger event {kind} was recorded. "
                    "Inventory states stay explicit; unknown is not absent."
                )
            elif kind.startswith("adapter_"):
                entry["description"] = (
                    f"Fictional adapter receipt event {kind} was recorded. "
                    "Source bytes still enter only through the import contract."
                )
            entries.append(entry)

        # Backfill: an older import superseded by a later amendment must point
        # forward even when the source row lookup above missed it (defensive;
        # the ledger normally keeps both rows).
        by_event = {entry["event_id"]: entry for entry in entries}
        for entry in entries:
            supersedes = entry.get("supersedes_event_id")
            if type(supersedes) is int and supersedes in by_event:
                older = by_event[supersedes]
                if older.get("superseded_by_event_id") is None:
                    older["superseded_by_event_id"] = entry["event_id"]
                    if older.get("status") == "current":
                        older["status"] = "superseded"

        return {
            "case_id": case_id,
            "synthetic": True,
            "disclaimer": DISCLAIMER,
            "count": len(entries),
            "counts": {"entries": len(entries)},
            "entries": entries,
        }
