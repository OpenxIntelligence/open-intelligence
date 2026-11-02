"""Evidence packet → existing append-only review receipts, fictional data only.

These are actual PatientRegistry, EHR, LIS, source, rights, Composer, source
quote, and review queue domain objects. No verified real clinician or consent.
"""
import unittest
from unittest.mock import patch
from open_intelligence.store import CaseStore

from open_intelligence.authorized_evidence_review import AuthorizedEvidenceReviewHandoff
from open_intelligence.evidence_review_packet import EvidenceReviewPacket
from open_intelligence.knowledge_context import KnowledgeContextError
from test_patient_clinical_knowledge_integration import (
    AuthorizedPatientEvidenceIntegrationTests as Fixture, CASE,
)

EVIDENCE_KEY = "EVID-QUOTED"
STATEMENT = "Independently authored fictional study claims no therapeutic outcomes."
ORIGINAL = (f"OI-SYNTHETIC-EVIDENCE/1\n"
            f"Evidence: {EVIDENCE_KEY}\n"
            f"Title: Fictional research methods statement\n"
            f"Issued-At: 2026-01-01\n"
            f"Rights: original-synthetic\n"
            f"Statement: {STATEMENT}\n").encode()
AMENDED = (f"OI-SYNTHETIC-EVIDENCE/1\n"
           f"Evidence: {EVIDENCE_KEY}\n"
           f"Title: Fictional research methods corrected\n"
           f"Issued-At: 2026-01-02\n"
           f"Rights: original-synthetic\n"
           f"Amends: {EVIDENCE_KEY}@1\n"
           f"Statement: Corrected fictional evidence describes additional uncertainty.\n").encode()


