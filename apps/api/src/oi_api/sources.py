"""PG16 persistence port of the first-party CaseStore's original-source contract.

Structured report versions 1 and 2 accept independently authored synthetic inputs. The original
bytes and source-line assertions have one H1 owner, linked by FK to the H1
canonical case binding. Source quotes remain unreviewed; no patient data,
clinical interpretation or automatic research/medical authorization is added.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import TypeAdapter

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.store import InvalidInput, parse_report

from .case_bindings import _case_id
from .record_requests import PostgresRecordRequests
from .source_integrity import (
    SourceIntegrityError, validate_fhir_laboratory_original,
    validate_original, validate_snapshot,
)

_TIMESTAMP_JSON = TypeAdapter(datetime)
PreparedResponse = TypeVar("PreparedResponse")


def _source_id(value: object) -> str:
    import re
    if type(value) is not str or re.fullmatch(r"SRC-[0-9A-F]{32}", value) is None:
        raise PatientRegistryError("Invalid synthetic source identifier")
    return value


class PostgresSourceVersions:
    """One original document/version/assertion writer, no duplicate source truth."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical patient registry required")
        self.registry = registry

    @staticmethod
    def receipt_cutoff(value: str) -> datetime:
        """Explicit receipt time, at PostgreSQL's microsecond precision."""
        if not isinstance(value, str) or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value
        ) is None:
            raise PatientRegistryError("Use an explicit RFC3339 receipt cutoff")
        try:
            cutoff = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise PatientRegistryError("Invalid receipt cutoff") from None
        if cutoff > datetime.now(timezone.utc):
            raise PatientRegistryError("Receipt cutoff cannot be in the future")
        return cutoff

    @staticmethod
    def _history(index: dict, cutoff: datetime) -> dict:
        # This is received-time source membership, not a reconstruction of past
        # assertions, clinical decisions, grants, or external record availability.
        selected = {}
        previous = {}
        for source in sorted(index["sources"], key=lambda s: (s["document_id"], s["version"])):
            received = datetime.fromisoformat(source["received_at"].replace("Z", "+00:00"))
            document = source["document_id"]
            if document in previous and received < previous[document]:
                raise SourceIntegrityError("Source receipt chronology is inconsistent")
            previous[document] = received
            if received <= cutoff:
                # Today's mutable supersession label would leak later context.
                selected[document] = {key: value for key, value in source.items() if key != "state"}
        return {
            "contract": "oi.synthetic-source-history/1",
            "patient_id": index["patient_id"], "case_id": index["case_id"],
            "received_through": _TIMESTAMP_JSON.dump_python(cutoff, mode="json"),
            "cutoff_basis": "platform_received_at", "selection": "latest_version_per_document",
            "sources": list(selected.values()), "synthetic": True, "clinical_interpretation": False,
        }

    def _document_filter(self) -> str:
        # Direct migration fixtures legitimately seed old structured-only
        # schemas. HTTP separately requires the exact current migration head.
        exists = self.registry._fetchone("SELECT to_regclass('clinical_source.document_intakes')")[0]
        return ("AND source_id NOT IN (SELECT source_id FROM clinical_source.document_intakes) "
                if exists is not None else "")

    def _is_reviewed(self, source_id: str) -> bool:
        return bool(self._document_filter() and self.registry._fetchone(
            "SELECT source_id FROM clinical_source.document_intakes WHERE source_id=%s", (source_id,)))

    def _binding(self, patient_id: str, case_id: str, organization: str, purpose: str) -> int:
        PostgresRecordRequests(self.registry)._active_patient(patient_id, organization)
        # Row lock serializes same-case imports and revocation, including
        # the first document version before any source row can be locked.
        row = self.registry._fetchone(
            "SELECT patient_id,origin_org,status,purpose,revision FROM coordination.patient_case_bindings "
            "WHERE case_id=%s FOR UPDATE", (case_id,)
        )
        if (row is None or row[0] != patient_id or row[1] != organization
                or row[2] != "active" or row[3] != purpose):
            raise PatientRegistryDenied("Case/source mapping unavailable")
        return row[4]

    def _read_receipt(self, patient_id: str, case_id: str, *, actor: str, purpose: str,
                      binding_revision: int, event: str, receipt_id: str,
                      recheck_authority: Callable[[], None],
                      **references) -> str:
        """Authorize prepared disclosure, not guaranteed network delivery.

        The owner still holds the active-patient and case-binding locks. A
        callback or immutable-event failure aborts this transaction and withholds
        the result. External authority can change after this last check; it is
        not transactionally locked with PostgreSQL or HTTP delivery.
        """
        recheck_authority()
        self.registry.append_event(
            patient_id, event, receipt_id=receipt_id, case_id=case_id,
            actor=_key(actor, "actor"), purpose=purpose,
            binding_revision=binding_revision, **references,
        )
        # The event append can perform SQL I/O while the external grant changes.
        # Reauthenticate after persistence and before the transaction commits;
        # denial rolls back the event and withholds the prepared source/document.
        recheck_authority()
        return receipt_id

    def _sources(self, case_id: str) -> list[dict]:
        rows = self.registry._fetchall(
            "SELECT source_id,document_id,version,sha256,kind,event_date,issued_at,"
            "received_at,specimen_id,state,supersedes_id "
            "FROM clinical_source.source_versions WHERE case_id=%s "
            + self._document_filter() +
            "ORDER BY document_id,version", (case_id,),
        )
        return self._source_metadata(rows)

    @staticmethod
    def _source_metadata(rows) -> list[dict]:
        return [
            {"source_id": r[0], "document_id": r[1], "version": r[2],
             "sha256": r[3], "kind": r[4], "event_date": r[5].isoformat(),
             "issued_at": r[6].isoformat(),
             # Use the same datetime serialization as the HTTP response model:
             # UTC becomes Z rather than +00:00 before the audit digest is made.
             "received_at": _TIMESTAMP_JSON.dump_python(r[7], mode="json"),
             "specimen_id": r[8], "state": r[9], "supersedes_id": r[10]}
            for r in rows
        ]

    def _validate_index(self, case_id: str, sources: list[dict], assertions: list[tuple]) -> dict[tuple[str, int], dict]:
        # One additional case-scoped read, not one query per finding. Existing
        # patient/binding locks still cover materialization and validation.
        rows = self.registry._fetchall(
            "SELECT source_id,document_id,version,sha256,kind,event_date,issued_at,"
            "received_at,specimen_id,state,supersedes_id,raw "
            "FROM clinical_source.source_versions WHERE case_id=%s "
            + self._document_filter() +
            "ORDER BY document_id,version", (case_id,),
        )
        if self._source_metadata(rows) != sources:
            raise SourceIntegrityError("Stored source snapshot integrity check failed")
        fields = ("source_id", "document_id", "version", "sha256", "kind", "event_date",
                  "issued_at", "received_at", "specimen_id", "state", "supersedes_id", "raw")
        originals = [dict(zip(fields, row), case_id=case_id) for row in rows]
        fhir_sources = {}
        fhir_observations = {}
        table = self.registry._fetchone(
            "SELECT to_regclass('clinical_source.fhir_laboratory_sources')")[0]
        if table is not None:
            metadata_rows = self.registry._fetchall(
                "SELECT f.source_id,f.source_organization,f.source_system,f.subject_reference,"
                "f.specimen_reference,f.specimen_type_text,f.specimen_collected_at,"
                "f.report_reference,f.report_effective_at,f.report_issued_at,f.fhir_release,"
                "f.profile_contract,f.observation_count "
                "FROM clinical_source.fhir_laboratory_sources f "
                "JOIN clinical_source.source_versions s ON s.source_id=f.source_id "
                "WHERE s.case_id=%s ORDER BY s.document_id,s.version", (case_id,))
            metadata_fields = (
                "source_id","source_organization","source_system","subject_reference",
                "specimen_reference","specimen_type_text","specimen_collected_at",
                "report_reference","report_effective_at","report_issued_at","fhir_release",
                "profile_contract","observation_count")
            fhir_sources = {row[0]: dict(zip(metadata_fields, row)) for row in metadata_rows}
            observation_rows = self.registry._fetchall(
                "SELECT o.source_id,o.observation_reference,o.position,o.loinc_code,"
                "o.effective_at,o.issued_at,o.status,o.value_text,o.unit_code,o.absent_reason,"
                "o.source_reported,o.clinical_review "
                "FROM clinical_source.fhir_laboratory_observations o "
                "JOIN clinical_source.source_versions s ON s.source_id=o.source_id "
                "WHERE s.case_id=%s ORDER BY s.document_id,s.version,o.position", (case_id,))
            observation_fields = (
                "source_id","observation_reference","position","loinc_code","effective_at",
                "issued_at","status","value_text","unit_code","absent_reason",
                "source_reported","clinical_review")
            for row in observation_rows:
                item = dict(zip(observation_fields, row))
                fhir_observations.setdefault(row[0], []).append(item)
        return validate_snapshot(
            originals, assertions, requested_case_id=case_id,
            fhir_sources=fhir_sources, fhir_observations=fhir_observations)

    def list(self, patient_id: str, case_id: str, *, organization: str,
             actor: str, purpose: str, recheck_authority: Callable[[], None],
             received_through: str | None = None,
             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Prepare a trusted read view before its final authority check and commit.

        ``prepare_response`` is application-owned projection/DTO validation, not
        an external tool or model. It runs under the existing locks. Its receipt
        ID is reserved in memory and becomes a receipt only if the subsequent
        authority check, event insertion and transaction commit all succeed.
        """
        with self.registry.transaction():
            return self.list_locked(
                patient_id, case_id, organization=organization, actor=actor,
                purpose=purpose, recheck_authority=recheck_authority,
                received_through=received_through,
                prepare_response=prepare_response,
            )

    def list_locked(self, patient_id: str, case_id: str, *, organization: str,
                    actor: str, purpose: str, recheck_authority: Callable[[], None],
                    received_through: str | None = None,
                    prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Prepare and audit the same source view inside the caller's transaction.

        Question persistence uses this entry point so its write, prepared DTO,
        final authority check and source access receipt commit together. This
        helper never starts or commits a second transaction.
        """
        if not self.registry._transaction_active:
            raise PatientRegistryError("Source preparation requires caller transaction")
        cutoff = self.receipt_cutoff(received_through) if received_through is not None else None
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        binding_revision = self._binding(patient_id, case_id, organization, purpose)
        sources = self._sources(case_id)
        rows = self.registry._fetchall(
            "SELECT a.source_id,a.finding_key,a.certainty,a.quote,a.source_line "
            "FROM clinical_source.assertions a "
            "JOIN clinical_source.source_versions s ON s.source_id=a.source_id "
            "WHERE s.case_id=%s AND s.state='current' "
            "ORDER BY s.document_id,s.version,a.source_line", (case_id,),
        )
        oncology_by_line = self._validate_index(case_id, sources, rows)
        findings = []
        for source_id, key, state, quote, line in rows:
            finding = {"source_id": source_id, "finding_key": key, "reported_state": state,
                       "source_statement": quote, "source_line": line,
                       "clinical_review_state": "not_established"}
            if (source_id, line) in oncology_by_line:
                finding["oncology"] = oncology_by_line[(source_id, line)]
            findings.append(finding)
        result = {
            "contract": "oi.synthetic-original-sources/1",
            "patient_id": patient_id, "case_id": case_id,
            "sources": sources, "source_reported_assertions": findings,
            "synthetic": True, "clinical_interpretation": False,
            "research_review_invalidation_integrated": False,
        }
        if cutoff is not None:
            result = self._history(result, cutoff)
        # This receipt describes canonical source context, not delivery or
        # question review. Projection and receipt IDs do not change the digest.
        digest = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
        receipt_id = "ACCESS-" + uuid.uuid4().hex.upper()
        result["access_receipt_id"] = receipt_id
        prepared = prepare_response(result) if prepare_response is not None else result
        self._read_receipt(
            patient_id, case_id, actor=actor, purpose=purpose,
            binding_revision=binding_revision, event="source.read_authorized",
            receipt_id=receipt_id,
            recheck_authority=recheck_authority, snapshot_sha256=digest,
            source_count=len(result["sources"]), assertion_count=0 if cutoff is not None else len(rows),
            **({"received_through": result["received_through"]} if cutoff is not None else {}),
        )
        return prepared

    def original(self, patient_id: str, case_id: str, source_id: str, *,
                 organization: str, actor: str, purpose: str,
                 recheck_authority: Callable[[], None],
                 prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Prepare the original under owner locks before authorizing disclosure.

        The application-owned callback includes DTO validation and HTTP encoding.
        Preparation failure withholds the original and rolls back its receipt.
        """
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        source_id = _source_id(source_id)
        organization = _key(organization, "organization")
        with self.registry.transaction():
            binding_revision = self._binding(patient_id, case_id, organization, purpose)
            if self._is_reviewed(source_id):
                raise PatientRegistryDenied("Use the reviewed-document original endpoint")
            stored, raw = self._validated_original(case_id, source_id)
            result = {"source_id": source_id, "case_id": case_id,
                    "document_id": stored["document_id"], "version": stored["version"],
                    "state": stored["state"], "sha256": stored["sha256"],
                    "original_text": raw.decode("utf-8"),
                    "synthetic": True, "clinical_review_state": "not_established"}
            result["access_receipt_id"] = "ACCESS-" + uuid.uuid4().hex.upper()
            prepared = prepare_response(result) if prepare_response is not None else result
            self._read_receipt(
                patient_id, case_id, actor=actor, purpose=purpose,
                binding_revision=binding_revision, event="source.original_read_authorized",
                receipt_id=result["access_receipt_id"],
                recheck_authority=recheck_authority, source_id=source_id,
                sha256=stored["sha256"], source_version=stored["version"], source_state=stored["state"],
            )
            return prepared

    def _validated_original(self, case_id: str, source_id: str) -> tuple[dict, bytes]:
        """Reuse exact-original validation inside the caller's locked transaction.

        No authorization or transaction is opened here. Both report and image
        owners first acquire the canonical patient/case locks through _binding.
        Historical report access remains valid; the image owner adds freshness.
        """
        row = self.registry._fetchone(
            "SELECT raw,sha256,document_id,version,state,source_id,case_id,"
            "kind,event_date,issued_at,specimen_id,supersedes_id "
            "FROM clinical_source.source_versions WHERE case_id=%s AND source_id=%s",
            (case_id, source_id),
        )
        if row is None:
            raise PatientRegistryDenied("Source unavailable")
        stored = dict(zip(("raw", "sha256", "document_id", "version", "state", "source_id",
                           "case_id", "kind", "event_date", "issued_at", "specimen_id", "supersedes_id"), row))
        predecessor = None
        if stored["supersedes_id"] is not None:
            previous = self.registry._fetchone(
                "SELECT source_id,case_id,document_id,version,kind,event_date,specimen_id,state "
                "FROM clinical_source.source_versions WHERE source_id=%s AND case_id=%s",
                (stored["supersedes_id"], case_id),
            )
            if previous is not None:
                predecessor = dict(zip(("source_id", "case_id", "document_id", "version", "kind",
                                        "event_date", "specimen_id", "state"), previous))
        lab_table = self.registry._fetchone(
            "SELECT to_regclass('clinical_source.fhir_laboratory_sources')")[0]
        if lab_table is not None:
            metadata_row = self.registry._fetchone(
                "SELECT source_id,source_organization,source_system,subject_reference,"
                "specimen_reference,specimen_type_text,specimen_collected_at,"
                "report_reference,report_effective_at,report_issued_at,fhir_release,"
                "profile_contract,observation_count "
                "FROM clinical_source.fhir_laboratory_sources WHERE source_id=%s",
                (source_id,))
            if metadata_row is not None:
                metadata_fields = (
                    "source_id","source_organization","source_system","subject_reference",
                    "specimen_reference","specimen_type_text","specimen_collected_at",
                    "report_reference","report_effective_at","report_issued_at","fhir_release",
                    "profile_contract","observation_count")
                metadata = dict(zip(metadata_fields, metadata_row))
                observation_rows = self.registry._fetchall(
                    "SELECT source_id,observation_reference,position,loinc_code,effective_at,"
                    "issued_at,status,value_text,unit_code,absent_reason,source_reported,"
                    "clinical_review FROM clinical_source.fhir_laboratory_observations "
                    "WHERE source_id=%s ORDER BY position", (source_id,))
                observation_fields = (
                    "source_id","observation_reference","position","loinc_code","effective_at",
                    "issued_at","status","value_text","unit_code","absent_reason",
                    "source_reported","clinical_review")
                observations = [dict(zip(observation_fields, row)) for row in observation_rows]
                return stored, validate_fhir_laboratory_original(
                    stored, metadata, observations, requested_case_id=case_id,
                    predecessor=predecessor)
        return stored, validate_original(stored, requested_case_id=case_id, predecessor=predecessor)

    def import_original(self, patient_id: str, case_id: str, original: bytes, *,
                        organization: str, actor: str, purpose: str,
                        recheck_authority: Callable[[], None],
                        prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Prepare every success and refresh authority before source commit.

        Response preparation is application-owned work, including serialization
        at the HTTP boundary. Failure rolls back tentative imports, amendment
        state, assertions, quarantine and events. Duplicate exits use the same
        boundary before disclosing a historical source identity.
        """
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if purpose not in ("operations", "research"):
            raise PatientRegistryError("Unsupported synthetic source purpose")
        # Reuse the original CaseStore parser; never infer a finding from
        # free text, rewrite an external Patient header or normalize LF/UTF-8.
        try:
            parsed = parse_report(original, allow_oncology=True)
        except InvalidInput:
            raise PatientRegistryError("Unsupported fictional report format") from None
        digest = hashlib.sha256(original).hexdigest()

        def complete(result):
            prepared = prepare_response(result) if prepare_response is not None else result
            recheck_authority()
            return prepared

        with self.registry.transaction():
            self._binding(patient_id, case_id, organization, purpose)
            if parsed.patient_id != case_id:
                # Preserve the wrong-case original only in the quarantine
                # owner, without publishing clinical observations or receipts.
                existing = self.registry._fetchone(
                    "SELECT quarantine_id FROM clinical_source.quarantine "
                    "WHERE target_case_id=%s AND sha256=%s",
                    (case_id, digest),
                )
                if existing is not None:
                    return complete({"result": "quarantined", "duplicate": True,
                                     "source_id": None, "version": None})
                self.registry._execute(
                    "INSERT INTO clinical_source.quarantine "
                    "(target_case_id,declared_case_id,sha256,raw,reason) "
                    "VALUES (%s,%s,%s,%s,'case_mismatch')",
                    (case_id, parsed.patient_id, digest, original),
                )
                self.registry.append_event(
                    patient_id, "source.original.quarantined",
                    case_id=case_id, actor=actor,
                )
                return complete({"result": "quarantined", "duplicate": False,
                                 "source_id": None, "version": None})
            old = self.registry._fetchone(
                "SELECT source_id,version,sha256,kind,event_date,specimen_id "
                "FROM clinical_source.source_versions "
                "WHERE case_id=%s AND document_id=%s "
                "ORDER BY version DESC LIMIT 1", (case_id, parsed.document_id),
            )
            if old and self._is_reviewed(old[0]):
                raise PatientRegistryConflict("Document format cannot change across intake owners")
            previously_seen = self.registry._fetchone(
                "SELECT source_id,version FROM clinical_source.source_versions "
                "WHERE case_id=%s AND document_id=%s AND sha256=%s",
                (case_id, parsed.document_id, digest),
            )
            if previously_seen is not None:
                return complete({"result": "duplicate", "duplicate": True,
                                 "source_id": previously_seen[0], "version": previously_seen[1]})
            if old is not None and old[2] == digest:
                return complete({"result": "duplicate", "duplicate": True,
                                 "source_id": old[0], "version": old[1]})
            if old is not None and parsed.amends != (parsed.document_id, old[1]):
                raise PatientRegistryConflict("Changed original requires latest explicit amendment")
            if old is None and parsed.amends is not None:
                raise PatientRegistryConflict("First document cannot amend an absent original")
            if old is not None and (
                old[3], old[4].isoformat(), old[5]
            ) != (parsed.kind, parsed.event_date, parsed.specimen_id):
                raise PatientRegistryConflict("Amendment cannot alter original event identity")
            version = (old[1] + 1) if old else 1
            source_id = "SRC-" + uuid.uuid4().hex.upper()
            if old is not None:
                self.registry._execute(
                    "UPDATE clinical_source.source_versions SET state='superseded' "
                    "WHERE source_id=%s AND case_id=%s AND state='current'",
                    (old[0], case_id),
                )
            self.registry._execute(
                "INSERT INTO clinical_source.source_versions "
                "(source_id,case_id,document_id,version,sha256,raw,kind,event_date,"
                "issued_at,specimen_id,state,supersedes_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::date,%s::date,%s,'current',%s)",
                (source_id, case_id, parsed.document_id, version, digest, original,
                 parsed.kind, parsed.event_date, parsed.issued_at,
                 parsed.specimen_id, old[0] if old else None),
            )
            for assertion in parsed.findings:
                self.registry._execute(
                    "INSERT INTO clinical_source.assertions "
                    "(source_id,finding_key,certainty,quote,source_line) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (source_id, assertion.key, assertion.state,
                     assertion.quote, assertion.line),
                )
            self.registry.append_event(
                patient_id, "source.original.imported",
                case_id=case_id, source_id=source_id,
                version=version, actor=actor,
            )
            return complete({"result": "imported", "duplicate": False,
                             "source_id": source_id, "version": version})
