"""Canonical-source persistence adapter for strict synthetic FHIR R4 laboratory bundles."""
from __future__ import annotations

from datetime import datetime, date
import hashlib
import json
import re
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .laboratory_fhir_r4 import prepare_laboratory_bundle
from .sources import PostgresSourceVersions


def _fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _document_id(report_reference: str) -> str:
    return "FHIRLAB-" + hashlib.sha256(report_reference.encode()).hexdigest()[:24].upper()


def _day(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()


class PostgresLaboratoryFHIR:
    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical patient registry required")
        self.registry = registry
        self.sources = PostgresSourceVersions(registry)

    def _available(self) -> bool:
        return self.registry._fetchone(
            "SELECT to_regclass('clinical_source.fhir_laboratory_sources')")[0] is not None

    def source_ids_locked(self, case_id: str) -> set[str]:
        if not self._available():
            return set()
        return {row[0] for row in self.registry._fetchall(
            "SELECT source_id FROM clinical_source.fhir_laboratory_sources WHERE case_id=%s",
            (case_id,))}

    def is_source_locked(self, source_id: str) -> bool:
        return self._available() and self.registry._fetchone(
            "SELECT source_id FROM clinical_source.fhir_laboratory_sources WHERE source_id=%s",
            (source_id,)) is not None

    def _subject_locked(self, patient_id: str, case_id: str, organization: str, purpose: str) -> str:
        self.sources._binding(patient_id, case_id, organization, purpose)
        row = self.registry._fetchone(
            "SELECT source_subject_ref FROM coordination.patient_case_bindings "
            "WHERE case_id=%s AND patient_id=%s AND origin_org=%s AND status='active' AND purpose=%s",
            (case_id, patient_id, organization, purpose))
        if row is None:
            raise PatientRegistryDenied("Source mapping unavailable")
        return "Patient/" + row[0]

    @staticmethod
    def _intent(case_id: str, digest: str, expected_previous_source_id: str | None) -> str:
        return _fingerprint({"case_id": case_id, "sha256": digest,
                             "expected_previous_source_id": expected_previous_source_id})

    def _receipt_locked(self, source_id: str, *, duplicate: bool) -> dict:
        row = self.registry._fetchone(
            "SELECT s.version,s.sha256,count(o.observation_reference) "
            "FROM clinical_source.source_versions s "
            "JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id "
            "LEFT JOIN clinical_source.fhir_laboratory_observations o ON o.source_id=s.source_id "
            "WHERE s.source_id=%s GROUP BY s.version,s.sha256", (source_id,))
        if row is None:
            raise RuntimeError("Stored FHIR laboratory command target unavailable")
        return {"source_id": source_id, "version": row[0], "duplicate": duplicate,
                "original_sha256": row[1], "observation_count": row[2]}

    def import_bundle(self, patient_id: str, case_id: str, raw: bytes, *,
                      request_key: str, expected_previous_source_id: str | None,
                      organization: str, actor: str, purpose: str,
                      prepare_bundle=prepare_laboratory_bundle,
                      prepare_response=None, recheck_authority):
        patient_id = _key(patient_id, "patient_id")
        case_id = _key(case_id, "case_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        if purpose != "operations":
            raise PatientRegistryError("FHIR laboratory persistence is operations-only")
        if type(raw) is not bytes:
            raise PatientRegistryError("Exact FHIR bytes required")
        digest = hashlib.sha256(raw).hexdigest()
        intent = self._intent(case_id, digest, expected_previous_source_id)

        def complete(result):
            prepared = prepare_response(result) if prepare_response is not None else result
            recheck_authority()
            return prepared

        with self.registry.transaction():
            subject = self._subject_locked(patient_id, case_id, organization, purpose)
            existing = self.registry._fetchone(
                "SELECT intent_sha256,source_id FROM clinical_source.fhir_laboratory_commands "
                "WHERE case_id=%s AND request_key=%s", (case_id, request_key))
            if existing is not None:
                if existing[0] != intent:
                    raise PatientRegistryConflict("FHIR laboratory request key reused with changed intent")
                return complete(self._receipt_locked(existing[1], duplicate=True))

            parsed = prepare_bundle(raw, expected_subject_reference=subject)
            if parsed.report_reference is None:
                raise PatientRegistryConflict("Persisted FHIR laboratory source requires one final DiagnosticReport")
            document_id = _document_id(parsed.report_reference)
            old = self.registry._fetchone(
                "SELECT source_id,version,sha256,kind,event_date,specimen_id "
                "FROM clinical_source.source_versions WHERE case_id=%s AND document_id=%s "
                "ORDER BY version DESC LIMIT 1", (case_id, document_id))
            seen = self.registry._fetchone(
                "SELECT source_id FROM clinical_source.source_versions "
                "WHERE case_id=%s AND document_id=%s AND sha256=%s",
                (case_id, document_id, digest))
            if seen is not None:
                self.registry._execute(
                    "INSERT INTO clinical_source.fhir_laboratory_commands "
                    "(case_id,request_key,intent_sha256,source_id,result,actor,purpose) "
                    "VALUES (%s,%s,%s,%s,'duplicate',%s,%s)",
                    (case_id, request_key, intent, seen[0], actor, purpose))
                return complete(self._receipt_locked(seen[0], duplicate=True))

            if old is None:
                if expected_previous_source_id is not None:
                    raise PatientRegistryConflict("First FHIR laboratory source cannot declare a predecessor")
            else:
                if expected_previous_source_id != old[0]:
                    raise PatientRegistryConflict("Changed FHIR laboratory source requires exact current predecessor")
                previous = self.registry._fetchone(
                    "SELECT specimen_reference,specimen_collected_at,report_reference "
                    "FROM clinical_source.fhir_laboratory_sources WHERE source_id=%s", (old[0],))
                if old[3] != "laboratory" or previous is None:
                    raise PatientRegistryConflict("Document format cannot change across intake owners")
                if (previous[0], previous[1], previous[2]) != (
                        parsed.specimen_reference, parsed.specimen_collected_at, parsed.report_reference):
                    raise PatientRegistryConflict("FHIR laboratory amendment cannot retarget specimen or report identity")

            version = old[1] + 1 if old else 1
            source_id = "SRC-" + uuid.uuid4().hex.upper()
            if old is not None:
                self.registry._execute(
                    "UPDATE clinical_source.source_versions SET state='superseded' "
                    "WHERE source_id=%s AND case_id=%s AND state='current'", (old[0], case_id))
            event_date = _day(parsed.specimen_collected_at)
            issued_at = max(_day(row["issued_at"]) for row in parsed.observations)
            self.registry._execute(
                "INSERT INTO clinical_source.source_versions "
                "(source_id,case_id,document_id,version,sha256,raw,kind,event_date,issued_at,"
                "specimen_id,state,supersedes_id) VALUES "
                "(%s,%s,%s,%s,%s,%s,'laboratory',%s::date,%s::date,%s,'current',%s)",
                (source_id, case_id, document_id, version, digest, raw, event_date, issued_at,
                 parsed.specimen_reference, old[0] if old else None))
            self.registry._execute(
                "INSERT INTO clinical_source.fhir_laboratory_sources "
                "(source_id,case_id,subject_reference,specimen_reference,specimen_type_text,"
                "specimen_collected_at,report_reference,parser_contract,clinical_review) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'oi.fhir-r4-laboratory-source/1','not_performed')",
                (source_id, case_id, parsed.subject_reference, parsed.specimen_reference,
                 parsed.specimen_type_text, parsed.specimen_collected_at, parsed.report_reference))
            for ordinal, row in enumerate(parsed.observations, 1):
                self.registry._execute(
                    "INSERT INTO clinical_source.fhir_laboratory_observations "
                    "(source_id,ordinal,observation_reference,loinc_code,effective_at,issued_at,status,"
                    "value_text,unit_code,absent_reason,source_reported,clinical_review) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,'not_performed')",
                    (source_id, ordinal, row["reference"], row["loinc_code"], row["effective_at"],
                     row["issued_at"], row["status"], row["value_text"], row["unit_code"],
                     row["absent_reason"]))
            self.registry._execute(
                "INSERT INTO clinical_source.fhir_laboratory_commands "
                "(case_id,request_key,intent_sha256,source_id,result,actor,purpose) "
                "VALUES (%s,%s,%s,%s,'imported',%s,%s)",
                (case_id, request_key, intent, source_id, actor, purpose))
            self.registry.append_event(
                patient_id, "source.fhir_laboratory.imported", case_id=case_id,
                source_id=source_id, version=version, observation_count=len(parsed.observations),
                actor=actor)
            return complete(self._receipt_locked(source_id, duplicate=False))

    def validate_original_row_locked(self, row: dict) -> bytes:
        if not self._available():
            raise RuntimeError("FHIR laboratory owner unavailable")
        supplied = row["raw"]
        if not isinstance(supplied, (bytes, bytearray, memoryview)):
            raise RuntimeError("Stored FHIR laboratory original unavailable")
        raw = bytes(supplied)
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise RuntimeError("Stored FHIR laboratory digest differs")
        metadata = self.registry._fetchone(
            "SELECT case_id,subject_reference,specimen_reference,specimen_type_text,"
            "specimen_collected_at,report_reference,parser_contract,clinical_review "
            "FROM clinical_source.fhir_laboratory_sources WHERE source_id=%s", (row["source_id"],))
        if metadata is None or metadata[0] != row["case_id"] or metadata[6:] != (
                "oi.fhir-r4-laboratory-source/1", "not_performed"):
            raise RuntimeError("Stored FHIR laboratory metadata differs")
        parsed = prepare_laboratory_bundle(raw, expected_subject_reference=metadata[1])
        if parsed.report_reference is None:
            raise RuntimeError("Stored FHIR laboratory report identity missing")
        expected_document = _document_id(parsed.report_reference)
        issued_day = max(_day(item["issued_at"]) for item in parsed.observations)
        if (row["kind"] != "laboratory" or row["document_id"] != expected_document
                or row["event_date"].isoformat() != _day(parsed.specimen_collected_at)
                or row["issued_at"].isoformat() != issued_day
                or row["specimen_id"] != parsed.specimen_reference
                or metadata[2:6] != (parsed.specimen_reference, parsed.specimen_type_text,
                                     parsed.specimen_collected_at, parsed.report_reference)):
            raise RuntimeError("Stored FHIR laboratory source context differs")
        version = row["version"]
        if type(version) is not int or version < 1 or row["state"] not in ("current","superseded"):
            raise RuntimeError("Stored FHIR laboratory version differs")
        if version == 1:
            if row["supersedes_id"] is not None:
                raise RuntimeError("Stored FHIR laboratory first version has predecessor")
        else:
            previous = self.registry._fetchone(
                "SELECT source_id,case_id,document_id,version,kind,event_date,specimen_id,state "
                "FROM clinical_source.source_versions WHERE source_id=%s AND case_id=%s",
                (row["supersedes_id"], row["case_id"]))
            if previous != (row["supersedes_id"], row["case_id"], row["document_id"], version - 1,
                            "laboratory", row["event_date"], row["specimen_id"], "superseded"):
                raise RuntimeError("Stored FHIR laboratory lineage differs")
        stored = self.registry._fetchall(
            "SELECT ordinal,observation_reference,loinc_code,effective_at,issued_at,status,"
            "value_text,unit_code,absent_reason,source_reported,clinical_review "
            "FROM clinical_source.fhir_laboratory_observations WHERE source_id=%s ORDER BY ordinal",
            (row["source_id"],))
        expected = [
            (ordinal, item["reference"], item["loinc_code"], item["effective_at"], item["issued_at"],
             item["status"], item["value_text"], item["unit_code"], item["absent_reason"],
             True, "not_performed")
            for ordinal, item in enumerate(parsed.observations, 1)
        ]
        if stored != expected:
            raise RuntimeError("Stored FHIR laboratory observations differ")
        return raw

    def current_projection_locked(self, case_id: str) -> list[dict]:
        if not self._available():
            return []
        source_rows = self.registry._fetchall(
            "SELECT s.raw,s.sha256,s.document_id,s.version,s.state,s.source_id,s.case_id,s.kind,"
            "s.event_date,s.issued_at,s.specimen_id,s.supersedes_id "
            "FROM clinical_source.source_versions s "
            "JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id "
            "WHERE s.case_id=%s AND s.state='current' ORDER BY s.document_id,s.version", (case_id,))
        fields=("raw","sha256","document_id","version","state","source_id","case_id","kind",
                "event_date","issued_at","specimen_id","supersedes_id")
        for source in source_rows:
            self.validate_original_row_locked(dict(zip(fields, source)))
        rows = self.registry._fetchall(
            "SELECT s.source_id,s.document_id,s.version,s.sha256,o.observation_reference,o.loinc_code,"
            "o.effective_at,o.issued_at,o.status,o.value_text,o.unit_code,o.absent_reason,"
            "f.specimen_reference,o.source_reported,o.clinical_review "
            "FROM clinical_source.source_versions s "
            "JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id "
            "JOIN clinical_source.fhir_laboratory_observations o ON o.source_id=s.source_id "
            "WHERE s.case_id=%s AND s.state='current' ORDER BY o.effective_at,s.document_id,s.version,o.ordinal",
            (case_id,))
        keys=("source_id","document_id","document_version","source_sha256","observation_reference",
              "loinc_code","effective_at","issued_at","status","value_text","unit_code",
              "absent_reason","specimen_reference","source_reported","clinical_review")
        return [dict(zip(keys,row)) for row in rows]
