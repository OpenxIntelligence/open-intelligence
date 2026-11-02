"""Synthetic-only adapter between canonical patient registry and first-party LIS.

The case is a bounded source/evidence workspace, NOT another patient identity.
Neither proof reference nor test authorizer is verified identity, consent, or a
licensed clinical sign-off. Do not expose this domain through public HTTP.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from .clinical_lab import ClinicalLabOperations
from .patient_registry import PatientRegistry, PatientRegistryDenied, _key
from .platform_events import OutboxContractError, consume_ordered, enqueue, validate_event
from .store import CaseStore, InvalidInput

EVENT_TYPES = {
    "clinical_lab_order_requested": "lab.order.requested",
    "clinical_lab_order_cancelled": "lab.order.cancelled",
    "clinical_lab_specimen_accessioned": "lab.specimen.accessioned",
    "clinical_lab_qc_recorded": "lab.qc.recorded",
    "clinical_lab_observation_released": "lab.observation.released",
}
LAB_COMMANDS = frozenset({
    "request_lab_order", "cancel_order", "accession_specimen",
    "record_quality_check", "release_observation",
})
BINDINGS = """
CREATE TABLE IF NOT EXISTS identity_case_bindings (
  case_id TEXT PRIMARY KEY REFERENCES cases(case_id),
  patient_id TEXT NOT NULL REFERENCES identity_patients(patient_id),
  source_organization TEXT NOT NULL, source_system TEXT NOT NULL,
  source_subject_ref TEXT NOT NULL, review_ref TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','revoked')),
  revoked_at TEXT, revocation_reason TEXT,
  UNIQUE(source_organization,source_system,source_subject_ref)
);
CREATE INDEX IF NOT EXISTS idx_identity_case_binding_patient
  ON identity_case_bindings(patient_id);
