"""A real mixed-anchor case must keep text-only operations scoped to text questions."""
import json

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from test_canonical_review_flow import create_question
from test_laboratory_fhir_r4 import OBS, PATIENT, encode, example
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class LaboratoryQuestionLegacyBoundaryTests(SourceVersionFixture):
    def event_count(self):
        with self.engine.connect() as db:
            return db.execute(text("SELECT count(*) FROM identity.identity_domain_events")).scalar_one()

    def test_supported_text_and_unsupported_lab_ids_in_same_case(self):
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read", "source_brief_export",
            "evidence_read", "authored_evidence_read", "review_packet_read", "review_queue_read",
            "review_return", "followthrough_read", "followthrough_create",
        ))
        self.write()
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base, source_subject=PATIENT.split("/")[1])
            path = f"/v1/patients/{patient}/cases/CASE-ALPHA"

            def expect(status, suffix, body=None):
                code, result, _ = request(base, path + suffix, token=TOKEN_A, body=body)
                self.assertEqual(code, status, (suffix, result))
                return result

            status, note, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, note)
            lab = expect(201, "/laboratory/fhir-r4/sources", {
                "synthetic": True, "request_key": "IMPORT-BOUNDARY-LAB",
                "bundle_json": encode(example()).decode("utf-8"), "expected_previous_source_id": None,
            })
            note_qid, snapshot = create_question(self, base, patient, note["source_id"])
            selection = {"synthetic": True, "source_id": lab["source_id"],
                         "question": "What did this fictional laboratory observation report?",
                         "observation_reference": OBS, "expected_source_snapshot_sha256": snapshot}
            prepared = expect(200, "/composer/laboratory-preflight", selection)
            lab_qid = expect(201, "/composer/laboratory-questions", {
                **selection, "expected_preflight_sha256": prepared["preflight_sha256"],
                "request_key": "QUESTION-BOUNDARY-LAB",
            })["question_id"]
            self.assertNotEqual(note_qid, lab_qid)
            txt, typed = "/questions/" + note_qid, "/questions/" + lab_qid

            # The same authorized actor can exercise each of the text routes.
            # A 404 for a laboratory target must not just be a missing permission.
            reads = (("/source-review-packet", None), ("/manual-passages", None),
                     ("/evidence", None), ("/evidence-links", None),
                     ("/evidence-search", {"synthetic": True, "query": "fictional"}))
            results = {}
            for suffix, body in reads:
                result = expect(200, txt + suffix, body)
                self.assertIn(note_qid, json.dumps(result))
                self.assertNotIn(lab_qid, json.dumps(result))
                results[suffix] = result
            note_row, = expect(200, "/questions")["questions"]
            queue_row, = expect(200, "/review-queue")["items"]
            self.assertEqual((note_row["question_id"], queue_row["question_id"]), (note_qid, note_qid))
            note_anchor = {"synthetic": True, "source_snapshot_contract": note_row["source_snapshot_contract"],
                           "expected_source_snapshot_sha256": snapshot,
                           "expected_preflight_sha256": note_row["preflight_sha256"]}
            expect(200, txt + "/brief", note_anchor)
            writes = (
                ("/manual-passages", {"synthetic": True, "request_key": "PASSAGES-BOUNDARY",
                                      "expected_context_sha256": results["/manual-passages"]["context_sha256"],
                                      "references": []}),
                ("/return-for-verification", {"synthetic": True, "request_key": "RETURN-BOUNDARY",
                                              "expected_queue_fingerprint": queue_row["queue_fingerprint"],
                                              "reason": "Independently verify the fictional source."}),
                ("/followthrough", {**note_anchor, "request_key": "TASK-BOUNDARY",
                                    "title": "Inspect the fictional original", "reason": "Prepare a source question",
                                    "review_trigger": "When the source is reviewed"}),
            )
            for suffix, body in writes:
                expect(201, txt + suffix, body)
            task, = expect(200, "/followthrough")["tasks"]
            self.assertEqual(task["question_id"], note_qid)

            # Use valid-shaped commands and unused keys, so unrelated request
            # conflicts cannot mask a missing anchor-kind check.
            before = self.event_count()
            for suffix, body in (*reads, ("/brief", note_anchor), *writes):
                if body and "request_key" in body:
                    body = {**body, "request_key": body["request_key"] + "-LAB"}
                with self.subTest(route=suffix, is_write=body is not None):
                    denied = expect(404, typed + suffix, body)
                    self.assertEqual(set(denied), {"detail"})
                    self.assertNotIn(lab_qid, json.dumps(denied))
            self.assertEqual(self.event_count(), before, "refused operations must not commit read/write receipts")
            self.assertEqual([r["question_id"] for r in expect(200, "/followthrough")["tasks"]], [note_qid])
            self.assertEqual([r["question_id"] for r in expect(200, "/review-queue")["receipts"]], [note_qid])
