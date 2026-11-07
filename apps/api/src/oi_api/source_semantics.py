"""Versioned semantic projection of the existing authorized source World Model.

No new ledger, inferred ontology mapping, patient fact, or execution authority.
The pure semantic contract is reused from #606; source custody remains in PG.
"""
from dataclasses import asdict
from typing import Literal

from open_intelligence.semantic_contract import Concept, SemanticReference, SemanticRegistry

from .contracts import Contract


REGISTRY = SemanticRegistry((
    Concept("oi:source-statement", 1, "An attributed statement in an exact source version; unreviewed."),
    Concept("oi:laboratory-observation", 1, "A source-reported structured laboratory observation; unreviewed."),
), ())
STATES = {
    "reported": "present", "negative": "negative", "pending": "pending",
    "indeterminate": "indeterminate", "not-reported": "missing",
    "not-assessed": "missing", "conflicting": "conflicting",
}
ABSENCE = {"unknown": "indeterminate", "not-performed": "missing",
           "error": "indeterminate", "masked": "missing"}


class SourceSemanticReference(Contract):
    owner: Literal["clinical_source"]
    record_id: str
    concept_id: Literal["oi:source-statement", "oi:laboratory-observation"]
    concept_version: Literal[1]
    source_version_id: str
    knowledge_kind: Literal["reported"]
    evidence_status: Literal["present", "negative", "missing", "pending", "indeterminate", "conflicting"]
    source_sha256: str
    original_state: str


class SourceSemantics(Contract):
    contract: Literal["oi.source-semantics/1"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    source_snapshot_sha256: str
    synthetic: Literal[True]
    clinical_interpretation: Literal[False]
    records: list[SourceSemanticReference]


def project_source_semantics(world: dict) -> SourceSemantics:
    """Consume the validated World Model inside its source-read transaction.

    'present' means a reported entry exists, never normality or disease presence.
    Keep the original state (including masked/not-assessed) alongside the broad
    evidence class so normalization cannot erase why information is unavailable.
    """
    records = []
    for concept, rows in (("oi:source-statement", world["observations"]),
                          ("oi:laboratory-observation", world["laboratory_observations"])):
        for row in rows:
            if concept == "oi:source-statement":
                location = f"line/{row['source_line']}"
                original = row["reported_state"]
                status = STATES[original]
            else:
                location = f"observation/{row['observation_reference']}"
                original = row["absent_reason"] if row["status"] == "reported_absent" else row["status"]
                status = ABSENCE[original] if row["status"] == "reported_absent" else "present"
            ref = SemanticReference("clinical_source", f"{row['source_id']}/{location}",
                                    concept, 1, row["source_id"], "reported", status)
            REGISTRY.validate_reference(ref)
            records.append(SourceSemanticReference(**asdict(ref),
                source_sha256=row["source_sha256"], original_state=original))
    return SourceSemantics(contract="oi.source-semantics/1", patient_id=world["patient_id"],
        case_id=world["case_id"], access_receipt_id=world["access_receipt_id"],
        source_snapshot_sha256=world["snapshot_fingerprint"], synthetic=True,
        clinical_interpretation=False, records=records)
