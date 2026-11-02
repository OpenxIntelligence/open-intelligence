"""Actual first-party canonical patient/EHR/LIS → source-bound Composer tests.

Uses the same real SQLite registry, EHR notes, source ledger, LIS, pending
receiver and injected synthetic test policy from test_clinical_continuity.
No real patient, genuine identity proof, clinician sign-off or model call.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from open_intelligence.clinical_composer_context import AuthorizedClinicalComposer
from open_intelligence.composer import build_composer_context
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.store import InvalidInput

from test_clinical_continuity import (
    ClinicalContinuityIntegrationTests, ACTOR, CASE,
)


class AuthorizedClinicalComposerIntegrationTests(unittest.TestCase):
    # Reuse the established real service fixture without inheriting/re-running
    # its existing unrelated tests. No copied patient or mock source ledger.
    setUp = ClinicalContinuityIntegrationTests.setUp
    actor = ClinicalContinuityIntegrationTests.actor
    workflow = ClinicalContinuityIntegrationTests.workflow
    _source = ClinicalContinuityIntegrationTests._source

    def prepare(self):
        source, note_id = self.workflow()
        question_id = self.store.add_question(
            CASE, "Which original fictional findings require source review?")
        composed = AuthorizedClinicalComposer(self.view, self.store)
        return composed, question_id, source, note_id

    def test_authorized_context_contains_same_patient_ehr_lab_and_exact_sources(self):
        composed, question, source, note_id = self.prepare()
        before = len(self.store.state(CASE)["events"])
        result = composed.snapshot(
            self.patient_id, CASE, question, **self.actor())
        self.assertEqual(result["contract"], "oi.synthetic-authorized-clinical-composer/1")
        self.assertEqual(result["patient_id"], self.patient_id)
        self.assertEqual(result["case_id"], CASE)
        self.assertEqual(result["question_id"], question)
        self.assertEqual(result["clinical"]["contract"], "oi.clinical-continuity-review/1")
        self.assertEqual(result["clinical"]["patient_id"], self.patient_id)
        self.assertEqual(result["clinical"]["lab_evidence_candidates"][0]["source_version_id"], source)
        self.assertEqual(result["clinical"]["lab_evidence_candidates"][0]["clinical_assessment"],
                         "not_established")
        self.assertEqual(result["clinical"]["note_source_links"][0]["source_version_id"], source)
        self.assertEqual(result["composer"]["case_id"], CASE)
        self.assertEqual(result["composer"]["question_id"], question)
        self.assertEqual(len(result["composer"]["fingerprint"]), 64)
        self.assertIn(source, [a["source_version_id"]
                              for a in result["composer"]["source_anchors"]])
        self.assertEqual(result["authority"]["actor_policy"],
                         "synthetic_injected_authorizer_only")
        self.assertEqual(result["authority"]["clinical_review"], "not_performed")
        self.assertEqual(result["snapshot_consistency"], "not_a_distributed_atomic_snapshot")
        self.assertEqual(result["composer"]["tool_status"]["clinical_authorization"],
                         "not_verified")
        self.assertNotIn("Unverified fictional clinical note text", str(result))
        self.assertEqual(len(self.store.state(CASE)["events"]), before,
                         "Composer read must not persist or authorize an action")

    def test_wrong_case_and_other_patient_question_are_not_disclosed(self):
        composed, question, *_ = self.prepare()
        other = "CASE-CLIN-CONT-OTHER"
        foreign_question = self.store.add_question(
            other, "Unrelated fictional patient question")
        with self.assertRaises((PatientRegistryDenied, InvalidInput)):
            composed.snapshot(self.patient_id, other, foreign_question, **self.actor())
        with self.assertRaises(InvalidInput):
            composed.snapshot(self.patient_id, CASE, foreign_question, **self.actor())
        self.assertEqual(self.store.state(other)["sources"], [])

    def test_untrusted_actor_and_unsupported_purpose_denied(self):
        composed, question, *_ = self.prepare()
        with self.assertRaises(PatientRegistryDenied):
            composed.snapshot(self.patient_id, CASE, question,
                              actor="idp:untrusted", purpose="care")
        with self.assertRaises(PatientRegistryDenied):
            composed.snapshot(self.patient_id, CASE, question,
                              actor=ACTOR, purpose="research")

    def test_revoked_binding_denies_existing_source_context(self):
        composed, question, *_ = self.prepare()
        composed.snapshot(self.patient_id, CASE, question, **self.actor())
        self.bridge.revoke_case(
            patient_id=self.patient_id, case_id=CASE,
            actor=ACTOR, purpose="care",
            reason="Synthetic patient-to-case relationship was revoked.")
        with self.assertRaises(PatientRegistryDenied):
            composed.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_mid_read_revocation_does_not_disclose_context(self):
        composed, question, *_ = self.prepare()
        original = build_composer_context

        def revoke_after_context(store, case, qid):
            result = original(store, case, qid)
            self.bridge.revoke_case(
                patient_id=self.patient_id, case_id=CASE,
                actor=ACTOR, purpose="care",
                reason="The fictional consented relationship was revoked during preview.")
            return result

        with patch("open_intelligence.clinical_composer_context.build_composer_context",
                   side_effect=revoke_after_context):
            with self.assertRaises(PatientRegistryDenied):
                composed.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_changed_source_during_composer_preview_fails_closed(self):
        composed, question, source, _ = self.prepare()
        original = build_composer_context

        def correct_during_preview(store, case, qid):
            result = original(store, case, qid)
            self._source("LAB-CONT-001", "laboratory", "result", "indeterminate",
                         specimen="SPEC-CONT-001", amendment=1)
            return result

        with patch("open_intelligence.clinical_composer_context.build_composer_context",
                   side_effect=correct_during_preview):
            with self.assertRaisesRegex(ClinicalContinuityError, "changed|stale"):
                composed.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_unrelated_adapter_subject_conflict_denied_without_leaking_record(self):
        composed, question, *_ = self.prepare()
        # The canonical clinical continuity service must still reject later
        # source adapter identity inconsistency, even for an otherwise current
        # Composer fingerprint.
        from test_clinical_continuity import report, ORG
        self.store.import_adapter_report(
            CASE, report("LATE-SOURCE", "laboratory", "flag", "reported",
                         specimen="SPEC-CONT-001"),
            source_organization=ORG, source_system="SYNTHETIC-LIS",
            source_subject_ref="DIFFERENT-LOCAL-SUBJECT",
            receipt_id="RECEIPT-UNREVIEWED", adapter_id="TEST-ADAPTER",
            retrieved_at="2026-11-02T17:00:00Z")
        with self.assertRaises(PatientRegistryDenied):
            composed.snapshot(self.patient_id, CASE, question, **self.actor())


if __name__ == "__main__":
    unittest.main()
