"""Cross-domain first-party clinical continuity tests; fictional fixture inputs."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.clinical_continuity import (
    ClinicalContinuityError, ClinicalContinuityView)
from open_intelligence.clinical_source_provenance import ClinicalSourceProvenance
from open_intelligence.clinical_lab_bridge import (
    CanonicalLabBridge, LinkedLabCaseStore,
    consume_lab_review_event, install_lab_review_projection)
from open_intelligence.platform_integration import CanonicalEHRHost
from open_intelligence.clinical_encounters import ClinicalEncounters
from open_intelligence.patient_registry import PatientRegistry, PatientRegistryDenied
from open_intelligence.platform_events import install

ACTOR = "idp:fictional-clinician"
CASE = "CASE-CLIN-CONT-001"
ORG = "ORG-FICTIONAL-CARE"


def report(document, kind, finding, state, *, specimen=None, amendment=None):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {CASE}",
             f"Document: {document}", f"Type: {kind}",
             "Event-Date: 2026-01-05", "Issued-At: 2026-01-06"]
    if specimen:
        lines.append(f"Specimen: {specimen}")
    if amendment:
        lines.append(f"Amends: {document}@{amendment}")
    lines.append(f"Finding: {finding}|{state}|Fictional reported item only.")
    return ("\n".join(lines) + "\n").encode()


class ClinicalContinuityIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = LinkedLabCaseStore(Path(tmp.name) / "clinical.sqlite")
        self.addCleanup(self.store.close)
        self.store.add_case(CASE, "Fictional source workspace")
        self.store.add_case("CASE-CLIN-CONT-OTHER", "Second source workspace")
        self.allow = lambda actor, pid, action, purpose: (
            actor == ACTOR and purpose == "care" and pid == getattr(self, "patient_id", pid))
        self.registry = PatientRegistry(self.store.db, authorizer=self.allow)
        install(self.store.db)
        self.ehr = ClinicalEncounters(CanonicalEHRHost(self.registry), self.allow)
        self.bridge = CanonicalLabBridge(self.store, self.registry, authorizer=self.allow)
        self.patient_id = self.registry.create_patient(
            organization=ORG, actor=ACTOR, purpose="care",
            request_key="CREATE-CONTINUITY-PATIENT")['patient_id']
        self.bridge.bind_case(
            patient_id=self.patient_id, case_id=CASE,
            source_organization=ORG, source_system="SYNTHETIC-LIS",
            source_subject_ref="LOCAL-SUBJECT-01", review_ref="REVIEWED-LINK-001",
            actor=ACTOR, purpose="care")

        def independently_verified_binding(patient, case, actor, purpose):
            try:
                self.bridge._allow(actor, patient, "case_read", purpose)
                return self.bridge._binding(patient, case) is not None
            except Exception:
                return False

        self.provenance = ClinicalSourceProvenance(
            self.registry, self.store, self.allow, independently_verified_binding)
        self.receiver = sqlite3.connect(":memory:")
        self.receiver.row_factory = sqlite3.Row
        self.addCleanup(self.receiver.close)
        install(self.receiver)
        install_lab_review_projection(self.receiver)
        self.view = ClinicalContinuityView(
            self.registry, self.bridge, self.provenance,
            self.receiver, authorizer=self.allow)

    def actor(self):
        return {"actor": ACTOR, "purpose": "care"}

    def _source(self, document, kind, finding, state, specimen=None, amendment=None):
        return self.store.import_report(
            CASE, report(document, kind, finding, state,
                         specimen=specimen, amendment=amendment))["source_id"]

    def workflow(self):
        self.ehr.schedule(self.patient_id, "ENCOUNTER-CONT-001", "outpatient",
                          "2026-11-02", request_key="ENC-REQUEST-001", **self.actor())
        encounter = self.ehr.schedule(
            self.patient_id, "ENCOUNTER-CONT-001", "outpatient",
            "2026-11-02", request_key="ENC-REQUEST-001", **self.actor())
        self.ehr.transition(self.patient_id, encounter["encounter_id"],
                            "in_progress", expected_revision=1,
                            request_key="ENC-START-001", **self.actor())
        order_source = self._source("ORDER-CONT-001", "clinical", "order", "reported")
        self.bridge.command(self.patient_id, CASE, "request_lab_order",
                            "ORDER-CONT-001", order_source,
                            "Fictional assay", "Test requester", **self.actor())
        self.bridge.command(self.patient_id, CASE, "accession_specimen",
                            "ORDER-CONT-001", "ACC-CONT-001", "SPEC-CONT-001",
                            "Test accessioner", **self.actor())
        src = self._source("LAB-CONT-001", "laboratory", "result", "negative",
                           specimen="SPEC-CONT-001")
        self.bridge.command(self.patient_id, CASE, "record_quality_check",
                            "ACC-CONT-001", "QC-CONT-001", src,
                            "passed", "Test checker", **self.actor())
        self.bridge.command(self.patient_id, CASE, "release_observation",
                            "ACC-CONT-001", "RELEASE-CONT-001", src,
                            "result", "Test releaser", **self.actor())
        self.ehr.write_note(self.patient_id, encounter["encounter_id"],
                            "NOTE-CONT-001", "Unverified fictional clinical note text",
                            expected_version=0, request_key="NOTE-CONT-WRITE", **self.actor())
        note_version = self.ehr.note_history(
            self.patient_id, encounter["encounter_id"],
            "NOTE-CONT-001", **self.actor())[0]["id"]
        self.provenance.attach(self.patient_id, CASE, note_version, src, 8,
                               **self.actor())
        events = [json.loads(r[0]) for r in self.store.db.execute(
            "SELECT envelope_json FROM platform_outbox ORDER BY seq")]
        lab_events = [e for e in events if e["owner_domain"] == "lab"]
        self.assertEqual(len(lab_events), 4)
        for ev in lab_events:
            self.receiver.execute("BEGIN IMMEDIATE")
            with self.receiver:
                self.assertTrue(consume_lab_review_event(
                    self.receiver, self.bridge, ev,
                    patient_id=self.patient_id, case_id=CASE, **self.actor()))
        return src, note_version

    def snapshot(self, **overrides):
        options = {"actor": ACTOR, "purpose": "care"}
        options.update(overrides)
        return self.view.snapshot(self.patient_id, CASE, **options)

    def test_unified_read_shows_note_and_lab_but_no_clinical_verdict(self):
        src, note_id = self.workflow()
        result = self.snapshot()
        self.assertEqual(result["contract"], "oi.clinical-continuity-review/1")
        self.assertEqual(result["patient_id"], self.patient_id)
        self.assertEqual(len(result["note_source_links"]), 1)
        self.assertEqual(result["note_source_links"][0]["source_version_id"], src)
        self.assertEqual(len(result["lab_evidence_candidates"]), 1)
        lab = result["lab_evidence_candidates"][0]
        self.assertEqual(lab["current_provenance_state"],
                         "current_source_pending_clinician_review")
        self.assertEqual(lab["source_version_id"], src)
        self.assertEqual(lab["clinical_assessment"], "not_established")
        self.assertEqual(result["patient_world_model_clinical_belief"], "not_generated")
        self.assertEqual(result["note_versions_requiring_source_review"] if "note_versions_requiring_source_review" in result else [], [])
        self.assertNotIn("Unverified fictional clinical note text", str(result))
        self.assertEqual(len(result["review_required"]), 1)

    def test_amendment_stales_old_lab_and_note_without_rewriting_history(self):
        src, _ = self.workflow()
        self._source("LAB-CONT-001", "laboratory", "result", "indeterminate",
                     specimen="SPEC-CONT-001", amendment=1)
        snapshot = self.snapshot()
        lab = snapshot["lab_evidence_candidates"][0]
        self.assertEqual(lab["source_version_id"], src)
        self.assertEqual(lab["current_provenance_state"],
                         "source_superseded_review_required")
        self.assertTrue(any(x["kind"] == "clinical_note" for x in snapshot["review_required"]))
        self.assertEqual(len(snapshot["review_required"]), 2)
        self.assertEqual(self.receiver.execute(
            "SELECT review_state FROM lab_world_model_review_candidates").fetchone()[0],
            "pending")  # historical, not automatically approved or erased

    def test_new_failed_qc_flags_old_release_as_needing_review(self):
        self.workflow()
        self.bridge.command(self.patient_id, CASE, "record_quality_check",
                            "ACC-CONT-001", "QC-CONT-002",
                            self.receiver.execute(
                                "SELECT source_version_id FROM lab_world_model_review_candidates"
                            ).fetchone()[0],
                            "failed", "Test checker", **self.actor())
        snapshot = self.snapshot()
        self.assertEqual(snapshot["lab_evidence_candidates"][0]["current_provenance_state"],
                         "quality_changed_review_required")

    def test_revoked_case_binding_denies_both_domains(self):
        self.workflow()
        self.bridge.revoke_case(patient_id=self.patient_id, case_id=CASE,
                                actor=ACTOR, purpose="care",
                                reason="Patient cancelled synthetic association")
        with self.assertRaises(PatientRegistryDenied):
            self.snapshot()

    def test_other_actor_and_purpose_denied_without_data(self):
        self.workflow()
        with self.assertRaises(PatientRegistryDenied):
            self.snapshot(actor="idp:untrusted")
        with self.assertRaises(PatientRegistryDenied):
            self.snapshot(purpose="research")

    def test_forged_receiver_candidate_fails_closed(self):
        self.workflow()
        self.receiver.execute(
            "UPDATE lab_world_model_review_candidates SET specimen_id='SPEC-FORGED'")
        self.receiver.commit()
        with self.assertRaises(ClinicalContinuityError):
            self.snapshot()

    def test_missing_event_receipt_fails_closed(self):
        self.workflow()
        self.store.db.execute("DELETE FROM platform_outbox WHERE owner_domain='lab'")
        self.store.db.commit()
        with self.assertRaises(ClinicalContinuityError):
            self.snapshot()

    def test_outbox_payload_change_rejected_even_if_identifiers_look_plausible(self):
        self.workflow()
        row = self.store.db.execute(
            "SELECT event_id,envelope_json FROM platform_outbox "
            "WHERE event_type='lab.observation.released'").fetchone()
        corrupted = json.loads(row["envelope_json"])
        corrupted["source_version_ref"] = "SRC-V-888888"
        self.store.db.execute(
            "UPDATE platform_outbox SET envelope_json=? WHERE event_id=?",
            (json.dumps(corrupted, sort_keys=True), row["event_id"]))
        self.store.db.commit()
        with self.assertRaises(ClinicalContinuityError):
            self.snapshot()

    def test_original_release_receipt_corruption_is_rejected(self):
        self.workflow()
        r = self.store.db.execute(
            "SELECT id FROM events WHERE kind='clinical_lab_observation_released'").fetchone()
        self.store.db.execute(
            "UPDATE events SET details=? WHERE id=?",
            ('{"release_id":999999,"qc_id":999999,"assertion_id":999999}', r[0]))
        self.store.db.commit()
        with self.assertRaises(ClinicalContinuityError):
            self.snapshot()

    def test_amended_lab_releases_remain_distinct_and_only_latest_is_current(self):
        src, _ = self.workflow()
        amended = self._source("LAB-CONT-001", "laboratory", "result",
                               "indeterminate", specimen="SPEC-CONT-001", amendment=1)
        self.bridge.command(self.patient_id, CASE, "record_quality_check",
                            "ACC-CONT-001", "QC-CONT-002", amended,
                            "passed", "Test checker", **self.actor())
        self.bridge.command(self.patient_id, CASE, "release_observation",
                            "ACC-CONT-001", "RELEASE-CONT-002", amended,
                            "result", "Test releaser", **self.actor())
        new_lab_events = [json.loads(r[0]) for r in self.store.db.execute(
            "SELECT envelope_json FROM platform_outbox "
            "WHERE event_type IN ('lab.qc.recorded','lab.observation.released') ORDER BY seq")]
        self.assertEqual(len(new_lab_events), 4)
        for event in new_lab_events[-2:]:
            self.receiver.execute("BEGIN IMMEDIATE")
            with self.receiver:
                self.assertTrue(consume_lab_review_event(
                    self.receiver, self.bridge, event,
                    patient_id=self.patient_id, case_id=CASE, **self.actor()))
        result = self.snapshot()
        lab = result["lab_evidence_candidates"]
        self.assertEqual(len(lab), 2)
        by_source = {r["source_version_id"]: r for r in lab}
        self.assertEqual(by_source[src]["current_provenance_state"],
                         "source_superseded_review_required")
        self.assertEqual(by_source[amended]["current_provenance_state"],
                         "current_source_pending_clinician_review")
        self.assertEqual(result["note_source_links"][0]["source_version_id"], src)
        self.assertEqual(result["patient_world_model_clinical_belief"], "not_generated")

    def test_revocation_between_source_and_receiver_reads_fails_closed(self):
        self.workflow()
        original = self.provenance.context_snapshot

        def revoked_during_read(*args, **kwargs):
            output = original(*args, **kwargs)
            self.bridge.revoke_case(
                patient_id=self.patient_id, case_id=CASE,
                actor=ACTOR, purpose="care",
                reason="Fictional owner revoked while evidence was being read")
            return output

        self.provenance.context_snapshot = revoked_during_read
        with self.assertRaises(PatientRegistryDenied):
            self.snapshot()

    def test_view_without_independent_authorizer_denies_even_after_binding(self):
        self.workflow()
        untrusted = ClinicalContinuityView(
            self.registry, self.bridge, self.provenance, self.receiver)
        with self.assertRaises(PatientRegistryDenied):
            untrusted.snapshot(self.patient_id, CASE, **self.actor())

    def test_adapter_identity_conflict_after_review_blocks_existing_patient(self):
        self.workflow()
        self.store.import_adapter_report(
            CASE, report("LATE-ADAPTER-REPORT", "laboratory", "flag", "reported",
                         specimen="SPEC-CONT-001"),
            source_organization=ORG, source_system="SYNTHETIC-LIS",
            source_subject_ref="UNREVIEWED-SUBJECT-REPLACEMENT",
            receipt_id="REC-UNREVIEWED", adapter_id="ADAPTER-TEST",
            retrieved_at="2026-11-02T17:00:00Z")
        # The source adapter's identity assignment must not override the
        # independently reviewed canonical patient-to-case association.
        with self.assertRaises(PatientRegistryDenied):
            self.snapshot()

    def test_preexisting_adapter_identity_conflict_prevents_new_case_binding(self):
        other_case = "CASE-CLIN-CONT-OTHER"
        other = self.patient_id
        # Existing adapter already associated this source system with a
        # different local identity for the second source workspace.
        self.store.import_adapter_report(
            other_case, report("FOREIGN-ADAPTER-REPORT", "clinical", "flag", "reported")
            .replace(f"Patient: {CASE}".encode(), f"Patient: {other_case}".encode()),
            source_organization=ORG, source_system="SYNTHETIC-LIS",
            source_subject_ref="UNREVIEWED-SUBJECT-002",
            receipt_id="REC-OTHER", adapter_id="ADAPTER-TEST",
            retrieved_at="2026-11-02T17:00:00Z")
        with self.assertRaisesRegex(Exception, "identity|Identity|mismatch|conflict"):
            self.bridge.bind_case(
                patient_id=other, case_id=other_case,
                source_organization=ORG, source_system="SYNTHETIC-LIS",
                source_subject_ref="DIFFERENT-REVIEWED-SUBJECT",
                review_ref="REVIEW-OTHER-001", actor=ACTOR, purpose="care")

    def test_empty_case_contains_no_auto_assessed_lab_or_notes(self):
        view = self.snapshot()
        self.assertEqual(view["lab_evidence_candidates"], [])
        self.assertEqual(view["note_source_links"], [])
        self.assertEqual(view["review_required"], [])


if __name__ == "__main__":
    unittest.main()
