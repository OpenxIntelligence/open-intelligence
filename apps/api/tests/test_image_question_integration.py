"""Real PG16/HTTP acceptance for canonical questions and original image custody.

Reports and DICOM bytes are independently authored fixtures. Reuse the shared
source fixture, not an existing test class; no inherited test suite is repeated.
"""
import hashlib
import unittest

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from test_image_custody import AMENDED, REPORT, image_bytes, image_request
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


QUESTION = "What source evidence is missing from this fictional imaging report?"
REVISED_QUESTION = "What changed in the amended fictional imaging report?"


class ImageQuestionIntegrationHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "image_import", "image_read", "image_original_read",
        ))
        self.write()

    @staticmethod
    def case_path(patient):
        return f"/v1/patients/{patient}/cases/CASE-ALPHA"

    def image_path(self, patient, source):
        return self.url(patient) + "/" + source + "/images"

    def read_json(self, base, path):
        status, result, _ = request(base, path, token=TOKEN_A)
        self.assertEqual(status, 200, result)
        return result

    def prepare_question(self, base, patient, source, world, *, line=7,
                         question=QUESTION):
        status, result, _ = request(
            base, self.case_path(patient) + "/composer/source-preflight",
            token=TOKEN_A, body={
                "synthetic": True,
                "expected_source_snapshot_sha256": world["snapshot_fingerprint"],
                "source_id": source, "source_line": line, "question": question,
            },
        )
        self.assertEqual(status, 200, result)
        self.assertEqual(result["source_snapshot_contract"], "oi.pg-source-world-model/1")
        self.assertEqual(result["source_snapshot_sha256"], world["snapshot_fingerprint"])
        self.assertFalse(result["model_execution_authorized"])
        self.assertFalse(result["clinical_approval"])
        return result

    @staticmethod
    def question_intent(prepared, key):
        return {
            "synthetic": True, "request_key": key,
            "question": prepared["question"],
            "source_id": prepared["selected_source"]["source_id"],
            "source_line": prepared["selected_source"]["line"],
            "expected_source_snapshot_sha256": prepared["source_snapshot_sha256"],
            "expected_preflight_sha256": prepared["preflight_sha256"],
        }

    def save_question(self, base, patient, prepared, key):
        intent = self.question_intent(prepared, key)
        status, result, _ = request(
            base, self.case_path(patient) + "/questions", token=TOKEN_A, body=intent,
        )
        self.assertEqual(status, 201, result)
        self.assertFalse(result["duplicate"])
        return result["question_id"], intent

    def rows(self, sql, params=None):
        with self.engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(sql), params or {}).all()]

    def question_record(self, question_id):
        return self.rows(
            "SELECT question_id,question,source_id,source_line,source_version,"
            "source_sha256,source_snapshot_sha256,preflight_sha256,source_snapshot_contract "
            "FROM investigation.source_questions WHERE question_id=:question",
            {"question": question_id},
        )

    def test_image_activity_preserves_question_then_amendment_requires_explicit_reassessment(self):
        raw = image_bytes()
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, imported, _ = self.ingest(base, patient, REPORT)
            self.assertEqual(status, 201, imported)
            source = imported["source_id"]
            prefix = self.case_path(patient)
            path = self.image_path(patient, source)
            world = self.read_json(base, prefix + "/world-model")
            fingerprint = world["snapshot_fingerprint"]
            self.assertEqual(world["contract"], "oi.pg-source-world-model/1")
            self.assertEqual(world["observations"][0]["source_id"], source)
            self.assertEqual(world["observations"][0]["source_line"], 7)
            prepared = self.prepare_question(base, patient, source, world)
            question_id, intent = self.save_question(
                base, patient, prepared, "IMAGE-QUESTION-ORIGINAL",
            )
            original_question = self.question_record(question_id)
            before_images = self.read_json(base, prefix + "/questions")
            self.assertEqual(before_images["questions"][0]["source_context_state"],
                             "current_unreviewed_question")

            status, image, _ = image_request(base, path, raw=raw)
            self.assertEqual((status, image["result"]), (201, "imported"))
            image_id = image["image_id"]
            self.assertEqual(image["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertFalse(image["source_identity_verified"])
            self.assertFalse(image["clinical_interpretation"])
            status, duplicate, _ = image_request(base, path, raw=raw)
            self.assertEqual((status, duplicate["result"], duplicate["image_id"]),
                             (200, "duplicate", image_id))
            index = self.read_json(base, path)
            self.assertEqual([item["image_id"] for item in index["images"]], [image_id])
            status, original, headers = image_request(base, path + "/" + image_id)
            self.assertEqual((status, original), (200, raw))
            after_images = self.read_json(base, prefix + "/world-model")
            self.assertEqual(after_images["snapshot_fingerprint"], fingerprint)
            refreshed = self.prepare_question(base, patient, source, after_images)
            self.assertEqual(refreshed["preflight_sha256"], prepared["preflight_sha256"])
            after_questions = self.read_json(base, prefix + "/questions")
            self.assertEqual(after_questions["questions"], before_images["questions"])
            self.assertEqual(self.question_record(question_id), original_question)
            receipts = [
                world["access_receipt_id"], prepared["access_receipt_id"],
                before_images["access_receipt_id"], index["access_receipt_id"],
                headers["X-OI-Access-Receipt"], after_images["access_receipt_id"],
                refreshed["access_receipt_id"], after_questions["access_receipt_id"],
            ]
            self.assertEqual(len(set(receipts)), len(receipts))

            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amended["version"]), (201, 2))
            new_source = amended["source_id"]
            self.assertNotEqual(new_source, source)
            amended_world = self.read_json(base, prefix + "/world-model")
            self.assertNotEqual(amended_world["snapshot_fingerprint"], fingerprint)
            historical = self.read_json(base, self.url(patient) + "/" + source)
            self.assertEqual(historical["original_text"], REPORT)
            self.assertEqual(historical["sha256"], hashlib.sha256(REPORT.encode()).hexdigest())
            stale = self.read_json(base, prefix + "/questions")["questions"][0]
            self.assertEqual(stale["question_id"], question_id)
            self.assertEqual(stale["source_id"], source)
            self.assertEqual(stale["source_line"], 7)
            self.assertEqual(stale["source_version"], 1)
            self.assertEqual(stale["source_sha256"], hashlib.sha256(REPORT.encode()).hexdigest())
            self.assertEqual(stale["source_snapshot_sha256"], fingerprint)
            self.assertEqual(stale["source_context_state"], "source_reassessment_required")
            self.assertEqual(self.question_record(question_id), original_question)
            self.assertEqual(request(base, prefix + "/questions", token=TOKEN_A,
                                     body=intent)[:2],
                             (200, {"question_id": question_id, "duplicate": True}))
            self.assertEqual(request(base, prefix + "/questions", token=TOKEN_A,
                                     body={**intent, "request_key": "IMAGE-QUESTION-STALE"})[0], 409)

            new_path = self.image_path(patient, new_source)
            self.assertEqual(image_request(base, path + "/" + image_id)[0], 404)
            self.assertEqual(self.read_json(base, new_path)["images"], [])
            self.assertEqual(image_request(base, new_path + "/" + image_id)[0], 404)
            self.assertEqual(self.rows(
                "SELECT source_id,image_id FROM clinical_source.source_image_links"
            ), [(source, image_id)])
            status, linked, _ = image_request(base, new_path, raw=raw)
            self.assertEqual((status, linked["result"], linked["image_id"]),
                             (201, "linked", image_id))
            self.assertEqual(image_request(base, new_path + "/" + image_id)[:2], (200, raw))
            relinked_world = self.read_json(base, prefix + "/world-model")
            self.assertEqual(relinked_world["snapshot_fingerprint"],
                             amended_world["snapshot_fingerprint"])
            self.assertEqual(self.read_json(base, prefix + "/questions")["questions"], [stale])

            revised = self.prepare_question(base, patient, new_source, relinked_world,
                                            line=8, question=REVISED_QUESTION)
            new_question_id, _ = self.save_question(
                base, patient, revised, "IMAGE-QUESTION-AMENDED",
            )
            questions = self.read_json(base, prefix + "/questions")["questions"]
            by_id = {item["question_id"]: item for item in questions}
            self.assertEqual(set(by_id), {question_id, new_question_id})
            self.assertEqual(by_id[question_id], stale)
            current = by_id[new_question_id]
            self.assertEqual((current["source_id"], current["source_line"], current["source_version"]),
                             (new_source, 8, 2))
            self.assertEqual(current["source_context_state"], "current_unreviewed_question")
            self.assertEqual(current["source_sha256"], hashlib.sha256(AMENDED.encode()).hexdigest())
            for item in questions:
                self.assertEqual(item["human_review_state"], "not_submitted")
                self.assertFalse(item["clinical_approval"])
                self.assertFalse(item["model_executed"])

        # Restart uses the same durable patient/source/question/image owners.
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(self.read_json(restarted, prefix + "/questions")["questions"], questions)
            self.assertEqual(image_request(restarted, new_path + "/" + image_id)[:2], (200, raw))
            self.assertEqual(self.read_json(restarted, self.url(patient) + "/" + source)["original_text"], REPORT)
        self.assertEqual(self.question_record(question_id), original_question)
        objects = self.rows("SELECT image_id,sha256,raw FROM clinical_source.dicom_objects")
        self.assertEqual(len(objects), 1)
        self.assertEqual((objects[0][0], objects[0][1], bytes(objects[0][2])),
                         (image_id, hashlib.sha256(raw).hexdigest(), raw))
        self.assertEqual(set(self.rows("SELECT source_id,image_id FROM clinical_source.source_image_links")),
                         {(source, image_id), (new_source, image_id)})
        self.assertEqual(self.rows("SELECT count(*) FROM investigation.source_questions"), [(2,)])
        self.assertEqual(self.rows(
            "SELECT count(*) FROM identity.identity_domain_events "
            "WHERE event_type='investigation.question.created'"
        ), [(2,)])

    def test_image_original_and_question_permissions_are_independent(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, imported, _ = self.ingest(base, patient, REPORT)
            self.assertEqual(status, 201, imported)
            source = imported["source_id"]
            prefix = self.case_path(patient)
            world = self.read_json(base, prefix + "/world-model")
            prepared = self.prepare_question(base, patient, source, world)
            question_id, intent = self.save_question(base, patient, prepared, "IMAGE-GRANT-QUESTION")
            path = self.image_path(patient, source)
            status, image, _ = image_request(base, path, raw=image_bytes())
            self.assertEqual(status, 201, image)
            original_path = path + "/" + image["image_id"]
            initial_actions = list(self.creds[0]["actions"])

            self.creds[0]["actions"] = [action for action in initial_actions
                                        if action != "image_original_read"]
            self.write()
            self.assertEqual(image_request(base, original_path)[0], 404)
            self.assertEqual(self.read_json(base, path)["images"][0]["image_id"], image["image_id"])
            self.assertEqual(self.read_json(base, prefix + "/questions")["questions"][0]["question_id"],
                             question_id)
            self.assertEqual(request(base, prefix + "/questions", token=TOKEN_A, body=intent)[0], 200)
            self.assertEqual(self.rows(
                "SELECT count(*) FROM identity.identity_domain_events "
                "WHERE event_type='image.original_read_authorized'"
            ), [(0,)])

            # Keep every source and image grant while withdrawing each question
            # grant separately; a 404 must not be explained by source denial.
            for action, body in (("question_read", None), ("question_create", intent)):
                with self.subTest(withdrawn=action):
                    self.creds[0]["actions"] = [item for item in initial_actions if item != action]
                    self.write()
                    self.assertEqual(request(base, prefix + "/questions", token=TOKEN_A,
                                             body=body)[0], 404)
                    self.assertEqual(image_request(base, original_path)[:2], (200, image_bytes()))
                    self.assertEqual(self.read_json(base, prefix + "/world-model")["snapshot_fingerprint"],
                                     world["snapshot_fingerprint"])

            # Image grants need no question, Composer or source-disclosure grant.
            self.creds[0]["actions"] = ["patient_read", "image_read", "image_original_read"]
            self.write()
            for path_to_deny, body in ((prefix + "/questions", None),
                                       (prefix + "/questions", intent),
                                       (prefix + "/world-model", None)):
                self.assertEqual(request(base, path_to_deny, token=TOKEN_A, body=body)[0], 404)
            self.assertEqual(image_request(base, original_path)[:2], (200, image_bytes()))
            self.assertEqual(self.read_json(base, path)["images"][0]["image_id"], image["image_id"])

            # Conversely, source/question grants never imply any image grant.
            self.creds[0]["actions"] = [action for action in initial_actions
                                        if not action.startswith("image_")]
            self.write()
            self.assertEqual(image_request(base, original_path)[0], 404)
            self.assertEqual(request(base, path, token=TOKEN_A)[0], 404)
            restored = self.read_json(base, prefix + "/questions")["questions"][0]
            self.assertEqual(restored["source_context_state"], "current_unreviewed_question")
            self.assertEqual(self.read_json(base, prefix + "/world-model")["snapshot_fingerprint"],
                             world["snapshot_fingerprint"])
            self.assertEqual(self.rows("SELECT count(*) FROM investigation.source_questions"), [(1,)])

    def test_failed_image_relink_preserves_original_and_allows_source_reassessment_question(self):
        raw = image_bytes()
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, imported, _ = self.ingest(base, patient, REPORT)
            self.assertEqual(status, 201, imported)
            source = imported["source_id"]
            prefix = self.case_path(patient)
            world = self.read_json(base, prefix + "/world-model")
            prepared = self.prepare_question(base, patient, source, world)
            question_id, _ = self.save_question(base, patient, prepared, "ROLLBACK-QUESTION-ONE")
            original_question = self.question_record(question_id)
            status, image, _ = image_request(base, self.image_path(patient, source), raw=raw)
            self.assertEqual(status, 201, image)
            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual(status, 201, amended)
            new_source = amended["source_id"]
            new_path = self.image_path(patient, new_source)
            amended_world = self.read_json(base, prefix + "/world-model")
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.fail_integration_image_link() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                        IF NEW.event_type='image.source_linked' THEN
                            RAISE EXCEPTION 'AUTHORED-IMAGE-LINK-FAILURE';
                        END IF;
                        RETURN NEW;
                    END; $$;
                    CREATE TRIGGER fail_integration_image_link
                    BEFORE INSERT ON identity.identity_domain_events
                    FOR EACH ROW EXECUTE FUNCTION identity.fail_integration_image_link();
                """)
            self.assertEqual(image_request(base, new_path, raw=raw)[:2],
                             (503, {"detail": "Patient registry unavailable"}))
            self.assertEqual(self.rows("SELECT source_id,image_id FROM clinical_source.source_image_links"),
                             [(source, image["image_id"])])
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects"), [(1,)])
            self.assertEqual(self.rows(
                "SELECT count(*) FROM identity.identity_domain_events WHERE event_type='image.source_linked'"
            ), [(0,)])
            self.assertEqual(self.read_json(base, new_path)["images"], [])
            self.assertEqual(self.question_record(question_id), original_question)
            self.assertEqual(self.read_json(base, self.url(patient) + "/" + source)["original_text"], REPORT)
            self.assertEqual(self.read_json(base, prefix + "/world-model")["snapshot_fingerprint"],
                             amended_world["snapshot_fingerprint"])

            # A failed image attachment is not a failed source amendment, nor a
            # prerequisite for a new source-only, explicitly unreviewed question.
            revised = self.prepare_question(base, patient, new_source, amended_world,
                                            line=8, question=REVISED_QUESTION)
            new_question, _ = self.save_question(base, patient, revised, "ROLLBACK-QUESTION-TWO")
            questions = self.read_json(base, prefix + "/questions")["questions"]
            self.assertEqual({item["question_id"]: item["source_context_state"] for item in questions}, {
                question_id: "source_reassessment_required",
                new_question: "current_unreviewed_question",
            })
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "DROP TRIGGER fail_integration_image_link ON identity.identity_domain_events"
                )
            status, linked, _ = image_request(base, new_path, raw=raw)
            self.assertEqual((status, linked["result"], linked["image_id"]),
                             (201, "linked", image["image_id"]))
            self.assertEqual(self.read_json(base, prefix + "/questions")["questions"], questions)
            self.assertEqual(image_request(base, new_path + "/" + image["image_id"])[:2], (200, raw))
            self.assertEqual(self.read_json(base, prefix + "/world-model")["snapshot_fingerprint"],
                             amended_world["snapshot_fingerprint"])


if __name__ == "__main__":
    unittest.main()
