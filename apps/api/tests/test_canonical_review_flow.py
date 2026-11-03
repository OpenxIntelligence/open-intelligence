"""Actual PG16/HTTP convergence of canonical questions and nonterminal returns.

All source text, questions and return reasons are independently fictional.
Only the shared fixture is inherited; no upstream test methods are duplicated.
"""
import unittest

from sqlalchemy import text

from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import AMENDED, SourceVersionFixture


RETURN_REASON = "Please independently verify this fictional source quotation and uncertainty."


def create_question(test, base, patient, source_id, *, line=8,
                    request_key="CANONICAL-REVIEW-QUESTION-V1"):
    """Reach the review boundary through the already connected canonical API."""
    prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
    status, world, _ = request(base, prefix + "/world-model", token=TOKEN_A)
    test.assertEqual(status, 200, world)
    test.assertEqual(world["contract"], "oi.pg-source-world-model/1")
    question = "Which independently fictional source details require verification?"
    status, prepared, _ = request(
        base, prefix + "/composer/source-preflight", token=TOKEN_A,
        body={"synthetic": True, "source_id": source_id, "source_line": line,
              "question": question,
              "expected_source_snapshot_sha256": world["snapshot_fingerprint"]},
    )
    test.assertEqual(status, 200, prepared)
    test.assertEqual(prepared["source_snapshot_contract"], "oi.pg-source-world-model/1")
    status, saved, _ = request(
        base, prefix + "/questions", token=TOKEN_A,
        body={"synthetic": True, "request_key": request_key,
              "source_id": source_id, "source_line": line, "question": question,
              "expected_source_snapshot_sha256": world["snapshot_fingerprint"],
              "expected_preflight_sha256": prepared["preflight_sha256"]},
    )
    test.assertEqual(status, 201, saved)
    test.assertFalse(saved["duplicate"])
    return saved["question_id"], world["snapshot_fingerprint"]


