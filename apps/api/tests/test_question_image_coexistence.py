"""One real H1 case: canonical question + exact image + amended original.

Uses the independently authored source/image fixtures and actual disposable
PostgreSQL 16. It does not infer image findings or create clinical decisions.
"""
import hashlib
from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture
from test_image_custody import REPORT, AMENDED, image_bytes, image_request


QUESTION_ONE = "Which original imaging statement requires independent verification?"
QUESTION_TWO = "What changed after the fictional imaging report amendment?"


class QuestionImageCoexistenceTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "image_import", "image_read", "image_original_read",
            "composer_context_read", "question_create", "question_read",
        ))
        self.write()

    @staticmethod
    def case_root(pid):
        return f"/v1/patients/{pid}/cases/CASE-ALPHA"

    def question(self, base, pid, sid, *, text_value, key):
        root = self.case_root(pid)
        code, model, _ = request(base, root + "/world-model", token=TOKEN_A)
        self.assertEqual(code, 200, model)
        fingerprint = model["snapshot_fingerprint"]
        observations = [o for o in model["observations"]
                        if o["source_id"] == sid]
        self.assertEqual(len(observations), 1)
        line = observations[0]["source_line"]
        status, prepared, _ = request(
            base, root + "/composer/source-preflight",
            token=TOKEN_A, body={
                "synthetic": True,
                "expected_source_snapshot_sha256": fingerprint,
                "source_id": sid, "source_line": line,
                "question": text_value,
            },
        )
        self.assertEqual(status, 200, prepared)
        status, saved, _ = request(
            base, root + "/questions", token=TOKEN_A,
            body={
                "synthetic": True, "request_key": key,
                "question": text_value, "source_id": sid, "source_line": line,
                "expected_source_snapshot_sha256": fingerprint,
                "expected_preflight_sha256": prepared["preflight_sha256"],
            },
        )
        self.assertEqual(status, 201, saved)
        return saved["question_id"]

    def test_same_case_image_and_question_survive_amendment_without_retarget(self):
        raw = image_bytes()
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            root = self.case_root(patient)
            status, report, _ = self.ingest(base, patient, REPORT)
            self.assertEqual(status, 201)
            old_source = report["source_id"]
            old_images = root + "/sources/" + old_source + "/images"
            status, imported, _ = image_request(base, old_images, raw=raw)
            self.assertEqual((status, imported["result"]), (201, "imported"))
            image_id = imported["image_id"]
            self.assertEqual(imported["sha256"], hashlib.sha256(raw).hexdigest())

            first_question = self.question(
                base, patient, old_source,
                text_value=QUESTION_ONE, key="QUESTION-IMAGE-V1",
            )
            status, image_copy, _ = image_request(
                base, old_images + "/" + image_id
            )
            self.assertEqual((status, image_copy), (200, raw))
            self.assertEqual(request(base, root + "/questions")[0], 200)

            status, amended, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual(status, 201)
            current_source = amended["source_id"]
            self.assertNotEqual(current_source, old_source)
            # No auto-retargeting of the earlier source's image or question.
            self.assertEqual(image_request(base, old_images)[0], 404)
            self.assertEqual(image_request(base, old_images + "/" + image_id)[0], 404)
            current_images = root + "/sources/" + current_source + "/images"
            empty = request(base, current_images, token=TOKEN_A)
            self.assertEqual(empty[0], 200)
            self.assertEqual(empty[1]["images"], [])

            history = request(base, root + "/questions", token=TOKEN_A)
            self.assertEqual(history[0], 200)
            old = next(x for x in history[1]["questions"]
                       if x["question_id"] == first_question)
            self.assertEqual(old["source_context_state"], "source_reassessment_required")
            self.assertEqual(old["source_id"], old_source)
            self.assertFalse(old["clinical_approval"])

            # Re-link the same immutable DICOM bytes to the accepted amendment
            # instead of copying the object or changing its original source.
            relink = image_request(base, current_images, raw=raw)
            self.assertEqual((relink[0], relink[1]["result"]), (201, "linked"))
            self.assertEqual(relink[1]["image_id"], image_id)
            status, restored, _ = image_request(
                base, current_images + "/" + image_id,
            )
            self.assertEqual((status, restored), (200, raw))

            second_question = self.question(
                base, patient, current_source,
                text_value=QUESTION_TWO, key="QUESTION-IMAGE-V2",
            )
            self.assertNotEqual(first_question, second_question)
            history = request(base, root + "/questions", token=TOKEN_A)
            self.assertEqual(history[0], 200)
            entries = {x["question_id"]: x for x in history[1]["questions"]}
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[first_question]["source_id"], old_source)
            self.assertEqual(entries[first_question]["source_context_state"],
                             "source_reassessment_required")
            self.assertEqual(entries[second_question]["source_id"], current_source)
            self.assertEqual(entries[second_question]["source_context_state"],
                             "current_unreviewed_question")
            self.assertTrue(all(not x["model_executed"] and
                                not x["clinical_approval"] for x in entries.values()))
            with self.engine.connect() as conn:
                counts = (
                    conn.execute(text(
                        "SELECT count(*) FROM clinical_source.dicom_objects"
                    )).scalar_one(),
                    conn.execute(text(
                        "SELECT count(*) FROM clinical_source.source_image_links"
                    )).scalar_one(),
                    conn.execute(text(
                        "SELECT count(*) FROM investigation.source_questions"
                    )).scalar_one(),
                )
            self.assertEqual(counts, (1, 2, 2))

        with running_server(create_app(self.settings)) as reopened:
            status, persisted, _ = request(
                reopened, self.case_root(patient) + "/questions", token=TOKEN_A
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(persisted["questions"]), 2)
            status, original, _ = image_request(
                reopened, self.case_root(patient) + "/sources/"
                + current_source + "/images/" + image_id,
            )
            self.assertEqual((status, original), (200, raw))

    def test_image_and_question_rights_are_independent_within_same_case(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            report = self.ingest(base, patient, REPORT)[1]
            sid = report["source_id"]
            image_path = self.case_root(patient) + "/sources/" + sid + "/images"
            self.assertEqual(image_request(base, image_path, raw=image_bytes())[0], 201)
            self.question(base, patient, sid, text_value=QUESTION_ONE, key="RIGHTS-ONE")
            questions_path = self.case_root(patient) + "/questions"

            self.creds[0]["actions"].remove("image_read")
            self.write()
            self.assertEqual(request(base, image_path, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, questions_path, token=TOKEN_A)[0], 200)
            self.creds[0]["actions"].append("image_read")
            self.creds[0]["actions"].remove("question_read")
            self.write()
            self.assertEqual(request(base, questions_path, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, image_path, token=TOKEN_A)[0], 200)
