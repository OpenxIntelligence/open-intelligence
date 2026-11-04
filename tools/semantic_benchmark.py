"""Standalone offline testbed for first-party schema semantics.

No network access, database credentials, SQL generation, NVIDIA imports, PHI,
or model calls. A vendor (or any other system) can be scored only after a
separately obtained, untrusted, schema-only JSON prediction file is supplied.

The lexical baseline is intentionally simple. Accuracy on these hand-authored
synthetic prompts is engineering evidence, not clinical validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any

from semantic_contract_probe import schema_manifest, validate_mapping_candidate, CANDIDATE_CONTRACT

CASES_CONTRACT = "oi.semantic-benchmark-cases/1"
PREDICTIONS_CONTRACT = "oi.semantic-benchmark-predictions/1"
REPORT_CONTRACT = "oi.semantic-benchmark-report/1"
CATEGORIES = frozenset({"field_lookup", "ambiguous", "unsupported", "unsafe", "false_join"})
IDENT = re.compile(r"B-[0-9]{3}\Z")
PHRASE_WORD = re.compile(r"[a-z0-9_]+")
MAX_CASES = 128

# This baseline matches literal names from the allowlisted manifest, plus a
# small guard-phrase list for unsafe or out-of-scope wording. Several guard
# phrases mirror the negative cases' wording, so the abstention rate on these
# authored cases is not independent evidence that the guards generalize; it
# shows the guards fire on the cases they were written against.
# These guard clauses are not a clinical intent classifier; no execution is possible
# in this harness even if a query is misclassified. They are useful negatives.
# Phrases are matched against normalized text (lowercased, split on
# non-alphanumeric characters), so they must be written in normalized form:
# an apostrophe splits a word, which is why "patient's full name" appears
# here as "patient s full name".
UNSAFE_PHRASES = (
    "prescribe", "treatment should", "confirm that this person", "confirms that this person",
    "patient s full name",
    "patient name", "all patient cases", "ignore instructions", "expose all report",
    "read access across cases", "execute the generated query", "trial eligibility",
    "clinically reviewed", "recommendation", "recommendations", "give me the sql", "which patients",
)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def field_set() -> set[tuple[str, str]]:
    return {(c["concept"], f) for c in schema_manifest()["concepts"] for f in c["fields"]}


def validate_cases(payload: Any) -> list[dict[str, Any]]:
    if type(payload) is not dict or set(payload) != {"contract", "cases"} or payload["contract"] != CASES_CONTRACT:
        raise ValueError("Invalid benchmark envelope")
    rows = payload["cases"]
    if type(rows) is not list or not 30 <= len(rows) <= MAX_CASES:
        raise ValueError("Benchmark requires 30-128 synthetic cases")
    allowed = field_set()
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"id", "question", "category", "expected"}:
            raise ValueError("Invalid case fields")
        ident, q, category, expected = row["id"], row["question"], row["category"], row["expected"]
        if type(ident) is not str or not IDENT.fullmatch(ident) or ident in seen:
            raise ValueError("Duplicate or malformed case identifier")
        seen.add(ident)
        if (type(q) is not str or not 8 <= len(q) <= 180 or q != q.strip()
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in q)):
            raise ValueError("Invalid synthetic question")
        if category not in CATEGORIES:
            raise ValueError("Unknown case category")
        if category == "field_lookup":
            if type(expected) is not dict or set(expected) != {"concept", "field"} or (
                expected["concept"], expected["field"]) not in allowed:
                raise ValueError("Invalid positive expected mapping")
        elif expected is not None:
            raise ValueError("Negatives must expect abstention")
    if sum(r["expected"] is None for r in rows) < 10:
        raise ValueError("Benchmark missing abstention negatives")
    return rows


def _contains_phrase(question: str, phrase: str) -> bool:
    # Token matching guards against spurious matches in wider words.
    return bool(re.search(r"(?<![a-z0-9_])" + re.escape(phrase) + r"(?![a-z0-9_])", question))


def deterministic_baseline(question: str) -> dict[str, str]:
    """Minimal exact-vocabulary control, with conservative abstention.

    Detect only singular/plural concept names from the existing schema and
    exact field labels, not a curated synonym dictionary built from this test.
    A small guard-phrase list abstains on unsafe or out-of-scope wording
    first; several of those phrases mirror the negative cases' wording, so
    the abstention rate on these authored cases does not by itself prove
    the guards generalize.
    The concept label is removed before field matching: otherwise the word
    'version' in 'source version' would falsely answer every version question.
    """
    text = " ".join(PHRASE_WORD.findall(question.lower()))
    if any(_contains_phrase(text, word) for word in UNSAFE_PHRASES):
        return {"status": "abstain", "reason": "unsafe_or_out_of_scope"}
    scopes = []
    for concept in sorted(c["concept"] for c in schema_manifest()["concepts"]):
        label = concept.replace("_", " ")
        hit = next((v for v in (label+"s", label) if _contains_phrase(text, v)), None)
        if hit:
            scopes.append((concept, hit))
    if len(scopes) != 1:
        return {"status": "abstain", "reason": "ambiguous_or_missing_concept"}
    concept, scope_phrase = scopes[0]
    stripped = " ".join(text.replace(scope_phrase, " ").split())
    fields = next(c["fields"] for c in schema_manifest()["concepts"] if c["concept"] == concept)
    matches = [field for field in fields if _contains_phrase(stripped, field.replace("_", " "))]
    if len(matches) != 1:
        return {"status": "abstain", "reason": "ambiguous_or_missing_field"}
    return {"status": "proposed", "concept": concept, "field": matches[0]}


def validate_external_predictions(payload: Any, cases: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Validate an imported result file; never assert it originated from NVIDIA.

    An external prediction is structurally checked. Source authenticity,
    model runtime, absence of hidden PHI calls, and answer quality remain unverified.
    """
    if (type(payload) is not dict or set(payload) != {"contract", "manifest_sha256", "case_set_sha256", "predictions"}
            or payload["contract"] != PREDICTIONS_CONTRACT
            or payload["manifest_sha256"] != schema_manifest()["sha256"]
            or payload["case_set_sha256"] != digest({"contract": CASES_CONTRACT, "cases": cases})):
        raise ValueError("Untrusted, stale or malformed prediction envelope")
    entries = payload["predictions"]
    if type(entries) is not list or len(entries) != len(cases):
        raise ValueError("Prediction set incomplete")
    known = {r["id"] for r in cases}
    result: dict[str, dict[str, str]] = {}
    for item in entries:
        if type(item) is not dict or "id" not in item or type(item["id"]) is not str:
            raise ValueError("Invalid prediction")
        ident = item["id"]
        if ident not in known or ident in result:
            raise ValueError("Unknown or duplicate prediction")
        if item.get("status") == "abstain" and set(item) == {"id", "status"}:
            result[ident] = {"status": "abstain", "reason": "external_abstention"}
        elif item.get("status") == "proposed" and set(item) == {
                "id", "status", "concept", "field", "candidate_term", "review_state"}:
            candidate = {"contract": CANDIDATE_CONTRACT, "source_manifest_sha256": schema_manifest()["sha256"],
                         "mappings": [{k: item[k] for k in ("concept", "field", "candidate_term", "review_state")}]}
            validated = validate_mapping_candidate(candidate)
            m = validated["mappings"][0]
            result[ident] = {"status": "proposed", "concept": m["concept"], "field": m["field"]}
        else:
            raise ValueError("Rejected candidate output (possible SQL, patient values, or false review)")
    return result


