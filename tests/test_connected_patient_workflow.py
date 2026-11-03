"""One fictional patient across existing record, evidence, report and task owners.

This is integration verification, not clinical approval, live evidence retrieval,
real identity or a second state store. Original source-owner fixtures are reused.
"""
import importlib.util
import unittest
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.world_model import synthetic_world_model
import test_pwm_v2_report_receipt_integration as prior

CASE = prior.CASE


class ConnectedPatientWorkflowTests(unittest.TestCase):
    setUp = prior.PatientWorldModelReportReceiptIntegration.setUp
    actor = prior.PatientWorldModelReportReceiptIntegration.actor
    workflow = prior.PatientWorldModelReportReceiptIntegration.workflow
    _source = prior.PatientWorldModelReportReceiptIntegration._source
    prepare = prior.PatientWorldModelReportReceiptIntegration.prepare
    candidate = prior.PatientWorldModelReportReceiptIntegration.candidate
    build = prior.PatientWorldModelReportReceiptIntegration.build
    report = prior.PatientWorldModelReportReceiptIntegration.report
    world = prior.PatientWorldModelReportReceiptIntegration.world
    hypothesis = prior.PatientWorldModelReportReceiptIntegration.hypothesis

    def connected(self):
        self.assertTrue(callable(getattr(self.store, "create_followthrough_task", None)),
                        "Existing follow-through owner is not integrated into the clinical/evidence store")
        self.assertIsNotNone(importlib.util.find_spec("open_intelligence.patient_report"),
                             "Existing readable patient report owner is not integrated")
        scope = self.build()
        source = next(s for s in self.store.state(CASE)["sources"]
                      if s["document_id"] == "ORDER-CONT-001")
        return scope, source

    def task(self, question, source_id, title):
        return self.store.create_followthrough_task(
            CASE, title, actor_label="Fictional coordinator",
            reason="Prepare materials for an independent fictional source review.",
            question_id=question, source_version_id=source_id,
            due_date="2026-11-04", review_trigger="When original source material changes")

    def complete(self, task_id):
        for status in ("assigned", "acknowledged", "completed"):
            kwargs = {"owner_label": "Fictional reviewer"} if status == "assigned" else {}
            self.store.update_followthrough_task(
                CASE, task_id, status, actor_label="Fictional coordinator",
                reason="Record the fictional preparation work without clinical sign-off.", **kwargs)

    def test_two_time_points_keep_one_source_question_review_and_task_history(self):
        scope, source = self.connected()
        from open_intelligence.patient_report import build_patient_report, render_text
        original = self.store.source_text(CASE, source["id"])
        world = self.world(scope)
        self.assertTrue(any(o["source_version_id"] == source["id"]
                            for o in world["patient_world_model"]["observations"]))
        prepared = self.report(scope)
        open_task = self.task(scope["question"], source["id"], "Collect fictional review materials")
        done_task = self.task(scope["question"], source["id"], "Record fictional packet preparation")
        self.complete(done_task)
        first = self.store.state(CASE)
        self.assertEqual(next(q["state"] for q in first["questions"]
                              if q["id"] == scope["question"]), "open")
        readable = render_text(build_patient_report(first))
        self.assertIn(f"Follow-through task #{open_task}.", readable)
        self.assertIn(source["sha256"], readable)
        self.assertIn("Recorded status: completed", readable)
        self.assertFalse(prepared["clinical_signoff"])
        prior_history = next(t["history"] for t in first["followthrough"]["tasks"]
                             if t["id"] == done_task)
        replacement = self._source("ORDER-CONT-001", "clinical", "order", "negative", amendment=1)
        second = self.store.state(CASE)
        tasks = {t["id"]: t for t in second["followthrough"]["tasks"]}
        self.assertTrue(tasks[open_task]["needs_recheck"])
        self.assertFalse(tasks[done_task]["needs_recheck"])
        self.assertEqual(tasks[done_task]["history"], prior_history)
        self.assertEqual(tasks[done_task]["source_version_id"], source["id"])
        self.assertEqual(self.store.source_text(CASE, source["id"]), original)
        self.assertNotEqual(replacement, source["id"])
        revised_world = synthetic_world_model(second, CASE)
        self.assertFalse(any(o["source_version_id"] == source["id"]
                             for o in revised_world["observations"]))
        with self.assertRaises((KnowledgeContextError, ClinicalContinuityError)):
            self.report(scope)
        self.assertEqual(len(self.store.review_queue(CASE)["receipts"]), 1)
        self.assertEqual(self.store.review_queue(CASE)["receipts"][0]["id"],
                         prepared["receipt"]["receipt_id"])
        updated = render_text(build_patient_report(second))
        self.assertIn("linked source amended", updated)
        self.assertIn(source["sha256"], updated)
        reopened = CaseStore(self.store.path)
        try:
            recovered = reopened.state(CASE)
            self.assertEqual(recovered["followthrough"]["tasks"], second["followthrough"]["tasks"])
            self.assertEqual(render_text(build_patient_report(recovered)), updated)
            self.assertEqual(reopened.review_queue(CASE)["receipts"],
                             self.store.review_queue(CASE)["receipts"])
        finally:
            reopened.close()

    def test_rights_revocation_withholds_model_text_without_erasing_task_history(self):
        scope, source = self.connected()
        prepared = self.report(scope)
        task_id = self.task(scope["question"], source["id"], "Record fictional material preparation")
        self.complete(task_id)
        history = self.store.state(CASE)["followthrough"]["tasks"][0]["history"]
        self.store.revoke_rights_source(scope["rights_id"], "Fictional rights permission withdrawn.")
        self.assertTrue(self.hypothesis(scope)["investigation"]["output_withheld"])
        self.assertEqual(self.hypothesis(scope)["investigation"]["claims"], [])
        self.assertEqual(self.store.state(CASE)["followthrough"]["tasks"][0]["history"], history)
        self.assertFalse(prepared["clinical_signoff"])

    def test_wrong_case_cannot_adopt_or_change_the_connected_followthrough(self):
        scope, source = self.connected()
        from open_intelligence.patient_report import build_patient_report, render_text
        task_id = self.task(scope["question"], source["id"], "Private fictional packet for this case")
        other = "CASE-CLIN-CONT-OTHER"
        before = self.store.state(CASE)
        with self.assertRaises(InvalidInput):
            self.store.create_followthrough_task(
                other, "Unrelated fictional packet", actor_label="Fictional coordinator",
                source_version_id=source["id"], question_id=scope["question"],
                due_date="2026-11-04")
        with self.assertRaises(InvalidInput):
            self.store.update_followthrough_task(
                other, task_id, "assigned", actor_label="Fictional coordinator",
                owner_label="Fictional owner", reason="Different case cannot alter this task.")
        self.assertEqual(self.store.state(CASE), before)
        self.assertNotIn("Private fictional packet", render_text(build_patient_report(self.store.state(other))))


if __name__ == "__main__":
    unittest.main()
