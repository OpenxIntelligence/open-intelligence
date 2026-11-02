"""First-party clinical domain-host adapter for canonical patient and outbox.

This binds independent first-party identity, encounter, and transport modules
without introducing a second patient registry or a second note/source ledger.
The caller-owned connection and ClinicalEncounters command scope are required.

NOT an identity provider, permission service, HIPAA/PHI-ready system,
clinical authorization, or an external broker.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .patient_registry import PatientRegistry, PatientRegistryError
from .platform_events import enqueue

EVENT_TYPES = {
    "clinical_encounter_scheduled": "clinical.encounter.scheduled",
    "clinical_encounter_state_changed": "clinical.encounter.state_changed",
    "clinical_note_draft_saved": "clinical.note.draft_saved",
    "clinical_note_attestation_recorded": "clinical.note.attestation_recorded",
}


class EventedClinicalHost:
    """ClinicalDomainHost implementation over the ONE identity-owner database.

    Requires that PatientRegistry, ClinicalEncounters and platform_events.install
    are initialized on the same connection before operational commands.
    """
    def __init__(self, registry: PatientRegistry):
        if not isinstance(registry, PatientRegistry):
            raise TypeError("expected first-party PatientRegistry")
        self.registry = registry
        self.db: sqlite3.Connection = registry.db

    def require_patient(self, patient_id: str) -> None:
        """Only the host port; the ClinicalEncounters PEP must authorize actor."""
        self.registry.require_patient(patient_id)

    def append_event(self, patient_id: str, kind: str, **details: object) -> None:
        """Append clinical event and outbox message in SAME command transaction.

        The event is an opaque metadata reference; no note body leaves the
        EHR-owned operational table. A failed append aborts the caller's
        transaction. No network I/O, no implicit commit.
        """
        if not self.db.in_transaction:
            raise PatientRegistryError("clinical event must share operational transaction")
        if kind not in EVENT_TYPES:
            raise PatientRegistryError("unsupported first-party clinical event kind")
        self.registry.append_event(patient_id, kind, **details)
        receipt_id = self.db.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Counter uses only clinical-domain events. Identity creation and other
        # products do not affect the clinical stream revision sequence.
        revision = self.db.execute(
            "SELECT COUNT(*) FROM identity_domain_events WHERE patient_id=? "
            "AND event_type LIKE 'clinical_%'",
            (patient_id,),
        ).fetchone()[0]
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        envelope = {
            "schema": "oi.domain-event/1",
            "event_id": f"EV-CLINICAL-{receipt_id}",
            "event_type": EVENT_TYPES[kind],
            "owner_domain": "clinical",
            "issuer_namespace": "urn:oi:internal:clinical",
            "aggregate": {
                "type": "patient_activity",
                "id": patient_id,
                "revision": revision,
            },
            "subject_binding_id": patient_id,
            "source_version_ref": None,
            "supersedes_source_ref": None,
            "occurred_at": {"value": stamp, "precision": "second"},
            "recorded_at": stamp,
            "correlation_id": f"FLOW-CLINICAL-{receipt_id}",
            "causation_id": f"CMD-CLINICAL-{receipt_id}",
            # No actual trusted authorization receipt exists in this slice.
            "authorization_decision_ref": None,
            "payload_ref": f"CLINICAL-EVENT-{receipt_id}",
        }
        enqueue(self.db, envelope)
