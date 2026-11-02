"""Canonical patient + EHR + domain event transport, in one DB transaction.

Original first-party integration layer, depending on the reviewed patient
registry, EHR domain-host port and typed domain-event outbox. This is an
INTERNAL API: credentials, consent and signed authority must come from a
qualified external policy enforcement point before real data is accepted.

Do not alias a legacy CaseStore case ID to a canonical patient ID. The LIS
source-backed operations still have a distinct legacy-case contract and must
be explicitly adapted and reviewed before they can join these patient events.
"""
from __future__ import annotations

import re
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .patient_registry import PatientRegistry
from .platform_events import OutboxContractError, enqueue, install

# The four currently implemented EHR operational events. There is no generic
# free-text event API: unsupported event names/fields fail closed.
_KIND = {
    "clinical_encounter_scheduled": ("ehr.encounter.scheduled", "encounter", "encounter_id", "revision"),
    "clinical_encounter_state_changed": ("ehr.encounter.state_changed", "encounter", "encounter_id", "revision"),
    "clinical_note_draft_saved": ("ehr.note.draft_saved", "note", "note_id", "version"),
    "clinical_note_attestation_recorded": ("ehr.note.attestation_recorded", "note", "note_id", "version"),
}
_ALLOWED = {
    "clinical_encounter_scheduled": {"encounter_id", "revision", "actor", "purpose", "request_key"},
    "clinical_encounter_state_changed": {"encounter_id", "revision", "actor", "purpose", "request_key", "from_status", "to_status"},
    "clinical_note_draft_saved": {"encounter_id", "note_id", "version", "actor", "purpose", "request_key", "correction_pending"},
    "clinical_note_attestation_recorded": {"encounter_id", "note_id", "version", "actor", "purpose", "request_key", "corrected"},
}
_REQUIRED = {
    "clinical_encounter_scheduled": _ALLOWED["clinical_encounter_scheduled"],
    "clinical_encounter_state_changed": _ALLOWED["clinical_encounter_state_changed"],
    "clinical_note_draft_saved": _ALLOWED["clinical_note_draft_saved"],
    "clinical_note_attestation_recorded": _ALLOWED["clinical_note_attestation_recorded"],
}
_REQUEST = re.compile(r"[A-Za-z0-9_.:-]{8,100}\Z")


class IntegrationError(ValueError):
    """Invalid cross-domain contract; state transaction must roll back."""


