"""Actual PG16/HTTP lifecycle across the existing image and review owners.

All reports, images, questions and reasons are independently authored fiction.
Reuse fixture helpers without inheriting any upstream test methods.
"""
import hashlib
import unittest

from http_support import running_server
from oi_api.app import create_app
from test_canonical_review_flow import RETURN_REASON
from test_image_custody import AMENDED, REPORT, image_bytes, image_request
import test_image_question_integration as image_question_fixtures
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class ImageReviewIntegrationHTTPTests(SourceVersionFixture):
    case_path = staticmethod(image_question_fixtures.ImageQuestionIntegrationHTTPTests.case_path)
    image_path = image_question_fixtures.ImageQuestionIntegrationHTTPTests.image_path
    read_json = image_question_fixtures.ImageQuestionIntegrationHTTPTests.read_json
    prepare_question = image_question_fixtures.ImageQuestionIntegrationHTTPTests.prepare_question
    question_intent = staticmethod(
        image_question_fixtures.ImageQuestionIntegrationHTTPTests.question_intent)
    save_question = image_question_fixtures.ImageQuestionIntegrationHTTPTests.save_question
    rows = image_question_fixtures.ImageQuestionIntegrationHTTPTests.rows
    question_record = image_question_fixtures.ImageQuestionIntegrationHTTPTests.question_record

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "image_import", "image_read", "image_original_read",
            "review_queue_read", "review_return",
        ))
        self.write()

    def queue(self, base, patient):
        result = self.read_json(base, self.case_path(patient) + "/review-queue")
        self.assertEqual(result["contract"], "oi.synthetic-question-review-return-queue/2")
        self.assertRegex(result["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
        for field in ("clinical_approval", "reviewer_identity_verified",
                      "external_notification_sent", "review_completion_supported"):
            self.assertIs(result[field], False)
        return result

    def return_url(self, patient, question):
        return self.case_path(patient) + f"/questions/{question}/return-for-verification"

    def return_question(self, base, patient, item, key):
        intent = {"synthetic": True, "request_key": key,
                  "expected_queue_fingerprint": item["queue_fingerprint"],
                  "reason": RETURN_REASON}
        status, receipt, _ = request(
            base, self.return_url(patient, item["question_id"]), token=TOKEN_A, body=intent)
        self.assertEqual(status, 201, receipt)
        self.assertEqual(receipt["question_id"], item["question_id"])
        self.assertFalse(receipt["duplicate"])
        self.assertRegex(receipt["receipt_id"], r"^REVIEW-[0-9A-F]{32}$")
        return intent, {**receipt, "duplicate": True}

    def durable_state(self):
        """Complete owned rows detect partial writes, including access events."""
        return {
            "questions": self.rows("SELECT * FROM investigation.source_questions ORDER BY question_id"),
            "returns": self.rows("SELECT * FROM investigation.question_review_receipts ORDER BY receipt_id"),
            "images": self.rows("SELECT * FROM clinical_source.dicom_objects ORDER BY image_id"),
            "links": self.rows("SELECT * FROM clinical_source.source_image_links ORDER BY source_id,image_id"),
            "events": self.rows("SELECT * FROM identity.identity_domain_events ORDER BY id"),
        }

    def prepare(self, base):
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient, REPORT)
        self.assertEqual(status, 201, source)
        world = self.read_json(base, self.case_path(patient) + "/world-model")
        prepared = self.prepare_question(base, patient, source["source_id"], world)
        question, _ = self.save_question(base, patient, prepared, "IMAGE-REVIEW-QUESTION-V1")
        return patient, source["source_id"], question, world, prepared

    def test_images_returns_and_amendment_preserve_one_immutable_history(self):
        # Including image/access events in content identity would stale the
        # captured return intent; relinking must never make its old anchor current.
        raw = image_bytes()
        with running_server(create_app(self.settings)) as base:
            patient, source, question, world, prepared = self.prepare(base)
            prefix = self.case_path(patient)
            image_path = self.image_path(patient, source)
            initial = self.queue(base, patient)
            item = initial["items"][0]
            self.assertEqual((item["question_id"], item["source_id"], item["source_line"]),
                             (question, source, 7))
            self.assertEqual(item["review_state"], "awaiting_independent_verification")
            original_question = self.question_record(question)

            status, image, _ = image_request(base, image_path, raw=raw)
            self.assertEqual((status, image["result"]), (201, "imported"))
            image_id = image["image_id"]
            self.assertEqual(image["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(image_request(base, image_path, raw=raw)[:2],
                             (200, {**image, "result": "duplicate"}))
            index = self.read_json(base, image_path)
            status, retrieved, headers = image_request(base, image_path + "/" + image_id)
            self.assertEqual((status, retrieved), (200, raw))
            self.assertNotEqual(index["access_receipt_id"], headers["X-OI-Access-Receipt"])
            after_images = self.queue(base, patient)
            self.assertEqual(after_images["items"], initial["items"])
            self.assertEqual(after_images["receipts"], [])
            self.assertNotEqual(after_images["access_receipt_id"], initial["access_receipt_id"])
            after_world = self.read_json(base, prefix + "/world-model")
            self.assertEqual(after_world["snapshot_fingerprint"], world["snapshot_fingerprint"])
            after_preflight = self.prepare_question(base, patient, source, after_world)
            self.assertEqual(after_preflight["preflight_sha256"], prepared["preflight_sha256"])
            self.assertEqual(self.question_record(question), original_question)

            # Deliberately submit the fingerprint captured BEFORE image writes.
            intent, duplicate = self.return_question(base, patient, item, "IMAGE-REVIEW-RETURN-V1")
            returned = self.queue(base, patient)
            self.assertEqual(returned["items"][0]["queue_fingerprint"], item["queue_fingerprint"])
            self.assertEqual(returned["items"][0]["current_return_receipt_id"], duplicate["receipt_id"])
            self.assertEqual(returned["items"][0]["review_state"], "returned_for_independent_verification")
            self.assertEqual(len(returned["receipts"]), 1)
            immutable_return = self.durable_state()["returns"]
            self.assertEqual(image_request(base, image_path + "/" + image_id)[:2], (200, raw))
            reread = self.queue(base, patient)
            self.assertEqual(reread["items"], returned["items"])
            self.assertEqual(reread["receipts"], returned["receipts"])

            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amended["version"]), (201, 2))
            new_source = amended["source_id"]
            historical = self.queue(base, patient)
            old = historical["items"][0]
            self.assertEqual((old["source_id"], old["source_line"], old["source_version"]),
                             (source, 7, 1))
            self.assertEqual(old["source_snapshot_sha256"], world["snapshot_fingerprint"])
            self.assertEqual(old["review_state"], "source_reassessment_required")
            self.assertIsNone(old["queue_fingerprint"])
            self.assertIsNone(old["current_return_receipt_id"])
            self.assertEqual((old["return_count"], old["prior_return_count"]), (0, 1))
            self.assertEqual(historical["receipts"], returned["receipts"])
            self.assertEqual(self.question_record(question), original_question)
            self.assertEqual(self.durable_state()["returns"], immutable_return)
            before_denials = self.durable_state()
            for path in (image_path, image_path + "/" + image_id,
                         self.image_path(patient, new_source) + "/" + image_id):
                self.assertEqual(image_request(base, path)[0], 404)
            self.assertEqual(request(base, self.return_url(patient, question), token=TOKEN_A,
                                     body={**intent, "request_key": "STALE-NEW-IMAGE-REVIEW"})[0], 409)
            self.assertEqual(self.durable_state(), before_denials)
            self.assertEqual(request(base, self.return_url(patient, question), token=TOKEN_A,
                                     body=intent)[:2], (200, duplicate))
            self.assertEqual(self.durable_state()["returns"], immutable_return)

            amended_world = self.read_json(base, prefix + "/world-model")
            self.assertNotEqual(amended_world["snapshot_fingerprint"], world["snapshot_fingerprint"])
            new_path = self.image_path(patient, new_source)
            status, linked, _ = image_request(base, new_path, raw=raw)
            self.assertEqual((status, linked["result"], linked["image_id"]), (201, "linked", image_id))
            self.assertEqual(image_request(base, new_path + "/" + image_id)[:2], (200, raw))
            self.assertEqual(image_request(base, image_path + "/" + image_id)[0], 404)
            relinked = self.queue(base, patient)
            self.assertEqual(relinked["items"], historical["items"])
            self.assertEqual(relinked["receipts"], historical["receipts"])
            relinked_world = self.read_json(base, prefix + "/world-model")
            self.assertEqual(relinked_world["snapshot_fingerprint"], amended_world["snapshot_fingerprint"])

            revised = self.prepare_question(
                base, patient, new_source, relinked_world, line=8,
                question=image_question_fixtures.REVISED_QUESTION)
            new_question, _ = self.save_question(base, patient, revised, "IMAGE-REVIEW-QUESTION-V2")
            current_queue = self.queue(base, patient)
            current = next(row for row in current_queue["items"] if row["question_id"] == new_question)
            self.assertEqual((current["source_id"], current["source_line"], current["source_version"]),
                             (new_source, 8, 2))
            self.assertEqual((current["return_count"], current["prior_return_count"]), (0, 0))
            new_intent, new_duplicate = self.return_question(
                base, patient, current, "IMAGE-REVIEW-RETURN-V2")
            self.assertNotEqual(new_duplicate["receipt_id"], duplicate["receipt_id"])
            final = self.queue(base, patient)
            self.assertEqual(len(final["receipts"]), 2)
            self.assertEqual(next(row for row in final["items"] if row["question_id"] == question), old)
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects"), [(1,)])
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links"), [(2,)])
            self.assertEqual(self.rows(
                "SELECT count(*) FROM identity.identity_domain_events "
                "WHERE event_type='investigation.review.returned_for_verification'"), [(2,)])

        with running_server(create_app(self.settings)) as restarted:
            reopened = self.queue(restarted, patient)
            self.assertEqual(reopened["items"], final["items"])
            self.assertEqual(reopened["receipts"], final["receipts"])
            self.assertEqual(image_request(restarted, new_path + "/" + image_id)[:2], (200, raw))
            for qid, body, receipt in ((question, intent, duplicate),
                                       (new_question, new_intent, new_duplicate)):
                self.assertEqual(request(restarted, self.return_url(patient, qid), token=TOKEN_A,
                                         body=body)[:2], (200, receipt))
            self.assertEqual(self.queue(restarted, patient)["receipts"], final["receipts"])
            self.assertEqual(self.question_record(question), original_question)

    def test_image_and_review_grants_remain_independent_with_atomic_denials(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, question, _, _ = self.prepare(base)
            path = self.image_path(patient, source)
            status, image, _ = image_request(base, path, raw=image_bytes())
            self.assertEqual(status, 201, image)
            original_path = path + "/" + image["image_id"]
            item = self.queue(base, patient)["items"][0]
            all_actions = list(self.creds[0]["actions"])

            # A review-only operator may read the queue and record a return;
            # those rights cannot disclose or import image objects.
            self.creds[0]["actions"] = [action for action in all_actions if not action.startswith("image_")]
            self.write()
            before = self.durable_state()
            for url, raw in ((path, None), (original_path, None), (path, image_bytes())):
                self.assertEqual(image_request(base, url, raw=raw)[0], 404)
            self.assertEqual(self.durable_state(), before)
            self.assertEqual(self.queue(base, patient)["items"][0], item)
            intent, duplicate = self.return_question(base, patient, item, "INDEPENDENT-IMAGE-RETURN")

            # Each review action is independent from both image access and the
            # other review action. Denial must add neither access nor return events.
            for missing in ("review_queue_read", "review_return"):
                with self.subTest(withdrawn=missing):
                    self.creds[0]["actions"] = [action for action in all_actions if action != missing]
                    self.write()
                    before = self.durable_state()
                    url = (self.case_path(patient) + "/review-queue" if missing == "review_queue_read"
                           else self.return_url(patient, question))
                    body = None if missing == "review_queue_read" else intent
                    status, denied, _ = request(base, url, token=TOKEN_A, body=body)
                    self.assertEqual((status, set(denied)), (404, {"detail"}))
                    self.assertEqual(self.durable_state(), before)
                    self.assertEqual(image_request(base, original_path)[:2], (200, image_bytes()))
                    if missing == "review_queue_read":
                        self.assertEqual(request(base, self.return_url(patient, question),
                                                 token=TOKEN_A, body=intent)[:2], (200, duplicate))
                    else:
                        self.assertEqual(self.queue(base, patient)["items"][0]["current_return_receipt_id"],
                                         duplicate["receipt_id"])

    def test_failed_image_relink_cannot_rewrite_or_duplicate_historical_return(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, question, _, _ = self.prepare(base)
            path = self.image_path(patient, source)
            status, image, _ = image_request(base, path, raw=image_bytes())
            self.assertEqual(status, 201, image)
            item = self.queue(base, patient)["items"][0]
            intent, duplicate = self.return_question(base, patient, item, "ROLLBACK-IMAGE-RETURN")
            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual(status, 201, amended)
            historical = self.queue(base, patient)
            new_path = self.image_path(patient, amended["source_id"])
            before = self.durable_state()
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.fail_image_review_link() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                        IF NEW.event_type='image.source_linked' THEN
                            RAISE EXCEPTION 'AUTHORED-IMAGE-REVIEW-LINK-FAILURE';
                        END IF;
                        RETURN NEW;
                    END; $$;
                    CREATE TRIGGER fail_image_review_link
                    BEFORE INSERT ON identity.identity_domain_events
                    FOR EACH ROW EXECUTE FUNCTION identity.fail_image_review_link();
                """)
            self.assertEqual(image_request(base, new_path, raw=image_bytes())[:2],
                             (503, {"detail": "Patient registry unavailable"}))
            self.assertEqual(self.durable_state(), before)
            self.assertEqual(request(base, self.return_url(patient, question), token=TOKEN_A,
                                     body=intent)[:2], (200, duplicate))
            self.assertEqual(self.durable_state()["returns"], before["returns"])
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "DROP TRIGGER fail_image_review_link ON identity.identity_domain_events")
            status, linked, _ = image_request(base, new_path, raw=image_bytes())
            self.assertEqual((status, linked["result"], linked["image_id"]),
                             (201, "linked", image["image_id"]))
            after = self.queue(base, patient)
            self.assertEqual(after["items"], historical["items"])
            self.assertEqual(after["receipts"], historical["receipts"])


if __name__ == "__main__":
    unittest.main()
