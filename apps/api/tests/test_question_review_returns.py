"""Actual PostgreSQL 16 acceptance for the first-party nonterminal review-return owner.

All data is independently fictional. The queue is a projection of the existing
canonical source_questions; the single new durable owner stores immutable
returned-only receipts, never clinical approval or professional signature.
"""
from concurrent.futures import ThreadPoolExecutor
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
import unittest

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.migrate import migrate
from oi_api.request_limits import PatientRequestLimit
from oi_api import patients as patient_routes
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_questions import QUESTION
import test_source_questions as question_fixtures
from test_source_versions import AMENDED, SourceVersionFixture

REASON = "Please independently verify this fictional source quotation and uncertainty."
SOURCE_CONTRACT = "oi.pg-source-world-model/1"
FINGERPRINT_CONTRACT = "oi.synthetic-source-review-return/2"


class QuestionReviewContractTests(unittest.TestCase):
    def test_canonical_review_routes_are_in_the_existing_api_contract(self):
        schema = create_app(Settings.from_env({})).openapi()
        prefix = "/v1/patients/{patient_id}/cases/{case_id}"
        queue = prefix + "/review-queue"
        returning = prefix + "/questions/{question_id}/return-for-verification"
        self.assertIn(queue, list(schema["paths"]))
        self.assertIn(returning, list(schema["paths"]))
        self.assertEqual(schema["paths"][queue]["get"]["security"],
                         [{"SyntheticFixture": []}])
        self.assertEqual(schema["paths"][returning]["post"]["security"],
                         [{"SyntheticFixture": []}])
        models = schema["components"]["schemas"]
        self.assertEqual(models["QuestionReviewQueue"]["properties"]["contract"]["const"],
                         "oi.synthetic-question-review-return-queue/2")
        self.assertIn("access_receipt_id", models["QuestionReviewQueue"]["required"])
        for model in ("QuestionReviewItem", "QuestionReturnHistory"):
            self.assertIn("source_snapshot_contract", models[model]["required"])
            self.assertIn("queue_fingerprint_contract", models[model]["required"])
        self.assertEqual(models["QuestionReviewItem"]["properties"]
                         ["queue_fingerprint_contract"]["const"], FINGERPRINT_CONTRACT)
        self.assertEqual(set(models["ReturnForVerificationReceipt"]["properties"]),
                         {"receipt_id", "question_id", "duplicate"})

    def test_return_ingress_bounds_declared_and_chunked_bodies_before_parsing(self):
        async def exercise(declared):
            seen = []
            async def downstream(scope, receive, send):
                seen.append("downstream")
            chunks = iter([
                {"type": "http.request", "body": b"x" * 8000, "more_body": True},
                {"type": "http.request", "body": b"x" * 8000, "more_body": True},
                {"type": "http.request", "body": b"x" * 1000, "more_body": False},
            ])
            async def receive():
                return next(chunks)
            async def send(message):
                seen.append(message)
            await PatientRequestLimit(downstream)({
                "type": "http", "method": "POST", "path":
                "/v1/patients/PAT-FICTION/cases/CASE-FICTION/questions/"
                "QUESTION-FICTION/return-for-verification",
                "headers": [(b"content-length", b"17000")] if declared else [],
            }, receive, send)
            self.assertNotIn("downstream", seen)
            self.assertEqual(seen[0]["status"], 413)
            self.assertIn((b"cache-control", b"no-store"), seen[0]["headers"])
            self.assertEqual(json.loads(seen[1]["body"]),
                             {"detail": "Request body too large"})
        for declared in (False, True):
            with self.subTest(content_length=declared):
                asyncio.run(exercise(declared))


