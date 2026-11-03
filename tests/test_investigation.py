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
from open_intelligence.store import CaseStore
from open_intelligence.investigation import (
    InvestigationError,
    ValidatedInvestigation,
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


class InvestigationFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        synthetic = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
        self.synthetic = synthetic
        self.pathology_source = self.store.import_report(
            "CASE-ALPHA", (synthetic / "alpha-pathology-original.txt").read_bytes())["source_id"]
        self.imaging_source = self.store.import_report(
            "CASE-ALPHA", (synthetic / "alpha-imaging.txt").read_bytes())["source_id"]

    def tearDown(self):
        self.store.close()

    def _save(self, text, source_id):
        question_id = self.store.add_question("CASE-ALPHA", text)
        validated = ValidatedInvestigation(
            status="completed", claims=[claim(source_id=source_id)], abstentions=[], dropped=[],
            model="recorded-replay", mode="replay")
        investigation_id = self.store.save_investigation(
            "CASE-ALPHA", question_id, "evidence-summary", validated, "replay")
        return question_id, investigation_id

    def test_amendment_stales_citing_investigation_without_snapshot_only(self):
        path_question, path_investigation = self._save(
            "What does the fictional pathology source report?", self.pathology_source)
        image_question, image_investigation = self._save(
            "What does the fictional imaging source report?", self.imaging_source)

        # Neither question has a human snapshot. Freshness must therefore be
        # driven by the investigation's own durable source citations.
        self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-pathology-amended.txt").read_bytes())

        investigations = {row["id"]: row for row in self.store.list_investigations("CASE-ALPHA")}
        self.assertEqual(investigations[path_investigation]["stale"], 1)
        self.assertEqual(investigations[image_investigation]["stale"], 0)
        questions = {row["id"]: row for row in self.store.state("CASE-ALPHA")["questions"]}
        self.assertEqual(questions[path_question]["state"], "open")
        self.assertEqual(questions[image_question]["state"], "addressed")

        # Historical output stays inspectable and pinned to its original source.
        saved = self.store.get_investigation("CASE-ALPHA", path_investigation)
        self.assertEqual(saved["claims"][0]["citations"],
                         [{"type": "source", "id": self.pathology_source}])
        sources = {row["id"]: row for row in self.store.state("CASE-ALPHA")["sources"]}
        self.assertEqual(sources[self.pathology_source]["state"], "superseded")

    def test_duplicate_amendment_does_not_change_freshness_again(self):
        _, investigation_id = self._save(
            "What does the fictional pathology source report?", self.pathology_source)
        amended = (self.synthetic / "alpha-pathology-amended.txt").read_bytes()
        self.store.import_report("CASE-ALPHA", amended)
        events_before = list(self.store.state("CASE-ALPHA")["events"])

        duplicate = self.store.import_report("CASE-ALPHA", amended)

        self.assertEqual(duplicate["result"], "duplicate")
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", investigation_id)["stale"], 1)
        self.assertEqual(self.store.state("CASE-ALPHA")["events"], events_before)

    def test_amendment_never_stales_another_case_investigation(self):
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        beta_source = self.store.import_report(
            "CASE-BETA", (self.synthetic / "beta-pathology.txt").read_bytes())["source_id"]
        beta_question = self.store.add_question(
            "CASE-BETA", "What does the fictional beta source report?")
        validated = ValidatedInvestigation(
            status="completed", claims=[claim(source_id=beta_source)], abstentions=[], dropped=[],
            model="recorded-replay", mode="replay")
        beta_investigation = self.store.save_investigation(
            "CASE-BETA", beta_question, "evidence-summary", validated, "replay")

        self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-pathology-amended.txt").read_bytes())

        self.assertEqual(self.store.get_investigation("CASE-BETA", beta_investigation)["stale"], 0)
        beta_questions = {row["id"]: row for row in self.store.state("CASE-BETA")["questions"]}
        self.assertEqual(beta_questions[beta_question]["state"], "addressed")


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
        # B-01: case routes require a fictional actor; seed() grants this one.
        values['X-Fictional-Actor'] = 'FICTIONAL-NAVIGATOR-A'
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
