"""Synthetic patient → EHR/LIS → knowledge → anchored review packet integration."""
import unittest
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.evidence_review_packet import EvidenceReviewPacket
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.patient_registry import PatientRegistryDenied
from test_patient_clinical_knowledge_integration import (
    AuthorizedPatientEvidenceIntegrationTests as Fixture, study, CASE,
)

class EvidenceQuoteReviewTests(unittest.TestCase):
    setUp = Fixture.setUp
    actor = Fixture.actor
    workflow = Fixture.workflow
    _source = Fixture._source
    prepare = Fixture.prepare

    def setup_candidate(self):
        bridge, question, sources, proposals = self.prepare()
        aid = self.store.state(CASE)["assertions"][0]["id"]
        proposals.append({
            "assertion_id": aid, "knowledge_id": "KNOW-SYN-001",
            "relation": "contradicts", "applicability": "limited",
            "reviewer_note": "Fictional comparison not independently reviewed",
            "proposed_by": "TEST-REVIEWER"
        })
        return EvidenceReviewPacket(bridge), bridge, question, sources, aid

    def quotes(self, aid, text="claims no therapeutic outcomes"):
        return [{"assertion_id": aid, "knowledge_id": "KNOW-SYN-001", "quote": text}]

    def test_exact_quote_receipt_is_unreviewed_and_read_only(self):
        obj, bridge, q, sources, aid = self.setup_candidate()
        before = self.store.state(CASE)
        result = obj.preview(self.patient_id, CASE, q,
                             selected_quotes=self.quotes(aid), **self.actor())
        self.assertEqual(result["contract"], "oi.synthetic-source-quote-review/1")
        self.assertEqual(result["human_review_state"], "pending")
        self.assertFalse(result["action_authorized"])
        self.assertFalse(result["clinical_conclusion_established"])
        self.assertFalse(result["model_executed"])
        cited = result["quoted_comparisons"][0]
        self.assertEqual(cited["external_reference"]["exact_quote"],
                         "claims no therapeutic outcomes")
        self.assertEqual(cited["patient_reference"]["assertion_id"], aid)
        self.assertFalse(cited["external_reference"]["publisher_rights_independently_verified"])
        self.assertEqual(before["events"], self.store.state(CASE)["events"])

    def test_forged_and_duplicate_quote_rejected(self):
        obj, _, q, _, aid = self.setup_candidate()
        for selections in [
            self.quotes(aid, "This fake result guarantees a cure."),
            self.quotes(aid) + self.quotes(aid),
            self.quotes(aid, " " * 3),
            [{"assertion_id": True, "knowledge_id": "KNOW-SYN-001", "quote": "claims no therapeutic outcomes"}],
        ]:
            with self.subTest(selections=selections), self.assertRaises(KnowledgeContextError):
                obj.preview(self.patient_id, CASE, q, selected_quotes=selections,
                            **self.actor())

    def test_revocation_and_metadata_only_deny_quotation(self):
        obj, _, q, sources, aid = self.setup_candidate()
        sources[0]["rights_state"] = "revoked"
        with self.assertRaises(KnowledgeContextError):
            obj.preview(self.patient_id, CASE, q,
                        selected_quotes=self.quotes(aid), **self.actor())
        sources[0] = study()
        sources[0].pop("evidence_text")
        with self.assertRaises(KnowledgeContextError):
            obj.preview(self.patient_id, CASE, q,
                        selected_quotes=self.quotes(aid), **self.actor())

    def test_source_amendment_invalidates_assertion(self):
        obj, _, q, _, aid = self.setup_candidate()
        obj.preview(self.patient_id, CASE, q,
                    selected_quotes=self.quotes(aid), **self.actor())
        self._source("ORDER-CONT-001", "clinical", "order", "negative", amendment=1)
        with self.assertRaises(KnowledgeContextError):
            obj.preview(self.patient_id, CASE, q,
                        selected_quotes=self.quotes(aid), **self.actor())

    def test_mid_assembly_rights_change_fails_closed(self):
        obj, bridge, q, sources, aid = self.setup_candidate()
        original = bridge.snapshot
        n = {"calls": 0}
        def updated(*args, **kwargs):
            result = original(*args, **kwargs)
            n["calls"] += 1
            if n["calls"] == 1:
                sources[0]["evidence_text"] += " Another fictional sentence."
            return result
        bridge.snapshot = updated
        with self.assertRaises(ClinicalContinuityError):
            obj.preview(self.patient_id, CASE, q,
                        selected_quotes=self.quotes(aid), **self.actor())

    def test_wrong_patient_actor_and_purpose_refused(self):
        obj, _, q, _, aid = self.setup_candidate()
        for case,actor,purpose in [
            ("CASE-CLIN-CONT-OTHER", "idp:clinician-001", "care"),
            (CASE, "UNTRUSTED-ACTOR", "care"),
            (CASE, "idp:clinician-001", "research"),
        ]:
            with self.assertRaises((ClinicalContinuityError, PatientRegistryDenied)):
                obj.preview(self.patient_id, case, q, actor=actor, purpose=purpose,
                            selected_quotes=self.quotes(aid))

    def test_empty_sources_never_invent_findings(self):
        bridge, q, sources, links = self.prepare()
        sources[:] = []
        result = EvidenceReviewPacket(bridge).preview(
            self.patient_id, CASE, q, selected_quotes=[], **self.actor())
        self.assertEqual(result["quoted_comparisons"], [])
        self.assertEqual(result["human_review_state"], "pending")
        self.assertFalse(result["action_authorized"])


if __name__ == "__main__":
    unittest.main()
