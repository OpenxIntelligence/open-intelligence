"""Real cross-branch source → Composer hypothesis → durable calculation acceptance.

These tests operate ONLY on independently authored fictional records, local
SQLite and local HTTP. No real patient, external source or live model is used.
They catch inconsistency between the existing model-investigation state and
the existing persisted computation run journal after input changes.
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.composer import build_composer_context
from open_intelligence.durable_runs import DurableComposerRuns
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.store import CaseStore


def lab_report(case, document, day, value, *, qc="passed"):
    return (
        "OI-SYNTHETIC-REPORT/1\n"
        f"Patient: {case}\nDocument: {document}\nType: laboratory\n"
        f"Event-Date: {day}\nIssued-At: {day}\n"
        "Specimen: SPEC-INTEGRATION\n"
        f"Finding: hemoglobin|reported|OI-LAB-VALUE/1;value={value};unit=g/dL;qc={qc}\n"
    ).encode("utf-8")


def evidence():
    return (
        "OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVID-INTEGRATED\n"
        "Title: Original fictional laboratory interpretation limitations\n"
        "Issued-At: 2026-01-03\nRights: original-synthetic\n"
        "Statement: Fictional technical limitations do not establish clinical benefit.\n"
    ).encode("utf-8")


class CrossBranchComposerIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "integrated-fiction.sqlite")
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        self.first = lab_report("CASE-ALPHA", "LAB-INTEG-A", "2026-05-01", "10.2")
        self.second = lab_report("CASE-ALPHA", "LAB-INTEG-B", "2026-06-01", "9.8")
        self.store.import_report("CASE-ALPHA", self.first)
        self.store.import_report("CASE-ALPHA", self.second)
        self.question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional laboratory record establish?")
        self.beta_question = self.store.add_question(
            "CASE-BETA", "What source information is missing in fictional case Beta?")
        self.runs = DurableComposerRuns(self.store)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def context(self, case="CASE-ALPHA", question_id=None):
        return build_composer_context(
            self.store, case, self.question if question_id is None else question_id)

    def model(self, case="CASE-ALPHA", question_id=None):
        q = self.question if question_id is None else question_id
        result = ValidatedInvestigation(
            "abstained", [], [{"topic": "Unsupported clinical inference",
                               "reason": "insufficient_evidence"}],
            [], "recorded-replay", "replay")
        fp = self.context(case, q)["fingerprint"]
        return self.store.save_investigation(
            case, q, "evidence-summary", result, "replay",
            context_fingerprint=fp)

    def completed_numeric_work(self, key="INTEG-RUN-0001", question=None):
        q = self.question if question is None else question
        fresh = self.context(question_id=q)["fingerprint"]
        item = self.runs.queue("CASE-ALPHA", q, fresh, "hemoglobin", key)
        done = self.runs.execute("CASE-ALPHA", item["run_id"])
        self.assertEqual(done["state"], "completed")
        self.assertEqual(done["result"]["result"]["delta"], "-0.4")
        self.assertEqual(done["clinical_authorization"], "not_verified")
        self.assertTrue(done["result"]["result"]["points"][0]["source"]["source_sha256"])
        return done

    def question_status(self, case, question):
        return next(row["state"] for row in self.store.state(case)["questions"]
                    if row["id"] == question)

    def acknowledge_question(self, case, question):
        source_id = next(s["id"] for s in self.store.state(case)["sources"]
                         if s["state"] == "current")
        snapshot_id = self.store.create_snapshot(
            case, question, "A human-authored fictional source review.", [source_id])
        self.store.acknowledge_demo_review(case, snapshot_id, "Synthetic reviewer")
        self.assertEqual(self.question_status(case, question), "addressed")

    def test_new_accepted_source_stales_model_and_completed_run_together(self):
        self.store.import_report(
            "CASE-BETA", lab_report("CASE-BETA", "LAB-BETA-REVIEW", "2026-06-01", "8.8"))
        self.acknowledge_question("CASE-ALPHA", self.question)
        self.acknowledge_question("CASE-BETA", self.beta_question)
        model = self.model()
        beta_model = self.model("CASE-BETA", self.beta_question)
        done = self.completed_numeric_work()
        old_model = self.store.get_investigation("CASE-ALPHA", model)
        imported = self.store.import_report(
            "CASE-ALPHA",
            lab_report("CASE-ALPHA", "LAB-INTEG-C", "2026-07-01", "9.4"))
        self.assertEqual(imported["result"], "imported")
        self.assertIn(model, imported.get("invalidated_model_investigation_ids", []))
        old_after = self.store.get_investigation("CASE-ALPHA", model)
        self.assertTrue(old_after["stale"])
        self.assertEqual(old_after["abstentions"], old_model["abstentions"])
        self.assertEqual(self.question_status("CASE-ALPHA", self.question), "open")
        completed_after = self.runs.get("CASE-ALPHA", done["run_id"])
        self.assertEqual(completed_after["state"], "stale")
        self.assertEqual(completed_after["result"]["result"]["delta"], "-0.4")
        self.assertEqual(completed_after["events"][-1]["reason"], "source_context_changed")
        self.assertFalse(self.store.get_investigation("CASE-BETA", beta_model)["stale"])
        self.assertEqual(self.question_status("CASE-BETA", self.beta_question), "addressed")
        original = self.store.source_text(
            "CASE-ALPHA", done["result"]["result"]["points"][0]["source"]["source_version_id"])
        self.assertIn("OI-LAB-VALUE/1;value=10.2", original)

    def test_new_question_assessment_invalidates_only_that_model_and_its_run(self):
        second_question = self.store.add_question(
            "CASE-ALPHA", "Which other unresolved source fact exists?")
        self.acknowledge_question("CASE-ALPHA", self.question)
        self.acknowledge_question("CASE-ALPHA", second_question)
        a = self.model()
        b = self.model(question_id=second_question)
        work = self.completed_numeric_work()
        v = self.store.import_synthetic_evidence(evidence())
        self.assertEqual(v["result"], "imported")
        # Unassessed library material is not model-prompt evidence.
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", a)["stale"])
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.question, v["evidence_version_id"],
            "context", "limited",
            "This fictional evidence has limited applicability for this question.")
        self.assertTrue(self.store.get_investigation("CASE-ALPHA", a)["stale"])
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", b)["stale"])
        self.assertEqual(self.question_status("CASE-ALPHA", self.question), "open")
        self.assertEqual(self.question_status("CASE-ALPHA", second_question), "addressed")
        self.assertEqual(self.runs.get("CASE-ALPHA", work["run_id"])["state"], "stale")
        self.assertEqual(self.runs.get("CASE-ALPHA", work["run_id"])["result"]["result"]["delta"],
                         "-0.4")

    def test_evidence_withdrawal_preserves_original_model_and_numeric_receipt(self):
        evidence_id = self.store.import_synthetic_evidence(evidence())["evidence_version_id"]
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.question, evidence_id,
            "supports", "limited",
            "Only a limited fictional methodological statement is supported.")
        model_id = self.model()
        done = self.completed_numeric_work("INTEG-RUN-0002")
        before = self.store.get_investigation("CASE-ALPHA", model_id)
        self.store.withdraw_synthetic_evidence(
            evidence_id, "Original fictional evidence withdrawn for rights recheck.")
        after = self.store.get_investigation("CASE-ALPHA", model_id)
        self.assertTrue(after["stale"])
        self.assertEqual(after["created_at"], before["created_at"])
        self.assertEqual(after["abstentions"], before["abstentions"])
        self.assertEqual(self.runs.get("CASE-ALPHA", done["run_id"])["state"], "stale")
        self.assertEqual(len(self.runs.get("CASE-ALPHA", done["run_id"])["events"]), 4)

    def test_duplicate_and_cross_patient_quarantine_leave_current_work_unchanged(self):
        self.acknowledge_question("CASE-ALPHA", self.question)
        model_id = self.model()
        done = self.completed_numeric_work("INTEG-RUN-0003")
        self.assertEqual(self.store.import_report("CASE-ALPHA", self.first)["result"], "duplicate")
        self.assertEqual(self.store.import_report("CASE-BETA", self.first)["result"],
                         "quarantined")
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", model_id)["stale"])
        self.assertEqual(self.question_status("CASE-ALPHA", self.question), "addressed")
        self.assertEqual(self.runs.get("CASE-ALPHA", done["run_id"])["state"], "completed")
        self.assertEqual(self.runs.list("CASE-BETA"), [])


class ComposerHttpContinuity(CrossBranchComposerIntegration):
    def setUp(self):
        super().setUp()
        handler = type("BoundCrossBranchHandler", (Handler,), {"db_path": self.path})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def request(self, path, body=None):
        uri = f"http://127.0.0.1:{self.server.server_port}{path}"
        request = Request(uri, data=None if body is None else json.dumps(body).encode("utf-8"),
                          headers={} if body is None else {"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=8) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_actual_http_chart_composer_and_run_share_one_source_change(self):
        base = "/api/cases/CASE-ALPHA"
        _, preview = self.request(base + f"/composer/context?question_id={self.question}")
        status, model = self.request(base + "/investigations", {
            "question_id": self.question, "template": "evidence-summary",
            "mode": "replay", "context_fingerprint": preview["fingerprint"]})
        self.assertEqual(status, 201)
        self.assertEqual(model["review_state"], "pending")
        _, revised = self.request(base + f"/composer/context?question_id={self.question}")
        root = base + "/composer/runs"
        status, task = self.request(root, {
            "question_id": self.question, "context_fingerprint": revised["fingerprint"],
            "finding_key": "hemoglobin", "idempotency_key": "HTTP-INTEGRATION-0001"})
        self.assertEqual(status, 201)
        self.assertEqual(task["state"], "queued")
        status, finished = self.request(root + f"/{task['run_id']}/execute", {})
        self.assertEqual(status, 200)
        self.assertEqual(finished["state"], "completed")
        self.assertEqual(finished["result"]["result"]["delta"], "-0.4")
        raw = lab_report("CASE-ALPHA", "LAB-INTEG-C", "2026-07-01", "9.4")
        status, uploaded = self.request(base + "/imports", {"text": raw.decode()})
        self.assertEqual(status, 200)
        self.assertEqual(uploaded["result"], "imported")
        status, hypothesis = self.request(base + f"/investigations/{model['id']}")
        self.assertEqual(status, 200)
        self.assertTrue(hypothesis["stale"])
        status, history = self.request(root + f"/{task['run_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(history["state"], "stale")
        self.assertEqual(history["result"]["result"]["delta"], "-0.4")
        status, beta = self.request("/api/cases/CASE-BETA/composer/runs")
        self.assertEqual(status, 200)
        self.assertEqual(beta["runs"], [])
        status, newer = self.request(base + f"/composer/context?question_id={self.question}")
        self.assertEqual(status, 200)
        self.assertNotEqual(preview["fingerprint"], newer["fingerprint"])
        self.assertEqual(newer["question_state"], "open")


if __name__ == "__main__":
    unittest.main()
