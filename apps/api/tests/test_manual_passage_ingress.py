"""Bound synthetic reference commands before the downstream JSON parser runs."""

import asyncio
import json
import unittest

from oi_api.request_limits import PatientRequestLimit


PATH = ("/v1/patients/PAT-FICTION/cases/CASE-FICTION/questions/"
        "QUESTION-" + "A" * 32 + "/manual-passages")


class ManualPassageIngressTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, chunks, headers=(), *, stall=False, path=PATH):
        sent, delivered = [], []
        messages = iter(chunks)
        reads = 0

        async def receive():
            nonlocal reads
            reads += 1
            if stall:
                await asyncio.sleep(6)
            return next(messages)

        async def downstream(scope, receive, send):
            delivered.append(await receive())

        async def send(message):
            sent.append(message)

        await PatientRequestLimit(downstream)({
            "type": "http", "method": "POST", "path": path,
            "headers": list(headers),
        }, receive, send)
        return sent, delivered, reads

    def assert_rejected(self, sent, delivered, status):
        self.assertEqual(len(delivered), 0, "the JSON parser must never see rejected input")
        self.assertEqual(sent[0]["status"], status)
        self.assertIn((b"cache-control", b"no-store"), sent[0]["headers"])
        self.assertIn((b"connection", b"close"), sent[0]["headers"])

    async def test_declared_oversize_rejects_without_reading_the_body(self):
        sent, delivered, reads = await self.exercise([], [(b"content-length", b"16385")])
        self.assert_rejected(sent, delivered, 413)
        self.assertEqual(reads, 0)

    async def test_chunked_and_underdeclared_oversize_reject_before_parsing(self):
        for headers in ([], [(b"content-length", b"1")]):
            with self.subTest(headers=headers):
                sent, delivered, reads = await self.exercise([
                    {"type": "http.request", "body": b"x" * 8192, "more_body": True},
                    {"type": "http.request", "body": b"x" * 8193, "more_body": False},
                ], headers)
                self.assert_rejected(sent, delivered, 413)
                self.assertEqual(reads, 2)

    async def test_slow_body_is_rejected_before_parsing(self):
        sent, delivered, _ = await self.exercise([
            {"type": "http.request", "body": b"{}", "more_body": False},
        ], stall=True)
        self.assert_rejected(sent, delivered, 408)

    async def test_disconnected_body_never_reaches_parser(self):
        sent, delivered, _ = await self.exercise([{"type": "http.disconnect"}])
        self.assertEqual((sent, delivered), ([], []))

    async def test_invalid_length_is_rejected_without_reading(self):
        for length in (b"-1", b"not-a-length"):
            with self.subTest(length=length):
                sent, delivered, reads = await self.exercise([], [(b"content-length", length)])
                self.assert_rejected(sent, delivered, 400)
                self.assertEqual(reads, 0)

    async def test_twenty_maximal_references_are_delivered_unchanged_once(self):
        payload = {
            "synthetic": True, "request_key": "F" * 128,
            "expected_context_sha256": "a" * 64,
            "references": [{
                "source_id": "SRC-" + f"{i:032X}",
                "annotation_revision_id": "ANN-" + "B" * 32,
                "selection_key": "a" * 60, "anchor_sha256": "b" * 64,
            } for i in range(20)],
        }
        body = json.dumps(payload).encode()
        self.assertLess(len(body), 16384)
        sent, delivered, reads = await self.exercise([
            {"type": "http.request", "body": body[:100], "more_body": True},
            {"type": "http.request", "body": body[100:], "more_body": False},
        ])
        self.assertEqual(sent, [])
        self.assertEqual(delivered, [{"type": "http.request", "body": body, "more_body": False}])
        self.assertEqual(reads, 2)

    async def test_every_registered_patient_post_is_bounded_before_parsing(self):
        from oi_api.app import create_app
        from oi_api.config import Settings
        app = create_app(Settings(database_url=None))
        paths = [path for path, operations in app.openapi()["paths"].items()
                 if "post" in operations and path.startswith("/v1/patients")]
        self.assertGreaterEqual(len(paths), 24)
        for path in paths:
            with self.subTest(path=path):
                sent, delivered, reads = await self.exercise(
                    [{"type": "http.request", "body": b"{}", "more_body": False}],
                    [(b"content-length", b"2097153")], path=path)
                self.assert_rejected(sent, delivered, 413)
                self.assertEqual(reads, 0)

    async def test_laboratory_envelope_preserves_maximum_escaped_string(self):
        # JSON may escape each non-BMP code point as two six-byte surrogates.
        body = json.dumps({"synthetic": True, "bundle_json": "\U0001f9ea" * 65536}).encode()
        sent, delivered, reads = await self.exercise([
            {"type": "http.request", "body": body, "more_body": False},
        ], path="/v1/patients/PAT-FICTION/cases/CASE-FICTION/laboratory/fhir-r4/preview")
        self.assertEqual(sent, [])
        self.assertEqual(delivered[0]["body"], body)
        self.assertEqual(reads, 1)

    async def test_preview_and_receipt_reject_chunked_excess(self):
        for path, limit in (
            ("/v1/patients/PAT-FICTION/record-requests/REQ-FICTION/receive", 16384),
            ("/v1/patients/PAT-FICTION/cases/CASE-FICTION/laboratory/fhir-r4/preview", 800000),
        ):
            with self.subTest(path=path):
                sent, delivered, _ = await self.exercise([
                    {"type": "http.request", "body": b"x" * limit, "more_body": True},
                    {"type": "http.request", "body": b"x", "more_body": False},
                ], path=path)
                self.assert_rejected(sent, delivered, 413)