class CanonicalReviewFlowHTTPTests(SourceVersionFixture):
    def review_counts(self, patient):
        with self.engine.connect() as connection:
            receipts = connection.execute(text(
                "SELECT count(*) FROM investigation.question_review_receipts "
                "WHERE patient_id=:patient"
            ), {"patient": patient}).scalar_one()
            events = connection.execute(text(
                "SELECT count(*) FROM identity.identity_domain_events "
                "WHERE patient_id=:patient "
                "AND event_type='investigation.review.returned_for_verification'"
            ), {"patient": patient}).scalar_one()
        return receipts, events

    def test_canonical_question_return_keeps_its_identity_after_amendment(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, original, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, original)
            self.creds[0]["actions"].extend((
                "composer_context_read", "question_create", "question_read",
            ))
            self.write()
            question_id, snapshot = create_question(
                self, base, patient, original["source_id"]
            )
            prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
            queue_url = prefix + "/review-queue"

            # The unchanged base supports the entire question setup above.
            # Introduce new actions only at the missing review boundary.
            self.creds[0]["actions"].extend(("review_queue_read", "review_return"))
            self.write()
            status, queue, _ = request(base, queue_url, token=TOKEN_A)
            self.assertEqual(status, 200, queue)
            self.assertEqual(queue["contract"], "oi.synthetic-question-review-return-queue/2")
            self.assertRegex(queue["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertEqual(len(queue["items"]), 1)
            self.assertEqual(queue["receipts"], [])
            item = queue["items"][0]
            self.assertEqual(item["question_id"], question_id)
            self.assertEqual(item["source_id"], original["source_id"])
            self.assertEqual(item["source_line"], 8)
            self.assertEqual(item["source_snapshot_sha256"], snapshot)
            self.assertEqual(item["source_snapshot_contract"], "oi.pg-source-world-model/1")
            self.assertEqual(item["queue_fingerprint_contract"], "oi.synthetic-source-review-return/2")
            self.assertEqual(item["review_state"], "awaiting_independent_verification")
            fingerprint = item["queue_fingerprint"]
            self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
            for field in ("external_notification_sent", "reviewer_identity_verified",
                          "clinical_approval", "review_completion_supported"):
                self.assertIs(queue[field], False)

            status, repeated, _ = request(base, queue_url, token=TOKEN_A)
            self.assertEqual(status, 200, repeated)
            self.assertNotEqual(repeated["access_receipt_id"], queue["access_receipt_id"])
            self.assertEqual(repeated["items"][0]["queue_fingerprint"], fingerprint)

            return_url = prefix + f"/questions/{question_id}/return-for-verification"
            intent = {"synthetic": True, "request_key": "CANONICAL-RETURN-V1",
                      "expected_queue_fingerprint": fingerprint, "reason": RETURN_REASON}
            status, returned, _ = request(base, return_url, token=TOKEN_A, body=intent)
            self.assertEqual(status, 201, returned)
            self.assertEqual(returned["question_id"], question_id)
            self.assertFalse(returned["duplicate"])
            receipt_id = returned["receipt_id"]
            self.assertRegex(receipt_id, r"^REVIEW-[0-9A-F]{32}$")
            status, duplicate, _ = request(base, return_url, token=TOKEN_A, body=intent)
            self.assertEqual(status, 200, duplicate)
            self.assertEqual(duplicate, {"receipt_id": receipt_id,
                                        "question_id": question_id, "duplicate": True})
            # Source access receipts may be added; the return effect is singular.
            self.assertEqual(self.review_counts(patient), (1, 1))
            status, recorded, _ = request(base, queue_url, token=TOKEN_A)
            self.assertEqual(status, 200, recorded)
            self.assertEqual(recorded["items"][0]["review_state"],
                             "returned_for_independent_verification")
            self.assertEqual(recorded["items"][0]["current_return_receipt_id"], receipt_id)
            self.assertEqual(len(recorded["receipts"]), 1)
            receipt = recorded["receipts"][0]
            self.assertEqual(receipt["receipt_id"], receipt_id)
            self.assertEqual(receipt["source_snapshot_contract"], "oi.pg-source-world-model/1")
            self.assertEqual(receipt["queue_fingerprint_contract"], "oi.synthetic-source-review-return/2")
            self.assertEqual(receipt["action"], "returned")
            self.assertEqual(receipt["reason"], RETURN_REASON)
            self.assertFalse(receipt["clinical_approval"])
            self.assertFalse(receipt["reviewer_identity_verified"])
            self.assertFalse(receipt["external_notification_sent"])

            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual(status, 201, amended)
            status, after, _ = request(base, queue_url, token=TOKEN_A)
            self.assertEqual(status, 200, after)
            historical = after["items"][0]
            self.assertEqual(historical["question_id"], question_id)
            self.assertEqual(historical["source_id"], original["source_id"])
            self.assertEqual(historical["source_version"], 1)
            self.assertEqual(historical["source_line"], 8)
            self.assertEqual(historical["source_snapshot_sha256"], snapshot)
            self.assertEqual(historical["review_state"], "source_reassessment_required")
            self.assertIsNone(historical["queue_fingerprint"])
            self.assertIsNone(historical["current_return_receipt_id"])
            self.assertEqual((historical["return_count"], historical["prior_return_count"]), (0, 1))
            self.assertEqual(after["receipts"], recorded["receipts"])
            status, refused, _ = request(
                base, return_url, token=TOKEN_A,
                body={**intent, "request_key": "STALE-NEW-RETURN"},
            )
            self.assertEqual(status, 409, refused)
            status, recovered, _ = request(base, return_url, token=TOKEN_A, body=intent)
            self.assertEqual(status, 200, recovered)
            self.assertEqual(recovered, duplicate)
            self.assertEqual(self.review_counts(patient), (1, 1))

            fresh_question, _ = create_question(
                self, base, patient, amended["source_id"], line=9,
                request_key="CANONICAL-REVIEW-QUESTION-V2",
            )
            status, final, _ = request(base, queue_url, token=TOKEN_A)
            self.assertEqual(status, 200, final)
            self.assertEqual(len(final["items"]), 2)
            current = next(row for row in final["items"] if row["question_id"] == fresh_question)
            self.assertEqual(current["source_id"], amended["source_id"])
            self.assertEqual(current["source_line"], 9)
            self.assertEqual(current["review_state"], "awaiting_independent_verification")
            self.assertIsNone(current["current_return_receipt_id"])
            self.assertEqual((current["return_count"], current["prior_return_count"]), (0, 0))
            self.assertEqual(final["receipts"], recorded["receipts"])
            self.assertEqual(self.review_counts(patient), (1, 1))


if __name__ == "__main__":
    unittest.main()
