"""Read-only unified case-home composition over the existing case ledger.

This module adds no facts, no interpretation, and no second record. It calls
the existing builders and accessors — ``CaseStore.state``,
``mission.build_patient_mission``, ``timeline.case_timeline``,
``changes.changes_since_review``, ``CaseStore.option_view``,
``CaseStore.list_investigations`` and ``CaseStore.case_discovery_links`` —
and embeds their outputs citation-for-citation. Every section names the
builder it came from; anything with no builder in this build (patient goals,
clinical staging) is reported as unavailable, never inferred.

The composition never writes to the ledger, never calls a model, and never
fetches external data. It reports ledger facts only, for one case at a time.
No clinical meaning is inferred here: no response, progression, staging,
grading, eligibility, efficacy, treatment-relevance, significance, or
benefit claim appears anywhere in this projection.
"""

from __future__ import annotations

from .changes import changes_since_review
from .mission import build_patient_mission
from .store import CaseStore
from .timeline import case_timeline

MARKING = "FICTIONAL DEMO DATA — not a real patient"
SCOPE = "synthetic_workflow_only"

BUILDERS = {
    "mission": "open_intelligence.mission.build_patient_mission",
    "timeline": "open_intelligence.timeline.case_timeline",
    "changes": "open_intelligence.changes.changes_since_review",
    "options": "open_intelligence.store.CaseStore.option_view",
    "investigations": "open_intelligence.store.CaseStore.list_investigations",
    "discovery": "open_intelligence.store.CaseStore.case_discovery_links",
    "ledger": "open_intelligence.store.CaseStore.state",
}

LIMITATIONS = [
    "Read-only composition: every section below cites the existing builder "
    "or ledger read it came from. No new fact is created here.",
    "Fictional synthetic data only. Nothing here is clinically appraised, "
    "and nothing here stands in for care decisions.",
    "Patient goals are not shown because this build has no goals builder "
    "and no goals table; nothing is substituted or inferred.",
    "Stage is the workflow/review state from the mission projection "
    "(awaiting_sources, ready_to_define_question, investigation_in_progress, "
    "review_required, reviewed_in_demo). This build performs no clinical staging.",
    "A demo acknowledgment is not clinician identity, clinical approval, or "
    "patient applicability.",
    "The changes section uses its default anchor (the latest demo-review "
    "acknowledgment, or case creation when nothing has been acknowledged). "
    "An explicit anchor remains available only at /changes-since-review.",
    "A source amendment marks the case's model investigations stale as a "
    "whole; an evidence change marks only the investigations whose claims "
    "cite an assessment of that exact evidence version.",
    "A broker-link re-review flags the valid discovery links that cite it "
    "through the event ledger; those link rows stay valid until their own "
    "rights row is revoked or corrected.",
]


def _report_position(store: CaseStore, case_id: str) -> dict:
    """The ledger position this composition reflects (read time, not event time)."""
    latest = store.db.execute(
        "SELECT id,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
        (case_id,)).fetchone()
    if latest:
        return {"event_id": latest["id"], "occurred_at": latest["occurred_at"]}
    return {"event_id": None, "occurred_at": None}


