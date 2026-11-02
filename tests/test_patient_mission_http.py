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


class PatientMissionHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "patient-mission-http.sqlite")
        seed(cls.path)
        bound_handler = type(
            "BoundPatientMissionHandlerForTest", (Handler,), {"db_path": cls.path}
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

    def request(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_seeded_case_exposes_read_only_patient_mission(self):
        status, mission = self.request("/api/cases/CASE-ALPHA/mission")

        self.assertEqual(status, 200)
        self.assertEqual(mission["case"]["case_id"], "CASE-ALPHA")
        self.assertEqual(mission["case"]["scope"], "synthetic_workflow_only")
        self.assertEqual(mission["workflow_status"], "ready_to_define_question")
        self.assertEqual(mission["where_am_i"]["current_source_documents"], 2)
        self.assertEqual(mission["where_am_i"]["reported_statements"], 5)
        self.assertTrue(mission["what_we_know"])
        self.assertIn(
            "not a diagnosis or treatment recommendation",
            mission["guardrails"][0],
        )

    def test_unknown_case_uses_existing_case_boundary(self):
        status, error = self.request("/api/cases/CASE-UNKNOWN/mission")

        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")

    def test_unexpected_host_cannot_read_patient_mission(self):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(
                "GET",
                "/api/cases/CASE-ALPHA/mission",
                headers={"Host": f"untrusted.example:{self.port}"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            self.assertIn("Unexpected Host", response.read().decode())
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
