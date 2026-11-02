"""Full synthetic patient/EHR/LIS/knowledge/Composer/numeric review consistency.

The fixture reuses both upstream owner implementations (PR #143 and #144).
All assertions, measurements and research quotations are invented; no
external retrieval, patient data, medical inference or clinical signing.
"""
import unittest
from unittest.mock import patch

from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.unified_clinical_review import UnifiedClinicalReview
from test_clinical_continuity import CASE
from test_patient_research_run_review import (
    PatientResearchRunReviewIntegration as Fixture, numeric,
)


class UnifiedClinicalReviewIntegration(unittest.TestCase):
    setUp = Fixture.setUp
    actor = Fixture.actor
    workflow = Fixture.workflow
    _source = Fixture._source
    prepare = Fixture.prepare

    def setup_bundle(self):
        self.prepare()
        self.assertions = self.store.state(CASE)["assertions"]
        self.assertTrue(self.assertions)
        self.assertion_id = self.assertions[0]["id"]
        self.proposals = [{
            "assertion_id": self.assertion_id,
            "knowledge_id": "KNOW-SYN-001",
            "relation": "contradicts",
            "applicability": "limited",
            "reviewer_note": "An invented relationship awaiting professional review.",
            "proposed_by": "FIXTURE-RESEARCHER",
        }]

        def provider(patient, case, question, actor, purpose):
            return {
                "sources": [dict(x) for x in self.sources],
                "proposals": [dict(x) for x in self.proposals],
            }

        # The original authorized knowledge owner is used by both readers.
        self.knowledge.source_provider = provider
        self.bundle = UnifiedClinicalReview(self.knowledge, self.runs)

    def read(self, **kw):
        return self.bundle.preview(
            kw.get("patient_id", self.patient_id),
            kw.get("case_id", CASE),
            kw.get("question_id", self.question),
            kw.get("run_id", self.run["run_id"]),
            actor=kw.get("actor", self.actor()["actor"]),
            purpose=kw.get("purpose", "care"),
            selected_quotes=kw.get("selected_quotes", [{
                "assertion_id": self.assertion_id,
                "knowledge_id": "KNOW-SYN-001",
                "quote": "claims no therapeutic outcomes",
            }]),
        )

    def test_one_preview_carries_both_source_quoted_evidence_and_numeric_receipt(self):
        self.setup_bundle()
        initial_events = self.store.state(CASE)["events"]
        result = self.read()
        self.assertEqual(result["contract"], "oi.synthetic-unified-clinical-review/1")
        self.assertEqual(result["patient_id"], self.patient_id)
        self.assertEqual(result["human_review_state"], "pending")
        self.assertFalse(result["clinical_approval"])
        self.assertFalse(result["external_effect_authorized"])
        self.assertFalse(result["publisher_rights_independently_verified"])
        self.assertFalse(result["model_executed_by_bundle"])
        evidence = result["evidence_review"]
        numeric = result["numeric_receipt"]
        self.assertEqual(evidence["quoted_comparisons"][0]["external_reference"]["exact_quote"],
                         "claims no therapeutic outcomes")
        self.assertEqual(evidence["quoted_comparisons"][0]["patient_reference"]["assertion_id"],
                         self.assertion_id)
        self.assertEqual(evidence["human_review_state"], "pending")
        self.assertEqual(numeric["status"],
                         "current_numeric_receipt_pending_human_review")
        self.assertEqual(numeric["run"]["result"]["result"]["delta"], "-0.4")
        self.assertEqual({p["source_version_id"] for p in
                          numeric["original_source_provenance"]},
                         {self.first, self.second})
        self.assertEqual(result["composer_context_fingerprint"],
                         evidence["composer_context_fingerprint"])
        self.assertEqual(initial_events, self.store.state(CASE)["events"])

    def test_numeric_amendment_preserves_historical_receipt_without_staling_unrelated_quote(self):
        self.setup_bundle()
        previous = self.read()
        self.store.import_report(
            CASE, numeric("NUM-LAB-2", "2026-03-01", "8.1", amendment=1))
        result = self.read()
        self.assertNotEqual(result["composer_context_fingerprint"],
                            previous["composer_context_fingerprint"])
        self.assertEqual(result["numeric_receipt"]["status"],
                         "historical_numeric_receipt_reassessment_required")
        self.assertEqual(result["numeric_receipt"]["run"]["result"]["result"]["delta"],
                         "-0.4")
        self.assertEqual(result["evidence_review"]["quoted_comparisons"][0]
                         ["patient_reference"]["assertion_id"], self.assertion_id)
        self.assertEqual(result["human_review_state"], "pending")
        self.assertFalse(result["clinical_approval"])

    def test_withheld_or_fabricated_publication_text_fails_closed(self):
        self.setup_bundle()
        forged = [{
            "assertion_id": self.assertion_id,
            "knowledge_id": "KNOW-SYN-001",
            "quote": "a cure is guaranteed",
        }]
        with self.assertRaises(KnowledgeContextError):
            self.read(selected_quotes=forged)
        self.sources[0]["rights_state"] = "revoked"
        with self.assertRaises(KnowledgeContextError):
            self.read()

    def test_unapproved_actor_purpose_or_patient_is_denied(self):
        self.setup_bundle()
        attempts = [
            {"actor": "idp:untrusted"},
            {"purpose": "research"},
            {"case_id": "CASE-CLIN-CONT-OTHER"},
        ]
        for kw in attempts:
            with self.subTest(kw=kw), self.assertRaises(
                    (ClinicalContinuityError, PatientRegistryDenied)):
                self.read(**kw)

    def test_rights_change_between_evidence_and_numeric_reads_aborts_bundle(self):
        self.setup_bundle()
        original = self.bundle.evidence.preview

        def mutate_after_quote(*args, **kwargs):
            output = original(*args, **kwargs)
            self.sources[0]["evidence_text"] += " Additional invented sentence."
            return output

        with patch.object(self.bundle.evidence, "preview",
                          side_effect=mutate_after_quote):
            with self.assertRaisesRegex(ClinicalContinuityError, "changed"):
                self.read()

    def test_run_receipt_change_after_numeric_read_aborts_bundle(self):
        self.setup_bundle()
        original = self.bundle.numeric.snapshot

        def mutate_after_numeric(*args, **kwargs):
            output = original(*args, **kwargs)
            with self.store.db:
                self.store.db.execute(
                    "UPDATE composer_tool_runs SET state='cancelled' WHERE id=?",
                    (self.run["run_id"],))
            return output

        with patch.object(self.bundle.numeric, "snapshot",
                          side_effect=mutate_after_numeric):
            with self.assertRaisesRegex(ClinicalContinuityError, "receipt changed"):
                self.read()


if __name__ == "__main__":
    unittest.main()
