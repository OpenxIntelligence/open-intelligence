"""Offline, synthetic-only laboratory evaluation records for OI-011.

This local experiment log is not an H1 patient store, an authorization boundary,
a training service, or an independent clinical evaluation. It calls the existing
FHIR parser for its deterministic baseline; candidate outputs are supplied files.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

from .laboratory_fhir_r4 import prepare_laboratory_bundle

CONTRACT = "oi.synthetic-laboratory-evaluation/1"
APPLICATION_ID = 0x4F494C45
MAX_JSON_BYTES = 4 * 1024 * 1024
SPLITS = ("train", "validation", "test")
FIELDS = ("subject_reference", "specimen_reference", "source_sha256", "source_version",
          "loinc_code", "effective_at", "issued_at", "status", "value_text",
          "unit_code", "absent_reason")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _shape(value, keys):
    _require(type(value) is dict and set(value) == set(keys), "Unexpected or missing fields")


def _text(value, limit=256):
    _require(type(value) is str and 0 < len(value.strip()) <= limit
             and not any(ord(c) < 32 for c in value), "Invalid text")


def _id(value):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value),
             "Invalid identifier")


def _sha(value, length=64):
    _require(type(value) is str and re.fullmatch(r"[a-f0-9]{%d}" % length, value),
             "Invalid digest")


def _positive(value):
    _require(type(value) is int and value > 0, "Positive integer required")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def read_json(raw):
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_JSON_BYTES, "JSON size boundary")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "Duplicate JSON member")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Nonfinite JSON value")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
        _json(value)  # Also reject numeric overflow such as 1e999.
        return value
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError("Invalid JSON") from exc


def _observations(rows):
    _require(type(rows) is list and len(rows) <= 32, "Invalid observation list")
    seen = set()
    for row in rows:
        _shape(row, ("reference", *FIELDS))
        _text(row["reference"])
        _require(row["reference"] not in seen, "Duplicate observation reference")
        seen.add(row["reference"])
        for key in FIELDS:
            if key == "source_version":
                _positive(row[key])
            elif key in ("value_text", "unit_code", "absent_reason") and row[key] is None:
                continue
            else:
                _text(row[key])
        _sha(row["source_sha256"])
    return rows


def _output(output):
    _shape(output, ("status", "observations", "reason"))
    _require(output["status"] in ("extracted", "abstained", "error"), "Invalid output status")
    _observations(output["observations"])
    if output["status"] == "extracted":
        _require(output["reason"] is None, "Extracted output cannot carry failure reason")
    else:
        _require(not output["observations"], "Failure or abstention must not assert results")
        _text(output["reason"], 2000)


def _manifest(manifest):
    _shape(manifest, ("contract", "dataset_id", "version", "synthetic", "authorship", "cases"))
    _require(manifest["contract"] == CONTRACT and manifest["synthetic"] is True,
             "Only declared synthetic evaluation fixtures are supported")
    _id(manifest["dataset_id"])
    _positive(manifest["version"])
    _text(manifest["authorship"], 2000)
    _require(type(manifest["cases"]) is list and 0 < len(manifest["cases"]) <= 100,
             "Dataset must contain 1..100 cases")
    seen = set()
    source_versions, source_hashes = set(), set()
    for case in manifest["cases"]:
        _shape(case, ("case_id", "split", "source_id", "source_version", "subject_reference",
                      "bundle_json", "source_sha256", "training_eligible"))
        _id(case["case_id"])
        _id(case["source_id"])
        _require(case["case_id"] not in seen, "Duplicate case ID")
        seen.add(case["case_id"])
        _require(case["split"] in SPLITS, "Invalid dataset split")
        _positive(case["source_version"])
        _require(type(case["training_eligible"]) is bool, "Explicit training eligibility required")
        _require(not case["training_eligible"] or case["split"] == "train",
                 "Held-out cases cannot be training eligible")
        _require(type(case["bundle_json"]) is str, "Original bundle text required")
        raw = case["bundle_json"].encode("utf-8")
        parsed = prepare_laboratory_bundle(raw, expected_subject_reference=case["subject_reference"])
        _require(parsed.source_sha256 == case["source_sha256"], "Source hash mismatch")
        source_key = (case["source_id"], case["source_version"])
        _require(source_key not in source_versions and case["source_sha256"] not in source_hashes,
                 "Repeated source would duplicate evaluation opportunities")
        source_versions.add(source_key)
        source_hashes.add(case["source_sha256"])


def baseline_output(case):
    parsed = prepare_laboratory_bundle(case["bundle_json"].encode("utf-8"),
                                      expected_subject_reference=case["subject_reference"])
    rows = []
    for observation in parsed.observations:
        row = {key: value for key, value in observation.items()
               if key in FIELDS or key == "reference"}
        row.update(subject_reference=parsed.subject_reference,
                   specimen_reference=parsed.specimen_reference,
                   source_sha256=parsed.source_sha256, source_version=case["source_version"])
        rows.append(row)
    return {"status": "extracted", "observations": rows, "reason": None}


class LaboratoryEvaluationRegistry:
    """Append-only local study artifacts; never opens the application's database.

    The SQLite file is an offline experiment artifact, not a replacement for the
    accepted PostgreSQL application. Local file administrators are trusted.
    """

    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        try:
            with self._transaction():
                app_id = self.db.execute("PRAGMA application_id").fetchone()[0]
                version = self.db.execute("PRAGMA user_version").fetchone()[0]
                tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                _require((app_id == APPLICATION_ID and version == 1)
                         or (app_id == 0 and version == 0 and not tables),
                         "Not a supported laboratory evaluation registry")
                if app_id == APPLICATION_ID:
                    triggers = {r[0] for r in self.db.execute(
                        "SELECT name FROM sqlite_master WHERE type='trigger'")}
                    _require(tables == {"records", "splits"} and triggers == {
                        f"{table}_{operation}" for table in tables for operation in ("UPDATE", "DELETE")},
                        "Incomplete laboratory evaluation schema")
                    return
                self.db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, "
                                "id TEXT NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL, "
                                "recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), "
                                "PRIMARY KEY(kind,id))")
                self.db.execute("CREATE TABLE IF NOT EXISTS splits (identity TEXT PRIMARY KEY, "
                                "split TEXT NOT NULL)")
                for table in ("records", "splits"):
                    for operation in ("UPDATE", "DELETE"):
                        self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} "
                                        f"BEFORE {operation} ON {table} BEGIN "
                                        "SELECT RAISE(ABORT,'immutable evaluation record'); END")
                self.db.execute(f"PRAGMA application_id={APPLICATION_ID}")
                self.db.execute("PRAGMA user_version=1")
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _transaction(self):
        nested = self.db.in_transaction
        self.db.execute("SAVEPOINT evaluation_nested" if nested else "BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("RELEASE SAVEPOINT evaluation_nested" if nested else "COMMIT")
        except BaseException:
            if nested:
                self.db.execute("ROLLBACK TO SAVEPOINT evaluation_nested")
                self.db.execute("RELEASE SAVEPOINT evaluation_nested")
            else:
                self.db.execute("ROLLBACK")
            raise

    def _put(self, kind, key, value):
        payload, digest = _json(value), fingerprint(value)
        prior = self.db.execute("SELECT payload,sha256 FROM records WHERE kind=? AND id=?",
                                (kind, key)).fetchone()
        if prior is not None:
            _require(prior == (payload, digest), "Identifier already has different immutable content")
        else:
            self.db.execute("INSERT INTO records (kind,id,payload,sha256) VALUES (?,?,?,?)",
                            (kind, key, payload, digest))
        return digest

    def _get(self, kind, key):
        row = self.db.execute("SELECT payload,sha256 FROM records WHERE kind=? AND id=?",
                              (kind, key)).fetchone()
        _require(row is not None, "Unknown evaluation record")
        payload = read_json(row[0].encode())
        _require(fingerprint(payload) == row[1], "Evaluation record integrity failure")
        return payload

    def freeze(self, manifest):
        # Snapshot caller data before validating or committing it.
        manifest = read_json(_json(manifest).encode())
        _manifest(manifest)
        with self._transaction():
            for case in manifest["cases"]:
                for identity in ("subject:" + case["subject_reference"],
                                 "source:" + case["source_id"], "hash:" + case["source_sha256"]):
                    prior = self.db.execute("SELECT split FROM splits WHERE identity=?", (identity,)).fetchone()
                    _require(prior is None or prior[0] == case["split"],
                             "Patient or source crosses frozen dataset splits")
                    if prior is None:
                        self.db.execute("INSERT INTO splits VALUES (?,?)", (identity, case["split"]))
                self._put("source-owner", case["source_id"], case["subject_reference"])
                self._put("source-version", f'{case["source_id"]}:{case["source_version"]}',
                          {"subject_reference": case["subject_reference"], "sha256": case["source_sha256"]})
            key = f'{manifest["dataset_id"]}:{manifest["version"]}'
            return {"dataset": key, "sha256": self._put("dataset", key, manifest)}

    def dataset(self, key):
        return self._get("dataset", key)

    def record_run(self, run_id, dataset, system, outputs, *, execution="supplied_outputs",
                   evaluated_splits=None):
        _id(run_id)
        _shape(system, ("system_id", "system_version", "software_commit"))
        _id(system["system_id"])
        _text(system["system_version"])
        _sha(system["software_commit"], 40)
        _require(execution in ("supplied_outputs", "deterministic_parser"), "Invalid execution kind")
        manifest = self.dataset(dataset)
        if evaluated_splits is None:
            evaluated_splits = list(SPLITS)
        _require(type(evaluated_splits) is list and bool(evaluated_splits)
                 and all(type(s) is str and s in SPLITS for s in evaluated_splits)
                 and len(set(evaluated_splits)) == len(evaluated_splits), "Invalid evaluated splits")
        cases = [c for c in manifest["cases"] if c["split"] in evaluated_splits]
        _require(bool(cases), "No cases in evaluated splits")
        _shape(outputs, [c["case_id"] for c in cases])
        for output in outputs.values():
            _output(output)
        if execution == "deterministic_parser":
            _require(system["system_id"] == "oi.fhir-r4-laboratory-parser"
                     and outputs == {c["case_id"]: baseline_output(c) for c in cases},
                     "Baseline receipt does not match canonical parser")
        run = {"contract": CONTRACT, "run_id": run_id, "dataset": dataset,
               "dataset_sha256": fingerprint(manifest), "system": system, "execution": execution,
               "model_execution_verified": False, "software_commit_verified": False,
               "parser_source_sha256": (hashlib.sha256(Path(__file__).with_name(
                   "laboratory_fhir_r4.py").read_bytes()).hexdigest()
                   if execution == "deterministic_parser" else None), "outputs": outputs}
        # Preserve the byte shape of historical all-split records and retries.
        if evaluated_splits != list(SPLITS):
            run["evaluated_splits"] = evaluated_splits
        with self._transaction():
            return {"run_id": run_id, "sha256": self._put("run", run_id, run)}

    def run(self, key):
        run = self._get("run", key)
        _require(fingerprint(self.dataset(run["dataset"])) == run["dataset_sha256"],
                 "Dataset fingerprint changed")
        return run

    def baseline(self, run_id, dataset, software_commit):
        cases = self.dataset(dataset)["cases"]
        return self.record_run(run_id, dataset,
                               {"system_id": "oi.fhir-r4-laboratory-parser", "system_version": "1",
                                "software_commit": software_commit},
                               {c["case_id"]: baseline_output(c) for c in cases},
                               execution="deterministic_parser")

    def review(self, review):
        _shape(review, ("run_id", "case_id", "reviewer_id", "independence_declared", "decision",
                        "output_sha256", "corrected_observations", "reason", "correction_seconds"))
        _id(review["reviewer_id"])
        _require(type(review["independence_declared"]) is bool, "Explicit independence declaration required")
        _text(review["reason"], 2000)
        seconds = review["correction_seconds"]
        _require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0,
                 "Invalid correction time")
        run = self.run(review["run_id"])
        _require(review["case_id"] in run["outputs"], "Case does not belong to run")
        output = run["outputs"][review["case_id"]]
        _require(fingerprint(output) == review["output_sha256"], "Review refers to a different output")
        decision = review["decision"]
        _require(decision in ("accept", "correct", "unassessable"), "Invalid review decision")
        if decision == "accept":
            _require(output["status"] == "extracted", "Cannot accept failed extraction as a reference")
        if decision == "correct":
            rows = _observations(review["corrected_observations"])
        else:
            _require(review["corrected_observations"] is None, "Correction requires correct decision")
            rows = output["observations"] if decision == "accept" else []
        case = next(c for c in self.dataset(run["dataset"])["cases"] if c["case_id"] == review["case_id"])
        # Resolve identity directly from the frozen original, not the extractor's
        # output: an extractor omission must remain correctable and measurable.
        original = read_json(case["bundle_json"].encode("utf-8"))
        anchors = {"Observation/" + r["id"]: {
            "subject_reference": r["subject"]["reference"],
            "specimen_reference": r["specimen"]["reference"],
            "source_sha256": case["source_sha256"], "source_version": case["source_version"]}
            for entry in original["entry"] if (r := entry["resource"])["resourceType"] == "Observation"}
        for row in rows:
            _require(row["reference"] in anchors, "Review cites an unknown observation")
            for key in ("subject_reference", "specimen_reference", "source_sha256", "source_version"):
                _require(row[key] == anchors[row["reference"]][key], "Review source identity mismatch")
            if row["status"] == "reported_value":
                _require(row["value_text"] is not None and row["unit_code"] is not None
                         and row["absent_reason"] is None, "Incoherent reviewed value")
                _require(re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", row["value_text"]),
                         "Reviewed quantity must preserve decimal text")
            else:
                _require(row["status"] == "reported_absent" and row["value_text"] is None
                         and row["unit_code"] is None
                         and row["absent_reason"] in ("unknown", "not-performed", "error", "masked"),
                         "Incoherent reviewed missingness")
        if decision != "unassessable":
            _require({r["reference"] for r in rows} == set(anchors),
                     "Review reference must cover every source observation")
        key = f'{review["run_id"]}:{review["case_id"]}'
        with self._transaction():
            return {"review": key, "sha256": self._put("review", key, review)}

    def score(self, candidate_id, reference_id):
        candidate, reference = self.run(candidate_id), self.run(reference_id)
        _require(candidate["dataset_sha256"] == reference["dataset_sha256"],
                 "Candidate and reference must use the same frozen dataset")
        groups = {split: {"cases": 0, "assessed_cases": 0, "unassessable_cases": 0,
                          "field_opportunities": 0, "field_errors": 0, "omissions": 0,
                          "unsupported_observations": 0, "abstentions": 0, "execution_errors": 0,
                          "reference_correction_seconds": 0} for split in SPLITS}
        details = []
        for case in self.dataset(candidate["dataset"])["cases"]:
            if case["split"] not in candidate.get("evaluated_splits", SPLITS):
                continue
            case_id = case["case_id"]
            _require(case_id in reference["outputs"], "Reference did not evaluate this case")
            review = self._get("review", f"{reference_id}:{case_id}")
            g = groups[case["split"]]
            g["cases"] += 1
            output = candidate["outputs"][case_id]
            g["abstentions"] += output["status"] == "abstained"
            g["execution_errors"] += output["status"] == "error"
            g["reference_correction_seconds"] += review["correction_seconds"]
            if review["decision"] == "unassessable":
                g["unassessable_cases"] += 1
                continue
            g["assessed_cases"] += 1
            expected = (review["corrected_observations"] if review["decision"] == "correct"
                        else reference["outputs"][case_id]["observations"])
            expected = {r["reference"]: r for r in expected}
            actual = {r["reference"]: r for r in output["observations"]}
            g["field_opportunities"] += len(expected) * len(FIELDS)
            missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
            g["omissions"] += len(missing)
            g["unsupported_observations"] += len(extra)
            errors = [{"reference": ref, "field": field} for ref, row in expected.items()
                      for field in FIELDS if ref not in actual or row[field] != actual[ref][field]]
            g["field_errors"] += len(errors)
            details.append({"case_id": case_id, "omitted": missing, "unsupported": extra, "errors": errors})
        report = {"contract": CONTRACT, "candidate_run": candidate_id, "reference_run": reference_id,
                "candidate_sha256": fingerprint(candidate), "reference_sha256": fingerprint(reference),
                "dataset_sha256": candidate["dataset_sha256"], "by_split": groups, "details": details,
                "clinical_validation": False, "independent_evaluation_established": False,
                "promotion_authorized": False, "training_performed": False}
        with self._transaction():
            self._put("score", fingerprint(report), report)
        return report

    def training_examples(self, reference_id):
        """Explicit export of eligible reviewed train rows; never executes training."""
        run = self.run(reference_id)
        examples = []
        for case in self.dataset(run["dataset"])["cases"]:
            if case["split"] != "train" or case["training_eligible"] is not True:
                continue
            review = self._get("review", f'{reference_id}:{case["case_id"]}')
            if review["decision"] == "unassessable":
                continue
            rows = (review["corrected_observations"] if review["decision"] == "correct"
                    else run["outputs"][case["case_id"]]["observations"])
            examples.append({"case_id": case["case_id"], "bundle_json": case["bundle_json"],
                             "source_sha256": case["source_sha256"], "source_version": case["source_version"],
                             "observations": rows, "review_sha256": fingerprint(review)})
        return {"contract": CONTRACT, "dataset_sha256": run["dataset_sha256"],
                "reference_run": reference_id, "training_performed": False, "examples": examples}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("freeze", "record", "review"):
        commands.add_parser(command).add_argument("--input", type=Path, required=True)
    baseline = commands.add_parser("baseline")
    baseline.add_argument("--dataset", required=True)
    baseline.add_argument("--run", required=True)
    baseline.add_argument("--software-commit", required=True)
    score = commands.add_parser("score")
    score.add_argument("--candidate", required=True)
    score.add_argument("--reference", required=True)
    export = commands.add_parser("training-examples")
    export.add_argument("--reference", required=True)
    show = commands.add_parser("show-run")
    show.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        with LaboratoryEvaluationRegistry(args.registry) as registry:
            if args.command == "freeze":
                result = registry.freeze(read_json(args.input.read_bytes()))
            elif args.command == "record":
                value = read_json(args.input.read_bytes())
                _shape(value, ("run_id", "dataset", "system", "outputs"))
                result = registry.record_run(**value)
            elif args.command == "review":
                result = registry.review(read_json(args.input.read_bytes()))
            elif args.command == "baseline":
                result = registry.baseline(args.run, args.dataset, args.software_commit)
            elif args.command == "score":
                result = registry.score(args.candidate, args.reference)
            elif args.command == "show-run":
                result = registry.run(args.run)
            else:
                result = registry.training_examples(args.reference)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        parser.exit(2, f"Laboratory evaluation rejected: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
