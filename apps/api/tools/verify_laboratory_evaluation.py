"""Exercise the offline laboratory registry using public authored practice labels.

Reviews below are scripted fixture comparisons, never actual human review. No
model is called and no training is performed. Use a disposable local registry.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import subprocess

from oi_api.laboratory_evaluation import LaboratoryEvaluationRegistry, fingerprint, read_json

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "validation" / "laboratory-evaluation"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    reference = read_json((FIXTURES / "reference.json").read_bytes())["observations"]
    with LaboratoryEvaluationRegistry(args.registry) as registry:
        frozen = registry.freeze(read_json((FIXTURES / "dataset.json").read_bytes()))
        registry.baseline("practice-baseline", frozen["dataset"], commit)
        baseline = registry.run("practice-baseline")
        for case_id, output in baseline["outputs"].items():
            registry.review({"run_id": "practice-baseline", "case_id": case_id,
                             "reviewer_id": "scripted-fixture-reference", "independence_declared": False,
                             "decision": "correct", "output_sha256": fingerprint(output),
                             "corrected_observations": reference[case_id],
                             "reason": "Scripted authored reference; no human review performed.",
                             "correction_seconds": 0})
        baseline_report = registry.score("practice-baseline", "practice-baseline")
        assert sum(x["field_errors"] for x in baseline_report["by_split"].values()) == 0
        outputs = deepcopy(baseline["outputs"])
        outputs["LAB-TRAIN-A"]["observations"][0]["unit_code"] = "wrong-unit"
        outputs["LAB-TEST-C-V1"] = {"status": "abstained", "observations": [], "reason": "Planted omission"}
        registry.record_run("practice-defects", frozen["dataset"],
                            {"system_id": "scripted-negative-control", "system_version": "1",
                             "software_commit": commit}, outputs)
        defects_report = registry.score("practice-defects", "practice-baseline")
        assert defects_report["by_split"]["train"]["field_errors"] == 1
        assert defects_report["by_split"]["test"]["omissions"] == 1
        assert registry.training_examples("practice-baseline")["examples"] == []
    with LaboratoryEvaluationRegistry(args.registry) as registry:
        assert registry.run("practice-baseline") == baseline
        assert registry.score("practice-defects", "practice-baseline") == defects_report
    print(json.dumps({"software_commit": commit, "dataset": frozen, "restart_verified": True,
                      "human_review_performed": False, "training_performed": False,
                      "clinical_validation": False, "baseline": baseline_report,
                      "negative_control": defects_report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
