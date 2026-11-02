"""Read-only Patient Mission projection for the synthetic engineering demo.

The projection summarizes workflow state already present in ``CaseStore``.
It does not add facts, interpret medicine, persist a second record, or make a
clinical recommendation.
"""

from __future__ import annotations

import json

UNRESOLVED_SOURCE_STATES = frozenset({
    "pending",
    "indeterminate",
    "not-reported",
    "not-assessed",
    "conflicting",
})

GUARDRAILS = [
    "Synthetic workflow orientation only; this is not a diagnosis or treatment recommendation.",
    "Every displayed statement comes from an authored synthetic source version; no AI clinical inference is performed.",
    "Review acknowledgments in this demo do not establish clinician identity, clinical approval, or patient applicability.",
]


def _safe_event_details(raw: object) -> dict:
    """Return a JSON object or an empty mapping; never infer damaged details."""
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _known_statement(assertion: dict) -> dict:
    return {
        "finding_key": assertion["finding_key"],
        "state": assertion["certainty"],
        "statement": assertion["quote"],
        "source_version_id": assertion["source_version_id"],
        "source_line": assertion["source_line"],
    }


def _material_changes(events: list[dict]) -> list[dict]:
    changes: list[dict] = []
    for event in events:
        details = _safe_event_details(event.get("details"))
        if not details:
            continue
        kind = event.get("kind")
        change_kind: str | None = None
        summary: str | None = None
        if kind == "source_imported" and details.get("amends_id"):
            document_id = details.get("document_id")
            version = details.get("version")
            amends_id = details.get("amends_id")
            invalidated = details.get("invalidated_snapshots")
            if not isinstance(document_id, str) or type(version) is not int or type(amends_id) is not int:
                continue
            invalidated = [item for item in invalidated if type(item) is int] if isinstance(invalidated, list) else []
            if invalidated:
                ids = ", ".join(str(item) for item in invalidated)
                effect = f"dependent investigation IDs {ids} were marked stale"
            else:
                effect = "no dependent investigations were marked stale"
            change_kind = "source_amended"
            summary = f"{document_id}@{version} replaced source version #{amends_id}; {effect}."
        elif kind == "evidence_invalidated":
            evidence_version_id = details.get("evidence_version_id")
            invalidated = details.get("invalidated_snapshots")
            reason = details.get("reason")
            if type(evidence_version_id) is not int or not isinstance(reason, str):
                continue
            invalidated = [item for item in invalidated if type(item) is int] if isinstance(invalidated, list) else []
            ids = ", ".join(str(item) for item in invalidated) or "none"
            change_kind = "evidence_invalidated"
            summary = (
                f"Synthetic evidence version #{evidence_version_id} changed because of {reason}; "
                f"dependent investigation IDs: {ids}."
            )
        elif kind == "source_quarantined":
            quarantine_id = details.get("quarantine_id")
            reason = details.get("reason")
            if type(quarantine_id) is not int or not isinstance(reason, str):
                continue
            change_kind = "source_quarantined"
            summary = f"Source delivery #{quarantine_id} was quarantined for {reason}."
        if change_kind and summary:
            changes.append({
                "event_id": event.get("id"),
                "kind": change_kind,
                "occurred_at": event.get("occurred_at"),
                "summary": summary,
            })
        if len(changes) == 5:
            break
    return changes


