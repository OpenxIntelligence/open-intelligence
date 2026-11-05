"""A real mixed-anchor case must keep text-only operations scoped to text questions."""
import json

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.database import Database
from oi_api.evidence_catalog import fictional_records, seed_fictional_records
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_authored_evidence_postgres import EvidenceFixture
from test_canonical_review_flow import create_question
from test_laboratory_fhir_r4 import OBS, PATIENT, encode, example
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class LaboratoryQuestionLegacyBoundaryTests(SourceVersionFixture):
    def event_count(self):
        with self.engine.connect() as db:
            return db.execute(text("SELECT count(*) FROM identity.identity_domain_events")).scalar_one()

    def test_text_only_consumers_and_wrong_task_fingerprint_refuse_lab_target(self):
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
                    # Task writes now support either origin, but a text question's
                    # preflight can never authorize a task for a laboratory result.
                    expected_status = 409 if suffix == "/followthrough" else 404
                    denied = expect(expected_status, typed + suffix, body)
                    self.assertEqual(set(denied), {"detail"})
                    self.assertNotIn(lab_qid, json.dumps(denied))
            self.assertEqual(self.event_count(), before, "refused operations must not commit read/write receipts")
            self.assertEqual([r["question_id"] for r in expect(200, "/followthrough")["tasks"]], [note_qid])
            self.assertEqual([r["question_id"] for r in expect(200, "/review-queue")["receipts"]], [note_qid])


