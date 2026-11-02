"""Actual synthetic clinical+knowledge+numeric+PWM composition regressions.

Reuses original test fixtures from PR #149 and original PWM code from #147.
No clinical claims, public datasets, network retrieval, or external model call.
"""
import unittest
from unittest.mock import patch

from open_intelligence.authorized_world_model_review import AuthorizedWorldModelReview
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.world_model import synthetic_world_model
from test_clinical_continuity import CASE
from test_patient_research_run_review import numeric
from test_unified_clinical_review import UnifiedClinicalReviewIntegration as Fixture


class AuthorizedWorldModelReviewTests(unittest.TestCase):
    setUp = Fixture.setUp
    actor = Fixture.actor
    workflow = Fixture.workflow
    _source = Fixture._source
    prepare = Fixture.prepare
    setup_bundle = Fixture.setup_bundle

    def bundle_read(self, **kwargs):
        return self.bridge.preview(
            kwargs.get("patient_id", self.patient_id),
            kwargs.get("case_id", CASE),
            kwargs.get("question_id", self.question),
            kwargs.get("run_id", self.run["run_id"]),
            actor=kwargs.get("actor", self.actor()["actor"]),
            purpose=kwargs.get("purpose", "care"),
            selected_quotes=kwargs.get("selected_quotes", [{
                "assertion_id": self.assertion_id,
                "knowledge_id": "KNOW-SYN-001",
                "quote": "claims no therapeutic outcomes",
            }]),
        )

    def test_one_authorized_context_exposes_current_pwm_evidence_and_numeric_receipt(self):
        self.setup_bundle()
        self.bridge = AuthorizedWorldModelReview(self.bundle)
        events = self.store.state(CASE)["events"]
        result = self.bundle_read()
        self.assertEqual(result["contract"], "oi.synthetic-authorized-world-model-review/1")
        self.assertEqual(result["patient_id"], self.patient_id)
        pwm = result["patient_world_model"]
        unified = result["unified_review"]
        self.assertEqual(pwm["case_id"], CASE)
        self.assertEqual(pwm["clinical_interpretation"], "not_generated")
        self.assertEqual(pwm["authority"], "source_report_only_unreviewed")
        self.assertEqual(pwm["summary"]["current_observations"],
                         len(self.store.state(CASE)["assertions"]))
        self.assertIn(self.assertion_id,
                      {x["assertion_id"] for x in pwm["observations"]})
        self.assertEqual(unified["evidence_review"]["quoted_comparisons"][0]
                         ["external_reference"]["exact_quote"],
                         "claims no therapeutic outcomes")
        self.assertEqual(unified["numeric_receipt"]["status"],
                         "current_numeric_receipt_pending_human_review")
        self.assertFalse(result["clinical_approval"])
        self.assertFalse(result["model_executed_by_adapter"])
        self.assertEqual(result["human_review_state"], "pending")
        self.assertEqual(self.store.state(CASE)["events"], events)

    def test_amendment_marks_historical_numeric_without_erasing_source_history(self):
        self.setup_bundle()
        self.bridge = AuthorizedWorldModelReview(self.bundle)
        previous = self.bundle_read()
        self.store.import_report(
            CASE, numeric("NUM-LAB-2", "2026-03-01", "8.1", amendment=1))
        changed = self.bundle_read()
        self.assertEqual(changed["unified_review"]["numeric_receipt"]["status"],
                         "historical_numeric_receipt_reassessment_required")
        self.assertGreater(changed["patient_world_model"]["summary"]
                           ["superseded_sources"],
                           previous["patient_world_model"]["summary"]["superseded_sources"])
        self.assertFalse(changed["clinical_approval"])
        self.assertTrue(changed["patient_world_model"]["history"])

    def test_wrong_actor_purpose_and_patient_fail_closed(self):
        self.setup_bundle()
        self.bridge = AuthorizedWorldModelReview(self.bundle)
        for kw in ({"actor": "idp:untrusted"}, {"purpose": "research"},
                   {"case_id": "CASE-OTHER-PATIENT"}):
            with self.subTest(kw=kw):
                with self.assertRaises((ClinicalContinuityError, PatientRegistryDenied)):
                    self.bundle_read(**kw)

    def test_external_rights_withdrawal_does_not_expose_world_model(self):
        self.setup_bundle()
        self.bridge = AuthorizedWorldModelReview(self.bundle)
        self.sources[0]["rights_state"] = "revoked"
        with self.assertRaises(KnowledgeContextError):
            self.bundle_read()

    def test_corrupted_world_model_source_hash_is_rejected(self):
        self.setup_bundle()
        self.bridge = AuthorizedWorldModelReview(self.bundle)
        def tampered(*args):
            state = synthetic_world_model(*args)
            state["observations"][0]["source_sha256"] = "0" * 64
            return state
        with patch(
            "open_intelligence.authorized_world_model_review.synthetic_world_model",
            side_effect=tampered,
        ):
            with self.assertRaisesRegex(ClinicalContinuityError, "diverge"):
                self.bundle_read()

    def test_source_amendment_during_bundle_assembly_fails_closed(self):
        self.setup_bundle()
        self.bridge = AuthorizedWorldModelReview(self.bundle)
        original = self.bridge.unified.preview
        def amend_after_review(*args, **kwargs):
            output = original(*args, **kwargs)
            self.store.import_report(
                CASE, numeric("NUM-LAB-2", "2026-03-01", "8.1", amendment=1))
            return output
        with patch.object(self.bridge.unified, "preview",
                          side_effect=amend_after_review):
            with self.assertRaisesRegex(ClinicalContinuityError, "changed"):
                self.bundle_read()


if __name__ == "__main__":
    unittest.main()
