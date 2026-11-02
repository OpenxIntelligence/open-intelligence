"""IV-02/IV-03 contract integrity: the adjudication contract, the baseline
procedure, and the run-record template must stay complete, mutually
consistent, and free of packet fixture answers.

These tests validate the contract documents only. They do not depend on
any packet fixture files (for example the runnable packet proposed in
PR #24), so they pass on main whether or not that packet has merged.
They are engineering checks on documents, not clinical validation.
"""

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKET_DIR = ROOT / "validation" / "iv01"
ADJUDICATION = PACKET_DIR / "ADJUDICATION.md"
BASELINE = PACKET_DIR / "BASELINE.md"
RUN_RECORD = PACKET_DIR / "run_record_template.json"

# Outcome vocabulary shared by ADJUDICATION.md and the worksheet columns.
OUTCOMES = (
    "correct",
    "incorrect",
    "unsupported",
    "omitted",
    "abstain",
    "not_applicable",
    "not_scored",
)

BURDEN_BUCKETS = (
    "acquisition",
    "preparation",
    "correction",
    "review",
    "coordination",
)

# Strings that would leak packet fixture answers or case identities into
# evaluator-facing contract documents. The contract must stay generic:
# it names no fixture case, source, or expected answer.
FORBIDDEN_FIXTURE_STRINGS = (
    "CASE-EVAL",
    "EVAL-A-PATH",
    "EVAL-B-PATH",
    "designer_expected",
    "coordinator_key",
)


class TestAdjudicationContract(unittest.TestCase):
    def setUp(self):
        self.text = ADJUDICATION.read_text(encoding="utf-8")

    def test_document_exists_and_states_unadjudicated(self):
        self.assertTrue(ADJUDICATION.is_file())
        self.assertIn("unadjudicated", self.text.lower())
        self.assertIn("not clinical validation", self.text.lower())

    def test_two_rubrics_present_and_never_merged(self):
        self.assertIn("Rubric A", self.text)
        self.assertIn("Rubric B", self.text)
        self.assertIn("never merged", self.text.lower())
        self.assertIn("not-assessable-from-synthetic-packet", self.text)

    def test_rubric_a_outcome_vocabulary(self):
        for outcome in OUTCOMES:
            self.assertIn("`%s`" % outcome, self.text)

    def test_severity_categories_s0_to_s3(self):
        for level in ("S0", "S1", "S2", "S3"):
            self.assertIn(level, self.text)
        self.assertNotIn("S4", self.text)
        self.assertIn("never averaged away", self.text.lower())

    def test_independence_conflict_and_prior_exposure(self):
        for term in ("conflict", "prior exposure", "recused", "anonymous"):
            self.assertIn(term, self.text.lower())

    def test_disagreement_and_abstention_procedure(self):
        self.assertIn("explicitly unresolved", self.text)
        self.assertIn("abstain", self.text.lower())
        self.assertIn("reported separately from omissions", self.text.lower())
        self.assertIn("never scored as correct", self.text.lower())

    def test_freeze_before_scoring_and_retrofit_ban(self):
        self.assertIn("frozen", self.text.lower())
        self.assertIn("before", self.text.lower())
        self.assertIn("retrofit", self.text.lower())

    def test_denominators_and_preservation(self):
        for term in (
            "Source fidelity",
            "Missingness fidelity",
            "Identity boundary",
            "Amendment handling",
            "Temporal leakage",
            "False urgency",
        ):
            self.assertIn(term, self.text)
        self.assertIn("false", self.text.lower())
        self.assertIn("percentage-only", self.text)

    def test_worksheet_columns_cover_burden_and_leakage(self):
        for column in (
            "rubric_a_outcome",
            "rubric_b_outcome",
            "severity",
            "post_cutoff_leak",
            "prior_key_exposure",
            "disagreement",
            "adjudicator_outcome",
        ):
            self.assertIn(column, self.text)
        for bucket in BURDEN_BUCKETS:
            self.assertIn("%s_minutes" % bucket, self.text)

    def test_decision_template(self):
        for decision in ("Go", "Repair", "Stop"):
            self.assertIn(decision, self.text)

    def test_no_fixture_answers_leak_into_contract(self):
        for leaked in FORBIDDEN_FIXTURE_STRINGS:
            self.assertNotIn(leaked, self.text)


