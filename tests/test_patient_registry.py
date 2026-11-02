"""Canonical patient-registry operational tests; opaque fictional identifiers only."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.patient_registry import (
    PatientRegistry, PatientRegistryConflict, PatientRegistryDenied,
    PatientRegistryError,
)


class PatientRegistryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "patient-identity.sqlite"
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.allow = lambda actor, subject, action, purpose: actor == "CLINICIAN-ONE"
        self.registry = PatientRegistry(self.db, self.allow)

    def create(self, **overrides):
        data = {"organization": "HOSPITAL-ONE", "actor": "CLINICIAN-ONE",
                "purpose": "care", "request_key": "REQUEST-ONE"}
        data.update(overrides)
        return self.registry.create_patient(**data)

    def test_registration_is_durable_idempotent_and_org_scoped(self):
        first = self.create()
        self.assertFalse(first["duplicate"])
        patient_id = first["patient_id"]
        self.assertTrue(patient_id.startswith("PAT-"))
        self.assertEqual(self.create(), {"patient_id": patient_id, "duplicate": True})
        self.assertEqual(
            self.registry.get_patient(patient_id, actor="CLINICIAN-ONE", purpose="care")["status"],
            "active",
        )
        self.assertEqual(len(self.registry.list_patients(
            organization="HOSPITAL-ONE", actor="CLINICIAN-ONE", purpose="care")), 1)
        second = self.create(organization="HOSPITAL-TWO")
        self.assertNotEqual(second["patient_id"], patient_id)
        self.assertEqual(len(self.registry.list_patients(
            organization="HOSPITAL-TWO", actor="CLINICIAN-ONE", purpose="care")), 1)
        self.db.close()
        self.db = sqlite3.connect(self.path)
        self.registry = PatientRegistry(self.db, self.allow)
        self.assertEqual(self.create(), {"patient_id": patient_id, "duplicate": True})
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_patients").fetchone()[0], 2)

    def test_requires_trusted_authorizer_for_all_external_operations(self):
        locked = PatientRegistry(self.db)
        with self.assertRaises(PatientRegistryDenied):
            locked.create_patient(organization="HOSPITAL-ONE",
                                  actor="CLINICIAN-ONE", purpose="care",
                                  request_key="REQUEST-X")
        created = self.create()
        with self.assertRaises(PatientRegistryDenied):
            locked.get_patient(created["patient_id"], actor="CLINICIAN-ONE", purpose="care")
        with self.assertRaises(PatientRegistryDenied):
            locked.list_patients(
                organization="HOSPITAL-ONE", actor="CLINICIAN-ONE", purpose="care")
        with self.assertRaises(PatientRegistryDenied):
            locked.suspend_patient(created["patient_id"], actor="CLINICIAN-ONE",
                                   purpose="care", expected_revision=1)
        with self.assertRaises(PatientRegistryDenied):
            self.registry.get_patient(created["patient_id"], actor="UNTRUSTED",
                                      purpose="care")

    def test_same_request_key_new_actor_or_purpose_is_conflict(self):
        first = self.create()
        self.registry.authorizer = lambda *_: True
        with self.assertRaises(PatientRegistryConflict):
            self.create(actor="CLINICIAN-TWO")
        with self.assertRaises(PatientRegistryConflict):
            self.create(purpose="research")
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_patients").fetchone()[0], 1)
        self.assertEqual(self.create()["patient_id"], first["patient_id"])

    def test_state_transitions_are_revised_and_immutable_receipts(self):
        pid = self.create()["patient_id"]
        result = self.registry.suspend_patient(
            pid, actor="CLINICIAN-ONE", purpose="care", expected_revision=1)
        self.assertEqual(result["revision"], 2)
        with self.assertRaises(PatientRegistryDenied):
            self.registry.require_patient(pid)
        with self.assertRaises(PatientRegistryConflict):
            self.registry.suspend_patient(
                pid, actor="CLINICIAN-ONE", purpose="care", expected_revision=1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM identity_create_receipts")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE identity_domain_events SET event_type='tampered'")

    def test_host_event_is_transactional_and_contains_no_patient_narrative(self):
        pid = self.create()["patient_id"]
        self.db.execute("CREATE TABLE clinical_encounters_test(id TEXT PRIMARY KEY)")
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with self.db:
                self.db.execute("INSERT INTO clinical_encounters_test VALUES ('ENC-ONE')")
                self.registry.append_event(pid, "clinical.encounter.started",
                                           encounter_id="ENC-ONE")
                raise RuntimeError("failure")
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM clinical_encounters_test").fetchone()[0], 0)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_domain_events").fetchone()[0], 1)
        with self.db:
            self.db.execute("INSERT INTO clinical_encounters_test VALUES ('ENC-ONE')")
            self.registry.append_event(pid, "clinical.encounter.started",
                                       encounter_id="ENC-ONE")
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM identity_domain_events").fetchone()[0], 2)
        with self.assertRaises(PatientRegistryError):
            self.registry.append_event(pid, "clinical.encounter.started", actor="any")

    def test_unverified_identity_and_real_data_are_not_accepted(self):
        with self.assertRaises(PatientRegistryError):
            self.create(organization="Hospital A/123")
        with self.assertRaises(PatientRegistryError):
            self.create(request_key="X")
        created = self.create()
        with self.assertRaises(PatientRegistryDenied):
            self.registry.get_patient(created["patient_id"], actor="CLINICIAN-ONE",
                                      purpose="unauthorized")
        with self.assertRaises(PatientRegistryError):
            self.registry.suspend_patient(
                created["patient_id"], actor="CLINICIAN-ONE",
                purpose="care", expected_revision=True)


if __name__ == "__main__":
    unittest.main()
