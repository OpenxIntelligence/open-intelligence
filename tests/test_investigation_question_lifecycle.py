"""An unreviewed model attempt must not settle a patient's open question.

All cases and results are independently authored synthetic fixtures. The HTTP
journey uses the offline replay path and a loopback-only test server.
"""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.composer import build_composer_context, composer_context_fingerprint
from open_intelligence.investigation import ValidatedInvestigation, validate_output
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import CaseStore, InvalidInput


FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class InvestigationQuestionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "case.sqlite"
        self.store = CaseStore(self.db_path)
        self.addCleanup(lambda: self.store.close())
        self.store.add_case("CASE-ALPHA", "Fictional lifecycle case Alpha")
        self.store.add_case("CASE-BETA", "Fictional lifecycle case Beta")
        imported = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-original.txt").read_bytes()
        )
        self.source_id = imported["source_id"]

    def result(self):
        result = validate_output(
            {
                "claims": [{
                    "text": "An authored synthetic report is available for review.",
                    "support": "context",
                    "citations": [{"type": "source", "id": self.source_id}],
                    "uncertainty": "high",
                    "limits": "This is an unreviewed synthetic research hypothesis.",
                }],
                "abstentions": [],
            },
            {self.source_id},
            set(),
        )
        result.mode = "replay"
        result.model = "recorded-replay"
        return result

    def test_investigation_storage_fails_closed_for_cross_case_question(self):
        # A valid question ID owned by another case is not sufficient authority
        # to insert a result into this case's investigation ledger.
        other_question = self.store.add_question(
            "CASE-BETA", "Why does this invented other case remain distinct?"
        )
        before_alpha = self.store.state("CASE-ALPHA")
        before_beta = self.store.state("CASE-BETA")
        for invalid_id in (other_question, 999999, True):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(InvalidInput):
                    self.store.save_investigation(
                        "CASE-ALPHA", invalid_id, "evidence-summary",
                        self.result(), "replay"
                    )
        self.assertEqual(self.store.list_investigations("CASE-ALPHA"), [])
        self.assertEqual(self.store.state("CASE-ALPHA")["questions"],
                         before_alpha["questions"])
        self.assertEqual(self.store.state("CASE-BETA")["questions"],
                         before_beta["questions"])
        self.assertEqual(self.store.state("CASE-ALPHA")["events"],
                         before_alpha["events"])

    def test_every_unreviewed_attempt_keeps_its_question_open(self):
        for status in ("completed", "abstained", "blocked_by_policy", "failed"):
            with self.subTest(status=status):
                question_id = self.store.add_question(
                    "CASE-ALPHA", f"What remains unresolved after a {status} attempt?"
                )
                result = self.result() if status == "completed" else ValidatedInvestigation(
                    status=status, claims=[],
                    abstentions=[{"topic": "question", "reason": "insufficient_evidence"}],
                    dropped=[], model="recorded-replay", mode="replay",
                )
                investigation_id = self.store.save_investigation(
                    "CASE-ALPHA", question_id, "evidence-summary", result, "replay"
                )

                receipt = self.store.get_investigation("CASE-ALPHA", investigation_id)
                self.assertEqual(receipt["status"], status)
                self.assertEqual(receipt["review_state"], "pending")
                questions = {
                    row["id"]: row["state"]
                    for row in self.store.state("CASE-ALPHA")["questions"]
                }
                self.assertEqual(questions[question_id], "open")

    def test_invalid_question_identifiers_fail_before_database_access(self):
        # In particular, Python bools must not alias question 1, and integers
        # outside SQLite's signed 64-bit range must not escape as OverflowError.
        self.store.add_question("CASE-ALPHA", "Which fictional source needs review?")
        validated = self.result()
        invalid_ids = (True, False, None, "1", 1.0, [], {}, 0, -1,
                       2**63, -(2**63) - 1, 10**100)
        operations = {
            "facts": lambda q: self.store.investigation_facts("CASE-ALPHA", q),
            "save": lambda q: self.store.save_investigation(
                "CASE-ALPHA", q, "evidence-summary", validated, "replay"),
        }
        before = self.store.state("CASE-ALPHA")
        for operation, call in operations.items():
            for question_id in invalid_ids:
                with self.subTest(operation=operation, question_id=question_id):
                    statements = []
                    self.store.db.set_trace_callback(statements.append)
                    error = None
                    try:
                        call(question_id)
                    except Exception as exc:
                        error = exc
                    finally:
                        self.store.db.set_trace_callback(None)
                    self.assertIsInstance(error, InvalidInput)
                    self.assertEqual(statements, [])
        self.assertEqual(self.store.state("CASE-ALPHA"), before)
        self.assertEqual(self.store.list_investigations("CASE-ALPHA"), [])

    def test_facts_reject_foreign_and_absent_representable_question_ids(self):
        other_question = self.store.add_question(
            "CASE-BETA", "Why does this invented other case remain distinct?"
        )
        before_alpha = self.store.state("CASE-ALPHA")
        before_beta = self.store.state("CASE-BETA")
        for question_id in (other_question, 999999, 2**63 - 1):
            with self.subTest(question_id=question_id):
                with self.assertRaises(InvalidInput):
                    self.store.investigation_facts("CASE-ALPHA", question_id)
                with self.assertRaises(InvalidInput):
                    self.store.save_investigation(
                        "CASE-ALPHA", question_id, "evidence-summary", self.result(), "replay"
                    )
        self.assertEqual(self.store.state("CASE-ALPHA"), before_alpha)
        self.assertEqual(self.store.state("CASE-BETA"), before_beta)
        self.assertEqual(self.store.list_investigations("CASE-ALPHA"), [])

    def test_composer_rejects_unrepresentable_question_ids(self):
        for read in (build_composer_context, composer_context_fingerprint):
            for question_id in (2**63, 10**100):
                with self.subTest(reader=read.__name__, question_id=question_id):
                    error = None
                    try:
                        read(self.store, "CASE-ALPHA", question_id)
                    except Exception as exc:
                        error = exc
                    self.assertIsInstance(error, InvalidInput)

    def test_http_rejects_huge_question_with_forged_context_fingerprint(self):
        handler = type("BoundedQuestionHandler", (Handler,), {
            "db_path": str(self.db_path),
            "log_message": lambda self, *args: None,
        })
        before = self.store.state("CASE-ALPHA")
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/cases/CASE-ALPHA/investigations",
                data=json.dumps({"question_id": 2**63, "template": "evidence-summary",
                                 "mode": "replay", "context_fingerprint": "0" * 64}).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with self.assertRaises(HTTPError) as caught:
                    urlopen(request, timeout=5)
                self.assertEqual(caught.exception.code, 422)
                with caught.exception as response:
                    self.assertIn("error", json.loads(response.read()))
            finally:
                server.shutdown()
                thread.join(timeout=5)
        self.assertEqual(self.store.state("CASE-ALPHA"), before)
        self.assertEqual(self.store.list_investigations("CASE-ALPHA"), [])

    def test_receipt_and_unresolved_mission_survive_restart(self):
        question_id = self.store.add_question(
            "CASE-ALPHA", "What still needs a human review?"
        )
        investigation_id = self.store.save_investigation(
            "CASE-ALPHA", question_id, "evidence-summary", self.result(), "replay"
        )
        self.store.close()
        self.store = CaseStore(self.db_path)

        receipt = self.store.get_investigation("CASE-ALPHA", investigation_id)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["kind"], "hypothesis")
        self.assertEqual(receipt["review_state"], "pending")
        self.assertEqual(receipt["model"], "recorded-replay")
        self.assertEqual(receipt["claims"][0]["citations"],
                         [{"type": "source", "id": self.source_id}])
        state = self.store.state("CASE-ALPHA")
        self.assertTrue(any(
            event["kind"] == "investigation_created"
            and json.loads(event["details"])["investigation_id"] == investigation_id
            for event in state["events"]
        ))
        mission = build_patient_mission(state)
        self.assertEqual(mission["workflow_status"], "investigation_in_progress")
        self.assertEqual(mission["where_am_i"]["open_questions"], 1)
        self.assertEqual(
            [row["question_id"] for row in mission["what_remains_unresolved"]["questions"]],
            [question_id],
        )
        self.assertNotIn("monitor_changes", {row["kind"] for row in mission["next_actions"]})

    def test_explicit_demo_review_addresses_only_its_question(self):
        reviewed_question = self.store.add_question("CASE-ALPHA", "Which source needs review?")
        other_question = self.store.add_question("CASE-ALPHA", "What remains unexplained?")
        beta_question = self.store.add_question("CASE-BETA", "What is missing in Beta?")
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", reviewed_question,
            "A human-authored draft for a bounded synthetic review.", [self.source_id]
        )
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        # A subsequent attempt neither reopens the acknowledged question nor
        # promotes a model receipt into that separate demo review.
        investigation_id = self.store.save_investigation(
            "CASE-ALPHA", reviewed_question, "evidence-summary", self.result(), "replay"
        )
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(
            {row["id"]: row["state"] for row in state["questions"]},
            {reviewed_question: "addressed", other_question: "open"},
        )
        self.assertEqual(state["snapshots"][0]["state"], "reviewed_in_demo")
        self.assertEqual(
            self.store.get_investigation("CASE-ALPHA", investigation_id)["review_state"],
            "pending",
        )
        self.assertEqual(
            {row["id"]: row["state"] for row in self.store.state("CASE-BETA")["questions"]},
            {beta_question: "open"},
        )

    def test_http_replay_preserves_open_questions_with_and_without_evidence(self):
        handler = type("LifecycleHandler", (Handler,), {
            "db_path": str(self.db_path),
            "log_message": lambda self, *args: None,
        })
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(path, data=None):
                req = Request(
                    f"http://127.0.0.1:{server.server_address[1]}{path}",
                    data=None if data is None else json.dumps(data).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(req, timeout=5) as response:
                    return response.status, json.loads(response.read())

            try:
                for case_id, expected_status in (("CASE-ALPHA", "completed"),
                                                 ("CASE-BETA", "abstained")):
                    with self.subTest(case_id=case_id):
                        status, question = request(f"/api/cases/{case_id}/questions", {
                            "question": "What still needs a source-grounded review?"
                        })
                        self.assertEqual(status, 201)
                        question_id = question["question_id"]
                        status, receipt = request(f"/api/cases/{case_id}/investigations", {
                            "question_id": question_id,
                            "template": "evidence-summary", "mode": "replay",
                        })
                        self.assertEqual(status, 201)
                        self.assertEqual(receipt["status"], expected_status)
                        self.assertEqual(receipt["review_state"], "pending")
                        status, mission = request(f"/api/cases/{case_id}/mission")
                        self.assertEqual(status, 200)
                        self.assertEqual(mission["where_am_i"]["open_questions"], 1)
                        self.assertEqual(
                            [row["question_id"] for row in
                             mission["what_remains_unresolved"]["questions"]],
                            [question_id],
                        )
                        self.assertNotIn("monitor_changes", {
                            row["kind"] for row in mission["next_actions"]
                        })
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
