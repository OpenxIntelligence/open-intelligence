"""Two-phase DOI lookup on canonical H1 evidence; no patient context reaches a provider.

Preflight and final disclosure are separate transactions. The provider runs
with no patient connection/lock. Facts-only declarations apply to explicitly
enabled synthetic engineering, not a commercial, clinical or AI-use approval.
"""
import hmac
import json
import uuid

from open_intelligence.crossref_metadata import ADAPTER_VERSION
from open_intelligence.evidence_catalog import record_fingerprint
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError
from open_intelligence.rights import permitted
from .crossref_contract import (
    POLICY_SHA256, PERMISSIONS, bounded_doi, selected_projection, restore_projection,
    catalog_record, digest,
)
from .evidence_catalog import RECORD_FIELDS, _rights_locked, materialize_locked, public_metadata
from .question_evidence import PostgresQuestionEvidence


def lock_doi_family(registry, doi):
    """Same lock order for lookup and trusted rights writers, including first import."""
    doi = bounded_doi(doi)
    registry._fetchone("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("oi.crossref.doi:"+doi,))


def projection_locked(registry, doi, version):
    row = registry._fetchone(
        "SELECT p.projection,p.projection_sha256,p.first_retrieved_at,p.adapter_version,p.policy_sha256,"
        "p.acquisition_mode,r.provider_retrieved_at,r.adapter_version,r.policy_sha256,r.acquisition_mode "
        "FROM investigation.crossref_metadata_projections p "
        "JOIN investigation.crossref_retrieval_receipts r ON r.receipt_id=p.origin_receipt_id "
        "AND r.record_id=p.record_id AND r.version=p.version WHERE p.record_id=%s AND p.version=%s", (doi, version))
    if (row is None or row[1] != version or row[3] != ADAPTER_VERSION or row[4] != POLICY_SHA256
            or row[2] != row[6] or row[3] != row[7] or row[4] != row[8] or row[5] != row[9]):
        raise PatientRegistryError("Crossref projection provenance unavailable")
    selected = row[0]
    first = row[2].isoformat()
    if type(selected) is not dict or selected.get("doi") != doi or digest(selected) != version:
        raise PatientRegistryError("Crossref selected metadata integrity unavailable")
    try:
        restore_projection(selected, first)
    except (ValueError, TypeError, KeyError):
        raise PatientRegistryError("Crossref selected metadata unavailable") from None
    return selected, first, row[5]


def family_rights_locked(registry, doi, rights_versions, expected=None):
    lock_doi_family(registry, doi)
    rows = registry._fetchall("SELECT "+RECORD_FIELDS+" FROM investigation.evidence_catalog_records "
        "WHERE record_id=%s ORDER BY version LIMIT 101 FOR SHARE", (doi,))
    if len(rows) > 100:
        raise PatientRegistryError("DOI version limit reached")
    decisions = {}
    for row in rows:
        record, _, decision = materialize_locked(registry, row)
        if any(not permitted(record.permissions, "metadata", operation,
                             revoked=record.revoked, superseded=record.superseded)
               for operation in ("store", "display")):
            raise PatientRegistryDenied("DOI metadata rights unavailable")
        decisions[record.version] = decision
        rights_versions[(record.id, record.version)] = decision
    # A withdrawal followed by a grant is still a new decision; do not silently
    # bind an in-flight fetch to changed authority. Concurrent new snapshots are
    # acceptable only under their independently checked current declarations.
    if expected is not None and any(decisions.get(version) != decision for version, decision in expected.items()):
        raise PatientRegistryDenied("DOI metadata rights changed")
    return decisions


class CrossrefQuestionLookup:
    def __init__(self, registry):
        self.registry = registry
        self.owner = PostgresQuestionEvidence(registry)

    @staticmethod
    def _current(question, expected=None):
        if question["source_context_state"] != "current_unreviewed_question":
            raise PatientRegistryConflict("Question source context requires reassessment")
        captured = {"source_snapshot_sha256": question["source_snapshot_sha256"],
                    "preflight_sha256": question["preflight_sha256"]}
        if expected is not None and any(not hmac.compare_digest(captured[key], expected[key]) for key in captured):
            raise PatientRegistryConflict("Question source context changed during lookup")
        return captured

    def preflight(self, patient_id, case_id, question_id, *, organization, actor, purpose,
                  doi, recheck_authority):
        doi = bounded_doi(doi)
        def operation(question, scope, rights_versions):
            captured = self._current(question)
            captured["policy_sha256"] = POLICY_SHA256
            captured["rights"] = family_rights_locked(self.registry, doi, rights_versions)
            return captured
        return self.owner._run(patient_id, case_id, question_id, organization=organization,
            actor=actor, purpose=purpose, operation=operation, recheck_authority=recheck_authority,
            prepare_response=None, extra_actions=("evidence_lookup",))

    def retain(self, patient_id, case_id, question_id, *, organization, actor, purpose, doi,
               projected, captured, acquisition_mode, recheck_authority, prepare_response):
        doi = bounded_doi(doi)
        selected = selected_projection(projected, doi)
        version = digest(selected)
        if acquisition_mode not in {"provider_lookup", "protocol_fixture"}:
            raise PatientRegistryError("Trusted acquisition mode unavailable")
        retrieved_at = projected["source"]["retrieved_at"]
        def operation(question, scope, rights_versions):
            self._current(question, captured)
            if captured.get("policy_sha256") != POLICY_SHA256:
                raise PatientRegistryDenied("DOI metadata policy changed")
            family_rights_locked(self.registry, doi, rights_versions, expected=captured["rights"])
            old = self.registry._fetchone("SELECT "+RECORD_FIELDS+" FROM investigation.evidence_catalog_records "
                "WHERE record_id=%s AND version=%s FOR SHARE", (doi, version))
            receipt_id = "EVIDENCE-RETRIEVAL-"+uuid.uuid4().hex.upper()
            if old is None:
                if len(rights_versions) >= 100:
                    raise PatientRegistryError("DOI version limit reached")
                record = catalog_record(selected, version)
                fingerprint = record_fingerprint(record)
                self.registry._execute("INSERT INTO investigation.evidence_catalog_records ("+RECORD_FIELDS+") "
                    "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)",
                    (doi, version, record.source_kind, record.title, json.dumps(record.terms), record.licence,
                     record.link, None, None, fingerprint))
                decision = _rights_locked(self.registry, doi, version, permissions=PERMISSIONS, revoked=False,
                    superseded=False, recorded_by=actor, reason="Facts-only synthetic developer policy "+POLICY_SHA256)
                rights_versions[(doi, version)] = decision
                self.registry._execute("INSERT INTO investigation.crossref_metadata_projections "
                    "(record_id,version,projection,projection_sha256,first_retrieved_at,origin_receipt_id,adapter_version,policy_sha256,acquisition_mode) "
                    "VALUES (%s,%s,%s::jsonb,%s,%s::timestamptz,%s,%s,%s,%s)",
                    (doi,version,json.dumps(selected),version,retrieved_at,receipt_id,ADAPTER_VERSION,POLICY_SHA256,acquisition_mode))
            self.registry._execute("INSERT INTO investigation.crossref_retrieval_receipts "
                "(receipt_id,record_id,version,patient_id,case_id,question_id,origin_org,actor,purpose,"
                "source_snapshot_sha256,preflight_sha256,provider_retrieved_at,adapter_version,policy_sha256,acquisition_mode) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::timestamptz,%s,%s,%s)",
                (receipt_id,doi,version,patient_id,case_id,question_id,organization,actor,purpose,
                 captured["source_snapshot_sha256"],captured["preflight_sha256"],retrieved_at,ADAPTER_VERSION,POLICY_SHA256,acquisition_mode))
            record, fingerprint = self.owner._record(doi, version, rights_versions)
            visible = public_metadata(record, fingerprint, case_id=case_id, organization=organization, registry=self.registry)
            if visible is None:
                raise PatientRegistryDenied("DOI metadata unavailable")
            self.registry.append_event(patient_id, "evidence.metadata.retrieved", case_id=case_id,
                question_id=question_id, receipt_id=receipt_id, doi_sha256=digest({"doi":doi}),
                metadata_version=version, acquisition_mode=acquisition_mode, actor=actor)
            return {**scope, "contract": "oi.pg-question-evidence-search/1", "query": doi, "records": [visible]}
        return self.owner._run(patient_id, case_id, question_id, organization=organization,
            actor=actor, purpose=purpose, operation=operation, recheck_authority=recheck_authority,
            prepare_response=prepare_response, extra_actions=("evidence_lookup",))
