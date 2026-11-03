"""PostgreSQL persistence adapter for #224's original evidence metadata contract.

This boundary accepts independently authored fictional metadata only. There is
no HTTP rights-grant endpoint and no live publisher connector. Operator fixture
declarations are auditable inputs, not independent legal permission. Pure
validation/citation helpers are shared with the original isolated catalog.
"""
from __future__ import annotations

from dataclasses import replace
import hmac
import json
import re
import unicodedata
from urllib.parse import urlsplit
import uuid

from open_intelligence.evidence_catalog import EvidenceRecord, record_fingerprint, metadata_hit
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryError, _key
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.rights import normalize_permissions, permitted

RECORD_FIELDS = "record_id,version,source_kind,title,terms,licence,link,case_id,organization,metadata_sha256"


def _visible(value, maximum, *, minimum=1):
    if (type(value) is not str or not minimum <= len(value) <= maximum
            or value != value.strip()
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value)):
        raise PatientRegistryError("Invalid fictional metadata field")
    return value


def _fictional(record):
    """Narrow the general contract to the currently authorized fixture boundary."""
    if not isinstance(record, EvidenceRecord) or record.source_kind != "fictional":
        raise PatientRegistryError("Only independently authored fictional metadata is enabled")
    if (type(record.id) is not str or re.fullmatch(r"FICT-[A-Z0-9-]{1,123}", record.id) is None
            or type(record.version) is not str
            or re.fullmatch(r"[A-Za-z0-9._-]{1,64}", record.version) is None):
        raise PatientRegistryError("Invalid fictional metadata identity")
    _visible(record.title, 300)
    _visible(record.licence, 128)
    _visible(record.link, 512)
    url = urlsplit(record.link)
    if (url.scheme != "https" or url.netloc != "example.invalid"
            or not url.path.startswith("/fictional/") or url.query or url.fragment):
        raise PatientRegistryError("Only explicit fictional source links are enabled")
    if type(record.terms) is not tuple or len(record.terms) > 32:
        raise PatientRegistryError("Invalid fictional metadata terms")
    for term in record.terms:
        _visible(term, 80)
    if type(record.revoked) is not bool or type(record.superseded) is not bool:
        raise PatientRegistryError("Rights flags must be exact booleans")
    if record.case_id is not None:
        _key(record.case_id, "case_id")
        _key(record.organization, "organization")
    # Shared owner validates complete scope and metadata identity.
    record_fingerprint(record)
    return record


def fictional_records():
    """Original nonclinical engineering examples; not derived from a real case."""
    permission = {"metadata": {"store": "allowed", "display": "allowed"}}
    return [
        EvidenceRecord(
            id="FICT-RECORD-CONTINUITY", version="1", source_kind="fictional",
            title="Fictional study of record continuity during care handoffs",
            terms=("continuity", "records", "handoffs"), licence="Original synthetic fixture",
            link="https://example.invalid/fictional/FICT-RECORD-CONTINUITY/1",
            permissions=permission,
        ),
        EvidenceRecord(
            id="FICT-TRIAL-PREPARATION", version="1", source_kind="fictional",
            title="Fictional trial discussion preparation protocol",
            terms=("trial", "questions", "preparation"), licence="Original synthetic fixture",
            link="https://example.invalid/fictional/FICT-TRIAL-PREPARATION/1",
            permissions=permission,
        ),
    ]


def _rights_locked(registry, record_id, version, *, permissions, revoked, superseded,
                   recorded_by, reason):
    if type(revoked) is not bool or type(superseded) is not bool:
        raise PatientRegistryError("Rights flags must be exact booleans")
    normalized = normalize_permissions(permissions)
    _key(recorded_by, "recorded_by")
    _visible(reason, 500, minimum=3)
    row = registry._fetchone(
        "SELECT record_id FROM investigation.evidence_catalog_records "
        "WHERE record_id=%s AND version=%s FOR UPDATE", (record_id, version),
    )
    if row is None:
        raise PatientRegistryError("Evidence record unavailable")
    last = registry._fetchone(
        "SELECT COALESCE(max(revision),0) FROM investigation.evidence_rights_decisions "
        "WHERE record_id=%s AND version=%s", (record_id, version),
    )[0]
    identifier = "EVIDENCE-RIGHTS-" + uuid.uuid4().hex.upper()
    registry._execute(
        "INSERT INTO investigation.evidence_rights_decisions "
        "(decision_id,record_id,version,revision,permissions,revoked,superseded,recorded_by,reason) "
        "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
        (identifier, record_id, version, last + 1, json.dumps(normalized), revoked,
         superseded, recorded_by, reason),
    )
    return identifier


