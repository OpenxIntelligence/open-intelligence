"""Source-rights and patient-context tests against the actual CaseStore ledger.

No external guideline text or real patient data appears in test fixtures.
"""
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.knowledge_context import (
    KnowledgeContextError, compile_context,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "synthetic"


def source(family="nccn", *, approved=False, with_text=False):
    permissions = {}
    if approved:
        permissions = {
            "metadata": {
                "store": "allowed", "display": "allowed", "ml_use": "allowed",
            },
            "full_text": {
                "store": "allowed", "display": "allowed", "ml_use": "allowed",
            },
        }
    item = {
        "id": "KNOWLEDGE-001",
        "family": family,
        "public_identifier": "SYNTHETIC-EVIDENCE-001",
        "version": "V1",
        "source_date": "2026-09-18",
        "rights_state": "approved" if approved else "hold",
        "permission_receipt": "TEST-RECEIPT-NOT-LEGAL-CLEARANCE" if approved else None,
        "permissions": permissions,
        "content_state": "current",
    }
    if approved:
        item["title"] = "Independently authored fictional study"
    if with_text:
        item["evidence_text"] = (
            "Independently authored synthetic evidence statement for "
            "software validation, not a genuine clinical publication."
        )
    return item


class KnowledgeContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CaseStore(Path(self.temp.name) / "case.sqlite")
        self.addCleanup(self.store.close)
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.first = self.store.import_report(
            "CASE-ALPHA", (EXAMPLES / "alpha-pathology-original.txt").read_bytes()
        )
        self.store.import_report(
            "CASE-BETA", (EXAMPLES / "beta-pathology.txt").read_bytes()
        )

    def packet(self, sources=None, links=None, case="CASE-ALPHA", state=None):
        return compile_context(
            case,
            self.store.state(case) if state is None else state,
            sources if sources is not None else [],
            links,
        )

    def test_actual_case_ledger_sources_and_observations_preserved(self):
        packet = self.packet([source()])
        self.assertEqual(packet["case_id"], "CASE-ALPHA")
        self.assertEqual(packet["clinical_review_state"], "not_clinically_reviewed")
        self.assertEqual(packet["model_use_state"], "not_authorized_by_this_packet")
        self.assertEqual(packet["knowledge_sources"][0]["evidence_text"], None)
        self.assertTrue(packet["knowledge_sources"][0]["content_withheld"])
        self.assertEqual(len(packet["missing_evidence"]), 1)
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(len(packet["patient_assertions"]), len(state["assertions"]))
        for value in packet["patient_assertions"]:
            self.assertEqual(value["source_version_id"], self.first["source_id"])
            self.assertEqual(len(value["source_hash"]), 64)
            self.assertEqual(value["epistemic_kind"], "reported_observation")

    def test_no_implicit_nccn_guideline_or_ai_rights(self):
        unlicensed = source(with_text=True)
        with self.assertRaisesRegex(KnowledgeContextError, "AI rights"):
            self.packet([unlicensed])
        with self.assertRaisesRegex(KnowledgeContextError, "metadata rights"):
            self.packet([{**source(), "title": "NCCN Guidelines"}])
        self.assertFalse(self.packet([source()])["knowledge_sources"][0]["model_text_available"])
        # A claimed human receipt with no explicit full_text/ml_use does not suffice.
        wrong_scope = source(approved=True, with_text=True)
        wrong_scope["permissions"]["full_text"]["ml_use"] = "unknown"
        with self.assertRaisesRegex(KnowledgeContextError, "AI rights"):
            self.packet([wrong_scope])

    def test_metadata_access_alone_is_not_publication_appraisal(self):
        source_meta = source(approved=True)
        source_meta["permissions"]["full_text"]["ml_use"] = "unknown"
        packet = self.packet([source_meta])
        self.assertEqual(packet["knowledge_sources"][0]["title"],
                         "Independently authored fictional study")
        self.assertIsNone(packet["knowledge_sources"][0]["evidence_text"])
        self.assertEqual(packet["comparison_proposals"], [])

    def test_licensed_fictional_comparison_stays_unreviewed(self):
        assert_id = self.store.state("CASE-ALPHA")["assertions"][0]["id"]
        relation = {
            "assertion_id": assert_id,
            "knowledge_id": "KNOWLEDGE-001",
            "relation": "contradicts",
            "applicability": "limited",
            "reviewer_note": "Fictional teaching comparison, not real science",
            "proposed_by": "SYNTHETIC-REVIEWER",
        }
        result = self.packet([source("other", approved=True, with_text=True)], [relation])
        self.assertEqual(result["comparison_proposals"][0]["relation"], "contradicts")
        self.assertEqual(
            result["comparison_proposals"][0]["review_state"], "unreviewed_proposal"
        )
        self.assertIn("synthetic", result["knowledge_sources"][0]["evidence_text"])

    def test_revocation_and_supersession_withhold_content(self):
        for field, value in (("rights_state", "revoked"),
                             ("content_state", "superseded"),
                             ("content_state", "withdrawn")):
            entry = source("other", approved=True)
            entry[field] = value
            packet = self.packet([entry])
            self.assertIsNone(packet["knowledge_sources"][0]["title"])
            self.assertTrue(packet["knowledge_sources"][0]["content_withheld"])
            with self.assertRaisesRegex(KnowledgeContextError, "AI rights"):
                entry["evidence_text"] = "This text was revoked or superseded"
                self.packet([entry])

    def test_amended_patient_source_changes_source_and_version(self):
        before = self.packet()
        self.store.import_report(
            "CASE-ALPHA", (EXAMPLES / "alpha-pathology-amended.txt").read_bytes()
        )
        after = self.packet()
        self.assertNotEqual(
            {x["source_version_id"] for x in before["patient_assertions"]},
            {x["source_version_id"] for x in after["patient_assertions"]},
        )
        with self.assertRaisesRegex(KnowledgeContextError, "stale patient assertion"):
            self.packet(
                [source("other", approved=True, with_text=True)],
                [{
                    "assertion_id": before["patient_assertions"][0]["id"],
                    "knowledge_id": "KNOWLEDGE-001",
                    "relation": "context",
                    "applicability": "unknown",
                    "reviewer_note": "Stale source must not be reused",
                    "proposed_by": "SYNTHETIC-REVIEWER",
                }],
            )

    def test_wrong_case_and_wrong_external_reference_fail_closed(self):
        with self.assertRaisesRegex(KnowledgeContextError, "cross-patient"):
            self.packet(case="CASE-ALPHA", state=self.store.state("CASE-BETA"))
        with self.assertRaisesRegex(KnowledgeContextError, "duplicated knowledge"):
            self.packet([source(), source()])
        with self.assertRaisesRegex(KnowledgeContextError, "knowledge source missing"):
            self.packet([{"id": "INVALID"}])

    def test_no_inferred_support_from_identifiers_alone(self):
        for family in ("nccn", "asco", "esmo", "pubmed", "pmc", "civic", "nci_pdq"):
            with self.subTest(family=family):
                packet = self.packet([source(family)])
                self.assertEqual(packet["comparison_proposals"], [])
                self.assertEqual(packet["missing_evidence"][0]["knowledge_id"], "KNOWLEDGE-001")


if __name__ == "__main__":
    unittest.main()
