"""Bounded local experiment execution over the OI-011 evaluation registry.

Two first-party adapters: the existing parser and an exact-source memorization
control fitted only on eligible reviewed training examples. No LLM, remote
model, arbitrary command, deployment, or clinical promotion is supported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time

from .laboratory_evaluation import (
    LaboratoryEvaluationRegistry, MAX_JSON_BYTES, _id, _json, _require, _sha,
    _shape, baseline_output, fingerprint, read_json,
)

TECHNIQUES = {"parser_baseline": "oi.fhir-r4-laboratory-parser/1",
              "exact_source_memory": "oi.exact-source-memory/1"}
OBJECTIVE = ["field_errors", "unsupported_observations", "execution_errors", "abstentions"]


def source_identity():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("laboratory_experiments.py", "laboratory_evaluation.py", "laboratory_fhir_r4.py")}


def _seconds(value, maximum):
    _require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum,
             "Invalid wall-time budget")


def worker(payload):
    """Allowlisted local adapters receive no test cases or validation references."""
    _shape(payload, ("technique", "training", "validation"))
    technique = payload["technique"]
    _require(technique in TECHNIQUES, "Unsupported technique")
    _require(type(payload["validation"]) is list and 0 < len(payload["validation"]) <= 100,
             "Validation inputs required")
    _require(type(payload["training"]) is list and len(payload["training"]) <= 100,
             "Invalid training inputs")
    _require(all(c["split"] == "validation" for c in payload["validation"]),
             "Worker received a non-validation inference case")
    _require(not ({e["source_sha256"] for e in payload["training"]}
                  & {c["source_sha256"] for c in payload["validation"]}),
             "Training and validation sources overlap")
    memory = {}
    if technique == "exact_source_memory":
        _require(bool(payload["training"]), "Memorization fit requires training examples")
        for example in payload["training"]:
            _require(example["split"] == "train" and example["training_eligible"] is True,
                     "Worker received ineligible training data")
            memory[example["source_sha256"]] = example["observations"]
    else:
        _require(not payload["training"], "Parser baseline must not receive training labels")
    outputs = {}
    for case in payload["validation"]:
        if technique == "parser_baseline":
            outputs[case["case_id"]] = baseline_output(case)
        elif case["source_sha256"] in memory:
            outputs[case["case_id"]] = {"status": "extracted", "reason": None,
                                       "observations": memory[case["source_sha256"]]}
        else:
            outputs[case["case_id"]] = {"status": "abstained", "observations": [],
                                       "reason": "No exact training source match"}
    checkpoint = ({"kind": "exact-source-memory", "version": 1, "entries": memory}
                  if technique == "exact_source_memory" else
                  {"kind": "deterministic-parser", "source_sha256": source_identity()["laboratory_fhir_r4.py"]})
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"outputs": outputs, "checkpoint": checkpoint, "fit_performed": bool(memory),
            "fitted_examples": len(memory), "neural_training_performed": False,
            "source_identity": source_identity(),
            "cpu_seconds": usage.ru_utime + usage.ru_stime,
            "peak_rss_kib": usage.ru_maxrss if sys.platform != "darwin" else usage.ru_maxrss / 1024}


def _worker_command():
    return [sys.executable, "-m", "oi_api.laboratory_experiments", "--worker"]


def _validate_result(result, payload, identity):
    _shape(result, ("outputs", "checkpoint", "fit_performed", "fitted_examples",
                    "neural_training_performed", "cpu_seconds", "peak_rss_kib", "source_identity"))
    _require(result["source_identity"] == identity, "Worker source differs from plan")
    memory_fit = payload["technique"] == "exact_source_memory"
    expected_count = len(payload["training"]) if memory_fit else 0
    _require(type(result["fitted_examples"]) is int and result["fitted_examples"] == expected_count
             and result["fit_performed"] is memory_fit and result["neural_training_performed"] is False,
             "Worker fit receipt differs from recipe inputs")
    for key in ("cpu_seconds", "peak_rss_kib"):
        value = result[key]
        _require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                 "Invalid worker resource measurement")
    expected_checkpoint = ({"kind": "exact-source-memory", "version": 1,
                            "entries": {e["source_sha256"]: e["observations"] for e in payload["training"]}}
                           if memory_fit else {"kind": "deterministic-parser",
                                               "source_sha256": identity["laboratory_fhir_r4.py"]})
    _require(result["checkpoint"] == expected_checkpoint, "Checkpoint does not match fitted inputs")


def run_worker(payload, timeout):
    # Only built-in source code is executed. This is process isolation and time
    # limiting, not a security sandbox for third-party or malicious model code.
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1]),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
    with tempfile.TemporaryDirectory(prefix="oi-lab-trial-") as cwd:
        completed = subprocess.run(_worker_command(), input=_json(payload).encode(),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=cwd, env=env, timeout=timeout, check=False)
    _require(completed.returncode == 0, "Worker exited unsuccessfully")
    return read_json(completed.stdout)


class LaboratoryExperiments:
    def __init__(self, registry: LaboratoryEvaluationRegistry):
        self.registry = registry

    def recipe(self, recipe):
        _shape(recipe, ("recipe_id", "version", "technique", "model_identity", "parameters"))
        _id(recipe["recipe_id"])
        _require(type(recipe["version"]) is int and recipe["version"] > 0, "Invalid recipe version")
        _require(type(recipe["technique"]) is str and recipe["technique"] in TECHNIQUES,
                 "No executable adapter for this technique")
        _require(recipe["model_identity"] == TECHNIQUES[recipe["technique"]], "Model/technique mismatch")
        _require(recipe["parameters"] == {}, "These adapters accept no hyperparameters")
        key = f'{recipe["recipe_id"]}:{recipe["version"]}'
        with self.registry._transaction():
            digest = self.registry._put("recipe", key, recipe)
        return {"recipe": key, "sha256": digest}

    def _inputs(self, dataset, reference_id):
        reference = self.registry.run(reference_id)
        _require(reference["dataset"] == dataset, "Reference/dataset mismatch")
        manifest = self.registry.dataset(dataset)
        validation = [c for c in manifest["cases"] if c["split"] == "validation"]
        _require(bool(validation), "A separate validation split is required")
        reviews = {}
        for case in validation:
            _require(case["case_id"] in reference["outputs"], "Reference has no validation output")
            review = self.registry._get("review", f'{reference_id}:{case["case_id"]}')
            reviews[case["case_id"]] = fingerprint(review)
        training = self.registry.training_examples(reference_id)["examples"]
        for example in training:
            example.update(split="train", training_eligible=True)
        return manifest, reference, validation, training, reviews

    def plan(self, spec):
        _shape(spec, ("experiment_id", "dataset", "reference_run", "recipes", "software_commit",
                      "max_total_wall_seconds", "max_trial_wall_seconds", "max_training_examples"))
        _id(spec["experiment_id"])
        _sha(spec["software_commit"], 40)
        _seconds(spec["max_total_wall_seconds"], 60)
        _seconds(spec["max_trial_wall_seconds"], 10)
        _require(type(spec["max_training_examples"]) is int and 0 <= spec["max_training_examples"] <= 100,
                 "Invalid training example budget")
        _require(type(spec["recipes"]) is list and 0 < len(spec["recipes"]) <= 8
                 and all(type(key) is str for key in spec["recipes"])
                 and len(set(spec["recipes"])) == len(spec["recipes"]), "Invalid recipe search space")
        recipes = [self.registry._get("recipe", key) for key in spec["recipes"]]
        manifest, reference, validation, training, reviews = self._inputs(spec["dataset"], spec["reference_run"])
        _require(len(training) <= spec["max_training_examples"], "Training example budget exceeded")
        if any(r["technique"] == "exact_source_memory" for r in recipes):
            _require(bool(training), "No explicitly eligible reviewed training examples")
        plan = {"spec": spec, "dataset_sha256": fingerprint(manifest),
                "reference_sha256": fingerprint(reference), "validation_reviews": reviews,
                "training_sha256": fingerprint(training),
                "recipes": {k: fingerprint(r) for k, r in zip(spec["recipes"], recipes)},
                "source_identity": source_identity(), "objective": OBJECTIVE,
                "selection_split": "validation", "test_sent_to_worker": False, "test_scored": False,
                "worker_limits": {"cpu_seconds": 5, "address_space_bytes": 256 * 1024 * 1024}}
        with self.registry._transaction():
            digest = self.registry._put("experiment-plan", spec["experiment_id"], plan)
        return {"experiment_id": spec["experiment_id"], "sha256": digest}

    def _cancel_request(self, experiment_id):
        exists = self.registry.db.execute(
            "SELECT 1 FROM records WHERE kind='experiment-cancel' AND id=?", (experiment_id,)).fetchone()
        return self.registry._get("experiment-cancel", experiment_id) if exists else None

    def cancel(self, experiment_id, reason):
        """Stop future trial claims; an already claimed worker retains its timeout."""
        _require(type(reason) is str and 0 < len(reason.strip()) <= 512, "Cancellation reason required (1-512 characters)")
        with self.registry._transaction():
            plan = self.registry._get("experiment-plan", experiment_id)
            request = {"experiment_id": experiment_id, "plan_sha256": fingerprint(plan), "reason": reason}
            prior = self._cancel_request(experiment_id)
            if prior is not None:
                _require(prior == request, "Cancellation already has a different immutable reason")
                return prior
            _require(not self.registry.db.execute(
                "SELECT 1 FROM records WHERE kind='experiment-finish' AND id=?", (experiment_id,)).fetchone(),
                "Finished experiment cannot be cancelled")
            self.registry._put("experiment-cancel", experiment_id, request)
        return request

    def inspect(self, experiment_id):
        plan = self.registry._get("experiment-plan", experiment_id)
        for kind, status in (("experiment-finish", "finished"), ("experiment-start", "interrupted_or_running")):
            if self.registry.db.execute("SELECT 1 FROM records WHERE kind=? AND id=?", (kind, experiment_id)).fetchone():
                return {"status": status, "plan": plan, "record": self.registry._get(kind, experiment_id),
                        "cancellation": self._cancel_request(experiment_id)}
        return {"status": "planned", "plan": plan, "cancellation": self._cancel_request(experiment_id)}

    def execute(self, experiment_id):
        state = self.inspect(experiment_id)
        if state["status"] == "finished":
            return state["record"]
        _require(state["status"] == "planned", "Experiment already claimed; inspect before starting a new experiment")
        plan, registry = state["plan"], self.registry
        spec = plan["spec"]
        _require(plan["source_identity"] == source_identity(), "Executor source changed since plan freeze")
        manifest, reference, validation, training, reviews = self._inputs(spec["dataset"], spec["reference_run"])
        _require(fingerprint(manifest) == plan["dataset_sha256"]
                 and fingerprint(reference) == plan["reference_sha256"]
                 and fingerprint(training) == plan["training_sha256"]
                 and reviews == plan["validation_reviews"], "Frozen experiment inputs changed")
        with registry._transaction():
            # Unlike ordinary idempotent record writes, a start is a unique claim.
            _require(not registry.db.execute("SELECT 1 FROM records WHERE kind='experiment-start' AND id=?",
                                             (experiment_id,)).fetchone(), "Experiment already claimed")
            registry._put("experiment-start", experiment_id,
                          {"plan_sha256": fingerprint(plan), "pid": os.getpid(), "started_unix": time.time()})
        started = time.monotonic()
        trials = []
        for index, key in enumerate(spec["recipes"]):
            trial_key = "trial-" + fingerprint([experiment_id, index])[:48]
            remaining = spec["max_total_wall_seconds"] - (time.monotonic() - started)
            trial = {"recipe": key, "recipe_sha256": plan["recipes"][key], "status": "budget_exhausted",
                     "run_id": None, "checkpoint_sha256": None, "score_sha256": None,
                     "cpu_seconds": None, "peak_rss_kib": None, "wall_seconds": 0,
                     "external_charge_usd": 0, "total_cost_usd": None, "fit_performed": False,
                     "neural_training_performed": False, "failure_reason": None}
            # Serialize each launch claim against cancellation on other connections.
            with registry._transaction():
                cancelled = self._cancel_request(experiment_id) is not None
                if not cancelled and remaining > 0:
                    registry._put("experiment-trial-start", trial_key,
                                  {"experiment_id": experiment_id, "recipe": key, "plan_sha256": fingerprint(plan)})
            if cancelled:
                trial["status"] = "cancelled"
                trial["failure_reason"] = "experiment_cancel_requested"
            if not cancelled and remaining > 0:
                before = time.monotonic()
                try:
                    recipe = registry._get("recipe", key)
                    _require(fingerprint(recipe) == plan["recipes"][key], "Recipe changed")
                    payload = {"technique": recipe["technique"], "validation": validation,
                               "training": training if recipe["technique"] == "exact_source_memory" else []}
                    result = run_worker(payload, min(remaining, spec["max_trial_wall_seconds"]))
                    _validate_result(result, payload, plan["source_identity"])
                    # No weight-execution claim is inferred from supplied output
                    # registration. The separate trial proves this adapter call.
                    registry.record_run(trial_key, spec["dataset"],
                                        {"system_id": recipe["technique"], "system_version": str(recipe["version"]),
                                         "software_commit": spec["software_commit"]}, result["outputs"],
                                        evaluated_splits=["validation"])
                    score = registry.score(trial_key, spec["reference_run"])
                    checkpoint = {"recipe_sha256": plan["recipes"][key], "training_sha256": plan["training_sha256"],
                                  "source_identity": plan["source_identity"], "artifact": result["checkpoint"]}
                    with registry._transaction():
                        checkpoint_sha = registry._put("checkpoint", trial_key, checkpoint)
                    trial.update(status="completed", run_id=trial_key, checkpoint_sha256=checkpoint_sha,
                                 score_sha256=fingerprint(score), cpu_seconds=result["cpu_seconds"],
                                 peak_rss_kib=result["peak_rss_kib"], fit_performed=result["fit_performed"],
                                 fitted_examples=result["fitted_examples"], validation=score["by_split"]["validation"])
                except subprocess.TimeoutExpired:
                    trial["status"] = "timed_out"
                    trial["failure_reason"] = "worker_wall_timeout"
                except (ValueError, OSError, sqlite3.Error) as exc:
                    trial["status"] = "failed"
                    trial["failure_reason"] = type(exc).__name__ + ": " + str(exc)[:256]
                trial["wall_seconds"] = time.monotonic() - before
            with registry._transaction():
                registry._put("experiment-trial", trial_key, trial)
            trials.append(trial)
        eligible = [t for t in trials if t["status"] == "completed"
                    and t["validation"]["field_opportunities"] > 0
                    and t["validation"]["unassessable_cases"] == 0]
        winner = min(eligible, key=lambda t: tuple(t["validation"][k] for k in OBJECTIVE)) if eligible else None
        receipt = {"experiment_id": experiment_id, "plan_sha256": fingerprint(plan), "trials": trials,
                   "selected_recipe": winner["recipe"] if winner else None,
                   "selection_basis": "lexicographic validation counts; recipe order breaks ties",
                   "wall_seconds": time.monotonic() - started, "test_sent_to_worker": False, "test_scored": False,
                   "promotion_authorized": False, "clinical_validation": False,
                   "neural_training_performed": False}
        with registry._transaction():
            cancellation = self._cancel_request(experiment_id)
            receipt["status"] = "cancelled" if cancellation else "completed"
            receipt["cancellation"] = cancellation
            if cancellation:
                receipt["selected_recipe"] = None
                receipt["selection_basis"] = "Selection suppressed by cancellation"
            registry._put("experiment-finish", experiment_id, receipt)
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("command", nargs="?", choices=("recipe", "plan", "execute", "inspect", "cancel"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--experiment")
    parser.add_argument("--reason", help="Required cancellation reason")
    args = parser.parse_args(argv)
    try:
        if args.worker:
            resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            result = worker(read_json(sys.stdin.buffer.read(MAX_JSON_BYTES + 1)))
        else:
            _require(args.registry is not None and args.command is not None, "Registry and command required")
            with LaboratoryEvaluationRegistry(args.registry) as registry:
                service = LaboratoryExperiments(registry)
                if args.command in ("recipe", "plan"):
                    _require(args.input is not None, "Input required")
                    result = getattr(service, args.command)(read_json(args.input.read_bytes()))
                else:
                    _require(args.experiment is not None, "Experiment ID required")
                    result = (service.cancel(args.experiment, args.reason) if args.command == "cancel"
                              else getattr(service, args.command)(args.experiment))
        print(_json(result))
        return 0
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        parser.exit(2, f"Experiment rejected: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
