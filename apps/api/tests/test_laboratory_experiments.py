"""Actual local workers, immutable experiments and held-out isolation."""
from contextlib import contextmanager
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

    def test_lock_wait_exhaustion_prevents_a_trial_claim(self):
        self.service.plan(self.spec())
        clock, transactions = [0], [0]
        original = self.registry._transaction
        @contextmanager
        def delayed_lock():
            with original():
                transactions[0] += 1
                if transactions[0] == 2:
                    clock[0] = 11
                yield
        with patch.object(self.registry, "_transaction", delayed_lock), \
                patch("oi_api.laboratory_experiments.time.monotonic", side_effect=lambda: clock[0]), \
                patch("oi_api.laboratory_experiments.run_worker") as launch:
            receipt = self.service.execute("search")
        launch.assert_not_called()
        self.assertEqual([t["status"] for t in receipt["trials"]], ["budget_exhausted"] * 2)
        self.assertEqual(self.registry.db.execute(
            "SELECT count(*) FROM records WHERE kind='experiment-trial-start'").fetchone()[0], 0)

    def test_trial_preparation_exhaustion_does_not_launch_worker(self):
        self.service.plan(self.spec())
        clock = [0]
        original = self.registry._get
        def delayed_recipe(kind, key):
            result = original(kind, key)
            if kind == "recipe":
                clock[0] = 11
            return result
        with patch.object(self.registry, "_get", side_effect=delayed_recipe), \
                patch("oi_api.laboratory_experiments.time.monotonic", side_effect=lambda: clock[0]), \
                patch("oi_api.laboratory_experiments.run_worker") as launch:
            receipt = self.service.execute("search")
        launch.assert_not_called()
        self.assertEqual([t["status"] for t in receipt["trials"]], ["budget_exhausted"] * 2)
        self.assertEqual(receipt["trials"][0]["failure_reason"], "worker_budget_exhausted_before_launch")

    def test_preparation_time_reduces_worker_timeout(self):
        spec = self.spec()
        spec["recipes"] = [self.keys[1]]
        self.service.plan(spec)
        clock = [0]
        original = self.registry._get
        def delayed_recipe(kind, key):
            result = original(kind, key)
            if kind == "recipe":
                clock[0] = 2
            return result
        with patch.object(self.registry, "_get", side_effect=delayed_recipe), \
                patch("oi_api.laboratory_experiments.time.monotonic", side_effect=lambda: clock[0]), \
                patch("oi_api.laboratory_experiments.run_worker", wraps=run_worker) as launch:
            receipt = self.service.execute("search")
        self.assertEqual(launch.call_args.args[1], 1)
        self.assertEqual(receipt["trials"][0]["status"], "completed")

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

    def test_cancel_before_execution_survives_reopen_and_launches_nothing(self):
        self.service.plan(self.spec())
        request = self.service.cancel("search", "Stop this experiment")
        with LaboratoryEvaluationRegistry(self.path) as reopened:
            service = LaboratoryExperiments(reopened)
            self.assertEqual(service.inspect("search")["cancellation"], request)
            with patch("oi_api.laboratory_experiments.run_worker", side_effect=AssertionError("No worker permitted")):
                receipt = service.execute("search")
                self.assertEqual(service.execute("search"), receipt)
            self.assertEqual(receipt["status"], "cancelled")
            self.assertIsNone(receipt["selected_recipe"])
            self.assertEqual([t["status"] for t in receipt["trials"]], ["cancelled", "cancelled"])
            self.assertEqual(service.cancel("search", "Stop this experiment"), request)
        self.assertEqual(self.registry.db.execute(
            "SELECT count(*) FROM records WHERE kind='experiment-trial-start'").fetchone()[0], 0)

    def test_cancel_during_worker_preserves_trial_and_prevents_next_claim(self):
        self.service.plan(self.spec())
        calls = []
        def stop_during_worker(payload, timeout):
            calls.append(payload["technique"])
            # A separate connection models a concurrent CLI stop request.
            with LaboratoryEvaluationRegistry(self.path) as reopened:
                LaboratoryExperiments(reopened).cancel("search", "Stop after current worker")
            return run_worker(payload, timeout)
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=stop_during_worker):
            receipt = self.service.execute("search")
        self.assertEqual(calls, ["exact_source_memory"])
        self.assertEqual([t["status"] for t in receipt["trials"]], ["completed", "cancelled"])
        self.assertIsNone(receipt["selected_recipe"])
        trial = receipt["trials"][0]
        self.assertEqual(fingerprint(self.registry._get("checkpoint", trial["run_id"])), trial["checkpoint_sha256"])

    def test_cancel_during_last_worker_suppresses_selection(self):
        spec = self.spec()
        spec["recipes"] = [self.keys[1]]
        self.service.plan(spec)
        def stop(payload, timeout):
            result = run_worker(payload, timeout)
            with LaboratoryEvaluationRegistry(self.path) as reopened:
                LaboratoryExperiments(reopened).cancel("search", "Do not select")
            return result
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=stop):
            receipt = self.service.execute("search")
        self.assertEqual(receipt["trials"][0]["status"], "completed")
        self.assertEqual(receipt["status"], "cancelled")
        self.assertIsNone(receipt["selected_recipe"])

    def test_cancellation_validation_and_cli(self):
        with self.assertRaises(ValueError):
            self.service.cancel("missing", "Stop")
        self.service.plan(self.spec())
        for reason in (None, " ", "x" * 513):
            with self.assertRaises(ValueError):
                self.service.cancel("search", reason)
        cmd = [sys.executable, "-m", "oi_api.laboratory_experiments", "--registry", str(self.path),
               "cancel", "--experiment", "search", "--reason", "CLI stop"]
        first = subprocess.run(cmd, capture_output=True, check=True)
        second = subprocess.run(cmd, capture_output=True, check=True)
        self.assertEqual(first.stdout, second.stdout)
        with self.assertRaisesRegex(ValueError, "different immutable reason"):
            self.service.cancel("search", "Changed reason")
        self.service.plan(self.spec("finished"))
        receipt = self.service.execute("finished")
        with self.assertRaisesRegex(ValueError, "Finished experiment"):
            self.service.cancel("finished", "Too late")
        self.assertEqual(self.service.execute("finished"), receipt)

    def test_lineage_is_read_only_complete_and_reopenable(self):
        self.service.plan(self.spec())
        receipt = self.service.execute("search")
        before = self.path.read_bytes()
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=AssertionError("No execution")), \
                patch.object(self.registry, "score", side_effect=AssertionError("No rescoring")):
            graph = self.service.lineage("search")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(graph["integrity_checked"])
        nodes = {(n["kind"], n["id"]) for n in graph["nodes"]}
        for trial in receipt["trials"]:
            self.assertIn(("checkpoint", trial["run_id"]), nodes)
            self.assertIn(("score", trial["score_sha256"]), nodes)
        self.assertEqual(len([n for n in graph["nodes"] if n["kind"] == "review" ]), 2)
        self.assertEqual(len(graph["sources"]), len(self.manifest["cases"]))
        self.assertNotIn("bundle_json", json.dumps(graph))
        cmd = [sys.executable, "-m", "oi_api.laboratory_experiments", "--registry", str(self.path),
               "lineage", "--experiment", "search"]
        result = subprocess.run(cmd, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), graph)
        self.assertEqual(self.path.read_bytes(), before)

    def test_lineage_supports_planned_and_cancelled_experiments(self):
        self.service.plan(self.spec())
        self.assertEqual(self.service.lineage("search")["status"], "planned")
        self.service.cancel("search", "Stop")
        self.service.execute("search")
        graph = self.service.lineage("search")
        kinds = [n["kind"] for n in graph["nodes"]]
        self.assertIn("experiment-cancel", kinds)
        self.assertNotIn("checkpoint", kinds)
        self.assertEqual(kinds.count("experiment-trial"), 2)

    def test_lineage_rejects_missing_and_inconsistent_artifacts(self):
        self.service.plan(self.spec())
        self.service.execute("search")
        original = self.registry._get
        for defect in ("missing-score", "changed-checkpoint", "changed-trial"):
            def damaged(kind, key):
                result = original(kind, key)
                if defect == "missing-score" and kind == "score":
                    raise ValueError("Unknown evaluation record")
                if defect == "changed-checkpoint" and kind == "checkpoint":
                    result["training_sha256"] = "0" * 64
                if defect == "changed-trial" and kind == "experiment-trial":
                    result["recipe_sha256"] = "0" * 64
                return result
            with self.subTest(defect=defect), patch.object(self.registry, "_get", side_effect=damaged):
                with self.assertRaises(ValueError):
                    self.service.lineage("search")

    def comparison_variant(self, reviewer="fixture-author"):
        manifest = deepcopy(self.manifest)
        manifest["version"] = 3
        manifest["cases"][0]["training_eligible"] = False
        dataset = self.registry.freeze(manifest)["dataset"]
        self.registry.baseline("variant-reference", dataset, "a" * 40)
        case_id = manifest["cases"][1]["case_id"]
        review = self.registry._get("review", "reference:" + case_id)
        review.update(run_id="variant-reference", reviewer_id=reviewer)
        self.registry.review(review)
        spec = self.spec("variant")
        spec.update(dataset=dataset, reference_run="variant-reference", recipes=[self.keys[1]], max_training_examples=0)
        self.service.plan(spec)
        return self.service.execute("variant")

    def test_compare_training_variants_preserves_ties_and_is_read_only(self):
        self.service.plan(self.spec())
        self.service.execute("search")
        self.comparison_variant()
        before = self.path.read_bytes()
        report = self.service.compare({"experiments": ["search", "variant"]})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([row["rank"] for row in report["rows"]], [1, 1, 2])
        self.assertNotEqual(report["inputs"][0]["training_sha256"], report["inputs"][1]["training_sha256"])
        self.assertFalse(report["test_scored"])
        self.assertFalse(report["promotion_authorized"])
        self.assertEqual(self.service.compare({"experiments": ["variant", "search"]}), report)
        request = Path(self.tmp.name) / "compare.json"
        request.write_text(json.dumps({"experiments": ["search", "variant"]}))
        cmd = [sys.executable, "-m", "oi_api.laboratory_experiments", "--registry", str(self.path),
               "compare", "--input", str(request)]
        result = subprocess.run(cmd, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), report)

    def test_compare_rejects_changed_reference_judgment(self):
        self.service.plan(self.spec())
        self.service.execute("search")
        self.comparison_variant(reviewer="different-adjudicator")
        with self.assertRaisesRegex(ValueError, "Incomparable"):
            self.service.compare({"experiments": ["search", "variant"]})

    def test_compare_rejects_unfinished_cancelled_or_duplicate_inputs(self):
        self.service.plan(self.spec())
        self.comparison_variant()
        with self.assertRaisesRegex(ValueError, "finished"):
            self.service.compare({"experiments": ["search", "variant"]})
        self.service.cancel("search", "Stop")
        self.service.execute("search")
        with self.assertRaisesRegex(ValueError, "Cancelled"):
            self.service.compare({"experiments": ["search", "variant"]})
        for values in (["variant"], ["variant", "variant"], "variant", [None, "variant"]):
            with self.assertRaises(ValueError):
                self.service.compare({"experiments": values})

    def test_compare_keeps_failed_candidates_visible_and_unranked(self):
        self.service.plan(self.spec())
        with patch("oi_api.laboratory_experiments.run_worker", side_effect=ValueError("Worker failed")):
            self.service.execute("search")
        self.comparison_variant()
        report = self.service.compare({"experiments": ["search", "variant"]})
        self.assertEqual([row["rank"] for row in report["rows"]], [1, None, None])
        self.assertEqual([row["status"] for row in report["rows"]], ["completed", "failed", "failed"])

    def test_failed_artifact_commit_rolls_back_candidate_and_preserves_failure(self):
        original = self.registry._put
        for kind in ("run", "score", "checkpoint", "experiment-trial"):
            experiment_id = "failure-" + kind
            self.service.plan(self.spec(experiment_id))
            def fail_write(record_kind, key, value):
                if record_kind == kind and (kind != "experiment-trial" or value["status"] == "completed"):
                    raise OSError("Injected artifact write failure")
                return original(record_kind, key, value)
            with self.subTest(kind=kind), patch.object(self.registry, "_put", side_effect=fail_write):
                receipt = self.service.execute(experiment_id)
            self.assertTrue(all(t["status"] == "failed" for t in receipt["trials"]))
            self.assertTrue(all(t["run_id"] is None for t in receipt["trials"]))
            for index in range(2):
                key = "trial-" + fingerprint([experiment_id, index])[:48]
                for artifact in ("run", "checkpoint"):
                    self.assertIsNone(self.registry.db.execute(
                        "SELECT 1 FROM records WHERE kind=? AND id=?", (artifact, key)).fetchone())
            self.assertEqual(self.registry.db.execute("SELECT count(*) FROM records WHERE kind='score'").fetchone()[0], 0)
            with LaboratoryEvaluationRegistry(self.path) as reopened:
                service = LaboratoryExperiments(reopened)
                self.assertEqual(service.execute(experiment_id), receipt)
                self.assertTrue(service.lineage(experiment_id)["integrity_checked"])

    def test_interrupt_during_artifact_commit_rolls_back_without_false_completion(self):
        self.service.plan(self.spec())
        original = self.registry._put
        def interrupt(kind, key, value):
            if kind == "checkpoint":
                raise KeyboardInterrupt()
            return original(kind, key, value)
        with patch.object(self.registry, "_put", side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            self.service.execute("search")
        self.assertFalse(self.registry.db.in_transaction)
        with LaboratoryEvaluationRegistry(self.path) as reopened:
            service = LaboratoryExperiments(reopened)
            self.assertEqual(service.inspect("search")["status"], "interrupted_or_running")
            kinds = [n["kind"] for n in service.lineage("search")["nodes"]]
            self.assertNotIn("checkpoint", kinds)
            self.assertNotIn("score", kinds)
            self.assertNotIn("experiment-trial", kinds)
            self.assertEqual(kinds.count("run"), 1)  # Only the reference exists.
            with self.assertRaisesRegex(ValueError, "already claimed"):
                service.execute("search")

    def test_candidate_artifacts_are_invisible_until_trial_commit(self):
        self.service.plan(self.spec())
        original = self.registry._put
        checks = []
        reader = LaboratoryEvaluationRegistry(self.path)
        self.addCleanup(reader.close)
        def observe(record_kind, key, value):
            if record_kind == "checkpoint":
                checks.append(reader.db.execute("SELECT 1 FROM records WHERE kind='run' AND id=?", (key,)).fetchone())
            return original(record_kind, key, value)
        with patch.object(self.registry, "_put", side_effect=observe):
            receipt = self.service.execute("search")
        self.assertEqual(checks, [None, None])
        self.assertTrue(all(t["status"] == "completed" for t in receipt["trials"]))
        self.assertTrue(self.service.lineage("search")["integrity_checked"])

    def test_cli_executes_and_reopens_existing_plan(self):
        self.service.plan(self.spec())
        cmd = [sys.executable, "-m", "oi_api.laboratory_experiments", "--registry", str(self.path)]
        first = subprocess.run(cmd + ["execute", "--experiment", "search"], capture_output=True, check=True)
        second = subprocess.run(cmd + ["execute", "--experiment", "search"], capture_output=True, check=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["selected_recipe"], "parser_baseline:1")


if __name__ == "__main__":
    unittest.main()
