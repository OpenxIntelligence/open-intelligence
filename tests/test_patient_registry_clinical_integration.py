"""Cross-PR integration: PR #85 canonical patient host with PR #74 clinical domain.

Only fictional opaque identities. Injected authorizers are test predicates, not
trusted production credentials. This is no PHI, patient consent or clinical
signature validation. The test intentionally uses NO CaseStore/cases table.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.patient_registry import (
    PatientRegistry, PatientRegistryDenied,
)
from open_intelligence.clinical_encounters import (
    ClinicalEncounters, ClinicalAuthorizationError, ClinicalConflict,
)


class CanonicalIdentityEncounterIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "first-party-domains.sqlite"
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.registry_policy = lambda actor, subject, action, purpose: (
            actor == "CLINICIAN-ONE" and purpose == "care")
        self.registry = PatientRegistry(self.db, self.registry_policy)
        self.first = self.registry.create_patient(
            organization="HOSPITAL-ONE", actor="CLINICIAN-ONE",
            purpose="care", request_key="REGISTER-ONE")["patient_id"]
        self.other = self.registry.create_patient(
            organization="HOSPITAL-ONE", actor="CLINICIAN-ONE",
            purpose="care", request_key="REGISTER-TWO")["patient_id"]
        self.clinical_policy = lambda actor, patient, action, purpose: (
            actor == "CLINICIAN-ONE" and patient == self.first
            and purpose == "care" and action in {
                "encounter.schedule", "encounter.transition", "encounter.read",
                "note.write", "note.read", "note.attest"})
        self.clinical = ClinicalEncounters(self.registry, self.clinical_policy)
        self.actor = {"actor": "CLINICIAN-ONE", "purpose": "care"}

    def _schedule(self, request_key="REQUEST-SCHEDULE-01"):
        return self.clinical.schedule(
            self.first, "ENCOUNTER-ONE", "outpatient", "2026-11-02",
            request_key=request_key, **self.actor)

    def test_real_first_party_registry_hosts_encounter_and_corrected_note(self):
        self.assertFalse(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cases'").fetchone())
        schedule = self._schedule()
        self.assertEqual(schedule["status"], "scheduled")
        self.assertEqual(self._schedule(), schedule)  # exact idempotent retry
        begin = self.clinical.transition(
            self.first, schedule["encounter_id"], "in_progress",
            expected_revision=1, request_key="REQUEST-BEGIN-01", **self.actor)
        self.assertEqual(begin["status"], "in_progress")
        draft = self.clinical.write_note(
            self.first, schedule["encounter_id"], "NOTE-ONE",
            "Fictional, unverified encounter note; no real patient information.",
            expected_version=0, request_key="REQUEST-NOTE-01", **self.actor)
        self.assertEqual(draft["status"], "draft")
        signed_in_test = self.clinical.attest_note(
            self.first, schedule["encounter_id"], "NOTE-ONE",
            expected_version=1, request_key="REQUEST-ACK-01", **self.actor)
        self.assertEqual(signed_in_test["status"], "attested")
        correction = self.clinical.write_note(
            self.first, schedule["encounter_id"], "NOTE-ONE",
            "Corrected fictional encounter text; the first version remains retained.",
            expected_version=2, correction_reason="Synthetic author correction",
            request_key="REQUEST-CORRECT-01", **self.actor)
        self.assertEqual(correction["status"], "draft_correction")
        self.assertEqual(self.clinical.attest_note(
            self.first, schedule["encounter_id"], "NOTE-ONE",
            expected_version=3, request_key="REQUEST-ACK-CORRECT-01", **self.actor
        )["status"], "attested_correction")
        history = self.clinical.note_history(
            self.first, schedule["encounter_id"], "NOTE-ONE", **self.actor)
        self.assertEqual([h["status"] for h in history],
                         ["draft", "attested", "draft_correction", "attested_correction"])
        self.assertIn("Fictional, unverified", history[0]["body"])
        self.assertNotEqual(history[0]["sha256"], history[-1]["sha256"])
        self.assertEqual({x["patient_id"] for x in self.clinical.list_encounters(
            self.first, **self.actor)}, {self.first})
        # Events are on the canonical host, carrying references not clinical text.
        events = self.db.execute(
            "SELECT event_type,metadata_json FROM identity_domain_events "
            "WHERE patient_id=? ORDER BY id", (self.first,)).fetchall()
        self.assertGreaterEqual(len(events), 6)
        self.assertNotIn("Corrected fictional encounter", repr(events))
        self.assertFalse(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cases'").fetchone())

    def test_patient_isolation_and_suspension_stop_new_clinical_operations(self):
        self._schedule()
        with self.assertRaises(ClinicalAuthorizationError):
            self.clinical.schedule(
                self.other, "ENCOUNTER-TWO", "outpatient", "2026-11-02",
                request_key="REQUEST-OTHER-01", **self.actor)
        with self.assertRaises(ClinicalAuthorizationError):
            self.clinical.list_encounters(self.other, **self.actor)
        with self.assertRaises(ClinicalAuthorizationError):
            self.clinical.list_encounters(self.first, actor="ATTACKER-ONE",
                                          purpose="care")
        self.registry.suspend_patient(
            self.first, actor="CLINICIAN-ONE", purpose="care", expected_revision=1)
        with self.assertRaises(PatientRegistryDenied):
            self.clinical.list_encounters(self.first, **self.actor)
        with self.assertRaises(PatientRegistryDenied):
            self.clinical.schedule(
                self.first, "ENCOUNTER-SECOND", "outpatient", "2026-11-03",
                request_key="REQUEST-POSTSUSPEND-01", **self.actor)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_encounters").fetchone()[0], 1)

    def test_failed_host_event_rolls_back_domain_write_and_command_receipt(self):
        original = self.registry.append_event
        def fail(patient_id, kind, **details):
            if kind == "clinical_encounter_scheduled":
                raise RuntimeError("synthetic event failure")
            return original(patient_id, kind, **details)
        self.registry.append_event = fail
        try:
            with self.assertRaisesRegex(RuntimeError, "synthetic event failure"):
                self._schedule()
        finally:
            self.registry.append_event = original
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_encounters").fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_encounter_commands").fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM identity_domain_events WHERE patient_id=?",
            (self.first,)).fetchone()[0], 1)
        self.assertEqual(self._schedule()["status"], "scheduled")

    def test_restart_preserves_one_patient_identity_and_encounter_scope(self):
        previous = self._schedule()
        self.db.close()
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.registry = PatientRegistry(self.db, self.registry_policy)
        self.clinical = ClinicalEncounters(self.registry, self.clinical_policy)
        self.assertEqual(self.registry.create_patient(
            organization="HOSPITAL-ONE", actor="CLINICIAN-ONE",
            purpose="care", request_key="REGISTER-ONE")["patient_id"], self.first)
        self.assertEqual(self._schedule(), previous)
        self.assertEqual(len(self.clinical.list_encounters(self.first, **self.actor)), 1)
        with self.assertRaises(ClinicalConflict):
            self.clinical.schedule(
                self.first, "DIFFERENT-ENCOUNTER", "outpatient", "2026-11-03",
                request_key="REQUEST-SCHEDULE-01", **self.actor)


if __name__ == "__main__":
    unittest.main()
