"""Read-only source-derived H1 Patient World Model projection over the *one* PG source owner.

This intentionally exposes less than the SQLite clinical World Model: no
questions, models, evidence assessments, clinician decisions or action ledger
have been migrated. Projection only; creates no source/patient/clinical rows.
No PHI, external data, AI inference, clinical interpretation or rights grant.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json

from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.store import STATES

UNRESOLVED = frozenset((
    "pending", "indeterminate", "not-reported", "not-assessed", "conflicting",
))


def project_source_world_model(index: dict, laboratory_observations: list[dict] | tuple = ()) -> dict:
    """Project a single transactionally read source index without a second ledger.

    The caller obtains the index from PostgresSourceVersions.list() after
    current patient/case/organization + source_read permission checks.
    A same-specimen/same-event-date reported-vs-negative disagreement is
    evidence of contradictory *source statements*, not a clinical diagnosis.
    """
    if (type(index) is not dict
            or index.get("contract") != "oi.synthetic-original-sources/1"
            or index.get("synthetic") is not True
            or index.get("clinical_interpretation") is not False
            or index.get("research_review_invalidation_integrated") is not False):
        raise PatientRegistryError("Unsupported original-source index for projection")
    patient_id = index.get("patient_id")
    case_id = index.get("case_id")
    receipt_id = index.get("access_receipt_id")
    if (type(receipt_id) is not str or not receipt_id.startswith("ACCESS-")
            or len(receipt_id) != 39):
        raise PatientRegistryError("Source read access receipt required")
    sources = index.get("sources")
    findings = index.get("source_reported_assertions")
    if (not isinstance(patient_id, str) or not patient_id
            or not isinstance(case_id, str) or not case_id
            or type(sources) is not list or type(findings) is not list):
        raise PatientRegistryError("Incomplete scoped original-source index")
    if len(sources) > 512 or len(findings) > 4096:
        raise PatientRegistryError("Source projection exceeds bounds")
    by_id: dict[str, dict] = {}
    by_document: dict[str, set[int]] = defaultdict(set)
    for source in sources:
        if type(source) is not dict:
            raise PatientRegistryError("Malformed source projection")
        source_id = source.get("source_id")
        document_id = source.get("document_id")
        version = source.get("version")
        if (not isinstance(source_id, str) or not source_id.startswith("SRC-")
                or source_id in by_id
                or not isinstance(document_id, str)
                or type(version) is not int or version < 1
                or version in by_document[document_id]
                or source.get("state") not in ("current", "superseded")):
            raise PatientRegistryError("Invalid source identity or version")
        by_document[document_id].add(version)
        by_id[source_id] = source
    current = sorted(
        (s for s in sources if s["state"] == "current"),
        key=lambda s: (s["event_date"], s["issued_at"], s["received_at"],
                       s["document_id"], s["version"], s["source_id"]),
    )
    history = sorted(
        (s for s in sources if s["state"] == "superseded"),
        key=lambda s: (s["document_id"], s["version"], s["source_id"]),
    )
    observations: list[dict] = []
    seen_line: set[tuple[str, int]] = set()
    for item in findings:
        if type(item) is not dict:
            raise PatientRegistryError("Malformed reported finding")
        source_id = item.get("source_id")
        source = by_id.get(source_id)
        line = item.get("source_line")
        state = item.get("reported_state")
        if (source is None or source["state"] != "current"
                or type(line) is not int or line < 1
                or (source_id, line) in seen_line
                or state not in STATES
                or item.get("clinical_review_state") != "not_established"):
            raise PatientRegistryError("Invalid source-reported observation")
        seen_line.add((source_id, line))
        observations.append({
            "source_id": source_id,
            "document_id": source["document_id"],
            "document_version": source["version"],
            "source_sha256": source["sha256"],
            "source_kind": source["kind"],
            "finding_key": item["finding_key"],
            "reported_state": state,
            "source_statement": item["source_statement"],
            "source_line": line,
            "specimen_id": source["specimen_id"],
            "event_date": source["event_date"],
            "issued_at": source["issued_at"],
            "review_state": "not_established",
            "clinical_meaning": None,
            **({"oncology": item["oncology"]} if "oncology" in item else {}),
        })
    observations.sort(
        key=lambda o: (o["event_date"], o["document_id"],
                       o["document_version"], o["source_line"], o["source_id"]),
    )
    if type(laboratory_observations) not in (list, tuple) or len(laboratory_observations) > 4096:
        raise PatientRegistryError("Invalid laboratory projection")
    laboratory = []
    seen_labs = set()
    required_lab = {
        "source_id","document_id","document_version","source_sha256",
        "observation_reference","loinc_code","effective_at","issued_at",
        "specimen_reference","specimen_type_text","specimen_collected_at",
        "report_reference","status","value_text","unit_code","absent_reason",
        "source_reported","review_state","clinical_review","clinical_meaning",
    }
    for item in laboratory_observations:
        if type(item) is not dict or set(item) != required_lab:
            raise PatientRegistryError("Invalid laboratory observation projection")
        source = by_id.get(item["source_id"])
        identity = (item["source_id"], item["observation_reference"])
        if (source is None or source["state"] != "current" or source["kind"] != "laboratory"
                or identity in seen_labs
                or (item["document_id"], item["document_version"], item["source_sha256"])
                   != (source["document_id"], source["version"], source["sha256"])
                or item["status"] not in ("reported_value", "reported_absent")
                or item["source_reported"] is not True
                or item["review_state"] != "not_established"
                or item["clinical_review"] != "not_performed"
                or item["clinical_meaning"] is not None):
            raise PatientRegistryError("Invalid laboratory observation projection")
        if item["status"] == "reported_value":
            if item["value_text"] is None or item["unit_code"] is None or item["absent_reason"] is not None:
                raise PatientRegistryError("Invalid laboratory value projection")
        else:
            if item["value_text"] is not None or item["unit_code"] is not None or item["absent_reason"] not in (
                    "unknown", "not-performed", "error", "masked"):
                raise PatientRegistryError("Invalid laboratory absence projection")
        seen_labs.add(identity)
        laboratory.append(dict(item))
    laboratory.sort(key=lambda o: (
        o["effective_at"], o["document_id"], o["document_version"],
        o["observation_reference"], o["source_id"]))
    grouped: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for item in observations:
        context = item.get("oncology")
        if item["specimen_id"] is None or (context and context["episode_id"] is None):
            continue
        # Generic findings retain the legacy rule. Compare attributed findings
        # only within the same source-declared tumor and role.
        key = (item["specimen_id"], item["event_date"], item["finding_key"],
               context["episode_id"] if context else "", context["role"] if context else "")
        grouped[key].append(item)
    conflicts = []
    for (specimen, event_date, finding_key, _, _), items in sorted(grouped.items()):
        states = {item["reported_state"] for item in items}
        if not {"reported", "negative"}.issubset(states):
            continue
        conflicts.append({
            "specimen_id": specimen,
            "event_date": event_date,
            "finding_key": finding_key,
            "status": "unresolved_source_disagreement",
            "reported_states": sorted(states),
            "source_refs": [
                {"source_id": item["source_id"], "source_line": item["source_line"]}
                for item in items
            ],
            "clinical_interpretation": "not_performed",
        })
    unresolved_refs = [
        {"source_id": item["source_id"], "source_line": item["source_line"]}
        for item in observations if item["reported_state"] in UNRESOLVED
    ]
    # Not a permission token. A future Composer executor must re-read the
    # original source owner and verify the current fingerprint at execution.
    fingerprint_input = {
        "patient_id": patient_id,
        "case_id": case_id,
        "current_sources": current,
        # The canonical source rows already commit to FHIR raw bytes via SHA-256.
        # Keep this fingerprint source-based so every investigation/review caller
        # obtains the same snapshot identity without needing a second derived read.
        "observations": observations,
    }
    digest = hashlib.sha256(json.dumps(
        fingerprint_input, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    cutoff = max((s["received_at"] for s in sources), default=None)
    return {
        "contract": "oi.pg-source-world-model/1",
        "patient_id": patient_id,
        "case_id": case_id,
        "access_receipt_id": receipt_id,
        "synthetic": True,
        "authority": "source_report_only_unreviewed",
        "clinical_interpretation": False,
        "research_review_invalidation_integrated": False,
        "composer_execution_authorized": False,
        "snapshot_fingerprint": digest,
        "as_of_received_at": cutoff,
        "summary": {
            "current_sources": len(current),
            "historical_sources": len(history),
            "current_observations": len(observations) + len(laboratory),
            "current_laboratory_observations": len(laboratory),
            "unresolved_observations": len(unresolved_refs)
                + sum(1 for item in laboratory if item["status"] == "reported_absent"),
            "source_disagreements": len(conflicts),
        },
        "current_sources": current,
        "history": history,
        "observations": observations,
        "laboratory_observations": laboratory,
        "laboratory_timeline": [{
            "source_id": item["source_id"],
            "observation_reference": item["observation_reference"],
            "loinc_code": item["loinc_code"],
            "effective_at": item["effective_at"],
            "issued_at": item["issued_at"],
            "specimen_reference": item["specimen_reference"],
            "status": item["status"],
            "clinical_interpretation": "not_performed",
        } for item in laboratory],
        "unresolved_refs": unresolved_refs,
        "conflicts": conflicts,
        "limitations": [
            "Only independently fictional source-reported findings are represented.",
            "Original bytes and source custody remain in the existing PostgreSQL owner.",
            "No clinical identity proof, consent, professional review or real PHI support.",
            "Absent specimens cannot be assumed to be identical; different dates are not conflicts.",
            "No inferred diagnosis, staging, treatment response, trial eligibility or recommendations.",
            "Typed FHIR laboratory rows remain source-reported and unreviewed; no reference-range or normal/abnormal inference.",
            "No biomedical evidence, Composer execution, human-review queue or outcomes integrated.",
            "Fingerprint is not signed, a permission grant or a safe execution authorization.",
        ],
    }
