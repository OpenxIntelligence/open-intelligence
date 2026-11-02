"""Native Composer context contract tests over the existing synthetic ledger.

The native Composer is a source-bound preflight on the *existing* investigation
path. It creates no new patient record, model, agent queue or clinical decision.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from open_intelligence.__main__ import seed
from open_intelligence.composer import build_composer_context, composer_context_fingerprint
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.store import CaseStore, InvalidInput


EVIDENCE = (b"OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVID-COMPOSER\n"
            b"Title: Independently authored fictional study note\n"
            b"Issued-At: 2026-01-03\nRights: original-synthetic\n"
            b"Statement: This fictional study note is not a real clinical guideline.\n")


class ComposerContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "composer.sqlite"
        seed(str(self.db_path))
        self.store = CaseStore(self.db_path)
        self.question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional source record establish and leave unresolved?")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_source_bound_context_reuses_canonical_patient_mission_and_source_lines(self):
        context = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.assertEqual(context["case_id"], "CASE-ALPHA")
        self.assertEqual(context["question_id"], self.question)
        self.assertEqual(context["mission"]["case"]["case_id"], "CASE-ALPHA")
        self.assertEqual(context["mission"]["workflow_status"], "investigation_in_progress")
        self.assertTrue(context["source_anchors"])
        self.assertTrue(all(
            isinstance(x["source_version_id"], int) and x["source_line"] > 0
            and x["reported_state"] in {"reported", "negative", "pending", "indeterminate",
                                         "not-reported", "not-assessed", "conflicting"}
            for x in context["source_anchors"]))
        self.assertTrue(all(x["document_id"] and x["sha256"]
                            for x in context["current_sources"]))
        self.assertTrue(all(x["state"] == "current" for x in context["current_sources"]))
        self.assertEqual(len(context["fingerprint"]), 64)
        self.assertEqual(
            context["fingerprint"],
            composer_context_fingerprint(self.store, "CASE-ALPHA", self.question))
        self.assertEqual(context["context_kind"], "synthetic_source_bound_read_only")

    def test_context_exposes_only_bounded_tasks_and_explicitly_unavailable_knowledge(self):
        context = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.assertEqual(set(x["id"] for x in context["templates"]),
                         {"evidence-summary", "timeline-gaps", "evidence-applicability"})
        self.assertEqual(context["tool_status"]["external_guideline_search"], "unavailable")
        self.assertEqual(context["tool_status"]["live_clinical_trials"], "unavailable")
        self.assertEqual(context["tool_status"]["clinical_authorization"], "not_verified")
        self.assertEqual(context["tool_status"]["analysis_execution"], "unavailable")
        self.assertNotIn("patient treatment recommendation", str(context).lower())

    def test_missing_or_other_case_question_is_refused(self):
        with self.assertRaises(InvalidInput):
            build_composer_context(self.store, "CASE-BETA", self.question)
        with self.assertRaises(InvalidInput):
            build_composer_context(self.store, "CASE-ALPHA", 999999)
        with self.assertRaises(InvalidInput):
            build_composer_context(self.store, "CASE-ALPHA", True)

    def test_amendment_changes_preview_and_refuses_obsolete_context_on_atomic_save(self):
        before = build_composer_context(self.store, "CASE-ALPHA", self.question)
        original = next(x for x in before["current_sources"]
                        if x["kind"] == "pathology")
        from open_intelligence.__main__ import SYNTHETIC
        changed = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        self.assertEqual(changed["result"], "imported")
        after = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])
        self.assertNotIn(original["id"], {x["id"] for x in after["current_sources"]})
        self.assertEqual(len(before["current_sources"]), len(after["current_sources"]))
        validated = ValidatedInvestigation("abstained", [], [], [], "recorded-replay", "replay")
        with self.assertRaisesRegex(InvalidInput, "stale"):
            self.store.save_investigation(
                "CASE-ALPHA", self.question, "evidence-summary", validated, "replay",
                context_fingerprint=before["fingerprint"])
        self.assertEqual(self.store.list_investigations("CASE-ALPHA"), [])

    def test_current_source_and_eligible_assessment_are_exactly_version_scoped(self):
        before = build_composer_context(self.store, "CASE-ALPHA", self.question)
        imported = self.store.import_synthetic_evidence(EVIDENCE)
        self.assertEqual(imported["result"], "imported")
        evidence_version = imported["evidence_version_id"]
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.question, evidence_version,
            "context", "limited",
            "Fictional supporting research note has explicitly limited applicability.")
        assessed = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.assertNotEqual(assessed["fingerprint"], before["fingerprint"])
        self.assertEqual(len(assessed["evidence_assessments"]), 1)
        self.assertEqual(assessed["evidence_assessments"][0]["applicability"], "limited")
        self.store.withdraw_synthetic_evidence(
            evidence_version, "Fictional example withdrawn for reproducible verification.")
        withdrawn = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.assertEqual(withdrawn["evidence_assessments"], [])
        self.assertNotEqual(assessed["fingerprint"], withdrawn["fingerprint"])

    def test_source_amendment_stales_saved_model_only_investigation_without_draft(self):
        before = build_composer_context(self.store, "CASE-ALPHA", self.question)
        validated = ValidatedInvestigation(
            "abstained", [], [{"topic": "Unresolved history",
                               "reason": "insufficient_evidence"}],
            [], "recorded-replay", "replay")
        investigation_id = self.store.save_investigation(
            "CASE-ALPHA", self.question, "evidence-summary",
            validated, "replay", context_fingerprint=before["fingerprint"])
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", investigation_id)["stale"])
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"], [])
        from open_intelligence.__main__ import SYNTHETIC
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        self.assertTrue(
            self.store.get_investigation("CASE-ALPHA", investigation_id)["stale"],
            "A model-only result over the full case context must not survive "
            "a source amendment as current work")

    def test_fingerprint_is_stable_on_restart_until_inputs_change(self):
        before = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.store.close()
        self.store = CaseStore(self.db_path)
        after = build_composer_context(self.store, "CASE-ALPHA", self.question)
        self.assertEqual(before["fingerprint"], after["fingerprint"])
        self.assertEqual(before["source_anchors"], after["source_anchors"])


if __name__ == "__main__":
    unittest.main()