"""
REVIEW = """
CREATE TABLE IF NOT EXISTS lab_world_model_review_candidates (
 event_id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, case_id TEXT NOT NULL,
 accession_id INTEGER NOT NULL, specimen_id TEXT NOT NULL,
 source_version_id INTEGER NOT NULL, assertion_id INTEGER NOT NULL,
 finding_key TEXT NOT NULL, reported_state TEXT NOT NULL,
 review_state TEXT NOT NULL CHECK(review_state='pending'),
 received_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _src_ref(source_id: object) -> str | None:
    if source_id is None:
        return None
    if type(source_id) is not int or source_id < 1:
        raise InvalidInput("source version reference must be a positive integer")
    return f"SRC-V-{source_id}"


class LinkedLabCaseStore(CaseStore):
    """The existing CaseStore event insertion plus an atomic outbox hook.

    Only actual LIS command events need the hook. Calling unwrapped LIS
    operations fails closed; never publish events after their command commits.
    """

    def __init__(self, db_path):
        super().__init__(db_path)
        self._lab_bridge = None
        self._lab_context = None

    def _event(self, case_id: str, kind: str, **details: object) -> None:
        super()._event(case_id, kind, **details)
        if kind in EVENT_TYPES:
            if not self.db.in_transaction or self._lab_bridge is None or self._lab_context is None:
                raise InvalidInput("LIS command requires an authorized canonical bridge")
            receipt_id = self.db.execute("SELECT last_insert_rowid()").fetchone()[0]
            self._lab_bridge._publish(case_id, kind, receipt_id, details)


class CanonicalLabBridge:
    """Explicit, reviewed one-case-to-one-patient link and guarded LIS commands."""

    def __init__(self, store: LinkedLabCaseStore, registry: PatientRegistry,
                 authorizer: Callable[[str, str, str, str], bool] | None = None):
        if not isinstance(store, LinkedLabCaseStore) or registry.db is not store.db:
            raise TypeError("bridge requires one canonical registry and one SQLite connection")
        if store.db.in_transaction:
            raise InvalidInput("initialize case linkage outside an active transaction")
        self.store = store
        self.db = store.db
        self.registry = registry
        self.authorizer = authorizer
        self.db.executescript(BINDINGS)
        self.lab = ClinicalLabOperations(store)
        if store._lab_bridge is not None:
            raise InvalidInput("a case store may have only one lab integration bridge")
        store._lab_bridge = self

    def _allow(self, actor: str, patient_id: str, action: str, purpose: str) -> None:
        _key(actor, "actor")
        _key(patient_id, "patient_id")
        if purpose not in {"care", "operations"}:
            raise PatientRegistryDenied("invalid laboratory use purpose")
        try:
            allowed = bool(self.authorizer and
                           self.authorizer(actor, patient_id, action, purpose))
        except Exception:
            allowed = False
        if not allowed:
            raise PatientRegistryDenied("laboratory bridge access denied")
        self.registry.require_patient(patient_id)

    def bind_case(self, *, patient_id: str, case_id: str,
                  source_organization: str, source_system: str,
                  source_subject_ref: str, review_ref: str,
                  actor: str, purpose: str) -> dict:
        """Requires a human-reviewed reference; never matches by name or label."""
        self._allow(actor, patient_id, "case_bind", purpose)
        self.store._case(case_id)
        for value, name in (
            (case_id, "case_id"), (source_organization, "source_organization"),
            (source_system, "source_system"),
            (source_subject_ref, "source_subject_ref"),
            (review_ref, "review_ref"),
        ):
            _key(value, name)
        if self.db.in_transaction:
            raise InvalidInput("binding owns its transaction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute(
                "SELECT * FROM identity_case_bindings WHERE case_id=?", (case_id,)
            ).fetchone()
            signature = (patient_id, source_organization, source_system,
                         source_subject_ref, review_ref)
            if prior:
                recorded = tuple(prior[k] for k in (
                    "patient_id", "source_organization", "source_system",
                    "source_subject_ref", "review_ref"))
                if recorded != signature or prior["status"] != "active":
                    raise InvalidInput("case is permanently linked or revoked; no reassignment")
                self.db.commit()
                return {"case_id": case_id, "patient_id": patient_id, "duplicate": True}
            self.db.execute(
                """INSERT INTO identity_case_bindings
                   (case_id,patient_id,source_organization,source_system,
                    source_subject_ref,review_ref,created_by,created_at,status)
                   VALUES(?,?,?,?,?,?,?,?,'active')""",
                (case_id, patient_id, source_organization, source_system,
                 source_subject_ref, review_ref, actor, _now()))
            self.registry.append_event(
                patient_id, "identity.case_binding_created",
                case_id=case_id, review_ref=review_ref,
                source_organization=source_organization, source_system=source_system)
            self.db.commit()
            return {"case_id": case_id, "patient_id": patient_id, "duplicate": False}
        except BaseException:
            self.db.rollback()
            raise

    def revoke_case(self, *, patient_id: str, case_id: str,
                    actor: str, purpose: str, reason: str) -> None:
        self._allow(actor, patient_id, "case_revoke", purpose)
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 200:
            raise InvalidInput("revocation requires a meaningful bounded reason")
        if self.db.in_transaction:
            raise InvalidInput("revocation owns its transaction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self._binding(patient_id, case_id)
            self.db.execute(
                """UPDATE identity_case_bindings
                   SET status='revoked',revoked_at=?,revocation_reason=?
                   WHERE case_id=? AND patient_id=? AND status='active'""",
                (_now(), reason.strip(), case_id, patient_id))
            self.registry.append_event(
                patient_id, "identity.case_binding_revoked",
                case_id=case_id, actor=actor)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _binding(self, patient_id: str, case_id: str) -> sqlite3.Row:
        self.registry.require_patient(patient_id)
        row = self.db.execute(
            "SELECT * FROM identity_case_bindings WHERE case_id=?", (case_id,)
        ).fetchone()
        if row is None or row["patient_id"] != patient_id or row["status"] != "active":
            raise PatientRegistryDenied("missing, revoked or mismatched case binding")
        return row

    def command(self, patient_id: str, case_id: str, method: str, *args,
                actor: str, purpose: str) -> dict:
        """Only allow listed real LIS commands with bound patient/case."""
        if method not in LAB_COMMANDS:
            raise InvalidInput("unsupported laboratory command")
        self._allow(actor, patient_id, "lab_" + method, purpose)
        self._binding(patient_id, case_id)
        if self.store._lab_context is not None:
            raise InvalidInput("reentrant laboratory context denied")
        self.store._lab_context = (patient_id, case_id, actor, purpose)
        try:
            return getattr(self.lab, method)(case_id, *args)
        finally:
            self.store._lab_context = None

    def case_state(self, patient_id: str, case_id: str, *,
                   actor: str, purpose: str) -> dict:
        self._allow(actor, patient_id, "lab_read", purpose)
        self._binding(patient_id, case_id)
        return self.lab.case_state(case_id)

    def _publish(self, case_id: str, kind: str, receipt_id: int, details: dict) -> None:
        patient_id, expected_case, actor, purpose = self.store._lab_context
        if case_id != expected_case:
            raise InvalidInput("lab event tried to publish under another case")
        self._allow(actor, patient_id, "lab_" + kind, purpose)
        self._binding(patient_id, case_id)
        revision = self.db.execute(
            """SELECT COUNT(*) FROM events WHERE case_id=?
               AND kind IN (?,?,?,?,?)""",
            (case_id, *EVENT_TYPES.keys())).fetchone()[0]
        # Receipt refers to the authoritative CaseStore event, not report text.
        stamp = _now()
        enqueue(self.db, {
            "schema": "oi.domain-event/1",
            "event_id": f"EV-LAB-{receipt_id}",
            "event_type": EVENT_TYPES[kind],
            "owner_domain": "lab",
            "issuer_namespace": "urn:oi:internal:lab",
            "aggregate": {"type": "lab_case_activity", "id": case_id,
                          "revision": revision},
            "subject_binding_id": patient_id,
            "source_version_ref": _src_ref(details.get("source_version_id")),
            "supersedes_source_ref": None,
            "occurred_at": {"value": stamp, "precision": "second"},
            "recorded_at": stamp,
            "correlation_id": f"FLOW-LAB-{case_id}",
            "causation_id": f"CMD-LAB-{receipt_id}",
            "authorization_decision_ref": None,
            "payload_ref": f"LAB-EVENT-{receipt_id}",
        })


def install_lab_review_projection(receiver: sqlite3.Connection) -> None:
    """Run during migration, after platform_events.install, outside a transaction."""
    if receiver.in_transaction:
        raise OutboxContractError("projection migration requires an idle connection")
    receiver.executescript(REVIEW)


def consume_lab_review_event(
    receiver: sqlite3.Connection, bridge: CanonicalLabBridge,
    event: dict, *, patient_id: str, case_id: str, actor: str, purpose: str,
) -> bool:
    """Consume an ordered event; only QC-backed RELEASE creates a review candidate.

    The consumer rechecks binding, issuer, case, source, specimen and actual
    release against the authoritative store. This is not clinical validation.
    """
    bridge._allow(actor, patient_id, "lab_event_consume", purpose)
    bridge._binding(patient_id, case_id)
    ev = validate_event(event)
    if (ev["owner_domain"] != "lab" or
        ev["issuer_namespace"] != "urn:oi:internal:lab" or
        ev["event_type"] not in EVENT_TYPES.values() or
        ev["aggregate"]["type"] != "lab_case_activity" or
        ev["aggregate"]["id"] != case_id or
        ev["subject_binding_id"] != patient_id):
        raise OutboxContractError("lab consumer rejected issuer/subject/case mismatch")
    if not ev["payload_ref"].startswith("LAB-EVENT-"):
        raise OutboxContractError("invalid lab receipt reference")
    try:
        receipt_id = int(ev["payload_ref"][len("LAB-EVENT-"):])
    except ValueError:
        raise OutboxContractError("invalid lab event receipt") from None
    row = bridge.db.execute(
        "SELECT kind,details FROM events WHERE id=? AND case_id=?",
        (receipt_id, case_id)).fetchone()
    if row is None or EVENT_TYPES.get(row["kind"]) != ev["event_type"]:
        raise OutboxContractError("lab event has no matching authoritative receipt")
    details = json.loads(row["details"])
    if ev["source_version_ref"] != _src_ref(details.get("source_version_id")):
        raise OutboxContractError("source version reference changed")
    released = None
    if row["kind"] == "clinical_lab_observation_released":
        released = bridge.db.execute(
            """SELECT r.*,a.specimen_id,a.case_id AS accession_case,
                      q.outcome AS qc_outcome,
                      q.source_version_id AS qc_source,
                      s.state AS source_state,s.specimen_id AS source_specimen,
                      ordsrc.state AS order_source_state,
                      f.source_version_id AS assertion_source,
                      f.case_id AS assertion_case
               FROM clinical_lab_releases r
               JOIN clinical_lab_accessions a ON a.id=r.accession_id
               JOIN clinical_lab_orders o ON o.id=a.order_id
               JOIN source_versions ordsrc ON ordsrc.id=o.source_version_id
               JOIN clinical_lab_qc q ON q.id=r.qc_id
               JOIN source_versions s ON s.id=r.source_version_id
               JOIN assertions f ON f.id=r.assertion_id
               WHERE r.id=? AND r.case_id=? AND o.case_id=?""",
            (details.get("release_id"), case_id, case_id)
        ).fetchone()
        if released is None or (
            released["accession_case"] != case_id or
            released["qc_outcome"] != "passed" or
            released["qc_source"] != released["source_version_id"] or
            released["source_state"] != "current" or
            released["order_source_state"] != "current" or
            released["source_specimen"] != released["specimen_id"] or
            released["assertion_case"] != case_id or
            released["assertion_source"] != released["source_version_id"] or
            released["source_version_id"] != details.get("source_version_id") or
            released["assertion_id"] != details.get("assertion_id") or
            released["qc_id"] != details.get("qc_id")
        ):
            raise OutboxContractError("release source/QC/specimen provenance is not current")
        latest = bridge.db.execute(
            "SELECT id FROM clinical_lab_qc WHERE accession_id=? ORDER BY id DESC LIMIT 1",
            (released["accession_id"],)).fetchone()
        if latest is None or latest[0] != released["qc_id"]:
            raise OutboxContractError("release requires fresh latest QC")
    if not receiver.in_transaction:
        raise OutboxContractError("receiving domain must own the transaction")

    def apply_effect(db: sqlite3.Connection, _: dict) -> None:
        if released is not None:
            db.execute(
                """INSERT INTO lab_world_model_review_candidates
                   (event_id,patient_id,case_id,accession_id,specimen_id,
                    source_version_id,assertion_id,finding_key,reported_state,
                    review_state,received_at)
                   VALUES(?,?,?,?,?,?,?,?,?,'pending',?)""",
                (ev["event_id"], patient_id, case_id, released["accession_id"],
                 released["specimen_id"], released["source_version_id"],
                 released["assertion_id"], released["finding_key"],
                 released["reported_state"], _now()))
    return consume_ordered(receiver, "LAB-WORLD-MODEL-REVIEW", ev, apply_effect)
