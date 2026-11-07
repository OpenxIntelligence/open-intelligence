"""Native FHIR R4 laboratory custody under the canonical source/version owner."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
import re
from typing import TypeVar
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id, CanonicalCaseBindings
from .laboratory_fhir_r4 import PreparedLaboratoryBundle
from .sources import PostgresSourceVersions, _source_id

PreparedResponse = TypeVar("PreparedResponse")
_DOCUMENT_ID = re.compile(r"[A-Z][A-Z0-9-]{1,39}\Z")


class PostgresLaboratoryFHIR:
    """One modality adapter; source_versions remains the source of custody truth."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical patient registry required")
        self.registry = registry
        self.sources = PostgresSourceVersions(registry)

    @staticmethod
    def _document_id(report_reference: str | None) -> str:
        if type(report_reference) is not str or not report_reference.startswith("DiagnosticReport/"):
            raise PatientRegistryError("Persisted laboratory bundle requires one final DiagnosticReport")
        value = report_reference.split("/", 1)[1]
        if _DOCUMENT_ID.fullmatch(value) is None:
            raise PatientRegistryError("FHIR report identifier is outside the canonical source profile")
        return value

    @staticmethod
    def _specimen_id(reference: str) -> str:
        if type(reference) is not str or not reference.startswith("Specimen/"):
            raise PatientRegistryError("FHIR specimen identity unavailable")
        value = reference.split("/", 1)[1]
        if not value or len(value) > 128:
            raise PatientRegistryError("FHIR specimen identity unavailable")
        return value

    @staticmethod
    def _source_date(value: str | None, field: str) -> str:
        if type(value) is not str:
            raise PatientRegistryError(field + " unavailable")
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            raise PatientRegistryError(field + " unavailable") from None

    def _binding_metadata(self, patient_id: str, case_id: str, organization: str,
                          purpose: str, source_identity_id: str | None = None) -> tuple[int, str, str, str]:
        revision = self.sources._binding(patient_id, case_id, organization, purpose)
        row = CanonicalCaseBindings(self.registry).source_identity(
            patient_id, case_id, organization=organization, purpose=purpose,
            identity_id=source_identity_id)
        return revision, row[0], row[1], row[2]

    def _receipt(self, source_id: str, *, duplicate: bool) -> dict:
        row = self.registry._fetchone(
            "SELECT s.version,count(o.observation_reference),s.sha256 "
            "FROM clinical_source.source_versions s "
            "JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id "
            "LEFT JOIN clinical_source.fhir_laboratory_observations o ON o.source_id=f.source_id "
            "WHERE s.source_id=%s GROUP BY s.version,s.sha256",
            (source_id,),
        )
        if row is None:
            raise PatientRegistryError("FHIR laboratory receipt integrity failure")
        return {"source_id": source_id, "version": row[0],
                "observation_count": row[1], "duplicate": duplicate,
                "original_sha256": row[2]}

    def import_bundle(self, patient_id: str, case_id: str, prepared: PreparedLaboratoryBundle, *,
                      organization: str, actor: str, purpose: str, request_key: str,
                      expected_previous_source_id: str | None,
                      recheck_authority: Callable[[], None],
                      source_identity_id: str | None = None,
                      prepare_response: Callable[[dict], PreparedResponse] | None = None
                      ) -> dict | PreparedResponse:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        if purpose != "operations":
            raise PatientRegistryDenied("FHIR laboratory import unavailable")
        if not isinstance(prepared, PreparedLaboratoryBundle) or prepared.persisted:
            raise PatientRegistryError("Validated unpersisted FHIR laboratory bundle required")
        expected_previous_source_id = (
            _source_id(expected_previous_source_id)
            if expected_previous_source_id is not None else None
        )
        document_id = self._document_id(prepared.report_reference)
        specimen_id = self._specimen_id(prepared.specimen_reference)
        event_date = self._source_date(prepared.report_effective_at, "FHIR report effective date")
        issued_at = self._source_date(prepared.report_issued_at, "FHIR report issued date")
        intent = _digest({
            **({"source_identity_id": source_identity_id} if source_identity_id is not None else {}),
            "operation": "fhir_laboratory_import",
            "patient_id": patient_id, "case_id": case_id,
            "organization": organization, "actor": actor, "purpose": purpose,
            "source_sha256": prepared.source_sha256,
            "report_reference": prepared.report_reference,
            "expected_previous_source_id": expected_previous_source_id,
        })

        def complete(result):
            value = prepare_response(result) if prepare_response is not None else result
            recheck_authority()
            return value

        with self.registry.transaction():
            _, source_org, source_system, source_subject = self._binding_metadata(
                patient_id, case_id, organization, purpose, source_identity_id)
            if prepared.subject_reference != "Patient/" + source_subject:
                raise PatientRegistryDenied("Mapped FHIR subject changed")

            command = self.registry._fetchone(
                "SELECT request_digest,source_id FROM clinical_source.fhir_laboratory_commands "
                "WHERE origin_org=%s AND case_id=%s AND request_key=%s",
                (organization, case_id, request_key),
            )
            if command is not None:
                if command[0] != intent:
                    raise PatientRegistryConflict("request key reused with different laboratory intent")
                return complete(self._receipt(command[1], duplicate=True))

            old = self.registry._fetchone(
                "SELECT s.source_id,s.version,s.sha256,s.kind,s.event_date,s.specimen_id,"
                "f.source_organization,f.source_system,f.subject_reference,"
                "f.specimen_reference,f.report_reference "
                "FROM clinical_source.source_versions s "
                "LEFT JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id "
                "WHERE s.case_id=%s AND s.document_id=%s AND s.state='current' FOR UPDATE OF s",
                (case_id, document_id),
            )
            if old is not None and old[6] is None:
                raise PatientRegistryConflict("Document format cannot change across intake owners")
            if old is not None and tuple(old[6:9]) != (source_org, source_system, prepared.subject_reference):
                raise PatientRegistryConflict("Report identifier belongs to another source identity")
            if old is None and expected_previous_source_id is not None:
                raise PatientRegistryConflict("First FHIR source cannot amend an absent original")
            if old is not None and expected_previous_source_id is not None and expected_previous_source_id != old[0]:
                raise PatientRegistryConflict("FHIR amendment predecessor is not current")

            seen = self.registry._fetchone(
                "SELECT s.source_id,s.version,s.state FROM clinical_source.source_versions s "
                "JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=s.source_id "
                "WHERE s.case_id=%s AND s.document_id=%s AND s.sha256=%s "
                "ORDER BY s.version DESC LIMIT 1",
                (case_id, document_id, prepared.source_sha256),
            )
            if seen is not None:
                # A prior request key may always replay its own immutable historical
                # receipt (handled above). A *new* request key must never resurrect
                # superseded bytes as though they were the current laboratory source.
                if seen[2] != "current":
                    raise PatientRegistryConflict("Historical FHIR source cannot be re-imported as current")
                if expected_previous_source_id is not None and old is not None and expected_previous_source_id != old[0]:
                    raise PatientRegistryConflict("FHIR amendment predecessor is not current")
                self.registry._execute(
                    "INSERT INTO clinical_source.fhir_laboratory_commands "
                    "(origin_org,patient_id,case_id,request_key,request_digest,source_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (organization, patient_id, case_id, request_key, intent, seen[0]),
                )
                return complete(self._receipt(seen[0], duplicate=True))

            if old is not None:
                if expected_previous_source_id != old[0]:
                    raise PatientRegistryConflict("Changed FHIR original requires latest explicit amendment")
                if (old[3], old[4].isoformat(), old[5], old[6], old[7], old[8], old[9], old[10]) != (
                    "laboratory", event_date, specimen_id, source_org, source_system,
                    prepared.subject_reference, prepared.specimen_reference, prepared.report_reference,
                ):
                    raise PatientRegistryConflict("FHIR amendment cannot alter source event identity")
                version = old[1] + 1
            else:
                version = 1

            source_id = "SRC-" + uuid.uuid4().hex.upper()
            if old is not None:
                changed = self.registry._execute(
                    "UPDATE clinical_source.source_versions SET state='superseded' "
                    "WHERE source_id=%s AND case_id=%s AND state='current'",
                    (old[0], case_id),
                )
                if changed != 1:
                    raise PatientRegistryConflict("FHIR source state changed")

            self.registry._execute(
                "INSERT INTO clinical_source.source_versions "
                "(source_id,case_id,document_id,version,sha256,raw,kind,event_date,"
                "issued_at,specimen_id,state,supersedes_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,'laboratory',%s::date,%s::date,%s,'current',%s)",
                (source_id, case_id, document_id, version, prepared.source_sha256,
                 prepared.original_bytes, event_date, issued_at, specimen_id,
                 old[0] if old is not None else None),
            )
            self.registry._execute(
                "INSERT INTO clinical_source.fhir_laboratory_sources "
                "(source_id,source_organization,source_system,subject_reference,"
                "specimen_reference,specimen_type_text,specimen_collected_at,"
                "report_reference,report_effective_at,report_issued_at,fhir_release,"
                "profile_contract,observation_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s::timestamptz,%s,%s::timestamptz,"
                "%s::timestamptz,'R4','oi.fhir-r4-laboratory-custody/1',%s)",
                (source_id, source_org, source_system, prepared.subject_reference,
                 prepared.specimen_reference, prepared.specimen_type_text,
                 prepared.specimen_collected_at, prepared.report_reference,
                 prepared.report_effective_at, prepared.report_issued_at,
                 len(prepared.observations)),
            )
            for position, observation in enumerate(prepared.observations, 1):
                self.registry._execute(
                    "INSERT INTO clinical_source.fhir_laboratory_observations "
                    "(source_id,observation_reference,position,loinc_code,effective_at,"
                    "issued_at,status,value_text,unit_code,absent_reason,source_reported,"
                    "clinical_review) "
                    "VALUES (%s,%s,%s,%s,%s::timestamptz,%s::timestamptz,%s,%s,%s,%s,true,'not_performed')",
                    (source_id, observation["reference"], position,
                     observation["loinc_code"], observation["effective_at"],
                     observation["issued_at"], observation["status"],
                     observation["value_text"], observation["unit_code"],
                     observation["absent_reason"]),
                )
            self.registry._execute(
                "INSERT INTO clinical_source.fhir_laboratory_commands "
                "(origin_org,patient_id,case_id,request_key,request_digest,source_id) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (organization, patient_id, case_id, request_key, intent, source_id),
            )
            self.registry.append_event(
                patient_id, "source.original.imported",
                case_id=case_id, source_id=source_id, version=version,
                actor=actor, source_format="fhir-r4-laboratory",
            )
            return complete(self._receipt(source_id, duplicate=False))

    def current_observations_locked(self, case_id: str) -> list[dict]:
        return self.observations_for_sources_locked(case_id)

    def observations_for_sources_locked(self, case_id: str,
                                       source_ids: list[str] | None = None) -> list[dict]:
        """Read current rows, or exact sources from an already validated owner index."""
        if not self.registry._transaction_active:
            raise PatientRegistryError("Laboratory projection requires caller transaction")
        case_id = _case_id(case_id)
        if source_ids is not None and (type(source_ids) is not list or len(source_ids) > 512):
            raise PatientRegistryError("Invalid laboratory source selection")
        rows = self.registry._fetchall(
            "SELECT o.source_id,s.document_id,s.version,s.sha256,o.observation_reference,"
            "o.loinc_code,o.effective_at,o.issued_at,f.specimen_reference,"
            "f.specimen_type_text,f.specimen_collected_at,f.report_reference,o.status,"
            "o.value_text,o.unit_code,o.absent_reason "
            "FROM clinical_source.fhir_laboratory_observations o "
            "JOIN clinical_source.fhir_laboratory_sources f ON f.source_id=o.source_id "
            "JOIN clinical_source.source_versions s ON s.source_id=o.source_id "
            "WHERE s.case_id=%s AND "
            + ("s.state='current' " if source_ids is None else "s.source_id=ANY(%s) ") +
            "ORDER BY o.effective_at,s.document_id,s.version,o.position",
            (case_id,) if source_ids is None else (case_id, source_ids),
        )
        return [{
            "source_id": r[0], "document_id": r[1], "document_version": r[2],
            "source_sha256": r[3], "observation_reference": r[4],
            "loinc_code": r[5],
            "effective_at": r[6].isoformat(),
            "issued_at": r[7].isoformat(),
            "specimen_reference": r[8], "specimen_type_text": r[9],
            "specimen_collected_at": r[10].isoformat(),
            "report_reference": r[11], "status": r[12],
            "value_text": r[13], "unit_code": r[14], "absent_reason": r[15],
            "source_reported": True, "review_state": "not_established",
            "clinical_review": "not_performed", "clinical_meaning": None,
        } for r in rows]
