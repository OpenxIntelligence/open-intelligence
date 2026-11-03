"""Local workspace request boundary regressions, independently fictional only.

This guards the existing loopback-only Handler/WorkspaceHandler integration:
a malicious Host or cross-site browser request cannot read the workspace or
create/import a fictional case. These checks are NOT production auth/CSRF
control, verified patient consent, or PHI readiness.
"""
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_workspace_start_http import WorkspaceStartHttpTests


class WorkspaceLoopbackBoundaryTests(unittest.TestCase):
    setUp = WorkspaceStartHttpTests.setUp
    stop = WorkspaceStartHttpTests.stop

    def check_request(self, path, *, payload=None, headers=None):
        request_headers = dict(headers or {})
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(self.url + path, data=data, headers=request_headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status
        except HTTPError as error:
            error.read()
            return error.code

    def test_host_rebinding_cannot_read_workspace_or_source_api(self):
        self.assertEqual(self.check_request("/", headers={"Host": "attacker.invalid"}), 403)
        self.assertEqual(self.check_request(
            "/api/cases", headers={"Host": "attacker.invalid"}), 403)
        self.assertEqual(self.check_request(
            "/composer.js", headers={"Host": "attacker.invalid"}), 403)
        self.assertEqual(self.check_request(
            "/workspace-entry.js", headers={"Host": "attacker.invalid"}), 403)

    def test_foreign_origin_cannot_create_case_even_with_loopback_host(self):
        self.assertEqual(self.check_request(
            "/api/cases", payload={
                "case_id": "CASE-START", "label": "Fictional case Start"
            }, headers={"Origin": "https://attacker.invalid"}), 403)
        self.assertEqual(WorkspaceStartHttpTests.read(self, "/api/cases"), [])

    def test_cross_site_fetch_metadata_cannot_create_case_without_origin(self):
        self.assertEqual(self.check_request(
            "/api/cases", payload={
                "case_id": "CASE-START", "label": "Fictional case Start"
            }, headers={"Sec-Fetch-Site": "cross-site"}), 403)
        self.assertEqual(WorkspaceStartHttpTests.read(self, "/api/cases"), [])

    def test_rebinding_cannot_write_even_with_matching_origin(self):
        self.assertEqual(self.check_request(
            "/api/cases", payload={
                "case_id": "CASE-START", "label": "Fictional case Start"
            }, headers={
                "Host": "attacker.invalid",
                "Origin": f"http://127.0.0.1:{self.server.server_port}",
            }), 403)
        self.assertEqual(WorkspaceStartHttpTests.read(self, "/api/cases"), [])


if __name__ == "__main__":
    unittest.main()
