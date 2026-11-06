"""Governed metadata discovery and immutable citations on canonical questions."""
from __future__ import annotations

import hashlib
import hmac
import re
import uuid

from open_intelligence.citation_verifier import parse_citation, verify_record
from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .reviewed_documents import ReviewedDocuments
from .reviewed_questions import resolve_question_locked
from .case_bindings import _case_id
from .composer_preflight import SOURCE_SNAPSHOT_CONTRACT, SHA256
from .evidence_catalog import RECORD_FIELDS, _visible, materialize_locked, public_metadata
from .source_questions import PostgresSourceQuestions
from .sources import PostgresSourceVersions


class PostgresQuestionEvidence:
    """No second question or patient store; reuse the source owner's transaction."""

    def __init__(self, registry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _run(self, patient_id, case_id, question_id, *, organization, actor, purpose,
             operation, recheck_authority, prepare_response, write=False, reviewed_source=None):
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if (purpose != "operations" or type(question_id) is not str
                or re.fullmatch(r"QUESTION-[0-9A-F]{32}", question_id) is None):
            raise PatientRegistryDenied("Question evidence unavailable")
        rights_versions = {}

        def authority():
            recheck_authority()
            for action in ("patient_read", "question_read", "source_read", "evidence_read") + (
                    ("evidence_link",) if write else ()):
                self.registry._allow(actor, patient_id, action, purpose)
            if reviewed_source is not None:
                self.registry._allow(actor, patient_id, "source_original_read", purpose)
            # Record row locks serialize a different connection's rights append.
            # Also refuse a same-transaction callback changing inspected rights.
            for (record_id, version), expected in rights_versions.items():
                latest = self.registry._fetchone(
                    "SELECT decision_id FROM investigation.evidence_rights_decisions "
                    "WHERE record_id=%s AND version=%s ORDER BY revision DESC LIMIT 1",
                    (record_id, version),
                )
                if (latest[0] if latest else None) != expected:
                    raise PatientRegistryDenied("Evidence rights changed")

        def prepare(index):
            items = PostgresSourceQuestions(self.registry).project_locked(
                patient_id, case_id, organization=organization, source_index=index,
            )
            question = next((item for item in items if item["question_id"] == question_id), None)
            if question is None:
                raise PatientRegistryDenied("Question evidence unavailable")
            return encode(question, index["access_receipt_id"])

        def encode(question, receipt):
            scope = {
                "patient_id": patient_id, "case_id": case_id, "question_id": question_id,
                "source_context_state": question["source_context_state"],
                "source_access_receipt_id": receipt,
                "synthetic": True, "model_executed": False,
                "content_appraised": False, "clinical_approval": False,
            }
            result = operation(question, scope, rights_versions)
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            authority()
            if reviewed_source is not None:
                owner = ReviewedDocuments(self.registry)
                scope = (patient_id, case_id, organization, purpose, reviewed_source)
                question, binding = resolve_question_locked(owner, scope, question_id)
                selection = question["selection"]
                current = selection["selection_state"] == "current_unreviewed_selection"
                receipt = "ACCESS-" + uuid.uuid4().hex.upper()
                prepared = encode({"source_context_state": "current_unreviewed_question" if current
                                   else "source_reassessment_required"}, receipt)
                owner._read_receipt(patient_id, case_id, actor=actor, purpose=purpose,
                    binding_revision=binding, event="source.document_question_access_authorized",
                    receipt_id=receipt, source_id=reviewed_source, sha256=selection["anchor"]["original_sha256"],
                    recheck_authority=authority)
                authority()
                return prepared
            prepared = PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor,
                purpose=purpose, prepare_response=prepare, recheck_authority=authority,
            )
            # The source owner checks before writing its access receipt. Check
            # again after that audit tail, still under the same record locks,
            # so a trusted same-transaction callback cannot change the rights
            # of metadata that was already encoded for disclosure.
            authority()
            return prepared

    def _record(self, record_id, version, rights_versions):
        row = self.registry._fetchone(
            "SELECT " + RECORD_FIELDS + " FROM investigation.evidence_catalog_records "
            "WHERE record_id=%s AND version=%s FOR SHARE", (record_id, version),
        )
        if row is None:
            return None, None
        record, digest, decision = materialize_locked(self.registry, row)
        rights_versions[(record.id, record.version)] = decision
        return record, digest

    def search(self, patient_id, case_id, question_id, *, organization, actor, purpose,
               query, recheck_authority, prepare_response=None, reviewed_source=None):
        _visible(query, 200)
        tokens = re.findall(r"\w+", query.casefold())
        if not tokens or len(tokens) > 24:
            raise PatientRegistryError("A bounded metadata query is required")

        def operation(question, scope, rights_versions):
            rows = self.registry._fetchall(
                "SELECT " + RECORD_FIELDS + " FROM investigation.evidence_catalog_records "
                "WHERE (case_id IS NULL AND organization IS NULL) "
                "OR (case_id=%s AND organization=%s) "
                "ORDER BY record_id,version LIMIT 1001 FOR SHARE", (case_id, organization),
            )
            if len(rows) > 1000:
                raise PatientRegistryError("Fictional catalog exceeds bounded search limit")
            results = []
            for row in rows:
                record, digest, decision = materialize_locked(self.registry, row)
                visible = public_metadata(record, digest, case_id=case_id, organization=organization)
                # Never match an unauthorized title/terms and reveal its existence.
                if visible is None:
                    continue
                haystack = set(re.findall(r"\w+", (record.title + " " + " ".join(record.terms)).casefold()))
                if not all(token in haystack for token in tokens):
                    continue
                rights_versions[(record.id, record.version)] = decision
                results.append(visible)
                if len(results) == 25:
                    break
            self.registry.append_event(
                patient_id, "evidence.metadata.searched", question_id=question_id,
                case_id=case_id, actor=actor, query_sha256=hashlib.sha256(query.encode()).hexdigest(),
                result_count=len(results), result_manifest_sha256=_digest(results),
            )
            return {**scope, "contract": "oi.pg-question-evidence-search/1", "query": query, "records": results}

        return self._run(patient_id, case_id, question_id, organization=organization,
                         actor=actor, purpose=purpose, operation=operation,
                         recheck_authority=recheck_authority, prepare_response=prepare_response, reviewed_source=reviewed_source)

    def links(self, patient_id, case_id, question_id, *, organization, actor, purpose,
              recheck_authority, prepare_response=None):
        def operation(question, scope, rights_versions):
            rows = self.registry._fetchall(
                "SELECT link_id,record_id,version,metadata_sha256,created_at,actor "
                "FROM investigation.question_evidence_links "
                "WHERE patient_id=%s AND case_id=%s AND question_id=%s AND origin_org=%s "
                "ORDER BY created_at,link_id LIMIT 101", (patient_id, case_id, question_id, organization),
            )
            if len(rows) > 100:
                raise PatientRegistryError("Evidence history exceeds bounded read limit")
            links = []
            for link_id, record_id, version, expected, created, author in rows:
                record, digest = self._record(record_id, version, rights_versions)
                citation = f"{record_id}@{version}"
                visible = None
                if record is None:
                    status = "unavailable"
                elif not hmac.compare_digest(expected, digest):
                    raise PatientRegistryError("Immutable citation metadata changed")
                elif record.superseded:
                    status = "superseded"
                else:
                    verified = verify_record(record, citation, case_id=case_id, organization=organization)
                    visible = public_metadata(record, digest, case_id=case_id, organization=organization) if verified.ok else None
                    status = "available" if visible is not None else "rights_restricted"
                links.append({"link_id": link_id, "citation": citation,
                              "metadata_sha256": expected, "created_at": created.isoformat(),
                              "actor_label": author, "status": status, "record": visible})
            self.registry.append_event(patient_id, "evidence.links.read_authorized",
                                       question_id=question_id, case_id=case_id, actor=actor,
                                       link_count=len(links))
            return {**scope, "contract": "oi.pg-question-evidence-links/1", "links": links}

        return self._run(patient_id, case_id, question_id, organization=organization,
                         actor=actor, purpose=purpose, operation=operation,
                         recheck_authority=recheck_authority, prepare_response=prepare_response)

    def create_link(self, patient_id, case_id, question_id, *, organization, actor, purpose,
                    request_key, citation, expected_metadata_sha256, source_snapshot_contract,
                    expected_source_snapshot_sha256, expected_preflight_sha256,
                    recheck_authority, prepare_response=None):
        request_key = _key(request_key, "request_key")
        try:
            record_id, version = parse_citation(citation)
        except ValueError:
            raise PatientRegistryError("Malformed citation") from None
        if (not record_id.startswith("FICT-") or version is None
                or citation != f"{record_id}@{version}"):
            raise PatientRegistryError("An exact fictional evidence version is required")
        if source_snapshot_contract != SOURCE_SNAPSHOT_CONTRACT:
            raise PatientRegistryConflict("Question context requires reassessment")
        for fingerprint in (expected_metadata_sha256, expected_source_snapshot_sha256,
                            expected_preflight_sha256):
            if type(fingerprint) is not str or SHA256.fullmatch(fingerprint) is None:
                raise PatientRegistryError("Exact fingerprints required")
        intent = _digest({
            "operation": "evidence.link", "patient_id": patient_id, "case_id": case_id,
            "question_id": question_id, "organization": organization, "actor": actor,
            "purpose": purpose, "request_key": request_key, "citation": citation,
            "metadata_sha256": expected_metadata_sha256,
            "source_snapshot_contract": source_snapshot_contract,
            "source_snapshot_sha256": expected_source_snapshot_sha256,
            "preflight_sha256": expected_preflight_sha256,
        })

        def operation(question, scope, rights_versions):
            old = self.registry._fetchone(
                "SELECT link_id,intent_sha256,record_id,version,metadata_sha256 "
                "FROM investigation.question_evidence_links "
                "WHERE patient_id=%s AND request_key=%s FOR UPDATE", (patient_id, request_key),
            )
            if old is not None:
                if not hmac.compare_digest(old[1], intent):
                    raise PatientRegistryConflict("Evidence request key reused with changed intent")
                # An exact retry recovers the original identity receipt only;
                # it releases no cached metadata or new effect after revocation.
                return {"link_id": old[0], "citation": f"{old[2]}@{old[3]}",
                        "metadata_sha256": old[4], "duplicate": True}
            if (question["source_context_state"] != "current_unreviewed_question"
                    or not hmac.compare_digest(question["source_snapshot_sha256"], expected_source_snapshot_sha256)
                    or not hmac.compare_digest(question["preflight_sha256"], expected_preflight_sha256)):
                raise PatientRegistryConflict("Question source context changed")
            record, digest = self._record(record_id, version, rights_versions)
            verified = verify_record(record, citation, case_id=case_id, organization=organization)
            if not verified.ok or public_metadata(record, digest, case_id=case_id, organization=organization) is None:
                raise PatientRegistryDenied("Evidence unavailable")
            if not hmac.compare_digest(digest, expected_metadata_sha256):
                raise PatientRegistryConflict("Evidence version differs from the selected result")
            count = self.registry._fetchone(
                "SELECT count(*) FROM investigation.question_evidence_links WHERE question_id=%s", (question_id,),
            )[0]
            if count >= 100:
                raise PatientRegistryError("Question evidence link limit reached")
            link_id = "EVIDENCE-LINK-" + uuid.uuid4().hex.upper()
            inserted = self.registry._fetchone(
                "INSERT INTO investigation.question_evidence_links "
                "(link_id,patient_id,case_id,question_id,origin_org,actor,purpose,request_key,"
                "intent_sha256,record_id,version,metadata_sha256,source_snapshot_contract,"
                "source_snapshot_sha256,preflight_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING link_id",
                (link_id, patient_id, case_id, question_id, organization, actor, purpose,
                 request_key, intent, record_id, version, digest, source_snapshot_contract,
                 expected_source_snapshot_sha256, expected_preflight_sha256),
            )
            if inserted is None:
                # Different case bindings can race for one patient-wide key.
                # Never turn that defined conflict into a generic SQL failure.
                prior = self.registry._fetchone(
                    "SELECT link_id,intent_sha256,record_id,version,metadata_sha256 "
                    "FROM investigation.question_evidence_links "
                    "WHERE patient_id=%s AND request_key=%s FOR UPDATE", (patient_id, request_key),
                )
                if prior is None or not hmac.compare_digest(prior[1], intent):
                    raise PatientRegistryConflict("Evidence request key reused with changed intent")
                return {"link_id": prior[0], "citation": f"{prior[2]}@{prior[3]}",
                        "metadata_sha256": prior[4], "duplicate": True}
            self.registry.append_event(
                patient_id, "evidence.citation.linked", question_id=question_id, case_id=case_id,
                link_id=link_id, record_id=record_id, record_version=version,
                metadata_sha256=digest, rights_decision_id=rights_versions[(record_id, version)], actor=actor,
            )
            return {"link_id": link_id, "citation": citation,
                    "metadata_sha256": digest, "duplicate": False}

        return self._run(patient_id, case_id, question_id, organization=organization,
                         actor=actor, purpose=purpose, operation=operation,
                         recheck_authority=recheck_authority, prepare_response=prepare_response, write=True)
