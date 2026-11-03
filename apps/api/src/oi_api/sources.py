"""PG16 persistence port of the first-party CaseStore's original-source contract.

Only independently authored OI-SYNTHETIC-REPORT/1 is accepted. The original
bytes and source-line assertions have one H1 owner, linked by FK to the H1
canonical case binding. Source quotes remain unreviewed; no patient data,
clinical interpretation or automatic research/medical authorization is added.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from pydantic import TypeAdapter

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.store import InvalidInput, parse_report

from .case_bindings import _case_id
from .record_requests import PostgresRecordRequests
from .source_integrity import SourceIntegrityError, validate_original, validate_snapshot

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
        return receipt_id

    def _sources(self, case_id: str) -> list[dict]:
        rows = self.registry._fetchall(
            "SELECT source_id,document_id,version,sha256,kind,event_date,issued_at,"
            "received_at,specimen_id,state,supersedes_id "
            "FROM clinical_source.source_versions WHERE case_id=%s "
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

    def _validate_index(self, case_id: str, sources: list[dict], assertions: list[tuple]) -> None:
        # One additional case-scoped read, not one query per finding. Existing
        # patient/binding locks still cover materialization and validation.
        rows = self.registry._fetchall(
            "SELECT source_id,document_id,version,sha256,kind,event_date,issued_at,"
            "received_at,specimen_id,state,supersedes_id,raw "
            "FROM clinical_source.source_versions WHERE case_id=%s "
            "ORDER BY document_id,version", (case_id,),
        )
        if self._source_metadata(rows) != sources:
            raise SourceIntegrityError("Stored source snapshot integrity check failed")
        fields = ("source_id", "document_id", "version", "sha256", "kind", "event_date",
                  "issued_at", "received_at", "specimen_id", "state", "supersedes_id", "raw")
        originals = [dict(zip(fields, row), case_id=case_id) for row in rows]
        validate_snapshot(originals, assertions, requested_case_id=case_id)

    def list(self, patient_id: str, case_id: str, *, organization: str,
             actor: str, purpose: str, recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Prepare a trusted read view before its final authority check and commit.

        ``prepare_response`` is application-owned projection/DTO validation, not
        an external tool or model. It runs under the existing locks. Its receipt
        ID is reserved in memory and becomes a receipt only if the subsequent
        authority check, event insertion and transaction commit all succeed.
        """
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        with self.registry.transaction():
            binding_revision = self._binding(patient_id, case_id, organization, purpose)
            sources = self._sources(case_id)
            rows = self.registry._fetchall(
                "SELECT a.source_id,a.finding_key,a.certainty,a.quote,a.source_line "
                "FROM clinical_source.assertions a "
                "JOIN clinical_source.source_versions s ON s.source_id=a.source_id "
                "WHERE s.case_id=%s AND s.state='current' "
                "ORDER BY s.document_id,s.version,a.source_line", (case_id,),
            )
            self._validate_index(case_id, sources, rows)
            result = {
                "contract": "oi.synthetic-original-sources/1",
                "patient_id": patient_id, "case_id": case_id,
                "sources": sources,
                "source_reported_assertions": [
                    {"source_id": r[0], "finding_key": r[1],
                     "reported_state": r[2], "source_statement": r[3],
                     "source_line": r[4], "clinical_review_state": "not_established"}
                    for r in rows
                ],
                "synthetic": True, "clinical_interpretation": False,
                "research_review_invalidation_integrated": False,
            }
            # Hash the exact materialized response before adding its receipt.
            # Only this digest and bounded references enter the event ledger.
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
                source_count=len(sources), assertion_count=len(rows),
            )
            return prepared

    def original(self, patient_id: str, case_id: str, source_id: str, *,
                 organization: str, actor: str, purpose: str,
                 recheck_authority: Callable[[], None]) -> dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        source_id = _source_id(source_id)
        organization = _key(organization, "organization")
        with self.registry.transaction():
            binding_revision = self._binding(patient_id, case_id, organization, purpose)
            stored, raw = self._validated_original(case_id, source_id)
            result = {"source_id": source_id, "case_id": case_id,
                    "document_id": stored["document_id"], "version": stored["version"],
                    "state": stored["state"], "sha256": stored["sha256"],
                    "original_text": raw.decode("utf-8"),
                    "synthetic": True, "clinical_review_state": "not_established"}
            result["access_receipt_id"] = self._read_receipt(
                patient_id, case_id, actor=actor, purpose=purpose,
                binding_revision=binding_revision, event="source.original_read_authorized",
                receipt_id="ACCESS-" + uuid.uuid4().hex.upper(),
                recheck_authority=recheck_authority, source_id=source_id,
                sha256=stored["sha256"], source_version=stored["version"], source_state=stored["state"],
            )
            return result

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
        return stored, validate_original(stored, requested_case_id=case_id, predecessor=predecessor)

    def import_original(self, patient_id: str, case_id: str, original: bytes, *,
                        organization: str, actor: str, purpose: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if purpose not in ("operations", "research"):
            raise PatientRegistryError("Unsupported synthetic source purpose")
        # Reuse the original CaseStore parser; never infer a finding from
        # free text, rewrite an external Patient header or normalize LF/UTF-8.
        try:
            parsed = parse_report(original)
        except InvalidInput:
            raise PatientRegistryError("Unsupported fictional report format") from None
        digest = hashlib.sha256(original).hexdigest()
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
                    return {"result": "quarantined", "duplicate": True,
                            "source_id": None, "version": None}
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
                return {"result": "quarantined", "duplicate": False,
                        "source_id": None, "version": None}
            old = self.registry._fetchone(
                "SELECT source_id,version,sha256,kind,event_date,specimen_id "
                "FROM clinical_source.source_versions "
                "WHERE case_id=%s AND document_id=%s "
                "ORDER BY version DESC LIMIT 1", (case_id, parsed.document_id),
            )
            previously_seen = self.registry._fetchone(
                "SELECT source_id,version FROM clinical_source.source_versions "
                "WHERE case_id=%s AND document_id=%s AND sha256=%s",
                (case_id, parsed.document_id, digest),
            )
            if previously_seen is not None:
                return {"result": "duplicate", "duplicate": True,
                        "source_id": previously_seen[0], "version": previously_seen[1]}
            if old is not None and old[2] == digest:
                return {"result": "duplicate", "duplicate": True,
                        "source_id": old[0], "version": old[1]}
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
            return {"result": "imported", "duplicate": False,
                    "source_id": source_id, "version": version}
