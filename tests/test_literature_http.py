"""Real loopback HTTP boundaries; provider calls are always replaced offline."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import __main__ as application
from open_intelligence.literature import LiteratureError


RESULT = {
    "provider": "europe_pmc", "endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    "adapter_version": "1", "provider_api_version": "6.9", "retrieved_at": "2026-11-02T12:00:00Z",
    "response_sha256": "a" * 64, "provider_hit_count": 7, "returned_record_count": 1,
    "excluded_counts": {}, "citations": [], "metadata_only": True,
    "clinical_evidence_appraised": False, "clinical_use": "not evidence for a clinical conclusion",
    "rights_status": "not_assessed",
}
REQUEST = {"terms": "public oncology review", "human_authored": True,
           "public_terms_only": True, "page_size": 5}


class LiteratureHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "must-not-be-created.sqlite"
        self.handler = type("BoundLiteratureHandler", (application.Handler,), {
            "db_path": str(self.db_path), "allow_literature_live": True,
            "literature_request_lock": threading.Lock(), "literature_last_request": None,
        })
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.provider_patch = patch("open_intelligence.__main__.search_europe_pmc", create=True,
                                    return_value=copy.deepcopy(RESULT))
        self.provider = self.provider_patch.start()
        self.store_patch = patch("open_intelligence.__main__.CaseStore",
                                 side_effect=AssertionError("Literature requests must not access the case store"))
        self.store = self.store_patch.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.store_patch.stop()
        self.provider_patch.stop()
        self.assertFalse(self.db_path.exists())
        self.temp.cleanup()

    def request(self, path="/api/literature/search", payload=REQUEST, headers=None, *, method=None):
        headers = {"Content-Type": "application/json", **(headers or {})}
        req = Request(self.base + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers=headers, method=method)
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if "json" in response.headers.get("Content-Type", "") else body

    def test_status_is_default_off_and_requires_no_database_or_provider(self):
        self.assertFalse(getattr(application.Handler, "allow_literature_live", True))
        self.handler.allow_literature_live = False
        code, status = self.request("/api/literature/status", None)
        self.assertEqual(code, 200)
        self.assertIs(status["live_enabled"], False)
        self.assertTrue(status["metadata_only"])
        self.assertFalse(status["clinical_evidence_appraised"])
        self.assertEqual(status["rights_status"], "not_assessed")
        code, denied = self.request()
        self.assertEqual(code, 403)
        self.assertEqual(denied["code"], "disabled")
        self.provider.assert_not_called()
        self.store.assert_not_called()

    def test_success_passes_only_explicit_public_terms_and_has_no_persistence(self):
        code, result = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(result, RESULT)
        self.provider.assert_called_once_with("public oncology review", human_authored=True,
                                              public_terms_only=True, page_size=5)
        self.store.assert_not_called()
        self.assertNotIn(REQUEST["terms"], json.dumps(result))

    def test_unexpected_case_provider_or_context_fields_fail_before_adapter(self):
        for field in ("case_id", "patient_id", "question", "context", "source_ids", "endpoint", "opener", "clock"):
            with self.subTest(field=field):
                code, result = self.request(payload={**REQUEST, field: "DO-NOT-EGRESS"})
                self.assertEqual(code, 422)
                self.assertEqual(result["code"], "invalid_input")
                self.assertNotIn("DO-NOT-EGRESS", json.dumps(result))
        self.provider.assert_not_called()
        self.store.assert_not_called()

    def test_exact_true_attestations_and_bounded_typed_inputs_required(self):
        invalid = []
        for field in ("human_authored", "public_terms_only"):
            for value in (False, 1, "true", None):
                invalid.append({**REQUEST, field: value})
            invalid.append({key: value for key, value in REQUEST.items() if key != field})
        invalid += [{**REQUEST, "terms": value} for value in (None, {}, "", "ab", " " * 5, "x" * 241)]
        invalid += [{**REQUEST, "page_size": value} for value in (True, 0, -1, 11, "5", 2.5)]
        for payload in invalid:
            with self.subTest(payload=payload):
                code, result = self.request(payload=payload)
                self.assertEqual(code, 422)
                self.assertEqual(result["code"], "invalid_input")
        self.provider.assert_not_called()
        self.store.assert_not_called()

    def test_terms_in_url_rejected_before_adapter(self):
        code, result = self.request("/api/literature/search?terms=DO-NOT-EGRESS")
        self.assertEqual(code, 422)
        self.assertEqual(result["code"], "invalid_input")
        self.provider.assert_not_called()
        self.store.assert_not_called()

    def test_wrong_methods_and_unknown_literature_routes_do_not_open_case_store(self):
        for path, payload, expected in (
            ("/api/literature/search", None, 405),
            ("/api/literature/status", REQUEST, 405),
            ("/api/literature/unknown", None, 404),
            ("/api/literature/unknown", REQUEST, 404),
        ):
            with self.subTest(path=path, payload=payload):
                self.assertEqual(self.request(path, payload)[0], expected)
        self.provider.assert_not_called()
        self.store.assert_not_called()

    def test_host_origin_and_fetch_site_guards_precede_egress(self):
        for headers in ({"Host": "foreign.invalid"}, {"Origin": "https://foreign.invalid"},
                        {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                code, result = self.request(headers=headers)
                self.assertEqual(code, 403)
        code, _ = self.request("/api/literature/status", None, {"Host": "foreign.invalid"})
        self.assertEqual(code, 403)
        self.provider.assert_not_called()
        self.store.assert_not_called()

    def test_rate_limit_is_shared_by_request_instances_and_releases(self):
        with patch("open_intelligence.__main__.monotonic", side_effect=[100.0, 100.99, 101.0]):
            self.assertEqual(self.request()[0], 200)
            code, limited = self.request()
            self.assertEqual(code, 429)
            self.assertEqual(limited["code"], "rate_limited")
            self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.provider.call_count, 2)

    def test_only_one_inflight_request_can_reach_adapter(self):
        entered, release = threading.Event(), threading.Event()
        def blocked_provider(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise AssertionError("Test did not release the provider")
            return copy.deepcopy(RESULT)
        self.provider.side_effect = blocked_provider
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.request)
            try:
                self.assertTrue(entered.wait(2))
                code, busy = self.request()
                self.assertEqual(code, 429)
                self.assertEqual(busy["code"], "busy")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=4)[0], 200)
        self.assertEqual(self.provider.call_count, 1)

    def test_known_and_unknown_provider_failures_use_fixed_query_free_errors(self):
        failures = [LiteratureError("invalid_input"), LiteratureError("transport_failed"),
                    LiteratureError("invalid_response"), LiteratureError("response_too_large"),
                    RuntimeError("SECRET-PROVIDER-QUERY raw response")]
        mutated = LiteratureError("transport_failed")
        mutated.code = "SECRET-PROVIDER-QUERY"
        mutated.args = ("SECRET-PROVIDER-QUERY",)
        failures.append(mutated)
        for error in failures:
            with self.subTest(error=type(error).__name__):
                self.handler.literature_last_request = None
                self.provider.side_effect = error
                code, result = self.request()
                self.assertEqual(code, 422 if getattr(error, "code", None) == "invalid_input" else 502)
                self.assertEqual(result["code"], "invalid_input" if code == 422 else "provider_unavailable")
                self.assertNotIn("SECRET", json.dumps(result))
                self.assertNotIn(REQUEST["terms"], json.dumps(result))
                self.assertFalse(self.handler.literature_request_lock.locked())

    def test_static_form_and_script_are_available_without_database(self):
        code, html = self.request("/", None)
        self.assertEqual(code, 200)
        self.assertIn('id="literature-search-form"', html)
        self.assertIn('id="literature-public-attestation"', html)
        self.assertIn('src="/literature.js"', html)
        code, script = self.request("/literature.js", None)
        self.assertEqual(code, 200)
        self.assertIn("/api/literature/status", script)
        self.store.assert_not_called()

    def test_logs_never_include_request_query_body_or_unknown_method(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            self.request("/api/literature/search?terms=SECRET-URL", {**REQUEST, "case_id": "SECRET-BODY"})
            self.request(payload={**REQUEST, "terms": "SECRET BODY"})
            conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
            try:
                conn.request("SECRET-METHOD", "/?SECRET-DIAGNOSTIC")
                response = conn.getresponse()
                response.read()
            finally:
                conn.close()
        self.assertNotIn("SECRET", out.getvalue())
        self.assertIn("[local demo]", out.getvalue())


class LiteratureCliTests(unittest.TestCase):
    def test_operator_enable_flag_is_explicit_and_default_is_off(self):
        captured = []
        class FakeServer:
            def __init__(self, address, handler):
                captured.append((address, handler))
            def serve_forever(self):
                pass
            def server_close(self):
                pass
        for flag in ([], ["--enable-literature-live"]):
            with patch.object(application, "ThreadingHTTPServer", FakeServer), \
                 patch("sys.argv", ["open_intelligence", "serve", *flag]), \
                 contextlib.redirect_stdout(io.StringIO()):
                application.main()
            address, handler = captured[-1]
            self.assertEqual(address[0], "127.0.0.1")
            self.assertIs(handler.allow_literature_live, bool(flag))


if __name__ == "__main__":
    unittest.main()
