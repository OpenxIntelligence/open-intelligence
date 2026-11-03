"""Read-only B-11 enrichment projections over the case ledger.

Three projections, no writes, no new tables, no model calls, no external
data. Each function reads the existing ledger only and reports ledger facts
with source-version + anchor references (+ review state where one exists):

- :func:`case_visits`: visits as occurred-date groupings of existing ledger
  rows (sources / assertions / questions / snapshots). Groupings only: no
  visit entity exists here. Dedicated visit-record entities are draft-#233
  territory and are deliberately NOT built in this slice.
- :func:`case_journey_stages`: a deterministic stage rule over the timeline
  projection and the existing workflow states, with the rule shown beside
  the view. No human-assigned stage tags, no transition writes, no edits to
  the sources described. Human tag systems are draft-#77 territory.
- :func:`case_biological_context`: a read-only view over
  ``biological_assets`` + ``biological_inventory_assertions`` + linked
  source anchors. Per-assertion detail only; no rollup of assertions is
  ever computed (the OI-020 SCHEMA comment forbids it). Authored
  explanations are draft-#73 territory and are deliberately NOT built here.

Ordering, gap, and conflict semantics come from :mod:`timeline` and are
imported, never forked: the visit and journey projections call
:func:`timeline.case_timeline` and build on its ordered entries. Workflow
states come from :mod:`mission` the same way. Findings are quoted with
their authored ``reported_state``; no response, progression, staging,
grading, eligibility, efficacy, treatment-relevance, significance, or
benefit claim appears anywhere in these projections.
"""

from __future__ import annotations

import json

from .mission import build_patient_mission
from .store import CaseStore, InvalidInput
from .timeline import case_timeline

VISITS_DISCLAIMER = (
    "Fictional synthetic data only. A visit here is an occurred-date "
    "grouping of existing ledger rows, not a scheduled appointment, an "
    "encounter, or a clinical event. Groupings describe record coverage; "
    "they do not interpret clinical meaning, significance, progression, "
    "response, or relevance of any entry."
)

STAGES_DISCLAIMER = (
    "Fictional synthetic data only. Journey stages are workflow states "
    "computed by a fixed rule over ledger facts, not medical or "
    "patient-condition states. The rule is shown beside the view; stage "
    "position never edits, tags, or reinterprets the sources it describes."
)

BIOLOGY_DISCLAIMER = (
    "Fictional synthetic data only. This view describes recorded "
    "biological-asset rows and their own inventory assertions, each with "
    "its anchor, attributor, and state. It computes no rollup, makes no "
    "interpretive claim, and offers no diagnosis, recommendation, or "
    "assessment of response, progression, eligibility, or efficacy."
)

ORDERING_NOTE = (
    "Source ordering imported from timeline.case_timeline: occurred date, "
    "then documented (issued) date, then received date, then document id, "
    "version, and row id. Gaps and occurred-date conflicts are passed "
    "through from that projection, never recomputed here."
)


def _supersession_map(rows: list[dict]) -> dict[int, int | None]:
    """Map every source row id to its document's current row id (or None)."""
    current_by_document: dict[str, int] = {}
    for row in rows:
        if row["state"] == "current":
            current_by_document[row["document_id"]] = row["id"]
    return {row["id"]: current_by_document.get(row["document_id"]) for row in rows}


def _source_card(row: dict, superseded_by: int | None) -> dict:
    """One source's identity, time facets, and state, kept distinct."""
    return {
        "source_id": row["id"],
        "document_id": row["document_id"],
        "version": row["version"],
        "kind": row["kind"],
        "specimen_id": row["specimen_id"],
        "occurred": row["event_date"],
        "documented": row["issued_at"],
        "received": row["received_at"],
        "state": row["state"],
        "supersedes_source_id": row["supersedes_id"],
        "superseded_by_source_id": superseded_by,
    }


