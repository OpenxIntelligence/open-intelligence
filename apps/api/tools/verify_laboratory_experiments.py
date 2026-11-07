"""Actual two-candidate experiment using independently fictional practice data.

Scripted reference labels; no human adjudication, LLM, neural fine-tuning,
external service, or product deployment. Test references are deliberately absent.
"""
import argparse
import json
from pathlib import Path
import subprocess

from oi_api.laboratory_evaluation import LaboratoryEvaluationRegistry, fingerprint, read_json
from oi_api.laboratory_experiments import LaboratoryExperiments, TECHNIQUES

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "validation/laboratory-evaluation"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = read_json((FIXTURES / "dataset.json").read_bytes())
    manifest["version"] = 2
    manifest["cases"][0]["training_eligible"] = True
    gold = read_json((FIXTURES / "reference.json").read_bytes())["observations"]
    with LaboratoryEvaluationRegistry(args.registry) as registry:
        dataset = registry.freeze(manifest)["dataset"]
        registry.baseline("experiment-reference", dataset, commit)
        reference = registry.run("experiment-reference")
        for case in manifest["cases"]:
            if case["split"] == "test":
                continue
            key = case["case_id"]
            registry.review({"run_id": "experiment-reference", "case_id": key,
                             "reviewer_id": "scripted-fixture-reference", "independence_declared": False,
                             "decision": "correct", "output_sha256": fingerprint(reference["outputs"][key]),
                             "corrected_observations": gold[key], "reason": "Authored fixture; no human review",
                             "correction_seconds": 0})
        service = LaboratoryExperiments(registry)
        recipes = [service.recipe({"recipe_id": method, "version": 1, "technique": method,
                                   "model_identity": TECHNIQUES[method], "parameters": {}})["recipe"]
                   for method in ("exact_source_memory", "parser_baseline")]
        service.plan({"experiment_id": "practice-search", "dataset": dataset,
                      "reference_run": "experiment-reference", "recipes": recipes,
                      "software_commit": commit, "max_total_wall_seconds": 10,
                      "max_trial_wall_seconds": 3, "max_training_examples": 1})
        receipt = service.execute("practice-search")
        assert receipt["selected_recipe"] == "parser_baseline:1"
        assert receipt["trials"][0]["fit_performed"] is True
        assert receipt["trials"][0]["validation"]["abstentions"] == 1
        assert receipt["trials"][1]["validation"]["field_errors"] == 0
        assert all(t["status"] == "completed" for t in receipt["trials"])
        for trial in receipt["trials"]:
            assert set(registry.run(trial["run_id"])["outputs"]) == {"LAB-VALIDATION-B"}
            assert fingerprint(registry._get("checkpoint", trial["run_id"])) == trial["checkpoint_sha256"]
    with LaboratoryEvaluationRegistry(args.registry) as registry:
        assert LaboratoryExperiments(registry).execute("practice-search") == receipt
    print(json.dumps({"software_commit": commit, "restart_and_exact_retry_verified": True,
                      "human_review_performed": False, "receipt": receipt}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
