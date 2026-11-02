"""Integrated first-party identity, clinical EHR and durable outbox behavior.

No mock domain records: these tests execute actual SQLite operations. The
policy callbacks are TEST DOUBLES, not verified clinician identity or consent.
"""
from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_intelligence.clinical_encounters import ClinicalEncounters, ClinicalAuthorizationError
from open_intelligence.patient_registry import PatientRegistry, PatientRegistryDenied
from open_intelligence.platform_events import claim, complete, validate_event
from open_intelligence.platform_integration import (
    CanonicalEHRHost, VerifiedEHRChangeConsumer, IntegrationError,
)


class IntegratedClinicalPlatformTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.db = sqlite3.connect(Path(t.name) / "one-patient-record.sqlite")
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.actor = "CLINICIAN-ONE"
        self.policy = lambda actor, subject, action, purpose: (
            actor == self.actor and purpose == "care" and
            (subject == "HOSPITAL-ONE" or subject.startswith("PAT-")))
        self.registry = PatientRegistry(self.db, authorizer=self.policy)
        self.patient_id = self.registry.create_patient(
            organization="HOSPITAL-ONE", actor=self.actor, purpose="care",
            request_key="CREATE-PATIENT-0001")["patient_id"]
        self.host = CanonicalEHRHost(self.registry)
        self.ehr = ClinicalEncounters(self.host, authorizer=self.policy)
        self.consumer = VerifiedEHRChangeConsumer(self.registry, authorizer=self.policy)

    def _schedule(self, request_key="SCHEDULE-ORDER-001"):
        return self.ehr.schedule(
            self.patient_id, "VISIT-0001", "outpatient", "2026-11-02",
            actor=self.actor, purpose="care", request_key=request_key)

    def _events(self):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT envelope_json FROM platform_outbox ORDER BY seq")]

    def _begin(self):
        enc = self._schedule()
        return self.ehr.transition(
            self.patient_id, enc["encounter_id"], "in_progress",
            expected_revision=1, actor=self.actor, purpose="care",
            request_key="BEGIN-VISIT-00001")

    def test_real_operational_journey_one_patient_identity_one_transactional_event_flow(self):
        enc = self._begin()
        encounter_id = enc["encounter_id"]
        self.ehr.write_note(
            self.patient_id, encounter_id, "NOTE-0001", "Fictional authored note",
            expected_version=0, actor=self.actor, purpose="care",
            request_key="DRAFT-NOTE-00001")
        self.ehr.attest_note(
            self.patient_id, encounter_id, "NOTE-0001", expected_version=1,
            actor=self.actor, purpose="care", request_key="ATTEST-NOTE-0001")
        self.ehr.transition(
            self.patient_id, encounter_id, "completed", expected_revision=2,
            actor=self.actor, purpose="care", request_key="CLOSE-VISIT-0001")
        self.ehr.write_note(
            self.patient_id, encounter_id, "NOTE-0001", "Corrected fictional note",
            expected_version=2, correction_reason="Corrected laboratory reference",
            actor=self.actor, purpose="care", request_key="CORRECT-NOTE-001")
        self.ehr.attest_note(
            self.patient_id, encounter_id, "NOTE-0001", expected_version=3,
            actor=self.actor, purpose="care", request_key="ATTEST-CORRECTION-01")
        events = self._events()
        self.assertEqual(len(events), 7)
        self.assertEqual({e["subject_binding_id"] for e in events}, {self.patient_id})
        self.assertEqual({e["owner_domain"] for e in events}, {"ehr"})
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_domain_events").fetchone()[0],
            8)  # initial patient creation + 7 EHR events
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='cases'").fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM identity_patients").fetchone()[0], 1)
        self.assertEqual([e["aggregate"]["revision"] for e in events
                          if e["aggregate"]["type"] == "encounter"], [1, 2, 3])
        self.assertEqual([e["aggregate"]["revision"] for e in events
                          if e["aggregate"]["type"] == "note"], [1, 2, 3, 4])
        self.assertNotIn("Fictional authored note", json.dumps(events))
        self.assertNotIn("Corrected laboratory reference", json.dumps(events))
        for ev in events:
            validate_event(ev)
            self.assertTrue(self.consumer.apply(ev, actor=self.actor, purpose="care"))
            self.assertFalse(self.consumer.apply(ev, actor=self.actor, purpose="care"))
        self.assertEqual(len(self.consumer.list_changes(
            self.patient_id, actor=self.actor, purpose="care")), 7)
        # A read model has POINTERS only; the original EHR owns note text.
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM platform_ehr_change_index").fetchone()[0], 7)
        self.assertNotIn("Fictional", " ".join(str(x) for x in
            self.db.execute("SELECT * FROM platform_ehr_change_index").fetchall()))
        self.assertEqual([x["status"] for x in self.ehr.note_history(
            self.patient_id, encounter_id, "NOTE-0001", actor=self.actor,
            purpose="care")], ["draft", "attested", "draft_correction", "attested_correction"])

    def test_outbox_delivery_lease_and_consumer_receipt(self):
        self._schedule()
        leased = claim(self.db, "WORKER-CLINICAL", now=1000)
        self.assertEqual(len(leased), 1)
        self.assertTrue(self.consumer.apply(leased[0]["event"], actor=self.actor, purpose="care"))
        with self.db:
            complete(self.db, leased[0]["event_id"], "WORKER-CLINICAL", now=1001)
        self.assertEqual(self.db.execute(
            "SELECT state FROM platform_outbox").fetchone()[0], "dispatched")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM platform_inbox_receipts").fetchone()[0], 1)
        self.assertEqual(claim(self.db, "WORKER-OTHER", now=2000), [])

    def test_idempotency_and_rollbacks_cover_state_local_journal_outbox_and_receipt(self):
        original = self._schedule()
        before = {table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("clinical_encounters", "clinical_encounter_commands",
                                "platform_outbox", "identity_domain_events")}
        self.assertEqual(self._schedule(), original)
        after = {table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                 for table in before}
        self.assertEqual(before, after)
        with patch("open_intelligence.platform_integration.enqueue",
                   side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaisesRegex(RuntimeError, "outbox unavailable"):
                self.ehr.schedule(
                    self.patient_id, "VISIT-0002", "outpatient", "2026-11-02",
                    actor=self.actor, purpose="care", request_key="FAIL-WRITE-00001")
        for table, count in before.items():
            self.assertEqual(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], count)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_encounters WHERE external_key='VISIT-0002'").fetchone()[0], 0)
        self.assertEqual(self.ehr.schedule(
            self.patient_id, "VISIT-0002", "outpatient", "2026-11-02",
            actor=self.actor, purpose="care", request_key="FAIL-WRITE-00001")["status"], "scheduled")

    def test_unbound_wrong_patient_and_forged_events_never_enter_projection(self):
        self._schedule()
        e = self._events()[0]
        another = self.registry.create_patient(
            organization="HOSPITAL-ONE", actor=self.actor, purpose="care",
            request_key="CREATE-PATIENT-0002")["patient_id"]
        tampered = copy.deepcopy(e)
        tampered["subject_binding_id"] = another
        with self.assertRaises(IntegrationError):
            self.consumer.apply(tampered, actor=self.actor, purpose="care")
        tampered = copy.deepcopy(e)
        tampered["aggregate"]["id"] = "ENC-999999"
        with self.assertRaises(IntegrationError):
            self.consumer.apply(tampered, actor=self.actor, purpose="care")
        tampered = copy.deepcopy(e)
        tampered["payload_ref"] = "EHR-NOTE-9999-V1"
        with self.assertRaises(IntegrationError):
            self.consumer.apply(tampered, actor=self.actor, purpose="care")
        tampered = copy.deepcopy(e)
        tampered["authorization_decision_ref"] = "FAKE-APPROVAL"
        with self.assertRaises(IntegrationError):
            self.consumer.apply(tampered, actor=self.actor, purpose="care")
        tampered = copy.deepcopy(e)
        tampered["event_type"] = "laboratory.order.requested"
        tampered["owner_domain"] = "laboratory"
        with self.assertRaises(IntegrationError):
            self.consumer.apply(tampered, actor=self.actor, purpose="care")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM platform_ehr_change_index").fetchone()[0], 0)

    def test_policy_denial_suspension_and_fail_closed_consumer(self):
        self._schedule()
        e = self._events()[0]
        with self.assertRaises(PermissionError):
            self.consumer.apply(e, actor="UNTRUSTED", purpose="care")
        with self.assertRaises(ClinicalAuthorizationError):
            self.ehr.list_encounters(self.patient_id, actor="UNTRUSTED", purpose="care")
        self.registry.suspend_patient(self.patient_id, actor=self.actor,
                                      purpose="care", expected_revision=1)
        with self.assertRaises(PatientRegistryDenied):
            self.consumer.apply(e, actor=self.actor, purpose="care")
        with self.assertRaises(PatientRegistryDenied):
            self.ehr.list_encounters(self.patient_id, actor=self.actor, purpose="care")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM platform_ehr_change_index").fetchone()[0], 0)

    def test_out_of_order_change_event_rejected_without_side_effects(self):
        self._begin()
        first, second = self._events()
        from open_intelligence.platform_events import OutboxContractError
        with self.assertRaisesRegex(OutboxContractError, "expected 1"):
            self.consumer.apply(second, actor=self.actor, purpose="care")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM platform_ehr_change_index").fetchone()[0], 0)
        self.assertTrue(self.consumer.apply(first, actor=self.actor, purpose="care"))
        self.assertTrue(self.consumer.apply(second, actor=self.actor, purpose="care"))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM platform_inbox_receipts").fetchone()[0], 2)

    def test_reopen_existing_db_preserves_patient_identity_commands_and_outbox(self):
        scheduled = self._schedule()
        original_event = self._events()[0]
        path = Path(self.db.execute("PRAGMA database_list").fetchone()[2])
        self.db.close()
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(self.db.close)
        self.registry = PatientRegistry(self.db, self.policy)
        self.host = CanonicalEHRHost(self.registry)
        self.ehr = ClinicalEncounters(self.host, self.policy)
        self.consumer = VerifiedEHRChangeConsumer(self.registry, authorizer=self.policy)
        self.assertEqual(self._schedule(), scheduled)
        self.assertEqual(self._events(), [original_event])
        self.assertTrue(self.consumer.apply(original_event, actor=self.actor, purpose="care"))
        self.assertFalse(self.consumer.apply(original_event, actor=self.actor, purpose="care"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM identity_patients").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 1)

    def test_legacy_lis_is_not_implicitly_identical_to_canonical_patient(self):
        from open_intelligence.clinical_lab import ClinicalLabOperations
        with self.assertRaises(TypeError):
            ClinicalLabOperations(self.registry)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='cases'").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM identity_patients").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
