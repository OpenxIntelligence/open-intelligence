"""Integrated canonical patient/EHR/LIS + Composer v2 broker + durable review.

Exercises the actual original first-party stores and rights broker with only
independently authored fictional inputs. No live model, network or clinical use.
"""
import unittest
from unittest.mock import patch

from open_intelligence.composer import CONTEXT_VERSION
from open_intelligence.investigation import validate_output
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.store import InvalidInput

from test_composer_broker_context import link, payload
from test_patient_research_run_review import (
    PatientResearchRunReviewIntegration, CASE, numeric,
)


class CanonicalPatientBrokerV2Integration(unittest.TestCase):
    setUp = PatientResearchRunReviewIntegration.setUp
    actor = PatientResearchRunReviewIntegration.actor
    workflow = PatientResearchRunReviewIntegration.workflow
    _source = PatientResearchRunReviewIntegration._source
    prepare = PatientResearchRunReviewIntegration.prepare
    read = PatientResearchRunReviewIntegration.read

    def broker(self):
        return link(
            self.store, self.question, case=CASE, key="EVIDENCE-V2-ONE",
            excerpt="Independently authored fictional research offers counterevidence.",
            citation_title="Fictional methods comparison.")

    def hypothesis(self, lid):
        facts = self.store.investigation_facts(CASE, self.question)
        valid = validate_output(
            payload(lid), facts["valid_sources"], facts["valid_assessments"],
            facts["valid_brokers"])
        self.assertEqual(len(valid.claims), 1)
        iid = self.store.save_investigation(
            CASE, self.question, "evidence-summary", valid, "replay",
            context_fingerprint=facts["context_fingerprint"],
            input_receipts=facts["input_receipts"])
        return iid

    def new_numeric_run(self):
        ctx = self.knowledge.snapshot(
            self.patient_id, CASE, self.question, **self.actor())
        fingerprint = ctx["clinical_composer"]["composer"]["fingerprint"]
        queued = self.runs.queue(
            CASE,self.question,fingerprint,"hemoglobin","RIGHTS-V2-RUN-02")
        finished = self.runs.execute(CASE,queued["run_id"])
        self.assertEqual(finished["state"],"completed")
        return finished

    def model_read(self, iid, **params):
        return self.review.investigation_snapshot(
            params.get("patient_id",self.patient_id),
            params.get("case_id",CASE),
            params.get("question_id",self.question),iid,
            actor=params.get("actor",self.actor()["actor"]),
            purpose=params.get("purpose","care"))

    def test_broker_research_and_durable_numeric_are_one_authorized_context(self):
        self.prepare()
        self.assertEqual(CONTEXT_VERSION,"composer-context-v2")
        original = self.completed
        rid,lid=self.broker()
        self.assertEqual(self.runs.get(CASE,original["run_id"])["state"],"stale")
        current=self.new_numeric_run()
        iid=self.hypothesis(lid)
        packet=self.model_read(iid)
        self.assertEqual(packet["review_status"],"unreviewed_source_bound_investigation")
        self.assertEqual(packet["investigation"]["claims"][0]["citations"],
                         [{"type":"broker","id":lid}])
        self.assertEqual(packet["investigation"]["input_receipts"][0]["broker_link_id"],lid)
        self.assertEqual(packet["investigation"]["input_context"]["context_fingerprint"],
                         current["context_fingerprint"])
        self.assertEqual(self.read(run_id=current["run_id"])["review_status"],
                         "current_numeric_receipt_pending_human_review")
        self.assertFalse(packet["model_execution_authorized"])
        self.assertEqual(packet["clinical_approval"],"not_performed")
        self.assertEqual(next(row["state"] for row in self.store.state(CASE)["questions"]
                              if row["id"]==self.question),"open",
                         "Unreviewed AI output must not close the patient's question")

    def test_rights_revocation_withholds_hypothesis_and_stales_numeric_receipt(self):
        self.prepare()
        rid,lid=self.broker()
        numeric_run=self.new_numeric_run()
        iid=self.hypothesis(lid)
        prior=self.model_read(iid)
        self.assertTrue(prior["investigation"]["claims"])
        self.store.revoke_rights_source(rid,"Fictional external input permission withdrawn.")
        current=self.model_read(iid)
        self.assertEqual(current["review_status"],"historical_investigation_reassessment_required")
        self.assertEqual(current["investigation"]["claims"],[])
        self.assertEqual(current["investigation"]["abstentions"],[])
        self.assertTrue(current["investigation"]["output_withheld"])
        self.assertNotIn("Fictional broker material is inconclusive",str(current))
        old=self.read(run_id=numeric_run["run_id"])
        self.assertEqual(old["review_status"],"historical_numeric_receipt_reassessment_required")
        self.assertEqual(old["durable_run"]["result"]["result"]["delta"],"-0.4")
        self.assertEqual(next(row["state"] for row in self.store.state(CASE)["questions"]
                              if row["id"]==self.question),"open")

    def test_new_patient_source_amendment_stales_model_but_keeps_source_history(self):
        self.prepare()
        _,lid=self.broker()
        run=self.new_numeric_run()
        iid=self.hypothesis(lid)
        self.store.import_report(CASE,numeric(
            "NUM-LAB-2","2026-03-01","7.2",amendment=1))
        out=self.model_read(iid)
        self.assertEqual(out["review_status"],"historical_investigation_reassessment_required")
        self.assertFalse(out["investigation"]["claims"])
        self.assertTrue(out["investigation"]["stale"])
        old=self.read(run_id=run["run_id"])
        self.assertEqual(old["review_status"],"historical_numeric_receipt_reassessment_required")
        self.assertIn("value=9.8",self.store.source_text(CASE,self.second))
        self.assertEqual(self.store.state("CASE-CLIN-CONT-OTHER")["investigations"],[])

    def test_denied_actor_purpose_and_revoked_case_block_history(self):
        self.prepare()
        _,lid=self.broker()
        iid=self.hypothesis(lid)
        for kwargs in ({"actor":"idp:untrusted"},{"purpose":"research"},
                       {"case_id":"CASE-CLIN-CONT-OTHER"}):
            with self.subTest(kwargs=kwargs),self.assertRaises(
                    (PatientRegistryDenied,ClinicalContinuityError,InvalidInput)):
                self.model_read(iid,**kwargs)
        self.bridge.revoke_case(
            patient_id=self.patient_id,case_id=CASE,
            actor=self.actor()["actor"],purpose="care",
            reason="Fictional patient binding revoked after investigation.")
        with self.assertRaises(PatientRegistryDenied):
            self.model_read(iid)

    def test_revoke_mid_read_cannot_release_cached_hypothesis(self):
        self.prepare()
        rid,lid=self.broker()
        iid=self.hypothesis(lid)
        origin=self.runs.store.get_investigation
        count={"n":0}
        def changed(case,inv):
            result=origin(case,inv)
            count["n"]+=1
            if count["n"]==1:
                self.store.revoke_rights_source(
                    rid,"Fictional source revoked during assembled review.")
            return result
        with patch.object(self.runs.store,"get_investigation",side_effect=changed):
            with self.assertRaises(ClinicalContinuityError):
                self.model_read(iid)

if __name__=="__main__":
    unittest.main()
