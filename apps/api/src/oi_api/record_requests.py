"""First-party synthetic PostgreSQL record-acquisition lifecycle.

Uses the one canonical patient registry, existing immutable event journal and
existing clinical_source.source_versions owner. A received *pointer* is an
append-only identity event, never a new source/document table or copied bytes.
No provider communication, identity proof, clinical validation or PHI support.
"""
from __future__ import annotations

from datetime import datetime
from collections.abc import Callable
import hashlib
from typing import TypeVar
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
    _digest, _key, _now,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

KINDS = frozenset(("clinical", "pathology", "laboratory", "imaging", "molecular", "other"))
PreparedResponse = TypeVar("PreparedResponse")


def _label(value: str, max_size: int) -> str:
    if (not isinstance(value, str) or not value.strip()
            or len(value.strip()) > max_size
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise PatientRegistryError("Invalid fictional record request")
    return value.strip()


class PostgresRecordRequests:
    """Operational request state keyed to the single canonical patient."""

    def __init__(self, patients: PostgresPatientRegistry):
        if not isinstance(patients, PostgresPatientRegistry):
            raise TypeError("Canonical patient registry required")
        self.patients = patients

    def _active_patient(self, patient_id: str, organization: str) -> None:
        # Row lock prevents a concurrent patient suspension until the command
        # commits; the policy was independently checked at the route boundary.
        row = self.patients._fetchone(
            "SELECT origin_org,status FROM identity.identity_patients "
            "WHERE patient_id=%s FOR SHARE", (patient_id,),
        )
        if row is None or row[0] != organization or row[1] != "active":
            raise PatientRegistryDenied("Patient unavailable")

    def _receipt(self, patient_id: str, request_id: str, kind: str,
                 organization: str, *, disclose_source: bool = False) -> dict | None:
        """Resolve one immutable receipt through its original source owner.

        All calls run within the registry's existing transaction. A revoked
        patient-case binding withholds source identifiers from request readers.
        A historical source amendment never silently updates the old receipt.
        """
        events = self.patients._fetchall(
            "SELECT metadata_json->>'case_id',metadata_json->>'source_id',"
            "metadata_json->>'source_sha256',metadata_json->>'source_version',occurred_at "
            "FROM identity.identity_domain_events "
            "WHERE patient_id=%s AND event_type='record.request.received' "
            "AND metadata_json->>'request_id'=%s ORDER BY id LIMIT 2",
            (patient_id, request_id),
        )
        if not events:
            return None
        if len(events) != 1:
            raise PatientRegistryError("Ambiguous record receipt history")
        case_id, source_id, digest, source_version, received_at = events[0]
        source = self.patients._fetchone(
            "SELECT s.case_id,s.sha256,s.version,s.kind,s.state,"
            "b.patient_id,b.origin_org,b.status "
            "FROM clinical_source.source_versions s "
            "JOIN coordination.patient_case_bindings b ON b.case_id=s.case_id "
            "WHERE s.source_id=%s", (source_id,),
        )
        if (source is None or source[0] != case_id or source[1] != digest
                or str(source[2]) != source_version or source[3] != kind
                or source[5] != patient_id or source[6] != organization):
            raise PatientRegistryError("Received source reference integrity mismatch")
        if source[7] != "active":
            state = "binding_revoked_not_usable"
        elif source[4] != "current":
            state = "source_superseded_reconciliation_required"
        else:
            state = "source_current_unreviewed"
        ref = None
        if disclose_source and source[7] == "active":
            ref = {"case_id": case_id, "source_id": source_id,
                   "version": source[2], "sha256": digest}
        return {
            "source_id": source_id, "case_id": case_id,
            "receipt_status": state, "reference": ref, "received_at": received_at,
        }

    def _record(self, row: tuple, *, organization: str,
                disclose_source: bool = False) -> dict:
        (request_id, patient_id, kind, record_label, provider, status, revision,
         created_at, updated_at) = row
        received = self._latest_receipt(patient_id, request_id, kind, organization,
                                 disclose_source=disclose_source)
        if status == "cancelled" and received is not None:
            raise PatientRegistryError("Contradictory received/cancelled history")
        return {
            "request_id": request_id, "patient_id": patient_id,
            "kind": kind, "record_label": record_label,
            "source_organization": provider,
            # Operational status is a projection of the immutable receipt
            # event, not a second mutable copy of that receipt in this table.
            "status": "received" if received else status,
            "revision": received["revision"] if received else revision,
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            # A receive is a journal event, not a record-request row update.
            # Project the true transition time rather than incorrectly
            # repeating the original request's creation timestamp.
            "updated_at": (
                received["received_at"].isoformat()
                if received and isinstance(received["received_at"], datetime)
                else (updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at))
            ),
            "receipt_status": received["receipt_status"] if received else "not_received",
            "source_reference": received["reference"] if received else None,
            "external_request_sent": False,
        }

    def list(self, patient_id: str, *, organization: str,
             disclose_source: bool = False,
             prepare_response: Callable[[list[dict]], PreparedResponse] | None = None,
             recheck_authority: Callable[[], None] | None = None) -> list[dict] | PreparedResponse:
        patient_id = _key(patient_id, "patient_id")
        organization = _key(organization, "organization")
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            rows = self.patients._fetchall(
                "SELECT request_id,patient_id,kind,record_label,source_organization,"
                "status,revision,created_at,updated_at "
                "FROM coordination.record_requests WHERE patient_id=%s AND origin_org=%s "
                "ORDER BY created_at,request_id FOR SHARE", (patient_id, organization),
            )
            result = [self._record(row, organization=organization,
                                   disclose_source=disclose_source) for row in rows]
            prepared = prepare_response(result) if prepare_response is not None else result
            if recheck_authority is not None:
                recheck_authority()
            return prepared

    def create(self, patient_id: str, *, organization: str, actor: str, purpose: str,
               request_key: str, kind: str, record_label: str,
               source_organization: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        if type(kind) is not str or kind not in KINDS:
            raise PatientRegistryError("Invalid fictional source category")
        record_label = _label(record_label, 140)
        source_organization = _label(source_organization, 100)
        if purpose not in ("operations", "research"):
            raise PatientRegistryError("Invalid purpose")
        digest = _digest({
            "patient": patient_id, "org": organization, "actor": actor,
            "purpose": purpose, "kind": kind, "record_label": record_label,
            "source_organization": source_organization,
        })
        request_id = "RECORD-" + uuid.uuid4().hex.upper()
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "INSERT INTO coordination.record_requests "
                "(request_id,patient_id,origin_org,request_key,intent_sha256,kind,"
                "record_label,source_organization,actor,purpose,status,revision) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'requested',1) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING request_id",
                (request_id, patient_id, organization, request_key, digest, kind,
                 record_label, source_organization, actor, purpose),
            )
            if row is None:
                old = self.patients._fetchone(
                    "SELECT request_id,intent_sha256 FROM coordination.record_requests "
                    "WHERE patient_id=%s AND request_key=%s", (patient_id, request_key),
                )
                if old is None or old[1] != digest:
                    raise PatientRegistryConflict("Request key reused with changed intent")
                return {"request_id": old[0], "duplicate": True}
            self.patients.append_event(
                patient_id, "record.request.created",
                request_id=request_id, actor=actor, revision=1,
            )
            return {"request_id": request_id, "duplicate": False}

    def cancel(self, patient_id: str, request_id: str, *,
               organization: str, actor: str, reason: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        request_id = _key(request_id, "request_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        reason = _label(reason, 200)
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "SELECT status,revision FROM coordination.record_requests "
                "WHERE request_id=%s AND patient_id=%s AND origin_org=%s FOR UPDATE",
                (request_id, patient_id, organization),
            )
            if row is None:
                raise PatientRegistryDenied("Record request unavailable")
            # Under the request row lock: no cancellation may race with an
            # immutable received receipt, even if the source was superseded.
            already_received = self.patients._fetchone(
                "SELECT 1 FROM identity.identity_domain_events "
                "WHERE patient_id=%s AND event_type='record.request.received' "
                "AND metadata_json->>'request_id'=%s LIMIT 1",
                (patient_id, request_id),
            )
            if already_received is not None:
                raise PatientRegistryConflict("Received record cannot be cancelled")
            if row[0] == "cancelled":
                return {"request_id": request_id, "duplicate": True}
            if row[0] != "requested" or row[1] != 1:
                raise PatientRegistryConflict("Record request state changed")
            changed = self.patients._fetchone(
                "UPDATE coordination.record_requests SET status='cancelled',revision=2,"
                "cancellation_reason=%s,updated_at=now() "
                "WHERE request_id=%s AND patient_id=%s AND status='requested' "
                "RETURNING request_id", (reason, request_id, patient_id),
            )
            if changed is None:
                raise PatientRegistryConflict("Record request state changed")
            self.patients.append_event(
                patient_id, "record.request.cancelled",
                request_id=request_id, actor=actor, revision=2,
            )
            return {"request_id": request_id, "duplicate": False}

    def receive(self, patient_id: str, request_id: str, case_id: str,
                source_id: str, *, organization: str,
                actor: str, purpose: str,
                recheck_authority: Callable[[], None],
                prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Attach an existing exact current original; do not ingest or recopy it.

        The row lock serializes receive/cancel/idempotent retry. The qualified
        canonical case binding is held through the event commit, as is the
        original source integrity check. This does not verify the provider
        label or perform clinical acceptance of the document.

        Both new receipts and historical retries prepare their response and
        refresh current authority under these locks before commit. The existing
        event is a received pointer, not proof of HTTP delivery.
        """
        from .case_bindings import _case_id
        from .sources import _source_id, PostgresSourceVersions
        patient_id = _key(patient_id, "patient_id")
        request_id = _key(request_id, "request_id")
        case_id = _case_id(case_id)
        source_id = _source_id(source_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if purpose not in ("operations", "research"):
            raise PatientRegistryError("Invalid source-receipt purpose")

        def complete(result):
            prepared = prepare_response(result) if prepare_response is not None else result
            recheck_authority()
            return prepared

        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "SELECT kind,status,revision FROM coordination.record_requests "
                "WHERE request_id=%s AND patient_id=%s AND origin_org=%s FOR UPDATE",
                (request_id, patient_id, organization),
            )
            if row is None:
                raise PatientRegistryDenied("Record request unavailable")
            if row[1] != "requested" or row[2] != 1:
                raise PatientRegistryConflict("Record request not eligible for receipt")
            PostgresSourceVersions(self.patients)._binding(
                patient_id, case_id, organization, purpose,
            )
            source = self.patients._fetchone(
                "SELECT case_id,kind,version,sha256,state,raw "
                "FROM clinical_source.source_versions "
                "WHERE source_id=%s FOR SHARE",
                (source_id,),
            )
            if (source is None or source[0] != case_id or source[1] != row[0]):
                raise PatientRegistryDenied("Source does not match requested category and case")
            if hashlib.sha256(bytes(source[5])).hexdigest() != source[3]:
                raise PatientRegistryError("Original source integrity check failed")
            existing = self._receipt(patient_id, request_id, row[0], organization)
            if existing is not None:
                if existing["case_id"] != case_id or existing["source_id"] != source_id:
                    raise PatientRegistryConflict("Record request already has a different source")
                return complete({"request_id": request_id, "source_id": source_id,
                                 "version": source[2], "duplicate": True})
            if source[4] != "current":
                raise PatientRegistryConflict("Source version is no longer current")
            # This *one* existing immutable patient event is the only durable
            # receipt. No unverified document bytes, provider claims or
            # secondary record-request ledger are created.
            self.patients.append_event(
                patient_id, "record.request.received",
                request_id=request_id, case_id=case_id, source_id=source_id,
                source_sha256=source[3], source_version=source[2], actor=actor,
            )
            return complete({"request_id": request_id, "source_id": source_id,
                             "version": source[2], "duplicate": False})

    def _source_chain(self, source_id: str, case_id: str, kind: str, *,
                      verify_originals: bool = True) -> dict:
        """Validate original bytes and every amendment edge with the source owner."""
        from .source_integrity import SourceIntegrityError, validate_original
        row = self.patients._fetchone(
            "SELECT document_id FROM clinical_source.source_versions "
            "WHERE source_id=%s AND case_id=%s", (source_id, case_id),
        )
        if row is None:
            raise PatientRegistryDenied("Source unavailable")
        # Request-only readers may see operational status, but must not load
        # original bytes without the independent source_read grant.
        raw_column = ",raw" if verify_originals else ""
        rows = self.patients._fetchall(
            "SELECT source_id,case_id,document_id,version,sha256,kind,event_date,"
            "issued_at,specimen_id,state,supersedes_id" + raw_column + " "
            "FROM clinical_source.source_versions WHERE case_id=%s AND document_id=%s "
            "ORDER BY version LIMIT 257 FOR SHARE", (case_id, row[0]),
        )
        if not rows or len(rows) > 256:
            raise SourceIntegrityError("Source history unavailable")
        fields = ("source_id", "case_id", "document_id", "version", "sha256", "kind",
                  "event_date", "issued_at", "specimen_id", "state", "supersedes_id", "raw")
        chain = {}
        previous = None
        for version, values in enumerate(rows, start=1):
            source = dict(zip(fields, values))
            if verify_originals:
                validate_original(source, requested_case_id=case_id, predecessor=previous)
            elif (source["case_id"] != case_id or source["document_id"] != row[0]
                  or source["supersedes_id"] != (previous["source_id"] if previous else None)
                  or (previous is not None and
                      (source["kind"], source["event_date"], source["specimen_id"]) !=
                      (previous["kind"], previous["event_date"], previous["specimen_id"]))):
                raise SourceIntegrityError("Source metadata history unavailable")
            if (type(source["version"]) is not int or source["version"] != version or source["kind"] != kind
                    or source["state"] != ("current" if version == len(rows) else "superseded")):
                raise SourceIntegrityError("Source history unavailable")
            chain[source["source_id"]] = source
            previous = source
        if source_id not in chain:
            raise SourceIntegrityError("Source history unavailable")
        return chain

    def _history(self, patient_id: str, request_id: str, kind: str,
                 organization: str, *, verify_originals: bool = True) -> list[dict]:
        """Project the immutable journal; malformed or forked history fails closed."""
        from .source_integrity import SourceIntegrityError
        events = self.patients._fetchall(
            "SELECT event_type,metadata_json,occurred_at "
            "FROM identity.identity_domain_events WHERE patient_id=%s "
            "AND event_type IN ('record.request.received','record.request.reconciled') "
            "AND metadata_json->>'request_id'=%s ORDER BY id LIMIT 257",
            (patient_id, request_id),
        )
        if not events:
            return []
        if len(events) > 256:
            raise SourceIntegrityError("Record receipt history unavailable")
        case_id = events[0][1].get("case_id")
        binding = self.patients._fetchone(
            "SELECT patient_id,origin_org,status FROM coordination.patient_case_bindings "
            "WHERE case_id=%s FOR SHARE", (case_id,),
        )
        if binding is None or tuple(binding[:2]) != (patient_id, organization):
            raise SourceIntegrityError("Record receipt binding mismatch")
        chain = self._source_chain(events[0][1].get("source_id"), case_id, kind,
                                   verify_originals=verify_originals)
        history = []
        keys, identifiers = set(), set()
        for index, (event_type, metadata, occurred_at) in enumerate(events):
            source = chain.get(metadata.get("source_id"))
            if (event_type != ("record.request.received" if index == 0 else "record.request.reconciled")
                    or metadata.get("case_id") != case_id or source is None
                    or type(metadata.get("source_version")) is not int
                    or metadata["source_version"] != source["version"]
                    or metadata.get("source_sha256") != source["sha256"]
                    or not isinstance(occurred_at, datetime) or occurred_at.utcoffset() is None):
                raise SourceIntegrityError("Record receipt history mismatch")
            if index:
                old = chain[history[-1]["source_reference"]["source_id"]]
                expected_digest = _digest({
                    "patient": patient_id, "request": request_id, "case": case_id,
                    "organization": organization, "actor": metadata.get("actor"),
                    "purpose": metadata.get("purpose"), "expected": old["source_id"],
                    "replacement": source["source_id"], "reason": "source_amendment",
                })
                if (metadata.get("previous_source_id") != old["source_id"]
                        or source["version"] <= old["version"]
                        or metadata.get("reason_code") != "source_amendment"
                        or metadata.get("organization") != organization
                        or metadata.get("purpose") not in ("operations", "research")
                        or type(metadata.get("revision")) is not int
                        or metadata["revision"] != index + 2
                        or metadata.get("intent_sha256") != expected_digest
                        or not isinstance(metadata.get("request_key"), str)
                        or metadata["request_key"] in keys
                        or not isinstance(metadata.get("reconciliation_id"), str)
                        or metadata["reconciliation_id"] in identifiers):
                    raise SourceIntegrityError("Record receipt history mismatch")
                keys.add(metadata["request_key"])
                identifiers.add(metadata["reconciliation_id"])
            history.append({
                "kind": "received" if index == 0 else "reconciled",
                "source_reference": {"case_id": case_id, "source_id": source["source_id"],
                                     "version": source["version"], "sha256": source["sha256"]},
                "previous_source_id": metadata.get("previous_source_id") if index else None,
                "reconciliation_id": metadata.get("reconciliation_id") if index else None,
                "revision": index + 2, "occurred_at": occurred_at,
                "actor": metadata["actor"],
                "reason_code": "source_amendment" if index else None,
                "clinical_approval": False, "external_request_sent": False,
                "_metadata": metadata, "_source_state": source["state"],
                "_binding_active": binding[2] == "active",
            })
        return history

    def _latest_receipt(self, patient_id: str, request_id: str, kind: str,
                        organization: str, *, disclose_source: bool = False) -> dict | None:
        history = self._history(patient_id, request_id, kind, organization,
                                verify_originals=disclose_source)
        if not history:
            return None
        latest = history[-1]
        state = ("binding_revoked_not_usable" if not latest["_binding_active"] else
                 "source_current_unreviewed" if latest["_source_state"] == "current" else
                 "source_superseded_reconciliation_required")
        return {"receipt_status": state, "received_at": latest["occurred_at"],
                "revision": latest["revision"],
                "reference": latest["source_reference"]
                if disclose_source and latest["_binding_active"] else None}

    def reconcile(self, patient_id: str, request_id: str, case_id: str, *,
                  expected_source_id: str, replacement_source_id: str,
                  request_key: str, reason_code: str, organization: str,
                  actor: str, purpose: str, recheck_authority: Callable[[], None],
                  prepare_response: Callable[[dict], PreparedResponse]) -> PreparedResponse:
        """Append an explicit operational reconciliation, never rewrite a receipt."""
        from .case_bindings import _case_id
        from .sources import _source_id, PostgresSourceVersions
        patient_id = _key(patient_id, "patient_id")
        request_id = _key(request_id, "request_id")
        case_id = _case_id(case_id)
        expected_source_id = _source_id(expected_source_id)
        replacement_source_id = _source_id(replacement_source_id)
        request_key = _key(request_key, "request_key")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if purpose not in ("operations", "research") or reason_code != "source_amendment":
            raise PatientRegistryError("Invalid reconciliation purpose")
        digest = _digest({
            "patient": patient_id, "request": request_id, "case": case_id,
            "organization": organization, "actor": actor, "purpose": purpose,
            "expected": expected_source_id, "replacement": replacement_source_id,
            "reason": reason_code,
        })

        def result(metadata, duplicate):
            return {"request_id": request_id,
                    "reconciliation_id": metadata["reconciliation_id"],
                    "previous_source_id": metadata["previous_source_id"],
                    "source_id": metadata["source_id"], "version": metadata["source_version"],
                    "duplicate": duplicate, "clinical_approval": False,
                    "external_request_sent": False}

        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "SELECT kind,status,revision FROM coordination.record_requests "
                "WHERE request_id=%s AND patient_id=%s AND origin_org=%s FOR UPDATE",
                (request_id, patient_id, organization),
            )
            if row is None:
                raise PatientRegistryDenied("Record request unavailable")
            if tuple(row[1:]) != ("requested", 1):
                raise PatientRegistryConflict("Record request not eligible")
            PostgresSourceVersions(self.patients)._binding(
                patient_id, case_id, organization, purpose)
            history = self._history(patient_id, request_id, row[0], organization)
            if not history:
                raise PatientRegistryConflict("Record request has no received original")
            if history[0]["source_reference"]["case_id"] != case_id:
                raise PatientRegistryDenied("Record receipt case unavailable")
            for entry in history[1:]:
                metadata = entry["_metadata"]
                if metadata["request_key"] == request_key:
                    if metadata["intent_sha256"] != digest:
                        raise PatientRegistryConflict("Request key reused with changed intent")
                    prepared = prepare_response(result(metadata, True))
                    recheck_authority()
                    return prepared
            if len(history) >= 256:
                raise PatientRegistryConflict("Record receipt history limit reached")
            latest = history[-1]["source_reference"]
            if latest["source_id"] != expected_source_id:
                raise PatientRegistryConflict("Record receipt changed; refresh before reconciling")
            chain = self._source_chain(expected_source_id, case_id, row[0])
            replacement = chain.get(replacement_source_id)
            if (replacement is None or replacement["state"] != "current"
                    or replacement["version"] <= latest["version"]):
                raise PatientRegistryConflict("Replacement must be a current amendment descendant")
            metadata = {
                "request_id": request_id, "case_id": case_id,
                "reconciliation_id": "RECON-" + uuid.uuid4().hex.upper(),
                "previous_source_id": expected_source_id,
                "source_id": replacement_source_id,
                "source_sha256": replacement["sha256"],
                "source_version": replacement["version"],
                "request_key": request_key, "intent_sha256": digest,
                "reason_code": reason_code, "organization": organization,
                "actor": actor, "purpose": purpose, "revision": len(history) + 2,
            }
            prepared = prepare_response(result(metadata, False))
            recheck_authority()
            self.patients.append_event(patient_id, "record.request.reconciled", **metadata)
            # An audit hook/provider may itself withdraw external authority.
            recheck_authority()
            return prepared

    def receipt_history(self, patient_id: str, request_id: str, *, organization: str,
                        actor: str, purpose: str, recheck_authority: Callable[[], None],
                        prepare_response: Callable[[dict], PreparedResponse]) -> PreparedResponse:
        from .sources import PostgresSourceVersions
        patient_id = _key(patient_id, "patient_id")
        request_id = _key(request_id, "request_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "SELECT kind FROM coordination.record_requests WHERE request_id=%s "
                "AND patient_id=%s AND origin_org=%s FOR SHARE",
                (request_id, patient_id, organization),
            )
            if row is None:
                raise PatientRegistryDenied("Record request unavailable")
            # Derive the case from the immutable original receipt, never caller input.
            initial = self._receipt(patient_id, request_id, row[0], organization)
            binding_revision = None
            if initial is not None:
                binding_revision = PostgresSourceVersions(self.patients)._binding(
                    patient_id, initial["case_id"], organization, purpose)
            history = self._history(patient_id, request_id, row[0], organization)
            receipt_id = "ACCESS-" + uuid.uuid4().hex.upper()
            prepared = prepare_response({
                "patient_id": patient_id, "request_id": request_id,
                "receipts": [{k: v for k, v in entry.items() if not k.startswith("_")}
                             for entry in history],
                "access_receipt_id": receipt_id,
            })
            recheck_authority()
            self.patients.append_event(
                patient_id, "record.receipt_history.read_authorized",
                request_id=request_id, receipt_id=receipt_id, actor=actor, purpose=purpose,
                case_id=initial["case_id"] if initial else None,
                binding_revision=binding_revision, receipt_count=len(history),
            )
            recheck_authority()
            return prepared
