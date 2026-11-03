"""One fictional patient: source World Model, rights-aware Composer v2, report and review.

The test reuses the original patient/EHR/LIS, knowledge, quote, numerical and
review owners. Public case datasets, clinician credentials, live models, licensed
medical text and clinical actions are never used. Report preparation is NOT
approval or delivery.
"""
import json
import unittest

from open_intelligence.authorized_world_model_review import AuthorizedWorldModelReview
from open_intelligence.durable_runs import DurableComposerRuns
from open_intelligence.evidence_report_handoff import ReportReviewHandoff
from open_intelligence.evidence_review_report import EvidenceReviewReport
from open_intelligence.investigation import validate_output
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.unified_clinical_review import UnifiedClinicalReview

from test_authorized_evidence_review_handoff import ReviewHandoffTests as Fixture, CASE
from test_composer_broker_context import link, payload
from test_patient_research_run_review import numeric


class PatientWorldModelReportReceiptIntegration(unittest.TestCase):
    setUp = Fixture.setUp
    actor = Fixture.actor
    workflow = Fixture.workflow
    _source = Fixture._source
    prepare = Fixture.prepare
    candidate = Fixture.candidate

    def build(self):
        handoff, question, assessment, sources, quotes = self.candidate()
        for item in ("metadata", "full_text"):
            sources[0]["permissions"][item]["redistribute"] = "allowed"
        renderer = EvidenceReviewReport(
            handoff.packet,
            export_authorizer=lambda a, p, op, purpose: (
                a == self.actor()["actor"] and p == self.patient_id
                and op == "evidence_report.export" and purpose == "care"))
        report_review = ReportReviewHandoff(renderer, handoff)

        # Two fresh original fictional numeric reports, on the existing ledger.
        first = self.store.import_report(
            CASE, numeric("NUM-REPORT-001", "2026-02-01", "10.2"))["source_id"]
        second = self.store.import_report(
            CASE, numeric("NUM-REPORT-002", "2026-03-01", "9.8"))["source_id"]

        rights_id, broker_id = link(
            self.store, question, key="SYNTHETIC-REPORT-BROKER-V2",
            case=CASE, citation_title="Fictional counterevidence",
            excerpt="Independent fictional analysis does not establish clinical benefit.")
        knowledge = handoff.packet.bridge
        runs = DurableComposerRuns(self.store)
        snapshot = knowledge.snapshot(
            self.patient_id, CASE, question, **self.actor())
        fingerprint = snapshot["clinical_composer"]["composer"]["fingerprint"]
        queued = runs.queue(
            CASE, question, fingerprint, "hemoglobin", "REPORT-PWM-V2-RUN-001")
        done = runs.execute(CASE, queued["run_id"])
        self.assertEqual(done["state"], "completed")

        facts = self.store.investigation_facts(CASE, question)
        validated = validate_output(
            payload(broker_id), facts["valid_sources"],
            facts["valid_assessments"], facts["valid_brokers"])
        self.assertEqual(len(validated.claims), 1)
        investigation_id = self.store.save_investigation(
            CASE, question, "evidence-summary", validated, "replay",
            context_fingerprint=facts["context_fingerprint"],
            input_receipts=facts["input_receipts"])
        unified = UnifiedClinicalReview(knowledge, runs)
        world = AuthorizedWorldModelReview(unified)
        return {
            "service": report_review, "question": question,
            "assessment": assessment, "quotes": quotes, "world": world,
            "unified": unified, "run_id": queued["run_id"],
            "investigation_id": investigation_id, "rights_id": rights_id,
            "sources": {first, second}
        }

    def report(self, scope):
        return scope["service"].return_for_review(
            self.patient_id, CASE, scope["question"], scope["assessment"],
            selected_quotes=scope["quotes"],
            reason="Independent professional review required for fictional evidence.",
            **self.actor())

    def world(self, scope):
        return scope["world"].preview(
            self.patient_id, CASE, scope["question"], scope["run_id"],
            selected_quotes=scope["quotes"], **self.actor())

    def hypothesis(self, scope):
        return scope["unified"].numeric.investigation_snapshot(
            self.patient_id, CASE, scope["question"],
            scope["investigation_id"], **self.actor())

    def test_one_patient_world_model_to_report_and_nonterminal_review_receipt(self):
        scope = self.build()
        original = self.world(scope)
        hypothesis = self.hypothesis(scope)
        self.assertEqual(original["unified_review"]["numeric_receipt"]["status"],
                         "current_numeric_receipt_pending_human_review")
        self.assertEqual(hypothesis["review_status"],
                         "unreviewed_source_bound_investigation")
        self.assertEqual({p["source_version_id"] for p in original["unified_review"]
                          ["numeric_receipt"]["original_source_provenance"]}, scope["sources"])

        sent = self.report(scope)
        self.assertEqual(sent["contract"], "oi.synthetic-report-review-handoff/1")
        self.assertFalse(sent["clinical_signoff"])
        self.assertEqual(sent["receipt_semantics"],
                         "prepared_report_reference_not_delivery_or_approval")
        self.assertEqual(sent["report"]["human_review_state"], "pending")
        queue = self.store.review_queue(CASE)
        self.assertTrue(any(
            r["queue_key"] == sent["receipt"]["queue_key"] and r["action"] == "returned"
            for r in queue["receipts"]))
        self.assertFalse(any(
            item["queue_key"] == sent["receipt"]["queue_key"]
            for item in queue["resolved"]))
        record = next(
            json.loads(event["details"])["prepared_report"]
            for event in self.store.state(CASE)["events"]
            if event["kind"] == "review_receipt_recorded")
        self.assertEqual(record["body_sha256"], sent["report"]["body_sha256"])
        self.assertEqual(record["packet_sha256"], sent["report"]["packet_sha256"])
        self.assertNotIn("body", record)
        self.assertEqual(record["semantics"], "prepared_not_delivery_or_approval")
        self.assertEqual(next(q["state"] for q in self.store.state(CASE)["questions"]
                              if q["id"] == scope["question"]), "open")
        # Even after the queue receipt, no medical authority is added.
        current = self.world(scope)
        self.assertFalse(current["clinical_approval"])
        self.assertEqual(current["human_review_state"], "pending")

    def test_broker_revocation_withholds_hypothesis_and_preserves_prepared_history(self):
        scope = self.build()
        sent = self.report(scope)
        self.store.revoke_rights_source(
            scope["rights_id"], "Synthetic publication permission withdrawn.")
        world = self.world(scope)
        model = self.hypothesis(scope)
        self.assertEqual(world["unified_review"]["numeric_receipt"]["status"],
                         "historical_numeric_receipt_reassessment_required")
        self.assertEqual(model["review_status"],
                         "historical_investigation_reassessment_required")
        self.assertEqual(model["investigation"]["claims"], [])
        self.assertEqual(model["investigation"]["abstentions"], [])
        self.assertTrue(model["investigation"]["output_withheld"])
        # The earlier receipt is historical; it was not a delivery/approval.
        receipts = self.store.review_queue(CASE)["receipts"]
        self.assertTrue(any(r["id"] == sent["receipt"]["receipt_id"] for r in receipts))
        self.assertFalse(world["clinical_approval"])

    def test_source_correction_cannot_relabel_a_prepared_report_as_current(self):
        scope = self.build()
        first = self.report(scope)
        self._source("ORDER-CONT-001", "clinical", "order",
                     "negative", amendment=1)
        prior = len(self.store.review_queue(CASE)["receipts"])
        with self.assertRaises((KnowledgeContextError, ClinicalContinuityError)):
            self.report(scope)
        self.assertEqual(len(self.store.review_queue(CASE)["receipts"]), prior)
        self.assertEqual(first["receipt_semantics"],
                         "prepared_report_reference_not_delivery_or_approval")


if __name__ == "__main__":
    unittest.main()
