import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.patient_report import render_text
from open_intelligence.store import CaseStore


class PatientReportHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "patient-report-http.sqlite")
        seed(cls.path)
        bound_handler = type(
            "BoundPatientReportHandlerForTest", (Handler,), {"db_path": cls.path}
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json"} if payload is not None else {},
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def test_seeded_case_exposes_read_only_patient_report(self):
        status, _, body = self.request("/api/cases/CASE-ALPHA/patient-report")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertTrue(payload["fictional"])
        self.assertIn("Fictional", payload["demo_notice"])
        self.assertEqual(
            payload["section_ids"],
            ["overview", "timeline", "questions", "options", "followthrough", "goals"],
        )
        overview = next(
            section for section in payload["sections"] if section["id"] == "overview"
        )
        self.assertEqual(overview["item_count"], 5)
        self.assertEqual(overview["cited_count"], 5)
        goals = next(
            section for section in payload["sections"] if section["id"] == "goals"
        )
        self.assertEqual(goals["items"], [])
        self.assertIn("Unknown", goals["empty_text"])

    def test_plain_text_format_matches_json_report(self):
        _, _, body = self.request("/api/cases/CASE-ALPHA/patient-report?format=text")
        text = body.decode("utf-8")

        self.assertTrue(text.startswith("OPEN INTELLIGENCE — PLAIN-LANGUAGE CASE REPORT\n"))
        self.assertIn("Fictional case CASE-ALPHA", text)
        self.assertIn("TIMELINE HIGHLIGHTS", text)
        self.assertIn("Source: Source version #", text)
        self.assertIn("Unknown — not stated in the record.", text)
        self.assertTrue(text.endswith("End of report.\n"))

    def test_json_download_payload_preserves_the_displayed_snapshot(self):
        store = CaseStore(self.path)
        try:
            store.add_case("CASE-REPORT-HTTP", "Fictional report HTTP case")
        finally:
            store.close()
        prefix = "/api/cases/CASE-REPORT-HTTP"
        status, _, body = self.request(prefix + "/followthrough-tasks", {
            "title": "Collect fictional notes for the next visit",
            "actor_label": "Fictional Recorder",
            "review_trigger": "The next fictional visit is arranged.",
        })
        self.assertEqual(status, 201)
        task_id = json.loads(body)["task_id"]
        _, headers, body = self.request(prefix + "/patient-report")
        displayed = json.loads(body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(displayed["text"], render_text(displayed))
        self.assertIn("Collect fictional notes for the next visit", displayed["text"])
        self.assertNotIn("Fictional New Owner", displayed["text"])

        status, _, _ = self.request(prefix + f"/followthrough-tasks/{task_id}/status", {
            "status": "assigned", "actor_label": "Fictional Recorder",
            "owner_label": "Fictional New Owner",
            "reason": "Assign the fictional preparation work to its owner.",
        })
        self.assertEqual(status, 200)
        _, _, body = self.request(prefix + "/patient-report")
        updated = json.loads(body)
        self.assertEqual(updated["text"], render_text(updated))
        self.assertIn("Fictional New Owner", updated["text"])
        self.assertNotEqual(updated["as_of"]["event_id"], displayed["as_of"]["event_id"])
        self.assertNotIn("Fictional New Owner", displayed["text"])
        _, _, body = self.request(prefix + "/patient-report?format=text")
        self.assertEqual(body.decode("utf-8"), updated["text"])
        _, _, body = self.request("/api/cases/CASE-BETA/patient-report")
        self.assertNotIn("Fictional New Owner", body.decode("utf-8"))
        self.assertNotIn("Collect fictional notes for the next visit", body.decode("utf-8"))

    def test_report_is_case_scoped(self):
        _, _, body = self.request("/api/cases/CASE-BETA/patient-report")
        rendered = body.decode("utf-8")

        self.assertNotIn("Marker A was not tested in this specimen.", rendered)

    def test_malformed_task_status_returns_422_without_changing_case(self):
        store = CaseStore(self.path)
        try:
            store.add_case("CASE-REPORT-INVALID", "Fictional invalid status case")
        finally:
            store.close()
        prefix = "/api/cases/CASE-REPORT-INVALID"
        status, _, body = self.request(prefix + "/followthrough-tasks", {
            "title": "Collect fictional appointment notes",
            "actor_label": "Fictional Recorder",
        })
        self.assertEqual(status, 201)
        task_id = json.loads(body)["task_id"]
        _, _, before = self.request(prefix + "/state")
        for invalid_status in ([], {}, ["completed"], 42, True, None):
            with self.subTest(status=invalid_status):
                status, _, body = self.request(prefix + f"/followthrough-tasks/{task_id}/status", {
                    "status": invalid_status, "actor_label": "Fictional Recorder",
                    "reason": "This malformed transition must leave the record untouched.",
                })
                self.assertEqual(status, 422)
                self.assertEqual(json.loads(body)["error"], "Invalid follow-through status")
        _, _, after = self.request(prefix + "/state")
        self.assertEqual(json.loads(after), json.loads(before))

    def test_unknown_case_uses_existing_case_boundary(self):
        status, _, body = self.request("/api/cases/CASE-UNKNOWN/patient-report")
        error = json.loads(body)

        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")

    def test_unexpected_host_cannot_read_patient_report(self):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(
                "GET",
                "/api/cases/CASE-ALPHA/patient-report",
                headers={"Host": f"untrusted.example:{self.port}"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            self.assertIn("Unexpected Host", response.read().decode())
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
