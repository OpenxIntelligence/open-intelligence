"""Checks for original-synthetic, versioned research evidence.

These tests verify software contracts only, not clinical correctness.
"""
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]

def report(name):
    return (ROOT / "examples" / "synthetic" / name).read_bytes()

ORIGINAL = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: EVID-ASSAY
Title: Fictional assay methods example
Issued-At: 2026-05-09
Rights: original-synthetic
Statement: This independently authored fictional note describes an assay limitation; it is not evidence of treatment efficacy.
"""

AMENDED = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: EVID-ASSAY
Title: Fictional assay methods example, corrected
Issued-At: 2026-05-11
Rights: original-synthetic
Amends: EVID-ASSAY@1
Statement: This fictional correction makes the assay limitations explicit; no patient-specific conclusion follows.
"""


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "cases.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.source_a = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))["source_id"]
        self.source_b = self.store.import_report("CASE-BETA", report("beta-pathology.txt"))["source_id"]
        self.question_a = self.store.add_question("CASE-ALPHA", "What does the fictional assay demonstrate?")
        self.question_b = self.store.add_question("CASE-BETA", "What does the fictional assay not demonstrate?")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def assessment(self, case_id="CASE-ALPHA", question_id=None, evidence_id=None,
                   relation="context", applicability="limited"):
        evidence_id = evidence_id or self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        question_id = question_id or (self.question_a if case_id == "CASE-ALPHA" else self.question_b)
        return self.store.assess_synthetic_evidence(
            case_id, question_id, evidence_id, relation, applicability,
            "Fictional text is relevant only to demonstrating provenance, not clinical applicability.")

    def test_versioned_import_preserves_bytes_hash_and_line(self):
        outcome = self.store.import_synthetic_evidence(ORIGINAL)
        self.assertEqual(outcome["version"], 1)
        entry = self.store.state("CASE-ALPHA")["evidence"][0]
        self.assertEqual(entry["rights"], "original-synthetic")
        self.assertEqual(entry["state"], "current")
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertEqual(entry["statement_line"], 6)
        self.assertEqual(self.store.synthetic_evidence_text(outcome["evidence_version_id"]).encode(), ORIGINAL)

    def test_duplicate_noop_and_changed_requires_explicit_amendment(self):
        first = self.store.import_synthetic_evidence(ORIGINAL)
        second = self.store.import_synthetic_evidence(ORIGINAL)
        self.assertEqual(second["result"], "duplicate")
        self.assertEqual(first["evidence_version_id"], second["evidence_version_id"])
        changed = ORIGINAL.replace(b"assay limitation", b"assay limitations")
        with self.assertRaisesRegex(InvalidInput, "Amends"):
            self.store.import_synthetic_evidence(changed)
        self.assertEqual(len(self.store.state("CASE-ALPHA")["evidence"]), 1)

    def test_unlicensed_or_nonfictional_format_not_accepted(self):
        for raw in (
            ORIGINAL.replace(b"original-synthetic", b"public-article"),
            ORIGINAL.replace(b"OI-SYNTHETIC-EVIDENCE/1", b"JOURNAL-ARTICLE/1"),
            ORIGINAL.replace(b"Rights: original-synthetic\n", b""),
            ORIGINAL.replace(b"Statement: ", b"Unknown: "),
            b"\xff",
        ):
            with self.subTest(raw=raw[:70]):
                with self.assertRaises(InvalidInput):
                    self.store.import_synthetic_evidence(raw)
        self.assertEqual(self.store.state("CASE-BETA")["evidence"], [])

    def test_assessments_are_question_scoped_and_support_requires_applicability(self):
        version = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        a = self.assessment(evidence_id=version, relation="contradicts", applicability="unknown")
        rows = self.store.state("CASE-ALPHA")["evidence_assessments"]
        self.assertEqual(rows[0]["id"], a)
        self.assertEqual(rows[0]["relation"], "contradicts")
        self.assertEqual(rows[0]["statement_line"], 6)
        with self.assertRaisesRegex(InvalidInput, "inapplicable"):
            self.assessment(evidence_id=version, relation="supports", applicability="not_applicable")
        with self.assertRaisesRegex(InvalidInput, "Question not in this case"):
            self.assessment(case_id="CASE-BETA", question_id=self.question_a, evidence_id=version)

    def test_snapshot_binding_preserves_evidence_and_export_is_explicit(self):
        version = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        aid = self.assessment(evidence_id=version)
        sid = self.store.create_snapshot("CASE-ALPHA", self.question_a,
                                         "This case note and research text are synthetic only.",
                                         [self.source_a], [aid])
        snapshot = self.store.state("CASE-ALPHA")["snapshots"][0]
        self.assertEqual(snapshot["evidence_assessment_ids"], [aid])
        output = self.store.export_markdown("CASE-ALPHA", sid)
        self.assertIn("EVID-ASSAY@1", output)
        self.assertIn("Fictional evidence assessments", output)
        self.assertIn("Source line: 6", output)
        self.assertIn("not evidence of treatment efficacy", output)
        self.assertIn("no real publication", output)
        with self.assertRaisesRegex(InvalidInput, "outside this question"):
            self.store.create_snapshot("CASE-BETA", self.question_b,
                                       "This case should not reuse a different case assessment.",
                                       [self.source_b], [aid])

    def test_revision_invalidates_only_snapshots_using_old_version(self):
        old = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        aid = self.assessment(evidence_id=old)
        linked = self.store.create_snapshot("CASE-ALPHA", self.question_a,
                                            "First historical version of a fictional investigation.",
                                            [self.source_a], [aid])
        unaffected = self.store.create_snapshot("CASE-ALPHA", self.question_a,
                                                "Independent patient-source-only investigation draft.",
                                                [self.source_a])
        self.store.acknowledge_demo_review("CASE-ALPHA", linked, "Synthetic reviewer")
        result = self.store.import_synthetic_evidence(AMENDED)
        self.assertEqual(result["invalidated_snapshots"], [linked])
        states = {s["id"]: s["state"] for s in self.store.state("CASE-ALPHA")["snapshots"]}
        self.assertEqual(states[linked], "stale")
        self.assertEqual(states[unaffected], "draft")
        self.assertEqual(self.store.state("CASE-ALPHA")["evidence"][0]["state"], "superseded")
        self.assertEqual(self.store.state("CASE-ALPHA")["evidence"][1]["state"], "current")
        self.assertEqual(self.store.state("CASE-ALPHA")["questions"][0]["state"], "open")
        with self.assertRaisesRegex(InvalidInput, "stale"):
            self.store.create_snapshot("CASE-ALPHA", self.question_a,
                                       "An old evidence assessment must not be reused.", [self.source_a], [aid])
        self.assertEqual(self.store.synthetic_evidence_text(old).encode(), ORIGINAL)
        self.assertIn("superseded", self.store.export_markdown("CASE-ALPHA", linked))

    def test_withdrawal_invalidates_all_case_dependencies(self):
        version = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        a = self.assessment(evidence_id=version)
        b = self.assessment(case_id="CASE-BETA", evidence_id=version)
        alpha_snapshot = self.store.create_snapshot("CASE-ALPHA", self.question_a,
                                                     "Fictional content linked to a local source.",
                                                     [self.source_a], [a])
        beta_snapshot = self.store.create_snapshot("CASE-BETA", self.question_b,
                                                    "Fictional content linked to a different case.",
                                                    [self.source_b], [b])
        out = self.store.withdraw_synthetic_evidence(version, "Synthetic text intentionally retired from the demo.")
        self.assertEqual(set(out["invalidated_snapshots"]), {alpha_snapshot, beta_snapshot})
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"][0]["state"], "stale")
        self.assertEqual(self.store.state("CASE-BETA")["snapshots"][0]["state"], "stale")
        history = self.store.state("CASE-ALPHA")["evidence_changes"]
        self.assertEqual(history[0]["kind"], "withdrawn")
        self.assertEqual(history[0]["reason"], "Synthetic text intentionally retired from the demo.")
        with self.assertRaisesRegex(InvalidInput, "not current"):
            self.assessment(evidence_id=version)
        with self.assertRaisesRegex(InvalidInput, "Withdrawn evidence"):
            self.store.import_synthetic_evidence(AMENDED)


    def test_fictional_evidence_markdown_fences_do_not_escape_export(self):
        crafted = ORIGINAL.replace(b"EVID-ASSAY", b"EVID-FENCE").replace(
            b"assay limitation", b"long " + b"````" + b" assay limitation")
        version = self.store.import_synthetic_evidence(crafted)["evidence_version_id"]
        assessment = self.assessment(evidence_id=version)
        snapshot = self.store.create_snapshot("CASE-ALPHA", self.question_a,
                                              "A synthetic report with embedded Markdown fence characters.",
                                              [self.source_a], [assessment])
        export = self.store.export_markdown("CASE-ALPHA", snapshot)
        self.assertIn("`````text", export)
        self.assertIn("````" + " assay limitation", export)

    def test_invalid_assessment_types_fail_cleanly(self):
        version = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        with self.assertRaises(InvalidInput):
            self.store.assess_synthetic_evidence("CASE-ALPHA", self.question_a, version,
                                                  ["supports"], "limited",
                                                  "A fictional rationale with sufficient length.")

if __name__ == "__main__":
    unittest.main()
