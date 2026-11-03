"""Real HTTP ingress limits for synthetic case-binding revocation.

These checks need no database: oversized and stalled bodies must be rejected
before JSON parsing, authentication or any patient/case transaction.
"""

import http.client
import json
import unittest

from oi_api.app import create_app
from oi_api.config import Settings

from http_support import running_server


class CaseBindingIngressTests(unittest.TestCase):
    path = "/v1/patients/PAT-SYNTHETIC/case-bindings/CASE-SYNTHETIC/revoke"

    def test_oversized_declared_revoke_body_is_rejected_before_parsing(self):
        body = json.dumps({"synthetic": True, "reason": "x" * 17_000}).encode()
        with running_server(create_app(Settings.from_env({}))) as base:
            client = http.client.HTTPConnection(base.removeprefix("http://"), timeout=7)
            try:
                client.request("POST", self.path, body=body,
                               headers={"Content-Type": "application/json"})
                response = client.getresponse()
                self.assertEqual(response.status, 413)
                self.assertEqual(json.loads(response.read()), {"detail": "Request body too large"})
                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                self.assertEqual(response.getheader("Connection"), "close")
            finally:
                client.close()

    def test_oversized_chunked_revoke_body_is_rejected_before_parsing(self):
        body = json.dumps({"synthetic": True, "reason": "x" * 17_000}).encode()
        chunks = [body[:8_000], body[8_000:16_000], body[16_000:]]
        with running_server(create_app(Settings.from_env({}))) as base:
            client = http.client.HTTPConnection(base.removeprefix("http://"), timeout=7)
            try:
                client.request("POST", self.path, body=iter(chunks), encode_chunked=True,
                               headers={"Content-Type": "application/json"})
                response = client.getresponse()
                self.assertEqual(response.status, 413)
                self.assertEqual(json.loads(response.read()), {"detail": "Request body too large"})
                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                self.assertEqual(response.getheader("Connection"), "close")
            finally:
                client.close()

    def test_stalled_revoke_body_times_out_without_waiting_for_completion(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            client = http.client.HTTPConnection(base.removeprefix("http://"), timeout=7)
            try:
                client.putrequest("POST", self.path)
                client.putheader("Content-Type", "application/json")
                client.putheader("Content-Length", "100")
                client.endheaders(b'{"synthetic":')
                try:
                    response = client.getresponse()
                except TimeoutError:
                    self.fail("Revocation waited beyond the five-second ingress deadline")
                self.assertEqual(response.status, 408)
                self.assertEqual(json.loads(response.read()), {"detail": "Request body timed out"})
                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                self.assertEqual(response.getheader("Connection"), "close")
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
