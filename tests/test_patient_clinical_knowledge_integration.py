"""Real first-party synthetic patient → clinical/LIS → Composer → knowledge tests.

No external publication, API, live medical record, clinical authorization or AI.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from open_intelligence.clinical_composer_context import AuthorizedClinicalComposer
from open_intelligence.clinical_knowledge_context import AuthorizedClinicalKnowledge
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.patient_registry import PatientRegistryDenied

from test_clinical_continuity import (
    ClinicalContinuityIntegrationTests, ACTOR, CASE,
)


def study(*, licensed=True, text=True):
    all_perms = {
        "metadata": {"store": "allowed", "display": "allowed"},
        "full_text": {"store": "allowed", "display": "allowed",
                      "ml_use": "allowed" if licensed else "unknown"},
    }
    rights = {
        "id": "KNOW-SYN-001",
        "family": "other",
        "public_identifier": "SYNTHETIC-PUBLICATION-NOT-REAL",
        "version": "VERSION-SYNTHETIC-001",
        "source_date": "2026-01-01",
        "rights_state": "approved" if licensed else "hold",
        "content_state": "current",
        "permission_receipt": "FICTIONAL-RECEIPT-001" if licensed else None,
        "permissions": all_perms if licensed else {},
    }
    if licensed:
        rights["title"] = "Fictional research methods statement"
    if text:
        rights["evidence_text"] = (
            "Independently authored fictional study claims no therapeutic outcomes."
        )
    return rights


class AuthorizedPatientEvidenceIntegrationTests(unittest.TestCase):
    setUp = ClinicalContinuityIntegrationTests.setUp
    actor = ClinicalContinuityIntegrationTests.actor
    workflow = ClinicalContinuityIntegrationTests.workflow
    _source = ClinicalContinuityIntegrationTests._source

    def prepare(self, entries=None, proposals=None):
        self.workflow()
        question = self.store.add_question(CASE, "What contradicts the fictional laboratory observation?")
        items = [study()] if entries is None else entries
        links = [] if proposals is None else proposals
        def provider(pid, cid, qid, actor, purpose):
            return {"sources": copy.deepcopy(items),
                    "proposals": copy.deepcopy(links)}
        composed = AuthorizedClinicalComposer(self.view, self.store)
        bridge = AuthorizedClinicalKnowledge(composed, self.store, provider)
        return bridge, question, items, links

    def test_end_to_end_scoped_patient_source_evidence_and_pending_review(self):
        bridge, question, entries, links = self.prepare()
        assertion = self.store.state(CASE)["assertions"][0]["id"]
        links.append({
            "assertion_id": assertion, "knowledge_id": "KNOW-SYN-001",
            "relation": "contradicts", "applicability": "limited",
            "reviewer_note": "Fictional comparison not medical evidence",
            "proposed_by": "TEST-REVIEWER",
        })
        before = len(self.store.state(CASE)["events"])
        result = bridge.snapshot(
            self.patient_id, CASE, question, **self.actor())
        self.assertEqual(result["contract"], "oi.synthetic-authorized-patient-evidence/1")
        self.assertEqual(result["patient_id"], self.patient_id)
        self.assertEqual(result["question_id"], question)
        self.assertEqual(result["clinical_composer"]["clinical"]["patient_id"], self.patient_id)
        self.assertEqual(result["knowledge"]["case_id"], CASE)
        self.assertEqual(result["knowledge"]["comparison_proposals"][0]["relation"], "contradicts")
        self.assertEqual(result["knowledge"]["comparison_proposals"][0]["review_state"], "unreviewed_proposal")
        self.assertEqual(result["review_state"], "pending_human_evidence_review")
        self.assertFalse(result["model_execution_authorized"])
        self.assertFalse(result["clinical_conclusion_established"])
        self.assertEqual(result["rights_clearance"], "external_receipts_unverified_fixture_only")
        self.assertEqual(len(self.store.state(CASE)["events"]), before)
        self.assertNotIn("Unverified fictional clinical note text", str(result))
        self.assertNotIn("real_patient_authenticated", str(result))

    def test_unlicensed_content_and_metadata_only_do_not_enter_ai_context(self):
        bridge, question, entries, _ = self.prepare()
        entries[:] = [study(licensed=False)]
        with self.assertRaisesRegex(KnowledgeContextError, "AI rights"):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        # Even a metadata-readable source cannot supply text to AI if ML rights
        # are not explicitly granted.
        metad = study()
        metad["permissions"]["full_text"]["ml_use"] = "unknown"
        metad.pop("evidence_text")
        entries[:] = [metad]
        result = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertIsNone(result["knowledge"]["knowledge_sources"][0]["evidence_text"])
        self.assertEqual(result["knowledge"]["comparison_proposals"], [])
        self.assertFalse(result["model_execution_authorized"])

    def test_wrong_patient_case_actor_and_purpose_are_not_disclosed(self):
        bridge, question, _, _ = self.prepare()
        for opts in [
            {"patient_id": self.patient_id, "case_id": "CASE-CLIN-CONT-OTHER",
             "actor": ACTOR, "purpose": "care"},
            {"patient_id": self.patient_id, "case_id": CASE,
             "actor": "idp:unknown", "purpose": "care"},
            {"patient_id": self.patient_id, "case_id": CASE,
             "actor": ACTOR, "purpose": "research"},
        ]:
            with self.subTest(opts=opts), self.assertRaises((PatientRegistryDenied, ClinicalContinuityError)):
                bridge.snapshot(opts["patient_id"], opts["case_id"], question,
                                actor=opts["actor"], purpose=opts["purpose"])

    def test_source_amendment_blocks_stale_patient_assertion_proposal(self):
        bridge, question, _, links = self.prepare()
        prev = self.store.state(CASE)["assertions"][0]["id"]
        links.append({
            "assertion_id": prev, "knowledge_id": "KNOW-SYN-001",
            "relation": "supports", "applicability": "unknown",
            "reviewer_note": "Fictional stale source research",
            "proposed_by": "TEST-REVIEWER",
        })
        bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self._source("ORDER-CONT-001", "clinical", "order", "negative", amendment=1)
        with self.assertRaisesRegex(KnowledgeContextError, "stale patient assertion"):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_external_source_revocation_race_fails_closed(self):
        bridge, question, entries, _ = self.prepare()
        calls = {"count": 0}
        def revoke_between_reads(pid, case, qid, actor, purpose):
            calls["count"] += 1
            copy_source = study()
            if calls["count"] > 1:
                copy_source.pop("evidence_text")
                copy_source["rights_state"] = "revoked"
            return {"sources": [copy_source], "proposals": []}
        bridge.source_provider = revoke_between_reads
        with self.assertRaisesRegex(KnowledgeContextError, "changed"):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_patient_binding_revoked_mid_assembly_fails_closed(self):
        bridge, question, _, _ = self.prepare()
        original = bridge.source_provider
        def revoked(pid, cid, qid, actor, purpose):
            result = original(pid, cid, qid, actor, purpose)
            self.bridge.revoke_case(
                patient_id=self.patient_id, case_id=CASE,
                actor=ACTOR, purpose="care",
                reason="Fictional patient-to-case relationship withdrawn.")
            return result
        bridge.source_provider = revoked
        with self.assertRaises(PatientRegistryDenied):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_patient_source_amendment_during_provider_read_fails_closed(self):
        bridge, question, _, _ = self.prepare()
        original = bridge.source_provider
        counter = {"calls": 0}
        def changed(pid, cid, qid, actor, purpose):
            result = original(pid, cid, qid, actor, purpose)
            counter["calls"] += 1
            if counter["calls"] == 1:
                self._source("LAB-CONT-001", "laboratory", "result",
                             "indeterminate", specimen="SPEC-CONT-001",
                             amendment=1)
            return result
        bridge.source_provider = changed
        with self.assertRaisesRegex(ClinicalContinuityError, "changed|diverge|stale"):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_missing_external_provider_is_citation_only_and_never_retrieves(self):
        bridge, question, _, _ = self.prepare()
        bridge.source_provider = None
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            result = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertEqual(result["knowledge"]["knowledge_sources"], [])
        self.assertEqual(result["knowledge"]["comparison_proposals"], [])
        self.assertFalse(result["model_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
