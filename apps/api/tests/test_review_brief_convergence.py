"""Cross-owner HTTP acceptance; independently authored fictional sources only."""
import hashlib

from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture
from test_canonical_review_flow import create_question, RETURN_REASON


class ReviewBriefConvergenceTests(SourceVersionFixture):
    def seed(self, base):
        patient = self.setup_case(base)
        status, original, _ = self.ingest(base, patient)
        self.assertEqual(status, 201, original)
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_queue_read", "review_return", "source_brief_export",
        ))
        self.write()
        question, _ = create_question(self, base, patient, original["source_id"])
        prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
        status, listing, _ = request(base, prefix + "/questions", token=TOKEN_A)
        self.assertEqual(status, 200, listing)
        saved = listing["questions"][0]
        brief_intent = {
            "synthetic": True,
            "source_snapshot_contract": saved["source_snapshot_contract"],
            "expected_source_snapshot_sha256": saved["source_snapshot_sha256"],
            "expected_preflight_sha256": saved["preflight_sha256"],
        }
        return patient, prefix, question, brief_intent

    def test_return_and_brief_share_source_history_across_amendment_and_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient, prefix, question, brief_intent = self.seed(base)
            brief_url = prefix + f"/questions/{question}/brief"
            status, before, _ = request(base, brief_url, token=TOKEN_A, body=brief_intent)
            self.assertEqual(status, 200, before)
            status, queue, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, queue)
            item = queue["items"][0]
            self.assertEqual(item["source_id"], before["selected_source"]["source_id"])
            self.assertEqual(item["source_snapshot_sha256"], before["source_snapshot_sha256"])
            return_intent = {"synthetic": True, "request_key": "CONVERGED-RETURN",
                             "expected_queue_fingerprint": item["queue_fingerprint"],
                             "reason": RETURN_REASON}
            return_url = prefix + f"/questions/{question}/return-for-verification"
            status, returned, _ = request(base, return_url, token=TOKEN_A, body=return_intent)
            self.assertEqual(status, 201, returned)
            status, after, _ = request(base, brief_url, token=TOKEN_A, body=brief_intent)
            self.assertEqual(status, 200, after)
            self.assertEqual(after["question"], before["question"])
            self.assertEqual(after["selected_source"], before["selected_source"])
            self.assertNotEqual(after["access_receipt_id"], before["access_receipt_id"])
            self.assertFalse(after["clinical_approval"])
            self.assertFalse(after["biomedical_evidence_included"])
            self.assertEqual(after["body_sha256"], hashlib.sha256(after["body"].encode()).hexdigest())
            status, recorded, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, recorded)
            self.assertEqual(recorded["items"][0]["current_return_receipt_id"], returned["receipt_id"])
            self.assertEqual(recorded["items"][0]["queue_fingerprint"], item["queue_fingerprint"])
            history = recorded["receipts"]
            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual(status, 201, amendment)
            status, withheld, _ = request(base, brief_url, token=TOKEN_A, body=brief_intent)
            self.assertEqual(status, 409, withheld)
            self.assertEqual(set(withheld), {"detail"})

        # New app and HTTP server, same database and source/review owners.
        with running_server(create_app(self.settings)) as base:
            status, queue, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, queue)
            self.assertEqual(queue["receipts"], history)
            self.assertEqual(queue["items"][0]["review_state"], "source_reassessment_required")
            status, retried, _ = request(base, return_url, token=TOKEN_A, body=return_intent)
            self.assertEqual(status, 200, retried)
            self.assertEqual(retried["receipt_id"], returned["receipt_id"])
            self.assertTrue(retried["duplicate"])
            status, withheld, _ = request(base, brief_url, token=TOKEN_A, body=brief_intent)
            self.assertEqual(status, 409, withheld)
            source_id = before["selected_source"]["source_id"]
            status, original, _ = request(base, prefix + f"/sources/{source_id}", token=TOKEN_A)
            self.assertEqual(status, 200, original)
            self.assertEqual(original["original_text"], ORIGINAL)

    def test_export_and_operational_review_grants_remain_independent(self):
        with running_server(create_app(self.settings)) as base:
            _, prefix, question, intent = self.seed(base)
            brief_url = prefix + f"/questions/{question}/brief"
            self.creds[0]["actions"].remove("source_brief_export")
            self.write()
            self.assertEqual(request(base, brief_url, token=TOKEN_A, body=intent)[0], 404)
            status, queue, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, queue)
            self.creds[0]["actions"].append("source_brief_export")
            for action in ("review_queue_read", "review_return", "composer_context_read"):
                self.creds[0]["actions"].remove(action)
            self.write()
            self.assertEqual(request(base, prefix + "/review-queue", token=TOKEN_A)[0], 404)
            status, brief, _ = request(base, brief_url, token=TOKEN_A, body=intent)
            self.assertEqual(status, 200, brief)
            self.assertFalse(brief["clinical_approval"])