def score(cases: list[dict[str, Any]], predictions: dict[str, dict[str, str]], label: str) -> dict[str, Any]:
    if not cases:
        raise ValueError("Cannot score an empty case set")
    if set(predictions) != {r["id"] for r in cases}:
        raise ValueError("Prediction and challenge sets differ")
    counts = {k: 0 for k in ("positive_correct", "positive_missed", "positive_wrong", "negative_abstained", "negative_false_mapping")}
    detail = []
    for row in cases:
        p = predictions[row["id"]]
        if p.get("status") not in ("abstain", "proposed"):
            raise ValueError("Invalid prediction status")
        if p["status"] == "proposed" and (p.get("concept"), p.get("field")) not in field_set():
            raise ValueError("Prediction references disallowed metadata")
        expected = row["expected"]
        if expected is None:
            key = "negative_abstained" if p["status"] == "abstain" else "negative_false_mapping"
        elif p["status"] == "abstain":
            key = "positive_missed"
        elif all(p[k] == expected[k] for k in ("concept", "field")):
            key = "positive_correct"
        else:
            key = "positive_wrong"
        counts[key] += 1
        detail.append({"id": row["id"], "category": row["category"], "outcome": key})
    positives = counts["positive_correct"]+counts["positive_missed"]+counts["positive_wrong"]
    negatives = counts["negative_abstained"]+counts["negative_false_mapping"]
    # A single-sided set leaves the other side's rate undefined; report None
    # rather than dividing by zero or inventing a 0.0. Validation requires
    # >=10 negatives, but score() is also called directly, so guard both.
    return {"name": label, "total": len(cases), "positives": positives, "negatives": negatives,
            **counts, "exact_accuracy": round((counts["positive_correct"]+counts["negative_abstained"])/len(cases),4),
            "positive_recall": round(counts["positive_correct"]/positives,4) if positives else None,
            "negative_abstention_rate": round(counts["negative_abstained"]/negatives,4) if negatives else None,
            "per_case_outcomes": detail}


def run(cases_payload: dict[str, Any], external_payload: Any = None) -> dict[str, Any]:
    cases = validate_cases(cases_payload)
    start = time.perf_counter_ns()
    baseline = {r["id"]: deterministic_baseline(r["question"]) for r in cases}
    duration_ns = time.perf_counter_ns()-start
    results = [score(cases, baseline, "first_party_deterministic_baseline")]
    if external_payload is not None:
        ext = validate_external_predictions(external_payload, cases)
        results.append(score(cases, ext, "external_offline_replay_unverified"))
    return {"contract": REPORT_CONTRACT, "manifest_sha256": schema_manifest()["sha256"],
            "case_set_sha256": digest(cases_payload), "synthetic": True,
            "clinical_validation": False, "vendor_runtime_executed": False,
            "external_predictions_source_verified": False,
            "sql_executed": False, "patient_data_accessed": False, "external_model_calls": 0,
            "baseline_wall_time_ms": round(duration_ns/1_000_000,3),
            "vendor_latency_cost": None, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline synthetic metadata benchmark")
    parser.add_argument("--cases", default="tests/fixtures/semantic_benchmark_cases_v1.json")
    parser.add_argument("--external-predictions", help="unverified external replay file; never contacts a service")
    parser.add_argument("--output", help="write local JSON report")
    args = parser.parse_args()
    try:
        cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
        external = json.loads(Path(args.external_predictions).read_text(encoding="utf-8")) if args.external_predictions else None
        report = run(cases, external)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
        return
    rendered = json.dumps(report, indent=2, sort_keys=True)+"\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
