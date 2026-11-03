"""Real HTTP PDF/PWM/evidence/review continuity with no live model or sources.

All records, evidence passages and provider outputs below are independently
authored fiction. Only call_meta_api is stubbed: request validation, prompt
construction, citation checks, persistence, permissions and reads are real.
The HTTP mode named ``live`` exercises that production handler branch against
the in-process provider double; it is not evidence of a live model evaluation.
"""
from __future__ import annotations

import base64
import copy
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from open_intelligence.__main__ import Handler
from open_intelligence.store import CaseStore
from pdf_fixtures import text_pdf


CASE = "CASE-ALPHA"
SUPPORT = "Supporting fictional passage keeps the missing result unresolved."
COUNTER = "Contradicting fictional passage disputes treating missing data as a negative result."
DISPLAY_ONLY = "DISPLAY_ONLY_FICTIONAL_TEXT must never enter the provider prompt."
METADATA_ONLY = "METADATA_ONLY_FICTIONAL_TITLE"
TEST_OPERATOR_KEY = "synthetic-provider-double-not-a-real-credential"
PERMISSIONS = {
    item: {use: "allowed" for use in ("store", "display", "ml_use")}
    for item in ("metadata", "full_text")
}


class PdfWorldModelInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / "independent-fictional-workflow.sqlite")
        store = CaseStore(self.db_path)
        store.close()
        self.server = None
        self.start_server()
        self.addCleanup(self.stop_server)
        for case in (CASE, "CASE-BETA"):
            self.api("/api/cases", {"case_id": case, "label": "Independent fictional " + case}, expected=201)
        self.raw, self.preview, self.source = self.import_pdf()
        self.question_id = self.api(f"/api/cases/{CASE}/questions", {
            "question": "Which original passages and fictional evidence leave this question unresolved?"
        }, expected=201)["question_id"]
        self.brokers = {}
        for key, relation, excerpt, title, permissions in (
            ("support", "supports", SUPPORT, "Independent fictional supporting item", PERMISSIONS),
            ("counter", "contradicts", COUNTER, "Independent fictional contradicting item", PERMISSIONS),
            ("metadata", "context", None, METADATA_ONLY, {"metadata": PERMISSIONS["metadata"]}),
            ("display", "context", DISPLAY_ONLY, "DISPLAY_ONLY_FICTIONAL_TITLE", {
                item: {"store": "allowed", "display": "allowed", "ml_use": "denied"}
                for item in ("metadata", "full_text")
            }),
        ):
            rights = self.api("/api/rights/sources", {
                "source_key": "PWM-" + key.upper(), "owner": "Independent fictional test author",
                "version_label": "v1", "retrieved_at": "2026-07-03", "permissions": permissions,
            }, expected=201)
            link = self.api(f"/api/cases/{CASE}/broker-links", {
                "question_id": self.question_id, "rights_source_id": rights["rights_source_id"],
                "relation": relation, "applicability": "limited",
                "rationale": "Independent fictional comparison with unresolved applicability.",
                "citation_title": title, "excerpt": excerpt,
            }, expected=201)
            self.brokers[key] = {**rights, **link}

    def start_server(self):
        handler = type("PdfWorldModelIntegrationHandler", (Handler,), {
            "db_path": self.db_path, "log_message": lambda *_args: None,
            "allow_crossref_live": False,
        })
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)
        self.thread.start()

    def stop_server(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
            self.server = None

    def restart(self):
        self.stop_server()
        self.start_server()

    def request(self, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection = HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request("GET" if body is None else "POST", path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            result = json.loads(raw) if "application/json" in response.getheader("Content-Type", "") else raw
            return response.status, result, dict(response.getheaders())
        finally:
            connection.close()

    def api(self, path, payload=None, *, expected=200):
        status, result, _ = self.request(path, payload)
        self.assertEqual(status, expected, result)
        return result

    def ledger(self):
        store = CaseStore(self.db_path)
        try:
            return tuple(store.db.iterdump())
        finally:
            store.close()

    def model_history(self):
        store = CaseStore(self.db_path)
        try:
            return [tuple(row) for row in store.db.execute(
                "SELECT id,claims_json FROM investigations WHERE case_id=? ORDER BY id", (CASE,))]
        finally:
            store.close()

    def import_pdf(self, *, amended=False):
        marker = "Marker P remains pending." if amended else "Marker P was not assessed."
        raw = text_pdf([["Original fictional record for software tests."],
                        [marker, "Assay Q remains pending."]])
        upload = {"filename": "amended.pdf" if amended else "original.pdf",
                  "content_base64": base64.b64encode(raw).decode("ascii")}
        preview = self.api(f"/api/cases/{CASE}/documents/preview", upload)
        metadata = {"document_id": "PDF-WORLD", "kind": "pathology",
                    "event_date": "2026-07-01", "issued_at": "2026-07-02",
                    "specimen_id": "SYNTH-SPECIMEN", "manual_transcription_confirmed": True}
        if amended:
            metadata["amends_version"] = 1
        saved = self.api(f"/api/cases/{CASE}/documents", {
            **upload, "expected_sha256": preview["sha256"],
            "expected_extraction_sha256": preview["extraction_sha256"],
            "confirmed_case_id": CASE, "metadata": metadata,
            "findings": [
                {"key": "marker-p", "state": "pending" if amended else "not-assessed", "quote": marker, "line": 2},
                {"key": "assay-q", "state": "pending", "quote": "Assay Q remains pending.", "line": 3},
            ],
        })
        return raw, preview, saved

    def composer(self):
        return self.api(f"/api/cases/{CASE}/composer/context?question_id={self.question_id}")

    def candidate_payload(self):
        return {
            "claims": [
                {"text": "Selected fictional passage: 'Marker P was not assessed.'",
                 "support": "context", "citations": [{"type": "source", "id": self.source["source_id"]}],
                 "uncertainty": "high", "limits": "Constructed provider double; manual selection is unreviewed."},
                {"text": "Fictional support quotation: '" + SUPPORT + "'", "support": "supports",
                 "citations": [{"type": "broker", "id": self.brokers["support"]["broker_link_id"]}],
                 "uncertainty": "high", "limits": "Independent fiction, not medical evidence or a live model result."},
                {"text": "Fictional counterevidence quotation: '" + COUNTER + "'", "support": "contradicts",
                 "citations": [{"type": "broker", "id": self.brokers["counter"]["broker_link_id"]}],
                 "uncertainty": "high", "limits": "Independent fiction, not medical evidence or a live model result."},
            ],
            "abstentions": [{"topic": "Meaning of the unresolved fictional findings", "reason": "conflicting_evidence"}],
        }

    def run_provider_double(self, *, during_call=None):
        context = self.composer()
        captured = []
        def provider(prompt, key):
            self.assertEqual(key, TEST_OPERATOR_KEY)
            captured.append(prompt)
            if during_call is not None:
                during_call()
            return copy.deepcopy(self.candidate_payload())
        # Set only a known noncredential so the real environment-key reader runs.
        # No extraction, projection, prompt, rights, validation or store is mocked.
        with patch.dict(os.environ, {"META_API_KEY": TEST_OPERATOR_KEY}), \
                patch("open_intelligence.__main__.call_meta_api", side_effect=provider) as stub:
            status, result, _ = self.request(f"/api/cases/{CASE}/investigations", {
                "question_id": self.question_id, "template": "evidence-summary", "mode": "live",
                "context_fingerprint": context["fingerprint"],
            })
            self.assertEqual(stub.call_count, 1)
        self.assertEqual(len(captured), 1)
        return status, result, captured[0], context

    def human_report(self):
        summary = "Human-authored fictional discussion draft: the selected marker and assay remain unresolved."
        result = self.api(f"/api/cases/{CASE}/snapshots", {
            "question_id": self.question_id, "summary": summary,
            "source_ids": [self.source["source_id"]],
            "broker_link_ids": [self.brokers[key]["broker_link_id"] for key in ("support", "counter")],
        }, expected=201)
        return result["snapshot_id"], summary

    def acknowledge(self, snapshot_id):
        self.api(f"/api/cases/{CASE}/snapshots/{snapshot_id}/review", {
            "reviewer_label": "Unverified fictional reviewer",
        })

    def assert_pdf_projection(self, model, source, preview, *, amended=False):
        self.assertEqual(model["case_id"], CASE)
        self.assertTrue(model["synthetic"])
        self.assertEqual(model["clinical_interpretation"], "not_generated")
        self.assertEqual(model["summary"]["current_sources"], 1)
        self.assertEqual(model["summary"]["current_observations"], 2)
        self.assertEqual(model["summary"]["unresolved_observations"], 2)
        observations = {item["finding_key"]: item for item in model["observations"]}
        self.assertEqual(observations["marker-p"]["reported_state"], "pending" if amended else "not-assessed")
        self.assertEqual(observations["assay-q"]["reported_state"], "pending")
        self.assertEqual({item["assertion_id"] for item in model["unresolved"]},
                         {item["assertion_id"] for item in observations.values()})
        for item in observations.values():
            self.assertEqual(item["source_version_id"], source["source_id"])
            self.assertEqual(item["source_sha256"], preview["sha256"])
            self.assertEqual(item["classification_origin"], "user_selected")
            self.assertEqual(item["clinical_review"], "not_performed")
            self.assertEqual(item["annotation_method"], "manual-exact-extraction-line-selection")
            self.assertTrue(item["transcription_review_sha256"])
            self.assertEqual(item["text_origin"], "pdf_extraction")
            self.assertEqual(item["extraction_sha256"], preview["extraction_sha256"])
            self.assertEqual(item["source_page"], 2)
            self.assertEqual(item["page_line"], item["source_line"] - 1)
            self.assertEqual(item["page_text_sha256"], preview["pages"][1]["sha256"])
            self.assertIsNone(item["clinical_meaning"])
            self.assertEqual(item["review_state"], "not_established")
        original = model["current_sources"][0]
        self.assertEqual(original["classification_origin"], "user_selected")
        self.assertEqual(original["text_origin"], "pdf_extraction")
        self.assertEqual(original["extraction_sha256"], preview["extraction_sha256"])

    def test_http_record_and_actual_prompt_preserve_pdf_manual_and_evidence_boundaries(self):
        before_reads = self.ledger()
        record = self.api(f"/api/cases/{CASE}/world-model")
        self.assert_pdf_projection(record, self.source, self.preview)
        self.assertIn(self.question_id, record["review_needed"]["open_question_ids"])
        other = self.api("/api/cases/CASE-BETA/world-model")
        self.assertEqual(other["observations"], [])
        self.assertNotIn("PDF-WORLD", json.dumps(other))
        context = self.composer()
        self.assertEqual(self.ledger(), before_reads)
        rows = {item["id"]: item for item in context["external_evidence"]}
        eligible = {item["id"] for item in rows.values() if item["model_eligible"]}
        self.assertEqual(eligible, {self.brokers[key]["broker_link_id"] for key in ("support", "counter")})
        for key in ("metadata", "display"):
            row = rows[self.brokers[key]["broker_link_id"]]
            self.assertFalse(row["model_eligible"])
            self.assertTrue(row["withheld_reason"])
        self.assertIsNone(rows[self.brokers["metadata"]["broker_link_id"]]["excerpt"])

        status, candidate, prompt, used_context = self.run_provider_double()
        self.assertEqual(status, 201, candidate)
        for text in ("user_selected_status=not-assessed", "user_selected_status=pending",
                     "classification_origin=user_selected", "clinical_review=not_performed",
                     "text_origin=pdf_extraction", "source_page=2", "page_line=1", "extraction_line=2",
                     self.preview["extraction_sha256"], "Marker P was not assessed.", "Assay Q remains pending.",
                     SUPPORT, COUNTER, "relation=supports", "relation=contradicts"):
            self.assertIn(text, prompt)
        for text in (METADATA_ONLY, DISPLAY_ONLY, "DISPLAY_ONLY_FICTIONAL_TITLE", "certainty=negative"):
            self.assertNotIn(text, prompt)
        self.assertEqual(candidate["kind"], "hypothesis")
        self.assertEqual(candidate["review_state"], "pending")
        self.assertEqual(len(candidate["claims"]), 3)
        self.assertEqual(candidate["dropped"], [])
        self.assertEqual([claim["citations"] for claim in candidate["claims"]],
                         [claim["citations"] for claim in self.candidate_payload()["claims"]])
        self.assertEqual({receipt["broker_link_id"] for receipt in candidate["input_receipts"]}, eligible)
        self.assertEqual({receipt["relation"] for receipt in candidate["input_receipts"]}, {"supports", "contradicts"})
        self.assertEqual(candidate["input_context"]["context_fingerprint"], used_context["fingerprint"])
        self.assertEqual(candidate["input_context"]["prompt_sha256"], hashlib.sha256(prompt.encode()).hexdigest())
        after = self.api(f"/api/cases/{CASE}/world-model")
        self.assertEqual(after["observations"], record["observations"])
        self.assertIn(self.question_id, after["review_needed"]["open_question_ids"])
        self.assertEqual(after["review_needed"]["draft_snapshot_ids"], [])
        self.assertEqual(self.api(f"/api/cases/{CASE}/state")["snapshots"], [])

    def test_explicit_human_report_amendment_and_restart_preserve_both_pdf_versions(self):
        status, candidate, _, old_context = self.run_provider_double()
        self.assertEqual(status, 201, candidate)
        snapshot_id, summary = self.human_report()
        record = self.api(f"/api/cases/{CASE}/world-model")
        self.assertIn(snapshot_id, record["review_needed"]["draft_snapshot_ids"])
        self.assertIn(self.question_id, record["review_needed"]["open_question_ids"])
        self.acknowledge(snapshot_id)
        self.assertNotIn(self.question_id,
                         self.api(f"/api/cases/{CASE}/world-model")["review_needed"]["open_question_ids"])
        model = self.api(f"/api/cases/{CASE}/investigations/{candidate['id']}")
        self.assertEqual(model["review_state"], "pending")
        self.assertEqual(model["kind"], "hypothesis")

        amended_raw, amended_preview, amended_source = self.import_pdf(amended=True)
        record = self.api(f"/api/cases/{CASE}/world-model")
        self.assert_pdf_projection(record, amended_source, amended_preview, amended=True)
        self.assertEqual(record["history"][0]["source_version_id"], self.source["source_id"])
        self.assertEqual(record["history"][0]["source_sha256"], self.preview["sha256"])
        self.assertEqual(record["history"][0]["extraction_sha256"], self.preview["extraction_sha256"])
        self.assertIn(snapshot_id, record["review_needed"]["stale_snapshot_ids"])
        self.assertIn(self.question_id, record["review_needed"]["open_question_ids"])
        model = self.api(f"/api/cases/{CASE}/investigations/{candidate['id']}")
        self.assertTrue(model["stale"])
        self.assertTrue(model["output_withheld"])
        with patch("open_intelligence.__main__.call_meta_api") as unused:
            status, blocked, _ = self.request(f"/api/cases/{CASE}/investigations", {
                "question_id": self.question_id, "template": "evidence-summary", "mode": "live",
                "context_fingerprint": old_context["fingerprint"],
            })
        self.assertEqual(status, 422)
        self.assertIn("stale", blocked["error"])
        unused.assert_not_called()
        exported = self.api(f"/api/cases/{CASE}/snapshots/{snapshot_id}/export").decode()
        for text in ("**stale**", summary, "Marker P was not assessed.", self.preview["sha256"],
                     self.preview["extraction_sha256"], "classification_origin=user_selected"):
            self.assertIn(text, exported)
        self.assertNotIn("Marker P remains pending.", exported)

        self.restart()
        self.assertEqual(self.api(f"/api/cases/{CASE}/world-model"), record)
        for source_id, raw, extraction in (
            (self.source["source_id"], self.raw, self.preview["extraction_sha256"]),
            (amended_source["source_id"], amended_raw, amended_preview["extraction_sha256"]),
        ):
            self.assertEqual(self.api(f"/api/cases/{CASE}/sources/{source_id}/download"), raw)
            readable = self.api(f"/api/cases/{CASE}/sources/{source_id}")
            self.assertEqual(readable["text_origin"], "pdf_extraction")
            self.assertEqual(readable["extraction_sha256"], extraction)
        state = self.api(f"/api/cases/{CASE}/state")
        self.assertEqual(state["snapshots"][0]["summary"], summary)
        self.assertEqual(state["snapshots"][0]["state"], "stale")

    def test_permission_withdrawal_withholds_derived_output_without_erasing_history(self):
        status, candidate, _, _ = self.run_provider_double()
        self.assertEqual(status, 201, candidate)
        snapshot_id, summary = self.human_report()
        self.acknowledge(snapshot_id)
        model_history = self.model_history()
        before_record = self.api(f"/api/cases/{CASE}/world-model")
        self.api(f"/api/rights/sources/{self.brokers['support']['rights_source_id']}/revoke", {
            "reason": "Independent fictional source permission withdrawn after the test run.",
        })
        withheld = self.api(f"/api/cases/{CASE}/investigations/{candidate['id']}")
        self.assertTrue(withheld["stale"])
        self.assertTrue(withheld["output_withheld"])
        for key in ("claims", "abstentions", "dropped"):
            self.assertEqual(withheld[key], [])
        self.assertEqual(withheld["input_receipts"], candidate["input_receipts"])
        self.assertNotIn(SUPPORT, json.dumps(withheld))
        self.assertNotIn(COUNTER, json.dumps(withheld))
        self.assertEqual(self.model_history(), model_history)
        record = self.api(f"/api/cases/{CASE}/world-model")
        self.assertEqual(record["observations"], before_record["observations"])
        self.assertIn(snapshot_id, record["review_needed"]["stale_snapshot_ids"])
        self.assertIn(self.question_id, record["review_needed"]["open_question_ids"])
        state = self.api(f"/api/cases/{CASE}/state")
        withdrawn = next(row for row in state["broker_links"] if row["id"] == self.brokers["support"]["broker_link_id"])
        self.assertIsNone(withdrawn["excerpt"])
        self.assertIsNone(withdrawn["citation_title"])
        self.assertEqual(state["snapshots"][0]["summary"], summary)
        refreshed = {item["id"]: item for item in self.composer()["external_evidence"]}
        self.assertFalse(refreshed[self.brokers["support"]["broker_link_id"]]["model_eligible"])
        self.assertTrue(refreshed[self.brokers["counter"]["broker_link_id"]]["model_eligible"])
        self.restart()
        self.assertTrue(self.api(f"/api/cases/{CASE}/investigations/{candidate['id']}")["output_withheld"])
        self.assertEqual(self.model_history(), model_history)
        self.assertEqual(self.api(f"/api/cases/{CASE}/sources/{self.source['source_id']}/download"), self.raw)

    def test_permission_change_during_provider_call_refuses_persistence_and_model_promotion(self):
        record = self.api(f"/api/cases/{CASE}/world-model")
        def withdraw_during_call():
            self.api(f"/api/rights/sources/{self.brokers['support']['rights_source_id']}/revoke", {
                "reason": "Independent fictional rights withdrawal during the provider double.",
            })
        status, refused, prompt, _ = self.run_provider_double(during_call=withdraw_during_call)
        self.assertEqual(status, 422, refused)
        self.assertIn("stale", refused["error"])
        self.assertIn(SUPPORT, prompt)
        self.assertIn("classification_origin=user_selected", prompt)
        self.assertEqual(self.api(f"/api/cases/{CASE}/investigations")["investigations"], [])
        self.assertEqual(self.model_history(), [])
        self.assertEqual(self.api(f"/api/cases/{CASE}/state")["snapshots"], [])
        after = self.api(f"/api/cases/{CASE}/world-model")
        self.assertEqual(after["observations"], record["observations"])
        self.assertIn(self.question_id, after["review_needed"]["open_question_ids"])
        self.assertEqual(self.api(f"/api/cases/{CASE}/sources/{self.source['source_id']}/download"), self.raw)


if __name__ == "__main__":
    unittest.main()
