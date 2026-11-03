"""Actual PG16/HTTP acceptance for one canonical source-question workflow.

The reports and question are independently fictional. Reuse only the shared
fixture, not a test class, so this adds no duplicate inherited test methods.
"""
import hashlib
import unittest

from sqlalchemy import text

from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


QUESTION = "What source evidence remains missing for this fictional marker?"


class CanonicalQuestionFlowHTTPTests(SourceVersionFixture):
    def question_counts(self, patient):
        with self.engine.connect() as connection:
            questions = connection.execute(text(
                "SELECT count(*) FROM investigation.source_questions "
                "WHERE patient_id=:patient AND case_id='CASE-ALPHA'"
            ), {"patient": patient}).scalar_one()
            created_events = connection.execute(text(
                "SELECT count(*) FROM identity.identity_domain_events "
                "WHERE patient_id=:patient "
                "AND event_type='investigation.question.created'"
            ), {"patient": patient}).scalar_one()
        return questions, created_events

    def test_canonical_snapshot_survives_receipt_churn_and_reopens_on_amendment(self):
        """Catch incompatible fingerprints, receipt-bound hashes, or retargeted history."""
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, imported, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, imported)
            original_id = imported["source_id"]
            prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"

            status, world, _ = request(base, prefix + "/world-model", token=TOKEN_A)
            self.assertEqual(status, 200, world)
            self.assertEqual(world["contract"], "oi.pg-source-world-model/1")
            self.assertEqual(world["observations"][0]["source_id"], original_id)
            self.assertEqual(world["observations"][0]["source_line"], 8)
            status, repeated_world, _ = request(
                base, prefix + "/world-model", token=TOKEN_A
            )
            self.assertEqual(status, 200, repeated_world)
            fingerprint = world["snapshot_fingerprint"]
            self.assertEqual(repeated_world["snapshot_fingerprint"], fingerprint)
            self.assertRegex(world["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertRegex(repeated_world["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertNotEqual(repeated_world["access_receipt_id"],
                                world["access_receipt_id"])

            # Baseline source setup uses only already-supported action names.
            # Grant the new consumer actions at its boundary, so tests-first
            # failure is the unsupported preflight/question behavior, not setup.
            self.creds[0]["actions"].extend((
                "composer_context_read", "question_create", "question_read",
            ))
            self.write()
            preparation = {
                "synthetic": True,
                "expected_source_snapshot_sha256": fingerprint,
                "source_id": original_id,
                "source_line": 8,
                "question": QUESTION,
            }
            status, prepared, _ = request(
                base, prefix + "/composer/source-preflight",
                token=TOKEN_A, body=preparation,
            )
            self.assertEqual(status, 200, prepared)
            self.assertEqual(prepared["contract"], "oi.synthetic-source-composer-preflight/2")
            self.assertEqual(prepared["source_snapshot_contract"], "oi.pg-source-world-model/1")
            self.assertEqual(prepared["source_snapshot_sha256"], fingerprint)
            self.assertEqual(prepared["selected_source"]["source_id"], original_id)
            self.assertEqual(prepared["selected_source"]["line"], 8)
            self.assertEqual(prepared["selected_source"]["sha256"],
                             hashlib.sha256(ORIGINAL.encode("utf-8")).hexdigest())
            self.assertEqual(prepared["selected_source"]["statement"],
                             "Fictional café <script>literal</script>.")
            self.assertFalse(prepared["model_execution_authorized"])
            self.assertFalse(prepared["clinical_approval"])
            self.assertRegex(prepared["preflight_sha256"], r"^[0-9a-f]{64}$")

            status, repeated_preflight, _ = request(
                base, prefix + "/composer/source-preflight",
                token=TOKEN_A, body=preparation,
            )
            self.assertEqual(status, 200, repeated_preflight)
            self.assertEqual(repeated_preflight["preflight_sha256"],
                             prepared["preflight_sha256"])
            self.assertRegex(prepared["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertRegex(repeated_preflight["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertNotEqual(repeated_preflight["access_receipt_id"],
                                prepared["access_receipt_id"])

            intent = {
                "synthetic": True,
                "request_key": "CANONICAL-QUESTION-ONE",
                "question": QUESTION,
                "source_id": original_id,
                "source_line": 8,
                "expected_source_snapshot_sha256": fingerprint,
                "expected_preflight_sha256": prepared["preflight_sha256"],
            }
            status, saved, _ = request(
                base, prefix + "/questions", token=TOKEN_A, body=intent
            )
            self.assertEqual(status, 201, saved)
            self.assertFalse(saved["duplicate"])
            question_id = saved["question_id"]
            status, retried, _ = request(
                base, prefix + "/questions", token=TOKEN_A, body=intent
            )
            self.assertEqual(status, 200, retried)
            self.assertEqual(retried, {"question_id": question_id, "duplicate": True})
            # Successful source reads may add their own receipts. Count only
            # the durable question and its one creation event.
            self.assertEqual(self.question_counts(patient), (1, 1))

            status, listing, _ = request(base, prefix + "/questions", token=TOKEN_A)
            self.assertEqual(status, 200, listing)
            self.assertEqual(listing["contract"], "oi.synthetic-source-questions/2")
            self.assertRegex(listing["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertEqual(len(listing["questions"]), 1)
            self.assertEqual(listing["questions"][0]["source_context_state"],
                             "current_unreviewed_question")

            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual(status, 201, amended)
            self.assertEqual(amended["version"], 2)
            self.assertNotEqual(amended["source_id"], original_id)
            status, amended_world, _ = request(
                base, prefix + "/world-model", token=TOKEN_A
            )
            self.assertEqual(status, 200, amended_world)
            self.assertNotEqual(amended_world["snapshot_fingerprint"], fingerprint)

            status, stale, _ = request(
                base, prefix + "/questions", token=TOKEN_A,
                body={**intent, "request_key": "CANONICAL-QUESTION-STALE"},
            )
            self.assertEqual(status, 409, stale)
            self.assertEqual(self.question_counts(patient), (1, 1))
            status, after, _ = request(base, prefix + "/questions", token=TOKEN_A)
            self.assertEqual(status, 200, after)
            self.assertEqual(after["contract"], "oi.synthetic-source-questions/2")
            self.assertNotEqual(after["access_receipt_id"], listing["access_receipt_id"])
            self.assertEqual(len(after["questions"]), 1)
            retained = after["questions"][0]
            self.assertEqual(retained["question_id"], question_id)
            self.assertEqual(retained["question"], QUESTION)
            self.assertEqual(retained["source_id"], original_id)
            self.assertEqual(retained["source_line"], 8)
            self.assertEqual(retained["source_version"], 1)
            self.assertEqual(retained["source_sha256"],
                             hashlib.sha256(ORIGINAL.encode("utf-8")).hexdigest())
            self.assertEqual(retained["source_snapshot_sha256"], fingerprint)
            self.assertEqual(retained["source_snapshot_contract"], "oi.pg-source-world-model/1")
            self.assertEqual(retained["preflight_sha256"], prepared["preflight_sha256"])
            self.assertEqual(retained["source_context_state"], "source_reassessment_required")
            self.assertEqual(retained["human_review_state"], "not_submitted")
            self.assertFalse(retained["clinical_approval"])
            self.assertFalse(retained["model_executed"])
            self.assertEqual(self.question_counts(patient), (1, 1))


if __name__ == "__main__":
    unittest.main()
