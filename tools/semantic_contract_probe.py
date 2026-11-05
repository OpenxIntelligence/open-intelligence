"""Offline semantic-catalog boundary experiment (schema metadata only).

This is an internal evaluation contract, *not* an NVIDIA Auto Ontology API
adapter, SQL generator, clinical ontology, access provider, or data export.
Its only input is a human-curated field-name mapping; it never opens a database,
loads clinical records, or performs network/model calls.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

MANIFEST_CONTRACT = "oi.semantic-schema-manifest/1"
CANDIDATE_CONTRACT = "oi.semantic-mapping-candidate/1"

# Known read-only projection fields in oi_api.source_world_model at #381.
# These are *field names*, never their values. They are NOT raw SQL table
# columns and do not authorize querying the underlying canonical owners.
_FIELDS: dict[str, tuple[str, ...]] = {
    "source_version": (
        "source_id", "document_id", "version", "state", "event_date",
        "issued_at", "received_at", "sha256",
    ),
    "source_observation": (
        "source_id", "source_line", "finding_key", "reported_state",
        "review_state", "specimen_id", "event_date",
    ),
    "source_disagreement": (
        "specimen_id", "event_date", "finding_key", "status",
        "reported_states", "source_refs", "clinical_interpretation",
    ),
}


def _canonical_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=True, sort_keys=True, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def schema_manifest() -> dict[str, Any]:
    """Emit a deterministic, sanitized vocabulary, with no case data or SQL."""
    body: dict[str, Any] = {
        "contract": MANIFEST_CONTRACT,
        "scope": "known_projection_field_names_only",
        "owner": "existing_postgresql_patient_and_source_owners",
        "synthetic_evaluation_only": True,
        "clinical_ontology_authoritative": False,
        "allows_database_connections": False,
        "allows_sql_generation_or_execution": False,
        "allows_patient_data": False,
        "allows_clinical_review_or_writes": False,
        "concepts": [
            {"concept": name, "fields": list(fields)}
            for name, fields in sorted(_FIELDS.items())
        ],
    }
    return {**body, "sha256": _canonical_hash(body)}


def validate_mapping_candidate(candidate: Any) -> dict[str, Any]:
    """Fail closed on an untrusted model-proposed mapping, never approve it.

    An upstream adapter must first translate vendor output into this *strict*
    intermediate contract. Passing validation means only that a proposal is
    structurally allowed for manual inspection; it is not semantically correct.
    """
    if type(candidate) is not dict or set(candidate) != {
        "contract", "source_manifest_sha256", "mappings",
    }:
        raise ValueError("Invalid semantic candidate envelope")
    if candidate["contract"] != CANDIDATE_CONTRACT:
        raise ValueError("Unsupported semantic candidate contract")
    if candidate["source_manifest_sha256"] != schema_manifest()["sha256"]:
        raise ValueError("Stale or foreign schema manifest")
    rows = candidate["mappings"]
    if type(rows) is not list or not 1 <= len(rows) <= 32:
        raise ValueError("Invalid candidate size")
    seen: set[tuple[str, str]] = set()
    checked: list[dict[str, str]] = []
    for row in rows:
        if type(row) is not dict or set(row) != {
            "concept", "field", "candidate_term", "review_state",
        }:
            raise ValueError("Candidate contains non-schema fields")
        concept, field = row["concept"], row["field"]
        term, state = row["candidate_term"], row["review_state"]
        if (type(concept) is not str or concept not in _FIELDS
                or type(field) is not str or field not in _FIELDS[concept]):
            raise ValueError("Candidate references a non-allowlisted field")
        if (type(term) is not str
                or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", term) is None):
            raise ValueError("Invalid candidate term")
        if state != "unreviewed_proposal":
            raise ValueError("Only unreviewed semantic proposals are permitted")
        if (concept, field) in seen:
            raise ValueError("Duplicate field mapping")
        seen.add((concept, field))
        checked.append({
            "concept": concept, "field": field,
            "candidate_term": term, "review_state": "unreviewed_proposal",
        })
    return {
        "contract": CANDIDATE_CONTRACT,
        "source_manifest_sha256": candidate["source_manifest_sha256"],
        "mappings": checked,
        "semantic_accuracy_verified": False,
        "clinical_interpretation_authorized": False,
        "clinical_action_authorized": False,
        "writes_performed": False,
    }


if __name__ == "__main__":
    print(json.dumps(schema_manifest(), sort_keys=True, indent=2))
