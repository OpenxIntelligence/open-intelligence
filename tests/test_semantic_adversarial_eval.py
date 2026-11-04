"""Offline tests for newly authored, non-independent semantic challenge set."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import semantic_adversarial_eval as challenge
import semantic_benchmark as benchmark
from semantic_contract_probe import schema_manifest

CASES = json.loads((ROOT / "tests/fixtures/semantic_adversarial_challenge_v2.json").read_text())
ORIGINAL = json.loads((ROOT / "tests/fixtures/semantic_benchmark_cases_v1.json").read_text())


class SemanticAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.cases = copy.deepcopy(CASES)
        self.original = copy.deepcopy(ORIGINAL)

    def replay(self):
        return {
            "contract": benchmark.PREDICTIONS_CONTRACT,
            "manifest_sha256": schema_manifest()["sha256"],
            "case_set_sha256": benchmark.digest(self.cases),
            "predictions": [{"id": row["id"], "status": "abstain"} for row in self.cases["cases"]],
        }

    def test_exact_frozen_profile_and_disjoint_ids(self):
        rows = challenge.validate_challenge(self.cases, self.original)
        self.assertEqual(len(rows), 72)
        self.assertEqual(sum(r["expected"] is not None for r in rows), 36)
        self.assertEqual(sum(r["expected"] is None for r in rows), 36)
        self.assertTrue(all(201 <= int(r["id"][2:]) <= 272 for r in rows))
        self.assertEqual(len({r["id"] for r in rows}), 72)

    def test_diverse_negative_taxonomy(self):
        report = challenge.evaluate(self.cases, self.original)
        summary = report["methods"][0]["by_negative_category"]
        self.assertEqual({name: sum(values.values()) for name, values in summary.items()},
                         {"ambiguous": 7, "unsupported": 7, "unsafe": 10, "false_join": 12})

    def test_each_source_concept_has_twelve_positive_labels(self):
        report = challenge.evaluate(self.cases, self.original)
        summary = report["methods"][0]["by_positive_concept"]
        self.assertEqual(set(summary), set(challenge.EXPECTED_CONCEPTS))
        self.assertTrue(all(sum(values.values()) == 12 for values in summary.values()))

    def test_baseline_outputs_are_research_only(self):
        result = challenge.evaluate(self.cases, self.original)
        self.assertEqual(result["reference_status"], "author_labeled_synthetic_not_independently_adjudicated")
        self.assertFalse(result["questions_blinded_from_model"])
        self.assertTrue(result["synthetic_schema_only"])
        self.assertTrue(result["no_patient_records_accessed"])
        self.assertTrue(result["no_provider_called"])
        self.assertTrue(result["no_sql_executed"])
        self.assertFalse(result["model_generated_semantics_tested"])
        self.assertFalse(result["clinical_validation"])
        self.assertFalse(result["adoption_approved"])
        self.assertEqual(len(result["methods"]), 1)
        self.assertEqual(result["methods"][0]["method"], "first_party_deterministic_baseline")
        self.assertEqual(result["methods"][0]["positive_correct"]
                         + result["methods"][0]["positive_abstained"]
                         + result["methods"][0]["positive_wrong"], 36)
        self.assertEqual(result["methods"][0]["negative_abstained"]
                         + result["methods"][0]["negative_false_mapping"], 36)

    def test_novel_negative_exposes_original_guard_generalization_limit(self):
        result = challenge.evaluate(self.cases, self.original)["methods"][0]
        self.assertGreater(result["unsafe_false_mappings"] + result["false_join_mappings"], 0)
        self.assertGreater(result["negative_false_mapping"], 0)
        self.assertTrue(result["flagged_case_ids"])

    def test_no_direct_question_overlap_with_original(self):
        left = {challenge._normalized(r["question"]) for r in self.cases["cases"]}
        right = {challenge._normalized(r["question"]) for r in self.original["cases"]}
        self.assertFalse(left & right)

    def test_external_abstain_replay_is_not_fake_model_success(self):
        result = challenge.evaluate(self.cases, self.original, self.replay())
        ext = result["methods"][1]
        self.assertEqual(ext["method"], "external_offline_replay_unverified")
        self.assertEqual(ext["positive_correct"], 0)
        self.assertEqual(ext["positive_abstained"], 36)
        self.assertEqual(ext["negative_abstained"], 36)
        self.assertEqual(ext["negative_false_mapping"], 0)
        self.assertFalse(result["model_generated_semantics_tested"])
        self.assertFalse(result["adoption_approved"])

    def test_external_false_join_and_unsafe_are_counted(self):
        replay = self.replay()
        for ident, concept, field in [
            ("B-251", "source_observation", "reported_state"),
            ("B-261", "source_observation", "specimen_id"),
        ]:
            item = next(p for p in replay["predictions"] if p["id"] == ident)
            item.update({"status": "proposed", "concept": concept, "field": field,
                         "candidate_term": "unreviewed_field_candidate",
                         "review_state": "unreviewed_proposal"})
        result = challenge.evaluate(self.cases, self.original, replay)["methods"][1]
        self.assertEqual(result["unsafe_false_mappings"], 1)
        self.assertEqual(result["false_join_mappings"], 1)
        self.assertEqual(result["negative_false_mapping"], 2)
        self.assertIn("B-251", {x["id"] for x in result["flagged_case_ids"]})
        self.assertIn("B-261", {x["id"] for x in result["flagged_case_ids"]})

    def test_untrusted_external_patient_text_is_rejected(self):
        candidate = self.replay()
        candidate["predictions"][0]["patient_note"] = "unpermitted content"
        with self.assertRaises(ValueError):
            challenge.evaluate(self.cases, self.original, candidate)

    def test_stale_replay_hash_is_rejected(self):
        candidate = self.replay()
        candidate["case_set_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            challenge.evaluate(self.cases, self.original, candidate)

    def test_duplicate_original_question_rejected(self):
        self.cases["cases"][0]["question"] = self.original["cases"][0]["question"]
        with self.assertRaisesRegex(ValueError, "overlaps"):
            challenge.validate_challenge(self.cases, self.original)

    def test_duplicate_new_question_rejected(self):
        self.cases["cases"][1]["question"] = self.cases["cases"][0]["question"]
        with self.assertRaises(ValueError):
            challenge.validate_challenge(self.cases, self.original)

    def test_changed_gold_category_mix_is_rejected(self):
        self.cases["cases"][-1]["category"] = "unsafe"
        with self.assertRaisesRegex(ValueError, "coverage"):
            challenge.validate_challenge(self.cases, self.original)

    def test_changed_gold_concept_mix_is_rejected(self):
        self.cases["cases"][0]["expected"] = {"concept": "source_observation", "field": "source_id"}
        with self.assertRaisesRegex(ValueError, "12 mappings"):
            challenge.validate_challenge(self.cases, self.original)

    def test_missing_or_excess_cases_rejected(self):
        self.cases["cases"].pop()
        with self.assertRaisesRegex(ValueError, "72"):
            challenge.validate_challenge(self.cases, self.original)

    def test_oversized_input_rejected_without_reading_arbitrary_data(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fixture.json"
            path.write_bytes(b" " * (challenge.MAX_INPUT_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size bound"):
                challenge._strict_read(path)

    def test_report_digests_are_stable(self):
        a = challenge.evaluate(self.cases, self.original)
        b = challenge.evaluate(self.cases, self.original)
        self.assertEqual(a, b)
        self.assertEqual(a["challenge_sha256"], benchmark.digest(self.cases))
        self.assertEqual(a["original_benchmark_sha256"], benchmark.digest(self.original))


if __name__ == "__main__":
    unittest.main()
