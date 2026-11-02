"""Synthetic end-to-end canonical patient/EHR/LIS/outbox/review integration.

Real first-party implementations, fictional reports and test policy only.
No person matching, credential proof, medical signature, consent, or PHI.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.clinical_encounters import ClinicalEncounters
from open_intelligence.clinical_event_host import EventedClinicalHost
from open_intelligence.clinical_lab_bridge import (
    CanonicalLabBridge, LinkedLabCaseStore, consume_lab_review_event,
    install_lab_review_projection,
)
from open_intelligence.patient_registry import PatientRegistry, PatientRegistryDenied
from open_intelligence.platform_events import OutboxContractError, install
from open_intelligence.store import InvalidInput


ACTOR = "idp:fictional-clinician"
CASE = "CASE-RECONCILED-001"
OTHER_CASE = "CASE-RECONCILED-002"
ORG = "ORG-FICTIONAL-001"


def report(document, kind, finding, state, *, specimen=None, amendment=None):
    lines = [
        "OI-SYNTHETIC-REPORT/1", f"Patient: {CASE}",
        f"Document: {document}", f"Type: {kind}",
        "Event-Date: 2026-01-05", "Issued-At: 2026-01-06",
    ]
    if specimen:
        lines.append(f"Specimen: {specimen}")
    if amendment:
        lines.append(f"Amends: {document}@{amendment}")
    lines.append(f"Finding: {finding}|{state}|Fictional finding for regression only.")
    return ("\n".join(lines) + "\n").encode()


class PatientLisWorldModelIntegration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "integration.sqlite"
        self.store = LinkedLabCaseStore(self.path)
        self.addCleanup(lambda: self.store.close())
        self.store.add_case(CASE, "Fictional source case")
        self.store.add_case(OTHER_CASE, "Second fictional source case")
        self._start_services()
        self.patient_id = self.registry.create_patient(
            organization=ORG, actor=ACTOR, purpose="care",
            request_key="CREATE-SYNTHETIC-LAB-001")["patient_id"]
        self.bridge.bind_case(
            patient_id=self.patient_id, case_id=CASE,
            source_organization=ORG, source_system="FICTIONAL-LIS-A",
            source_subject_ref="LOCAL-CASE-IDENTITY-A",
            review_ref="EXPLICIT-REVIEW-001",
            actor=ACTOR, purpose="care")

    def _start_services(self):
        def allow(actor, subject, action, purpose):
            return actor == ACTOR and purpose == "care"
        self.registry = PatientRegistry(self.store.db, authorizer=allow)
        install(self.store.db)
        self.ehr = ClinicalEncounters(
            EventedClinicalHost(self.registry), authorizer=allow)
        self.bridge = CanonicalLabBridge(
            self.store, self.registry, authorizer=allow)

    def _source(self, *, document="ORDER-DOC-001", kind="clinical",
                finding="order", state="reported", specimen=None,
                amendment=None):
        return self.store.import_report(
            CASE, report(document, kind, finding, state,
                         specimen=specimen, amendment=amendment))["source_id"]

    def _command(self, name, *args, patient=None, case=CASE, actor=ACTOR):
        return self.bridge.command(patient or self.patient_id, case, name, *args,
                                   actor=actor, purpose="care")

    def _workflow(self):
        encounter = self.ehr.schedule(
            self.patient_id, "ENC-SYN-001", "outpatient", "2026-11-02",
            actor=ACTOR, purpose="care", request_key="ENC-REQUEST-001")
        order_source = self._source()
        self._command("request_lab_order", "ORDER-SYN-001", order_source,
                      "Fictional biomarker assay", "Demo requester")
        self._command("accession_specimen", "ORDER-SYN-001", "ACC-SYN-001",
                      "SPEC-SYN-001", "Demo accessioner")
        result_source = self._source(
            document="LAB-DOC-001", kind="laboratory", finding="result",
            state="negative", specimen="SPEC-SYN-001")
        self._command("record_quality_check", "ACC-SYN-001", "QC-SYN-001",
                      result_source, "passed", "Demo verifier")
        self._command("release_observation", "ACC-SYN-001", "REL-SYN-001",
                      result_source, "result", "Demo releaser")
        return encounter, result_source

    def _events(self):
        rows = self.store.db.execute(
            "SELECT envelope_json FROM platform_outbox ORDER BY seq").fetchall()
        return [json.loads(r[0]) for r in rows]

    def _receiver(self):
        receiver = sqlite3.connect(":memory:")
        receiver.row_factory = sqlite3.Row
        install(receiver)
        install_lab_review_projection(receiver)
        self.addCleanup(receiver.close)
        return receiver

    def test_real_ehr_lis_world_model_review_journey(self):
        encounter, source_id = self._workflow()
        self.assertEqual(encounter["status"], "scheduled")
        events = self._events()
        lab = [e for e in events if e["owner_domain"] == "lab"]
        self.assertEqual(len(lab), 4)
        self.assertEqual([e["aggregate"]["revision"] for e in lab], [1, 2, 3, 4])
        self.assertEqual(lab[-1]["event_type"], "lab.observation.released")
        self.assertEqual(lab[-1]["source_version_ref"], f"SRC-V-{source_id}")
        self.assertTrue(all(e["subject_binding_id"] == self.patient_id for e in lab))
        self.assertTrue(all(e["authorization_decision_ref"] is None for e in lab))
        self.assertNotIn("Fictional finding", json.dumps(lab))
        receiver = self._receiver()
        for event in lab:
            receiver.execute("BEGIN IMMEDIATE")
            with receiver:
                self.assertTrue(consume_lab_review_event(
                    receiver, self.bridge, event, patient_id=self.patient_id,
                    case_id=CASE, actor=ACTOR, purpose="care"))
        candidate = dict(receiver.execute(
            "SELECT * FROM lab_world_model_review_candidates").fetchone())
        self.assertEqual(candidate["patient_id"], self.patient_id)
        self.assertEqual(candidate["specimen_id"], "SPEC-SYN-001")
        self.assertEqual(candidate["source_version_id"], source_id)
        self.assertEqual(candidate["reported_state"], "negative")
        self.assertEqual(candidate["review_state"], "pending")
        receiver.execute("BEGIN IMMEDIATE")
        with receiver:
            self.assertFalse(consume_lab_review_event(
                receiver, self.bridge, lab[-1], patient_id=self.patient_id,
                case_id=CASE, actor=ACTOR, purpose="care"))
        self.assertEqual(receiver.execute(
            "SELECT COUNT(*) FROM lab_world_model_review_candidates").fetchone()[0], 1)

    def test_no_autolink_cross_patient_or_unverified_actor(self):
        other = self.registry.create_patient(
            organization=ORG, actor=ACTOR, purpose="care",
            request_key="CREATE-SYNTHETIC-LAB-002")["patient_id"]
        order_source = self._source()
        with self.assertRaises(PatientRegistryDenied):
            self._command("request_lab_order", "ORDER-SYN-001", order_source,
                          "Fictional biomarker assay", "Demo requester",
                          patient=other)
        with self.assertRaises(PatientRegistryDenied):
            self._command("request_lab_order", "ORDER-SYN-001", order_source,
                          "Fictional biomarker assay", "Demo requester",
                          actor="idp:untrusted")
        with self.assertRaises(InvalidInput):
            self.bridge.bind_case(
                patient_id=other, case_id=CASE, source_organization=ORG,
                source_system="FICTIONAL-LIS-A",
                source_subject_ref="LOCAL-CASE-IDENTITY-B",
                review_ref="EXPLICIT-REVIEW-002",
                actor=ACTOR, purpose="care")
        with self.assertRaises(sqlite3.IntegrityError):
            self.bridge.bind_case(
                patient_id=other, case_id=OTHER_CASE,
                source_organization=ORG, source_system="FICTIONAL-LIS-A",
                source_subject_ref="LOCAL-CASE-IDENTITY-A",
                review_ref="EXPLICIT-REVIEW-003",
                actor=ACTOR, purpose="care")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 0)

    def test_lab_missing_transport_rolls_back_operational_order(self):
        src = self._source()
        self.store.db.execute("DROP TABLE platform_outbox")
        with self.assertRaises(sqlite3.OperationalError):
            self._command("request_lab_order", "ORDER-SYN-001", src,
                          "Fictional biomarker assay", "Demo requester")
        self.assertEqual(self.bridge.case_state(
            self.patient_id, CASE, actor=ACTOR, purpose="care")["orders"], [])

    def test_revocation_blocks_delivery_and_original_case_cannot_rebind(self):
        _, _ = self._workflow()
        lab = [e for e in self._events() if e["owner_domain"] == "lab"]
        self.bridge.revoke_case(
            patient_id=self.patient_id, case_id=CASE, actor=ACTOR,
            purpose="care", reason="Fictional review link was withdrawn")
        with self.assertRaises(PatientRegistryDenied):
            self.bridge.case_state(
                self.patient_id, CASE, actor=ACTOR, purpose="care")
        receiver = self._receiver()
        receiver.execute("BEGIN IMMEDIATE")
        with receiver:
            with self.assertRaises(PatientRegistryDenied):
                consume_lab_review_event(
                    receiver, self.bridge, lab[0], patient_id=self.patient_id,
                    case_id=CASE, actor=ACTOR, purpose="care")
        with self.assertRaises(InvalidInput):
            self.bridge.bind_case(
                patient_id=self.patient_id, case_id=CASE,
                source_organization=ORG, source_system="FICTIONAL-LIS-A",
                source_subject_ref="LOCAL-CASE-IDENTITY-A",
                review_ref="EXPLICIT-REVIEW-001", actor=ACTOR, purpose="care")

    def test_source_amendment_prevents_stale_release_into_review(self):
        _, _ = self._workflow()
        lab = [e for e in self._events() if e["owner_domain"] == "lab"]
        self._source(
            document="LAB-DOC-001", kind="laboratory", finding="result",
            state="indeterminate", specimen="SPEC-SYN-001", amendment=1)
        receiver = self._receiver()
        for e in lab[:-1]:
            receiver.execute("BEGIN IMMEDIATE")
            with receiver:
                consume_lab_review_event(
                    receiver, self.bridge, e, patient_id=self.patient_id,
                    case_id=CASE, actor=ACTOR, purpose="care")
        receiver.execute("BEGIN IMMEDIATE")
        with receiver:
            with self.assertRaisesRegex(OutboxContractError, "provenance"):
                consume_lab_review_event(
                    receiver, self.bridge, lab[-1], patient_id=self.patient_id,
                    case_id=CASE, actor=ACTOR, purpose="care")
        self.assertEqual(receiver.execute(
            "SELECT COUNT(*) FROM lab_world_model_review_candidates").fetchone()[0], 0)

    def test_restart_preserves_binding_and_prevents_duplicate_outbox(self):
        _, _ = self._workflow()
        count = self.store.db.execute(
            "SELECT COUNT(*) FROM platform_outbox").fetchone()[0]
        self.store.close()
        self.store = LinkedLabCaseStore(self.path)
        self._start_services()
        state = self.bridge.case_state(
            self.patient_id, CASE, actor=ACTOR, purpose="care")
        self.assertEqual(len(state["releases"]), 1)
        self.assertTrue(self._command(
            "accession_specimen", "ORDER-SYN-001", "ACC-SYN-001",
            "SPEC-SYN-001", "Demo accessioner")["duplicate"])
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM platform_outbox").fetchone()[0], count)


if __name__ == "__main__":
    unittest.main()