class QuestionReviewReturnHTTPTests(SourceVersionFixture):
    # Reuse the canonical flow helpers without inheriting/re-running the whole
    # question and source test suites; those remain in their original modules.
    path = staticmethod(question_fixtures.SourceQuestionHTTPTests.path)
    model_path = staticmethod(question_fixtures.SourceQuestionHTTPTests.model_path)
    world = question_fixtures.SourceQuestionHTTPTests.world
    preflight = question_fixtures.SourceQuestionHTTPTests.preflight
    save = question_fixtures.SourceQuestionHTTPTests.save
    prepared = question_fixtures.SourceQuestionHTTPTests.prepared

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend([
            "composer_context_read", "question_create", "question_read",
            "review_queue_read", "review_return",
        ])
        self.write()

    @staticmethod
    def queue_path(patient,case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/review-queue"

    def inbox(self,base,patient,*,case="CASE-ALPHA",token=TOKEN_A):
        return request(base,self.queue_path(patient,case),token=token)

    def returning(self,base,patient,question_id,fingerprint,*,
                  request_key="RETURN-FICTION-ONE",reason=REASON,
                  case="CASE-ALPHA",token=TOKEN_A,**extra):
        return request(base,
            f"/v1/patients/{patient}/cases/{case}/questions/"
            f"{question_id}/return-for-verification",
            token=token, body={
                "synthetic":True, "request_key":request_key,
                "expected_queue_fingerprint":fingerprint,
                "reason":reason,**extra,
            })

    def prepared_question(self,base,patient,*,source=None,key="QUESTION-KEY-ONE",
                          line=8,question=QUESTION):
        if source is None:
            source=self.ingest(base,patient)[1]["source_id"]
        preflight=self.prepared(base,patient,source,line=line,question=question)
        save=self.save(base,patient,preflight,request_key=key)
        self.assertEqual(save[0],201,save)
        return save[1]["question_id"],source

    def test_return_is_nonterminal_atomic_idempotent_and_derived_from_question(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,source=self.prepared_question(base,patient)
            status,initial,_=self.inbox(base,patient)
            self.assertEqual(status,200)
            self.assertEqual(initial["contract"],"oi.synthetic-question-review-return-queue/2")
            self.assertTrue(initial["access_receipt_id"].startswith("ACCESS-"))
            self.assertEqual(len(initial["items"]),1)
            self.assertEqual(initial["receipts"],[])
            row=initial["items"][0]
            self.assertEqual(row["question_id"],qid)
            self.assertEqual(row["source_id"],source)
            self.assertEqual(row["source_snapshot_contract"], SOURCE_CONTRACT)
            self.assertEqual(row["queue_fingerprint_contract"], FINGERPRINT_CONTRACT)
            self.assertEqual(row["review_state"],"awaiting_independent_verification")
            fingerprint=row["queue_fingerprint"]
            self.assertEqual(len(fingerprint),64)
            for property in ("external_notification_sent","reviewer_identity_verified",
                             "clinical_approval","review_completion_supported"):
                self.assertIs(initial[property],False)
            with self.engine.connect() as conn:
                before=conn.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events"
                )).scalar_one()
            response=self.returning(base,patient,qid,fingerprint)
            self.assertEqual(response[0],201,response)
            receipt=response[1]["receipt_id"]
            self.assertTrue(receipt.startswith("REVIEW-"))
            self.assertEqual(len(receipt),39)
            duplicate=self.returning(base,patient,qid,fingerprint)
            self.assertEqual(duplicate[0],200)
            self.assertEqual(duplicate[1],{"receipt_id":receipt,"question_id":qid,"duplicate":True})
            status,returned,_=self.inbox(base,patient)
            self.assertEqual(status,200)
            self.assertEqual(returned["items"][0]["review_state"],
                             "returned_for_independent_verification")
            self.assertEqual(returned["items"][0]["current_return_receipt_id"],receipt)
            self.assertEqual(returned["items"][0]["return_count"],1)
            self.assertEqual(returned["items"][0]["prior_return_count"],0)
            self.assertEqual(len(returned["receipts"]),1)
            entry=returned["receipts"][0]
            self.assertEqual(entry["receipt_id"],receipt)
            self.assertEqual(entry["source_snapshot_contract"], SOURCE_CONTRACT)
            self.assertEqual(entry["queue_fingerprint_contract"], FINGERPRINT_CONTRACT)
            self.assertEqual(entry["action"],"returned")
            self.assertEqual(entry["reason"],REASON)
            self.assertEqual(entry["actor_label"],"ACTOR-ALPHA")
            self.assertFalse(entry["reviewer_identity_verified"])
            self.assertFalse(entry["external_notification_sent"])
            self.assertFalse(entry["clinical_approval"])
            self.assertFalse(returned["review_completion_supported"])
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM investigation.question_review_receipts"
                )).scalar_one(),1)
                events=conn.execute(text(
                    "SELECT event_type FROM identity.identity_domain_events"
                    " WHERE patient_id=:patient ORDER BY id"
                ),{"patient":patient}).scalars().all()
                self.assertEqual(events.count(
                    "investigation.review.returned_for_verification"),1)
                # New return, duplicate recovery and queue read each audit the
                # disclosed canonical source context, in addition to one return.
                self.assertEqual(len(events),before+4)
        with running_server(create_app(self.settings)) as again:
            self.assertEqual(self.inbox(again,patient)[1]["receipts"][0]["receipt_id"],receipt)
            self.assertEqual(self.returning(again,patient,qid,fingerprint)[1]["duplicate"],True)

    def test_correction_keeps_historical_receipt_and_forces_fresh_current_question(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,original=self.prepared_question(base,patient)
            old_fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            receipt=self.returning(base,patient,qid,old_fp)[1]["receipt_id"]
            corrected=self.ingest(base,patient,AMENDED)
            self.assertEqual(corrected[0],201)
            current=corrected[1]["source_id"]
            status,after,_=self.inbox(base,patient)
            self.assertEqual(status,200)
            row=after["items"][0]
            self.assertEqual(row["source_id"],original)
            self.assertEqual(row["review_state"],"source_reassessment_required")
            self.assertIsNone(row["queue_fingerprint"])
            self.assertIsNone(row["current_return_receipt_id"])
            self.assertEqual((row["return_count"],row["prior_return_count"]),(0,1))
            self.assertEqual(after["receipts"][0]["receipt_id"],receipt)
            # A retry of a previously committed exact request is recoverable,
            # but a NEW receipt against the old source is not permitted.
            retry=self.returning(base,patient,qid,old_fp)
            self.assertEqual((retry[0],retry[1]["duplicate"]),(200,True))
            self.assertEqual(self.returning(base,patient,qid,old_fp,
                             request_key="RETURN-OLD-NEW")[0],409)
            new_question,_=self.prepared_question(
                base,patient,source=current,line=9,
                question="What is the corrected fictional marker state?",key="QUESTION-KEY-TWO")
            new_queue=self.inbox(base,patient)[1]
            self.assertEqual(len(new_queue["items"]),2)
            current_item=next(r for r in new_queue["items"] if r["question_id"]==new_question)
            self.assertEqual(current_item["review_state"],"awaiting_independent_verification")
            self.assertEqual(self.returning(base,patient,new_question,
                current_item["queue_fingerprint"],request_key="RETURN-CURRENT")[0],201)
            final=self.inbox(base,patient)[1]
            self.assertEqual(len(final["receipts"]),2)
            self.assertEqual({x["review_state"] for x in final["items"]},
                             {"source_reassessment_required","returned_for_independent_verification"})

    def test_grants_patient_case_and_purpose_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.inbox(base,patient,token=TOKEN_B)[0],404)
            self.assertEqual(self.inbox(base,patient,case="CASE-BETA")[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp,token=TOKEN_B)[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp,case="CASE-BETA")[0],404)
            self.creds[0]["actions"].remove("review_return")
            self.write()
            self.assertEqual(self.inbox(base,patient)[0],200)
            self.assertEqual(self.returning(base,patient,qid,fp)[0],404)
            self.creds[0]["actions"].append("review_return")
            self.creds[0]["actions"].remove("review_queue_read")
            self.write()
            self.assertEqual(self.inbox(base,patient)[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp)[0],201)
            self.creds[0]["actions"].append("review_queue_read")
            self.creds[0]["actions"].remove("question_read")
            self.write()
            self.assertEqual(self.inbox(base,patient)[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp,request_key="OTHER")[0],404)
            self.creds[0]["actions"].append("question_read")
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(self.inbox(base,patient)[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp,request_key="OTHER")[0],404)
            self.creds[0]["actions"].append("source_read")
            self.creds[0]["purpose"]="research"
            self.write()
            self.assertEqual(self.inbox(base,patient)[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp,request_key="OTHER")[0],404)

    def test_stale_fingerprint_intent_conflict_and_bad_reason_are_denied(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.returning(base,patient,qid,"0"*64)[0],409)
            self.assertEqual(self.returning(base,patient,qid,fp,
                                            reason="short")[0],422)
            self.assertEqual(self.returning(base,patient,qid,fp,
                                            reason="Malformed\nreason invalid")[0],422)
            self.assertEqual(self.returning(base,patient,qid,fp,
                                            reason="Please verify.\u202e Hidden direction.")[0],422)
            self.assertEqual(self.returning(base,patient,qid,fp,
                                            synthetic=False)[0],422)
            self.assertEqual(self.returning(base,patient,qid,fp)[0],201)
            self.assertEqual(self.returning(base,patient,qid,fp,
                reason="A different request for verification is not the same intent.")[0],409)
            self.assertEqual(self.returning(base,patient,qid,fp,
                request_key="SECOND-RETURN")[0],201)

    def test_question_return_is_immutable_and_cross_patient_inserts_are_denied(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.returning(base,patient,qid,fp)[0],201)
            for query in (
                "UPDATE investigation.question_review_receipts SET action='reviewed'",
                "UPDATE investigation.question_review_receipts SET reason='forged'",
                "DELETE FROM investigation.question_review_receipts",
            ):
                with self.subTest(query=query),self.assertRaises(SQLAlchemyError):
                    with self.engine.begin() as conn:
                        conn.execute(text(query))
            with self.assertRaises(SQLAlchemyError):
                with self.engine.begin() as conn:
                    conn.execute(text(
                        "INSERT INTO investigation.question_review_receipts "
                        "(receipt_id,question_id,patient_id,case_id,origin_org,"
                        "request_key,intent_sha256,queue_fingerprint,"
                        "source_snapshot_sha256,actor,purpose,action,reason,"
                        "source_snapshot_contract,queue_fingerprint_contract) "
                        "SELECT 'REVIEW-'||repeat('F',32),question_id,patient_id,"
                        "case_id,'ORG-OTHER','FALSE-ORG-KEY',repeat('f',64),"
                        "repeat('f',64),source_snapshot_sha256,actor,purpose,"
                        "'returned','Independent fictional verification is needed',"
                        "'oi.pg-source-world-model/1','oi.synthetic-source-review-return/2' "
                        "FROM investigation.source_questions LIMIT 1"
                    ))
            self.assertEqual(len(self.inbox(base,patient)[1]["receipts"]),1)

    def test_event_failure_rolls_back_review_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            original=PostgresPatientRegistry.append_event
            def blocked(registry,pid,kind,**details):
                if kind=="investigation.review.returned_for_verification":
                    raise RuntimeError("Simulated failure in canonical event append")
                return original(registry,pid,kind,**details)
            with patch.object(PostgresPatientRegistry,"append_event",blocked):
                self.assertEqual(self.returning(base,patient,qid,fp)[0],503)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM investigation.question_review_receipts"
                )).scalar_one(),0)
            self.assertEqual(self.inbox(base,patient)[1]["receipts"],[])
            self.assertEqual(self.returning(base,patient,qid,fp)[0],201)

    def test_simultaneous_same_key_return_uses_single_receipt_event(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            def once(_):
                return self.returning(base,patient,qid,fp)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(once,range(2)))
            self.assertEqual({r[0] for r in results},{200,201})
            self.assertEqual(len({r[1]["receipt_id"] for r in results}),1)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM investigation.question_review_receipts"
                )).scalar_one(),1)
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='investigation.review.returned_for_verification'"
                )).scalar_one(),1)

    def test_revoked_binding_denies_history_and_new_returns_without_erasing_receipts(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.returning(base,patient,qid,fp)[0],201)
            revoked=request(base,
                f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A,body={"synthetic":True,
                                    "reason":"Fictional case mapping deliberately revoked"})
            self.assertEqual(revoked[0],200)
            self.assertEqual(self.inbox(base,patient)[0],404)
            self.assertEqual(self.returning(base,patient,qid,fp)[0],404)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM investigation.question_review_receipts"
                )).scalar_one(),1)

    def persisted_state(self):
        with self.engine.connect() as conn:
            return (
                conn.execute(text("SELECT * FROM investigation.question_review_receipts "
                                  "ORDER BY receipt_id")).all(),
                conn.execute(text("SELECT * FROM identity.identity_domain_events "
                                  "ORDER BY id")).all(),
            )

    def assert_withheld(self, response, expected, before):
        status, body, headers = response
        self.assertEqual(status, expected, body)
        self.assertEqual(set(body), {"detail"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        for private in (TOKEN_A, QUESTION, REASON, "PRIVATE-REVIEW"):
            self.assertNotIn(private, json.dumps(body))
        self.assertEqual(self.persisted_state(), before)

    def test_final_dto_rechecks_authority_for_queue_new_return_and_duplicate(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            fp = self.inbox(base, patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.returning(base, patient, qid, fp)[0], 201)
            initial = copy.deepcopy(self.creds)
            for operation in ("queue", "new", "duplicate"):
                action = "review_queue_read" if operation == "queue" else "review_return"
                changes = [(grant, {"actions": [a for a in initial[0]["actions"]
                                                if a != grant]}, 404)
                           for grant in ("patient_read", "source_read", "question_read", action)]
                changes += [
                    ("patient_scope", {"patient_ids": []}, 404),
                    ("actor", {"actor": "ACTOR-CHANGED"}, 404),
                    ("organization", {"organization": "ORG-CHANGED"}, 404),
                    ("purpose", {"purpose": "research"}, 404),
                    ("expiry", {"expires_at": (datetime.now(timezone.utc)
                                               - timedelta(minutes=1)).isoformat()}, 401),
                    ("credential_missing", None, 401),
                    ("provider_failure", None, 503),
                ]
                for name, change, expected in changes:
                    with self.subTest(operation=operation, change=name):
                        self.creds = copy.deepcopy(initial)
                        self.write()
                        before = self.persisted_state()
                        model_name = ("QuestionReviewQueue" if operation == "queue"
                                      else "ReturnForVerificationReceipt")
                        model = getattr(patient_routes, model_name)

                        def withdraw_after_dto(**values):
                            result = model(**values)
                            if name == "credential_missing":
                                self.creds.pop(0)
                                self.write()
                            elif name == "provider_failure":
                                self.access.write_text("PRIVATE-REVIEW-PROVIDER")
                            else:
                                self.creds[0].update(change)
                                self.write()
                            return result

                        with patch.object(patient_routes, model_name,
                                          side_effect=withdraw_after_dto) as prepared:
                            response = (self.inbox(base, patient) if operation == "queue" else
                                        self.returning(base, patient, qid, fp,
                                            request_key="RETURN-FICTION-ONE" if operation == "duplicate"
                                            else "RETURN-DENIED-NEW"))
                        prepared.assert_called_once()
                        self.assert_withheld(response, expected, before)

    def test_return_event_is_followed_by_fresh_authority_before_commit(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            fp = self.inbox(base, patient)[1]["items"][0]["queue_fingerprint"]
            before = self.persisted_state()
            original = PostgresPatientRegistry.append_event
            observed = []

            def withdraw_after_event(registry, pid, kind, **details):
                result = original(registry, pid, kind, **details)
                if kind == "investigation.review.returned_for_verification":
                    observed.append(details["receipt_id"])
                    self.creds[0]["actions"].remove("review_return")
                    self.write()
                return result

            with patch.object(PostgresPatientRegistry, "append_event", withdraw_after_event):
                response = self.returning(base, patient, qid, fp)
            self.assertEqual(len(observed), 1)
            self.assert_withheld(response, 404, before)

    def test_source_receipt_failure_rolls_back_new_return_and_withholds_queue_and_retry(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            fp = self.inbox(base, patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.returning(base, patient, qid, fp)[0], 201)
            before = self.persisted_state()
            with self.engine.begin() as conn:
                conn.exec_driver_sql("""
                    CREATE FUNCTION identity.reject_review_source_receipt() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type='source.read_authorized' THEN
                        RAISE EXCEPTION 'PRIVATE-REVIEW-ACCESS-AUDIT';
                    END IF;
                    RETURN NEW; END; $$;
                """)
                conn.exec_driver_sql(
                    "CREATE TRIGGER reject_review_source_receipt "
                    "BEFORE INSERT ON identity.identity_domain_events "
                    "FOR EACH ROW EXECUTE FUNCTION identity.reject_review_source_receipt()"
                )
            for operation in ("queue", "new", "duplicate"):
                with self.subTest(operation=operation):
                    response = (self.inbox(base, patient) if operation == "queue" else
                                self.returning(base, patient, qid, fp,
                                    request_key="RETURN-FICTION-ONE" if operation == "duplicate"
                                    else "RETURN-AUDIT-FAILURE"))
                    self.assert_withheld(response, 503, before)

    def test_dto_failure_rolls_back_prepared_return_and_event(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            fp = self.inbox(base, patient)[1]["items"][0]["queue_fingerprint"]
            before = self.persisted_state()
            model = patient_routes.ReturnForVerificationReceipt

            def invalid_response(**values):
                return model(**values, clinical_approval=True)

            with patch.object(patient_routes, "ReturnForVerificationReceipt",
                              side_effect=invalid_response) as prepared:
                response = self.returning(base, patient, qid, fp)
            prepared.assert_called_once()
            self.assert_withheld(response, 503, before)

    def test_review_actions_do_not_require_composer_or_question_create(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            for grant in ("composer_context_read", "question_create"):
                self.creds[0]["actions"].remove(grant)
            self.write()
            status, queue, _ = self.inbox(base, patient)
            self.assertEqual(status, 200, queue)
            response = self.returning(base, patient, qid, queue["items"][0]["queue_fingerprint"])
            self.assertEqual(response[0], 201, response)

    def test_receipt_bound_preserves_readable_history_and_duplicate_recovery(self):
        from oi_api import question_review_returns as owner
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            fp = self.inbox(base, patient)[1]["items"][0]["queue_fingerprint"]
            with patch.object(owner, "MAX_RECEIPTS", 1):
                self.assertEqual(self.returning(base, patient, qid, fp)[0], 201)
                before = self.persisted_state()
                self.assert_withheld(self.returning(base, patient, qid, fp,
                                     request_key="RETURN-OVER-LIMIT"), 422, before)
                self.assertEqual(self.inbox(base, patient)[0], 200)
                self.assertEqual(self.returning(base, patient, qid, fp)[0], 200)

    def test_downgrade_cannot_erase_canonical_receipt_provenance(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            qid, _ = self.prepared_question(base, patient)
            fp = self.inbox(base, patient)[1]["items"][0]["queue_fingerprint"]
            self.assertEqual(self.returning(base, patient, qid, fp)[0], 201)
        before = self.persisted_state()
        with self.assertRaises(CommandError):
            migrate(self.admin, "downgrade", "0006_source_questions")
        self.assertEqual(self.persisted_state(), before)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one(), "0014_manual_report_context")


if __name__=="__main__":
    unittest.main()