def _frozen(value: object) -> object:
    """Deep-freeze builder output into plain JSON values (no shared mutation)."""
    if isinstance(value, dict):
        return {key: _frozen(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_frozen(item) for item in value]
    return value


def build_case_home(store: CaseStore, case_id: str) -> dict:
    """Compose the unified case home for one case. Reads only; writes nothing."""
    state = store.state(case_id)
    mission = build_patient_mission(state)
    timeline = case_timeline(store, case_id)
    changes = changes_since_review(store, case_id)
    options = store.option_view(case_id)
    investigations = store.list_investigations(case_id)
    discovery_links = store.case_discovery_links(case_id)

    follow_ups = []
    for option in options["options"]:
        for task in option["preparation_tasks"]:
            follow_ups.append({
                "task_id": task["id"],
                "option_id": option["id"],
                "option_label": option["label"],
                "label": task["label"],
                "owner_label": task["owner_label"],
                "status": task["status"],
                "lead_time_days": task["lead_time_days"],
                "created_at": task["created_at"],
            })

    review_state = {
        "projection": "direct_ledger_read",
        "sources": ["CaseStore.state", "CaseStore.option_view",
                    "CaseStore.list_investigations", "CaseStore.case_discovery_links"],
        "snapshots": [
            {
                "snapshot_id": item["id"],
                "question_id": item["question_id"],
                "state": item["state"],
                "reviewed_at": item["reviewed_at"],
                "reviewer_label": item["reviewer_label"],
                "source_ids": list(item["source_ids"]),
                "evidence_assessment_ids": list(item["evidence_assessment_ids"]),
                "broker_link_ids": list(item["broker_link_ids"]),
            }
            for item in state["snapshots"]
        ],
        "options": [
            {
                "option_id": item["id"],
                "label": item["label"],
                "operational_status": item["operational_status"],
                "display_operational_status": item["display_operational_status"],
                "derived_epistemic_status": item["derived_epistemic_status"],
                "review_state": item["review_state"],
                "snapshot_id": item["snapshot_id"],
                "snapshot_state": item["snapshot_state"],
            }
            for item in options["options"]
        ],
        "investigations": [
            {
                "investigation_id": item["id"],
                "question_id": item["question_id"],
                "template": item["template"],
                "status": item["status"],
                "mode": item["mode"],
                "model": item["model"],
                "stale": bool(item["stale"]),
                "kind": item["kind"],
                "review_state": item["review_state"],
                "created_at": item["created_at"],
            }
            for item in investigations
        ],
        "discovery_links": [
            {
                "link_id": item["link_id"],
                "question_id": item["question_id"],
                "discovery_key": item["item"]["discovery_key"],
                "state": item["state"],
                "invalidated_cause": item["invalidated_cause"],
                "invalidated_rights_source_id": item["invalidated_rights_source_id"],
            }
            for item in discovery_links
        ],
        "inventory_assertions": [
            {
                "inventory_assertion_id": item["id"],
                "asset_id": item["asset_id"],
                "source_version_id": item["source_version_id"],
                "asserted_by": item["asserted_by"],
                "state": item["state"],
            }
            for item in state["biological_inventory_assertions"]
        ],
    }

    home = {
        "cover": {
            "fictional": True,
            "marking": MARKING,
            "scope": SCOPE,
            "case_id": state["case"]["case_id"],
            "label": state["case"]["label"],
            "generated_from": dict(BUILDERS),
            "report_position": _report_position(store, case_id),
            "changes_anchor": dict(changes["anchor"]),
            "timeline_as_of": dict(timeline["as_of"]),
        },
        "mission": mission,
        "timeline": timeline,
        "changes": changes,
        "attention": {
            "source": "mission",
            "builder": BUILDERS["mission"],
            "next_actions": mission["next_actions"],
            "material_changes": mission["material_changes"],
        },
        "goals": {
            "available": False,
            "reason": ("This build has no patient-goals builder and no goals "
                       "ledger table; no goals are shown and none are inferred."),
        },
        "follow_ups": {
            "projection": "option_view_ledger_read",
            "source": BUILDERS["options"],
            "preparation_tasks": follow_ups,
        },
        "review_state": review_state,
        "stage": {
            "source": "mission",
            "builder": BUILDERS["mission"],
            "workflow_status": mission["workflow_status"],
            "note": ("Workflow/review state only (awaiting_sources, "
                     "ready_to_define_question, investigation_in_progress, "
                     "review_required, reviewed_in_demo). This build performs "
                     "no clinical staging and reports no disease state."),
        },
        "limitations": list(LIMITATIONS),
    }
    return _frozen(home)
