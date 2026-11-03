"""Manual annotation revisions through the real, bounded local HTTP boundary.

Every record is independently fictional. These tests use the original source
owner and an actual loopback server, not mocked persistence or authorization.
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


class DocumentAnnotationRevisionHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "annotation-http.sqlite")
        store = CaseStore(self.db_path)
        try:
            store.add_case("CASE-ALPHA", "Independent fictional Alpha")
            store.add_case("CASE-BETA", "Independent fictional Beta")
        finally:
            store.close()
        handler = type("AnnotationRevisionHandler", (Handler,), {
            "db_path": self.db_path, "log_message": lambda *_args: None,
        })
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)
        self.thread.start()
        self.raw = ("\ufeffIndependent fictional annotation record\r\n"
                    "Amber observation; status remains pending.\r\n"
                    "Blue observation; status was not assessed.\r\n").encode("utf-8")
        self.source_id = self.import_original()["source_id"]
        self.path = f"/api/cases/CASE-ALPHA/sources/{self.source_id}/annotations"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path, payload=None, *, raw_body=None, headers=None):
        values = dict(headers or {})
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

    def import_original(self, *, amendment=False):
        raw = self.raw.replace(b"Amber observation", b"Amended amber observation") if amendment else self.raw
        metadata = {
            "document_id": "DOC-ANNOTATION", "kind": "clinical",
            "event_date": "2026-09-01", "issued_at": "2026-09-03" if amendment else "2026-09-02",
            "manual_transcription_confirmed": True,
        }
        if amendment:
            metadata["amends_version"] = 1
        status, result, _ = self.request("/api/cases/CASE-ALPHA/documents", {
            "filename": "fictional-annotations.txt",
            "content_base64": base64.b64encode(raw).decode("ascii"),
            "metadata": metadata, "findings": [],
            "expected_sha256": hashlib.sha256(raw).hexdigest(),
            "confirmed_case_id": "CASE-ALPHA",
        })
        self.assertEqual(status, 200, result)
        return result

    @staticmethod
    def finding(*, revised=False):
        return ({"key": "blue_tag", "state": "not-assessed",
                 "quote": "Blue observation; status was not assessed.", "line": 3}
                if revised else
                {"key": "amber_tag", "state": "pending",
                 "quote": "Amber observation; status remains pending.", "line": 2})

    def payload(self, *, expected_revision=1, revised=False):
        return {
            "findings": [self.finding(revised=revised)],
            "expected_revision": expected_revision,
            "expected_sha256": hashlib.sha256(self.raw).hexdigest(),
            "confirmed_case_id": "CASE-ALPHA",
            "manual_transcription_confirmed": True,
            "reason": "Correct the manually selected passage after checking the original." if revised
                      else "Add the first manually selected passage after checking the original.",
        }

    def revise(self, **kwargs):
        status, result, _ = self.request(self.path, self.payload(**kwargs))
        self.assertEqual(status, 200, result)
        self.assertEqual(result["result"], "revised")
        return result

    def ledger(self):
        store = CaseStore(self.db_path)
        try:
            return "\n".join(store.db.iterdump())
        finally:
            store.close()

    def create_question(self):
        status, result, _ = self.request("/api/cases/CASE-ALPHA/questions", {
            "question": "Which manually selected fictional passage needs another review?",
        })
        self.assertEqual(status, 201, result)
        return result["question_id"]

    def snapshot_payload(self, question_id, revision=None):
        payload = {"question_id": question_id, "source_ids": [self.source_id],
                   "summary": "Independent fictional review of the selected source passages."}
        if revision is not None:
            payload["expected_annotation_revisions"] = {str(self.source_id): revision}
        return payload

    def test_get_returns_exact_original_and_initial_receipt_without_writes(self):
        before = self.ledger()
        status, result, headers = self.request(self.path)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["case_id"], "CASE-ALPHA")
        self.assertEqual(result["source_id"], self.source_id)
        self.assertEqual(result["document_id"], "DOC-ANNOTATION")
        self.assertEqual(result["version"], 1)
        self.assertTrue(result["writable"])
        self.assertEqual(result["text"], self.raw.decode("utf-8"))
        self.assertEqual(result["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(result["lines"][1], {"line": 2, "text": self.finding()["quote"]})
        self.assertEqual(result["current_revision"]["revision"], 1)
        self.assertEqual(result["current_revision"]["findings"], [])
        self.assertEqual(len(result["history"]), 1)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.ledger(), before)

    def test_revision_and_exact_retry_preserve_one_original_and_append_receipts(self):
        revised = self.revise()
        self.assertEqual(revised["annotation_revision"], 2)
        self.assertEqual(revised["source_id"], self.source_id)
        self.assertEqual(revised["version"], 1)
        before_retry = self.ledger()
        status, duplicate, _ = self.request(self.path, self.payload())
        self.assertEqual(status, 200, duplicate)
        self.assertEqual(duplicate["result"], "duplicate")
        self.assertEqual(duplicate["annotation_revision"], 2)
        self.assertEqual(self.ledger(), before_retry)
        status, original, _ = self.request(
            f"/api/cases/CASE-ALPHA/sources/{self.source_id}/download")
        self.assertEqual(status, 200)
        self.assertEqual(original, self.raw)
        status, annotations, _ = self.request(self.path)
        self.assertEqual([r["revision"] for r in annotations["history"]], [1, 2])
        self.assertEqual(annotations["history"][0]["findings"], [])
        self.assertEqual(annotations["current_revision"]["findings"], [self.finding()])
        _, current, _ = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(len(current["sources"]), 1)
        self.assertEqual(current["assertions"][0]["classification_origin"], "user_selected")

    def test_stale_revision_cannot_overwrite_a_newer_confirmation(self):
        self.revise()
        before = self.ledger()
        status, _, _ = self.request(self.path, self.payload(revised=True))
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_revision_number_must_be_a_positive_integer_without_boolean_coercion(self):
        before = self.ledger()
        for invalid in (None, True, False, 0, -1, "1", 1.0, 10 ** 40):
            with self.subTest(value=invalid):
                status, _, _ = self.request(self.path, self.payload(expected_revision=invalid))
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_cross_case_reads_and_writes_cannot_reveal_or_change_annotations(self):
        before = self.ledger()
        other = self.path.replace("CASE-ALPHA", "CASE-BETA")
        payload = self.payload()
        payload["confirmed_case_id"] = "CASE-BETA"
        for body in (None, payload):
            status, result, _ = self.request(other, body)
            self.assertEqual(status, 422)
            self.assertNotIn("Amber observation", json.dumps(result))
        self.assertEqual(self.ledger(), before)

    def test_superseded_original_is_readable_but_cannot_receive_new_annotations(self):
        self.revise()
        self.import_original(amendment=True)
        before = self.ledger()
        status, result, _ = self.request(self.path)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["state"], "superseded")
        self.assertFalse(result["writable"])
        self.assertEqual(result["text"], self.raw.decode("utf-8"))
        status, _, _ = self.request(self.path, self.payload(expected_revision=2, revised=True))
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_structured_source_cannot_be_silently_reclassified_as_manual_intake(self):
        raw = (SYNTHETIC / "alpha-imaging.txt").read_text()
        status, result, _ = self.request("/api/cases/CASE-ALPHA/imports", {"text": raw})
        self.assertEqual(status, 200, result)
        path = f"/api/cases/CASE-ALPHA/sources/{result['source_id']}/annotations"
        before = self.ledger()
        for body in (None, self.payload()):
            status, _, _ = self.request(path, body)
            self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_missing_unknown_or_nested_unknown_fields_reject_without_writes(self):
        before = self.ledger()
        for invalid in (*self.payload().keys(), "extra", "nested"):
            with self.subTest(field=invalid):
                body = self.payload()
                if invalid == "extra":
                    body["url"] = "https://invalid.example/do-not-fetch"
                elif invalid == "nested":
                    body["findings"][0]["clinician_approved"] = True
                else:
                    del body[invalid]
                status, _, _ = self.request(self.path, body)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_duplicate_json_keys_nonfinite_and_invalid_envelopes_reject(self):
        before = self.ledger()
        raw = json.dumps(self.payload()).encode()
        bodies = (
            raw[:-1] + b',"expected_revision":1}',
            raw.replace(b'"line": 2', b'"line": 2, "line": 3'),
            raw.replace(b'"expected_revision": 1', b'"expected_revision": NaN'),
            raw.replace(b'"expected_revision": 1', b'"expected_revision": Infinity'),
            b'[]', b'{', b'"not an object"',
        )
        for body in bodies:
            with self.subTest(body=body[:80]):
                status, _, _ = self.request(self.path, raw_body=body)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_annotation_body_cap_does_not_expand_other_routes(self):
        before = self.ledger()
        status, _, _ = self.request(self.path, raw_body=b" " * 131073)
        self.assertEqual(status, 422)
        question = json.dumps({"question": "Which fictional source needs review?"}).encode()
        status, _, _ = self.request("/api/cases/CASE-ALPHA/questions",
                                    raw_body=question + b" " * 74000)
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_invalid_source_identifiers_receive_bounded_http_errors(self):
        before = self.ledger()
        for identifier in ("0", "9223372036854775808", "9" * 5000):
            for payload in (None, self.payload()):
                with self.subTest(length=len(identifier), post=payload is not None):
                    try:
                        status, _, _ = self.request(
                            f"/api/cases/CASE-ALPHA/sources/{identifier}/annotations", payload)
                    except RemoteDisconnected:
                        status = None
                    self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_existing_host_origin_and_content_type_guards_still_apply(self):
        before = self.ledger()
        for payload, headers, expected in (
            (None, {"Host": f"untrusted.example:{self.port}"}, 403),
            (self.payload(), {"Origin": "https://untrusted.example"}, 403),
            (self.payload(), {"Sec-Fetch-Site": "cross-site"}, 403),
            (self.payload(), {"Content-Type": "text/plain"}, 422),
        ):
            status, _, _ = self.request(self.path, payload, headers=headers)
            self.assertEqual(status, expected)
        self.assertEqual(self.ledger(), before)

    def test_hash_confirmation_reason_and_exact_quote_fail_closed(self):
        before = self.ledger()
        for invalid in ("hash", "case", "confirmation", "reason", "quote", "line", "status"):
            with self.subTest(invalid=invalid):
                payload = self.payload()
                if invalid == "hash":
                    payload["expected_sha256"] = "0" * 64
                elif invalid == "case":
                    payload["confirmed_case_id"] = "CASE-BETA"
                elif invalid == "confirmation":
                    payload["manual_transcription_confirmed"] = 1
                elif invalid == "reason":
                    payload["reason"] = " "
                elif invalid == "quote":
                    payload["findings"][0]["quote"] = "Invented passage absent from the original."
                elif invalid == "line":
                    payload["findings"][0]["line"] = 1
                else:
                    payload["findings"][0]["state"] = "clinician-approved"
                status, _, _ = self.request(self.path, payload)
                self.assertEqual(status, 422)
                self.assertEqual(self.ledger(), before)

    def test_snapshot_requires_the_revised_annotation_receipt_shown_to_the_author(self):
        self.revise()
        question_id = self.create_question()
        before = self.ledger()
        for revision in (None, 1, True, "2"):
            status, _, _ = self.request("/api/cases/CASE-ALPHA/snapshots",
                                        self.snapshot_payload(question_id, revision))
            self.assertEqual(status, 422)
            self.assertEqual(self.ledger(), before)
        status, result, _ = self.request("/api/cases/CASE-ALPHA/snapshots",
                                         self.snapshot_payload(question_id, 2))
        self.assertEqual(status, 201, result)

    def test_duplicate_snapshot_revision_keys_are_rejected_without_writes(self):
        self.revise()
        question_id = self.create_question()
        payload = self.snapshot_payload(question_id, 2)
        raw = json.dumps(payload).encode()
        target = json.dumps(str(self.source_id)).encode() + b": 2"
        raw = raw.replace(target, target + b", " + json.dumps(str(self.source_id)).encode() + b": 1")
        before = self.ledger()
        status, _, _ = self.request("/api/cases/CASE-ALPHA/snapshots", raw_body=raw)
        self.assertEqual(status, 422)
        self.assertEqual(self.ledger(), before)

    def test_correction_reopens_review_and_preserves_captured_historical_passages(self):
        self.revise()
        question_id = self.create_question()
        status, result, _ = self.request("/api/cases/CASE-ALPHA/snapshots",
                                         self.snapshot_payload(question_id, 2))
        self.assertEqual(status, 201, result)
        snapshot_id = result["snapshot_id"]
        status, _, _ = self.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/review",
                                    {"reviewer_label": "Fictional reviewer"})
        self.assertEqual(status, 200)
        revised = self.revise(expected_revision=2, revised=True)
        self.assertEqual(revised["annotation_revision"], 3)
        self.assertIn(snapshot_id, revised["invalidated_snapshots"])
        _, current, _ = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(current["snapshots"][0]["state"], "stale")
        self.assertEqual(current["questions"][0]["state"], "open")
        self.assertEqual(current["assertions"][0]["finding_key"], "blue_tag")
        status, exported, _ = self.request(
            f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/export")
        self.assertEqual(status, 200)
        historical = exported.decode("utf-8")
        self.assertIn("amber_tag", historical)
        self.assertNotIn("blue_tag", historical)
        _, original, _ = self.request(f"/api/cases/CASE-ALPHA/sources/{self.source_id}/download")
        self.assertEqual(original, self.raw)
        _, annotations, _ = self.request(self.path)
        self.assertEqual([r["revision"] for r in annotations["history"]], [1, 2, 3])
        self.assertEqual(annotations["history"][1]["findings"], [self.finding()])


if __name__ == "__main__":
    unittest.main()
