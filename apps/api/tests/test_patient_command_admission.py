"""Transport and public API contracts for the shared fictional patient command budget."""

import asyncio
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from oi_api.app import create_app
from oi_api.config import ConfigurationError, Settings
from oi_api.request_limits import PatientRequestLimit
from http_support import running_server


async def call(app, method="POST", path="/v1/patients", headers=(), chunks=(b"{}",)):
    messages = iter(chunks)
    sent = []
    reads = []

    async def receive():
        chunk = next(messages)
        reads.append(chunk)
        return {"type": "http.request", "body": chunk, "more_body": len(reads) < len(chunks)}

    async def send(message):
        sent.append(message)

    await app({"type": "http", "method": method, "path": path, "headers": list(headers)}, receive, send)
    return sent, reads


async def accepted(scope, receive, send):
    await send({"type": "http.response.start", "status": 204, "headers": []})


class AdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_routes_inherit_a_limit_for_every_command_verb(self):
        app = PatientRequestLimit(accepted)
        for verb in ("POST", "PATCH", "PUT", "DELETE"):
            with self.subTest(verb=verb):
                sent, reads = await call(app, verb, "/v1/patients/FICTIONAL/future-module",
                                         [(b"content-length", b"16385")])
                self.assertEqual((sent[0]["status"], reads), (413, []))

    async def test_unknown_paths_cannot_borrow_a_larger_upload_allowance(self):
        app = PatientRequestLimit(accepted)
        for path in ("future/documents", "future/sources", "future/questions/Q/evidence",
                     "cases/C/documents/preview/other"):
            with self.subTest(path=path):
                sent, reads = await call(app, path="/v1/patients/P/" + path, chunks=(b"a" * 16384, b"b"))
                self.assertEqual(sent[0]["status"], 413)
                self.assertEqual(len(reads), 2)

    async def test_large_envelopes_are_specific_to_their_import_operation(self):
        app = PatientRequestLimit(accepted)
        prefix = "/v1/patients/P/cases/C/"
        for suffix, limit in (("documents", 262144), ("documents/preview", 262144),
                              ("documents/D/annotations", 262144), ("questions/Q/evidence", 210000),
                              ("sources", 72000), ("sources/S/images", 2097152),
                              ("laboratory/fhir-r4/sources", 800000)):
            with self.subTest(suffix=suffix):
                path = prefix + suffix
                sent, _ = await call(app, path=path, chunks=(b"a" * limit,))
                self.assertEqual(sent[0]["status"], 204)
                sent, _ = await call(app, path=path, chunks=(b"a" * limit, b"b"))
                self.assertEqual(sent[0]["status"], 413)
                sent, _ = await call(app, method="PUT", path=path, chunks=(b"a" * 16385,))
                self.assertEqual(sent[0]["status"], 413)

    async def test_fixed_burst_and_refill_are_shared_across_paths_and_credentials(self):
        app = PatientRequestLimit(accepted, commands_per_minute=2)
        with patch("oi_api.request_limits.monotonic", return_value=10.0) as clock:
            for auth in (b"a", b"b"):
                sent, _ = await call(app, headers=[(b"authorization", auth)])
                self.assertEqual(sent[0]["status"], 204)
            for now, wait in ((10, 30), (10.2, 30), (39.9, 1)):
                clock.return_value = now
                sent, reads = await call(app, "PATCH", "/v1/patients/OTHER/future",
                                         [(b"x-forwarded-for", b"192.0.2.1")])
                self.assertEqual((sent[0]["status"], reads), (429, []))
                headers = dict(sent[0]["headers"])
                self.assertEqual(headers[b"retry-after"], str(wait).encode())
                self.assertEqual(headers[b"cache-control"], b"no-store")
            clock.return_value = 40.01
            sent, _ = await call(app)
            self.assertEqual(sent[0]["status"], 204)
            clock.return_value = 4000
            burst = await asyncio.gather(*(call(app) for _ in range(12)))
            self.assertEqual(sum(sent[0]["status"] == 204 for sent, _ in burst), 2)

    async def test_denied_commands_do_not_block_reads_health_or_neighbor_prefixes(self):
        app = PatientRequestLimit(accepted, commands_per_minute=1)
        await call(app)
        for method, path in (("GET", "/v1/patients/P"), ("GET", "/health/ready"),
                             ("POST", "/v1/patients-extra"), ("OPTIONS", "/v1/patients")):
            sent, reads = await call(app, method, path)
            self.assertEqual((sent[0]["status"], reads), (204, []))
        sent, reads = await call(app)
        self.assertEqual((sent[0]["status"], reads), (429, []))

    async def test_ambiguous_or_invalid_content_length_fails_before_body_read(self):
        app = PatientRequestLimit(accepted)
        for values in ((b"1", b"2"), (b"+2",), (b"2_0",), (b"",)):
            with self.subTest(values=values):
                sent, reads = await call(app, headers=[(b"content-length", value) for value in values])
                self.assertEqual((sent[0]["status"], reads), (400, []))


class ApplicationTests(unittest.TestCase):
    def test_rate_configuration_is_bounded_and_errors_are_safe(self):
        for value in ("0", "-1", "60001", "credential-canary", "1.5"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as error:
                Settings.from_env({"OI_API_PATIENT_COMMANDS_PER_MINUTE": value})
            self.assertEqual(str(error.exception), "Invalid patient command rate limit")
        self.assertEqual(Settings.from_env({"OI_API_PATIENT_COMMANDS_PER_MINUTE": "37"})
                         .patient_commands_per_minute, 37)

    def test_real_http_preserves_auth_then_rejects_before_parsing(self):
        app = create_app(Settings.from_env({"OI_API_PATIENT_COMMANDS_PER_MINUTE": "1"}))
        opener = build_opener(ProxyHandler({}))
        with running_server(app) as base:
            def post(body):
                req = Request(base + "/v1/patients", data=body, headers={"Content-Type": "application/json"})
                with self.assertRaises(HTTPError) as caught:
                    opener.open(req, timeout=5)
                with caught.exception as response:
                    return response.code, json.load(response), response.headers
            self.assertEqual(post(b'{"synthetic":true,"request_key":"FICTIONAL"}')[0], 401)
            status, body, headers = post(b"invalid JSON")
            self.assertEqual(status, 429)
            self.assertEqual(body, {"detail": "Patient command rate limit reached"})
            self.assertTrue(1 <= int(headers["Retry-After"]) <= 60)
            self.assertEqual(headers["Cache-Control"], "no-store")
            with opener.open(base + "/health", timeout=5) as response:
                self.assertEqual(response.status, 200)

    def test_openapi_only_advertises_command_limit_on_patient_commands(self):
        schema = create_app(Settings()).openapi()
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                with self.subTest(path=path, method=method):
                    limited = path.startswith("/v1/patients") and method in {"post", "put", "patch", "delete"}
                    responses = operation["responses"]
                    self.assertEqual("429" in responses, limited)
                    if limited:
                        self.assertIn("Retry-After", responses["429"]["headers"])
