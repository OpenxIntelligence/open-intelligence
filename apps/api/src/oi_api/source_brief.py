"""Deterministic source-linked brief for one saved, current fictional question.

Selectively preserves the source-brief renderer without its competing source
reader. The existing question/source owners supply validated context and retain
authorization, transaction and receipt ownership. No model or review is run.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from open_intelligence.patient_registry import PatientRegistryError

from .composer_preflight import SOURCE_SNAPSHOT_CONTRACT
from .source_anchor import oncology_lines, selected_observation_anchor

MAX_ENVELOPE_BYTES = 65_536


def check_brief_size(envelope: dict) -> None:
    """Refuse an oversized complete JSON response; never truncate its evidence."""
    encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_ENVELOPE_BYTES:
        raise PatientRegistryError("Source brief exceeds bounded response size")


def render_source_brief(world: dict, question: dict, selected_source: dict, *,
                        prepared_at: datetime | str) -> dict:
    """Render a current saved question and literal canonical source statements."""
    if (world.get("contract") != SOURCE_SNAPSHOT_CONTRACT
            or world.get("synthetic") is not True
            or world.get("authority") != "source_report_only_unreviewed"
            or world.get("clinical_interpretation") is not False
            or question.get("source_snapshot_contract") != SOURCE_SNAPSHOT_CONTRACT
            or question.get("patient_id") != world.get("patient_id")
            or question.get("case_id") != world.get("case_id")
            or question.get("source_snapshot_sha256") != world.get("snapshot_fingerprint")
            or question.get("source_context_state") != "current_unreviewed_question"
            or question.get("human_review_state") != "not_submitted"
            or question.get("clinical_approval") is not False
            or question.get("model_executed") is not False):
        raise PatientRegistryError("Unqualified source question for brief")
    if ((selected_source.get("source_id"), selected_source.get("line"),
         selected_source.get("sha256"), selected_source.get("version")) !=
            (question.get("source_id"), question.get("source_line"),
             question.get("source_sha256"), question.get("source_version"))):
        raise PatientRegistryError("Question source anchor does not match brief")
    matching = [item for item in world["observations"]
                if item["source_id"] == question["source_id"]
                and item["source_line"] == question["source_line"]]
    if len(matching) != 1:
        raise PatientRegistryError("Question source anchor is unavailable")
    if selected_source != selected_observation_anchor(matching[0]):
        raise PatientRegistryError("Brief source statement does not match canonical context")
    try:
        when = (datetime.fromisoformat(prepared_at.replace("Z", "+00:00"))
                if isinstance(prepared_at, str) else prepared_at)
        if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
            raise ValueError()
        timestamp = when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, AttributeError):
        raise PatientRegistryError("Invalid preparation time") from None

    lines = [
        "Open Intelligence — Source-linked question brief",
        "INDEPENDENTLY FICTIONAL DEVELOPMENT DATA ONLY", "",
        "Source statements only. Clinical review: not established.",
        "Human review: not_submitted. Clinical approval: false.",
        "Model executed: false. Biomedical evidence included: false.",
        "No diagnosis, treatment recommendation, AI answer or medical approval is provided.",
        "This brief does not establish a complete medical record.",
        "It is a snapshot, not a live view. Refresh sources before subsequent use.",
        "An exported copy cannot be revoked or silently updated.", "",
        f'Patient ID: {world["patient_id"]}', f'Source case: {world["case_id"]}',
        f"Prepared at: {timestamp}",
        f"Source snapshot contract: {SOURCE_SNAPSHOT_CONTRACT}",
        f'Source snapshot SHA-256: {world["snapshot_fingerprint"]}',
        "", "SAVED QUESTION", f'Question ID: {question["question_id"]}',
        f'Question saved at: {question["created_at"]}',
        f'Preflight SHA-256: {question["preflight_sha256"]}',
        "Exact saved question (literal text):", question["question"],
        "", "SELECTED ORIGINAL SOURCE ANCHOR",
        f'Document: {selected_source["document_id"]}@{selected_source["version"]}',
        f'Original source ID: {selected_source["source_id"]}',
        f'Original SHA-256: {selected_source["sha256"]}',
        f'Original line: {selected_source["line"]}',
        f'Finding key: {selected_source["finding_key"]}',
        f'Source-reported state: {selected_source["reported_state"]}',
        "Exact source statement (literal text):", selected_source["statement"],
        *oncology_lines(selected_source),
        "", "CURRENT SOURCE-REPORTED OBSERVATIONS",
    ]
    for source in world["current_sources"]:
        lines += ["", f'Document: {source["document_id"]}@{source["version"]}',
                  f'Original source ID: {source["source_id"]}',
                  f'Original SHA-256: {source["sha256"]}', f'Kind: {source["kind"]}',
                  f'Specimen: {source["specimen_id"] or "not recorded"}',
                  f'Event date: {source["event_date"]}', f'Issued date: {source["issued_at"]}',
                  f'Received at: {source["received_at"]}']
        for finding in world["observations"]:
            if finding["source_id"] == source["source_id"]:
                lines += ["", f'Finding key: {finding["finding_key"]}',
                          f'Source-reported state: {finding["reported_state"]}',
                          f'Original line: {finding["source_line"]}',
                          "Exact source statement (literal text):", finding["source_statement"]]
                lines.extend(oncology_lines(finding))
    by_anchor = {(item["source_id"], item["source_line"]): item
                 for item in world["observations"]}
    lines += ["", "UNRESOLVED SOURCE STATEMENTS"]
    if not world["unresolved_refs"]:
        lines.append("No unresolved labels in this bounded projection. This is not clinical clearance.")
    for ref in world["unresolved_refs"]:
        finding = by_anchor[(ref["source_id"], ref["source_line"])]
        lines.append(f'{finding["source_id"]} line {finding["source_line"]}: '
                     f'{finding["finding_key"]} — {finding["reported_state"]}')
    lines += ["", "SOURCE-LABEL DISAGREEMENTS"]
    if not world["conflicts"]:
        lines.append("None detected by the limited same-specimen/date/key rule; not independent adjudication.")
    for conflict in world["conflicts"]:
        first_ref = conflict["source_refs"][0]
        finding = by_anchor[(first_ref["source_id"], first_ref["source_line"])]
        lines += [f'{conflict["finding_key"]} / {conflict["specimen_id"]} / {conflict["event_date"]}',
                  *oncology_lines(finding),
                  "Source labels: " + " / ".join(conflict["reported_states"]),
                  "Clinical interpretation: not performed."]
        lines.extend(f'{ref["source_id"]} line {ref["source_line"]}'
                     for ref in conflict["source_refs"])
    lines += ["", "HISTORICAL SOURCE VERSIONS",
              "Prior originals are preserved, not substituted for current findings."]
    if not world["history"]:
        lines.append("No superseded versions in this snapshot.")
    for source in world["history"]:
        lines += [f'{source["document_id"]}@{source["version"]} / {source["source_id"]}',
                  f'State: {source["state"]}; original SHA-256: {source["sha256"]}',
                  f'Event: {source["event_date"]}; issued: {source["issued_at"]}; received: {source["received_at"]}']
    lines += ["", "LIMITATIONS", *world["limitations"],
              "No external publications or clinical guidelines are included.",
              "Source access is audited; no question, clinical review or verified external action is changed.", ""]
    body = "\n".join(lines)
    envelope = {
        "contract": "oi.synthetic-source-brief/2", "synthetic": True,
        "patient_id": world["patient_id"], "case_id": world["case_id"],
        "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
        "source_snapshot_sha256": world["snapshot_fingerprint"],
        "access_receipt_id": world["access_receipt_id"],
        "question": dict(question), "selected_source": dict(selected_source),
        "prepared_at": timestamp, "media_type": "text/plain;charset=utf-8",
        "body": body, "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "clinical_approval": False, "model_executed": False,
        "biomedical_evidence_included": False,
    }
    check_brief_size(envelope)
    return envelope
