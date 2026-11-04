"""Synthetic semantic mapping challenge: no patients, networking, model or SQL.

Research-only. Challenges are newly authored and NOT independently adjudicated
or concealed from evaluators. Do not report a provider's quality from this
harness without a real authenticated runtime receipt and separate review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from semantic_benchmark import (
    CASES_CONTRACT,
    deterministic_baseline,
    digest,
    run as benchmark_run,
    validate_cases,
)

CONTRACT = "oi.semantic-adversarial-challenge-report/1"
EXPECTED_CONCEPTS = ("source_version", "source_observation", "source_disagreement")
NEGATIVE_CLASSES = ("ambiguous", "unsupported", "unsafe", "false_join")
EXPECTED_NEGATIVES = {"ambiguous": 7, "unsupported": 7, "unsafe": 10, "false_join": 12}
MAX_INPUT_BYTES = 65_536


def _normalized(question: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", question.lower()))


def _strict_read(path: Path) -> Any:
    with path.open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Synthetic challenge file exceeds size bound")
    return json.loads(raw)


def validate_challenge(challenge: Any, original: Any) -> list[dict[str, Any]]:
    """Validate a disjoint, prespecified synthetic challenge suite.

    A unique question is not proof of independent clinical labeling. This
    function only prevents retesting the same text as the original baseline.
    """
    cases = validate_cases(challenge)
    baseline = validate_cases(original)
    if len(cases) != 72:
        raise ValueError("Frozen adversarial suite must contain 72 cases")
    if sum(r["expected"] is not None for r in cases) != 36:
        raise ValueError("Frozen suite requires 36 expected mappings")
    positive_counts = {name: 0 for name in EXPECTED_CONCEPTS}
    negatives = {kind: 0 for kind in NEGATIVE_CLASSES}
    for row in cases:
        if row["expected"] is None:
            negatives[row["category"]] += 1
        else:
            positive_counts[row["expected"]["concept"]] += 1
    if any(value != 12 for value in positive_counts.values()):
        raise ValueError("Expected 12 mappings for each approved concept")
    if negatives != EXPECTED_NEGATIVES:
        raise ValueError("Negative-case category coverage changed")
    ids = {row["id"] for row in cases}
    old_ids = {row["id"] for row in baseline}
    if ids & old_ids:
        raise ValueError("Challenge identifiers overlap original baseline")
    normalized = [_normalized(row["question"]) for row in cases]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate normalized questions in new challenge")
    if set(normalized) & {_normalized(row["question"]) for row in baseline}:
        raise ValueError("Question text overlaps the original benchmark")
    return cases


def _classification_summary(cases: list[dict[str, Any]], outcomes: list[dict[str, str]]) -> dict[str, Any]:
    by_id = {row["id"]: row for row in cases}
    negative = {name: {"abstained": 0, "false_mapping": 0} for name in NEGATIVE_CLASSES}
    concepts = {name: {"correct": 0, "abstained": 0, "wrong": 0} for name in EXPECTED_CONCEPTS}
    flagged = []
    for result in outcomes:
        row = by_id[result["id"]]
        outcome = result["outcome"]
        if row["expected"] is None:
            bucket = negative[row["category"]]
            bucket["abstained" if outcome == "negative_abstained" else "false_mapping"] += 1
            if outcome == "negative_false_mapping":
                flagged.append({"id": row["id"], "category": row["category"], "reason": "invalid_mapping_on_negative"})
        else:
            bucket = concepts[row["expected"]["concept"]]
            if outcome == "positive_correct":
                bucket["correct"] += 1
            elif outcome == "positive_missed":
                bucket["abstained"] += 1
            elif outcome == "positive_wrong":
                bucket["wrong"] += 1
                flagged.append({"id": row["id"], "category": "field_lookup", "reason": "wrong_field"})
            else:
                raise ValueError("Unexpected benchmark outcome")
    return {"by_negative_category": negative, "by_positive_concept": concepts,
            "flagged_case_ids": flagged,
            "unsafe_false_mappings": negative["unsafe"]["false_mapping"],
            "false_join_mappings": negative["false_join"]["false_mapping"]}


def evaluate(challenge: dict[str, Any], original: dict[str, Any], external_predictions: Any = None) -> dict[str, Any]:
    cases = validate_challenge(challenge, original)
    benchmark = benchmark_run(challenge, external_predictions)
    methods = []
    for result in benchmark["results"]:
        buckets = _classification_summary(cases, result["per_case_outcomes"])
        methods.append({
            "method": result["name"],
            "positive_correct": result["positive_correct"],
            "positive_abstained": result["positive_missed"],
            "positive_wrong": result["positive_wrong"],
            "negative_abstained": result["negative_abstained"],
            "negative_false_mapping": result["negative_false_mapping"],
            "positive_recall": result["positive_recall"],
            "negative_abstention_rate": result["negative_abstention_rate"],
            **buckets,
        })
    return {
        "contract": CONTRACT,
        "challenge_sha256": digest(challenge),
        "original_benchmark_sha256": digest(original),
        "schema_manifest_sha256": benchmark["manifest_sha256"],
        "challenge_size": len(cases),
        "reference_status": "author_labeled_synthetic_not_independently_adjudicated",
        "questions_blinded_from_model": False,
        "synthetic_schema_only": True,
        "no_patient_records_accessed": True,
        "no_provider_called": True,
        "no_sql_executed": True,
        "model_generated_semantics_tested": False,
        "clinical_validation": False,
        "adoption_approved": False,
        "methods": methods,
        "interpretation": (
            "This is a new, nonindependent author-labeled challenge set. "
            "False mappings measure a research boundary; no numeric threshold "
            "is an accepted clinical safety target. Vendor quality and "
            "latency/cost are unknown until an explicitly reviewed model run."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline adversarial semantic mapping evaluation")
    parser.add_argument("--cases", default="tests/fixtures/semantic_adversarial_challenge_v2.json")
    parser.add_argument("--original", default="tests/fixtures/semantic_benchmark_cases_v1.json")
    parser.add_argument("--external-predictions", help="untrusted offline replay, never a network call")
    parser.add_argument("--output", help="local report file")
    args = parser.parse_args()
    try:
        challenge = _strict_read(Path(args.cases))
        original = _strict_read(Path(args.original))
        candidate = _strict_read(Path(args.external_predictions)) if args.external_predictions else None
        output = evaluate(challenge, original, candidate)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        parser.error(str(exc))
        return
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
