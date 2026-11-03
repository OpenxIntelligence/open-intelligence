"""Read-only, source-derived synthetic Patient World Model projection.

This is a narrow engineering view of the EXISTING CaseStore snapshot, not a
second clinical record, patient identity, semantic reasoning engine or inferred
diagnosis. No model calls, external retrieval, writes or patient permissions.
Only expose this in the existing loopback-only fictional research demo.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import re
from typing import Any

from .document_intake import safe_filename
from .store import InvalidInput, STATES

UNRESOLVED = frozenset({
    "pending", "indeterminate", "not-reported", "not-assessed", "conflicting"
})
MAX_ID = 9223372036854775807
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MANUAL_FIELDS = ("classification_origin", "annotation_method", "clinical_review",
                  "transcription_review_sha256")
_PDF_IDENTITY = ("text_origin", "extraction_sha256")
_PDF_ANCHORS = ("source_page", "page_line", "page_text_sha256")
_PROVENANCE_FIELDS = _MANUAL_FIELDS + _PDF_IDENTITY + _PDF_ANCHORS


def _positive(value: Any, name: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise InvalidInput(f"{name} must be a positive signed 64-bit integer")
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise InvalidInput(f"{name} must be a SHA-256 digest")
    return value


def _check_case(item: dict, case_id: str) -> None:
    # CaseStore omits redundant scope on some source/assertion rows. If it is
    # supplied, never ignore an explicit contradictory case association.
    if "case_id" in item and item["case_id"] != case_id:
        raise InvalidInput("Patient/case row scope mismatch")


def _source_provenance(source: dict) -> dict:
    """Validate source-linked receipt association, without reading raw bytes."""
    if "document_intake" not in source:
        if any(field in source for field in _PROVENANCE_FIELDS):
            raise InvalidInput("Manual or PDF source provenance requires its intake receipt")
        return {}
    receipt = source["document_intake"]
    required = {"filename", "media_type", "extraction_method", "annotation_method",
                "manual_transcription_confirmed", "clinical_review", "review_sha256"}
    if not isinstance(receipt, dict) or not required <= receipt.keys():
        raise InvalidInput("Incomplete source intake provenance")
    filename = safe_filename(receipt["filename"])
    if (receipt["manual_transcription_confirmed"] is not True or
            receipt["clinical_review"] != "not_performed"):
        raise InvalidInput("Manual transcription must not imply clinical approval")
    reviewed = _hash(receipt["review_sha256"], "Transcription review")
    is_pdf = receipt["media_type"] == "application/pdf"
    if is_pdf:
        if (not filename.lower().endswith(".pdf") or receipt["extraction_method"] != "pypdf-text-v1" or
                receipt["annotation_method"] != "manual-exact-extraction-line-selection"):
            raise InvalidInput("Unsupported PDF source provenance")
    elif (receipt["media_type"] != "text/plain; charset=utf-8" or
          not filename.lower().endswith(".txt") or receipt["extraction_method"] != "utf8-plain-text-v1" or
          receipt["annotation_method"] != "manual-exact-line-selection" or
          "extraction_sha256" in receipt):
        raise InvalidInput("Unsupported text source provenance")
    expected = {"classification_origin": "user_selected",
                "annotation_method": receipt["annotation_method"],
                "clinical_review": "not_performed", "transcription_review_sha256": reviewed}
    if is_pdf:
        expected.update({"text_origin": "pdf_extraction",
                         "extraction_sha256": _hash(receipt.get("extraction_sha256"), "PDF extraction")})
    if any(source.get(field) != value for field, value in expected.items()):
        raise InvalidInput("Source provenance does not match its intake receipt")
    if any(field in source for field in _PDF_ANCHORS) or (not is_pdf and any(field in source for field in _PDF_IDENTITY)):
        raise InvalidInput("Unexpected source-level PDF anchor provenance")
    return expected


def _assertion_provenance(assertion: dict, source_provenance: dict, line: int) -> dict:
    """Preserve trusted frozen anchors and reject absent or mismatched origin.

    CaseStore already reads page anchors from the immutable rendition in the
    same transaction as this snapshot. This projection checks their shape and
    source receipt linkage; it does not independently reparse, re-hash, or
    reread PDF content. It cannot authenticate a consistently forged snapshot.
    """
    if not source_provenance:
        if any(field in assertion for field in _PROVENANCE_FIELDS):
            raise InvalidInput("Finding provenance has no associated source receipt")
        return {}
    if any(assertion.get(field) != value for field, value in source_provenance.items()):
        raise InvalidInput("Finding provenance does not match its source receipt")
    result = dict(source_provenance)
    if source_provenance.get("text_origin") == "pdf_extraction":
        page = _positive(assertion.get("source_page"), "Physical source page")
        page_line = _positive(assertion.get("page_line"), "Physical page line")
        if page > 20 or line > 512 or page_line > line:
            raise InvalidInput("PDF finding anchor exceeds the supported rendition bounds")
        result.update({"source_page": page, "page_line": page_line,
                       "page_text_sha256": _hash(assertion.get("page_text_sha256"), "Extracted page")})
    elif any(field in assertion for field in _PDF_IDENTITY + _PDF_ANCHORS):
        raise InvalidInput("Text finding cannot claim PDF extraction provenance")
    return result


def _source_view(item: dict, provenance: dict) -> dict:
    result = {
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
    if provenance:
        result.update(provenance)
        result["document_intake"] = deepcopy(item["document_intake"])
    return result


def _observation_ref(finding: dict) -> dict:
    result = {"assertion_id": finding["assertion_id"],
              "source_version_id": finding["source_version_id"],
              "source_line": finding["source_line"]}
    # Keep legacy authored references unchanged; manual classifications need
    # their complete origin so a status disagreement cannot imply adjudication.
    if "classification_origin" in finding:
        result["source_sha256"] = finding["source_sha256"]
        result.update({field: finding[field] for field in _PROVENANCE_FIELDS if field in finding})
    return result


def synthetic_world_model(state: dict, expected_case_id: str) -> dict:
    """Project exactly one canonical CaseStore.state() snapshot.

    Quotations remain literal source passages. Finding states are source-
    authored for the original report format, and user-selected classifications
    for reviewed document intake; neither is an independent biological fact.
    A conflict groups differing recorded statuses for an identical non-null
    specimen, reported event date and finding key. Manual classifications can
    disagree without establishing a clinical contradiction. Temporal changes
    and unknown specimen links are never fused or silently adjudicated.

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
    source_provenance: dict[int, dict] = {}
    for source in state["sources"]:
        if not isinstance(source, dict):
            raise InvalidInput("Malformed original source reference")
        source_id = _positive(source.get("id"), "Source version ID")
        required_source = {"document_id", "version", "sha256", "kind", "specimen_id",
                           "event_date", "issued_at", "received_at", "supersedes_id"}
        if not required_source <= source.keys():
            raise InvalidInput("Incomplete original source reference")
        for field in ("document_id", "kind", "event_date", "issued_at", "received_at"):
            if not isinstance(source[field], str) or not source[field]:
                raise InvalidInput("Malformed original source metadata")
        if source["specimen_id"] is not None and not isinstance(source["specimen_id"], str):
            raise InvalidInput("Malformed source specimen reference")
        _check_case(source, case_id)
        _positive(source["version"], "Document version")
        _hash(source["sha256"], "Original source")
        if source["supersedes_id"] is not None:
            _positive(source["supersedes_id"], "Superseded source ID")
        if (source_id in by_id or not isinstance(source.get("state"), str)
                or source["state"] not in {"current", "superseded"}):
            raise InvalidInput("Duplicate or unsupported source version")
        by_id[source_id] = source
        source_provenance[source_id] = _source_provenance(source)

    current = sorted(
        (_source_view(s, source_provenance[s["id"]]) for s in by_id.values() if s["state"] == "current"),
        key=lambda s: (s["event_date"], s["issued_at"], s["received_at"],
                       s["document_id"], s["version"], s["source_version_id"]),
    )
    history = sorted(
        (_source_view(s, source_provenance[s["id"]]) for s in by_id.values() if s["state"] == "superseded"),
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
        _check_case(assertion, case_id)
        if aid in seen_ids:
            raise InvalidInput("Duplicate finding identity")
        seen_ids.add(aid)
        source = by_id.get(sid)
        if source is None or source["state"] != "current":
            raise InvalidInput("Assertion references absent or superseded source")
        reported_state = assertion.get("certainty")
        if not isinstance(reported_state, str) or reported_state not in STATES:
            raise InvalidInput("Unrecognized reported finding state")
        if not isinstance(assertion.get("finding_key"), str) or not isinstance(assertion.get("quote"), str):
            raise InvalidInput("Finding key and literal quotation are required")
        provenance = _assertion_provenance(assertion, source_provenance[sid], line)
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
            **provenance,
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
            "observation_refs": [_observation_ref(f) for f in findings],
            "clinical_interpretation": "not_performed",
        })

    questions = state.get("questions", [])
    snapshots = state.get("snapshots", [])
    if not isinstance(questions, list) or not isinstance(snapshots, list):
        raise InvalidInput("Question/review snapshots required")
    for rows, allowed_states, label in ((questions, {"open", "addressed"}, "Question"),
                                        (snapshots, {"draft", "reviewed_in_demo", "stale"}, "Snapshot")):
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("state"), str)
                    or row["state"] not in allowed_states):
                raise InvalidInput(f"Unsupported {label.lower()} reference")
            _check_case(row, case_id)
            _positive(row.get("id"), f"{label} ID")
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
    if not isinstance(events, list):
        raise InvalidInput("Ledger event references required")
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("occurred_at"), str):
            raise InvalidInput("Malformed ledger event reference")
        _check_case(event, case_id)
        _positive(event.get("id"), "Event ID")
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
            ("Literal fictional source passages with user-selected classifications; transcription confirmation is not clinical adjudication."
             if any(source_provenance.values()) else
             "Source-authored fictional observations only; no general document extraction."),
            "No verified patient identity, clinical review, consent or PHI authorization.",
            "No diagnosis, progression, treatment response, trial eligibility or medical recommendation.",
            "No genome build or assay metadata can be inferred when source is silent.",
            "Event cutoff identifies a ledger receipt; historical as-of queries are not implemented.",
            "External literature evidence and authorizations are not included in this case-only projection.",
            *(["PDF anchors are copied from the trusted frozen CaseStore snapshot; this projection does not independently parse, re-hash or reread the original or rendition."]
              if any(p.get("text_origin") == "pdf_extraction" for p in source_provenance.values()) else []),
        ],
    }
