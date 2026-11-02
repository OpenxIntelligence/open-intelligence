"""One governed read projection for authored notes and laboratory review evidence.

This is a first-party *read* contract over existing EHR, lab, source and identity
owners. It stores no duplicate patient, clinical fact or diagnostic conclusion.

The receiving lab-review queue and original source store live in different
connections: this is not a global distributed snapshot. Each laboratory claim
is re-checked against authoritative source, QC, accession, case and outbox
receipts at read time; nothing stale is silently presented as current.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Callable

from .clinical_lab_bridge import CanonicalLabBridge
from .clinical_source_provenance import ClinicalSourceProvenance
from .patient_registry import PatientRegistry, PatientRegistryDenied
from .platform_events import OutboxContractError, validate_event


class ClinicalContinuityError(ValueError):
    """Inconsistent provenance: do not disclose a possibly misbound record."""


class ClinicalContinuityView:
    """Read-only reconciliation of existing note and lab-receiver references.

    Policy checks are injected and fail closed. Callers must provide a verified
    actor and purpose via the production host; the examples supply test doubles
    and may never process real patient information. No HTTP route is registered.
    """

    def __init__(self, registry: PatientRegistry, lab: CanonicalLabBridge,
                 provenance: ClinicalSourceProvenance,
                 lab_receiver: sqlite3.Connection,
                 authorizer: Callable[[str, str, str, str], bool] | None = None):
        if registry.db is not lab.db or registry.db is not provenance.db:
            raise ClinicalContinuityError("domains must share the authoritative patient/source connection")
        if lab_receiver is registry.db:
            raise ClinicalContinuityError("lab evidence receiver must be independently owned")
        self.registry = registry
        self.lab = lab
        self.provenance = provenance
        self.receiver = lab_receiver
        self.authorizer = authorizer

    def _authorize(self, patient_id: str, case_id: str,
                   actor: str, purpose: str) -> None:
        if purpose not in {"care", "operations"}:
            raise PatientRegistryDenied("unsupported clinical read purpose")
        try:
            allowed = bool(self.authorizer and
                           self.authorizer(actor, patient_id,
                                           "clinical_continuity.read", purpose))
        except Exception:
            allowed = False
        if not allowed:
            raise PatientRegistryDenied("clinical continuity access denied")
        self.lab._allow(actor, patient_id, "lab_read", purpose)
        self.lab._binding(patient_id, case_id)
        # ClinicalSourceProvenance performs its own independent patient/case
        # binding and source-read authorization on context_snapshot.

    def _lab_record(self, patient_id: str, case_id: str, candidate: dict) -> dict:
        """Verify a receiver candidate against the authoritative source ledger."""
        if (candidate["patient_id"] != patient_id or candidate["case_id"] != case_id or
                candidate["review_state"] != "pending"):
            raise ClinicalContinuityError("lab receiver record is not bound to this subject")
        outbox = self.registry.db.execute(
            "SELECT envelope_json,event_hash FROM platform_outbox WHERE event_id=?",
            (candidate["event_id"],),
        ).fetchone()
        if outbox is None:
            raise ClinicalContinuityError("lab review record lacks original event")
        try:
            event = validate_event(json.loads(outbox["envelope_json"]))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, OutboxContractError):
            raise ClinicalContinuityError("lab event evidence is invalid") from None
        canonical_json = json.dumps(event, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True)
        if hashlib.sha256(canonical_json.encode()).hexdigest() != outbox["event_hash"]:
            raise ClinicalContinuityError("lab outbox content hash is inconsistent")
        if (event["event_id"] != candidate["event_id"] or
            event["event_type"] != "lab.observation.released" or
            event["owner_domain"] != "lab" or
            event["issuer_namespace"] != "urn:oi:internal:lab" or
            event["aggregate"]["type"] != "lab_case_activity" or
            event["aggregate"]["id"] != case_id or
            event["subject_binding_id"] != patient_id or
            event["source_version_ref"] != f"SRC-V-{candidate['source_version_id']}"):
            raise ClinicalContinuityError("lab review event fails identity and source proof")
        payload_ref = event["payload_ref"]
        if not isinstance(payload_ref, str) or not payload_ref.startswith("LAB-EVENT-"):
            raise ClinicalContinuityError("lab event has no source receipt pointer")
        try:
            receipt_id = int(payload_ref[len("LAB-EVENT-"):])
        except ValueError:
            raise ClinicalContinuityError("lab source receipt pointer is invalid") from None
        if receipt_id < 1 or event["event_id"] != f"EV-LAB-{receipt_id}":
            raise ClinicalContinuityError("lab event identifier conflicts with original receipt")
        receipt = self.registry.db.execute(
            "SELECT kind, details FROM events WHERE id=? AND case_id=?",
            (receipt_id, case_id),
        ).fetchone()
        if receipt is None or receipt["kind"] != "clinical_lab_observation_released":
            raise ClinicalContinuityError("lab event has no matching release history")
        try:
            source_details = json.loads(receipt["details"])
        except (ValueError, TypeError):
            raise ClinicalContinuityError("original lab event details are corrupt") from None
        if (source_details.get("source_version_id") != candidate["source_version_id"] or
            source_details.get("assertion_id") != candidate["assertion_id"]):
            raise ClinicalContinuityError("lab evidence pointer differs from the release receipt")
        rows = self.registry.db.execute(
            """SELECT r.id, r.case_id, r.accession_id, r.source_version_id,
                      r.assertion_id, r.qc_id, r.finding_key, r.reported_state,
                      a.specimen_id, a.order_id, o.state AS order_state,
                      q.outcome AS qc_outcome,
                      q.source_version_id AS qc_source,
                      s.state AS source_state, s.specimen_id AS source_specimen,
                      os.state AS order_source_state,
                      f.source_version_id AS assertion_source,
                      f.case_id AS assertion_case
               FROM clinical_lab_releases r
               JOIN clinical_lab_accessions a ON a.id=r.accession_id
               JOIN clinical_lab_orders o ON o.id=a.order_id
               JOIN source_versions os ON os.id=o.source_version_id
               JOIN clinical_lab_qc q ON q.id=r.qc_id
               JOIN source_versions s ON s.id=r.source_version_id
               JOIN assertions f ON f.id=r.assertion_id
               WHERE r.case_id=? AND o.case_id=? AND a.case_id=?
                 AND r.accession_id=? AND r.source_version_id=?
                 AND r.assertion_id=? AND r.finding_key=? AND r.reported_state=?""",
            (case_id, case_id, case_id, candidate["accession_id"],
             candidate["source_version_id"], candidate["assertion_id"],
             candidate["finding_key"], candidate["reported_state"]),
        ).fetchall()
        if len(rows) != 1:
            raise ClinicalContinuityError("lab release cannot be uniquely traced")
        row = rows[0]
        if (row["id"] != source_details.get("release_id") or
            row["qc_id"] != source_details.get("qc_id") or
            row["specimen_id"] != candidate["specimen_id"] or
            row["assertion_case"] != case_id or
            row["assertion_source"] != row["source_version_id"] or
            row["source_specimen"] != candidate["specimen_id"] or
            row["qc_source"] != row["source_version_id"] or
            row["qc_outcome"] != "passed"):
            raise ClinicalContinuityError("lab accession, specimen or original QC is inconsistent")
        latest = self.registry.db.execute(
            """SELECT id,outcome,source_version_id FROM clinical_lab_qc
               WHERE accession_id=? ORDER BY id DESC LIMIT 1""",
            (row["accession_id"],),
        ).fetchone()
        if latest is None:
            raise ClinicalContinuityError("laboratory QC history is missing")
        if row["source_state"] != "current":
            freshness = "source_superseded_review_required"
        elif row["order_source_state"] != "current":
            freshness = "order_source_superseded_review_required"
        elif row["order_state"] == "cancelled":
            freshness = "order_cancelled_review_required"
        elif (latest["id"] != row["qc_id"] or latest["outcome"] != "passed" or
              latest["source_version_id"] != row["source_version_id"]):
            freshness = "quality_changed_review_required"
        else:
            freshness = "current_source_pending_clinician_review"
        return {
            "event_id": candidate["event_id"],
            "accession_id": candidate["accession_id"],
            "specimen_id": candidate["specimen_id"],
            "source_version_id": candidate["source_version_id"],
            "assertion_id": candidate["assertion_id"],
            "finding_key": candidate["finding_key"],
            "reported_state_as_stated": candidate["reported_state"],
            "original_review_state": "pending",
            "current_provenance_state": freshness,
            "clinical_assessment": "not_established",
        }

    def snapshot(self, patient_id: str, case_id: str, *,
                 actor: str, purpose: str) -> dict:
        """Return only source and clinical change pointers, not note body or PHI.

        Permissions and original lab records are revalidated every read. No
        long-lived cache is written. The caller must not interpret 'pending' as
        signed, clinically valid, normal, or safe. A separate policy-enforced
        patient/world-model transaction is needed for production consistency.
        """
        self._authorize(patient_id, case_id, actor, purpose)
        context = self.provenance.context_snapshot(
            patient_id, case_id, actor=actor, purpose=purpose)
        rows = self.receiver.execute(
            """SELECT * FROM lab_world_model_review_candidates
               WHERE patient_id=? AND case_id=? ORDER BY event_id""",
            (patient_id, case_id),
        ).fetchall()
        lab = [self._lab_record(patient_id, case_id, dict(r)) for r in rows]
        note_reviews = context["note_versions_requiring_source_review"]
        # A case grant can be revoked between the clinical source read and the
        # independent lab receiver read. Revalidate both policy boundaries
        # before releasing even an evidence pointer. This narrows, but does
        # not replace, the need for production cross-store snapshot control.
        self._authorize(patient_id, case_id, actor, purpose)
        self.provenance._allow(patient_id, case_id, actor=actor,
                               purpose=purpose, action="patient_context.read")
        return {
            "contract": "oi.clinical-continuity-review/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "encounters": context["encounters"],
            "note_versions": context["note_versions"],
            "note_source_links": context["note_source_links"],
            "lab_evidence_candidates": lab,
            "review_required": [
                *({"kind": "clinical_note", "note_version_id": k,
                    "reason": "source_superseded"} for k in note_reviews),
                *({"kind": "laboratory", "event_id": c["event_id"],
                    "reason": c["current_provenance_state"]} for c in lab),
            ],
            "patient_world_model_clinical_belief": "not_generated",
            "source_coverage": "source-linked_clinical_and_laboratory_only",
            "snapshot_consistency": "not_a_distributed_atomic_snapshot",
        }