def append_rights_decision(registry, record_id, version, *, permissions, revoked,
                           superseded, recorded_by, reason):
    """Trusted operator port; intentionally not exposed by a patient API route."""
    if not isinstance(registry, PostgresPatientRegistry):
        raise TypeError("Canonical PostgreSQL connection required")
    with registry.transaction():
        return _rights_locked(registry, record_id, version, permissions=permissions,
                              revoked=revoked, superseded=superseded,
                              recorded_by=recorded_by, reason=reason)


def seed_fictional_records(registry, records, *, recorded_by):
    """Explicitly seed original fixture metadata; never reset an existing grant."""
    if not isinstance(registry, PostgresPatientRegistry):
        raise TypeError("Canonical PostgreSQL connection required")
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= 100:
        raise PatientRegistryError("Bounded fictional fixture records required")
    _key(recorded_by, "recorded_by")
    checked = [_fictional(record) for record in records]
    with registry.transaction():
        for record in checked:
            permissions = normalize_permissions(record.permissions)
            if not permitted(permissions, "metadata", "store",
                             revoked=record.revoked, superseded=record.superseded):
                raise PatientRegistryError("Metadata storage requires an explicit fixture declaration")
            digest = record_fingerprint(record)
            old = registry._fetchone(
                "SELECT metadata_sha256 FROM investigation.evidence_catalog_records "
                "WHERE record_id=%s AND version=%s FOR UPDATE", (record.id, record.version),
            )
            if old is not None:
                if not hmac.compare_digest(old[0], digest):
                    raise PatientRegistryConflict("Immutable evidence version differs")
                continue
            registry._execute(
                "INSERT INTO investigation.evidence_catalog_records (" + RECORD_FIELDS + ") "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)",
                (record.id, record.version, record.source_kind, record.title,
                 json.dumps(record.terms), record.licence, record.link,
                 record.case_id, record.organization, digest),
            )
            _rights_locked(registry, record.id, record.version, permissions=permissions,
                           revoked=record.revoked, superseded=record.superseded,
                           recorded_by=recorded_by, reason="Original fictional fixture declaration")


def materialize_locked(registry, row):
    """Caller holds a SHARE lock on this record until source receipt commit."""
    record_id, version, kind, title, terms, licence, link, case, org, digest = row
    rights = registry._fetchone(
        "SELECT decision_id,permissions,revoked,superseded "
        "FROM investigation.evidence_rights_decisions "
        "WHERE record_id=%s AND version=%s ORDER BY revision DESC LIMIT 1",
        (record_id, version),
    )
    record = _fictional(EvidenceRecord(
        id=record_id, version=version, source_kind=kind, title=title,
        terms=tuple(terms), licence=licence, link=link, case_id=case, organization=org,
        permissions=rights[1] if rights else {},
        revoked=rights[2] if rights else True, superseded=rights[3] if rights else False,
    ))
    if not hmac.compare_digest(record_fingerprint(record), digest):
        raise PatientRegistryError("Evidence metadata integrity unavailable")
    return record, digest, rights[0] if rights else None


def public_metadata(record, digest, *, case_id, organization):
    """Searchable metadata needs storage AND display; a title is not a citation."""
    hit = metadata_hit(record, case_id=case_id, organization=organization)
    if (hit is None or hit.title is None
            or not permitted(record.permissions, "metadata", "display",
                             revoked=record.revoked, superseded=record.superseded)):
        return None
    return {
        "citation": f"{record.id}@{record.version}", "id": record.id,
        "version": record.version, "source_kind": record.source_kind,
        "title": hit.title, "licence": hit.licence, "link": hit.link,
        "metadata_sha256": digest, "availability": "metadata_only", "rights_status": "granted",
    }


def main():
    from .config import Settings
    from .database import Database
    database = Database(Settings.from_env())
    try:
        with database.registry_connection() as connection:
            seed_fictional_records(PostgresPatientRegistry(connection, lambda *args: False),
                                   fictional_records(), recorded_by="FIXTURE-AUTHOR")
        print("Original fictional metadata catalog seeded; no clinical content or external retrieval.")
    finally:
        database.close()


if __name__ == "__main__":
    main()
