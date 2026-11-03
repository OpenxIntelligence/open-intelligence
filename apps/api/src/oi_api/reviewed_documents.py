"""Reviewed document operations over the existing canonical source ledger.

Manual selections live in immutable source-owned revision children; they are
never inserted as source-authored assertions. PDF extraction precedes locks.
"""
import hashlib
import json
import uuid

from open_intelligence.document_intake import (
    preview_document, preview_saved_document, review_document, review_saved_document,
)
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError
from open_intelligence.store import InvalidInput
from .sources import PostgresSourceVersions, _source_id
from .source_integrity import SourceIntegrityError


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReviewedDocuments(PostgresSourceVersions):
    def _authorize(self, patient_id, case_id, organization, purpose, recheck):
        with self.registry.transaction():
            self._binding(patient_id, case_id, organization, purpose)
            recheck()

    def preview(self, patient_id, case_id, payload, *, organization, purpose,
                recheck_authority, prepare_response):
        self._authorize(patient_id, case_id, organization, purpose, recheck_authority)
        result = preview_document(payload.original_bytes(), payload.filename)
        with self.registry.transaction():
            self._binding(patient_id, case_id, organization, purpose)
            response = prepare_response(result)
            recheck_authority()
            return response

    def _revision(self, source_id, revision, findings, receipt, reason, actor, request_key, intent):
        revision_id = "ANN-" + uuid.uuid4().hex.upper()
        self.registry._execute(
            "INSERT INTO clinical_source.annotation_revisions "
            "(revision_id,source_id,revision,request_key,intent_sha256,findings_json,receipt_json,reason,actor) "
            "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)",
            (revision_id, source_id, revision, request_key, intent, canonical(findings),
             canonical(receipt), reason, actor))
        return revision_id

    def import_document(self, patient_id, case_id, payload, *, organization, actor,
                        purpose, recheck_authority, prepare_response):
        self._authorize(patient_id, case_id, organization, purpose, recheck_authority)
        raw = payload.original_bytes()
        metadata = payload.metadata.model_dump()
        findings = [f.model_dump() for f in payload.findings]
        parsed, receipt, rendition = review_document(case_id, raw, payload.filename,
            metadata, findings, payload.expected_sha256, payload.confirmed_case_id,
            payload.expected_extraction_sha256)
        # The source owner's receipt sorts selections by key.
        findings = sorted(findings, key=lambda f: f["key"])
        digest = hashlib.sha256(raw).hexdigest()
        with self.registry.transaction():
            self._binding(patient_id, case_id, organization, purpose)
            seen = self.registry._fetchone(
                "SELECT source_id FROM clinical_source.source_versions "
                "WHERE case_id=%s AND document_id=%s AND sha256=%s",
                (case_id, parsed.document_id, digest))
            if seen:
                stored = self._load(case_id, seen[0])
                if stored["initial_receipt"]["review_sha256"] != receipt["review_sha256"]:
                    raise PatientRegistryConflict("Original already has different intake selections")
                result = self._saved(stored, stored["revisions"][0]["revision_id"], True)
            else:
                old = self.registry._fetchone(
                    "SELECT s.source_id,s.version,s.kind,s.event_date,s.specimen_id,d.source_id "
                    "FROM clinical_source.source_versions s LEFT JOIN clinical_source.document_intakes d "
                    "ON d.source_id=s.source_id WHERE s.case_id=%s AND s.document_id=%s "
                    "ORDER BY s.version DESC LIMIT 1", (case_id, parsed.document_id))
                if old and (old[5] is None or parsed.amends != (parsed.document_id, old[1])
                            or (old[2], old[3].isoformat(), old[4]) !=
                            (parsed.kind, parsed.event_date, parsed.specimen_id)):
                    raise PatientRegistryConflict("Amendment must preserve latest reviewed-document identity")
                if not old and parsed.amends:
                    raise PatientRegistryConflict("Cannot amend an absent document")
                if old:
                    self._load(case_id, old[0])
                    self.registry._execute("UPDATE clinical_source.source_versions SET state='superseded' WHERE source_id=%s", (old[0],))
                source_id = "SRC-" + uuid.uuid4().hex.upper()
                version = old[1]+1 if old else 1
                self.registry._execute(
                    "INSERT INTO clinical_source.source_versions "
                    "(source_id,case_id,document_id,version,sha256,raw,kind,event_date,issued_at,specimen_id,state,supersedes_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::date,%s::date,%s,'current',%s)",
                    (source_id, case_id, parsed.document_id, version, digest, raw, parsed.kind,
                     parsed.event_date, parsed.issued_at, parsed.specimen_id, old[0] if old else None))
                self.registry._execute(
                    "INSERT INTO clinical_source.document_intakes (source_id,filename,metadata_json,receipt_json,rendition_json) "
                    "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)",
                    (source_id, payload.filename, canonical(metadata), canonical(receipt),
                     canonical(rendition) if rendition is not None else None))
                revision_id = self._revision(source_id, 1, findings, receipt, "Initial transcription confirmation",
                                             actor, "INITIAL", receipt["review_sha256"])
                self.registry.append_event(patient_id, "source.original.imported", case_id=case_id,
                    source_id=source_id, version=version, actor=actor,
                    classification_origin="user_selected", annotation_revision_id=revision_id)
                result = dict(source_id=source_id, version=version, annotation_revision_id=revision_id, duplicate=False)
            response = prepare_response(result)
            recheck_authority()
            return response

    @staticmethod
    def _saved(stored, revision_id, duplicate):
        return dict(source_id=stored["source_id"], version=stored["version"],
                    annotation_revision_id=revision_id, duplicate=duplicate)

    def _load(self, case_id, source_id):
        source_id = _source_id(source_id)
        row = self.registry._fetchone(
            "SELECT s.source_id,s.case_id,s.document_id,s.version,s.sha256,s.raw,s.kind,s.event_date,s.issued_at,"
            "s.specimen_id,s.state,s.supersedes_id,d.filename,d.metadata_json,d.receipt_json,d.rendition_json "
            "FROM clinical_source.source_versions s JOIN clinical_source.document_intakes d ON d.source_id=s.source_id "
            "WHERE s.case_id=%s AND s.source_id=%s", (case_id, source_id))
        if row is None:
            raise PatientRegistryDenied("Document unavailable")
        keys = ("source_id", "case_id", "document_id", "version", "sha256", "raw", "kind", "event_date",
                "issued_at", "specimen_id", "state", "supersedes_id", "filename", "metadata", "initial_receipt", "rendition")
        doc = dict(zip(keys, row))
        revisions = self.registry._fetchall(
            "SELECT revision_id,revision,findings_json,receipt_json,reason,actor,created_at "
            "FROM clinical_source.annotation_revisions WHERE source_id=%s ORDER BY revision", (source_id,))
        try:
            raw = bytes(doc["raw"])
            if hashlib.sha256(raw).hexdigest() != doc["sha256"] or not 1 <= len(revisions) <= 64:
                raise ValueError()
            doc["preview"] = preview_saved_document(raw, doc["filename"], doc["rendition"])
            metadata = doc["metadata"]
            if (metadata["document_id"],metadata["kind"],metadata["event_date"],metadata["issued_at"],metadata.get("specimen_id")) != (
                    doc["document_id"],doc["kind"],doc["event_date"].isoformat(),doc["issued_at"].isoformat(),doc["specimen_id"]):
                raise ValueError()
            if metadata.get("amends_version") != (doc["version"]-1 if doc["version"] > 1 else None):
                raise ValueError()
            if doc["version"] == 1:
                if doc["supersedes_id"] is not None: raise ValueError()
            else:
                predecessor = self.registry._fetchone(
                    "SELECT case_id,document_id,version,kind,event_date,specimen_id,state FROM clinical_source.source_versions WHERE source_id=%s",
                    (doc["supersedes_id"],))
                if predecessor != (case_id,doc["document_id"],doc["version"]-1,doc["kind"],doc["event_date"],doc["specimen_id"],"superseded"):
                    raise ValueError()
            doc["revisions"] = []
            for expected, rev in enumerate(revisions, 1):
                if rev[1] != expected: raise ValueError()
                _, receipt = review_saved_document(case_id, raw, doc["filename"], metadata, rev[2],
                    doc["sha256"], case_id, doc["preview"].get("extraction_sha256"), frozen_rendition=doc["rendition"])
                if canonical(receipt) != canonical(rev[3]): raise ValueError()
                if expected == 1 and canonical(receipt) != canonical(doc["initial_receipt"]): raise ValueError()
                doc["revisions"].append(dict(revision_id=rev[0],revision=rev[1],findings=rev[2],
                    review_sha256=receipt["review_sha256"],reason=rev[4],actor=rev[5],created_at=rev[6].isoformat(),
                    classification_origin="user_selected",clinical_review="not_performed"))
            doc["raw"] = raw
            return doc
        except Exception:
            raise SourceIntegrityError("Stored reviewed document integrity check failed") from None

    def read(self, patient_id, case_id, source_id=None, *, organization, actor, purpose,
             recheck_authority, prepare_response, original=False):
        with self.registry.transaction():
            binding = self._binding(patient_id, case_id, organization, purpose)
            if source_id is None:
                rows = self.registry._fetchall(
                    "SELECT s.source_id,s.document_id,s.version,s.state,s.sha256,d.filename "
                    "FROM clinical_source.source_versions s JOIN clinical_source.document_intakes d ON d.source_id=s.source_id "
                    "WHERE s.case_id=%s ORDER BY s.document_id,s.version LIMIT 513", (case_id,))
                if len(rows)>512: raise PatientRegistryError("Document list exceeds bounds")
                result = dict(patient_id=patient_id,case_id=case_id,documents=[dict(zip(
                    ("source_id","document_id","version","state","sha256","filename"),r)) for r in rows])
                doc = None
            else:
                doc = self._load(case_id, source_id)
                result = {k:doc[k] for k in ("source_id","case_id","document_id","version","state","sha256","filename","preview","revisions")}
                result["patient_id"] = patient_id
            receipt_id = "ACCESS-" + uuid.uuid4().hex.upper()
            result["access_receipt_id"] = receipt_id
            result["synthetic"] = True
            response = prepare_response(result, doc["raw"] if original and doc else None)
            self._read_receipt(patient_id,case_id,actor=actor,purpose=purpose,binding_revision=binding,
                event="source.original_read_authorized" if original else "source.document_read_authorized",
                receipt_id=receipt_id,recheck_authority=recheck_authority,source_id=source_id,
                sha256=doc["sha256"] if doc else None)
            return response

    def correct(self, patient_id, case_id, source_id, payload, *, organization, actor,
                purpose, recheck_authority, prepare_response):
        with self.registry.transaction():
            self._binding(patient_id,case_id,organization,purpose)
            doc = self._load(case_id,source_id)
            intent = fingerprint(payload.model_dump())
            prior = self.registry._fetchone(
                "SELECT revision_id,intent_sha256 FROM clinical_source.annotation_revisions WHERE source_id=%s AND request_key=%s",
                (source_id,payload.request_key))
            if prior:
                if prior[1]!=intent: raise PatientRegistryConflict("Correction key already has different intent")
                result = self._saved(doc,prior[0],True)
            else:
                if (doc["state"] != "current" or doc["revisions"][-1]["revision_id"] != payload.expected_revision_id
                        or len(doc["revisions"])>=64):
                    raise PatientRegistryConflict("Selection changed or original is historical; refresh")
                findings = sorted([f.model_dump() for f in payload.findings],key=lambda f:f["key"])
                _, receipt = review_saved_document(case_id,doc["raw"],doc["filename"],doc["metadata"],findings,
                    payload.expected_sha256,payload.confirmed_case_id,payload.expected_extraction_sha256,
                    frozen_rendition=doc["rendition"])
                revision_id=self._revision(source_id,len(doc["revisions"])+1,findings,receipt,payload.reason,
                    actor,payload.request_key,intent)
                self.registry.append_event(patient_id,"source.annotations.revised",case_id=case_id,
                    source_id=source_id,annotation_revision_id=revision_id,actor=actor)
                result=self._saved(doc,revision_id,False)
            response=prepare_response(result)
            recheck_authority()
            return response
