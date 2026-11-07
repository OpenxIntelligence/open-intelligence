"""Synthetic calibration-role isolation and original v1 receipt compatibility."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from oi_api.laboratory_evaluation import LaboratoryEvaluationRegistry, fingerprint, read_json
from oi_api.laboratory_experiments import LaboratoryExperiments, TECHNIQUES, run_worker, worker


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "validation/laboratory-evaluation"
V1 = "oi.synthetic-laboratory-evaluation/1"
V2 = "oi.synthetic-laboratory-evaluation/2"
CALIBRATION_FLAGS = ("calibration_sent_to_worker", "calibration_scored", "calibration_performed")
SYSTEM = {"system_id": "manual-calibration", "system_version": "1", "software_commit": "a" * 40}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def calibration_case(suffix="D", source_version=1, value="7.25"):
    """Author a fictional case from the repository's synthetic FHIR template."""
    case = deepcopy(read_json((FIXTURES / "dataset.json").read_bytes())["cases"][0])
    raw = case["bundle_json"]
    for kind in ("PATIENT", "SPECIMEN", "OBS", "REPORT"):
        raw = raw.replace("FICTIONAL-" + kind + "-A", "FICTIONAL-" + kind + "-" + suffix)
    raw = raw.replace('"value":4.20', '"value":' + value)
    case.update(case_id="LAB-CALIBRATION-" + suffix, split="calibration",
                source_id="LAB-SOURCE-" + suffix, source_version=source_version,
                subject_reference="Patient/FICTIONAL-PATIENT-" + suffix,
                bundle_json=raw, source_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                training_eligible=False)
    return case


def calibration_gold(case, value="7.25"):
    row = deepcopy(read_json((FIXTURES / "reference.json").read_bytes())["observations"]["LAB-TRAIN-A"][0])
    suffix = case["subject_reference"].removeprefix("Patient/FICTIONAL-PATIENT-")
    row.update(reference="Observation/FICTIONAL-OBS-" + suffix,
               subject_reference=case["subject_reference"],
               specimen_reference="Specimen/FICTIONAL-SPECIMEN-" + suffix,
               source_sha256=case["source_sha256"], source_version=case["source_version"],
               value_text=value)
    return [row]


class LaboratoryCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "calibration.sqlite"
        self.registry = LaboratoryEvaluationRegistry(self.path)
        self.addCleanup(self.registry.close)
        self.service = LaboratoryExperiments(self.registry)

    def manifest(self):
        value = read_json((FIXTURES / "dataset.json").read_bytes())
        value.update(contract=V2, dataset_id="calibration-practice")
        value["authorship"] += " Additional independently fictional calibration case."
        value["cases"][0]["training_eligible"] = True
        value["cases"].append(calibration_case())
        return value

    def snapshot(self):
        return (self.registry.db.execute("SELECT * FROM records ORDER BY kind,id").fetchall(),
                self.registry.db.execute("SELECT * FROM splits ORDER BY identity").fetchall())

    def freeze_v2(self, manifest):
        try:
            return self.registry.freeze(manifest)["dataset"]
        except ValueError as exc:
            self.fail("A valid synthetic calibration-role dataset was rejected: " + str(exc))

    def review(self, reference_id, case, observations):
        output = self.registry.run(reference_id)["outputs"][case["case_id"]]
        self.registry.review({"run_id": reference_id, "case_id": case["case_id"],
                              "reviewer_id": "fixture-author", "independence_declared": False,
                              "decision": "correct", "output_sha256": fingerprint(output),
                              "corrected_observations": observations,
                              "reason": "Authored synthetic engineering reference", "correction_seconds": 0})

    def prepare(self, manifest, reference_id):
        dataset = self.freeze_v2(manifest)
        self.registry.baseline(reference_id, dataset, "a" * 40)
        gold = read_json((FIXTURES / "reference.json").read_bytes())["observations"]
        for case in manifest["cases"]:
            if case["split"] in ("train", "validation"):
                self.review(reference_id, case, gold[case["case_id"]])
        return dataset

    def spec(self, experiment_id, dataset, reference_id, *, parser_only=False):
        keys = [self.service.recipe({"recipe_id": technique, "version": 1, "technique": technique,
                                     "model_identity": TECHNIQUES[technique], "parameters": {}})["recipe"]
                for technique in ("exact_source_memory", "parser_baseline")]
        return {"experiment_id": experiment_id, "dataset": dataset, "reference_run": reference_id,
                "recipes": keys[1:] if parser_only else keys, "software_commit": "a" * 40,
                "max_total_wall_seconds": 10, "max_trial_wall_seconds": 3, "max_training_examples": 1}

    def load_legacy(self):
        golden = read_json((FIXTURES / "legacy-v1-receipts.json").read_bytes())
        dataset = self.registry.freeze(golden["dataset"])["dataset"]
        with self.registry._transaction():
            for record in golden["records"]:
                self.assertEqual(self.registry._put(record["kind"], record["id"], record["payload"]),
                                 record["sha256"])
        return dataset, golden

    def test_unsupported_contracts_and_roles_leave_no_records_or_split_claims(self):
        before = self.snapshot()
        for contract, split, message in ((V1, "calibration", "split"),
                                         ("oi.synthetic-laboratory-evaluation/3", "train", None),
                                         (V2, "calibrate", "split")):
            manifest = self.manifest()
            manifest["contract"] = contract
            manifest["cases"][-1]["split"] = split
            with self.subTest(contract=contract, split=split):
                if message:
                    with self.assertRaisesRegex(ValueError, message):
                        self.registry.freeze(manifest)
                else:
                    with self.assertRaises(ValueError):
                        self.registry.freeze(manifest)
                self.assertEqual(self.snapshot(), before)

    def test_calibration_eligibility_and_cross_role_moves_fail_atomically(self):
        manifest = self.manifest()
        self.freeze_v2(manifest)
        before = self.snapshot()
        ineligible = deepcopy(manifest)
        ineligible["version"] = 2
        ineligible["cases"][-1]["training_eligible"] = True
        with self.assertRaisesRegex(ValueError, "Held-out"):
            self.registry.freeze(ineligible)
        self.assertEqual(self.snapshot(), before)

        calibration = manifest["cases"][-1]
        for identity in ("subject:" + calibration["subject_reference"],
                         "source:" + calibration["source_id"], "hash:" + calibration["source_sha256"]):
            self.assertEqual(self.registry.db.execute("SELECT split FROM splits WHERE identity=?", (identity,)).fetchone(),
                             ("calibration",))
        attempts = []
        for target in ("train", "validation", "test"):
            moved = deepcopy(calibration)
            moved["split"] = target
            attempts.append(("calibration-to-" + target, moved))
            moved = deepcopy(next(c for c in manifest["cases"] if c["split"] == target))
            moved.update(split="calibration", training_eligible=False)
            attempts.append((target + "-to-calibration", moved))
        # Different source/hash retains the patient boundary; a different patient
        # retains the source-family boundary even for a later source version.
        patient_alias = deepcopy(calibration)
        patient_alias.update(split="train", source_id="NEW-SOURCE-FOR-D", source_version=2)
        patient_alias["bundle_json"] += " "
        patient_alias["source_sha256"] = hashlib.sha256(patient_alias["bundle_json"].encode()).hexdigest()
        attempts.append(("patient-alias", patient_alias))
        source_alias = calibration_case("ANOTHER-PATIENT", source_version=2)
        source_alias.update(split="train", source_id=calibration["source_id"])
        attempts.append(("source-alias", source_alias))
        for index, (name, moved) in enumerate(attempts):
            attempted = deepcopy(manifest)
            attempted.update(dataset_id="rejected-" + name, version=1,
                             cases=[calibration_case("ROLLBACK-" + str(index)), moved])
            with self.subTest(move=name), self.assertRaisesRegex(ValueError, "splits"):
                self.registry.freeze(attempted)
            self.assertEqual(self.snapshot(), before)

    def test_real_workers_exclude_unreviewed_calibration_and_record_unused_role(self):
        manifest = self.manifest()
        dataset = self.prepare(manifest, "reference")
        reference = self.registry.run("reference")
        self.assertEqual(reference["contract"], V2)
        self.assertEqual(reference["evaluated_splits"], ["train", "validation", "calibration", "test"])
        exported = self.registry.training_examples("reference")
        self.assertEqual(exported["contract"], V2)
        self.assertEqual([e["case_id"] for e in exported["examples"]], ["LAB-TRAIN-A"])
        self.service.plan(self.spec("search", dataset, "reference"))
        plan = self.service.inspect("search")["plan"]
        for flag in CALIBRATION_FLAGS:
            self.assertIs(plan.get(flag), False)
        forbidden = [c for c in manifest["cases"] if c["split"] in ("calibration", "test")]
        original_get = self.registry._get
        payloads = []

        def guarded_get(kind, key):
            if kind == "review" and any(key.endswith(":" + c["case_id"]) for c in forbidden):
                raise AssertionError("Experiment read a reserved-role reference judgment")
            return original_get(kind, key)

        def capture(payload, timeout):
            payloads.append(deepcopy(payload))
            return run_worker(payload, timeout)

        with patch.object(self.registry, "_get", side_effect=guarded_get), \
                patch("oi_api.laboratory_experiments.run_worker", side_effect=capture):
            receipt = self.service.execute("search")
            graph = self.service.lineage("search")
        self.assertEqual([t["status"] for t in receipt["trials"]], ["completed", "completed"])
        self.assertEqual(receipt["selected_recipe"], "parser_baseline:1")
        for flag in CALIBRATION_FLAGS:
            self.assertIs(receipt.get(flag), False)
        self.assertEqual(len(payloads), 2)
        for payload in payloads:
            self.assertEqual([c["case_id"] for c in payload["validation"]], ["LAB-VALIDATION-B"])
            for case in forbidden:
                for key in ("case_id", "subject_reference", "source_sha256"):
                    self.assertNotIn(case[key], canonical(payload))
        self.assertEqual([e["case_id"] for e in payloads[0]["training"]], ["LAB-TRAIN-A"])
        self.assertEqual(payloads[1]["training"], [])
        for trial in receipt["trials"]:
            run = self.registry.run(trial["run_id"])
            self.assertEqual(run["contract"], V2)
            self.assertEqual(run["evaluated_splits"], ["validation"])
            self.assertEqual(set(run["outputs"]), {"LAB-VALIDATION-B"})
            score = self.registry._get("score", trial["score_sha256"])
            self.assertEqual(score["contract"], V2)
            self.assertEqual(score["by_split"]["calibration"]["cases"], 0)
        checkpoint = self.registry._get("checkpoint", receipt["trials"][0]["run_id"])
        self.assertEqual(set(checkpoint["artifact"]["entries"]), {manifest["cases"][0]["source_sha256"]})
        self.assertEqual({n["id"] for n in graph["nodes"] if n["kind"] == "review"},
                         {"reference:LAB-TRAIN-A", "reference:LAB-VALIDATION-B"})
        calibration = manifest["cases"][-1]
        with self.assertRaisesRegex(ValueError, "non-validation"):
            worker({"technique": "parser_baseline", "training": [], "validation": [calibration]})
        with self.assertRaisesRegex(ValueError, "ineligible"):
            worker({"technique": "exact_source_memory", "training": [calibration],
                    "validation": [manifest["cases"][1]]})

    def test_calibration_only_changes_leave_fitting_predictions_and_selection_unchanged(self):
        first = self.manifest()
        second = deepcopy(first)
        second["version"] = 2
        second["cases"][-1] = calibration_case(source_version=2, value="99.10")
        receipts = []
        for name, manifest in (("first", first), ("second", second)):
            dataset = self.prepare(manifest, name + "-reference")
            self.service.plan(self.spec(name, dataset, name + "-reference"))
            receipts.append(self.service.execute(name))
        self.assertNotEqual(receipts[0]["plan_sha256"], receipts[1]["plan_sha256"])
        self.assertEqual([r["selected_recipe"] for r in receipts], ["parser_baseline:1", "parser_baseline:1"])
        for left, right in zip(receipts[0]["trials"], receipts[1]["trials"]):
            self.assertEqual((left["status"], right["status"]), ("completed", "completed"))
            self.assertEqual(left["validation"], right["validation"])
            self.assertEqual(self.registry.run(left["run_id"])["outputs"], self.registry.run(right["run_id"])["outputs"])
            self.assertEqual(self.registry._get("checkpoint", left["run_id"])["artifact"],
                             self.registry._get("checkpoint", right["run_id"])["artifact"])
        comparison = self.service.compare({"experiments": ["first", "second"]})
        self.assertEqual([row["rank"] for row in comparison["rows"]], [1, 1, 2, 2])

    def test_explicit_manual_calibration_score_requires_its_review_and_keeps_other_roles_unscored(self):
        manifest = self.manifest()
        dataset = self.freeze_v2(manifest)
        self.registry.baseline("manual-reference", dataset, "a" * 40)
        case = manifest["cases"][-1]
        output = deepcopy(self.registry.run("manual-reference")["outputs"][case["case_id"]])
        output["observations"][0]["value_text"] = "123.45"
        self.registry.record_run("manual-calibration", dataset, SYSTEM, {case["case_id"]: output},
                                 evaluated_splits=["calibration"])
        run = self.registry.run("manual-calibration")
        self.assertEqual(run["contract"], V2)
        self.assertEqual(run["evaluated_splits"], ["calibration"])
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.registry.score("manual-calibration", "manual-reference")
        self.assertEqual(self.snapshot(), before)
        self.review("manual-reference", case, calibration_gold(case))
        report = self.registry.score("manual-calibration", "manual-reference")
        self.assertEqual(report["contract"], V2)
        self.assertEqual(report["by_split"]["calibration"]["cases"], 1)
        self.assertEqual(report["by_split"]["calibration"]["field_errors"], 1)
        self.assertEqual([report["by_split"][role]["cases"] for role in ("train", "validation", "test")], [0, 0, 0])
        self.assertEqual([detail["case_id"] for detail in report["details"]], [case["case_id"]])
        self.assertFalse(report["independent_evaluation_established"])
        self.assertEqual(self.registry.score("manual-calibration", "manual-reference"), report)

    def test_run_scope_is_bound_to_its_version_and_v2_never_uses_the_legacy_default(self):
        legacy_dataset, golden = self.load_legacy()
        legacy = next(r["payload"] for r in golden["records"]
                      if r["kind"] == "run" and r["id"] == "legacy")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "evaluated splits"):
            self.registry.record_run("invalid-v1-scope", legacy_dataset, SYSTEM,
                                     {"LAB-TRAIN-A": legacy["outputs"]["LAB-TRAIN-A"]},
                                     evaluated_splits=["train", "calibration"])
        self.assertEqual(self.snapshot(), before)
        dataset = self.freeze_v2(self.manifest())
        self.registry.baseline("scoped-v2", dataset, "a" * 40)
        unscoped = self.registry.run("scoped-v2")
        unscoped["run_id"] = "missing-v2-scope"
        del unscoped["evaluated_splits"]
        with self.registry._transaction():
            self.registry._put("run", unscoped["run_id"], unscoped)
        with self.assertRaisesRegex(ValueError, "explicit"):
            self.registry.run(unscoped["run_id"])

    def test_original_v1_run_and_score_bytes_survive_exact_retry_and_reopen(self):
        dataset, golden = self.load_legacy()
        for registry in (self.registry, LaboratoryEvaluationRegistry(self.path)):
            if registry is not self.registry:
                self.addCleanup(registry.close)
            for record in golden["records"]:
                payload = record["payload"]
                if record["kind"] == "run":
                    receipt = registry.record_run(payload["run_id"], dataset, payload["system"], payload["outputs"],
                                                  execution=payload["execution"],
                                                  evaluated_splits=payload.get("evaluated_splits"))
                    self.assertEqual(receipt["sha256"], record["sha256"])
                    self.assertEqual(canonical(registry.run(record["id"])), canonical(payload))
                elif record["kind"] == "score":
                    actual = registry.score(payload["candidate_run"], payload["reference_run"])
                    self.assertEqual(canonical(actual), canonical(payload))
                    self.assertEqual(hashlib.sha256(canonical(actual).encode()).hexdigest(), record["sha256"])
                stored = registry.db.execute("SELECT payload,sha256 FROM records WHERE kind=? AND id=?",
                                             (record["kind"], record["id"])).fetchone()
                self.assertEqual(stored, (canonical(payload), record["sha256"]))

    def test_completed_v1_history_stays_read_only_without_calibration_claims(self):
        dataset, _ = self.load_legacy()
        self.service.plan(self.spec("legacy-completed", dataset, "legacy", parser_only=True))
        receipt = self.service.execute("legacy-completed")
        self.assertEqual(receipt["selected_recipe"], "parser_baseline:1")
        for artifact in (self.service.inspect("legacy-completed")["plan"], receipt):
            for flag in CALIBRATION_FLAGS:
                self.assertNotIn(flag, artifact)
        before = self.path.read_bytes()
        with LaboratoryEvaluationRegistry(self.path) as reopened:
            service = LaboratoryExperiments(reopened)
            with patch("oi_api.laboratory_experiments.run_worker", side_effect=AssertionError("No rerun")), \
                    patch.object(reopened, "score", side_effect=AssertionError("No rescore")):
                self.assertEqual(canonical(service.execute("legacy-completed")), canonical(receipt))
                graph = service.lineage("legacy-completed")
        self.assertTrue(graph["integrity_checked"])
        self.assertEqual(graph["status"], "finished")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
