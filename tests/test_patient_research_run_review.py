"""Cross-owner authorized patient/EHR/LIS/knowledge/durable-run review tests.

All data and measured values are independently authored and fictional.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from open_intelligence.clinical_composer_context import AuthorizedClinicalComposer
from open_intelligence.clinical_knowledge_context import AuthorizedClinicalKnowledge
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.durable_runs import DurableComposerRuns
from open_intelligence.patient_research_review import PatientResearchReview
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.store import InvalidInput

from test_clinical_continuity import ClinicalContinuityIntegrationTests, CASE
from test_patient_clinical_knowledge_integration import study


def numeric(document: str, day: str, value: str, *, amendment=None) -> bytes:
    fields = [
        "OI-SYNTHETIC-REPORT/1",f"Patient: {CASE}",
        f"Document: {document}","Type: laboratory",
        f"Event-Date: {day}",f"Issued-At: {day}",
        "Specimen: SPEC-NUMERIC-ONLY",
    ]
    if amendment is not None:
        fields.append(f"Amends: {document}@{amendment}")
    fields.append(
        f"Finding: hemoglobin|reported|OI-LAB-VALUE/1;value={value};unit=g/dL;qc=passed")
    return ("\n".join(fields)+"\n").encode("utf-8")


class PatientResearchRunReviewIntegration(unittest.TestCase):
    setUp = ClinicalContinuityIntegrationTests.setUp
    actor = ClinicalContinuityIntegrationTests.actor
    workflow = ClinicalContinuityIntegrationTests.workflow
    _source = ClinicalContinuityIntegrationTests._source

    def prepare(self):
        self.workflow()
        self.first = self.store.import_report(
            CASE,numeric("NUM-LAB-1","2026-02-01","10.2"))["source_id"]
        self.second = self.store.import_report(
            CASE,numeric("NUM-LAB-2","2026-03-01","9.8"))["source_id"]
        self.question = self.store.add_question(
            CASE,"What is the fictional numeric difference between these laboratory sources?")
        self.sources = [study()]
        def provider(pid,case,qid,actor,purpose):
            return {"sources":[dict(x) for x in self.sources],"proposals":[]}
        self.knowledge = AuthorizedClinicalKnowledge(
            AuthorizedClinicalComposer(self.view,self.store),self.store,provider)
        self.runs = DurableComposerRuns(self.store)
        self.review = PatientResearchReview(self.knowledge,self.runs)
        self.gated = self.knowledge.snapshot(
            self.patient_id,CASE,self.question,**self.actor())
        self.run = self.runs.queue(
            CASE,self.question,self.gated["clinical_composer"]["composer"]["fingerprint"],
            "hemoglobin","CLINICAL-NUMERIC-RUN-01")
        self.completed = self.runs.execute(CASE,self.run["run_id"])
        self.assertEqual(self.completed["state"],"completed")
        self.assertEqual(self.completed["result"]["result"]["delta"],"-0.4")

    def read(self,**kw):
        return self.review.snapshot(
            kw.get("patient_id",self.patient_id),
            kw.get("case_id",CASE),
            kw.get("question_id",self.question),
            kw.get("run_id",self.run["run_id"]),
            actor=kw.get("actor",self.actor()["actor"]),
            purpose=kw.get("purpose","care"))

    def test_current_numeric_run_and_licensed_fictional_evidence_review_handoff(self):
        self.prepare()
        before = len(self.store.state(CASE)["events"])
        packet = self.read()
        self.assertEqual(packet["review_status"],"current_numeric_receipt_pending_human_review")
        self.assertEqual(packet["patient_id"],self.patient_id)
        self.assertEqual(packet["durable_run"]["result"]["result"]["delta"],"-0.4")
        self.assertEqual({p["source_version_id"] for p in
                          packet["original_source_provenance"]},{self.first,self.second})
        self.assertEqual(packet["patient_evidence"]["knowledge"]["knowledge_sources"][0]
                         ["id"],"KNOW-SYN-001")
        self.assertFalse(packet["model_execution_authorized"])
        self.assertEqual(packet["clinical_approval"],"not_performed")
        self.assertEqual(len(self.store.state(CASE)["events"]),before)
        self.assertEqual(next(q["state"] for q in self.store.state(CASE)["questions"]
                              if q["id"]==self.question),"open")
        self.assertNotIn("Unverified fictional clinical note text",str(packet))

    def test_source_cited_handoff_report_does_not_redistribute_external_content(self):
        self.prepare()
        exported = self.review.export_markdown(
            self.patient_id,CASE,self.question,self.run["run_id"],**self.actor())
        self.assertIn("fictional numeric research handoff",exported)
        self.assertIn("NUM-LAB-1@1",exported)
        self.assertIn("NUM-LAB-2@1",exported)
        self.assertIn(self.completed["context_fingerprint"],exported)
        self.assertIn("pending_human_review",exported)
        self.assertNotIn("Fictional research methods statement",exported)
        self.assertNotIn("Independently authored fictional study",exported)
        self.assertNotIn("Unverified fictional clinical note text",exported)
        self.assertNotIn("clinical approval granted",exported)
        self.store.import_report(
            CASE,numeric("NUM-LAB-2","2026-03-01","8.1",amendment=1))
        historical = self.review.export_markdown(
            self.patient_id,CASE,self.question,self.run["run_id"],**self.actor())
        self.assertIn("historical_numeric_receipt_reassessment_required",historical)
        self.assertIn("NUM-LAB-2@1",historical)
        self.assertNotIn("value=8.1",historical)

    def test_amendment_keeps_original_result_and_flags_reassessment(self):
        self.prepare()
        previous = self.read()
        self.store.import_report(
            CASE,numeric("NUM-LAB-2","2026-03-01","8.1",amendment=1))
        after = self.read()
        self.assertEqual(after["review_status"],
                         "historical_numeric_receipt_reassessment_required")
        self.assertEqual(after["durable_run"]["state"],"stale")
        self.assertEqual(after["durable_run"]["result"]["result"]["delta"],"-0.4")
        self.assertEqual(after["original_source_provenance"][1]["source_state"],"superseded")
        self.assertNotEqual(previous["patient_evidence"]["clinical_composer"]["composer"]
                            ["fingerprint"],after["patient_evidence"]["clinical_composer"]
                            ["composer"]["fingerprint"])
        self.assertIn("value=9.8",self.store.source_text(CASE,self.second))
        self.assertEqual(next(q["state"] for q in self.store.state(CASE)["questions"]
                              if q["id"]==self.question),"open")

    def test_other_case_actor_purpose_and_question_denied(self):
        self.prepare()
        for kw in (
            {"case_id":"CASE-CLIN-CONT-OTHER"},
            {"actor":"idp:untrusted"},
            {"purpose":"research"},
        ):
            with self.subTest(kw=kw),self.assertRaises((PatientRegistryDenied,ClinicalContinuityError)):
                self.read(**kw)
        other_q = self.store.add_question(CASE,"A separate fictional question")
        with self.assertRaises(InvalidInput):
            self.read(question_id=other_q)

    def test_revoked_patient_binding_disallows_historical_run_reads(self):
        self.prepare()
        self.bridge.revoke_case(
            patient_id=self.patient_id,case_id=CASE,
            actor=self.actor()["actor"],purpose="care",
            reason="Fictional case review link withdrawn after numeric result.")
        with self.assertRaises(PatientRegistryDenied):
            self.read()

    def test_revoked_rights_remove_external_text_without_hiding_numeric_history(self):
        self.prepare()
        self.sources[0] = {**study(),"rights_state":"revoked"}
        self.sources[0].pop("title")
        self.sources[0].pop("evidence_text")
        packet = self.read()
        self.assertIsNone(packet["patient_evidence"]["knowledge"]
                          ["knowledge_sources"][0]["evidence_text"])
        self.assertEqual(packet["patient_evidence"]["knowledge"]
                         ["knowledge_sources"][0]["rights_status"],"revoked")
        self.assertEqual(packet["review_status"],"current_numeric_receipt_pending_human_review")
        self.assertFalse(packet["model_execution_authorized"])

    def test_forged_result_source_hash_fails_closed(self):
        self.prepare()
        current = self.runs.get(CASE,self.run["run_id"])
        bad = current["result"]
        bad["result"]["points"][0]["source"]["source_sha256"] = "0"*64
        with self.store.db:
            self.store.db.execute("UPDATE composer_tool_runs SET result_json=? WHERE id=?",
                                  (json.dumps(bad),self.run["run_id"]))
        with self.assertRaisesRegex(ClinicalContinuityError,"source provenance mismatch"):
            self.read()

    def test_source_mutation_during_review_fails_closed(self):
        self.prepare()
        original = self.runs.get
        called = {"n":0}
        def interleaved(case,run_id):
            result=original(case,run_id)
            called["n"]+=1
            if called["n"]==1:
                self.store.import_report(
                    CASE,numeric("NUM-LAB-2","2026-03-01","7.7",amendment=1))
            return result
        with patch.object(self.runs,"get",side_effect=interleaved):
            with self.assertRaisesRegex(ClinicalContinuityError,"changed"):
                self.read()

if __name__=="__main__":
    unittest.main()
