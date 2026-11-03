"""Actual PG16/HTTP acceptance of archive reads within canonical review history.

Reports, questions, reasons and DICOM originals are independently authored
fixtures. The injected archive is controlled; no live PACS or network-isolation
claim is made. Reuse helpers, without inheriting another test class's methods.
"""
import json
from unittest.mock import Mock

from http_support import running_server
from oi_api.app import create_app
from test_image_custody import AMENDED, image_bytes, image_request
import test_image_question_integration as question_fixtures
import test_image_review_integration as review_fixtures
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class ArchiveQuestionReviewIntegrationHTTPTests(SourceVersionFixture):
    case_path = staticmethod(review_fixtures.ImageReviewIntegrationHTTPTests.case_path)
    image_path = review_fixtures.ImageReviewIntegrationHTTPTests.image_path
    read_json = review_fixtures.ImageReviewIntegrationHTTPTests.read_json
    prepare_question = review_fixtures.ImageReviewIntegrationHTTPTests.prepare_question
    question_intent = staticmethod(review_fixtures.ImageReviewIntegrationHTTPTests.question_intent)
    save_question = review_fixtures.ImageReviewIntegrationHTTPTests.save_question
    rows = review_fixtures.ImageReviewIntegrationHTTPTests.rows
    question_record = review_fixtures.ImageReviewIntegrationHTTPTests.question_record
    queue = review_fixtures.ImageReviewIntegrationHTTPTests.queue
    return_url = review_fixtures.ImageReviewIntegrationHTTPTests.return_url
    return_question = review_fixtures.ImageReviewIntegrationHTTPTests.return_question
    durable_state = review_fixtures.ImageReviewIntegrationHTTPTests.durable_state
    prepare = review_fixtures.ImageReviewIntegrationHTTPTests.prepare

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "image_import", "image_read", "image_original_read",
            "review_queue_read", "review_return",
        ))
        self.write()
        self.raw = image_bytes()
        self.archive = Mock()
        self.archive.read.return_value = self.raw

    def prepare_connected(self, base):
        patient, source, question, world, prepared = self.prepare(base)
        path = self.image_path(patient, source)
        status, image, _ = image_request(base, path, raw=self.raw)
        self.assertEqual((status, image["result"]), (201, "imported"))
        item = next(row for row in self.queue(base, patient)["items"]
                    if row["question_id"] == question)
        intent, duplicate = self.return_question(base, patient, item, "ARCHIVE-RETURN-V1")
        self.archive.read.assert_not_called()
        return patient, source, question, world, prepared, image["image_id"], intent, duplicate

    def assert_withheld(self, response, status, before):
        self.assertEqual(response[0], status)
        self.assertIsInstance(response[1], dict)
        self.assertEqual(set(response[1]), {"detail"})
        if status == 503:
            self.assertEqual(response[1], {"detail": "Patient registry unavailable"})
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", response[2])
        for private in (TOKEN_A, "PRIVATE-ARCHIVE-DETAIL", "DICM", "2.25.103"):
            self.assertNotIn(private, json.dumps(response[1]))
        self.assertEqual(self.durable_state(), before)

    def test_archive_read_amendment_relink_and_returns_preserve_canonical_history(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            patient, source, question, world, prepared, image, intent, duplicate = self.prepare_connected(base)
            prefix = self.case_path(patient)
            original_path = self.image_path(patient, source) + "/" + image
            original_question = self.question_record(question)
            original_returns = self.durable_state()["returns"]
            returned = self.queue(base, patient)
            code, raw, headers = image_request(base, original_path)
            self.assertEqual((code, raw), (200, self.raw))
            self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            self.assertEqual(self.rows(
                "SELECT metadata_json->>'receipt_id' FROM identity.identity_domain_events "
                "WHERE event_type='image.original_read_authorized' ORDER BY id"),
                [(headers["X-OI-Access-Receipt"],)])
            after = self.queue(base, patient)
            self.assertEqual((after["items"], after["receipts"]),
                             (returned["items"], returned["receipts"]))
            after_world = self.read_json(base, prefix + "/world-model")
            self.assertEqual(after_world["snapshot_fingerprint"], world["snapshot_fingerprint"])
            self.assertEqual(self.question_record(question), original_question)
            self.assertEqual(self.durable_state()["returns"], original_returns)

            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amendment["version"]), (201, 2))
            new_source = amendment["source_id"]
            new_path = self.image_path(patient, new_source)
            historical = self.queue(base, patient)
            old = next(row for row in historical["items"] if row["question_id"] == question)
            self.assertEqual((old["source_id"], old["source_line"], old["source_version"]),
                             (source, 7, 1))
            self.assertEqual(old["source_snapshot_sha256"], world["snapshot_fingerprint"])
            self.assertEqual(old["review_state"], "source_reassessment_required")
            self.assertIsNone(old["current_return_receipt_id"])
            self.assertEqual(historical["receipts"], returned["receipts"])
            before = self.durable_state()
            calls = self.archive.read.call_count
            for path in (original_path, new_path + "/" + image):
                self.assert_withheld(image_request(base, path), 404, before)
            self.assertEqual(self.archive.read.call_count, calls)

            # Both exact request identities remain recoverable after amendment.
            question_intent = self.question_intent(prepared, "IMAGE-REVIEW-QUESTION-V1")
            self.assertEqual(request(base, prefix + "/questions", token=TOKEN_A,
                                     body=question_intent)[:2],
                             (200, {"question_id": question, "duplicate": True}))
            self.assertEqual(request(base, self.return_url(patient, question),
                                     token=TOKEN_A, body=intent)[:2], (200, duplicate))
            self.assertEqual(self.question_record(question), original_question)
            self.assertEqual(self.durable_state()["returns"], original_returns)

            status, linked, _ = image_request(base, new_path, raw=self.raw)
            self.assertEqual((status, linked["result"], linked["image_id"]), (201, "linked", image))
            self.assertEqual(self.archive.read.call_count, calls)
            relinked = self.queue(base, patient)
            self.assertEqual((relinked["items"], relinked["receipts"]),
                             (historical["items"], historical["receipts"]))
            new_world = self.read_json(base, prefix + "/world-model")
            new_prepared = self.prepare_question(
                base, patient, new_source, new_world, line=8,
                question=question_fixtures.REVISED_QUESTION)
            new_question, _ = self.save_question(base, patient, new_prepared, "ARCHIVE-QUESTION-V2")
            item = next(row for row in self.queue(base, patient)["items"]
                        if row["question_id"] == new_question)
            self.assertEqual((item["source_id"], item["source_line"], item["source_version"]),
                             (new_source, 8, 2))
            _, new_return = self.return_question(base, patient, item, "ARCHIVE-RETURN-V2")
            self.assertNotEqual(new_return["receipt_id"], duplicate["receipt_id"])
            current = {row["question_id"]: row for row in self.queue(base, patient)["items"]}
            self.assertEqual(current[question], old)
            self.assertEqual(current[new_question]["review_state"], "returned_for_independent_verification")
            self.assertEqual(current[new_question]["current_return_receipt_id"], new_return["receipt_id"])
            self.assertEqual(image_request(base, new_path + "/" + image)[:2], (200, self.raw))
            self.assertEqual(self.archive.read.call_count, calls + 1)
            self.archive.read.assert_called_with("2.25.101", "2.25.102", "2.25.103")
            self.assertEqual(self.question_record(question), original_question)
            self.assertIn(original_returns[0], self.durable_state()["returns"])
            self.assertEqual(self.rows("SELECT count(*) FROM investigation.source_questions"), [(2,)])
            self.assertEqual(self.rows("SELECT count(*) FROM investigation.question_review_receipts"), [(2,)])
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects"), [(1,)])
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links"), [(2,)])

    def test_failed_archive_reads_preserve_questions_returns_and_custody_without_fallback(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            patient, source, _, _, _, image, _, _ = self.prepare_connected(base)
            path = self.image_path(patient, source) + "/" + image
            before = self.durable_state()
            # A valid local original exists throughout every failed archive read.
            self.assertEqual(bytes(self.rows(
                "SELECT raw FROM clinical_source.dicom_objects WHERE image_id=:image",
                {"image": image})[0][0]), self.raw)
            outcomes = (
                ("archive_error", None, RuntimeError("PRIVATE-ARCHIVE-DETAIL")),
                ("corrupt_bytes", self.raw + b"changed", None),
                ("wrong_subject", image_bytes(patient_id="SUBJECT-OTHER"), None),
                ("non_bytes", bytearray(self.raw), None),
            )
            for name, content, error in outcomes:
                with self.subTest(outcome=name):
                    self.archive.read.reset_mock()
                    self.archive.read.side_effect = error
                    self.archive.read.return_value = content
                    self.assert_withheld(image_request(base, path), 503, before)
                    self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            self.archive.read.side_effect = None
            self.archive.read.return_value = self.raw
            self.assertEqual(image_request(base, path)[:2], (200, self.raw))
            after = self.durable_state()
            for owner in ("questions", "returns", "images", "links"):
                self.assertEqual(after[owner], before[owner])
            self.assertEqual(self.rows(
                "SELECT count(*) FROM identity.identity_domain_events "
                "WHERE event_type='image.original_read_authorized'"), [(1,)])

    def test_missing_grants_and_revoked_binding_do_not_fetch_archive_or_change_history(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            patient, source, question, _, _, image, intent, _ = self.prepare_connected(base)
            path = self.image_path(patient, source) + "/" + image
            actions = list(self.creds[0]["actions"])
            for missing in ("image_original_read", "patient_read"):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"] = [action for action in actions if action != missing]
                    self.write()
                    before = self.durable_state()
                    self.assert_withheld(image_request(base, path), 404, before)
                    self.archive.read.assert_not_called()
            self.creds[0]["actions"] = actions
            self.write()
            status, _, _ = request(
                base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A, body={"synthetic": True, "reason": "Authored archive-review revocation"})
            self.assertEqual(status, 200)
            before = self.durable_state()
            self.assert_withheld(image_request(base, path), 404, before)
            for url, body in (
                (self.case_path(patient) + "/questions", None),
                (self.case_path(patient) + "/review-queue", None),
                (self.return_url(patient, question), intent),
            ):
                self.assert_withheld(request(base, url, token=TOKEN_A, body=body), 404, before)
            self.archive.read.assert_not_called()
