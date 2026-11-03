"""Actual PostgreSQL 16 acceptance for the first-party nonterminal review-return owner.

All data is independently fictional. The queue is a projection of the existing
canonical source_questions; the single new durable owner stores immutable
returned-only receipts, never clinical approval or professional signature.
"""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import unittest

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_questions import SourceQuestionHTTPTests as QuestionFixture, QUESTION
from test_source_versions import AMENDED

REASON = "Please independently verify this fictional source quotation and uncertainty."


class QuestionReviewReturnHTTPTests(QuestionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(["review_queue_read", "review_return"])
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
            self.assertEqual(initial["contract"],"oi.synthetic-question-review-return-queue/1")
            self.assertEqual(len(initial["items"]),1)
            self.assertEqual(initial["receipts"],[])
            row=initial["items"][0]
            self.assertEqual(row["question_id"],qid)
            self.assertEqual(row["source_id"],source)
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
                self.assertEqual(len(events),before+1)
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
                        "source_snapshot_sha256,actor,purpose,action,reason) "
                        "SELECT 'REVIEW-'||repeat('F',32),question_id,patient_id,"
                        "case_id,'ORG-OTHER','FALSE-ORG-KEY',repeat('f',64),"
                        "repeat('f',64),source_snapshot_sha256,actor,purpose,"
                        "'returned','Independent fictional verification is needed' "
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


    def test_midflight_review_queue_revoke_clears_reply_after_source_projection(self):
        from oi_api.question_review_returns import PostgresQuestionReviewReturns
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            original=PostgresQuestionReviewReturns._read_locked
            observed=[]
            def revoked(subject,*args,**kwargs):
                result=original(subject,*args,**kwargs)
                observed.append(len(result[0]))
                self.creds[0]["actions"].remove("review_queue_read")
                self.write()
                return result
            with patch.object(PostgresQuestionReviewReturns,"_read_locked",revoked):
                status,body,_=self.inbox(base,patient)
            self.assertEqual(observed,[1])
            self.assertEqual(status,404)
            self.assertNotIn(qid,str(body))
            self.creds[0]["actions"].append("review_queue_read")
            self.write()
            self.assertEqual(self.inbox(base,patient)[0],200)

    def test_midflight_review_return_revoke_refuses_receipt_and_event(self):
        from oi_api.question_review_returns import PostgresQuestionReviewReturns
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            original=PostgresQuestionReviewReturns._read_locked
            def revoked(subject,*args,**kwargs):
                result=original(subject,*args,**kwargs)
                self.creds[0]["actions"].remove("review_return")
                self.write()
                return result
            with patch.object(PostgresQuestionReviewReturns,"_read_locked",revoked):
                status,body,_=self.returning(base,patient,qid,fp)
            self.assertEqual(status,404)
            self.assertNotIn(qid,str(body))
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.question_review_receipts"
                )).scalar_one(),0)
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='investigation.review.returned_for_verification'"
                )).scalar_one(),0)
            self.creds[0]["actions"].append("review_return")
            self.write()
            self.assertEqual(self.returning(base,patient,qid,fp)[0],201)

    def test_midflight_review_return_revoke_after_event_rolls_back(self):
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            original=PostgresPatientRegistry.append_event
            def changed_after_event(subject,pid,kind,**details):
                result=original(subject,pid,kind,**details)
                if kind=="investigation.review.returned_for_verification":
                    self.creds[0]["actions"].remove("review_return")
                    self.write()
                return result
            with patch.object(PostgresPatientRegistry,"append_event",changed_after_event):
                status,body,_=self.returning(base,patient,qid,fp,
                    request_key="RETURN-AFTER-EVENT")
            self.assertEqual(status,404)
            self.assertNotIn(qid,str(body))
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.question_review_receipts"
                )).scalar_one(),0)
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='investigation.review.returned_for_verification'"
                )).scalar_one(),0)
            self.creds[0]["actions"].append("review_return")
            self.write()
            self.assertEqual(self.returning(base,patient,qid,fp,
                request_key="RETURN-AFTER-EVENT")[0],201)

    def test_midflight_review_return_duplicate_actor_swap_denied(self):
        from oi_api.question_review_returns import PostgresQuestionReviewReturns
        with running_server(create_app(self.settings)) as base:
            patient=self.setup_case(base)
            qid,_=self.prepared_question(base,patient)
            fp=self.inbox(base,patient)[1]["items"][0]["queue_fingerprint"]
            receipt=self.returning(base,patient,qid,fp)[1]["receipt_id"]
            original=PostgresQuestionReviewReturns._read_locked
            def changed_actor(subject,*args,**kwargs):
                result=original(subject,*args,**kwargs)
                self.creds[0]["actor"]="ACTOR-SWAPPED"
                self.write()
                return result
            with patch.object(PostgresQuestionReviewReturns,"_read_locked",changed_actor):
                status,body,_=self.returning(base,patient,qid,fp)
            self.assertEqual(status,404)
            self.assertNotIn(receipt,str(body))
            self.creds[0]["actor"]="ACTOR-ALPHA"
            self.write()
            self.assertEqual(self.returning(base,patient,qid,fp)[1]["receipt_id"],receipt)


if __name__=="__main__":
    unittest.main()
