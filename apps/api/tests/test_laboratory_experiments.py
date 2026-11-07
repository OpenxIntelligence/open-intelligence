"""Actual local workers, immutable experiments and held-out isolation."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from oi_api.laboratory_evaluation import LaboratoryEvaluationRegistry, fingerprint, read_json
from oi_api.laboratory_experiments import LaboratoryExperiments, TECHNIQUES, run_worker, worker

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "validation/laboratory-evaluation"


class LaboratoryExperimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "experiments.sqlite"
        self.registry = LaboratoryEvaluationRegistry(self.path)
        self.addCleanup(self.registry.close)
        self.service = LaboratoryExperiments(self.registry)
        self.manifest = read_json((FIXTURES / "dataset.json").read_bytes())
        self.manifest["version"] = 2
        self.manifest["cases"][0]["training_eligible"] = True
        self.dataset = self.registry.freeze(self.manifest)["dataset"]
        self.registry.baseline("reference", self.dataset, "a" * 40)
        run = self.registry.run("reference")
        gold = read_json((FIXTURES / "reference.json").read_bytes())["observations"]
        for case in self.manifest["cases"]:
            # Deliberately leave test cases unreviewed. The search must never
            # require or read their labels, and cannot score them successfully.
            if case["split"] == "test":
                continue
            case_id = case["case_id"]
            self.registry.review({"run_id": "reference", "case_id": case_id,
                                  "reviewer_id": "fixture-author", "independence_declared": False,
                                  "decision": "correct", "output_sha256": fingerprint(run["outputs"][case_id]),
                                  "corrected_observations": gold[case_id], "reason": "Authored synthetic fixture",
                                  "correction_seconds": 0})
        self.keys = []
        for technique in ("exact_source_memory", "parser_baseline"):
            self.keys.append(self.service.recipe({"recipe_id": technique, "version": 1,
                                                  "technique": technique, "model_identity": TECHNIQUES[technique],
                                                  "parameters": {}})["recipe"])

    def spec(self, experiment_id="search"):
        return {"experiment_id": experiment_id, "dataset": self.dataset, "reference_run": "reference",
                "recipes": self.keys, "software_commit": "a" * 40, "max_total_wall_seconds": 10,
                "max_trial_wall_seconds": 3, "max_training_examples": 1}

    def test_real_fit_checkpoint_validation_selection_and_restart(self):
        self.service.plan(self.spec())
        receipt = self.service.execute("search")
        self.assertEqual(receipt["selected_recipe"], "parser_baseline:1")
        trained, baseline = receipt["trials"]
        self.assertEqual(trained["status"], "completed")
        self.assertTrue(trained["fit_performed"])
        self.assertEqual(trained["fitted_examples"], 1)
        self.assertEqual(trained["validation"]["abstentions"], 1)
        self.assertEqual(baseline["validation"]["field_errors"], 0)
        self.assertGreater(trained["cpu_seconds"], 0)
        self.assertGreater(trained["peak_rss_kib"], 0)
        self.assertIsNone(trained["total_cost_usd"])
        self.assertFalse(receipt["neural_training_performed"])
        for trial in receipt["trials"]:
            run = self.registry.run(trial["run_id"])
            self.assertEqual(run["evaluated_splits"], ["validation"])
            self.assertEqual(set(run["outputs"]), {"LAB-VALIDATION-B"})
            self.assertEqual(fingerprint(self.registry._get("checkpoint", trial["run_id"])), trial["checkpoint_sha256"])
        checkpoint = self.registry._get("checkpoint", trained["run_id"])
        self.assertEqual(set(checkpoint["artifact"]["entries"]), {self.manifest["cases"][0]["source_sha256"]})
        with LaboratoryEvaluationRegistry(self.path) as reopened:
            service = LaboratoryExperiments(reopened)
            self.assertEqual(service.inspect("search")["status"], "finished")
            with patch("oi_api.laboratory_experiments.run_worker", side_effect=AssertionError("Do not execute retry")):
                self.assertEqual(service.execute("search"), receipt)

    def test_worker_receives_only_eligible_train_and_validation_without_gold(self):
        self.service.plan(self.spec())
        seen = []
        def capture(payload, timeout):
            seen.append(deepcopy(payload))
            return run_worker(payload, timeout)
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=capture):
            self.service.execute("search")
        self.assertEqual([e["case_id"] for e in seen[0]["training"]], ["LAB-TRAIN-A"])
        self.assertEqual(seen[1]["training"], [])
        for payload in seen:
            self.assertEqual([c["case_id"] for c in payload["validation"]], ["LAB-VALIDATION-B"])
            text = json.dumps(payload)
            self.assertNotIn("LAB-TEST", text)
            self.assertNotIn("corrected_observations", text)
            self.assertNotIn("reference_run", text)

    def test_unsupported_method_model_parameters_and_changed_recipe_rejected(self):
        for change in ({"technique": "sft"}, {"model_identity": "remote-model"}, {"parameters": {"command": "anything"}}):
            recipe = {"recipe_id": "new", "version": 1, "technique": "parser_baseline",
                      "model_identity": TECHNIQUES["parser_baseline"], "parameters": {}}
            recipe.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.service.recipe(recipe)
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.service.recipe({"recipe_id": "parser_baseline", "version": 1,
                                 "technique": "exact_source_memory", "model_identity": TECHNIQUES["exact_source_memory"],
                                 "parameters": {}})

    def test_frozen_plan_budgets_and_inputs_cannot_be_replaced(self):
        self.service.plan(self.spec())
        changed = self.spec()
        changed["max_training_examples"] = 2
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.service.plan(changed)
        for field, value in (("max_training_examples", 0), ("max_total_wall_seconds", float('nan')),
                             ("max_trial_wall_seconds", 11), ("recipes", self.keys * 2)):
            changed = self.spec("invalid")
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.service.plan(changed)

    def test_no_eligible_training_is_not_misrepresented_as_fit(self):
        m = read_json((FIXTURES / "dataset.json").read_bytes())
        dataset = self.registry.freeze(m)["dataset"]
        self.registry.baseline("ineligible", dataset, "a" * 40)
        run = self.registry.run("ineligible")
        self.registry.review({"run_id": "ineligible", "case_id": "LAB-VALIDATION-B", "reviewer_id": "fixture",
                              "independence_declared": False, "decision": "accept", "corrected_observations": None,
                              "output_sha256": fingerprint(run["outputs"]["LAB-VALIDATION-B"]),
                              "reason": "Fixture acceptance", "correction_seconds": 0})
        spec = self.spec()
        spec.update(dataset=dataset, reference_run="ineligible")
        with self.assertRaisesRegex(ValueError, "eligible reviewed"):
            self.service.plan(spec)

    def test_actual_process_timeout_is_recorded_and_not_retried(self):
        self.service.plan(self.spec())
        # Exercise the real subprocess timeout without adding a sleep/command
        # adapter to the production allowlist.
        with patch("oi_api.laboratory_experiments._worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(2)"]):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_worker({}, 0.02)
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=subprocess.TimeoutExpired("worker", 3)):
            receipt = self.service.execute("search")
        self.assertEqual([t["status"] for t in receipt["trials"]], ["timed_out", "timed_out"])
        self.assertIsNone(receipt["selected_recipe"])
        self.assertTrue(all(t["checkpoint_sha256"] is None for t in receipt["trials"]))
        self.assertEqual(self.service.execute("search"), receipt)

    def test_malformed_worker_result_and_failure_never_get_a_checkpoint(self):
        self.service.plan(self.spec())
        with patch("oi_api.laboratory_experiments.run_worker", return_value={"outputs": {}}):
            receipt = self.service.execute("search")
        self.assertTrue(all(t["status"] == "failed" for t in receipt["trials"]))
        self.assertIsNone(receipt["selected_recipe"])

    def test_false_fit_checkpoint_or_resource_receipt_is_rejected(self):
        for number, field, value in ((0, "checkpoint", {"kind": "invented-weights"}),
                                     (1, "cpu_seconds", True), (2, "fitted_examples", 999)):
            experiment_id = "forged-" + str(number)
            self.service.plan(self.spec(experiment_id))
            def forged(payload, timeout):
                result = run_worker(payload, timeout)
                result[field] = value
                return result
            with patch("oi_api.laboratory_experiments.run_worker", side_effect=forged):
                receipt = self.service.execute(experiment_id)
            self.assertTrue(all(t["status"] == "failed" and t["checkpoint_sha256"] is None
                                and t["run_id"] is None for t in receipt["trials"]))

    def test_code_drift_and_existing_claim_prevent_reexecution(self):
        self.service.plan(self.spec())
        with patch("oi_api.laboratory_experiments.source_identity", return_value={}):
            with self.assertRaisesRegex(ValueError, "source changed"):
                self.service.execute("search")
        with self.registry._transaction():
            self.registry._put("experiment-start", "search", {"prior_crashed_process": True})
        self.assertEqual(self.service.inspect("search")["status"], "interrupted_or_running")
        with self.assertRaisesRegex(ValueError, "already claimed"):
            self.service.execute("search")

    def test_concurrent_claims_execute_the_candidate_set_once(self):
        self.service.plan(self.spec())
        launches = []
        lock = threading.Lock()
        def launch(payload, timeout):
            with lock:
                launches.append(payload["technique"])
            time.sleep(0.03)
            return run_worker(payload, timeout)
        def execute(_):
            with LaboratoryEvaluationRegistry(self.path) as registry:
                try:
                    return LaboratoryExperiments(registry).execute("search")["selected_recipe"]
                except ValueError as exc:
                    return str(exc)
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=launch):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(execute, (1, 2)))
        self.assertIn("parser_baseline:1", results)
        self.assertEqual(launches, ["exact_source_memory", "parser_baseline"])

    def test_zero_opportunity_reference_cannot_select_a_candidate(self):
        # A new reference run can hold a different immutable review version.
        self.registry.baseline("unassessable", self.dataset, "a" * 40)
        run = self.registry.run("unassessable")
        for case_id in ("LAB-TRAIN-A", "LAB-VALIDATION-B"):
            self.registry.review({"run_id": "unassessable", "case_id": case_id, "reviewer_id": "fixture",
                                  "independence_declared": False, "decision": "unassessable",
                                  "corrected_observations": None, "reason": "Cannot assess",
                                  "output_sha256": fingerprint(run["outputs"][case_id]), "correction_seconds": 0})
        spec = self.spec()
        spec.update(reference_run="unassessable", recipes=[self.keys[1]])
        self.service.plan(spec)
        self.assertIsNone(self.service.execute("search")["selected_recipe"])

    def test_total_budget_prevents_starting_more_trials(self):
        self.service.plan(self.spec())
        with patch("oi_api.laboratory_experiments.time.monotonic", side_effect=[0, 11, 12, 13]):
            receipt = self.service.execute("search")
        self.assertEqual([t["status"] for t in receipt["trials"]], ["budget_exhausted", "budget_exhausted"])
        self.assertIsNone(receipt["selected_recipe"])

    def test_worker_rejects_test_inputs_and_train_validation_overlap(self):
        case = self.manifest["cases"][2]
        with self.assertRaisesRegex(ValueError, "non-validation"):
            worker({"technique": "parser_baseline", "training": [], "validation": [case]})
        case = self.manifest["cases"][1]
        with self.assertRaisesRegex(ValueError, "overlap"):
            worker({"technique": "exact_source_memory", "training": [{"source_sha256": case["source_sha256"]}],
                    "validation": [case]})

    def test_cli_executes_and_reopens_existing_plan(self):
        self.service.plan(self.spec())
        cmd = [sys.executable, "-m", "oi_api.laboratory_experiments", "--registry", str(self.path)]
        first = subprocess.run(cmd + ["execute", "--experiment", "search"], capture_output=True, check=True)
        second = subprocess.run(cmd + ["execute", "--experiment", "search"], capture_output=True, check=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["selected_recipe"], "parser_baseline:1")


if __name__ == "__main__":
    unittest.main()
