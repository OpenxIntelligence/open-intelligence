"""Actual PG16 source-quoted review packet acceptance: no new evidence owner.

Original bytes and source lines are validated by the existing source owner.
The quote packet is read-only, separately granted, and never a clinical review.
"""
from unittest.mock import patch
import hashlib
import json
import unittest
from sqlalchemy import text
from http_support import running_server
from oi_api.app import create_app
from oi_api.source_world_model import project_source_world_model
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_questions import SourceQuestionHTTPTests as QuestionFixture, QUESTION
from test_source_versions import AMENDED

OTHER = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-TWO\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n"
    "Specimen: SPECIMEN-ONE\n"
    "Finding: marker|reported|Another independently fictional source statement.\n"
)


class SourceQuoteReviewPacketHTTPTests(QuestionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].append("review_packet_read")
        self.write()

    @staticmethod
    def packet_path(patient,qid,case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/questions/{qid}/source-review-packet"

    def packet(self,base,patient,qid,*,case="CASE-ALPHA",token=TOKEN_A):
        return request(base,self.packet_path(patient,qid,case),token=token)

    def saved(self,base,patient,*,source=None,line=8,key="Q-ONE"):
        if source is None:
            source=self.ingest(base,patient)[1]["source_id"]
        prep=self.prepared(base,patient,source,line=line)
        code,saved,_=self.save(base,patient,prep,request_key=key)
        self.assertEqual(code,201,(code,saved))
        return saved["question_id"],source

    def test_packet_verifies_literal_original_quote_provenance_and_no_clinical_authority(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            qid,sid=self.saved(base,pid)
            status,packet,_=self.packet(base,pid,qid)
            self.assertEqual(status,200)
            self.assertEqual(packet["contract"],"oi.synthetic-question-source-review-packet/1")
            self.assertEqual((packet["patient_id"],packet["case_id"],packet["question_id"]),
                             (pid,"CASE-ALPHA",qid))
            self.assertTrue(packet["source_access_receipt_id"].startswith("ACCESS-"))
            self.assertEqual(packet["question"],QUESTION)
            self.assertTrue(packet["synthetic"])
            self.assertEqual(packet["source_context_state"],"current_unreviewed_source")
            self.assertEqual(packet["review_next_step"],"independent_source_verification_required")
            source=packet["selected_statement"]
            self.assertEqual(source["source_id"],sid)
            self.assertEqual(source["source_line"],8)
            self.assertEqual(source["document_version"],1)
            self.assertEqual(source["finding_key"],"marker")
            self.assertEqual(source["reported_state"],"not-reported")
            self.assertEqual(source["source_statement"],"Fictional café <script>literal</script>.")
            self.assertEqual(source["review_state"],"not_established")
            self.assertIsNone(source["clinical_meaning"])
            self.assertEqual(source["source_sha256"],packet["original_anchor"]["source_sha256"])
            self.assertFalse(packet["medical_interpretation_performed"])
            self.assertFalse(packet["clinical_review_connected"])
            self.assertFalse(packet["external_biomedical_evidence_qualified"])
            self.assertFalse(packet["published_evidence_rights_verified"])
            self.assertFalse(packet["reviewer_identity_verified"])
            self.assertFalse(packet["clinical_approval"])
            self.assertEqual(packet["related_statement_count_total"],0)
            fingerprint=packet.pop("packet_sha256")
            access=packet.pop("source_access_receipt_id")
            raw=json.dumps(packet,ensure_ascii=False,sort_keys=True,
                           separators=(",",":"),allow_nan=False).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),fingerprint)
            status,second,_=self.packet(base,pid,qid)
            self.assertEqual(status,200)
            self.assertNotEqual(second["source_access_receipt_id"],access)
            self.assertEqual(second["packet_sha256"],fingerprint)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM investigation.source_questions"
                )).scalar_one(),1)
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='source.read_authorized'"
                )).scalar_one()>=2,True)
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(self.packet(restarted,pid,qid)[1]["packet_sha256"],fingerprint)

    def test_amendment_keeps_historical_question_but_hides_stale_source_quote(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            qid,old=self.saved(base,pid)
            previous=self.packet(base,pid,qid)[1]
            amended=self.ingest(base,pid,AMENDED)
            self.assertEqual(amended[0],201)
            current=amended[1]["source_id"]
            status,historical,_=self.packet(base,pid,qid)
            self.assertEqual(status,200)
            self.assertEqual(historical["original_anchor"]["source_id"],old)
            self.assertEqual(historical["source_context_state"],"source_reassessment_required")
            self.assertEqual(historical["review_next_step"],"refresh_source_and_create_new_question")
            self.assertIsNone(historical["selected_statement"])
            self.assertEqual(historical["related_statements"],[])
            self.assertEqual(historical["related_statement_count_total"],0)
            self.assertNotEqual(historical["packet_sha256"],previous["packet_sha256"])
            revised=self.saved(base,pid,source=current,line=9,key="Q-AMENDED")[0]
            status,updated,_=self.packet(base,pid,revised)
            self.assertEqual(status,200)
            self.assertEqual(updated["source_context_state"],"current_unreviewed_source")
            self.assertEqual(updated["selected_statement"]["source_id"],current)
            self.assertEqual(updated["selected_statement"]["reported_state"],"negative")
            self.assertNotIn("Fictional café",str(updated["selected_statement"]))

    def test_related_same_specimen_date_quotes_never_turn_into_medical_inference(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            raw1=self.ingest(base,pid)
            raw2=self.ingest(base,pid,OTHER)
            self.assertEqual((raw1[0],raw2[0]),(201,201))
            qid,sid=self.saved(base,pid,source=raw1[1]["source_id"])
            packet=self.packet(base,pid,qid)[1]
            self.assertEqual(packet["source_context_state"],"current_unreviewed_source")
            self.assertEqual(packet["related_statement_count_total"],1)
            related=packet["related_statements"][0]
            self.assertEqual(related["source_id"],raw2[1]["source_id"])
            self.assertEqual(related["reported_state"],"reported")
            self.assertEqual(related["event_date"],packet["selected_statement"]["event_date"])
            self.assertEqual(related["specimen_id"],packet["selected_statement"]["specimen_id"])
            self.assertFalse(packet["related_statements_truncated"])
            self.assertFalse(packet["medical_interpretation_performed"])
            self.assertFalse(packet["clinical_approval"])

    def test_independent_packet_permission_and_patient_case_scope_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            qid,_=self.saved(base,pid)
            self.assertEqual(self.packet(base,pid,qid,token=TOKEN_B)[0],404)
            self.assertEqual(self.packet(base,pid,qid,case="CASE-BETA")[0],404)
            self.assertEqual(self.packet(base,pid,"QUESTION-"+"F"*32)[0],404)
            self.creds[0]["actions"].remove("review_packet_read");self.write()
            self.assertEqual(self.listing(base,pid)[0],200)
            self.assertEqual(self.packet(base,pid,qid)[0],404)
            self.creds[0]["actions"].append("review_packet_read")
            self.creds[0]["actions"].remove("question_read");self.write()
            self.assertEqual(self.packet(base,pid,qid)[0],404)
            self.creds[0]["actions"].append("question_read")
            self.creds[0]["actions"].remove("source_read");self.write()
            self.assertEqual(self.packet(base,pid,qid)[0],404)
            self.creds[0]["actions"].append("source_read")
            self.creds[0]["purpose"]="research";self.write()
            self.assertEqual(self.packet(base,pid,qid)[0],404)
            self.creds[0]["purpose"]="operations";self.write()
            self.assertEqual(self.packet(base,pid,qid)[0],200)
            self.creds[0]["patient_ids"]=[];self.write()
            self.assertEqual(self.packet(base,pid,qid)[0],404)

    def test_audit_append_failure_withholds_packet_and_rolls_back_event(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            qid,_=self.saved(base,pid)
            from open_intelligence.postgres_registry import PostgresPatientRegistry
            original=PostgresPatientRegistry.append_event
            def fail(registry,patient,event,**fields):
                if event=="source.read_authorized":
                    raise RuntimeError("Intentionally unavailable source audit")
                return original(registry,patient,event,**fields)
            with patch.object(PostgresPatientRegistry,"append_event",fail):
                result=self.packet(base,pid,qid)
            self.assertEqual(result[0],503)
            self.assertNotIn("Fictional café",str(result[1]))
            self.assertEqual(self.packet(base,pid,qid)[0],200)

    def test_revoked_case_mapping_clears_packet_without_erasing_original(self):
        with running_server(create_app(self.settings)) as base:
            pid=self.setup_case(base)
            qid,_=self.saved(base,pid)
            self.assertEqual(self.packet(base,pid,qid)[0],200)
            revoked=request(base,
                f"/v1/patients/{pid}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A,
                body={"synthetic":True,"reason":"Fictional mapping intentionally withdrawn"})
            self.assertEqual(revoked[0],200)
            self.assertEqual(self.packet(base,pid,qid)[0],404)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM investigation.source_questions"
                )).scalar_one(),1)


if __name__=="__main__":
    unittest.main()
