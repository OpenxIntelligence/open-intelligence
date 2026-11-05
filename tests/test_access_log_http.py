"""Slice 1 access-log HTTP route: operator/auditor read-only view.

Fictional actors/cases only. The route is role-only (no grant required:
auditors hold no case grants by design) and requires a session — the
transitional header identifies the demo clinician, which holds neither role.
"""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore
from open_intelligence.__main__ import (
    AUTH_REQUIRED_MESSAGE,
    DEMO_ACTOR,
    DEMO_OPERATOR,
    FICTIONAL_ACTOR_HEADER,
    FICTIONAL_ACTOR_PURPOSE,
    ROLE_DENIAL_MESSAGE,
    Handler,
)

OPERATOR = DEMO_OPERATOR
CLINICIAN = DEMO_ACTOR
AUDITOR = "FICTIONAL-AUDITOR-A"
PATIENT = "FICTIONAL-PATIENT-A"
CASE_A = "CASE-FIG-01"
CASE_B = "CASE-FIG-02"
PASSWORD = "fictional-demo-1"
PURPOSE = FICTIONAL_ACTOR_PURPOSE


class AccessLogHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "access-log.sqlite")
        self.store = CaseStore(self.db_path)
        self.store.add_case(CASE_A, "Fictional case Fig01")
        self.store.add_case(CASE_B, "Fictional case Fig02")
        report = ("\n".join([
            "OI-SYNTHETIC-REPORT/1", f"Patient: {CASE_A}",
            "Document: FIG01-PATH", "Type: pathology",
            "Event-Date: 2026-07-01", "Issued-At: 2026-07-03",
            "Specimen: FIG01-SPECIMEN",
            "Finding: fig01-marker|not-reported|Fictional Fig01 marker was not tested in this specimen.",
        ]) + "\n").encode("utf-8")
        self.store.import_report(CASE_A, report)
        self.store.create_account(CLINICIAN, "Fictional demo navigator", "clinician", PASSWORD)
        self.store.create_account(OPERATOR, "Fictional demo operator", "operator", PASSWORD)
        self.store.create_account(AUDITOR, "Fictional auditor", "auditor", PASSWORD)
        self.store.create_account(PATIENT, "Fictional patient", "patient", PASSWORD,
                                  own_case_id=CASE_A)
        self.store.create_grant(CLINICIAN, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        self.store.create_grant(OPERATOR, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        self.store.create_grant(PATIENT, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        bound = type("BoundHandlerForAccessLogTests", (Handler,), {"db_path": self.db_path})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.store.close()
        self.tmp.cleanup()

    def raw(self, path, data=None, headers=None):
        values = dict(headers or {})
        if data is not None:
            values["Content-Type"] = "application/json"
            values["Origin"] = f"http://127.0.0.1:{self.port}"
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=values)
        try:
            with urlopen(req, timeout=5) as response:
                return (response.status, response.headers.get("Set-Cookie"),
                        json.loads(response.read()))
        except HTTPError as err:
            return err.code, err.headers.get("Set-Cookie"), json.loads(err.read())

    def signin(self, account_id, password=PASSWORD):
        status, cookie, body = self.raw(
            "/api/auth/sign-in", {"account_id": account_id, "password": password})
        self.assertEqual(status, 200, body)
        return cookie.split(";", 1)[0]

    def request(self, path, data=None, cookie=None, actor=None):
        headers = {}
        if cookie is not None:
            headers["Cookie"] = cookie
        if actor is not None:
            headers[FICTIONAL_ACTOR_HEADER] = actor
        status, _, body = self.raw(path, data, headers)
        return status, body

    def test_operator_and_auditor_read_log_clinician_patient_denied(self):
        # Generate traffic: one allowed read, one denied cross-case read.
        clinician = self.signin(CLINICIAN)
        status, _ = self.request(f"/api/cases/{CASE_A}/state", cookie=clinician)
        self.assertEqual(status, 200)
        status, _ = self.request(f"/api/cases/{CASE_B}/state", cookie=clinician)
        self.assertEqual(status, 403)
        operator = self.signin(OPERATOR)
        status, body = self.request(f"/api/cases/{CASE_A}/access-log", cookie=operator)
        self.assertEqual(status, 200)
        rows = body["access_log"]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(set(row),
                             {"id", "actor", "case_id", "route", "result", "occurred_at"})
            self.assertIn(row["result"], ("allowed", "denied"))
            self.assertEqual(row["case_id"], CASE_A)
        self.assertIn("allowed", {r["result"] for r in rows})
        self.assertIn(CLINICIAN, {r["actor"] for r in rows})
        # No source text in the log.
        self.assertNotIn("Fictional Fig01 marker was not tested", json.dumps(rows))
        # The denied cross-case read is logged under the requested case.
        status, body = self.request(f"/api/cases/{CASE_B}/access-log", cookie=operator)
        self.assertEqual(status, 200)
        rows_b = body["access_log"]
        self.assertIn("denied", {r["result"] for r in rows_b})
        self.assertTrue(all(r["case_id"] == CASE_B for r in rows_b))
        self.assertIn(CLINICIAN, {r["actor"] for r in rows_b})
        # Auditor reads without any grant; clinician and patient cannot.
        auditor = self.signin(AUDITOR)
        status, _ = self.request(f"/api/cases/{CASE_A}/access-log", cookie=auditor)
        self.assertEqual(status, 200)
        status, body = self.request(f"/api/cases/{CASE_A}/access-log", cookie=clinician)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        patient = self.signin(PATIENT)
        status, body = self.request(f"/api/cases/{CASE_A}/access-log", cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        # The transitional header is not a session: header-only requests
        # are 401 here, never a role decision.
        status, body = self.request(f"/api/cases/{CASE_A}/access-log", actor=CLINICIAN)
        self.assertEqual(status, 401)
        self.assertEqual(body, {"error": AUTH_REQUIRED_MESSAGE})
        # Unsigned-in requests are 401.
        status, body = self.request(f"/api/cases/{CASE_A}/access-log")
        self.assertEqual(status, 401)
        self.assertEqual(body, {"error": AUTH_REQUIRED_MESSAGE})

    def test_unknown_case_still_422(self):
        operator = self.signin(OPERATOR)
        status, body = self.request("/api/cases/CASE-NOPE/access-log", cookie=operator)
        self.assertEqual(status, 422)
        self.assertEqual(body, {"error": "Unknown case"})


if __name__ == "__main__":
    unittest.main()
