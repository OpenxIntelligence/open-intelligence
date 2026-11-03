"""Real local HTTP PDF intake, original download and failure isolation."""
from __future__ import annotations

import base64
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from open_intelligence.__main__ import Handler
from open_intelligence.store import CaseStore
from pdf_fixtures import encrypted_pdf, streams_pdf, text_pdf


class PdfDocumentIntakeHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "fictional-pdf-http.sqlite")
        store = CaseStore(self.db_path)
        try:
            store.add_case("CASE-ALPHA", "Independent fictional Alpha")
            store.add_case("CASE-BETA", "Independent fictional Beta")
        finally:
            store.close()
        self.raw = text_pdf([["Independent fictional PDF"], ["Marker P was not assessed."]])
        self.start_server()
        status, self.preview, _ = self.request("/api/cases/CASE-ALPHA/documents/preview", self.preview_payload())
        self.assertEqual(status, 200, self.preview)

    def start_server(self):
        handler = type("PdfIntakeHandler", (Handler,), {
            "db_path": self.db_path, "log_message": lambda *_args: None})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)
        self.thread.start()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def tearDown(self):
        self.stop_server()
        self.temp.cleanup()

    def request(self, path, payload=None, headers=None):
        headers = dict(headers or {})
        body = None if payload is None else json.dumps(payload).encode()
        if body is not None:
            headers.setdefault("Content-Type", "application/json")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            conn.request("GET" if body is None else "POST", path, body=body, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            result = json.loads(raw) if "application/json" in response.getheader("Content-Type", "") else raw
            return response.status, result, dict(response.getheaders())
        finally:
            conn.close()

    def ledger(self):
        store = CaseStore(self.db_path)
        try:
            return tuple(store.db.iterdump())
        finally:
            store.close()

    def preview_payload(self, raw=None, filename="fictional.pdf"):
        return {"filename": filename, "content_base64": base64.b64encode(self.raw if raw is None else raw).decode()}

    def commit_payload(self):
        return {**self.preview_payload(), "expected_sha256": self.preview["sha256"],
                "expected_extraction_sha256": self.preview["extraction_sha256"], "confirmed_case_id": "CASE-ALPHA",
                "metadata": {"document_id": "PDF-HTTP", "kind": "pathology", "event_date": "2026-07-01",
                             "issued_at": "2026-07-02", "manual_transcription_confirmed": True},
                "findings": [{"key": "marker-p", "state": "not-assessed", "quote": "Marker P was not assessed.", "line": 2}]}

    def commit(self):
        status, result, _ = self.request("/api/cases/CASE-ALPHA/documents", self.commit_payload())
        self.assertEqual(status, 200, result)
        self.assertEqual(result["result"], "imported")
        return result["source_id"]

    def test_pdf_preview_is_read_only_and_pages_are_separate_from_original_hash(self):
        before = self.ledger()
        status, preview, _ = self.request("/api/cases/CASE-ALPHA/documents/preview", self.preview_payload())
        self.assertEqual(status, 200)
        self.assertEqual(preview["case_id"], "CASE-ALPHA")
        self.assertEqual(preview["media_type"], "application/pdf")
        self.assertEqual(preview["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(preview["lines"][1], {"line": 2, "text": "Marker P was not assessed.", "page": 2, "page_line": 1})
        self.assertEqual(preview["clinical_review"], "not_performed")
        self.assertNotEqual(preview["sha256"], preview["extraction_sha256"])
        self.assertEqual(self.ledger(), before)

    def test_download_is_exact_pdf_and_readable_route_is_labeled_after_server_restart(self):
        source_id = self.commit()
        before = self.ledger()
        self.stop_server()
        self.start_server()
        status, raw, headers = self.request(f"/api/cases/CASE-ALPHA/sources/{source_id}/download")
        self.assertEqual(status, 200)
        self.assertEqual(raw, self.raw)
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(int(headers["Content-Length"]), len(self.raw))
        self.assertEqual(headers["Content-Disposition"], 'attachment; filename="fictional.pdf"')
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        status, view, _ = self.request(f"/api/cases/CASE-ALPHA/sources/{source_id}")
        self.assertEqual(status, 200)
        self.assertEqual(view["text_origin"], "pdf_extraction")
        self.assertEqual(view["text"], "Independent fictional PDF\nMarker P was not assessed.")
        self.assertEqual(view["extraction_sha256"], self.preview["extraction_sha256"])
        self.assertEqual(view["original_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(view["lines"][1]["page"], 2)
        self.assertEqual(self.ledger(), before)

    def test_missing_or_changed_preview_identity_and_wrong_case_fail_without_writes(self):
        before = self.ledger()
        for field in ("expected_sha256", "expected_extraction_sha256", "confirmed_case_id"):
            for missing in (True, False):
                with self.subTest(field=field, missing=missing):
                    payload = self.commit_payload()
                    if missing:
                        del payload[field]
                    else:
                        payload[field] = "CASE-BETA" if field == "confirmed_case_id" else "0" * 64
                    status, _, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
                    self.assertEqual(status, 422)
                    self.assertEqual(self.ledger(), before)

    def test_client_page_text_fields_and_forged_passages_cannot_override_server_extraction(self):
        before = self.ledger()
        variants = []
        for field in ("pages", "text", "extractor", "media_type"):
            payload = self.commit_payload()
            payload[field] = "client supplied"
            variants.append(payload)
        for fields in ({"quote": "A fabricated negative finding."}, {"line": 1}, {"page": 1}, {"page_line": 1}):
            payload = self.commit_payload()
            payload["findings"][0].update(fields)
            variants.append(payload)
        for payload in variants:
            with self.subTest(payload=payload):
                status, _, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_duplicate_retry_does_not_rewrite_review_or_add_events(self):
        source_id = self.commit()
        before = self.ledger()
        payload = self.commit_payload()
        payload["filename"] = "renamed.pdf"
        status, result, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
        self.assertEqual(status, 200)
        self.assertEqual(result, {"result": "duplicate", "source_id": source_id, "version": 1})
        self.assertEqual(self.ledger(), before)
        payload["findings"][0]["state"] = "negative"
        status, _, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_extraction_failure_creates_nothing_and_server_handles_next_valid_file(self):
        before = self.ledger()
        for raw in (encrypted_pdf(), streams_pdf([b"q 100 0 0 100 36 600 cm /Im0 Do Q"], image_pages=(0,))):
            status, result, _ = self.request("/api/cases/CASE-ALPHA/documents/preview", self.preview_payload(raw))
            self.assertEqual(status, 422, result)
            self.assertEqual(self.ledger(), before)
        self.assertGreater(self.commit(), 0)

    def test_same_case_read_guards_and_host_origin_policy_apply_to_pdf_routes(self):
        source_id = self.commit()
        before = self.ledger()
        for suffix in ("", "/download"):
            status, result, _ = self.request(f"/api/cases/CASE-BETA/sources/{source_id}{suffix}")
            self.assertEqual(status, 422)
            self.assertNotIn("Marker P", json.dumps(result))
        status, _, _ = self.request("/api/cases/CASE-UNKNOWN/documents/preview", self.preview_payload())
        self.assertEqual(status, 422)
        for route, payload, headers in (
            ("/api/cases/CASE-ALPHA/documents/preview", self.preview_payload(), {"Origin": "https://untrusted.example"}),
            ("/api/cases/CASE-ALPHA/documents", self.commit_payload(), {"Sec-Fetch-Site": "cross-site"}),
            (f"/api/cases/CASE-ALPHA/sources/{source_id}/download", None, {"Host": f"untrusted.example:{self.port}"}),
        ):
            status, _, _ = self.request(route, payload, headers)
            self.assertEqual(status, 403)
        self.assertEqual(self.ledger(), before)

    def test_text_request_shape_remains_unchanged_and_rejects_pdf_only_confirmation_field(self):
        raw = b"\xef\xbb\xbfIndependent fictional text\r\nReview pending.\r\n"
        payload = self.commit_payload()
        payload.update(self.preview_payload(raw, "fictional.txt"))
        payload["expected_sha256"] = hashlib.sha256(raw).hexdigest()
        payload["findings"] = [{"key": "review", "state": "pending", "quote": "Review pending.", "line": 2}]
        before = self.ledger()
        status, _, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)
        del payload["expected_extraction_sha256"]
        status, saved, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
        self.assertEqual(status, 200, saved)
        status, original, headers = self.request(f"/api/cases/CASE-ALPHA/sources/{saved['source_id']}/download")
        self.assertEqual(status, 200)
        self.assertEqual(original, raw)
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        status, view, _ = self.request(f"/api/cases/CASE-ALPHA/sources/{saved['source_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(view["text"].encode(), raw)
        self.assertEqual(view["text_origin"], "original")
        self.assertNotIn("extraction_sha256", view)


if __name__ == "__main__":
    unittest.main()
