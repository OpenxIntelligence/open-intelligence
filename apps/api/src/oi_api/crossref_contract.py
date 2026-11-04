"""Narrow H1 facts-only projection; no publisher text or inferred permissions."""
import hashlib
import json
import re
from urllib.parse import quote

from open_intelligence.crossref_metadata import (
    API_ROOT, POLICY_URL, ACCESS_URL, ADAPTER_VERSION, normalize_doi,
)
from open_intelligence.evidence_catalog import EvidenceRecord, record_fingerprint
from open_intelligence.patient_registry import PatientRegistryError

LICENCE = "Crossref factual bibliographic metadata; article rights not granted"
PERMISSIONS = {"metadata": {"store": "allowed", "display": "allowed"}}
SELECTED_FIELDS = ("doi", "title", "journal", "year", "publication_type", "authors", "canonical_url")
POLICY = {"provider": "crossref", "version": "oi.crossref-metadata-policy/1",
          "rights_basis": POLICY_URL, "access_policy": ACCESS_URL,
          "permissions": PERMISSIONS, "release": "synthetic_developer_review_only"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


POLICY_SHA256 = digest(POLICY)


def bounded_doi(value):
    doi = normalize_doi(value)
    if len(doi) > 200 or len("https://doi.org/" + quote(doi, safe="")) > 512:
        raise ValueError("DOI exceeds the bounded H1 metadata contract")
    return doi


def exact_citation(value):
    if type(value) is not str:
        raise ValueError("Exact citation required")
    if re.fullmatch(r"FICT-[A-Z0-9-]{1,123}@[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        return value
    doi, separator, version = value.rpartition("@")
    if not separator or not re.fullmatch(r"[0-9a-f]{64}", version) or bounded_doi(doi) != doi:
        raise ValueError("Exact permitted metadata citation required")
    return value


def selected_projection(projected, doi):
    from open_intelligence.crossref_metadata import validate_projected_work
    checked = validate_projected_work(projected, bounded_doi(doi))
    return {key: checked[key] for key in SELECTED_FIELDS}


def restore_projection(selected, retrieved_at):
    if type(selected) is not dict or set(selected) != set(SELECTED_FIELDS):
        raise ValueError("Selected bibliography fields required")
    value = {"kind": "bibliographic_metadata_only", **selected,
             "source": {"provider": "Crossref REST API", "retrieved_at": retrieved_at,
                "record_url": API_ROOT + quote(selected["doi"], safe=""),
                "rights_basis": POLICY_URL, "access_policy": ACCESS_URL,
                "scope": "bibliographic facts only; Crossref-generated data CC0"},
             "clinical_evidence_appraised": False, "copyrighted_abstract_included": False}
    selected_projection(value, selected["doi"])
    return value


def catalog_record(selected, version, *, permissions=PERMISSIONS, revoked=False, superseded=False):
    if digest(selected) != version:
        raise PatientRegistryError("Crossref projection fingerprint differs")
    return EvidenceRecord(id=bounded_doi(selected["doi"]), version=version, source_kind="crossref",
        title=selected["title"], terms=(selected["doi"],), licence=LICENCE,
        link=selected["canonical_url"], permissions=permissions, revoked=revoked, superseded=superseded)


def bibliography(selected, first_retrieved_at, acquisition_mode):
    restored = restore_projection(selected, first_retrieved_at)
    if acquisition_mode not in {"provider_lookup", "protocol_fixture"}:
        raise ValueError("Trusted acquisition mode required")
    return {"doi": selected["doi"], "journal": selected["journal"], "year": selected["year"],
            "publication_type": selected["publication_type"], "authors": list(selected["authors"]),
            "retrieved_at": first_retrieved_at, "record_url": restored["source"]["record_url"],
            "rights_basis": POLICY_URL, "access_policy": ACCESS_URL,
            "adapter_version": ADAPTER_VERSION, "projection_sha256": digest(selected),
            "acquisition_mode": acquisition_mode}