def _next_actions(state: dict, current_sources: list[dict], open_questions: list[dict],
                  stale_snapshots: list[dict], quarantines: list[dict]) -> list[dict]:
    actions: list[dict] = []
    if not current_sources:
        actions.append({
            "kind": "gather_source",
            "label": "Import an authorized synthetic source",
            "reason": "No current source document is available for this synthetic case.",
        })
    if quarantines:
        actions.append({
            "kind": "review_quarantine",
            "label": "Review quarantined deliveries",
            "reason": "A source declared a different subject and no assertions were imported from it.",
        })
    if stale_snapshots:
        ids = ", ".join(str(item["id"]) for item in stale_snapshots)
        actions.append({
            "kind": "reconcile_stale_investigation",
            "label": "Reconcile source changes with stale investigations",
            "reason": f"Investigation IDs {ids} depend on superseded or invalidated source material.",
        })
    if current_sources and not state.get("questions"):
        actions.append({
            "kind": "define_question",
            "label": "Record the next unresolved question",
            "reason": "Sources exist, but no durable investigation question has been registered.",
        })
    active_question_ids = {
        item.get("question_id") for item in state.get("snapshots", [])
        if item.get("state") in {"draft", "reviewed_in_demo"}
    }
    missing_investigations = [
        question for question in open_questions
        if question.get("id") not in active_question_ids
    ]
    if missing_investigations:
        ids = ", ".join(f"Q{item['id']}" for item in missing_investigations)
        actions.append({
            "kind": "create_investigation",
            "label": "Create a source-bound investigation draft",
            "reason": f"Open questions {ids} do not have a current investigation snapshot.",
        })
    drafts = [item for item in state.get("snapshots", []) if item.get("state") == "draft"]
    if drafts:
        ids = ", ".join(str(item["id"]) for item in drafts)
        actions.append({
            "kind": "acknowledge_demo_review",
            "label": "Review current investigation drafts",
            "reason": f"Investigation IDs {ids} remain drafts; acknowledgment is demo-only and non-clinical.",
        })
    if not actions:
        actions.append({
            "kind": "monitor_changes",
            "label": "Monitor for source or evidence changes",
            "reason": "No unresolved workflow action is currently represented in the synthetic ledger.",
        })
    return actions[:6]


def build_patient_mission(state: dict) -> dict:
    """Project a canonical case snapshot into a synthetic workflow mission view."""
    case = state["case"]
    current_sources = [item for item in state.get("sources", []) if item.get("state") == "current"]
    known = [_known_statement(item) for item in state.get("assertions", [])]
    open_questions = [item for item in state.get("questions", []) if item.get("state") == "open"]
    stale_snapshots = [item for item in state.get("snapshots", []) if item.get("state") == "stale"]
    drafts = [item for item in state.get("snapshots", []) if item.get("state") == "draft"]
    reviewed = [item for item in state.get("snapshots", []) if item.get("state") == "reviewed_in_demo"]
    quarantines = list(state.get("quarantines", []))

    if stale_snapshots or quarantines:
        workflow_status = "review_required"
    elif open_questions or drafts:
        workflow_status = "investigation_in_progress"
    elif reviewed:
        workflow_status = "reviewed_in_demo"
    elif current_sources:
        workflow_status = "ready_to_define_question"
    else:
        workflow_status = "awaiting_sources"

    source_dates = [item.get("event_date") for item in current_sources if isinstance(item.get("event_date"), str)]
    unresolved_findings = [
        item for item in known if item["state"] in UNRESOLVED_SOURCE_STATES
    ]

    return {
        "case": {
            "case_id": case["case_id"],
            "label": case["label"],
            "scope": "synthetic_workflow_only",
        },
        "workflow_status": workflow_status,
        "where_am_i": {
            "current_source_documents": len(current_sources),
            "reported_statements": len(known),
            "open_questions": len(open_questions),
            "stale_investigations": len(stale_snapshots),
            "quarantined_deliveries": len(quarantines),
            "latest_source_event_date": max(source_dates) if source_dates else None,
        },
        "what_we_know": known,
        "what_remains_unresolved": {
            "source_findings": unresolved_findings,
            "questions": [
                {
                    "question_id": item["id"],
                    "question": item["question"],
                    "created_at": item["created_at"],
                }
                for item in open_questions
            ],
            "stale_investigation_ids": [item["id"] for item in stale_snapshots],
            "quarantined_delivery_ids": [item["id"] for item in quarantines],
        },
        "material_changes": _material_changes(state.get("events", [])),
        "next_actions": _next_actions(
            state, current_sources, open_questions, stale_snapshots, quarantines
        ),
        "guardrails": list(GUARDRAILS),
    }
