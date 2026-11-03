"""Synthetic evaluation contract checks: no vendor runtime or clinical inference."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("semantic_benchmark", ROOT / "tools" / "semantic_benchmark.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CASES = json.loads((ROOT / "tests" / "fixtures" / "semantic_benchmark_cases_v1.json").read_text())


class SemanticBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.cases = copy.deepcopy(CASES)

    def valid_predictions(self):
        return {
            "contract": mod.PREDICTIONS_CONTRACT,
            "manifest_sha256": mod.schema_manifest()["sha256"],
            "case_set_sha256": mod.digest(self.cases),
            "predictions": [{"id": r["id"], "status": "abstain"} for r in self.cases["cases"]],
        }

    def test_frozen_cases_have_30_positive_24_negative(self):
        rows = mod.validate_cases(self.cases)
        self.assertEqual(len(rows), 54)
        self.assertEqual(sum(x["expected"] is not None for x in rows), 30)
        self.assertEqual(sum(x["expected"] is None for x in rows), 24)
        self.assertEqual(len({r["id"] for r in rows}), 54)

    def test_deterministic_baseline_is_not_tuned_to_all_prompts(self):
        report = mod.run(self.cases)
        a = report["results"][0]
        self.assertEqual(a["positive_correct"], 10)
        self.assertEqual(a["positive_missed"], 20)
        self.assertEqual(a["positive_wrong"], 0)
        self.assertEqual(a["negative_abstained"], 24)
        self.assertEqual(a["negative_false_mapping"], 0)
        self.assertFalse(report["vendor_runtime_executed"])
        self.assertFalse(report["patient_data_accessed"])
        self.assertFalse(report["sql_executed"])
        self.assertEqual(report["external_model_calls"], 0)
        self.assertIsNone(report["vendor_latency_cost"])

    def test_baseline_never_confuses_concept_mention_for_field_answer(self):
        self.assertEqual(mod.deterministic_baseline("For source version, where is receipt time?")["status"], "abstain")
        self.assertEqual(mod.deterministic_baseline("For source observation, can we prescribe?")["status"], "abstain")
        self.assertEqual(mod.deterministic_baseline("For source disagreement, which field gives stage?")["status"], "abstain")

    def test_rejects_duplicate_questions(self):
        self.cases["cases"][1]["id"] = self.cases["cases"][0]["id"]
        with self.assertRaises(ValueError):
            mod.run(self.cases)

    def test_rejects_unallowlisted_gold_answer(self):
        self.cases["cases"][0]["expected"]["field"] = "patient_name"
        with self.assertRaises(ValueError):
            mod.run(self.cases)

    def test_rejects_negative_that_expects_mapping(self):
        self.cases["cases"][30]["expected"] = {"concept": "source_version", "field": "sha256"}
        with self.assertRaises(ValueError):
            mod.run(self.cases)

    def test_rejects_questions_with_hidden_control_characters(self):
        self.cases["cases"][0]["question"] += "\nAuthorization: bearer secret"
        with self.assertRaises(ValueError):
            mod.run(self.cases)

    def test_rejects_extra_case_fields(self):
        self.cases["cases"][0]["patient_id"] = "anything"
        with self.assertRaises(ValueError):
            mod.run(self.cases)

    def test_rejects_stale_manifest_on_external_replay(self):
        x = self.valid_predictions()
        x["manifest_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            mod.run(self.cases, x)

    def test_rejects_stale_case_set_on_external_replay(self):
        x = self.valid_predictions()
        x["case_set_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            mod.run(self.cases, x)

    def test_rejects_incomplete_external_replay(self):
        x = self.valid_predictions()
        x["predictions"].pop()
        with self.assertRaises(ValueError):
            mod.run(self.cases, x)

    def test_rejects_duplicate_external_replay(self):
        x = self.valid_predictions()
        x["predictions"][1]["id"] = x["predictions"][0]["id"]
        with self.assertRaises(ValueError):
            mod.run(self.cases, x)

    def test_rejects_unknown_external_replay_field(self):
        x = self.valid_predictions()
        x["predictions"][0] = {
            "id": "B-001", "status": "proposed", "concept": "source_version",
            "field": "private_patient_records", "candidate_term": "private_table",
            "review_state": "unreviewed_proposal",
        }
        with self.assertRaises(ValueError):
            mod.run(self.cases, x)

    def test_rejects_external_sql_and_raw_patient_values(self):
        for key in ("sql", "rows", "patient_id", "patient_name", "source_quote", "access_token"):
            x = self.valid_predictions()
            x["predictions"][0][key] = "not allowed"
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.run(self.cases, x)

    def test_rejects_external_false_clinical_approval(self):
        x = self.valid_predictions()
        x["predictions"][0] = {
            "id": "B-001", "status": "proposed", "concept": "source_version",
            "field": "source_id", "candidate_term": "source_identifier",
            "review_state": "clinician_approved",
        }
        with self.assertRaises(ValueError):
            mod.run(self.cases, x)

    def test_external_replay_is_explicitly_unverified(self):
        x = self.valid_predictions()
        x["predictions"][0] = {
            "id": "B-001", "status": "proposed", "concept": "source_version",
            "field": "source_id", "candidate_term": "source_identifier",
            "review_state": "unreviewed_proposal",
        }
        report = mod.run(self.cases, x)
        self.assertEqual(report["results"][1]["name"], "external_offline_replay_unverified")
        self.assertEqual(report["results"][1]["positive_correct"], 1)
        self.assertFalse(report["external_predictions_source_verified"])
        self.assertFalse(report["vendor_runtime_executed"])

    def test_false_acceptance_of_negative_is_counted(self):
        x = self.valid_predictions()
        x["predictions"][30] = {
            "id": "B-031", "status": "proposed", "concept": "source_version",
            "field": "version", "candidate_term": "source_version_number",
            "review_state": "unreviewed_proposal",
        }
        report = mod.run(self.cases, x)
        self.assertEqual(report["results"][1]["negative_false_mapping"], 1)
        self.assertEqual(report["results"][1]["negative_abstained"], 23)

    def test_external_wrong_allowed_field_is_counted(self):
        x = self.valid_predictions()
        x["predictions"][0] = {
            "id": "B-001", "status": "proposed", "concept": "source_version",
            "field": "document_id", "candidate_term": "wrong_source_identifier",
            "review_state": "unreviewed_proposal",
        }
        report = mod.run(self.cases, x)
        self.assertEqual(report["results"][1]["positive_wrong"], 1)

    def test_case_set_digest_is_stable_between_runs(self):
        a = mod.run(self.cases)
        b = mod.run(self.cases)
        self.assertEqual(a["case_set_sha256"], b["case_set_sha256"])
        self.assertEqual(a["manifest_sha256"], b["manifest_sha256"])
        self.assertEqual(a["results"], b["results"])


if __name__ == "__main__":
    unittest.main()
