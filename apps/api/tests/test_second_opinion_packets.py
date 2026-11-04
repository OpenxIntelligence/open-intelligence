"""Actual PostgreSQL acceptance for durable second-opinion packet preparation."""
import json
import unittest
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A,TOKEN_B,request
from test_source_versions import SourceVersionHTTPTests as SourceFixture,AMENDED
from test_source_questions import SourceQuestionHTTPTests as QuestionFixture


class SecondOpinionPacketHTTPTests(SourceFixture):
    world=QuestionFixture.world
    preflight=QuestionFixture.preflight
    prepared=QuestionFixture.prepared
    save=QuestionFixture.save

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend([
            "composer_context_read","question_create","question_read",
            "second_opinion_packet_read","second_opinion_packet_create",
        ])
        self.write()

    @staticmethod
    def path(patient,case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/second-opinion-packets"

    def question(self,base):
        patient=self.setup_case(base)
        source=self.ingest(base,patient)[1]["source_id"]
        preflight=self.prepared(base,patient,source)
        result=self.save(base,patient,preflight)
        self.assertEqual(result[0],201,result)
        return patient,source,preflight,result[1]["question_id"]

    def create_packet(self,base,patient,source,preflight,question_id,*,token=TOKEN_A,
                      case="CASE-ALPHA",key="SECOND-OPINION-PACKET-ONE",**overrides):
        body={
            "synthetic":True,"request_key":key,
            "title":"Focused fictional second-opinion discussion packet",
            "expected_source_snapshot_sha256":preflight["source_snapshot_sha256"],
            "source_ids":[source],"question_ids":[question_id],
        }
        body.update(overrides)
        return request(base,self.path(patient,case),token=token,body=body)

    def listing(self,base,patient,*,token=TOKEN_A,case="CASE-ALPHA"):
        return request(base,self.path(patient,case),token=token)

    def counts(self):
        with self.engine.connect() as db:
            return (
                db.execute(text("SELECT count(*) FROM coordination.second_opinion_packets")).scalar_one(),
                db.execute(text("SELECT count(*) FROM coordination.second_opinion_packet_sources")).scalar_one(),
                db.execute(text("SELECT count(*) FROM coordination.second_opinion_packet_questions")).scalar_one(),
                db.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                                "WHERE event_type='coordination.second_opinion_packet.created'")).scalar_one(),
            )

    def test_packet_is_durable_idempotent_and_becomes_stale_after_amendment(self):
        with running_server(create_app(self.settings)) as base:
            patient,source,preflight,qid=self.question(base)
            created=self.create_packet(base,patient,source,preflight,qid)
            self.assertEqual((created[0],created[1]["duplicate"]),(201,False))
            packet_id=created[1]["packet_id"]
            duplicate=self.create_packet(base,patient,source,preflight,qid)
            self.assertEqual((duplicate[0],duplicate[1]),(200,{"packet_id":packet_id,"duplicate":True}))
            status,body,headers=self.listing(base,patient)
            self.assertEqual(status,200)
            self.assertEqual(headers.get("Cache-Control"),"no-store")
            self.assertEqual(body["contract"],"oi.pg-second-opinion-packets/1")
            self.assertFalse(body["recipient_verification_supported"])
            self.assertFalse(body["external_dispatch_supported"])
            packet=body["packets"][0]
            self.assertEqual(packet["preparation_state"],"current_preparation")
            self.assertEqual(packet["sources"][0]["source_id"],source)
            self.assertEqual(packet["questions"][0]["question_id"],qid)
            self.assertFalse(packet["record_completeness_verified"])
            self.assertFalse(packet["recipient_verified"])
            self.assertFalse(packet["external_request_sent"])
            self.assertFalse(packet["clinical_approval"])
            self.assertEqual(self.counts(),(1,1,1,1))
            self.assertEqual(self.ingest(base,patient,AMENDED)[0],201)
            stale=self.listing(base,patient)[1]["packets"][0]
            self.assertEqual(stale["packet_id"],packet_id)
            self.assertEqual(stale["preparation_state"],"source_reassessment_required")
            self.assertEqual(stale["sources"][0]["state"],"superseded")
            self.assertEqual(stale["questions"][0]["source_context_state"],"source_reassessment_required")
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid,key="NEW-PACKET")[0],409)
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid)[0],200)
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(self.listing(restarted,patient)[1]["packets"][0]["packet_id"],packet_id)

    def test_changed_intent_wrong_scope_and_independent_grants_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            patient,source,preflight,qid=self.question(base)
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid)[0],201)
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid,title="Different packet focus")[0],409)
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid,case="CASE-BETA",key="WRONG-CASE")[0],404)
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid,token=TOKEN_B,key="WRONG-PATIENT")[0],404)
            for action,perform in (
                ("second_opinion_packet_read",lambda:self.listing(base,patient)),
                ("second_opinion_packet_create",lambda:self.create_packet(base,patient,source,preflight,qid,key="NEW-KEY")),
                ("source_read",lambda:self.listing(base,patient)),
                ("question_read",lambda:self.listing(base,patient)),
            ):
                self.creds[0]["actions"].remove(action);self.write()
                before=self.counts()
                self.assertEqual(perform()[0],404)
                self.assertEqual(self.counts(),before)
                self.creds[0]["actions"].append(action);self.write()

    def test_invalid_selection_and_event_failure_roll_back_without_partial_packet(self):
        with running_server(create_app(self.settings)) as base:
            patient,source,preflight,qid=self.question(base)
            for bad in (
                {"source_ids":[]},
                {"question_ids":[]},
                {"source_ids":[source,source]},
                {"question_ids":[qid,qid]},
                {"title":"short"},
                {"expected_source_snapshot_sha256":"0"*64},
                {"source_ids":["SRC-"+"F"*32]},
                {"question_ids":["QUESTION-"+"F"*32]},
            ):
                before=self.counts()
                self.assertIn(self.create_packet(base,patient,source,preflight,qid,key="BAD-"+str(len(json.dumps(bad))),**bad)[0],(404,409,422))
                self.assertEqual(self.counts(),before)
            original=PostgresPatientRegistry.append_event
            def fail(registry,patient_id,event_type,**payload):
                if event_type=="coordination.second_opinion_packet.created":
                    raise RuntimeError("Injected packet event failure")
                return original(registry,patient_id,event_type,**payload)
            with patch.object(PostgresPatientRegistry,"append_event",fail):
                self.assertEqual(self.create_packet(base,patient,source,preflight,qid,key="EVENT-FAIL")[0],503)
            self.assertEqual(self.counts(),(0,0,0,0))

    def test_serialization_time_revocation_rolls_back_create_and_hides_list(self):
        from oi_api import second_opinion_routes
        with running_server(create_app(self.settings)) as base:
            patient,source,preflight,qid=self.question(base)
            render=second_opinion_routes.JSONResponse.render
            def revoke_create(response,content):
                body=render(response,content)
                if isinstance(content,dict) and "packet_id" in content:
                    self.creds[0]["actions"].remove("second_opinion_packet_create");self.write()
                return body
            with patch.object(second_opinion_routes.JSONResponse,"render",revoke_create):
                status,body,_=self.create_packet(base,patient,source,preflight,qid)
            self.assertEqual(status,404)
            self.assertNotIn("SECONDOP-",json.dumps(body))
            self.assertEqual(self.counts(),(0,0,0,0))
            self.creds[0]["actions"].append("second_opinion_packet_create");self.write()
            self.assertEqual(self.create_packet(base,patient,source,preflight,qid)[0],201)

            def revoke_read(response,content):
                body=render(response,content)
                if isinstance(content,dict) and "packets" in content:
                    self.creds[0]["actions"].remove("second_opinion_packet_read");self.write()
                return body
            with patch.object(second_opinion_routes.JSONResponse,"render",revoke_read):
                status,body,_=self.listing(base,patient)
            self.assertEqual(status,404)
            self.assertNotIn("Focused fictional",json.dumps(body))


if __name__=="__main__":
    unittest.main()
