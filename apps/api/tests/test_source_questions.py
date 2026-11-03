"""Actual PG16 acceptance: durable canonical source questions, no clinical approval.

Uses the existing patient/case/original-source owner, exact preflight and
append-only identity event journal. All cases and source statements fictional.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import unittest
from unittest.mock import patch

from sqlalchemy import text
from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry

from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionHTTPTests as SourceFixture, AMENDED


QUESTION = "What is independently verifiable about this fictional source statement?"
REVISED = "What changed in the corrected fictional source report?"


class SourceQuestionHTTPTests(SourceFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend([
            "composer_context_read", "question_create", "question_read",
        ])
        self.write()

    @staticmethod
    def path(pid, case="CASE-ALPHA"):
        return f"/v1/patients/{pid}/cases/{case}/questions"

    @staticmethod
    def model_path(pid, case="CASE-ALPHA"):
        return f"/v1/patients/{pid}/cases/{case}/world-model"

    def world(self, base, patient):
        status, result, _ = request(base, self.model_path(patient), token=TOKEN_A)
        self.assertEqual(status, 200)
        return result

    def preflight(self, base, patient, source, fingerprint, *, line=8,
                  question=QUESTION, token=TOKEN_A, case="CASE-ALPHA"):
        return request(
            base, f"/v1/patients/{patient}/cases/{case}/composer/source-preflight",
            token=token, body={
                "synthetic": True, "expected_source_snapshot_sha256": fingerprint,
                "source_id": source, "source_line": line, "question": question,
            },
        )

    def save(self, base, patient, preflight, *, request_key="QUESTION-KEY-ONE",
             case="CASE-ALPHA", token=TOKEN_A, **override):
        data = {
            "synthetic": True, "request_key": request_key,
            "question": preflight["question"],
            "source_id": preflight["selected_source"]["source_id"],
            "source_line": preflight["selected_source"]["line"],
            "expected_source_snapshot_sha256": preflight["source_snapshot_sha256"],
            "expected_preflight_sha256": preflight["preflight_sha256"],
        }
        data.update(override)
        return request(base, self.path(patient,case), token=token, body=data)

    def listing(self, base, patient, *, case="CASE-ALPHA", token=TOKEN_A):
        return request(base, self.path(patient,case), token=token)

    def prepared(self, base, patient, source, *, line=8, question=QUESTION):
        fingerprint = self.world(base, patient)["source_snapshot_sha256"]
        result = self.preflight(base, patient, source, fingerprint,
                                line=line, question=question)
        self.assertEqual(result[0], 200, result)
        return result[1]

    def test_save_is_durable_idempotent_atomic_and_not_a_clinical_review(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base, patient)[1]["source_id"]
            preflight = self.prepared(base, patient, source)
            with self.engine.connect() as db:
                before_events = db.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events"
                )).scalar_one()
            code, created, _ = self.save(base, patient, preflight)
            self.assertEqual((code, created["duplicate"]), (201, False))
            qid = created["question_id"]
            self.assertTrue(qid.startswith("QUESTION-"))
            self.assertEqual(len(qid), 41)
            self.assertEqual(self.save(base, patient, preflight)[0], 200)
            self.assertEqual(self.save(base, patient, preflight)[1],
                             {"question_id": qid, "duplicate": True})
            status, listing, _ = self.listing(base, patient)
            self.assertEqual(status, 200)
            self.assertEqual(listing["patient_id"], patient)
            self.assertEqual(listing["case_id"], "CASE-ALPHA")
            self.assertTrue(listing["synthetic"])
            self.assertFalse(listing["clinical_approval"])
            self.assertFalse(listing["clinical_review_connected"])
            self.assertEqual(len(listing["questions"]), 1)
            item = listing["questions"][0]
            self.assertEqual(item["question_id"], qid)
            self.assertEqual(item["question"], QUESTION)
            self.assertEqual(item["source_id"], source)
            self.assertEqual(item["source_line"], 8)
            self.assertEqual(item["source_version"], 1)
            self.assertEqual(item["source_sha256"],
                             hashlib.sha256((
                                 "OI-SYNTHETIC-REPORT/1\n"
                                 "Patient: CASE-ALPHA\n"
                                 "Document: DOC-ONE\n"
                                 "Type: pathology\n"
                                 "Event-Date: 2026-01-10\n"
                                 "Issued-At: 2026-01-11\n"
                                 "Specimen: SPECIMEN-ONE\n"
                                 "Finding: marker|not-reported|"
                                 "Fictional café <script>literal</script>.\n"
                             ).encode()).hexdigest())
            self.assertEqual(item["source_context_state"], "current_unreviewed_question")
            self.assertEqual(item["human_review_state"], "not_submitted")
            self.assertFalse(item["model_executed"])
            self.assertFalse(item["clinical_approval"])
            self.assertNotIn("Fictional café", str(item))
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.source_questions"
                )).scalar_one(), 1)
                events = db.execute(text(
                    "SELECT event_type FROM identity.identity_domain_events "
                    "WHERE patient_id=:pid ORDER BY id"
                ), {"pid":patient}).scalars().all()
                self.assertEqual(events.count("investigation.question.created"), 1)
                self.assertEqual(len(events), before_events+1)
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(self.listing(restarted,patient)[1]["questions"][0]["question_id"],qid)
            self.assertEqual(self.save(restarted,patient,preflight)[1]["duplicate"],True)

    def test_amendment_reopens_saved_question_without_retarget_or_approval(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            old = self.ingest(base, patient)[1]["source_id"]
            original = self.prepared(base, patient, old)
            first = self.save(base,patient,original)[1]["question_id"]
            current = self.ingest(base,patient,AMENDED)
            self.assertEqual(current[0],201)
            new_id = current[1]["source_id"]
            recorded = self.listing(base,patient)[1]["questions"][0]
            self.assertEqual(recorded["question_id"],first)
            self.assertEqual(recorded["source_id"],old)
            self.assertEqual(recorded["source_context_state"],"source_reassessment_required")
            self.assertEqual(recorded["human_review_state"],"not_submitted")
            self.assertEqual(self.save(base,patient,original)[0],200)
            self.assertEqual(self.save(base,patient,original,request_key="NEW-KEY")[0],409)
            current_world = self.world(base,patient)
            changed = self.preflight(base,patient,new_id,
                current_world["source_snapshot_sha256"],line=9,question=REVISED)
            self.assertEqual(changed[0],200)
            self.assertEqual(self.save(base,patient,changed[1],
                                       request_key="REVISED-KEY")[0],201)
            all_questions = self.listing(base,patient)[1]["questions"]
            self.assertEqual(len(all_questions),2)
            self.assertEqual({q["source_context_state"] for q in all_questions},
                             {"current_unreviewed_question",
                              "source_reassessment_required"})
            self.assertEqual(all_questions[0]["source_id"],old)
            self.assertEqual(all_questions[1]["source_id"],new_id)

    def test_wrong_patient_case_action_purpose_and_request_key_collision_denied(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base,patient)[1]["source_id"]
            preflight = self.prepared(base,patient,source)
            self.assertEqual(self.save(base,patient,preflight)[0],201)
            self.assertEqual(self.save(base,patient,preflight,
                question="Different fictional question about this source?")[0],409)
            self.assertEqual(self.save(base,patient,preflight,
                request_key="BAD-NEW",case="CASE-BETA")[0],404)
            self.assertEqual(self.save(base,patient,preflight,
                request_key="BAD-PAT",token=TOKEN_B)[0],404)
            self.assertEqual(self.listing(base,patient,token=TOKEN_B)[0],404)
            self.creds[0]["actions"].remove("question_create")
            self.write()
            self.assertEqual(self.save(base,patient,preflight)[0],404)
            self.assertEqual(self.listing(base,patient)[0],200)
            self.creds[0]["actions"].append("question_create")
            self.creds[0]["actions"].remove("question_read")
            self.write()
            self.assertEqual(self.listing(base,patient)[0],404)
            self.creds[0]["actions"].append("question_read")
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(self.listing(base,patient)[0],404)
            self.assertEqual(self.save(base,patient,preflight)[0],404)
            self.creds[0]["actions"].append("source_read")
            self.creds[0]["purpose"]="research"
            self.write()
            self.assertEqual(self.save(base,patient,preflight)[0],404)
            self.assertEqual(self.listing(base,patient)[0],404)
            self.creds[0]["purpose"]="operations"
            self.write()
            self.assertEqual(self.listing(base,patient)[0],200)

    def test_event_failure_rolls_back_question_without_partial_row(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base,patient)[1]["source_id"]
            preflight = self.prepared(base,patient,source)
            prior = PostgresPatientRegistry.append_event
            def blocked(registry, pid, kind, **details):
                if kind=="investigation.question.created":
                    raise RuntimeError("Fictional question event intentionally unavailable")
                return prior(registry,pid,kind,**details)
            with patch.object(PostgresPatientRegistry,"append_event",blocked):
                self.assertEqual(self.save(base,patient,preflight)[0],503)
            self.assertEqual(self.listing(base,patient)[1]["questions"],[])
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.source_questions"
                )).scalar_one(),0)
            self.assertEqual(self.save(base,patient,preflight)[0],201)

    def test_db_guards_block_mutation_and_wrong_patient_source_insert(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base,patient)[1]["source_id"]
            preflight = self.prepared(base,patient,source)
            self.assertEqual(self.save(base,patient,preflight)[0],201)
            for stmt in (
                "DELETE FROM investigation.source_questions",
                "UPDATE investigation.source_questions SET question='forged'",
            ):
                with self.subTest(stmt=stmt),self.assertRaises(Exception):
                    with self.engine.begin() as db:
                        db.exec_driver_sql(stmt)
            with self.engine.begin() as db:
                sample = db.execute(text(
                    "SELECT question_id,patient_id,case_id,origin_org,request_key,"
                    "intent_sha256,actor,purpose,question,source_id,source_line,"
                    "source_sha256,source_version,source_snapshot_sha256,preflight_sha256 "
                    "FROM investigation.source_questions"
                )).one()
            fields=[*sample]
            fields[0]="QUESTION-"+"B"*32
            fields[3]="ORG-OTHER"
            fields[4]="FORGED-QUESTION-KEY"
            with self.assertRaises(Exception):
                with self.engine.begin() as db:
                    db.execute(text(
                        "INSERT INTO investigation.source_questions "
                        "(question_id,patient_id,case_id,origin_org,request_key,"
                        "intent_sha256,actor,purpose,question,source_id,source_line,"
                        "source_sha256,source_version,source_snapshot_sha256,preflight_sha256) "
                        "VALUES (:q,:p,:c,:o,:r,:i,:a,:purpose,:question,:s,:line,:hash,"
                        ":version,:fingerprint,:preflight)"
                    ), dict(zip(("q","p","c","o","r","i","a","purpose","question",
                                 "s","line","hash","version","fingerprint","preflight"),fields)))
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.source_questions"
                )).scalar_one(),1)

    def test_concurrent_identical_question_keys_commit_one_event(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            source=self.ingest(base,pid)[1]["source_id"]
            preflight=self.prepared(base,pid,source)
            barrier=threading.Barrier(2)
            def submit():
                barrier.wait(timeout=5)
                return self.save(base,pid,preflight)
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(submit)
                second=pool.submit(submit)
                results=[first.result(timeout=20),second.result(timeout=20)]
            self.assertEqual(sorted(r[0] for r in results),[200,201])
            self.assertEqual(results[0][1]["question_id"],results[1][1]["question_id"])
            with self.engine.connect() as db:
                count=db.execute(text(
                    "SELECT count(*) FROM investigation.source_questions"
                )).scalar_one()
                events=db.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='investigation.question.created'"
                )).scalar_one()
            self.assertEqual((count,events),(1,1))


if __name__=="__main__":
    unittest.main()
