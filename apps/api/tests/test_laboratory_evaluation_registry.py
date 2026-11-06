"""Synthetic integration checks for immutable laboratory experiment artifacts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from oi_api.laboratory_evaluation import (
    FIELDS, LaboratoryEvaluationRegistry, baseline_output, fingerprint, read_json,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "validation" / "laboratory-evaluation"
SYSTEM = {"system_id": "test-candidate", "system_version": "1", "software_commit": "a" * 40}


def manifest():
    return read_json((FIXTURES / "dataset.json").read_bytes())


def reference():
    return read_json((FIXTURES / "reference.json").read_bytes())["observations"]


class LaboratoryEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "experiments.sqlite"
        self.registry = LaboratoryEvaluationRegistry(self.path)
        self.addCleanup(self.registry.close)
        self.key = self.registry.freeze(manifest())["dataset"]

    def run_baseline(self, run_id="baseline"):
        self.registry.baseline(run_id, self.key, "a" * 40)
        return self.registry.run(run_id)

    def review_for(self, run, case_id, *, decision="correct"):
        return {"run_id": run["run_id"], "case_id": case_id, "reviewer_id": "fixture-author",
                "independence_declared": False, "decision": decision,
                "output_sha256": fingerprint(run["outputs"][case_id]),
                "corrected_observations": reference()[case_id] if decision == "correct" else None,
                "reason": "Authored engineering reference; not an independent human adjudication.",
                "correction_seconds": 0}

    def reviewed_baseline(self):
        run = self.run_baseline()
        for case_id in run["outputs"]:
            self.registry.review(self.review_for(run, case_id))
        return run

    def test_actual_parser_against_separately_authored_reference_and_restart(self):
        run = self.reviewed_baseline()
        for case_id, output in run["outputs"].items():
            self.assertEqual(output["observations"], reference()[case_id])
        report = self.registry.score("baseline", "baseline")
        self.assertEqual(sum(g["field_opportunities"] for g in report["by_split"].values()), 4 * len(FIELDS))
        self.assertEqual(sum(g["field_errors"] for g in report["by_split"].values()), 0)
        self.assertFalse(report["clinical_validation"])
        self.assertFalse(report["independent_evaluation_established"])
        with LaboratoryEvaluationRegistry(self.path) as reopened:
            self.assertEqual(reopened.run("baseline"), run)
            self.assertEqual(reopened.score("baseline", "baseline"), report)
            self.assertEqual(reopened.db.execute("SELECT count(*) FROM records WHERE kind='score'").fetchone()[0], 1)

    def test_errors_omissions_unsupported_and_precision_count_against_reference(self):
        run = self.reviewed_baseline()
        outputs = deepcopy(run["outputs"])
        a = outputs["LAB-TRAIN-A"]["observations"][0]
        a["value_text"], a["unit_code"] = "4.2", "mg/L"
        b = outputs["LAB-VALIDATION-B"]["observations"][0]
        b.update(status="reported_value", value_text="0", absent_reason=None, unit_code="10*9/L")
        outputs["LAB-TEST-C-V1"] = {"status": "abstained", "observations": [], "reason": "No supported result"}
        extra = deepcopy(outputs["LAB-TEST-C-V2"]["observations"][0])
        extra["reference"] = "Observation/FABRICATED"
        outputs["LAB-TEST-C-V2"]["observations"].append(extra)
        self.registry.record_run("candidate", self.key, SYSTEM, outputs)
        report = self.registry.score("candidate", "baseline")
        self.assertEqual(report["by_split"]["train"]["field_errors"], 2)
        self.assertEqual(report["by_split"]["validation"]["field_errors"], 4)
        self.assertEqual(report["by_split"]["test"]["field_errors"], len(FIELDS))
        self.assertEqual(report["by_split"]["test"]["omissions"], 1)
        self.assertEqual(report["by_split"]["test"]["unsupported_observations"], 1)
        self.assertEqual(report["by_split"]["test"]["abstentions"], 1)
        self.assertEqual(self.registry.run("baseline"), run)

    def test_correction_does_not_replace_output_and_different_review_conflicts(self):
        outputs = {c["case_id"]: baseline_output(c) for c in manifest()["cases"]}
        outputs["LAB-TRAIN-A"]["observations"][0]["unit_code"] = "wrong-unit"
        self.registry.record_run("candidate", self.key, SYSTEM, outputs)
        run = self.registry.run("candidate")
        review = self.review_for(run, "LAB-TRAIN-A")
        review["correction_seconds"] = 14.5
        receipt = self.registry.review(review)
        self.assertEqual(self.registry.review(review), receipt)
        self.assertEqual(self.registry.run("candidate"), run)
        review["reason"] = "Conflicting replacement"
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.registry.review(review)

    def test_exact_dataset_run_retries_and_changed_content_conflicts(self):
        frozen = self.registry.freeze(manifest())
        self.assertEqual(self.registry.freeze(manifest()), frozen)
        self.run_baseline()
        self.run_baseline()
        changed = manifest()
        changed["authorship"] += " Changed"
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.registry.freeze(changed)
        outputs = self.registry.run("baseline")["outputs"]
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.registry.record_run("baseline", self.key, SYSTEM, outputs)

    def test_split_lock_across_dataset_names_versions_and_amendments(self):
        for index in (0, 1, 2, 3):
            changed = manifest()
            changed["dataset_id"] = "another-study"
            changed["version"] = 2
            changed["cases"] = [changed["cases"][index]]
            changed["cases"][0]["split"] = "train" if index else "test"
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "splits"):
                self.registry.freeze(changed)

    def test_source_version_hash_conflict_and_failed_freeze_rolls_back_all_rows(self):
        changed = manifest()
        changed["version"] = 2
        changed["cases"] = [deepcopy(changed["cases"][0]), deepcopy(changed["cases"][0])]
        changed["cases"][0].update(case_id="NEW", source_id="NEW-SOURCE")
        changed["cases"][1]["case_id"] = "CHANGED"
        changed["cases"][1]["bundle_json"] += " "
        import hashlib
        changed["cases"][1]["source_sha256"] = hashlib.sha256(changed["cases"][1]["bundle_json"].encode()).hexdigest()
        count = self.registry.db.execute("SELECT count(*) FROM records").fetchone()[0]
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.registry.freeze(changed)
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM records").fetchone()[0], count)
        self.assertIsNone(self.registry.db.execute("SELECT 1 FROM splits WHERE identity='source:NEW-SOURCE'").fetchone())

    def test_training_requires_explicit_eligibility_and_excludes_held_out_rows(self):
        self.reviewed_baseline()
        self.assertEqual(self.registry.training_examples("baseline")["examples"], [])
        eligible = manifest()
        eligible["version"] = 2
        eligible["cases"][0]["training_eligible"] = True
        key = self.registry.freeze(eligible)["dataset"]
        self.registry.baseline("eligible", key, "a" * 40)
        run = self.registry.run("eligible")
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.registry.training_examples("eligible")
        self.registry.review(self.review_for(run, "LAB-TRAIN-A"))
        examples = self.registry.training_examples("eligible")["examples"]
        self.assertEqual([e["case_id"] for e in examples], ["LAB-TRAIN-A"])
        eligible["version"] = 3
        eligible["cases"][2]["training_eligible"] = True
        with self.assertRaisesRegex(ValueError, "Held-out"):
            self.registry.freeze(eligible)

    def test_review_must_bind_exact_output_patient_specimen_hash_and_version(self):
        run = self.run_baseline()
        review = self.review_for(run, "LAB-TRAIN-A")
        for field, value in (("subject_reference", "Patient/OTHER"), ("specimen_reference", "Specimen/OTHER"),
                             ("source_sha256", "b" * 64), ("source_version", 2), ("reference", "Observation/OTHER")):
            changed = deepcopy(review)
            changed["corrected_observations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.registry.review(changed)
        review["output_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "different output"):
            self.registry.review(review)

    def test_missing_reference_and_wrong_dataset_never_produce_scores(self):
        self.run_baseline()
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.registry.score("baseline", "baseline")
        changed = manifest()
        changed["version"] = 2
        key = self.registry.freeze(changed)["dataset"]
        self.registry.baseline("other", key, "a" * 40)
        with self.assertRaisesRegex(ValueError, "same frozen dataset"):
            self.registry.score("other", "baseline")
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM records WHERE kind='score'").fetchone()[0], 0)

    def test_unassessable_is_not_silently_scored_as_correct(self):
        run = self.run_baseline()
        for case_id in run["outputs"]:
            self.registry.review(self.review_for(run, case_id, decision="unassessable"))
        report = self.registry.score("baseline", "baseline")
        self.assertEqual(sum(g["unassessable_cases"] for g in report["by_split"].values()), 4)
        self.assertEqual(sum(g["assessed_cases"] for g in report["by_split"].values()), 0)
        self.assertEqual(sum(g["field_opportunities"] for g in report["by_split"].values()), 0)

    def test_database_update_delete_and_foreign_database_are_rejected(self):
        for sql in ("UPDATE records SET sha256='x'", "DELETE FROM records", "DELETE FROM splits"):
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                self.registry.db.execute(sql)
        foreign = Path(self.tmp.name) / "application.sqlite"
        with sqlite3.connect(foreign) as db:
            db.execute("CREATE TABLE patient_data (id TEXT)")
        before = foreign.read_bytes()
        with self.assertRaisesRegex(ValueError, "Not a supported"):
            LaboratoryEvaluationRegistry(foreign)
        self.assertEqual(foreign.read_bytes(), before)

    def test_concurrent_conflicting_split_freezes_have_one_winner(self):
        fresh = Path(self.tmp.name) / "concurrent.sqlite"
        def freeze(split):
            m = manifest()
            m["dataset_id"] = split
            m["cases"] = [m["cases"][0]]
            m["cases"][0]["split"] = split
            try:
                with LaboratoryEvaluationRegistry(fresh) as registry:
                    registry.freeze(m)
                return "accepted"
            except ValueError:
                return "rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(freeze, ("train", "test"))), ["accepted", "rejected"])

    def test_strict_json_and_source_hash_boundary(self):
        for raw in (b'{"a":1,"a":1}', b'{"a":NaN}', b'{"a":1e999}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_json(raw)
        for field, value in (("synthetic", False), ("version", True)):
            changed = manifest()
            changed[field] = value
            with self.assertRaises(ValueError):
                self.registry.freeze(changed)
        changed = manifest()
        changed["cases"][0]["source_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.registry.freeze(changed)

    def test_duplicate_source_under_another_case_does_not_inflate_denominator(self):
        changed = manifest()
        changed["version"] = 2
        duplicate = deepcopy(changed["cases"][0])
        duplicate["case_id"] = "ALIAS"
        changed["cases"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate evaluation"):
            self.registry.freeze(changed)

    def test_partial_outputs_and_false_baseline_receipts_are_rejected(self):
        outputs = {c["case_id"]: baseline_output(c) for c in manifest()["cases"]}
        with self.assertRaises(ValueError):
            self.registry.record_run("false-baseline", self.key, SYSTEM, outputs, execution="deterministic_parser")
        outputs.pop("LAB-TEST-C-V1")
        with self.assertRaises(ValueError):
            self.registry.record_run("partial", self.key, SYSTEM, outputs)

    def test_reference_anchor_resolution_does_not_depend_on_candidate_extractor(self):
        outputs = {c["case_id"]: {"status": "extracted", "observations": [], "reason": None}
                   for c in manifest()["cases"]}
        self.registry.record_run("omitting-parser", self.key, SYSTEM, outputs)
        run = self.registry.run("omitting-parser")
        with patch("oi_api.laboratory_evaluation.baseline_output", side_effect=AssertionError("Do not use parser as gold")):
            for case_id in outputs:
                self.registry.review(self.review_for(run, case_id))
        report = self.registry.score("omitting-parser", "omitting-parser")
        self.assertEqual(sum(g["omissions"] for g in report["by_split"].values()), 4)

    def test_cli_persists_across_processes_and_reports_error_without_mutation(self):
        db = Path(self.tmp.name) / "cli.sqlite"
        cmd = [sys.executable, "-m", "oi_api.laboratory_evaluation", "--registry", str(db)]
        result = subprocess.run(cmd + ["freeze", "--input", str(FIXTURES / "dataset.json")],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["dataset"], self.key)
        subprocess.run(cmd + ["baseline", "--dataset", self.key, "--run", "cli", "--software-commit", "a" * 40],
                       capture_output=True, text=True, check=True)
        result = subprocess.run(cmd + ["show-run", "--run", "cli"], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["execution"], "deterministic_parser")
        before = db.read_bytes()
        result = subprocess.run(cmd + ["score", "--candidate", "cli", "--reference", "missing"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
