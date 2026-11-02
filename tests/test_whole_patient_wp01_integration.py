"""WP-01 synthetic integration acceptance: real ledger -> evidence -> proposal -> review -> amendment.

This does not test the proposed native Composer, authenticated clinical review,
clinical orders, live guideline retrieval, or a production Patient World Model.
It exercises only the currently implemented source/evidence/investigation contracts.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.investigation import validate_output
from open_intelligence.mission import build_patient_mission


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "synthetic"
EVIDENCE = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: EVID-WP01
Title: Independently authored fictional research note
Issued-At: 2026-05-09
Rights: original-synthetic
Statement: This invented note only illustrates a limitation of fictional assay interpretation.
"""


class WholePatientWP01SyntheticIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "wp01.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def fixture(self, name):
        return (FIXTURES / name).read_bytes()

    def test_source_evidence_validated_proposal_review_and_selective_amendment(self):
        pathology = self.store.import_report(
            "CASE-ALPHA", self.fixture("alpha-pathology-original.txt"))
        imaging = self.store.import_report(
            "CASE-ALPHA", self.fixture("alpha-imaging.txt"))
        other_patient = self.store.import_report(
            "CASE-BETA", self.fixture("beta-pathology.txt"))

        first = self.store.state("CASE-ALPHA")
        source_ids = {s["id"] for s in first["sources"]}
        self.assertIn(pathology["source_id"], source_ids)
        marker = next(a for a in first["assertions"] if a["finding_key"] == "marker-a")
        self.assertEqual(marker["certainty"], "not-reported")
        self.assertEqual(marker["source_version_id"], pathology["source_id"])
        self.assertTrue(marker["source_line"] > 0)

        question = self.store.add_question(
            "CASE-ALPHA", "Which interpretation is supported by the reported marker status?")
        unrelated_question = self.store.add_question(
            "CASE-ALPHA", "What does the separate imaging report state?")
        external = self.store.import_synthetic_evidence(EVIDENCE)
        assessment = self.store.assess_synthetic_evidence(
            "CASE-ALPHA", question, external["evidence_version_id"],
            "context", "limited",
            "This fictional methods note provides contextual limitations, not patient-specific efficacy.")

        candidate = validate_output(
            {"claims": [{
                "text": "The original source reports a missing fictional marker result.",
                "support": "context",
                "citations": [{"type": "source", "id": pathology["source_id"]}],
                "uncertainty": "moderate",
                "limits": "Synthetic context only, not a medical interpretation.",
            }], "abstentions": []},
            valid_sources={pathology["source_id"]},
            valid_assessments={assessment},
        )
        self.assertEqual(candidate.status, "completed")
        self.assertEqual(candidate.claims[0]["kind"], "hypothesis")
        self.assertEqual(candidate.claims[0]["citations"][0]["id"], pathology["source_id"])

        bound = self.store.create_snapshot(
            "CASE-ALPHA", question,
            "A human-authored synthetic review draft for an unresolved test.",
            [pathology["source_id"]], [assessment])
        independent = self.store.create_snapshot(
            "CASE-ALPHA", unrelated_question,
            "A separate human-authored draft about the available imaging report.",
            [imaging["source_id"]])
        beta_question = self.store.add_question(
            "CASE-BETA", "What does the unrelated fictional patient source say?")
        beta = self.store.create_snapshot(
            "CASE-BETA", beta_question,
            "An independently authored synthetic draft for the other case.",
            [other_patient["source_id"]])

        self.store.acknowledge_demo_review("CASE-ALPHA", bound, "Synthetic reviewer")
        before = build_patient_mission(self.store.state("CASE-ALPHA"))
        self.assertEqual(before["case"]["case_id"], "CASE-ALPHA")
        self.assertNotEqual(before["workflow_status"], "review_required")

        amendment = self.store.import_report(
            "CASE-ALPHA", self.fixture("alpha-pathology-amended.txt"))
        self.assertEqual(amendment["invalidated_snapshots"], [bound])
        after = self.store.state("CASE-ALPHA")
        status = {s["id"]: s["state"] for s in after["snapshots"]}
        self.assertEqual(status[bound], "stale")
        self.assertEqual(status[independent], "draft")
        self.assertEqual(
            build_patient_mission(after)["workflow_status"], "review_required")
        self.assertEqual(
            [s["version"] for s in after["sources"] if s["document_id"] == "PATH-ALPHA"],
            [1, 2])
        self.assertEqual(
            self.store.source_text("CASE-ALPHA", pathology["source_id"]).encode(),
            self.fixture("alpha-pathology-original.txt"))
        self.assertEqual(
            self.store.state("CASE-BETA")["snapshots"][0]["id"], beta)
        self.assertEqual(
            self.store.state("CASE-BETA")["snapshots"][0]["state"], "draft")
        self.assertIn("stale", self.store.export_markdown("CASE-ALPHA", bound))

        with self.assertRaises(InvalidInput):
            self.store.acknowledge_demo_review("CASE-ALPHA", bound, "Synthetic reviewer")
        with self.assertRaises(InvalidInput):
            self.store.source_text("CASE-BETA", pathology["source_id"])

    def test_unsupported_claim_cannot_enter_validated_model_candidate(self):
        pathology = self.store.import_report(
            "CASE-ALPHA", self.fixture("alpha-pathology-original.txt"))
        candidate = validate_output(
            {"claims": [{
                "text": "I recommend starting the drug based on this report.",
                "support": "supports",
                "citations": [{"type": "source", "id": pathology["source_id"]}],
                "uncertainty": "low",
                "limits": "",
            }], "abstentions": []},
            valid_sources={pathology["source_id"]},
            valid_assessments=set(),
        )
        # The exact language guard is a *synthetic model-output filter*,
        # never sufficient to authorize diagnosis or treatment.
        self.assertEqual(candidate.status, "abstained")
        self.assertFalse(candidate.claims)
        self.assertTrue(candidate.dropped)


if __name__ == "__main__":
    unittest.main()