class TestBaselineProcedure(unittest.TestCase):
    def setUp(self):
        self.text = BASELINE.read_text(encoding="utf-8")

    def test_document_exists_and_states_limitations(self):
        self.assertTrue(BASELINE.is_file())
        self.assertIn("unadjudicated", self.text.lower())
        self.assertIn("not clinical validation", self.text.lower())
        self.assertIn("does not transfer", self.text.lower())

    def test_clean_checkout_is_fail_closed(self):
        for step in (
            "git clone",
            "git checkout",
            "git rev-parse HEAD",
            "git status --porcelain",
            "git diff --exit-code",
            "VOID",
        ):
            self.assertIn(step, self.text)
        self.assertIn("PYTHONPATH=src python3 -m unittest discover -s tests", self.text)
        self.assertIn("node --check web/app.js", self.text)

    def test_ordinary_case_brief_structure(self):
        self.assertIn("ordinary case brief", self.text.lower())
        for section in (
            "Sources actually reporting",
            "What remains unknown",
            "Source versions and specimen identities",
            "What changed since the previous cutoff",
            "What cannot be concluded",
        ):
            self.assertIn(section, self.text)
        self.assertIn("before the evaluated system output is opened", self.text)

    def test_three_arms_with_equal_information(self):
        for arm in (
            "Arm A",
            "Arm B",
            "Arm C",
            "Manual source reading",
            "deterministic",
            "current source-investigation application",
        ):
            self.assertIn(arm, self.text)
        self.assertIn("identical", self.text.lower())
        self.assertIn("counterbalance", self.text.lower())

    def test_burden_ledger_buckets(self):
        for bucket in BURDEN_BUCKETS:
            self.assertIn(bucket, self.text)
        self.assertIn("failed runs", self.text.lower())

    def test_no_fixture_answers_leak_into_baseline(self):
        for leaked in FORBIDDEN_FIXTURE_STRINGS:
            self.assertNotIn(leaked, self.text)


class TestRunRecordTemplate(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(RUN_RECORD.read_text(encoding="utf-8"))

    def test_template_is_unactivated_with_null_thresholds(self):
        self.assertEqual(self.record["status"], "not_activated")
        self.assertFalse(self.record["results_observed"])
        for value in self.record["thresholds"].values():
            self.assertIsNone(value)

    def test_required_fields_present(self):
        for field in (
            "evaluation_id",
            "packet_commit",
            "application_commit",
            "case_id",
            "cutoff",
            "arm",
            "reviewer_id",
            "input_sha256",
            "output_sha256",
            "baseline_brief_sha256",
            "git_status_clean",
            "decision",
        ):
            self.assertIn(field, self.record)

    def test_burden_and_outcome_fields(self):
        for bucket in BURDEN_BUCKETS:
            self.assertIn(bucket, self.record["burden_minutes"])
        self.assertIn("total", self.record["burden_minutes"])
        for field in (
            "reported",
            "unknown",
            "corrected",
            "abstained",
            "timed_out",
            "failed",
        ):
            self.assertIn(field, self.record["outcome_counts"])

    def test_freeze_checklist_all_false(self):
        self.assertTrue(self.record["freeze"])
        for value in self.record["freeze"].values():
            self.assertIs(value, False)

    def test_packet_and_application_commits_are_distinct_fields(self):
        self.assertIn("packet_commit", self.record)
        self.assertIn("application_commit", self.record)
        self.assertNotEqual("packet_commit", "application_commit")


if __name__ == "__main__":
    unittest.main()
