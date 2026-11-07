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

from .case_bindings import _case_id
from .composer_preflight import SOURCE_SNAPSHOT_CONTRACT, SHA256
from .evidence_catalog import RECORD_FIELDS, _visible, materialize_locked, public_metadata
from .laboratory_questions import PostgresLaboratoryQuestions
from .source_questions import PostgresSourceQuestions
from .sources import PostgresSourceVersions


class PostgresQuestionEvidence:
    """No second question or patient store; reuse the source owner's transaction."""

    question_owner = PostgresSourceQuestions
    laboratory = False

    def __init__(self, registry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _run(self, patient_id, case_id, question_id, *, organization, actor, purpose,
             operation, recheck_authority, prepare_response, write=False, discovery=False):
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
            items = self.question_owner(self.registry).project_locked(
                patient_id, case_id, organization=organization, source_index=index,
            )
            question = next((item for item in items if item["question_id"] == question_id), None)
            if question is None:
                raise PatientRegistryDenied("Question evidence unavailable")
            scope = {
                "patient_id": patient_id, "case_id": case_id, "question_id": question_id,
                "source_context_state": question["source_context_state"],
                "source_access_receipt_id": index["access_receipt_id"],
                "synthetic": True, "model_executed": False,
                "content_appraised": False, "clinical_approval": False,
            }
            if self.laboratory:
                if discovery and question["source_context_state"] != "current_unreviewed_question":
                    raise PatientRegistryConflict("Laboratory question requires source reassessment")
                scope["question_anchor"] = {key: question[key] for key in (
                    "source_id", "source_version", "source_sha256", "observation_reference",
                    "source_snapshot_sha256", "preflight_sha256",
                )}
            result = operation(question, scope, rights_versions)
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            authority()
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
               query, recheck_authority, prepare_response=None):
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
                         recheck_authority=recheck_authority, prepare_response=prepare_response, discovery=True)

    def links(self, patient_id, case_id, question_id, *, organization, actor, purpose,
              recheck_authority, prepare_response=None, project_links=None):
        """Project authorized links and optionally render a report inside the same transaction."""
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
                if self.laboratory:
                    self._verify_lab_anchor(link_id, question, record_id, version)
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
            result = {**scope, "contract": "oi.pg-question-evidence-links/1", "links": links}
            return project_links(question, result) if project_links is not None else result

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

        def permitted_digest(rights_versions):
            record, digest = self._record(record_id, version, rights_versions)
            verified = verify_record(record, citation, case_id=case_id, organization=organization)
            if not verified.ok or public_metadata(record, digest, case_id=case_id, organization=organization) is None:
                raise PatientRegistryDenied("Evidence unavailable")
            if not hmac.compare_digest(digest, expected_metadata_sha256):
                raise PatientRegistryConflict("Evidence version differs from the selected result")
            return digest

        def operation(question, scope, rights_versions):
            old = self.registry._fetchone(
                "SELECT link_id,intent_sha256,record_id,version,metadata_sha256 "
                "FROM investigation.question_evidence_links "
                "WHERE patient_id=%s AND request_key=%s FOR UPDATE", (patient_id, request_key),
            )
            if old is not None:
                if not hmac.compare_digest(old[1], intent):
                    raise PatientRegistryConflict("Evidence request key reused with changed intent")
                if self.laboratory:
                    self._verify_lab_anchor(old[0], question, record_id, version)
                    permitted_digest(rights_versions)
                # An exact retry recovers the original identity receipt only;
                # it releases no cached metadata or new effect after revocation.
                return {"link_id": old[0], "citation": f"{old[2]}@{old[3]}",
                        "metadata_sha256": old[4], "duplicate": True}
            if (question["source_context_state"] != "current_unreviewed_question"
                    or not hmac.compare_digest(question["source_snapshot_sha256"], expected_source_snapshot_sha256)
                    or not hmac.compare_digest(question["preflight_sha256"], expected_preflight_sha256)):
                raise PatientRegistryConflict("Question source context changed")
            digest = permitted_digest(rights_versions)
            count = self.registry._fetchone(
                "SELECT count(*) FROM investigation.question_evidence_links WHERE question_id=%s", (question_id,),
            )[0]
            if count >= 100:
                raise PatientRegistryError("Question evidence link limit reached")
            link_id = "EVIDENCE-LINK-" + uuid.uuid4().hex.upper()
            if self.laboratory:
                # Child first: a deferred composite FK requires this exact
                # question and link to exist together at commit. An ordinary
                # text link can never accidentally persist a typed association.
                self.registry._execute(
                    "INSERT INTO investigation.laboratory_citation_anchors "
                    "(link_id,question_id,source_id,observation_reference,rights_decision_id) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (link_id, question_id, question["source_id"], question["observation_reference"],
                     rights_versions[(record_id, version)]),
                )
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
                if self.laboratory:
                    # Same-case writers serialize on the source binding. A
                    # raced patient-wide key from a different case conflicts.
                    # Roll back the prepared child with the whole transaction.
                    raise PatientRegistryConflict("Evidence request key reused with changed intent")
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


class PostgresLaboratoryQuestionEvidence(PostgresQuestionEvidence):
    """Use the same catalog, rights, link and source owners for a typed question."""

    question_owner = PostgresLaboratoryQuestions
    laboratory = True

    def _verify_lab_anchor(self, link_id, question, record_id, version):
        # Validate the immutable write-time decision separately from current
        # display rights, which are evaluated on every read and retry.
        valid = self.registry._fetchone(
            "SELECT 1 FROM investigation.laboratory_citation_anchors a "
            "JOIN investigation.question_evidence_links l ON l.link_id=a.link_id AND l.question_id=a.question_id "
            "JOIN investigation.source_questions q ON q.question_id=l.question_id AND q.source_id=a.source_id "
            "AND q.patient_id=l.patient_id AND q.case_id=l.case_id AND q.origin_org=l.origin_org AND q.purpose=l.purpose "
            "JOIN investigation.evidence_catalog_records e ON e.record_id=l.record_id AND e.version=l.version "
            "AND e.metadata_sha256=l.metadata_sha256 "
            "JOIN investigation.evidence_rights_decisions r ON r.decision_id=a.rights_decision_id "
            "WHERE a.link_id=%s AND a.question_id=%s AND a.source_id=%s AND a.observation_reference=%s "
            "AND l.source_snapshot_contract=%s AND l.source_snapshot_sha256=%s AND l.preflight_sha256=%s "
            "AND r.record_id=l.record_id AND r.version=l.version AND r.record_id=%s AND r.version=%s "
            "AND NOT r.revoked AND NOT r.superseded AND r.permissions #>> '{metadata,store}'='allowed' "
            "AND r.permissions #>> '{metadata,display}'='allowed'",
            (link_id, question["question_id"], question["source_id"], question["observation_reference"],
             SOURCE_SNAPSHOT_CONTRACT, question["source_snapshot_sha256"], question["preflight_sha256"],
             record_id, version),
        )
        if valid is None:
            raise PatientRegistryError("Stored laboratory citation provenance is inconsistent")
