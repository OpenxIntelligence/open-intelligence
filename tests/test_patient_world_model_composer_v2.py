"""First-party synthetic Patient World Model + Composer v2 research compatibility.

This cross-branch test uses existing patient/EHR/LIS, source-ledger, knowledge,
quoted evidence, saved v2 broker hypothesis, and durable numeric run owners.
No clinical interpretation, real medical records, network, or external model.
"""
import unittest

from open_intelligence.authorized_world_model_review import AuthorizedWorldModelReview
from open_intelligence.composer import CONTEXT_VERSION
from open_intelligence.investigation import validate_output
from test_clinical_continuity import CASE
from test_composer_broker_context import link, payload
from test_patient_research_run_review import numeric
from test_authorized_world_model_review import AuthorizedWorldModelReviewTests as Fixture


class PatientWorldModelComposerV2Integration(unittest.TestCase):
    setUp = Fixture.setUp
    actor = Fixture.actor
    workflow = Fixture.workflow
    _source = Fixture._source
    prepare = Fixture.prepare
    setup_bundle = Fixture.setup_bundle

    def configure_v2(self):
        self.setup_bundle()
        self.world = AuthorizedWorldModelReview(self.bundle)
        self.assertEqual(CONTEXT_VERSION, "composer-context-v2")
        old_run_id = self.run["run_id"]
        rights_id, broker_id = link(
            self.store, self.question, key="PWM-BROKER-V2-ONE",
            case=CASE, citation_title="Original fictional counterevidence",
            excerpt="An independent fictional comparison has limited relevance.",
        )
        # New broker text/use rights affect the v2 fingerprint. The prior
        # numeric receipt must not silently remain current.
        self.assertEqual(self.runs.get(CASE, old_run_id)["state"], "stale")
        current = self.knowledge.snapshot(
            self.patient_id, CASE, self.question, **self.actor())
        fingerprint = current["clinical_composer"]["composer"]["fingerprint"]
        queued = self.runs.queue(
            CASE, self.question, fingerprint, "hemoglobin", "PWM-V2-NUMERIC-0001")
        completed = self.runs.execute(CASE, queued["run_id"])
        self.assertEqual(completed["state"], "completed")

        facts = self.store.investigation_facts(CASE, self.question)
        valid = validate_output(
            payload(broker_id), facts["valid_sources"],
            facts["valid_assessments"], facts["valid_brokers"])
        self.assertEqual(len(valid.claims), 1)
        investigation_id = self.store.save_investigation(
            CASE, self.question, "evidence-summary", valid, "replay",
            context_fingerprint=facts["context_fingerprint"],
            input_receipts=facts["input_receipts"])
        selected = [{
            "assertion_id": self.assertion_id,
            "knowledge_id": "KNOW-SYN-001",
            "quote": "claims no therapeutic outcomes",
        }]
        return rights_id, investigation_id, queued["run_id"], selected

    def view(self, run_id, quotes):
        return self.world.preview(
            self.patient_id, CASE, self.question, run_id,
            selected_quotes=quotes, **self.actor())

    def investigation(self, investigation_id):
        return self.bundle.numeric.investigation_snapshot(
            self.patient_id, CASE, self.question, investigation_id,
            **self.actor())

    def test_current_patient_presentation_reconciles_v2_broker_hypothesis_and_numeric_review(self):
        rights_id, investigation_id, run_id, selected = self.configure_v2()
        case_before = self.store.state(CASE)["events"]
        packet = self.view(run_id, selected)
        hypothesis = self.investigation(investigation_id)
        self.assertEqual(packet["contract"],
                         "oi.synthetic-authorized-world-model-review/1")
        self.assertEqual(packet["unified_review"]["numeric_receipt"]["status"],
                         "current_numeric_receipt_pending_human_review")
        self.assertEqual(packet["unified_review"]["numeric_receipt"]["run"]
                         ["context_fingerprint"],
                         packet["unified_review"]["composer_context_fingerprint"])
        self.assertEqual(packet["unified_review"]["evidence_review"]
                         ["quoted_comparisons"][0]["external_reference"]["exact_quote"],
                         "claims no therapeutic outcomes")
        self.assertTrue(packet["patient_world_model"]["observations"])
        self.assertEqual(hypothesis["review_status"],
                         "unreviewed_source_bound_investigation")
        self.assertEqual(hypothesis["investigation"]["claims"][0]["citations"][0],
                         {"type": "broker", "id": hypothesis["investigation"]
                          ["claims"][0]["citations"][0]["id"]})
        self.assertFalse(packet["clinical_approval"])
        self.assertEqual(packet["human_review_state"], "pending")
        self.assertEqual(case_before, self.store.state(CASE)["events"],
                         "Read-only preview must not write a clinical event")
        self.assertEqual(next(q["state"] for q in self.store.state(CASE)["questions"]
                              if q["id"] == self.question), "open")

    def test_revoked_broker_rights_redact_model_and_stale_numeric_without_erasing_pwm(self):
        rights_id, investigation_id, run_id, selected = self.configure_v2()
        before = self.view(run_id, selected)
        self.store.revoke_rights_source(
            rights_id, "Independent fictional publication permissions withdrawn.")
        after = self.view(run_id, selected)
        held = self.investigation(investigation_id)
        self.assertEqual(after["unified_review"]["numeric_receipt"]["status"],
                         "historical_numeric_receipt_reassessment_required")
        self.assertEqual(after["unified_review"]["numeric_receipt"]["run"]
                         ["run"]["result"]["delta"], "-0.4")
        self.assertEqual(held["review_status"],
                         "historical_investigation_reassessment_required")
        self.assertEqual(held["investigation"]["claims"], [])
        self.assertEqual(held["investigation"]["abstentions"], [])
        self.assertTrue(held["investigation"]["output_withheld"])
        self.assertEqual(after["patient_world_model"]["observations"],
                         before["patient_world_model"]["observations"])
        self.assertFalse(after["clinical_approval"])

    def test_amended_source_stales_broker_model_and_preserves_historical_numeric_measurement(self):
        _, investigation_id, run_id, selected = self.configure_v2()
        self.store.import_report(
            CASE, numeric("NUM-LAB-2", "2026-03-01", "8.1", amendment=1))
        packet = self.view(run_id, selected)
        model = self.investigation(investigation_id)
        self.assertEqual(packet["unified_review"]["numeric_receipt"]["status"],
                         "historical_numeric_receipt_reassessment_required")
        self.assertEqual(packet["unified_review"]["numeric_receipt"]["run"]
                         ["result"]["result"]["delta"], "-0.4")
        self.assertEqual(model["review_status"],
                         "historical_investigation_reassessment_required")
        self.assertEqual(model["investigation"]["claims"], [])
        self.assertEqual(model["investigation"]["abstentions"], [])
        self.assertEqual(packet["human_review_state"], "pending")
        self.assertFalse(packet["clinical_approval"])


if __name__ == "__main__":
    unittest.main()
