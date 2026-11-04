"""Synthetic question/evidence boundary and actual PostgreSQL acceptance.

These tests exercise the same canonical identity/source/question API; they do
not create a second case chart or infer scientific support from metadata.
"""
import asyncio
import json
import unittest

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.request_limits import PatientRequestLimit
from test_patients import request

PREFIX = "/v1/patients/PAT-FICTION/cases/CASE-ALPHA/questions/QUESTION-" + "A" * 32


class EvidenceBoundaryTests(unittest.TestCase):
    def test_evidence_operations_require_authentication_before_database_access(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            for suffix, body in (("/evidence-search", {"synthetic": True, "query": "fictional"}),
                                 ("/evidence-links", None),
                                 ("/evidence-links", {"synthetic": True})):
                with self.subTest(suffix=suffix, write=body is not None):
                    code, data, headers = request(base, PREFIX + suffix, body=body)
                    self.assertEqual(code, 401)
                    self.assertEqual(headers.get("Cache-Control"), "no-store")
                    self.assertNotIn("FICT-", json.dumps(data))

    def test_evidence_commands_bound_chunked_and_declared_payloads(self):
        async def exercise(route, declared):
            sent = []
            async def downstream(scope, receive, send):
                sent.append("unbounded")
            chunks = iter([
                {"type": "http.request", "body": b"x" * 9000, "more_body": True},
                {"type": "http.request", "body": b"x" * 9000, "more_body": False},
            ])
            async def receive():
                return next(chunks)
            async def send(message):
                sent.append(message)
            await PatientRequestLimit(downstream)({
                "type": "http", "method": "POST", "path": route,
                "headers": [(b"content-length", b"18000")] if declared else [],
            }, receive, send)
            self.assertNotIn("unbounded", sent)
            self.assertEqual(sent[0]["status"], 413)
            self.assertEqual(json.loads(sent[1]["body"]), {"detail": "Request body too large"})
        for suffix in ("/evidence-search", "/evidence-links"):
            for declared in (True, False):
                with self.subTest(suffix=suffix, declared=declared):
                    asyncio.run(exercise(PREFIX + suffix, declared))
