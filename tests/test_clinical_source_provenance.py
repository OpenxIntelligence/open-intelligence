"""First-party note/source provenance integration, with synthetic patient binding.

Real PatientRegistry, ClinicalEncounters and CaseStore run over the same SQLite
host. No real patient identity, PHI, signing, model analysis or clinical use.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.store import CaseStore
from open_intelligence.patient_registry import PatientRegistry
from open_intelligence.clinical_encounters import ClinicalEncounters
from open_intelligence.clinical_source_provenance import (
    ClinicalSourceProvenance, ClinicalSourceLinkDenied, ClinicalSourceLinkError,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class ClinicalSourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "patient-provenance.sqlite"
        self.store = CaseStore(self.path)
        self.addCleanup(self.store.close)
        self.db = self.store.db
        self.store.add_case("CASE-ALPHA", "Fictional oncology patient")
        self.store.add_case("CASE-BETA", "Other fictional patient")
        self.identity_policy = lambda actor, subject, action, purpose: (
            actor == "CLINICIAN-ONE" and purpose == "care")
        self.registry = PatientRegistry(self.db, self.identity_policy)
        self.patient = self.registry.create_patient(
            organization="HOSPITAL-ONE", actor="CLINICIAN-ONE",
            purpose="care", request_key="REGISTER-ONE")["patient_id"]
        self.other = self.registry.create_patient(
            organization="HOSPITAL-ONE", actor="CLINICIAN-ONE",
            purpose="care", request_key="REGISTER-TWO")["patient_id"]
        self.bindings = {
            self.patient: "CASE-ALPHA",
            self.other: "CASE-BETA",
        }
        self.binding_policy = lambda patient, case, actor, purpose: (
            actor == "CLINICIAN-ONE" and purpose == "care"
            and self.bindings.get(patient) == case)
        self.clinical_policy = lambda actor, patient, action, purpose: (
            actor == "CLINICIAN-ONE" and patient == self.patient
            and purpose == "care" and action in {
                "encounter.schedule", "encounter.transition", "encounter.read",
                "note.write", "note.read", "note.attest",
                "note.provenance_link", "note.provenance_read",
            })
        self.clinical = ClinicalEncounters(self.registry, self.clinical_policy)
        self.provenance = ClinicalSourceProvenance(
            self.registry, self.store, self.clinical_policy, self.binding_policy)
        self.actor = {"actor": "CLINICIAN-ONE", "purpose": "care"}
        self.source = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-original.txt").read_bytes()
        )["source_id"]
        self.foreign_source = self.store.import_report(
            "CASE-BETA", (FIXTURES / "beta-pathology.txt").read_bytes()
        )["source_id"]
        encounter = self.clinical.schedule(
            self.patient, "ENCOUNTER-ONE", "outpatient", "2026-11-02",
            request_key="REQUEST-ENCOUNTER-01", **self.actor)
        self.encounter_id = encounter["encounter_id"]
        self.clinical.transition(
            self.patient, self.encounter_id, "in_progress",
            expected_revision=1, request_key="REQUEST-START-01", **self.actor)
        self.note = self.clinical.write_note(
            self.patient, self.encounter_id, "NOTE-ONE",
            "Original fictional clinical note; the marker result remains unknown.",
            expected_version=0, request_key="REQUEST-DRAFT-01", **self.actor)
        self.assertEqual(self.note["version"], 1)
        self.note_version_id = self.clinical.note_history(
            self.patient, self.encounter_id, "NOTE-ONE", **self.actor)[0]["id"]
        self.source_line = 9

    def attach(self, **kwargs):
        data = {
            "patient_id": self.patient, "case_id": "CASE-ALPHA",
            "note_version_id": self.note_version_id,
            "source_version_id": self.source, "source_line": self.source_line,
            **self.actor,
        }
        data.update(kwargs)
        return self.provenance.attach(**data)

    def read(self, **kwargs):
        data = {
            "patient_id": self.patient, "case_id": "CASE-ALPHA",
            "note_version_id": self.note_version_id, **self.actor,
        }
        data.update(kwargs)
        return self.provenance.note_sources(**data)

    def test_draft_source_link_survives_attestation_and_amendment_without_rewriting(self):
        receipt = self.attach()
        self.assertFalse(receipt["duplicate"])
        self.assertEqual(self.attach(), {"link_id": receipt["link_id"], "duplicate": True})
        linked = self.read()
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["source_version_id"], self.source)
        self.assertEqual(linked[0]["document_id"], "PATH-ALPHA")
        self.assertEqual(linked[0]["document_version"], 1)
        self.assertEqual(linked[0]["specimen_id"], "BIOPSY-ALPHA")
        self.assertEqual(linked[0]["original_statement"], "Marker A was not tested in this specimen.")
        self.assertEqual(linked[0]["provenance_state"], "current_source_unreviewed")
        self.assertEqual(linked[0]["clinical_review_state"], "not_established_by_source_link")

        signed = self.clinical.attest_note(
            self.patient, self.encounter_id, "NOTE-ONE",
            expected_version=1, request_key="REQUEST-ATTEST-01", **self.actor)
        self.assertEqual(signed["status"], "attested")
        history_before = self.clinical.note_history(
            self.patient, self.encounter_id, "NOTE-ONE", **self.actor)
        self.assertEqual(len(history_before), 2)
        self.assertEqual(history_before[0]["body"], history_before[1]["body"])
        self.assertEqual(len(self.read()), 1)  # historical draft reference remains

        with self.assertRaisesRegex(ClinicalSourceLinkError, "Only a draft"):
            self.attach(note_version_id=history_before[1]["id"])

        self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-amended.txt").read_bytes())
        amended = self.read()
        self.assertEqual(len(amended), 1)
        self.assertEqual(amended[0]["provenance_state"],
                         "source_superseded_review_required")
        self.assertEqual(amended[0]["original_statement"],
                         "Marker A was not tested in this specimen.")
        self.assertEqual(self.clinical.note_history(
            self.patient, self.encounter_id, "NOTE-ONE", **self.actor), history_before)
        with self.assertRaisesRegex(ClinicalSourceLinkError, "superseded"):
            self.attach()

    def test_wrong_case_wrong_note_wrong_source_and_unverified_actor_denied(self):
        with self.assertRaises(ClinicalSourceLinkDenied):
            self.attach(case_id="CASE-BETA")
        with self.assertRaises(ClinicalSourceLinkDenied):
            self.read(case_id="CASE-BETA")
        with self.assertRaises(ClinicalSourceLinkDenied):
            self.attach(actor="UNTRUSTED-USER")
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach(source_version_id=self.foreign_source)
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach(source_line=1)
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach(note_version_id=99999)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_note_source_refs").fetchone()[0], 0)

    def test_revoked_binding_and_patient_suspension_fail_closed(self):
        self.attach()
        del self.bindings[self.patient]
        with self.assertRaises(ClinicalSourceLinkDenied):
            self.read()
        with self.assertRaises(ClinicalSourceLinkDenied):
            self.attach()
        self.bindings[self.patient] = "CASE-ALPHA"
        self.registry.suspend_patient(
            self.patient, actor="CLINICIAN-ONE", purpose="care", expected_revision=1)
        with self.assertRaises(PermissionError):
            self.read()
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_note_source_refs").fetchone()[0], 1)

    def test_event_failure_rolls_back_link_and_audit_and_can_retry(self):
        original = self.registry.append_event

        def reject_event(patient_id, kind, **details):
            if kind == "clinical_note_source_linked":
                raise RuntimeError("synthetic audit transaction failure")
            return original(patient_id, kind, **details)
        self.registry.append_event = reject_event
        try:
            with self.assertRaisesRegex(RuntimeError, "audit transaction failure"):
                self.attach()
        finally:
            self.registry.append_event = original
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clinical_note_source_refs").fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM identity_domain_events WHERE event_type='clinical_note_source_linked'").fetchone()[0], 0)
        self.assertFalse(self.attach()["duplicate"])
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM identity_domain_events WHERE event_type='clinical_note_source_linked'").fetchone()[0], 1)

    def test_restart_reuses_original_sources_and_reference_without_copying(self):
        before = self.attach()
        self.store.close()
        self.store = CaseStore(self.path)
        self.db = self.store.db
        self.registry = PatientRegistry(self.db, self.identity_policy)
        self.clinical = ClinicalEncounters(self.registry, self.clinical_policy)
        self.provenance = ClinicalSourceProvenance(
            self.registry, self.store, self.clinical_policy, self.binding_policy)
        self.assertEqual(self.read()[0]["link_id"], before["link_id"])
        self.assertEqual(self.attach()["duplicate"], True)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM source_versions").fetchone()[0], 2)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM identity_patients").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
