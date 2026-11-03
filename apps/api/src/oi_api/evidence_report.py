"""Pure human-only evidence rights and provenance-preserving report rendering.

Uses the shared rights vocabulary. No publisher verification, model eligibility,
clinical appraisal, network access or alternate patient/source ownership.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata

from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.rights import permitted, validate_content_item

MAX_RESPONSE_BYTES = 524288
MAX_BODY_BYTES = 131072


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def human_content_allowed(original: dict, current: dict, content_item: str, *,
                          withdrawn: bool = False, export: bool = False) -> bool:
    """Intersection of immutable referenced and current case-family declarations.

    Always check the original declared item in both maps. Display rights are not
    ML rights; this contract never creates model-eligible input.
    """
    validate_content_item(content_item)
    uses = ("store", "display", "redistribute") if export else ("store", "display")
    return not withdrawn and all(permitted(rights, item, use)
        for rights in (original, current) for item in ("metadata", content_item) for use in uses)


def quote_offset(statement: str, quote: str) -> int:
    if (type(quote) is not str or not 1 <= len(quote) <= 400
            or statement.find(quote) < 0
            or statement.find(quote, statement.find(quote) + 1) >= 0):
        raise PatientRegistryError("Quote must be a unique literal 1-400 character statement passage")
    return statement.index(quote)


def visible_line(value: str, name: str = "Rationale") -> str:
    if (type(value) is not str or value != value.strip() or not 10 <= len(value) <= 600
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value)):
        raise PatientRegistryError(f"{name} must be a visible 10-600 character line")
    return value


def packet_hash(packet: dict) -> str:
    return canonical_hash({key: value for key, value in packet.items()
                           if key not in {"packet_sha256", "access_receipt_id", "reports"}})


def _quoted(value: object) -> str:
    # Same literal-rendering policy as the reference governed report. JSON
    # quotes preserve whitespace; invisible/directional controls become visible.
    literal = json.dumps(str(value), ensure_ascii=False)
    return "".join(f"\\u{ord(c):04x}" if unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"}
                   else c for c in literal)


def render_evidence_report(snapshot: dict, *, renderer: str = "oi.h1-evidence-text/2") -> str:
    if renderer not in {"oi.h1-evidence-text/1", "oi.h1-evidence-text/2", "oi.h1-evidence-text/3"}:
        raise PatientRegistryError("Unknown evidence report renderer")
    from .authored_evidence_contracts import checked_report_snapshot
    try:
        value = checked_report_snapshot(snapshot)
        if ('manual_passages' in value) != (renderer == 'oi.h1-evidence-text/3'):
            raise ValueError('Report renderer does not match snapshot version')
    except (ValueError, TypeError) as exc:
        raise PatientRegistryError("Report snapshot provenance is invalid") from exc
    question, source = value["question"], value["selected_source"]
    lines = [
        "OPEN INTELLIGENCE — FICTIONAL EVIDENCE COMPARISON",
        "Immutable human-authored preparation; clinical review not performed.",
        "No model executed. Publisher rights are declared fictional permissions, not independently verified clearance.",
        "Selected passages are not an exhaustive literature search. Absence here is not absence of counterevidence.",
        "",
        f"Prepared: {value['prepared_at']} | Unverified actor label: {_quoted(value['actor_label'])}",
        f"Patient: {question['patient_id']} | Case: {question['case_id']}",
        f"Question: {question['question_id']} | {_quoted(question['question'])}",
        f"Source snapshot: {question['source_snapshot_contract']} {question['source_snapshot_sha256']}",
        f"Preflight: {question['preflight_sha256']}",
        "",
        "PATIENT SOURCE — REPORTED OBSERVATION, NOT CLINICAL INTERPRETATION",
        f"Original: {source['source_id']} | Document {source['document_id']} v{source['version']} | line {source['line']}",
        f"Original SHA-256: {source['sha256']}",
        f"Event: {source['event_date']} | Issued: {source['issued_at']} | Specimen: {_quoted(source['specimen_id'] or 'not specified')}",
        f"Source-reported state: {source['reported_state']}",
        f"Literal source statement: {_quoted(source['statement'])}",
    ]
    if renderer == 'oi.h1-evidence-text/3':
        context=value['manual_passages']
        lines.extend(['','ADDITIONAL MANUAL RECORD CONTEXT — USER-SELECTED, CLINICAL REVIEW NOT PERFORMED',
            'These passages are supplementary record context. The comparisons below concern the primary structured observation.',
            f"Context revision: {context['revision_id']} | {context['revision']} | SHA-256: {context['context_sha256']}",
            f"Attached by unverified actor label: {_quoted(context['attached_by'])} | {context['attached_at']}"])
        if not context['passages']:
            lines.append('The user explicitly selected no additional manual passages in this revision.')
        for passage in context['passages']:
            a=passage['anchor']
            lines.extend([
                f"Original: {a['source_id']} | Document {a['document_id']} v{a['source_version']} | line {a['line']} | physical page {a['page'] if a['page'] is not None else 'not applicable'}",
                f"Original SHA-256: {a['original_sha256']} | Extraction: {a['extraction_method']} | SHA-256: {a['extraction_sha256'] or 'not applicable'}",
                f"Annotation: {a['annotation_revision_id']} | revision {a['annotation_revision']} | key {a['selection_key']} | review SHA-256 {a['review_sha256']}",
                f"User-selected state: {a['selected_state']} | Unverified selecting actor: {_quoted(a['selected_by'])} | {a['selected_at']}",
                f"Exact manual quotation: {_quoted(a['quote'])}",
                f"Anchor SHA-256: {passage['anchor_sha256']}",
            ])
    groups = (("supports", "PROPOSED SUPPORT"), ("contradicts", "PROPOSED CONTRADICTION"),
              ("context", "PROPOSED CONTEXT"), ("unknown", "PROPOSED UNKNOWN RELATION"))
    for relation, title in groups:
        rows = [row for row in value["comparisons"] if row["assessment"]["relation"] == relation]
        lines.extend(["", f"{title} ({len(rows)})"])
        if not rows:
            lines.append("No selected comparison in this group; this is not a scientific conclusion.")
        for row in rows:
            assessment, evidence = row["assessment"], row["evidence"]
            lines.extend([
                f"Assessment: {assessment['assessment_id']} | human-selected relation: {relation}",
                f"Human-selected applicability: {assessment['applicability']} | clinical review not performed",
                f"Unverified author: {_quoted(assessment['actor_label'])} | recorded: {assessment['created_at']}",
                f"Evidence: {evidence['evidence_key']} v{evidence['version']} | {evidence['evidence_id']}",
                f"Title: {_quoted(evidence['title'])} | Issued: {evidence['issued_at']}",
                f"Original evidence SHA-256: {evidence['sha256']}",
                f"Declared content item: {evidence['content_item']} | rights SHA-256: {evidence['rights_sha256']}",
                f"Statement line: {evidence['statement_line']} | quote offset: {assessment['quote_start']} Unicode code points",
                f"Exact quotation: {_quoted(assessment['quote'])}",
                f"Human-authored rationale: {_quoted(assessment['rationale'])}",
            ])
            if renderer in {"oi.h1-evidence-text/2", "oi.h1-evidence-text/3"}:
                lines.append("Frozen declared permissions (not independently verified):")
                for item in ("metadata", evidence["content_item"]):
                    for use in ("store", "display", "redistribute", "ml_use"):
                        lines.append(f"{item}/{use}: {evidence['permissions'][item][use]}")
    lines.extend(["", "This preparation is historical from the moment recorded. Reopen through the authorized application to check current source, evidence and rights status.", ""])
    body = "\n".join(lines)
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise PatientRegistryError("Evidence report exceeds bounded body size")
    return body