def case_visits(store: CaseStore, case_id: str) -> dict:
    """Group existing ledger rows by occurred date. Reads only; writes nothing.

    Every visit group carries ``kind="occurred_date_grouping"`` and
    ``creates_entity=False``: the grouping key is the occurred date itself,
    and no visit id, table, or entity exists behind it.
    """
    timeline = case_timeline(store, case_id)
    with store.db:
        store.db.execute("BEGIN")
        source_rows = [dict(row) for row in store.db.execute(
            """SELECT id,document_id,version,kind,event_date,issued_at,received_at,
            specimen_id,state,supersedes_id FROM source_versions WHERE case_id=?""",
            (case_id,)).fetchall()]
        superseded_by = _supersession_map(source_rows)
        card_by_id = {row["id"]: _source_card(row, superseded_by[row["id"]])
                      for row in source_rows}
        assertion_rows = [dict(row) for row in store.db.execute(
            """SELECT id,source_version_id,finding_key,certainty,quote,source_line
            FROM assertions WHERE case_id=? ORDER BY id""", (case_id,)).fetchall()]
        snapshot_rows = [dict(row) for row in store.db.execute(
            "SELECT * FROM snapshots WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]
        bindings: dict[int, list[int]] = {}
        for snapshot in snapshot_rows:
            bindings[snapshot["id"]] = [row[0] for row in store.db.execute(
                "SELECT source_version_id FROM snapshot_sources WHERE snapshot_id=? ORDER BY source_version_id",
                (snapshot["id"],)).fetchall()]
        question_rows = [dict(row) for row in store.db.execute(
            "SELECT * FROM questions WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]

    occurred_dates = sorted({entry["occurred"] for entry in timeline["entries"]})
    entries_by_date: dict[str, list[dict]] = {day: [] for day in occurred_dates}
    for entry in timeline["entries"]:
        entries_by_date[entry["occurred"]].append(entry)
    history_by_date: dict[str, list[dict]] = {day: [] for day in occurred_dates}
    for historic in timeline["history"]:
        if historic["occurred"] in history_by_date:
            history_by_date[historic["occurred"]].append(historic)
    findings_by_source: dict[int, list[dict]] = {}
    for item in assertion_rows:
        findings_by_source.setdefault(item["source_version_id"], []).append({
            "finding_key": item["finding_key"],
            "reported_state": item["certainty"],
            "source_line": item["source_line"],
        })

    def history_view(historic: dict) -> dict:
        return {**historic, "reported_findings": findings_by_source.get(historic["source_id"], [])}

    ungrouped_history = [history_view(historic) for historic in timeline["history"]
                         if historic["occurred"] not in history_by_date]

    def snapshot_view(snapshot: dict) -> dict:
        cited = bindings.get(snapshot["id"], [])
        pointers = [{
            "superseded_source_id": source_id,
            "superseded_by_source_id": card_by_id[source_id]["superseded_by_source_id"],
            "document_id": card_by_id[source_id]["document_id"],
        } for source_id in cited
            if source_id in card_by_id and card_by_id[source_id]["state"] == "superseded"]
        return {
            "snapshot_id": snapshot["id"],
            "question_id": snapshot["question_id"],
            "state": snapshot["state"],
            "created_at": snapshot["created_at"],
            "reviewed_at": snapshot["reviewed_at"],
            "reviewer_label": snapshot["reviewer_label"],
            "cited_source_ids": cited,
            "supersession_pointers": pointers,
        }

    visits = []
    grouped_snapshot_ids: set[int] = set()
    grouped_question_ids: set[int] = set()
    for day in occurred_dates:
        day_source_ids = [entry["source_id"] for entry in entries_by_date[day]]
        # Snapshot membership must also see history entries: after an
        # amendment, a snapshot bound to the superseded version leaves
        # the current entries, and dropping it would silently erase
        # history instead of showing it stale with a pointer.
        day_snapshot_source_ids = set(day_source_ids) | {
            historic["source_id"] for historic in history_by_date[day]}
        day_assertions = [{
            "finding_key": item["finding_key"],
            "reported_state": item["certainty"],
            "statement": item["quote"],
            "source_version_id": item["source_version_id"],
            "source_line": item["source_line"],
        } for item in assertion_rows if item["source_version_id"] in day_source_ids]
        day_snapshots = [snapshot_view(snapshot) for snapshot in snapshot_rows
                         if any(source_id in day_snapshot_source_ids
                                for source_id in bindings.get(snapshot["id"], []))]
        for view in day_snapshots:
            grouped_snapshot_ids.add(view["snapshot_id"])
            grouped_question_ids.add(view["question_id"])
        day_questions = [{
            "question_id": row["id"],
            "question": row["question"],
            "state": row["state"],
            "created_at": row["created_at"],
        } for row in question_rows if row["id"] in {view["question_id"] for view in day_snapshots}]
        visits.append({
            "visit_key": f"occurred:{day}",
            "kind": "occurred_date_grouping",
            "creates_entity": False,
            "occurred": day,
            "sources": [card_by_id[entry["source_id"]] for entry in entries_by_date[day]],
            "superseded_versions": [history_view(historic) for historic in history_by_date[day]],
            "assertions": day_assertions,
            "snapshots": day_snapshots,
            "questions": day_questions,
        })

    ungrouped_questions = [{
        "question_id": row["id"],
        "question": row["question"],
        "state": row["state"],
        "created_at": row["created_at"],
        "reason": "No source-bound snapshot recorded, so no occurred date applies.",
    } for row in question_rows if row["id"] not in grouped_question_ids]

    return {
        "case_id": case_id,
        "synthetic": True,
        "disclaimer": VISITS_DISCLAIMER,
        "projection": "occurred_date_grouping",
        "visit_entities": [],
        "not_built_note": (
            "Groupings only. No visit table, route, or entity exists in "
            "this slice; dedicated visit-record entities are draft-#233 "
            "territory."
        ),
        "ordering_note": ORDERING_NOTE,
        "as_of": timeline["as_of"],
        "counts": {
            "visits": len(visits),
            "sources": sum(len(group["sources"]) for group in visits),
            "superseded_versions": sum(len(group["superseded_versions"]) for group in visits),
            "assertions": sum(len(group["assertions"]) for group in visits),
            "snapshots_grouped": len(grouped_snapshot_ids),
            "questions_grouped": len(grouped_question_ids),
            "questions_ungrouped": len(ungrouped_questions),
            "history_ungrouped": len(ungrouped_history),
        },
        "visits": visits,
        "ungrouped_questions": ungrouped_questions,
        "ungrouped_history": ungrouped_history,
        "coverage_gaps": timeline["gaps"],
        "occurred_conflicts": timeline["conflicts"],
        "empty_statement": (
            "No visits recorded — this fictional case has no current "
            "sources, so no occurred-date groupings exist."
            if not visits else None
        ),
    }


STAGE_RULE = {
    "name": "b11-journey-stage-rule",
    "version": 1,
    "description": (
        "The current stage is a fixed mapping of the existing Patient "
        "Mission workflow status (mission.build_patient_mission, imported "
        "not forked). Exactly one stage matches. Stages are workflow "
        "states, never medical or patient-condition states, and the rule "
        "never edits, tags, or reinterprets the sources it describes."
    ),
    "mapping": [
        {"workflow_status": "awaiting_sources", "stage": "pre_first_source",
         "label": "Pre-first-source",
         "condition": "No current source document is recorded."},
        {"workflow_status": "ready_to_define_question", "stage": "ready_to_define_question",
         "label": "Ready to define a question",
         "condition": "Current sources exist; no open question, draft, stale investigation, or quarantine is recorded."},
        {"workflow_status": "investigation_in_progress", "stage": "under_review",
         "label": "Under review",
         "condition": "An open question or a draft investigation is recorded."},
        {"workflow_status": "review_required", "stage": "review_required",
         "label": "Review required",
         "condition": "A stale investigation or a quarantined delivery is recorded."},
        {"workflow_status": "reviewed_in_demo", "stage": "reviewed",
         "label": "Reviewed",
         "condition": "A demo-acknowledged investigation is recorded and nothing above applies."},
    ],
}

_STAGE_BY_WORKFLOW = {item["workflow_status"]: item["stage"] for item in STAGE_RULE["mapping"]}

STAGE_EVENT_SUMMARIES = (
    "source_imported", "question_created", "draft_created",
    "demo_review_acknowledged", "source_quarantined", "evidence_invalidated",
)


def _event_summary(kind: str, details: dict) -> str:
    """One descriptive sentence over recorded event details; no inference."""
    if kind == "source_imported":
        base = (f"Source {details.get('document_id')}@{details.get('version')} "
                f"recorded as source #{details.get('source_id')}")
        if details.get("amends_id") is None:
            return base + " (first version)."
        invalidated = details.get("invalidated_snapshots") or []
        return (base + f" amending source #{details.get('amends_id')}; "
                f"{len(invalidated)} dependent investigation(s) marked stale.")
    if kind == "question_created":
        return f"Question #{details.get('question_id')} recorded."
    if kind == "draft_created":
        return (f"Draft #{details.get('snapshot_id')} recorded for "
                f"question #{details.get('question_id')}.")
    if kind == "demo_review_acknowledged":
        return (f"Draft #{details.get('snapshot_id')} acknowledged in demo "
                "(not clinical sign-off).")
    if kind == "source_quarantined":
        return (f"Delivery #{details.get('quarantine_id')} quarantined "
                f"({details.get('reason')}); nothing imported from it.")
    if kind == "evidence_invalidated":
        invalidated = details.get("invalidated_snapshots") or []
        return (f"Evidence version #{details.get('evidence_version_id')} "
                f"changed ({details.get('reason')}); "
                f"{len(invalidated)} dependent investigation(s) marked stale.")
    return "Recorded workflow event."


def case_journey_stages(store: CaseStore, case_id: str) -> dict:
    """Apply the deterministic stage rule. Reads only; writes nothing."""
    timeline = case_timeline(store, case_id)
    mission = build_patient_mission(store.state(case_id))
    current_stage = _STAGE_BY_WORKFLOW[mission["workflow_status"]]
    with store.db:
        store.db.execute("BEGIN")
        source_rows = [dict(row) for row in store.db.execute(
            """SELECT id,document_id,version,state FROM source_versions WHERE case_id=?""",
            (case_id,)).fetchall()]
        superseded_by = _supersession_map(source_rows)
        state_by_id = {row["id"]: row for row in source_rows}
        snapshot_rows = [dict(row) for row in store.db.execute(
            "SELECT id,question_id,state,reviewer_label FROM snapshots WHERE case_id=? ORDER BY id",
            (case_id,)).fetchall()]
        bindings: dict[int, list[int]] = {}
        for snapshot in snapshot_rows:
            bindings[snapshot["id"]] = [row[0] for row in store.db.execute(
                "SELECT source_version_id FROM snapshot_sources WHERE snapshot_id=? ORDER BY source_version_id",
                (snapshot["id"],)).fetchall()]
        question_rows = [dict(row) for row in store.db.execute(
            "SELECT id,state FROM questions WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]
        quarantine_ids = [row[0] for row in store.db.execute(
            "SELECT id FROM quarantine WHERE target_case_id=? ORDER BY id", (case_id,)).fetchall()]
        event_rows = [dict(row) for row in store.db.execute(
            "SELECT id,kind,details,occurred_at FROM events WHERE case_id=? ORDER BY id",
            (case_id,)).fetchall()]

    current_source_ids = [row["id"] for row in source_rows if row["state"] == "current"]
    open_question_ids = [row["id"] for row in question_rows if row["state"] == "open"]
    draft_ids = [row["id"] for row in snapshot_rows if row["state"] == "draft"]
    stale_ids = [row["id"] for row in snapshot_rows if row["state"] == "stale"]
    reviewed = [row for row in snapshot_rows if row["state"] == "reviewed_in_demo"]

    supporting = {
        "pre_first_source": {"current_source_count": len(current_source_ids)},
        "ready_to_define_question": {"current_source_ids": current_source_ids},
        "under_review": {"open_question_ids": open_question_ids, "draft_snapshot_ids": draft_ids},
        "review_required": {"stale_snapshot_ids": stale_ids, "quarantine_ids": quarantine_ids},
        "reviewed": {"reviewed_snapshot_ids": [row["id"] for row in reviewed],
                     "reviewer_labels": [row["reviewer_label"] for row in reviewed]},
    }
    stages = [{
        "stage": item["stage"],
        "label": item["label"],
        "condition": item["condition"],
        "workflow_status": item["workflow_status"],
        "current": item["stage"] == current_stage,
        "met": item["stage"] == current_stage,
        "supporting_facts": supporting[item["stage"]],
    } for item in STAGE_RULE["mapping"]]

    stale_pointers = []
    for snapshot in snapshot_rows:
        if snapshot["state"] != "stale":
            continue
        cited = []
        for source_id in bindings.get(snapshot["id"], []):
            row = state_by_id.get(source_id)
            if row is None:
                continue
            cited.append({
                "source_id": source_id,
                "document_id": row["document_id"],
                "version": row["version"],
                "state": row["state"],
                "superseded_by_source_id": superseded_by.get(source_id),
            })
        stale_pointers.append({
            "snapshot_id": snapshot["id"],
            "question_id": snapshot["question_id"],
            "state": "stale",
            "cited_sources": cited,
        })

    evidence_events = []
    for event in event_rows:
        if event["kind"] not in STAGE_EVENT_SUMMARIES:
            continue
        try:
            details = json.loads(event["details"])
        except (json.JSONDecodeError, TypeError):
            details = {}
        if not isinstance(details, dict):
            details = {}
        evidence_events.append({
            "event_id": event["id"],
            "kind": event["kind"],
            "occurred_at": event["occurred_at"],
            "summary": _event_summary(event["kind"], details),
        })
    occurred = [entry["occurred"] for entry in timeline["entries"]]

    return {
        "case_id": case_id,
        "synthetic": True,
        "disclaimer": STAGES_DISCLAIMER,
        "rule": STAGE_RULE,
        "human_stage_tags": [],
        "not_built_note": (
            "Deterministic rule view only. No human-assigned stage tags, "
            "no transition table, and no transition writes exist in this "
            "slice; human tag systems are draft-#77 territory."
        ),
        "ordering_note": ORDERING_NOTE,
        "as_of": timeline["as_of"],
        "workflow_status": mission["workflow_status"],
        "current_stage": current_stage,
        "stages": stages,
        "timeline_span": {
            "first_occurred": min(occurred) if occurred else None,
            "last_occurred": max(occurred) if occurred else None,
            "entries": timeline["counts"]["entries"],
            "gaps": timeline["counts"]["gaps"],
            "conflicts": timeline["counts"]["conflicts"],
            "superseded_versions": timeline["counts"]["superseded_versions"],
        },
        "stale_investigation_pointers": stale_pointers,
        "stage_evidence_events": evidence_events,
        "empty_statement": (
            "No sources recorded — journey position is pre-first-source; "
            "no stage evidence exists yet."
            if not timeline["entries"] else None
        ),
    }


def case_biological_context(store: CaseStore, case_id: str) -> dict:
    """Describe recorded biological assets. Reads only; writes nothing.

    Every inventory field value appears only inside its own assertion
    object, beside that assertion's anchor, attributor, and state. No
    value is merged, summarized, or rolled up across assertions.
    """
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        source_rows = [dict(row) for row in store.db.execute(
            """SELECT id,document_id,version,event_date,state FROM source_versions
            WHERE case_id=?""", (case_id,)).fetchall()]
        superseded_by = _supersession_map(source_rows)
        source_by_id = {row["id"]: row for row in source_rows}
        asset_rows = [dict(row) for row in store.db.execute(
            "SELECT * FROM biological_assets WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]
        assertion_rows = [dict(row) for row in store.db.execute(
            """SELECT * FROM biological_inventory_assertions WHERE case_id=? ORDER BY id""",
            (case_id,)).fetchall()]
        latest = store.db.execute(
            "SELECT id,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (case_id,)).fetchone()
    asset_by_pk = {row["id"]: row for row in asset_rows}

    def anchor_view(source_id: int) -> dict:
        row = source_by_id.get(source_id)
        if row is None:
            return {"source_version_id": source_id, "known": False}
        return {
            "source_version_id": source_id,
            "known": True,
            "document_id": row["document_id"],
            "version": row["version"],
            "event_date": row["event_date"],
            "state": row["state"],
            "superseded_by_source_id": superseded_by.get(source_id),
        }

    assets = []
    for asset in asset_rows:
        parent = asset_by_pk.get(asset["parent_asset_id"]) if asset["parent_asset_id"] is not None else None
        mine = [item for item in assertion_rows if item["asset_id"] == asset["id"]]
        if asset["specimen_state"] == "recorded":
            specimen_text = f"specimen {asset['specimen_id']}"
        else:
            specimen_text = "specimen unknown (explicit — not absent)"
        assets.append({
            "asset_pk": asset["id"],
            "asset_id": asset["asset_id"],
            "kind": asset["kind"],
            "episode_id": asset["episode_id"],
            "specimen": {"state": asset["specimen_state"], "specimen_id": asset["specimen_id"]},
            "observed_date": asset["observed_date"],
            "pointer_label": asset["pointer_label"],
            "parent": (None if parent is None else {
                "asset_pk": parent["id"],
                "asset_id": parent["asset_id"],
                "kind": parent["kind"],
            }),
            "creation_anchor": anchor_view(asset["anchor_source_version_id"]),
            "description": (
                f"Asset {asset['asset_id']} is recorded as kind {asset['kind']} "
                f"in episode {asset['episode_id']}, observed {asset['observed_date']}, "
                f"{specimen_text}."
            ),
            "inventory_assertions": [{
                "id": item["id"],
                "asserted_by": item["asserted_by"],
                "state": item["state"],
                "created_at": item["created_at"],
                "anchor": anchor_view(item["source_version_id"]),
                "fields": {
                    name: {"state": item[name + "_state"], "value": item[name + "_value"]}
                    for name in ("location", "quantity", "custody", "consent", "rights")
                },
            } for item in mine],
            "inventory_note": (
                "No inventory assertion recorded — inventory unknown, not absent."
                if not mine else None
            ),
        })

    return {
        "case_id": case_id,
        "synthetic": True,
        "disclaimer": BIOLOGY_DISCLAIMER,
        "authored_explanations": [],
        "not_built_note": (
            "Recorded-context view only. No authored explanation table or "
            "route exists in this slice; authored bio explanations are "
            "draft-#73 territory."
        ),
        "as_of": ({"event_id": latest["id"], "occurred_at": latest["occurred_at"]}
                  if latest else {"event_id": None, "occurred_at": None}),
        "counts": {
            "assets": len(assets),
            "inventory_assertions": sum(len(asset["inventory_assertions"]) for asset in assets),
            "note": "Row counts only; no assertion values are merged or rolled up.",
        },
        "assets": assets,
        "interpretive_claims": [],
        "labeling_contract": {
            "kind": "hypothesis",
            "review_state": "pending",
            "note": (
                "This view makes no interpretive claims. Any future "
                "interpretive sentence must carry kind=hypothesis and "
                "review_state=pending and stay inside the investigation "
                "guard vocabulary (no response, progression, eligibility, "
                "or efficacy inference)."
            ),
        },
        "empty_statement": (
            "No biological assets recorded — no asset or inventory rows "
            "exist for this fictional case."
            if not assets else None
        ),
    }
