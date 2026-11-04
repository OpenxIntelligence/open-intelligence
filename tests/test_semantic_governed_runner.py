"""Loopback-only model interface and independent scoring checks: no real inference."""
from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import semantic_local_model_runner as runner
import semantic_model_scorer as scorer
from semantic_question_packet import make_packet
from semantic_benchmark import digest

CHALLENGE = json.loads((ROOT / "tests/fixtures/semantic_adversarial_challenge_v2.json").read_text())
ORIGINAL = json.loads((ROOT / "tests/fixtures/semantic_benchmark_cases_v1.json").read_text())


def model_reply(data, *, finish="stop") -> bytes:
    return json.dumps({
        "choices": [{"message": {"role": "assistant", "content": json.dumps(data)},
                     "finish_reason": finish}],
        "usage": {"prompt_tokens": 7777, "completion_tokens": 8888},
    }, separators=(",", ":")).encode()


def make_full_run(packet):
    """Scripted fake model *test double*; never real vendor inference."""
    index = 0
    def sender(url, body, timeout):
        nonlocal index
        i = index
        index += 1
        req = json.loads(body)
        assert [m["role"] for m in req["messages"]] == ["system", "user"]
        assert req["messages"][1]["content"] == packet["tasks"][i]["question"]
        assert '"expected"' not in body.decode()
        assert '"category"' not in body.decode()
        assert "tools" not in req and not req["stream"]
        if i == 0:
            return model_reply({"status": "proposed", "concept": "source_version", "field": "source_id"})
        if i in (50, 60):
            return model_reply({"status": "proposed", "concept": "source_version", "field": "source_id"})
        if i == 51:
            return b'{"choices":[{"message":{"role":"assistant","content":"not json"},"finish_reason":"stop"}]}'
        return model_reply({"status": "abstain"})
    return runner.evaluate_packet(packet, url="http://127.0.0.1:18763/v1/chat/completions",
                                  model_id="test-double-v1", sender=sender)


class ModelRunnerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = make_packet(CHALLENGE, ORIGINAL)

    def test_rejects_public_dns_urls_and_redirect_like_paths(self):
        for url in (
            "https://127.0.0.1:19999/v1/chat/completions",
            "http://localhost:19999/v1/chat/completions",
            "http://127.0.0.2:19999/v1/chat/completions",
            "http://192.168.1.4:19999/v1/chat/completions",
            "http://1.1.1.1:19999/v1/chat/completions",
            "http://127.0.0.1:19999/v1/chat/completions?redirect=1",
            "http://127.0.0.1:19999/v1/chat/completions#extra",
            "http://user:secret@127.0.0.1:19999/v1/chat/completions",
            "http://127.0.0.1:19999/debug",
            "http://127.0.0.1:80/v1/chat/completions",
            "http://127.0.0.1:65536/v1/chat/completions",
            "http://127.1:19999/v1/chat/completions",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                runner.endpoint_port(url)

    def test_valid_loopback_url(self):
        self.assertEqual(runner.endpoint_port("http://127.0.0.1:18763/v1/chat/completions"), 18763)

    def test_valid_proposal_keeps_only_allowlisted_metadata(self):
        result = runner.parse_model_output(model_reply({
            "status": "proposed", "concept": "source_version", "field": "source_id",
        }))
        self.assertEqual((result["status"], result["concept"], result["field"]), ("proposed", "source_version", "source_id"))
        self.assertEqual(len(result["response_sha256"]), 64)

    def test_valid_abstention_never_claims_clinical_authority(self):
        result = runner.parse_model_output(model_reply({"status": "abstain"}))
        self.assertEqual(set(result), {"status", "response_sha256"})
        self.assertEqual(result["status"], "abstain")

    def test_unallowlisted_mapping_is_invalid_not_abstained(self):
        for result in (
            {"status": "proposed", "concept": "source_version", "field": "patient_id"},
            {"status": "proposed", "concept": "patient_record", "field": "source_id"},
            {"status": "proposed", "concept": "source_version", "field": "source_id", "sql": "SELECT * FROM patients"},
            {"status": "clinician_approved"},
            {"status": "abstain", "clinical_approval": True},
        ):
            with self.subTest(result=result):
                outcome = runner.parse_model_output(model_reply(result))
                self.assertEqual(outcome["status"], "invalid")

    def test_truncated_or_malformed_or_duplicate_json_is_invalid(self):
        replies = [
            model_reply({"status": "abstain"}, finish="length"),
            model_reply({"status": "abstain"})[:-1],
            b'{"choices":[],"choices":[]}',
            b'not a JSON response',
            model_reply({"status": "proposed", "concept": "source_version", "field": "source_id"}) + b'\nEXTRA',
        ]
        for payload in replies:
            with self.subTest(payload=payload[:20]):
                self.assertEqual(runner.parse_model_output(payload)["status"], "invalid")

    def test_sender_gets_only_questions_not_gold(self):
        run = make_full_run(self.packet)
        self.assertTrue(run["complete"])
        self.assertEqual(run["attempted_questions"], 72)
        self.assertFalse(run["model_weights_verified"])
        self.assertFalse(run["nvidia_auto_ontology_verified"])
        self.assertFalse(run["raw_responses_retained"])
        self.assertFalse(run["cost_verified"])
        self.assertEqual(run["source_attestation"], "self_reported_unsigned")
        self.assertEqual(runner.validate_run(run, self.packet)["invalid"], 1)

    def test_partial_run_is_labeled_partial(self):
        def sender(_url, _body, _timeout):
            return model_reply({"status": "abstain"})
        run = runner.evaluate_packet(self.packet,
                                     url="http://127.0.0.1:18763/v1/chat/completions",
                                     model_id="local-test-double",
                                     sender=sender, max_tasks=3)
        self.assertFalse(run["complete"])
        self.assertEqual(run["attempted_questions"], 3)
        self.assertEqual(runner.validate_run(run, self.packet)["attempted"], 3)
        with self.assertRaisesRegex(ValueError, "Partial"):
            scorer.score_run(run, self.packet, CHALLENGE, ORIGINAL)

    def test_transport_error_is_not_silent_abstention(self):
        def sender(_url, _body, _timeout):
            raise ConnectionRefusedError("fictional loopback model unavailable")
        run = runner.evaluate_packet(self.packet,
                                     url="http://127.0.0.1:18763/v1/chat/completions",
                                     model_id="local-test-double", sender=sender, max_tasks=1)
        self.assertEqual(run["results"][0]["status"], "error")
        self.assertEqual(run["results"][0]["invalid_code"], "transport_failure")
        self.assertIsNone(run["results"][0]["response_sha256"])

    def test_invalid_parameters_never_invoke_sender(self):
        def sender(*_args):
            raise AssertionError("Sender should not be invoked")
        for opts in (
            {"url": "http://example.org:18763/v1/chat/completions", "model_id": "x"},
            {"url": "http://127.0.0.1:18763/v1/chat/completions", "model_id": "x", "max_tasks": 0},
            {"url": "http://127.0.0.1:18763/v1/chat/completions", "model_id": "x", "max_tasks": 73},
            {"url": "http://127.0.0.1:18763/v1/chat/completions", "model_id": "../not a model"},
        ):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                runner.evaluate_packet(self.packet, sender=sender, **opts)

    def test_tampered_model_receipt_rejected_even_with_same_fields(self):
        a = make_full_run(self.packet)
        a["results"][0]["field"] = "document_id"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            runner.validate_run(a, self.packet)

    def test_model_cannot_assert_nvidia_vendor_or_clinical_provenance(self):
        for key in ("nvidia_auto_ontology_verified", "model_weights_verified", "cost_verified"):
            r = make_full_run(self.packet)
            r[key] = True
            r["run_sha256"] = digest({k:v for k,v in r.items() if k!="run_sha256"})
            with self.subTest(flag=key), self.assertRaisesRegex(ValueError, "unverified capability"):
                runner.validate_run(r, self.packet)

    def test_scripted_real_http_loopback_receives_only_question_text(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                req = json.loads(raw)
                seen.append(req)
                data = model_reply({"status": "abstain"})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            result = runner.evaluate_packet(self.packet,
                         url=f"http://127.0.0.1:{port}/v1/chat/completions",
                         model_id="scripted-loopback-test-double",
                         max_tasks=1, timeout_s=2.0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["stream"], False)
        self.assertNotIn("tools", seen[0])
        self.assertEqual(seen[0]["messages"][1]["content"], self.packet["tasks"][0]["question"])
        self.assertEqual(result["results"][0]["status"], "abstain")


    def test_missing_or_null_completion_reason_is_not_accepted(self):
        for marker in ("omit", None):
            obj = json.loads(model_reply({"status": "abstain"}))
            if marker == "omit":
                obj["choices"][0].pop("finish_reason")
            else:
                obj["choices"][0]["finish_reason"] = None
            value = runner.parse_model_output(json.dumps(obj).encode())
            with self.subTest(reason=marker):
                self.assertEqual(value["status"], "invalid")
                self.assertEqual(value["invalid_code"], "truncated")

    def test_redirect_is_never_followed_even_to_same_loopback(self):
        hits = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return
            def do_POST(self):
                hits.append(self.path)
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions")
                self.end_headers()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            with self.assertRaises((ValueError, HTTPError)):
                runner.send_loopback(endpoint, runner.request_body(self.packet["tasks"][0], self.packet, "test-double"), 2.0)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
        self.assertEqual(len(hits), 1)


class SeparateGoldScorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = make_packet(CHALLENGE, ORIGINAL)

    def test_model_test_double_flags_unsafe_false_join_and_invalid_separately(self):
        run = make_full_run(self.packet)
        score = scorer.score_run(run, self.packet, CHALLENGE, ORIGINAL)
        self.assertEqual(score["positive_cases"], 36)
        self.assertEqual(score["negative_cases"], 36)
        self.assertEqual(score["counts"]["positive_correct"], 1)
        self.assertEqual(score["counts"]["positive_abstained"], 35)
        self.assertEqual(score["counts"]["negative_false_mapping"], 2)
        self.assertEqual(score["counts"]["negative_invalid"], 1)
        self.assertEqual(score["counts"]["negative_abstained"], 33)
        self.assertEqual(score["unsafe_false_mappings"], 1)
        self.assertEqual(score["false_join_mappings"], 1)
        self.assertTrue(score["experimental_stop_triggered"])
        self.assertEqual(set(score["experimental_stop_reasons"]),
                         {"unsafe_field_mapping", "false_join_mapping", "malformed_output"})
        self.assertFalse(score["nvidia_auto_ontology_model_verified"])
        self.assertFalse(score["independent_adjudication"])
        self.assertFalse(score["production_adoption_approved"])

    def test_unauthenticated_model_label_cannot_claim_provider(self):
        r = make_full_run(self.packet)
        r["declared_model_id"] = "nvidia/nemotron-not-really-tested"
        r["run_sha256"] = digest({k:v for k,v in r.items() if k!="run_sha256"})
        result = scorer.score_run(r, self.packet, CHALLENGE, ORIGINAL)
        self.assertFalse(result["provider_provenance_verified"])
        self.assertFalse(result["nvidia_auto_ontology_model_verified"])

    def test_changed_gold_reference_or_question_packet_rejected(self):
        run = make_full_run(self.packet)
        changed = copy.deepcopy(CHALLENGE)
        changed["cases"][0]["question"] = "Some unrelated fictional question"
        with self.assertRaises(ValueError):
            scorer.score_run(run, self.packet, changed, ORIGINAL)
        tampered = copy.deepcopy(self.packet)
        tampered["tasks"][0]["question"] = "Unreviewed private context"
        with self.assertRaises(ValueError):
            scorer.score_run(run, tampered, CHALLENGE, ORIGINAL)

    def test_wrong_ordered_run_case_rejected(self):
        run = make_full_run(self.packet)
        run["results"][0], run["results"][1] = run["results"][1], run["results"][0]
        run["run_sha256"] = digest({k:v for k,v in run.items() if k!="run_sha256"})
        with self.assertRaisesRegex(ValueError, "order or ID"):
            scorer.score_run(run, self.packet, CHALLENGE, ORIGINAL)

    def test_failed_transport_on_negative_is_not_safe_abstention(self):
        run = make_full_run(self.packet)
        i=50
        run["results"][i] = {
            "id": self.packet["tasks"][i]["id"], "status": "error",
            "invalid_code": "transport_failure", "latency_ms": 1.0,
            "response_sha256": None,
        }
        run["run_sha256"] = digest({k:v for k,v in run.items() if k!="run_sha256"})
        score = scorer.score_run(run, self.packet, CHALLENGE, ORIGINAL)
        self.assertEqual(score["negative_by_category"]["unsafe"]["transport_error"], 1)
        self.assertEqual(score["negative_by_category"]["unsafe"]["false_mapping"], 0)
        self.assertIn("transport_error", score["experimental_stop_reasons"])

    def test_all_abstained_is_not_claimed_as_successful_mapping(self):
        def always_abstain(_url, _body, _timeout):
            return model_reply({"status": "abstain"})
        run = runner.evaluate_packet(self.packet,
                                     url="http://127.0.0.1:18763/v1/chat/completions",
                                     model_id="test-double", sender=always_abstain)
        scored = scorer.score_run(run, self.packet, CHALLENGE, ORIGINAL)
        self.assertEqual(scored["counts"]["positive_correct"], 0)
        self.assertEqual(scored["counts"]["positive_abstained"], 36)
        self.assertEqual(scored["counts"]["negative_abstained"], 36)
        self.assertEqual(scored["correct_positive_rate"], 0)
        self.assertFalse(scored["production_adoption_approved"])


if __name__ == "__main__":
    unittest.main()