class CanonicalEHRHost:
    """Adapter for ClinicalEncounters: one patient owner, one local journal,
    one transport outbox, all under the EHR command's transaction.

    `PatientRegistry.append_event` is the existing *local journal* adapter.
    `platform_events.enqueue` is transport delivery. Neither mints a consent
    grant or signs a clinical note. `db` must be the SAME sqlite3.Connection.
    """

    def __init__(self, registry: PatientRegistry, *, issuer_namespace: str = "OI-PLATFORM"):
        if not isinstance(registry, PatientRegistry):
            raise TypeError("CanonicalEHRHost requires the existing patient registry")
        self.registry = registry
        self.db: sqlite3.Connection = registry.db
        if self.db.in_transaction:
            raise IntegrationError("outbox initialization requires an idle connection")
        if not self.db.execute("PRAGMA foreign_keys").fetchone()[0]:
            raise IntegrationError("patient foreign key enforcement must be enabled")
        # This is a short-term SQLite migration for an unmerged branch.
        # Production uses versioned, reviewed migrations and a transactional
        # PostgreSQL equivalent, never an unqualified runtime schema install.
        install(self.db)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]{1,127}", issuer_namespace):
            raise IntegrationError("issuer namespace must be opaque")
        self.issuer_namespace = issuer_namespace

    def require_patient(self, patient_id: str) -> None:
        self.registry.require_patient(patient_id)

    def append_event(self, patient_id: str, kind: str, **details: object) -> None:
        if not self.db.in_transaction:
            raise IntegrationError("clinical event and outbox must share the state transaction")
        self.require_patient(patient_id)
        if kind not in _KIND or set(details) != _REQUIRED[kind]:
            raise IntegrationError("unknown or incomplete clinical event shape")
        event_type, aggregate_type, id_field, rev_field = _KIND[kind]
        aggregate_number = details[id_field]
        revision = details[rev_field]
        request_key = details["request_key"]
        if type(aggregate_number) is not int or aggregate_number < 1:
            raise IntegrationError("aggregate ID must be a positive integer")
        if type(revision) is not int or revision < 1:
            raise IntegrationError("aggregate version must be a positive integer")
        if not isinstance(request_key, str) or not _REQUEST.fullmatch(request_key):
            raise IntegrationError("causation requires an opaque command receipt key")
        if details["purpose"] not in {"care", "operations", "research"}:
            raise IntegrationError("unrecognized operational purpose")
        if not isinstance(details["actor"], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{3,100}", details["actor"]):
            raise IntegrationError("actor must be a bounded identifier")
        aggregate_id = f"{aggregate_type.upper()}-{aggregate_number}"
        # Stable for the same command; the EHR command receipt itself enforces
        # idempotency under (patient_id, request_key).
        event_id = "EVT-" + uuid.uuid5(
            uuid.NAMESPACE_URL,
            "|".join((self.issuer_namespace, patient_id, kind,
                      aggregate_id, str(revision), request_key)),
        ).hex.upper()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        event = {
            "schema": "oi.domain-event/1",
            "event_id": event_id,
            "event_type": event_type,
            "owner_domain": "ehr",
            "issuer_namespace": self.issuer_namespace,
            "aggregate": {"type": aggregate_type, "id": aggregate_id, "revision": revision},
            "subject_binding_id": patient_id,
            # A domain-authored note is NOT yet a PF-03 canonical source;
            # never fabricate source references or clinical review status.
            "source_version_ref": None,
            "supersedes_source_ref": None,
            "occurred_at": {"value": now, "precision": "second"},
            "recorded_at": now,
            "correlation_id": "REQ-" + request_key,
            "causation_id": "CMD-" + request_key,
            # A callback returning True isn't a signed policy decision receipt.
            "authorization_decision_ref": None,
            "payload_ref": f"EHR-{aggregate_id}-V{revision}",
        }
        # The two writes use the SAME connection/transaction as the EHR
        # insert/update and its idempotency command receipt. Either can throw:
        # the outer command context rolls back all four records together.
        self.registry.append_event(patient_id, kind, **details)
        if not enqueue(self.db, event):
            raise OutboxContractError("duplicate outbox event for new EHR command")

# Projection records contain only validated pointers. Clinical note text,
# authorization credentials, conclusions and PHI never leave their owning
# domain. This is an internal event-consumer read model, NOT a second EHR.
CHANGE_INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_ehr_change_index (
 consumer_id TEXT NOT NULL,
 event_id TEXT NOT NULL,
 patient_id TEXT NOT NULL,
 aggregate_type TEXT NOT NULL,
 aggregate_id TEXT NOT NULL,
 source_revision INTEGER NOT NULL,
 event_type TEXT NOT NULL,
 PRIMARY KEY(consumer_id,event_id)
);
CREATE INDEX IF NOT EXISTS idx_platform_ehr_change_patient
 ON platform_ehr_change_index(consumer_id,patient_id,event_id);
"""


class VerifiedEHRChangeConsumer:
    """Evidence-pointer change index with verified patient/aggregate binding.

    The *caller* supplies a trusted PEP callback; no callback or deny throws.
    `consume_ordered` enforces aggregate revision progression, exactly-once
    local effects and repeat-message deduplication. No clinical interpretation
    or new patient record is written. Production message authentication, cross-
    database inbox, signed policy receipts and source versions are still gates.
    """

    def __init__(self, registry: PatientRegistry, *, authorizer=None,
                 issuer_namespace: str = "OI-PLATFORM", consumer_id: str = "OI-PWM"):
        self.registry = registry
        self.db = registry.db
        self.authorizer = authorizer
        self.issuer_namespace = issuer_namespace
        self.consumer_id = consumer_id
        if self.db.in_transaction:
            raise IntegrationError("consumer schema install requires idle connection")
        install(self.db)
        self.db.executescript(CHANGE_INDEX_SCHEMA)

    def _authorize(self, actor: str, patient_id: str, purpose: str) -> None:
        self.registry.require_patient(patient_id)
        try:
            allowed = bool(self.authorizer and self.authorizer(
                actor, patient_id, "ehr_change.read", purpose))
        except Exception:
            allowed = False
        if not allowed:
            raise PermissionError("EHR change projection access denied")

    def _check_origin(self, event: dict) -> tuple[str, str, int]:
        if event["owner_domain"] != "ehr" or event["issuer_namespace"] != self.issuer_namespace:
            raise IntegrationError("unexpected event issuer or domain")
        if event["event_type"] not in {v[0] for v in _KIND.values()}:
            raise IntegrationError("unsupported EHR event kind")
        if event["authorization_decision_ref"] is not None:
            raise IntegrationError("unsigned authority reference cannot certify access")
        patient_id = event["subject_binding_id"]
        if not patient_id:
            raise IntegrationError("unbound EHR event cannot enter patient read model")
        self.registry.require_patient(patient_id)
        agg = event["aggregate"]
        aggregate_type = agg["type"]
        aggregate_id = agg["id"]
        revision = agg["revision"]
        if aggregate_type not in {"encounter", "note"}:
            raise IntegrationError("unknown operational aggregate")
        prefix = "ENCOUNTER-" if aggregate_type == "encounter" else "NOTE-"
        if not aggregate_id.startswith(prefix) or not aggregate_id[len(prefix):].isdigit():
            raise IntegrationError("aggregate ID shape is invalid")
        number = int(aggregate_id[len(prefix):])
        if number < 1 or event["payload_ref"] != f"EHR-{aggregate_id}-V{revision}":
            raise IntegrationError("payload reference is not a published domain pointer")
        if aggregate_type == "encounter":
            row = self.db.execute(
                "SELECT revision FROM clinical_encounters WHERE id=? AND patient_id=?",
                (number, patient_id)).fetchone()
            if row is None or row[0] < revision or not event["event_type"].startswith("ehr.encounter."):
                raise IntegrationError("encounter event not bound to this patient/version")
            if (event["event_type"] == "ehr.encounter.scheduled") != (revision == 1):
                raise IntegrationError("encounter event/revision mismatch")
        else:
            row = self.db.execute(
                "SELECT v.status FROM clinical_note_versions v "
                "JOIN clinical_note_headers n ON n.id=v.note_id "
                "JOIN clinical_encounters e ON e.id=n.encounter_id "
                "WHERE v.note_id=? AND v.version=? AND e.patient_id=?",
                (number, revision, patient_id)).fetchone()
            if row is None or not event["event_type"].startswith("ehr.note."):
                raise IntegrationError("note event not bound to this patient/version")
            if event["event_type"] == "ehr.note.draft_saved":
                if row[0] not in ("draft", "draft_correction"):
                    raise IntegrationError("note draft event not supported by source version")
            elif row[0] not in ("attested", "attested_correction"):
                raise IntegrationError("note attestation event not supported by source version")
        # The source module records an immutable local journal entry with
        # request_key and typed aggregate refs. Verify it is actually present.
        causation = event["causation_id"]
        if not causation.startswith("CMD-") or event["correlation_id"] != "REQ-" + causation[4:]:
            raise IntegrationError("missing matching EHR command causation")
        request_key = causation[4:]
        kind = next((k for k, v in _KIND.items() if v[0] == event["event_type"]), None)
        if kind is None:
            raise IntegrationError("event kind unsupported")
        expected_id = "EVT-" + uuid.uuid5(
            uuid.NAMESPACE_URL, "|".join((event["issuer_namespace"], patient_id,
                kind, aggregate_id, str(revision), request_key))
        ).hex.upper()
        if expected_id != event["event_id"]:
            raise IntegrationError("event identity not reproducible from its source command")
        id_field, revision_field = _KIND[kind][2:]
        rows = self.db.execute(
            "SELECT metadata_json FROM identity_domain_events "
            "WHERE patient_id=? AND event_type=?", (patient_id, kind)).fetchall()
        if not any(
            (lambda d: d.get("request_key") == request_key
             and d.get(id_field) == number and d.get(revision_field) == revision)(
                json.loads(row[0])) for row in rows
        ):
            raise IntegrationError("event has no source-journal evidence")
        return patient_id, aggregate_type, revision

    def apply(self, event: dict, *, actor: str, purpose: str) -> bool:
        # Revoked users must not even learn if this event has been processed.
        patient_id = event.get("subject_binding_id") if isinstance(event, dict) else None
        if not isinstance(patient_id, str):
            raise IntegrationError("event must declare a patient reference")
        self._authorize(actor, patient_id, purpose)
        from .platform_events import consume_ordered
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            # validate_event is always executed by consume_ordered; it is
            # additionally checked here for origin and subject relationship.
            from .platform_events import validate_event
            canonical = validate_event(event)
            patient_id, aggregate_type, revision = self._check_origin(canonical)
            def _write(db, ev):
                db.execute(
                    "INSERT INTO platform_ehr_change_index "
                    "(consumer_id,event_id,patient_id,aggregate_type,aggregate_id,source_revision,event_type) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (self.consumer_id, ev["event_id"], patient_id, aggregate_type,
                     ev["aggregate"]["id"], revision, ev["event_type"]),
                )
            return consume_ordered(self.db, self.consumer_id, canonical, _write)

    def list_changes(self, patient_id: str, *, actor: str, purpose: str) -> list[dict]:
        self._authorize(actor, patient_id, purpose)
        return [dict(row) for row in self.db.execute(
            "SELECT event_id,aggregate_type,aggregate_id,source_revision,event_type "
            "FROM platform_ehr_change_index WHERE patient_id=? AND consumer_id=? "
            "ORDER BY rowid", (patient_id, self.consumer_id)).fetchall()]

_LAB_KIND = {
    "clinical_lab_order_requested": ("lab.order.requested", "order", "order_id", 1, "order_key"),
    "clinical_lab_order_cancelled": ("lab.order.cancelled", "order", "order_id", 2, "order_key"),
    "clinical_lab_specimen_accessioned": ("lab.specimen.accessioned", "accession", "accession_id", 1, "accession_key"),
    "clinical_lab_qc_recorded": ("lab.qc.recorded", "qc", "qc_id", 1, "qc_id"),
    "clinical_lab_observation_released": ("lab.observation.released", "release", "release_id", 1, "release_id"),
}
_LAB_DETAILS = {
    "clinical_lab_order_requested": {"order_id", "order_key", "source_version_id"},
    "clinical_lab_order_cancelled": {"order_id", "order_key"},
    "clinical_lab_specimen_accessioned": {"accession_id", "order_id", "accession_key", "specimen_id"},
    "clinical_lab_qc_recorded": {"accession_id", "qc_id", "outcome", "source_version_id"},
    "clinical_lab_observation_released": {"accession_id", "release_id", "source_version_id", "assertion_id", "qc_id"},
}


class LegacyLabOutboxPublisher:
    """Transport compatibility for the existing source-bound CaseStore LIS.

    Critically: this producer sets ``subject_binding_id=None``. A legacy
    case ID is **not** an OI patient ID. No patient read model may consume the
    lab event until a separate, reviewed identity/consent reconciliation binds
    its source context to one canonical patient and the necessary authority.
    """

    def __init__(self, store, *, issuer_namespace="OI-LEGACY-SOURCE"):
        from .store import CaseStore
        if not isinstance(store, CaseStore):
            raise TypeError("LegacyLabOutboxPublisher requires the original source CaseStore")
        self.store = store
        self.db = store.db
        if self.db.in_transaction:
            raise IntegrationError("outbox install requires idle source connection")
        install(self.db)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]{1,127}", issuer_namespace):
            raise IntegrationError("legacy source namespace must be opaque")
        self.issuer_namespace = issuer_namespace

    def __call__(self, case_id: str, kind: str, details: dict[str, object]) -> None:
        if not self.db.in_transaction:
            raise IntegrationError("laboratory event transport must be atomic with source state")
        self.store._case(case_id)  # existing synthetic-only source boundary
        if kind not in _LAB_KIND or not isinstance(details, dict) or set(details) != _LAB_DETAILS[kind]:
            raise IntegrationError("unknown or incomplete source-bound lab event")
        event_type, aggregate_type, id_field, revision, causation_field = _LAB_KIND[kind]
        aggregate_num = details[id_field]
        if type(aggregate_num) is not int or aggregate_num < 1:
            raise IntegrationError("lab aggregate ID must be positive")
        cause = details[causation_field]
        if not isinstance(cause, (str, int)) or len(str(cause)) > 100 or not re.fullmatch(r"[A-Za-z0-9_-]+", str(cause)):
            raise IntegrationError("lab event command reference must be bounded")
        if "source_version_id" in details and (type(details["source_version_id"]) is not int or details["source_version_id"] < 1):
            raise IntegrationError("source version ref invalid")
        aggregate_id = f"LAB-{aggregate_type.upper()}-{aggregate_num}"
        event_id = "EVT-" + uuid.uuid5(uuid.NAMESPACE_URL,
            "|".join((self.issuer_namespace, case_id, kind, aggregate_id, str(revision), str(cause)))).hex.upper()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        event = {
            "schema": "oi.domain-event/1",
            "event_id": event_id,
            "event_type": event_type,
            "owner_domain": "lab",
            "issuer_namespace": self.issuer_namespace,
            "aggregate": {"type": aggregate_type, "id": aggregate_id, "revision": revision},
            "subject_binding_id": None,  # identity unverified: NEVER substitute case_id
            "source_version_ref": (f"LEGACY-SOURCE-{details['source_version_id']}"
                if "source_version_id" in details else None),
            "supersedes_source_ref": None,
            "occurred_at": {"value": now, "precision": "second"},
            "recorded_at": now,
            "correlation_id": "LEGACY-" + case_id,
            "causation_id": "LAB-CMD-" + str(cause),
            "authorization_decision_ref": None,  # no trusted clinical authorization
            "payload_ref": f"LEGACY-{aggregate_id}-V{revision}",
        }
        if not enqueue(self.db, event):
            raise OutboxContractError("duplicate outbox event for new lab operation")