class ReviewHandoffTests(unittest.TestCase):
    setUp = Fixture.setUp
    actor = Fixture.actor
    workflow = Fixture.workflow
    _source = Fixture._source
    prepare = Fixture.prepare

    def candidate(self):
        bridge, question, sources, proposals = self.prepare()
        evidence = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        assertion = self.store.state(CASE)["assertions"][0]["id"]
        aid = self.store.assess_synthetic_evidence(
            CASE, question, evidence, "context", "limited",
            "An independently authored fictional comparison awaiting human appraisal.")
        sources[0]["id"] = EVIDENCE_KEY
        sources[0]["version"] = "v1"
        sources[0]["evidence_text"] = STATEMENT
        proposals.append({
            "assertion_id": assertion,
            "knowledge_id": EVIDENCE_KEY,
            "relation": "context",
            "applicability": "limited",
            "reviewer_note": "Fictional comparison, no clinical inference established",
            "proposed_by": "TEST-REVIEWER",
        })
        selected = [{
            "assertion_id": assertion, "knowledge_id": EVIDENCE_KEY,
            "quote": "claims no therapeutic outcomes"
        }]
        return AuthorizedEvidenceReviewHandoff(
            EvidenceReviewPacket(bridge),
            return_authorizer=lambda actor, patient, action, purpose: (
                actor == self.actor()["actor"] and patient == self.patient_id
                and action == "evidence.review_return" and purpose == "care"
            )), question, aid, sources, selected

    def snapshot(self, handoff, question, aid, selected):
        return handoff.preview(
            self.patient_id, CASE, question, aid,
            selected_quotes=selected, **self.actor())

    def test_exact_versioned_quote_has_existing_queue_item_and_can_be_returned(self):
        handoff, q, aid, _, quotes = self.candidate()
        before = self.store.review_queue(CASE)
        packet = self.snapshot(handoff, q, aid, quotes)
        self.assertEqual(packet["contract"], "oi.synthetic-authorized-evidence-review-queue/1")
        self.assertEqual(packet["queue_key"], f"evidence-assessment:{aid}")
        self.assertEqual(packet["queue_status"], "awaiting_review")
        self.assertEqual(packet["review_action_allowed"], "returned_only")
        self.assertFalse(packet["clinician_signoff_authorized"])
        self.assertEqual(len(before["receipts"]), 0)
        outcome = handoff.return_for_review(
            self.patient_id, CASE, q, aid, selected_quotes=quotes,
            reason="Review required because fictional study evidence has not been appraised.",
            **self.actor())
        self.assertEqual(outcome["result"], "returned_for_independent_review")
        self.assertFalse(outcome["clinical_signoff"])
        current = self.store.review_queue(CASE)
        item = next(x for x in current["awaiting"]
                    if x["queue_key"] == f"evidence-assessment:{aid}")
        self.assertEqual(item["status"], "returned")
        self.assertEqual(item["receipts"][-1]["id"], outcome["receipt_id"])
        self.assertEqual(item["receipts"][-1]["action"], "returned")
        self.assertEqual(item["receipts"][-1]["reviewer_label"], self.actor()["actor"])
        self.assertFalse(any(x["queue_key"] == item["queue_key"] for x in current["resolved"]))
        self.assertEqual(len(current["receipts"]), 1)

    def test_review_receipt_and_event_rollback_together(self):
        handoff, q, aid, _, quotes = self.candidate()
        with patch.object(self.store, "_event", side_effect=RuntimeError("audit failure")):
            with self.assertRaisesRegex(RuntimeError, "audit failure"):
                handoff.return_for_review(
                    self.patient_id, CASE, q, aid, selected_quotes=quotes,
                    reason="Independent fictional evidence reviewer must examine the source.",
                    **self.actor())
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])
        # One later success; the earlier event failure cannot leave a receipt.
        result = handoff.return_for_review(
            self.patient_id, CASE, q, aid, selected_quotes=quotes,
            reason="Independent fictional evidence reviewer must examine the source.",
            **self.actor())
        self.assertEqual(result["result"], "returned_for_independent_review")
        self.assertEqual(len(self.store.review_queue(CASE)["receipts"]), 1)

    def test_return_receipt_persists_after_new_database_connection(self):
        handoff, q, aid, _, quotes = self.candidate()
        result = handoff.return_for_review(
            self.patient_id, CASE, q, aid, selected_quotes=quotes,
            reason="An independent fictional reviewer must evaluate relevance and uncertainty.",
            **self.actor())
        another = CaseStore(self.store.path)
        try:
            item = next(x for x in another.review_queue(CASE)["awaiting"]
                        if x["queue_key"] == f"evidence-assessment:{aid}")
            self.assertEqual(item["status"], "returned")
            self.assertEqual(item["receipts"][-1]["id"], result["receipt_id"])
        finally:
            another.close()

    def test_read_permission_does_not_authorize_review_write(self):
        handoff, q, aid, _, quotes = self.candidate()
        # Readable sources alone cannot grant permission to append a receipt.
        handoff.return_authorizer = None
        self.assertEqual(self.snapshot(handoff, q, aid, quotes)["queue_status"],
                         "awaiting_review")
        with self.assertRaises(PermissionError):
            handoff.return_for_review(
                self.patient_id, CASE, q, aid, selected_quotes=quotes,
                reason="Fictional study has not received independent appraisal.",
                **self.actor())
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_review_write_grant_revoked_mid_preflight_is_refused(self):
        handoff, q, aid, _, quotes = self.candidate()
        counter = {"calls": 0}
        def check(actor, patient, action, purpose):
            counter["calls"] += 1
            return counter["calls"] == 1
        handoff.return_authorizer = check
        with self.assertRaises(PermissionError):
            handoff.return_for_review(
                self.patient_id, CASE, q, aid, selected_quotes=quotes,
                reason="Fictional study has not received independent appraisal.",
                **self.actor())
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_rights_revocation_fails_without_new_receipt(self):
        handoff, q, aid, sources, quotes = self.candidate()
        sources[0]["rights_state"] = "revoked"
        with self.assertRaises(KnowledgeContextError):
            self.snapshot(handoff, q, aid, quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_missing_or_mismatched_local_source_denied(self):
        handoff, q, aid, sources, quotes = self.candidate()
        for field, value in [
            ("version", "v2"), ("id", "EVID-DIFFERENT"),
            ("source_date", "2026-01-03"), ("evidence_text", "Invented different text."),
        ]:
            old = sources[0][field]
            sources[0][field] = value
            with self.subTest(field=field), self.assertRaises(KnowledgeContextError):
                self.snapshot(handoff, q, aid, quotes)
            sources[0][field] = old
        with self.assertRaises(KnowledgeContextError):
            self.snapshot(handoff, q, 99999, quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_amended_original_evidence_reopens_stored_queue_fingerprint(self):
        handoff, q, aid, _, quotes = self.candidate()
        handoff.return_for_review(
            self.patient_id, CASE, q, aid, selected_quotes=quotes,
            reason="Fictional supporting material requires another evidence assessment.",
            **self.actor())
        before = next(x for x in self.store.review_queue(CASE)["awaiting"]
                      if x["queue_key"] == f"evidence-assessment:{aid}")
        self.store.import_synthetic_evidence(AMENDED)
        after = next(x for x in self.store.review_queue(CASE)["awaiting"]
                     if x["queue_key"] == f"evidence-assessment:{aid}")
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])
        self.assertEqual(after["status"], "awaiting_review")
        self.assertEqual(len(after["prior_receipts"]), 1)
        with self.assertRaises(KnowledgeContextError):
            self.snapshot(handoff, q, aid, quotes)

    def test_patient_source_amendment_denies_old_quote_approval(self):
        handoff, q, aid, _, quotes = self.candidate()
        self._source("ORDER-CONT-001", "clinical", "order", "negative", amendment=1)
        with self.assertRaises(KnowledgeContextError):
            self.snapshot(handoff, q, aid, quotes)
        self.assertEqual(len(self.store.review_queue(CASE)["receipts"]), 0)

    def test_invalid_actor_and_cross_case_refuse_review(self):
        handoff, q, aid, _, quotes = self.candidate()
        with self.assertRaises(PermissionError):
            handoff.return_for_review(self.patient_id, CASE, q, aid,
                 actor="UNTRUSTED-ACTOR", purpose="care",
                 selected_quotes=quotes, reason="Test-only denied review.")
        with self.assertRaises((PermissionError, ValueError)):
            handoff.preview(self.patient_id, "CASE-CLIN-CONT-OTHER", q, aid,
                 **self.actor(), selected_quotes=quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_existing_demo_acknowledgment_uses_same_review_receipt_owner(self):
        handoff, q, aid, sources, quotes = self.candidate()
        original_source = next(x for x in self.store.state(CASE)["sources"]
                               if x["state"] == "current")
        snapshot_id = self.store.create_snapshot(
            CASE, q, "Independently authored synthetic comparison awaiting inspection.",
            [original_source["id"]])
        self.store.acknowledge_demo_review(CASE, snapshot_id, "Demo reviewer")
        queue = self.store.review_queue(CASE)
        matching = [x for x in queue["resolved"]
                    if x["queue_key"] == f"snapshot:{snapshot_id}"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["resolved_by"]["action"], "acknowledged")
        self.assertEqual(matching[0]["resolved_by"]["fingerprint"], "reviewed_in_demo")
        self.assertFalse(any(x["queue_key"] == f"snapshot:{snapshot_id}"
                             for x in queue["awaiting"]))
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM review_receipts WHERE case_id=? AND queue_key=?",
            (CASE, f"snapshot:{snapshot_id}")).fetchone()[0], 1)



if __name__ == "__main__":
    unittest.main()
