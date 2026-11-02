"""Read-only, source-derived synthetic Patient World Model projection.

This is a narrow engineering view of the EXISTING CaseStore snapshot, not a
second clinical record, patient identity, semantic reasoning engine or inferred
diagnosis. No model calls, external retrieval, writes or patient permissions.
Only expose this in the existing loopback-only fictional research demo.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .store import InvalidInput, STATES

UNRESOLVED = frozenset({
    "pending", "indeterminate", "not-reported", "not-assessed", "conflicting"
})


def _positive(value: Any, name: str) -> int:
    if type(value) is not int or value < 1:
        raise InvalidInput(f"{name} must be a positive integer")
    return value


def _source_view(item: dict) -> dict:
    return {
        "source_version_id": item["id"],
        "document_id": item["document_id"],
        "version": item["version"],
        "source_sha256": item["sha256"],
        "kind": item["kind"],
        "specimen_id": item["specimen_id"],
        "event_date": item["event_date"],
        "issued_at": item["issued_at"],
        "received_at": item["received_at"],
        "state": item["state"],
        "supersedes_source_id": item["supersedes_id"],
    }


def synthetic_world_model(state: dict, expected_case_id: str) -> dict:
    """Project exactly one canonical CaseStore.state() snapshot.

    Source assertions are observations *reported* in authored fictional
    records, not independent biological facts. A conflict is narrowly a
    source-level disagreement for the identical non-null specimen, reported
    event date and finding key; temporal changes and unknown specimen links
    are never fused or silently adjudicated.

    The caller must perform access enforcement. This function only checks
    the scope of the already-authorized, synthetic case snapshot.
    """
    if not isinstance(state, dict) or not isinstance(state.get("case"), dict):
        raise InvalidInput("CaseStore.state snapshot required")
    case_id = state["case"].get("case_id")
    if (not isinstance(expected_case_id, str) or not expected_case_id
            or case_id != expected_case_id):
        raise InvalidInput("Patient/case snapshot scope mismatch")
    if not isinstance(state.get("sources"), list) or not isinstance(state.get("assertions"), list):
        raise InvalidInput("Case source and assertion lists required")

    by_id: dict[int, dict] = {}
    for source in state["sources"]:
        if not isinstance(source, dict):
            raise InvalidInput("Malformed original source reference")
        source_id = _positive(source.get("id"), "Source version ID")
        if source_id in by_id or source.get("state") not in {"current", "superseded"}:
            raise InvalidInput("Duplicate or unsupported source version")
        by_id[source_id] = source

    current = sorted(
        (_source_view(s) for s in by_id.values() if s["state"] == "current"),
        key=lambda s: (s["event_date"], s["issued_at"], s["received_at"],
                       s["document_id"], s["version"], s["source_version_id"]),
    )
    history = sorted(
        (_source_view(s) for s in by_id.values() if s["state"] == "superseded"),
        key=lambda s: (s["document_id"], s["version"], s["source_version_id"]),
    )
    observed = []
    seen_ids = set()
    for assertion in state["assertions"]:
        if not isinstance(assertion, dict):
            raise InvalidInput("Malformed original finding")
        aid = _positive(assertion.get("id"), "Assertion ID")
        sid = _positive(assertion.get("source_version_id"), "Assertion source ID")
        line = _positive(assertion.get("source_line"), "Exact assertion line")
        if aid in seen_ids:
            raise InvalidInput("Duplicate finding identity")
        seen_ids.add(aid)
        source = by_id.get(sid)
        if source is None or source["state"] != "current":
            raise InvalidInput("Assertion references absent or superseded source")
        reported_state = assertion.get("certainty")
        if reported_state not in STATES:
            raise InvalidInput("Unrecognized reported finding state")
        observation = {
            "assertion_id": aid,
            "finding_key": assertion["finding_key"],
            "reported_state": reported_state,
            "source_statement": assertion["quote"],
            "source_line": line,
            "source_version_id": sid,
            "document_id": source["document_id"],
            "document_version": source["version"],
            "source_sha256": source["sha256"],
            "source_kind": source["kind"],
            "specimen_id": source["specimen_id"],
            "event_date": source["event_date"],
            "issued_at": source["issued_at"],
            "received_at": source["received_at"],
            "review_state": "not_established",
            "clinical_meaning": None,
        }
        observed.append(observation)
    observed.sort(key=lambda s: (s["event_date"], s["document_id"],
                                 s["document_version"], s["source_line"], s["assertion_id"]))

    # Do not infer that two absent specimen identifiers refer to one sample.
    # Likewise, the same specimen's status across different times can change:
    # a temporal difference alone is not a source contradiction.
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for finding in observed:
        if finding["specimen_id"] is not None:
            grouped[(finding["specimen_id"], finding["event_date"],
                     finding["finding_key"])].append(finding)
    conflicts = []
    for (specimen_id, event_date, finding_key), findings in sorted(grouped.items()):
        reported_states = {f["reported_state"] for f in findings}
        if not {"reported", "negative"} <= reported_states:
            continue
        conflicts.append({
            "specimen_id": specimen_id,
            "event_date": event_date,
            "finding_key": finding_key,
            "status": "unresolved_source_disagreement",
            "reported_states": sorted(reported_states),
            "observation_refs": [
                {"assertion_id": f["assertion_id"],
                 "source_version_id": f["source_version_id"],
                 "source_line": f["source_line"]}
                for f in findings
            ],
            "clinical_interpretation": "not_performed",
        })

    questions = state.get("questions", [])
    snapshots = state.get("snapshots", [])
    if not isinstance(questions, list) or not isinstance(snapshots, list):
        raise InvalidInput("Question/review snapshots required")
    review_needed = {
        "open_question_ids": sorted(
            _positive(q["id"], "Question ID") for q in questions if q["state"] == "open"
        ),
        "draft_snapshot_ids": sorted(
            _positive(s["id"], "Snapshot ID") for s in snapshots if s["state"] == "draft"
        ),
        "stale_snapshot_ids": sorted(
            _positive(s["id"], "Snapshot ID") for s in snapshots if s["state"] == "stale"
        ),
    }
    events = state.get("events", [])
    latest = max(events, key=lambda e: e["id"]) if events else None
    return {
        "contract": "oi.synthetic-world-model/1",
        "synthetic": True,
        "case_id": case_id,
        "scope": "fictional_case_only_not_a_verified_patient",
        "authority": "source_report_only_unreviewed",
        "clinical_interpretation": "not_generated",
        "as_of_ledger": (
            {"event_id": latest["id"], "recorded_at": latest["occurred_at"]}
            if latest is not None else {"event_id": None, "recorded_at": None}
        ),
        "summary": {
            "current_sources": len(current),
            "superseded_sources": len(history),
            "current_observations": len(observed),
            "unresolved_observations": sum(f["reported_state"] in UNRESOLVED for f in observed),
            "source_disagreements": len(conflicts),
        },
        "current_sources": current,
        "history": history,
        "observations": observed,
        "unresolved": [f for f in observed if f["reported_state"] in UNRESOLVED],
        "conflicts": conflicts,
        "review_needed": review_needed,
        "limitations": [
            "Source-authored fictional observations only; no general document extraction.",
            "No verified patient identity, clinical review, consent or PHI authorization.",
            "No diagnosis, progression, treatment response, trial eligibility or medical recommendation.",
            "No genome build or assay metadata can be inferred when source is silent.",
            "Event cutoff identifies a ledger receipt; historical as-of queries are not implemented.",
            "External literature evidence and authorizations are not included in this case-only projection.",
        ],
    }
