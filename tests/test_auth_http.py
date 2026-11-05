"""Slice 1 auth HTTP routes: sign-in/out, sessions, gate rewire, accounts.

Fictional actors/cases only. The transitional header path is covered here
too: the seeded demo header still works, any other header value does not.
"""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import (
    AUTH_REQUIRED_MESSAGE,
    DEMO_ACTOR,
    DEMO_OPERATOR,
    FICTIONAL_ACTOR_HEADER,
    FICTIONAL_ACTOR_PURPOSE,
    GRANT_DENIAL_MESSAGE,
    ROLE_DENIAL_MESSAGE,
    Handler,
)

OPERATOR = DEMO_OPERATOR
CLINICIAN = DEMO_ACTOR
PATIENT = "FICTIONAL-PATIENT-A"
AUDITOR = "FICTIONAL-AUDITOR-A"
UNKNOWN_ACTOR = "FICTIONAL-NOBODY"
CASE_A = "CASE-FIG-01"
CASE_B = "CASE-FIG-02"
PASSWORD = "fictional-demo-1"
PURPOSE = FICTIONAL_ACTOR_PURPOSE


class AuthHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "auth.sqlite")
        self.store = CaseStore(self.db_path)
        self.store.add_case(CASE_A, "Fictional case Fig01")
        self.store.add_case(CASE_B, "Fictional case Fig02")
        self.store.create_account(CLINICIAN, "Fictional demo navigator", "clinician", PASSWORD)
        self.store.create_account(OPERATOR, "Fictional demo operator", "operator", PASSWORD)
        self.store.create_account(AUDITOR, "Fictional auditor", "auditor", PASSWORD)
        self.store.create_account(PATIENT, "Fictional patient", "patient", PASSWORD,
                                  own_case_id=CASE_A)
        self.store.create_grant(CLINICIAN, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        self.store.create_grant(CLINICIAN, CASE_B, PURPOSE, "2020-01-01", "2999-12-31")
        self.store.create_grant(OPERATOR, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        self.store.create_grant(PATIENT, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        bound = type("BoundHandlerForAuthTests", (Handler,), {"db_path": self.db_path})
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
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Max-Age=86400", cookie)
        self.assertEqual(body["account_id"], account_id)
        self.assertNotIn("password_hash", body)
        return cookie.split(";", 1)[0]

    def request(self, path, data=None, cookie=None, actor=None):
        headers = {}
        if cookie is not None:
            headers["Cookie"] = cookie
        if actor is not None:
            headers[FICTIONAL_ACTOR_HEADER] = actor
        status, _, body = self.raw(path, data, headers)
        return status, body

    def test_sign_in_success_wrong_password_unknown_and_passwordless(self):
        cookie = self.signin(CLINICIAN)
        self.assertTrue(cookie.startswith("oi_session="))
        status, body = self.request("/api/auth/session", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body["account_id"], CLINICIAN)
        self.assertEqual(body["role"], "clinician")
        for account_id, password in (
                (CLINICIAN, "wrong-password"), (UNKNOWN_ACTOR, PASSWORD),
                (CLINICIAN, ""), ("", PASSWORD)):
            with self.subTest(account_id=account_id):
                status, _, body = self.raw(
                    "/api/auth/sign-in", {"account_id": account_id, "password": password})
                self.assertEqual(status, 401)
                self.assertEqual(body, {"error": "Invalid account or password"})
        # Passwordless account cannot sign in.
        self.store.create_account("FICTIONAL-NOPASS-A", "No password", "clinician")
        status, _, body = self.raw(
            "/api/auth/sign-in",
            {"account_id": "FICTIONAL-NOPASS-A", "password": PASSWORD})
        self.assertEqual(status, 401)
        # Disabled account cannot sign in.
        self.store.set_account_status(CLINICIAN, "disabled")
        status, _, body = self.raw(
            "/api/auth/sign-in", {"account_id": CLINICIAN, "password": PASSWORD})
        self.assertEqual(status, 401)

    def test_sign_out_revokes_session_and_clears_cookie(self):
        cookie = self.signin(CLINICIAN)
        status, body = self.request("/api/auth/session", cookie=cookie)
        self.assertEqual(status, 200)
        status, set_cookie, body = self.raw("/api/auth/sign-out", {}, {"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"result": "signed_out"})
        self.assertIn("Max-Age=0", set_cookie)
        status, body = self.request("/api/auth/session", cookie=cookie)
        self.assertEqual(status, 401)
        self.assertEqual(body, {"error": AUTH_REQUIRED_MESSAGE})

    def test_session_endpoint_requires_sign_in(self):
        status, body = self.request("/api/auth/session")
        self.assertEqual(status, 401)
        status, body = self.request("/api/auth/session", actor=UNKNOWN_ACTOR)
        self.assertEqual(status, 401)

    def test_case_gate_uses_session_account_and_role(self):
        clinician = self.signin(CLINICIAN)
        status, body = self.request(f"/api/cases/{CASE_A}/state", cookie=clinician)
        self.assertEqual(status, 200)
        # Patient reads only their own bound case.
        patient = self.signin(PATIENT)
        status, body = self.request(f"/api/cases/{CASE_A}/state", cookie=patient)
        self.assertEqual(status, 200)
        status, body = self.request(f"/api/cases/{CASE_B}/state", cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Patient writes are denied by role even on their own case.
        status, body = self.request(
            f"/api/cases/{CASE_A}/questions",
            {"question": "Which fictional Fig01 marker needs review next?"},
            cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        # Clinician writes on a granted case.
        status, body = self.request(
            f"/api/cases/{CASE_A}/questions",
            {"question": "Which fictional Fig01 marker needs review next?"},
            cookie=clinician)
        self.assertEqual(status, 201)
        # Auditor holds no case grants: the grant gate denies case routes.
        auditor = self.signin(AUDITOR)
        status, body = self.request(f"/api/cases/{CASE_A}/state", cookie=auditor)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Unauthenticated case routes are denied.
        status, body = self.request(f"/api/cases/{CASE_A}/state")
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_case_list_is_grant_filtered_and_patient_scoped(self):
        clinician = self.signin(CLINICIAN)
        status, cases = self.request("/api/cases", cookie=clinician)
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in cases], [CASE_A, CASE_B])
        patient = self.signin(PATIENT)
        status, cases = self.request("/api/cases", cookie=patient)
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in cases], [CASE_A])
        status, body = self.request("/api/cases")
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_transitional_header_demo_only_and_session_wins(self):
        # The seeded demo header still works during the transition.
        status, body = self.request(f"/api/cases/{CASE_A}/state", actor=CLINICIAN)
        self.assertEqual(status, 200)
        # Any other header value is not an identity.
        for actor in (UNKNOWN_ACTOR, PATIENT, AUDITOR, OPERATOR, "not-valid!"):
            with self.subTest(actor=actor):
                status, body = self.request(f"/api/cases/{CASE_A}/state", actor=actor)
                self.assertEqual(status, 403)
                self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # A session wins over a simultaneous header: a patient session plus
        # the demo header still cannot write.
        patient = self.signin(PATIENT)
        status, body = self.request(
            f"/api/cases/{CASE_A}/questions",
            {"question": "Which fictional Fig01 marker needs review next?"},
            cookie=patient, actor=CLINICIAN)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})

    def test_operator_account_routes_and_role_enforcement(self):
        operator = self.signin(OPERATOR)
        status, body = self.request(
            "/api/auth/accounts",
            {"account_id": "FICTIONAL-CLINIC-B", "display_name": "Second clinician",
             "role": "clinician", "password": PASSWORD},
            cookie=operator)
        self.assertEqual(status, 201, body)
        self.assertEqual(body["account_id"], "FICTIONAL-CLINIC-B")
        self.assertNotIn("password_hash", body)
        status, body = self.request("/api/auth/accounts", cookie=operator)
        self.assertEqual(status, 200)
        self.assertIn("FICTIONAL-CLINIC-B", [a["account_id"] for a in body["accounts"]])
        status, body = self.request(
            "/api/auth/accounts/FICTIONAL-CLINIC-B/disable", {}, cookie=operator)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "disabled")
        status, _, _ = self.raw(
            "/api/auth/sign-in",
            {"account_id": "FICTIONAL-CLINIC-B", "password": PASSWORD})
        self.assertEqual(status, 401)
        status, body = self.request(
            "/api/auth/accounts/FICTIONAL-CLINIC-B/enable", {}, cookie=operator)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "active")
        status, body = self.request(
            "/api/auth/accounts/FICTIONAL-CLINIC-B/set-password",
            {"password": "fictional-demo-2"}, cookie=operator)
        self.assertEqual(status, 200)
        status, _, _ = self.raw(
            "/api/auth/sign-in",
            {"account_id": "FICTIONAL-CLINIC-B", "password": "fictional-demo-2"})
        self.assertEqual(status, 200)
        # Invalid account data stays 422; unknown account stays 422.
        status, body = self.request(
            "/api/auth/accounts",
            {"account_id": "FICTIONAL-CLINIC-B", "display_name": "Dup",
             "role": "clinician", "password": PASSWORD},
            cookie=operator)
        self.assertEqual(status, 422)
        status, body = self.request(
            "/api/auth/accounts/FICTIONAL-NOBODY/disable", {}, cookie=operator)
        self.assertEqual(status, 422)
        # Non-operator roles cannot use account routes; signed-out cannot.
        clinician = self.signin(CLINICIAN)
        status, body = self.request("/api/auth/accounts", cookie=clinician)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        status, body = self.request(
            "/api/auth/accounts",
            {"account_id": "FICTIONAL-X-A", "display_name": "X",
             "role": "auditor", "password": PASSWORD},
            cookie=clinician)
        self.assertEqual(status, 403)
        status, body = self.request("/api/auth/accounts")
        self.assertEqual(status, 401)
        self.assertEqual(body, {"error": AUTH_REQUIRED_MESSAGE})

    def test_unknown_case_still_422_for_signed_in_and_signed_out(self):
        clinician = self.signin(CLINICIAN)
        for cookie in (clinician, None):
            with self.subTest(signed_in=cookie is not None):
                status, body = self.request("/api/cases/CASE-NOPE/state", cookie=cookie)
                self.assertEqual(status, 422)
                self.assertEqual(body, {"error": "Unknown case"})


if __name__ == "__main__":
    unittest.main()
