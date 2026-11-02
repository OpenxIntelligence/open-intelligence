"""Native Composer preflight over the EXISTING fictional case and evidence ledger.

This does not implement a second patient world model, chat history, research
index, agent scheduler, clinical recommendation, or trusted authorization.
It reads the SAME current source/assessment state as the bounded investigation
engine, attaches exact provenance and a snapshot fingerprint, and reuses the
existing Patient Mission projection. No external network or model call here.
"""
from __future__ import annotations

import hashlib
import json
import re

from .investigation import TEMPLATES
from .mission import build_patient_mission
from .store import CaseStore, InvalidInput

CONTEXT_VERSION = "composer-context-v1"
QUESTION_KEYS = ("id", "question", "state")
SOURCE_KEYS = ("id", "document_id", "version", "sha256", "kind",
               "event_date", "issued_at", "received_at", "specimen_id")
ASSERTION_KEYS = ("id", "source_version_id", "finding_key", "certainty",
                  "quote", "source_line")
ASSESSMENT_KEYS = ("id", "evidence_version_id", "relation", "applicability",
                   "rationale", "sha256")


def _fields(row: dict, keys: tuple[str, ...]) -> dict:
    """Select explicit public fields; never export an entire DB row."""
    return {key: row[key] for key in keys}


def _fingerprint(case_id: str, question: dict, sources: list[dict],
                 assertions: list[dict], assessments: list[dict]) -> str:
    payload = {
        "version": CONTEXT_VERSION,
        "case_id": case_id,
        "question": _fields(question, QUESTION_KEYS),
        "sources": sorted((_fields(x, SOURCE_KEYS) for x in sources),
                          key=lambda row: row["id"]),
        "assertions": sorted((_fields(x, ASSERTION_KEYS) for x in assertions),
                             key=lambda row: row["id"]),
        "assessments": sorted((_fields(x, ASSESSMENT_KEYS) for x in assessments),
                              key=lambda row: row["id"]),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _snapshot_rows_from_state(state: dict, question_id: int) -> tuple:
    question = next((x for x in state["questions"] if x["id"] == question_id), None)
    if question is None:
        raise InvalidInput("Composer question is not in this case")
    sources = [x for x in state["sources"] if x["state"] == "current"]
    assertions = list(state["assertions"])
    # The case state includes evidence from the shared synthetic evidence
    # register. Only current, explicitly original-synthetic evidence which was
    # assessed for this case/question may enter the Composer context.
    eligible = {e["id"] for e in state["evidence"]
                if e["state"] == "current" and e["rights"] == "original-synthetic"}
    assessments = [
        x for x in state["evidence_assessments"]
        if x["question_id"] == question_id
        and x["evidence_version_id"] in eligible
        and x["evidence_state"] == "current"
    ]
    return question, sources, assertions, assessments


def composer_context_fingerprint(store: CaseStore, case_id: str,
                                 question_id: int) -> str:
    """Check exact current query/source/assessments, usable inside a write lock.

    A fingerprint is NOT a credential. It binds a proposed run to the same
    source versions and human-entered evidence assessments available to its
    existing investigation prompt at execution time.
    """
    store._case(case_id)
    if type(question_id) is not int or question_id < 1:
        raise InvalidInput("Composer question ID must be a positive integer")
    question = store.db.execute(
        "SELECT id,question,state FROM questions WHERE id=? AND case_id=?",
        (question_id, case_id)).fetchone()
    if question is None:
        raise InvalidInput("Composer question is not in this case")
    sources = store.db.execute(
        """SELECT id,document_id,version,sha256,kind,event_date,issued_at,
                  received_at,specimen_id FROM source_versions
           WHERE case_id=? AND state='current' ORDER BY id""",
        (case_id,)).fetchall()
    assertions = store.db.execute(
        """SELECT a.id,a.source_version_id,a.finding_key,a.certainty,
                  a.quote,a.source_line
           FROM assertions a JOIN source_versions s ON s.id=a.source_version_id
           WHERE a.case_id=? AND s.case_id=? AND s.state='current' ORDER BY a.id""",
        (case_id, case_id)).fetchall()
    assessments = store.db.execute(
        """SELECT a.id,a.evidence_version_id,a.relation,a.applicability,
                  a.rationale,v.sha256
           FROM evidence_assessments a JOIN evidence_versions v
             ON v.id=a.evidence_version_id
           WHERE a.case_id=? AND a.question_id=?
             AND v.state='current' AND v.rights='original-synthetic'
           ORDER BY a.id""",
        (case_id, question_id)).fetchall()
    return _fingerprint(
        case_id, dict(question), [dict(row) for row in sources],
        [dict(row) for row in assertions], [dict(row) for row in assessments])


def build_composer_context(store: CaseStore, case_id: str,
                           question_id: int) -> dict:
    """Prepare a source-bound preview within the existing investigation form.

    State snapshots are read consistently by CaseStore.state(). If an
    amendment raced the subsequent fingerprint calculation, retry rather than
    presenting a preview with a mismatching token. No database writes.
    """
    if type(question_id) is not int or question_id < 1:
        raise InvalidInput("Composer question ID must be a positive integer")
    for _ in range(3):
        state = store.state(case_id)
        q, sources, assertions, assessments = _snapshot_rows_from_state(
            state, question_id)
        token = _fingerprint(case_id, q, sources, assertions, assessments)
        if token == composer_context_fingerprint(store, case_id, question_id):
            break
    else:
        raise InvalidInput("Composer source context changed during preview; retry")

    source_by_id = {x["id"]: x for x in sources}
    anchors = []
    for a in assertions[:100]:
        s = source_by_id.get(a["source_version_id"])
        if not s:
            continue
        anchors.append({
            "source_version_id": a["source_version_id"],
            "document_id": s["document_id"],
            "version": s["version"],
            "source_line": a["source_line"],
            "finding_key": a["finding_key"],
            "reported_state": a["certainty"],
            "statement": a["quote"],
            "specimen_id": s["specimen_id"],
        })

    mission = build_patient_mission(state)
    cutoffs = [s["received_at"] for s in sources if s.get("received_at")]
    selected = mission["what_remains_unresolved"]
    return {
        "context_kind": "synthetic_source_bound_read_only",
        "case_id": case_id,
        "case_label": state["case"]["label"],
        "question_id": question_id,
        "question": q["question"],
        "question_state": q["state"],
        "fingerprint": token,
        "data_cutoff": max(cutoffs) if cutoffs else None,
        "current_sources": [
            dict(_fields(s, SOURCE_KEYS), state="current") for s in sources[:100]],
        "source_anchors": anchors,
        "source_count": len(sources),
        "source_preview_limit": 100,
        "evidence_assessments": [
            {"id": x["id"], "evidence_version_id": x["evidence_version_id"],
             "relation": x["relation"], "applicability": x["applicability"],
             "rationale": x["rationale"], "statement": x["statement"],
             "statement_line": x["statement_line"], "sha256": x["sha256"]}
            for x in assessments[:50]],
        "evidence_assessment_count": len(assessments),
        "mission": {
            "case": mission["case"],
            "workflow_status": mission["workflow_status"],
            "where_am_i": mission["where_am_i"],
            "unresolved": {
                "questions": selected["questions"],
                "stale_investigation_ids": selected["stale_investigation_ids"],
                "quarantined_delivery_ids": selected["quarantined_delivery_ids"],
            },
        },
        "templates": [
            {"id": template_id, "description": description}
            for template_id, description in TEMPLATES.items()
        ],
        "tool_status": {
            "local_source_review": "available",
            "recorded_replay": "available",
            "model_api_live": "operator_opt_in_only",
            "external_guideline_search": "unavailable",
            "live_clinical_trials": "unavailable",
            "analysis_execution": "unavailable",
            "clinical_authorization": "not_verified",
        },
        "ready_state": "evidence_available" if anchors or assessments
                       else "requires_source_review",
        "disclaimer": (
            "Fictional synthetic source context only. These are authored "
            "source statements, not verified patient facts or medical advice. "
            "Evidence is not selected for relevance by a clinician. "
            "No live standards-of-care retrieval, patient-specific diagnosis, "
            "trial eligibility, clinical approval or real patient access."
        ),
    }
