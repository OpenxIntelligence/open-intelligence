"""Composer read-only lab tool HTTP integration over canonical fictional sources."""
from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.composer import build_composer_context
from open_intelligence.composer_lab import composer_lab_trend
from open_intelligence.lab_trends import case_lab_trend
from open_intelligence.store import CaseStore, InvalidInput


def report(document, day, value, unit="g/dL", qc="passed", amends=None):
    content = [
        "OI-SYNTHETIC-REPORT/1", "Patient: CASE-ALPHA",
        f"Document: {document}", "Type: laboratory",
        f"Event-Date: {day}", f"Issued-At: {day}",
        "Specimen: SPECIMEN-ALPHA",
    ]
    if amends:
        content.append(f"Amends: {amends}")
    content.append(f"Finding: hemoglobin|reported|OI-LAB-VALUE/1;value={value};unit={unit};qc={qc}")
    return ("\n".join(content) + "\n").encode()


class ComposerLabIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "synthetic.sqlite")
        store = CaseStore(self.db)
        store.add_case("CASE-ALPHA", "Fictional case Alpha")
        store.add_case("CASE-BETA", "Fictional case Beta")
        store.import_report("CASE-ALPHA", report("LAB-001", "2026-05-01", "10.2"))
        store.import_report("CASE-ALPHA", report("LAB-002", "2026-06-01", "9.8"))
        self.qid = store.add_question("CASE-ALPHA", "Compare synthetic authored laboratory values")
        self.token = build_composer_context(store, "CASE-ALPHA", self.qid)["fingerprint"]
        store.close()
        bound = type("SyntheticComposerLabHandler", (Handler,), {"db_path": self.db})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def get(self, case="CASE-ALPHA", question_id=None, fingerprint=None,
            finding_key="hemoglobin", extra=None):
        query = [
            ("question_id", str(self.qid if question_id is None else question_id)),
            ("context_fingerprint", self.token if fingerprint is None else fingerprint),
            ("finding_key", finding_key),
        ]
        query.extend(extra or [])
        url = ("http://127.0.0.1:" + str(self.server.server_port) +
               f"/api/cases/{case}/composer/tools/lab-trend?" + urlencode(query))
        try:
            with urlopen(url, timeout=6) as result:
                return result.status, json.loads(result.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_live_http_uses_question_bound_snapshot_and_source_anchors(self):
        code, response = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(response["status"], "computed")
        self.assertEqual(response["result"]["delta"], "-0.4")
        self.assertEqual(response["context_fingerprint"], self.token)
        self.assertEqual(response["question_id"], self.qid)
        self.assertEqual(response["clinical_interpretation"], "not_performed")
        self.assertEqual(len(response["result"]["points"]), 2)
        self.assertTrue(all(point["source"]["source_line"] == 8
                            for point in response["result"]["points"]))
        self.assertIn("not_persisted", response["execution_receipt"])

    def test_stale_fingerprint_blocks_after_amendment(self):
        store = CaseStore(self.db)
        store.import_report("CASE-ALPHA", report("LAB-002", "2026-06-01", "7.2",
                                                   amends="LAB-002@1"))
        store.close()
        code, response = self.get()
        self.assertEqual(code, 422)
        self.assertIn("stale", response["error"].lower())
        self.assertNotIn("7.2", json.dumps(response))
        store = CaseStore(self.db)
        self.assertEqual(len(store.list_investigations("CASE-ALPHA")), 0)
        store.close()

    def test_wrong_patient_and_question_refuse_without_data_leak(self):
        for params in ({"case": "CASE-BETA"}, {"question_id": 999999}):
            code, response = self.get(**params)
            self.assertEqual(code, 422)
            self.assertNotIn("LAB-001", json.dumps(response))
        code, response = self.get(fingerprint="x" * 64)
        self.assertEqual(code, 422)

    def test_missing_duplicate_and_malformed_query_refuse(self):
        code, _ = self.get(finding_key="bad;sql")
        self.assertEqual(code, 422)
        code, _ = self.get(extra=[("question_id", str(self.qid))])
        self.assertEqual(code, 422)

    def test_comparison_holds_on_source_authored_failed_qc(self):
        store = CaseStore(self.db)
        store.import_report("CASE-ALPHA", report("LAB-002", "2026-06-01", "9.8",
                                                   qc="failed", amends="LAB-002@1"))
        fingerprint = build_composer_context(store, "CASE-ALPHA", self.qid)["fingerprint"]
        store.close()
        code, response = self.get(fingerprint=fingerprint)
        self.assertEqual(code, 200)
        self.assertEqual(response["status"], "held")
        self.assertIsNone(response["result"]["delta"])
        self.assertFalse(response["result"]["analysis_executed"])

    def test_read_only_http_adds_no_source_or_events(self):
        store = CaseStore(self.db)
        before = store.state("CASE-ALPHA")
        store.close()
        self.get()
        store = CaseStore(self.db)
        after = store.state("CASE-ALPHA")
        store.close()
        self.assertEqual(before, after)

    def test_browser_script_explicitly_checks_active_case_question_and_token(self):
        code, html = self._text("/")
        self.assertEqual(code, 200)
        self.assertIn('src="/composer.js"', html)
        code, js = self._text("/composer.js")
        self.assertEqual(code, 200)
        for key in ("composer/tools/lab-trend", "requestSequence", "context_fingerprint",
                    "oi:composer-open-source", "clinical_interpretation"):
            self.assertIn(key, js)

    def _text(self, route):
        with urlopen("http://127.0.0.1:" + str(self.server.server_port) + route, timeout=6) as response:
            return response.status, response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
