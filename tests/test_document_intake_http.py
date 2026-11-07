"""Bounded document upload/download through the real local HTTP boundary.

Inputs are independently authored fictional text. No provider, patient record,
external path or model service is used by these tests.
"""
from __future__ import annotations

import base64
import hashlib
from http.client import HTTPConnection, RemoteDisconnected
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from open_intelligence.__main__ import Handler, SYNTHETIC
from open_intelligence.store import CaseStore
from session_auth import signin_cookie


class DocumentIntakeHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "document-http.sqlite")
        store = CaseStore(self.db_path)
        try:
            store.add_case("CASE-ALPHA", "Independent fictional Alpha")
            store.add_case("CASE-BETA", "Independent fictional Beta")
            # B-01 actor-grant gate (merged after this slice was authored):
            # fresh cases carry no grant until one is recorded.
            store.create_grant("FICTIONAL-NAVIGATOR-A", "CASE-ALPHA",
                               "individual-access", "2020-01-01", "2999-12-31")
            store.create_grant("FICTIONAL-NAVIGATOR-A", "CASE-BETA",
                               "individual-access", "2020-01-01", "2999-12-31")
            # W1: the header path is gone; the demo account signs in.
            store.create_account("FICTIONAL-NAVIGATOR-A",
                                 "Fictional demo navigator", "clinician",
                                 "fictional-demo-1")
            self.legacy_raw = (SYNTHETIC / "alpha-imaging.txt").read_bytes()
            self.legacy_id = store.import_report("CASE-ALPHA", self.legacy_raw)["source_id"]
        finally:
            store.close()
        handler = type("DocumentIntakeHandler", (Handler,), {
            "db_path": self.db_path,
            "log_message": lambda *_args: None,
        })
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)
        self.thread.start()
        self._cookie = signin_cookie(self.port, "FICTIONAL-NAVIGATOR-A")
        self.raw = b"\xef\xbb\xbfFictional local note\r\nValue stable; review pending.\r\n"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path, payload=None, *, raw_body=None, headers=None):
        values = dict(headers or {})
        values.setdefault("Cookie", self._cookie)
        body = raw_body
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        if body is not None:
            values.setdefault("Content-Type", "application/json")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=8)
        try:
            conn.request("POST" if body is not None else "GET", path,
                         body=body, headers=values)
            response = conn.getresponse()
            contents = response.read()
            result = (json.loads(contents)
                      if "application/json" in response.getheader("Content-Type", "")
                      else contents)
            return response.status, result, dict(response.getheaders())
        finally:
            conn.close()

    def preview_payload(self, raw=None, filename="fictional-note.txt"):
        return {
            "filename": filename,
            "content_base64": base64.b64encode(self.raw if raw is None else raw).decode("ascii"),
        }

    def commit_payload(self):
        return {
            **self.preview_payload(),
            "metadata": {
                "document_id": "DOC-INTAKE",
                "kind": "clinical",
                "event_date": "2026-11-01",
                "issued_at": "2026-11-02",
                "manual_transcription_confirmed": True,
            },
            "findings": [{"key": "reported_value", "state": "reported",
                          "quote": "Value stable; review pending.", "line": 2}],
            "expected_sha256": hashlib.sha256(self.raw).hexdigest(),
            "confirmed_case_id": "CASE-ALPHA",
        }

    def ledger(self):
        # B-01 gate audit rows are not document writes: every gated case
        # route appends one access_log row even when the request is
        # rejected, so the no-write assertions below compare the dump
        # without access_log INSERTs. Source, annotation, receipt, and
        # quarantine rows are still compared exactly.
        store = CaseStore(self.db_path)
        try:
            return "\n".join(
                line for line in store.db.iterdump()
                if not line.startswith('INSERT INTO "access_log"'))
        finally:
            store.close()

    def commit(self):
        status, result, _ = self.request(
            "/api/cases/CASE-ALPHA/documents", self.commit_payload())
        self.assertEqual(status, 200, result)
        self.assertEqual(result["result"], "imported")
        return result["source_id"]

    def test_preview_numbers_original_lines_without_persisting_source_or_annotations(self):
        before = self.ledger()
        status, preview, _ = self.request(
            "/api/cases/CASE-ALPHA/documents/preview", self.preview_payload())
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview["case_id"], "CASE-ALPHA")
        self.assertEqual(preview["text"], self.raw.decode("utf-8"))
        self.assertEqual(preview["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(preview["byte_count"], len(self.raw))
        self.assertEqual(preview["lines"], [
            {"line": 1, "text": "\ufeffFictional local note"},
            {"line": 2, "text": "Value stable; review pending."},
        ])
        self.assertEqual(self.ledger(), before)

    def test_committed_original_bytes_download_with_attachment_and_existing_text_reader(self):
        source_id = self.commit()
        status, body, headers = self.request(
            f"/api/cases/CASE-ALPHA/sources/{source_id}/download")
        self.assertEqual(status, 200)
        self.assertEqual(body, self.raw)
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(headers["Content-Length"], str(len(self.raw)))
        self.assertEqual(headers["Content-Disposition"],
                         'attachment; filename="fictional-note.txt"')
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, text, _ = self.request(f"/api/cases/CASE-ALPHA/sources/{source_id}")
        self.assertEqual(status, 200)
        self.assertEqual(text["text"], self.raw.decode("utf-8"))

    def test_existing_structured_sources_download_without_rewriting_original_bytes(self):
        status, raw, headers = self.request(
            f"/api/cases/CASE-ALPHA/sources/{self.legacy_id}/download")
        self.assertEqual(status, 200)
        self.assertEqual(raw, self.legacy_raw)
        self.assertTrue(headers["Content-Disposition"].startswith("attachment; filename="))

    def test_missing_confirmation_hash_or_manual_transcription_does_not_write(self):
        before = self.ledger()
        for missing in ("confirmed_case_id", "expected_sha256", "manual_transcription_confirmed"):
            with self.subTest(missing=missing):
                payload = self.commit_payload()
                if missing == "manual_transcription_confirmed":
                    del payload["metadata"][missing]
                else:
                    del payload[missing]
                status, _, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_mismatched_hash_case_or_invented_quote_does_not_write(self):
        before = self.ledger()
        cases = ("hash", "case", "quote", "line", "findings_limit")
        for invalid in cases:
            with self.subTest(invalid=invalid):
                payload = self.commit_payload()
                if invalid == "hash":
                    payload["expected_sha256"] = "0" * 64
                elif invalid == "case":
                    payload["confirmed_case_id"] = "CASE-BETA"
                elif invalid == "quote":
                    payload["findings"][0]["quote"] = "A claim absent from the original source."
                elif invalid == "line":
                    payload["findings"][0]["line"] = 1
                else:
                    payload["findings"] = [
                        {"key": f"value_{n}", "state": "reported",
                         "quote": "Value stable; review pending.", "line": 2}
                        for n in range(31)]
                status, _, _ = self.request("/api/cases/CASE-ALPHA/documents", payload)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_unknown_fields_are_rejected_in_both_routes_and_nested_annotations(self):
        before = self.ledger()
        cases = ("preview", "commit", "metadata", "finding")
        for invalid in cases:
            with self.subTest(invalid=invalid):
                path = "/api/cases/CASE-ALPHA/documents"
                payload = self.commit_payload()
                if invalid == "preview":
                    path += "/preview"
                    payload = self.preview_payload()
                target = (payload["metadata"] if invalid == "metadata" else
                          payload["findings"][0] if invalid == "finding" else payload)
                target["url"] = "https://invalid.example/do-not-fetch.txt"
                status, _, _ = self.request(path, payload)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_noncanonical_or_invalid_base64_does_not_write(self):
        before = self.ledger()
        for value in (None, 12, "", "%%%", "SGVsbG8=\n", "Zh==", "Zg===", "é"):
            with self.subTest(value=value):
                payload = self.preview_payload()
                payload["content_base64"] = value
                status, _, _ = self.request("/api/cases/CASE-ALPHA/documents/preview", payload)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self):
        before = self.ledger()
        body = json.dumps(self.preview_payload()).encode("utf-8")
        duplicate = body[:-1] + b', "filename": "second.txt"}'
        for raw in (duplicate, b'{"filename":"note.txt","content_base64":NaN}', b'[]', b'{'):
            with self.subTest(raw=raw):
                status, _, _ = self.request(
                    "/api/cases/CASE-ALPHA/documents/preview", raw_body=raw)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_binary_non_utf8_and_pathlike_names_are_rejected_without_writes(self):
        before = self.ledger()
        samples = [(b"bad\x00text", "fictional.txt"), (b"\xff\xfe\x00", "fictional.txt")]
        samples.extend((self.raw, name) for name in (
            "../fictional.txt", "/tmp/fictional.txt", "C:\\fake\\fictional.txt",
            "https://invalid.example/fictional.txt", "note.txt\r\nX-Injected: yes", "note.pdf"))
        for raw, name in samples:
            with self.subTest(name=name, raw=raw):
                status, _, _ = self.request(
                    "/api/cases/CASE-ALPHA/documents/preview", self.preview_payload(raw, name))
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_sixty_four_kib_document_preview_fits_route_specific_encoded_body_limit(self):
        raw = (b"A" * 1023 + b"\n") * 64
        status, preview, _ = self.request(
            "/api/cases/CASE-ALPHA/documents/preview", self.preview_payload(raw))
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview["byte_count"], 65536)
        self.assertEqual(preview["sha256"], hashlib.sha256(raw).hexdigest())

    def test_decoded_and_http_body_limits_reject_without_raising_other_route_limits(self):
        before = self.ledger()
        too_large = self.preview_payload(b"A" * 65537)
        status, _, _ = self.request("/api/cases/CASE-ALPHA/documents/preview", too_large)
        self.assertEqual(status, 422)
        oversized_body = b" " * 131073
        status, _, _ = self.request(
            "/api/cases/CASE-ALPHA/documents/preview", raw_body=oversized_body)
        self.assertEqual(status, 422)
        # A valid existing-route payload padded beyond its old 72 KiB cap
        # would create a question if intake accidentally widened every route.
        question = json.dumps({"question": "Which fictional source needs review?"}).encode()
        status, _, _ = self.request(
            "/api/cases/CASE-ALPHA/questions", raw_body=question + b" " * 74000)
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_host_and_origin_guards_apply_to_uploads_and_downloads(self):
        source_id = self.commit()
        before = self.ledger()
        requests = (
            ("/api/cases/CASE-ALPHA/documents/preview", self.preview_payload(),
             {"Host": f"untrusted.example:{self.port}"}),
            ("/api/cases/CASE-ALPHA/documents", self.commit_payload(),
             {"Origin": "https://untrusted.example"}),
            ("/api/cases/CASE-ALPHA/documents/preview", self.preview_payload(),
             {"Sec-Fetch-Site": "cross-site"}),
            (f"/api/cases/CASE-ALPHA/sources/{source_id}/download", None,
             {"Host": f"untrusted.example:{self.port}"}),
        )
        for path, payload, headers in requests:
            with self.subTest(path=path, headers=headers):
                status, _, _ = self.request(path, payload, headers=headers)
                self.assertEqual(status, 403)
        self.assertEqual(self.ledger(), before)

    def test_other_case_cannot_download_source_and_unknown_case_cannot_preview(self):
        source_id = self.commit()
        before = self.ledger()
        status, result, _ = self.request(
            f"/api/cases/CASE-BETA/sources/{source_id}/download")
        self.assertEqual(status, 422)
        self.assertNotIn("Fictional local note", json.dumps(result))
        status, _, _ = self.request(
            "/api/cases/CASE-UNKNOWN/documents/preview", self.preview_payload())
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_download_rejects_out_of_range_identifiers_without_aborting_http_response(self):
        before = self.ledger()
        for identifier in ("0", "9223372036854775808", "9" * 5000):
            with self.subTest(identifier_length=len(identifier)):
                try:
                    status, _, _ = self.request(
                        f"/api/cases/CASE-ALPHA/sources/{identifier}/download")
                except RemoteDisconnected:
                    # A converter/SQLite exception must become a bounded input
                    # error response, not terminate a request-handler thread.
                    status = None
                self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)


if __name__ == "__main__":
    unittest.main()