class LaboratoryQuestionDependentStorageTests(EvidenceFixture):
    def test_text_dependents_reject_lab_targets_and_damaged_queue_withholds_receipts(self):
        # Start with real text-derived rows of every supported type, including
        # the command and origin behind a persisted evidence report.
        self.creds[0]["actions"].extend(("review_queue_read", "review_return", "evidence_read", "evidence_link"))
        self.write()
        database = Database(self.settings)
        self.addCleanup(database.close)
        with database.registry_connection() as connection:
            seed_fictional_records(PostgresPatientRegistry(connection, lambda *args: False),
                                  fictional_records(), recorded_by="FIXTURE-AUTHOR")
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            pid, text_qid = state["patient"], state["question"]
            case = f"/v1/patients/{pid}/cases/CASE-ALPHA"
            qpath = "/questions/" + text_qid

            def expect(status, suffix, body=None):
                code, value, _ = request(base, case + suffix, token=TOKEN_A, body=body)
                self.assertEqual(code, status, (suffix, value))
                return value

            note, = expect(200, "/questions")["questions"]
            metadata, = expect(200, qpath + "/evidence-search",
                               {"synthetic": True, "query": "continuity"})["records"]
            expect(201, qpath + "/evidence-links", {
                "synthetic": True, "request_key": "TEXT-METADATA", "citation": metadata["citation"],
                "expected_metadata_sha256": metadata["metadata_sha256"],
                "source_snapshot_contract": note["source_snapshot_contract"],
                "expected_source_snapshot_sha256": note["source_snapshot_sha256"],
                "expected_preflight_sha256": note["preflight_sha256"],
            })
            passage = expect(200, qpath + "/manual-passages")
            expect(201, qpath + "/manual-passages", {
                "synthetic": True, "request_key": "TEXT-PASSAGE", "references": [],
                "expected_context_sha256": passage["context_sha256"],
            })
            queued, = expect(200, "/review-queue")["items"]
            expect(201, qpath + "/return-for-verification", {
                "synthetic": True, "request_key": "TEXT-REVIEW", "reason": "Review the fictional note.",
                "expected_queue_fingerprint": queued["queue_fingerprint"],
            })
            raw = encode(example()).decode().replace("FICTIONAL-PATIENT-A", "SUBJECT-ALPHA")
            source = expect(201, "/laboratory/fhir-r4/sources", {
                "synthetic": True, "request_key": "IMPORT-DEPENDENT-LAB", "bundle_json": raw,
            })
            world = expect(200, "/world-model")
            selection = {"synthetic": True, "source_id": source["source_id"],
                         "question": "What question follows from this fictional lab result?",
                         "observation_reference": OBS, "expected_source_snapshot_sha256": world["snapshot_fingerprint"]}
            preview = expect(200, "/composer/laboratory-preflight", selection)
            lab_qid = expect(201, "/composer/laboratory-questions", {
                **selection, "request_key": "QUESTION-DEPENDENT-LAB",
                "expected_preflight_sha256": preview["preflight_sha256"],
            })["question_id"]
            tables = ("question_review_receipts", "question_passage_revisions", "question_evidence_links",
                      "question_evidence_assessments", "question_evidence_reports", "evidence_command_origins",
                      "evidence_commands")
            for table in tables:
                # Re-submit a real row with only its question target altered.
                # The anchor guard must reject it before any duplicate-key or
                # unrelated downstream constraint can mask a missing check.
                if table == "evidence_commands":
                    match = "r.operation='report' AND r.result->>'question_id'=:text_qid"
                    fields = "jsonb_build_object('result',r.result || jsonb_build_object('question_id',CAST(:lab_qid AS text)))"
                else:
                    match = "r.question_id=:text_qid"
                    fields = "jsonb_build_object('question_id',CAST(:lab_qid AS text))"
                if table == "question_evidence_links":
                    # Give the link authentic fingerprints for the lab target,
                    # so its original patient/case/source checks all succeed.
                    fields += """ || (SELECT jsonb_build_object(
                        'source_snapshot_contract',q.source_snapshot_contract,
                        'source_snapshot_sha256',q.source_snapshot_sha256,
                        'preflight_sha256',q.preflight_sha256)
                        FROM investigation.source_questions q WHERE q.question_id=:lab_qid)"""
                identity = "OVERRIDING SYSTEM VALUE" if table == "question_evidence_assessments" else ""
                marker = ("OI-LAB-CITATION-ANCHOR-REQUIRED" if table == "question_evidence_links"
                          else "OI-TEXT-QUESTION-TARGET-REQUIRED")
                with self.subTest(table=table), self.assertRaisesRegex(DBAPIError, marker):
                    with self.engine.begin() as db:
                        db.execute(text(f"""
                            INSERT INTO investigation.{table} {identity}
                            SELECT (jsonb_populate_record(NULL::investigation.{table}, to_jsonb(r) || {fields})).*
                            FROM investigation.{table} r WHERE {match} LIMIT 1
                        """), {"text_qid": text_qid, "lab_qid": lab_qid})

            # Inject one historically impossible receipt under a disabled new
            # guard, leaving all other installed guards active. Simulates a
            # damaged restore. Neither the typed ID nor reason may leave HTTP.
            with self.engine.begin() as db:
                db.exec_driver_sql("ALTER TABLE investigation.question_review_receipts "
                                   "DISABLE TRIGGER oi_anchor_text_question_required")
                db.execute(text("""
                    INSERT INTO investigation.question_review_receipts
                    SELECT (jsonb_populate_record(NULL::investigation.question_review_receipts,
                             to_jsonb(r) || jsonb_build_object(
                                 'receipt_id','REVIEW-'||repeat('C',32), 'request_key','DAMAGED-RESTORE',
                                 'question_id',q.question_id, 'source_snapshot_sha256',q.source_snapshot_sha256,
                                 'reason','Fictional damaged restore receipt'))).*
                    FROM investigation.question_review_receipts r
                    CROSS JOIN investigation.source_questions q
                    WHERE r.question_id=:text_qid AND q.question_id=:lab_qid
                """), {"text_qid": text_qid, "lab_qid": lab_qid})
                db.exec_driver_sql("ALTER TABLE investigation.question_review_receipts "
                                   "ENABLE TRIGGER oi_anchor_text_question_required")
            self.assertEqual(expect(503, "/review-queue"), {"detail": "Patient registry unavailable"})
