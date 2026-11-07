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
from session_auth import signin_demo
from open_intelligence.agent_writes import build_investigation_contract
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
    """Synthetic OI-009 regression: model input dependencies are case-wide."""

    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.synthetic = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
        self.path_source = self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-pathology-original.txt").read_bytes()
        )["source_id"]

    def tearDown(self):
        self.store.close()

    def _save(self, case_id, question, source_id, *, status="completed", store=None):
        db = store if store is not None else self.store
        question_id = db.add_question(case_id, question)
        validated = ValidatedInvestigation(
            status=status,
            claims=[claim(source_id=source_id)] if status == "completed" else [],
            abstentions=[] if status == "completed" else [
                {"topic": "question", "reason": "insufficient_evidence"}],
            dropped=[], model="recorded-replay", mode="replay")
        run_id = db.save_investigation(
            case_id, question_id, "evidence-summary", validated, "replay",
            write_contract=build_investigation_contract(
                db, case_id, question_id, "evidence-summary", validated.model))
        return question_id, run_id

    def test_amendment_invalidates_all_same_case_model_inputs_without_snapshot(self):
        # The model prompt includes both original sources, regardless of which
        # one its final answer happened to cite.
        image_source = self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-imaging.txt").read_bytes())["source_id"]
        path_question, path_run = self._save(
            "CASE-ALPHA", "What does the pathology source report?", self.path_source)
        image_question, image_run = self._save(
            "CASE-ALPHA", "What does the imaging source report?", image_source)
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"], [])
        original = self.store.db.execute(
            "SELECT raw,sha256 FROM source_versions WHERE id=?",
            (self.path_source,)).fetchone()
        original_bytes, original_hash = original["raw"], original["sha256"]

        changed = self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-pathology-amended.txt").read_bytes())
        self.assertEqual(changed["invalidated_snapshots"], [])
        self.assertEqual(set(changed["invalidated_model_investigation_ids"]),
                         {path_run, image_run})
        states = {row["id"]: row for row in self.store.list_investigations("CASE-ALPHA")}
        self.assertEqual(states[path_run]["stale"], 1)
        self.assertEqual(states[image_run]["stale"], 1)
        questions = {row["id"]: row for row in self.store.state("CASE-ALPHA")["questions"]}
        self.assertEqual(questions[path_question]["state"], "open")
        self.assertEqual(questions[image_question]["state"], "open")
        retained = self.store.get_investigation("CASE-ALPHA", path_run)
        self.assertEqual(retained["claims"][0]["citations"],
                         [{"type": "source", "id": self.path_source}])
        old = self.store.db.execute(
            "SELECT raw,sha256,state FROM source_versions WHERE id=?",
            (self.path_source,)).fetchone()
        self.assertEqual((old["raw"], old["sha256"], old["state"]),
                         (original_bytes, original_hash, "superseded"))

    def test_new_source_invalidates_abstention_and_completed_run(self):
        answered_question, answered_run = self._save(
            "CASE-ALPHA", "What is known from the original report?", self.path_source)
        abstained_question, abstained_run = self._save(
            "CASE-ALPHA", "What was not in the original record?", self.path_source,
            status="abstained")
        self.assertEqual(self.store.get_investigation(
            "CASE-ALPHA", abstained_run)["claims"], [])
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"], [])
        added = self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-imaging.txt").read_bytes())
        self.assertEqual(set(added["invalidated_model_investigation_ids"]),
                         {answered_run, abstained_run})
        self.assertEqual(self.store.get_investigation(
            "CASE-ALPHA", abstained_run)["stale"], 1)
        questions = {row["id"]: row for row in self.store.state("CASE-ALPHA")["questions"]}
        self.assertEqual(questions[answered_question]["state"], "open")
        self.assertEqual(questions[abstained_question]["state"], "open")

    def test_unrelated_human_imaging_snapshot_remains_reviewed(self):
        image_source = self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-imaging.txt").read_bytes())["source_id"]
        path_question, path_run = self._save(
            "CASE-ALPHA", "What does this pathology report contain?", self.path_source)
        image_question = self.store.add_question(
            "CASE-ALPHA", "What did the independent imaging review show?")
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", image_question,
            "Independently authored fictional imaging-only review.", [image_source])
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", snapshot_id, "Fictional reviewer")

        result = self.store.import_report(
            "CASE-ALPHA", (self.synthetic / "alpha-pathology-amended.txt").read_bytes())
        self.assertEqual(result["invalidated_snapshots"], [])
        self.assertEqual(result["invalidated_model_investigation_ids"], [path_run])
        self.assertEqual(self.store.get_investigation(
            "CASE-ALPHA", path_run)["stale"], 1)
        state = self.store.state("CASE-ALPHA")
        snap = next(row for row in state["snapshots"] if row["id"] == snapshot_id)
        self.assertEqual(snap["state"], "reviewed_in_demo")
        q = {row["id"]: row for row in state["questions"]}
        self.assertEqual(q[path_question]["state"], "open")
        self.assertEqual(q[image_question]["state"], "addressed")

    def test_duplicate_amendment_is_event_idempotent(self):
        _, run = self._save(
            "CASE-ALPHA", "What does the original pathology contain?", self.path_source)
        amended = (self.synthetic / "alpha-pathology-amended.txt").read_bytes()
        self.store.import_report("CASE-ALPHA", amended)
        events_before = list(self.store.state("CASE-ALPHA")["events"])
        duplicate = self.store.import_report("CASE-ALPHA", amended)
        self.assertEqual(duplicate["result"], "duplicate")
        self.assertEqual(self.store.state("CASE-ALPHA")["events"], events_before)
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", run)["stale"], 1)

    def test_other_case_investigation_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            filename = str(Path(tmp) / "freshness.sqlite")
            db = CaseStore(filename)
            try:
                db.add_case("CASE-ALPHA", "Fictional Alpha")
                db.add_case("CASE-BETA", "Fictional Beta")
                alpha_source = db.import_report(
                    "CASE-ALPHA", (self.synthetic / "alpha-pathology-original.txt").read_bytes()
                )["source_id"]
                beta_source = db.import_report(
                    "CASE-BETA", (self.synthetic / "beta-pathology.txt").read_bytes()
                )["source_id"]
                qa, ra = self._save(
                    "CASE-ALPHA", "What is recorded for fictional Alpha?", alpha_source,
                    store=db)
                qb, rb = self._save(
                    "CASE-BETA", "What is recorded for fictional Beta?", beta_source,
                    store=db)
                changed = db.import_report(
                    "CASE-ALPHA", (self.synthetic / "alpha-pathology-amended.txt").read_bytes())
                self.assertEqual(changed["invalidated_model_investigation_ids"], [ra])
                self.assertEqual(db.get_investigation("CASE-BETA", rb)["stale"], 0)
            finally:
                db.close()
            reopened = CaseStore(filename)
            try:
                self.assertEqual(reopened.get_investigation("CASE-ALPHA", ra)["stale"], 1)
                self.assertEqual(reopened.get_investigation("CASE-BETA", rb)["stale"], 0)
                state_alpha = {row["id"]: row for row in reopened.state("CASE-ALPHA")["questions"]}
                state_beta = {row["id"]: row for row in reopened.state("CASE-BETA")["questions"]}
                self.assertEqual(state_alpha[qa]["state"], "open")
                self.assertEqual(state_beta[qb]["state"], "addressed")
            finally:
                reopened.close()


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
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        values = {'Content-Type': 'application/json'} if data is not None else {}
        # W1: case routes require a live session; signin_demo signs in as the seeded demo clinician.
        values["Cookie"] = self._cookie
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


class AttributionRulePromptTests(unittest.TestCase):
    def test_build_prompt_contains_attribution_rule(self):
        prompt = build_prompt("evidence-summary", "What does the source report?", [], [])
        sentence = (
            "Attribute each claim to its sources through the citations array only. "
            "Do not write source version numbers in the claim text itself, neither "
            '"Source version N" nor "version N"; the citation identifies the source.'
        )
        # The prompt joins lines with newlines; normalise whitespace first.
        self.assertIn(sentence, " ".join(prompt.split()))


if __name__ == '__main__':
    unittest.main()
