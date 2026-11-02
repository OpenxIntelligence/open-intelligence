"""Tests for the bounded Meta Model API investigation (OI-008).

No live model call is made here: replay and validation are tested
directly, and the live path is tested only for its missing-key error.
A test that called the real API would be flaky, spend tokens, and
could not assert deterministically.
"""

import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.investigation import (
    InvestigationError,
    build_prompt,
    call_meta_api,
    validate_output,
)


def claim(text="The sources report a finding.", source_id=1, assessment_id=None):
    citations = [{"type": "source", "id": source_id}]
    if assessment_id is not None:
        citations.append({"type": "assessment", "id": assessment_id})
    return {"text": text, "support": "context", "citations": citations,
            "uncertainty": "moderate", "limits": "Synthetic only."}


class ValidationTests(unittest.TestCase):
    def test_good_claim_kept_as_hypothesis(self):
        result = validate_output({"claims": [claim()], "abstentions": []}, {1}, set())
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(result.claims), 1)
        self.assertEqual(result.claims[0]["kind"], "hypothesis")
        self.assertEqual(result.dropped, [])

    def test_unresolved_citation_drops_claim(self):
        result = validate_output({"claims": [claim(source_id=999)], "abstentions": []}, {1}, set())
        self.assertEqual(result.claims, [])
        self.assertEqual(result.dropped[0]["reason"], "unresolved_citation")
        self.assertEqual(result.status, "abstained")

    def test_recommendation_language_drops_claim(self):
        bad = claim(text="We recommend starting treatment X.")
        result = validate_output({"claims": [bad], "abstentions": []}, {1}, set())
        self.assertEqual(result.claims, [])
        self.assertEqual(result.dropped[0]["reason"], "language_guard")

    def test_invalid_uncertainty_drops_claim(self):
        bad = claim()
        bad["uncertainty"] = "certain"
        result = validate_output({"claims": [bad], "abstentions": []}, {1}, set())
        self.assertEqual(result.dropped[0]["reason"], "invalid_uncertainty")

    def test_empty_claims_abstain_with_reason(self):
        result = validate_output({"claims": [], "abstentions": []}, {1}, set())
        self.assertEqual(result.status, "abstained")
        self.assertEqual(result.abstentions[0]["reason"], "insufficient_evidence")

    def test_unknown_template_rejected_before_any_model_call(self):
        with self.assertRaises(InvestigationError):
            build_prompt("treat-this-patient", "What is relevant?", [], [])

    def test_live_call_parses_text_block_json(self):
        import io
        from unittest.mock import patch
        body = json.dumps({"content": [{"type": "text", "text": json.dumps(
            {"claims": [claim()], "abstentions": []})}]})
        response = io.BytesIO(body.encode())
        response.__enter__ = lambda self: self
        response.__exit__ = lambda *args: None
        with patch("open_intelligence.investigation.urllib.request.urlopen",
                   return_value=response):
            payload = call_meta_api("test prompt", "test-key-not-real")
        self.assertEqual(len(payload["claims"]), 1)
        self.assertEqual(payload["claims"][0]["text"], claim()["text"])


class HttpInvestigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'server.sqlite')
        seed(cls.path)
        bound_handler = type('BoundHandlerForInvestigation', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        values = {'Content-Type': 'application/json'} if data is not None else {}
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(), headers=values)
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_templates_listed(self):
        status, data = self.request('/api/investigations/templates')
        self.assertEqual(status, 200)
        self.assertIn("evidence-summary", [t["id"] for t in data["templates"]])

    def test_replay_investigation_is_hypothesis_pending(self):
        status, data = self.request('/api/cases/CASE-ALPHA/questions',
                                    {'question': 'What do the sources report about this case?'})
        self.assertEqual(status, 201)
        status, data = self.request('/api/cases/CASE-ALPHA/investigations',
                                    {'question_id': data['question_id'],
                                     'template': 'evidence-summary', 'mode': 'replay'})
        self.assertEqual(status, 201, data)
        self.assertEqual(data["kind"], "hypothesis")
        self.assertEqual(data["review_state"], "pending")
        self.assertEqual(data["mode"], "replay")
        self.assertEqual(data["model"], "recorded-replay")
        self.assertTrue(data["claims"])
        for kept in data["claims"]:
            self.assertEqual(kept["kind"], "hypothesis")
        status, listed = self.request('/api/cases/CASE-ALPHA/investigations')
        self.assertEqual(status, 200)
        self.assertTrue(any(item["id"] == data["id"] for item in listed["investigations"]))

    def test_unknown_template_rejected(self):
        status, data = self.request('/api/cases/CASE-ALPHA/questions',
                                    {'question': 'What do the sources report about this case?'})
        status, data = self.request('/api/cases/CASE-ALPHA/investigations',
                                    {'question_id': data['question_id'],
                                     'template': 'treat-this-patient', 'mode': 'replay'})
        self.assertEqual(status, 422)

    def test_live_without_key_offers_replay(self):
        saved = os.environ.pop("META_API_KEY", None)
        try:
            status, data = self.request('/api/cases/CASE-ALPHA/questions',
                                        {'question': 'What do the sources report about this case?'})
            status, data = self.request('/api/cases/CASE-ALPHA/investigations',
                                        {'question_id': data['question_id'],
                                         'template': 'evidence-summary', 'mode': 'live'})
            self.assertEqual(status, 503)
            self.assertIn("replay", data["error"])
        finally:
            if saved is not None:
                os.environ["META_API_KEY"] = saved


if __name__ == '__main__':
    unittest.main()
