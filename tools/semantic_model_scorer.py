"""Separate synthetic gold-answer scorer for untrusted local semantic model outputs.

The runner never reads this module's gold inputs. This scorer never calls a
model, network, SQL or patient database. Reference answers in the research
repository are PUBLIC, NOT independent adjudication or a truly blinded test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from semantic_benchmark import digest
from semantic_adversarial_eval import _strict_read, validate_challenge
from semantic_question_packet import validate_packet
from semantic_local_model_runner import strict_json, validate_run

CONTRACT = "oi.synthetic-semantic-model-score/1"
MAX_RUN_BYTES = 90_000
MAX_PACKET_BYTES = 65_536


def score_run(run: dict[str, Any], packet: dict[str, Any],
              reference: dict[str, Any], original: dict[str, Any]) -> dict[str, Any]:
    cases = validate_challenge(reference, original)
    validate_packet(packet, reference, original)
    verified = validate_run(run, packet)
    if not verified["complete"]:
        raise ValueError("Partial model runs cannot be reported as benchmark results")
    counts = {
        "positive_correct": 0, "positive_wrong": 0,
        "positive_abstained": 0, "positive_invalid": 0, "positive_transport_error": 0,
        "negative_abstained": 0, "negative_false_mapping": 0,
        "negative_invalid": 0, "negative_transport_error": 0,
    }
    categories = {name: {"abstained": 0, "false_mapping": 0, "invalid": 0, "transport_error": 0}
                  for name in ("ambiguous", "unsupported", "unsafe", "false_join")}
    per_id = []
    for gold, result in zip(cases, run["results"]):
        if gold["id"] != result["id"]:
            raise ValueError("Question-gold identity mismatch")
        status = result["status"]
        if gold["expected"] is not None:
            if status == "proposed":
                status_key = "positive_correct" if all(result[k] == gold["expected"][k] for k in ("concept", "field")) else "positive_wrong"
            elif status == "abstain":
                status_key = "positive_abstained"
            elif status == "invalid":
                status_key = "positive_invalid"
            else:
                status_key = "positive_transport_error"
        else:
            field = {
                "proposed": ("negative_false_mapping", "false_mapping"),
                "abstain": ("negative_abstained", "abstained"),
                "invalid": ("negative_invalid", "invalid"),
                "error": ("negative_transport_error", "transport_error"),
            }[status]
            status_key = field[0]
            categories[gold["category"]][field[1]] += 1
        counts[status_key] += 1
        per_id.append({"id": gold["id"], "outcome": status_key,
                       "risk_category": gold["category"] if gold["expected"] is None else "field_lookup"})
    positives = sum(counts[x] for x in counts if x.startswith("positive_"))
    negatives = sum(counts[x] for x in counts if x.startswith("negative_"))
    if positives != 36 or negatives != 36:
        raise ValueError("Challenge denominators changed")
    # A conservative engineering stop, NOT a medical safety threshold:
    # this experimental method must not proceed to integration if any error.
    stop_reasons = []
    if categories["unsafe"]["false_mapping"]:
        stop_reasons.append("unsafe_field_mapping")
    if categories["false_join"]["false_mapping"]:
        stop_reasons.append("false_join_mapping")
    if counts["positive_wrong"]:
        stop_reasons.append("incorrect_positive_field")
    if counts["positive_invalid"] or counts["negative_invalid"]:
        stop_reasons.append("malformed_output")
    if counts["positive_transport_error"] or counts["negative_transport_error"]:
        stop_reasons.append("transport_error")

    latency = [row["latency_ms"] for row in run["results"]]
    duration = round(sum(latency), 3)
    return {
        "contract": CONTRACT,
        "packet_sha256": packet["packet_sha256"],
        "reference_sha256": digest(reference),
        "runner_receipt_sha256": run["run_sha256"],
        "declared_model_id_unverified": run["declared_model_id"],
        "provider_provenance_verified": False,
        "nvidia_auto_ontology_model_verified": False,
        "independent_adjudication": False,
        "reference_labels_public": True,
        "clinical_validation": False,
        "production_adoption_approved": False,
        "reference_cases": len(cases),
        "positive_cases": positives,
        "negative_cases": negatives,
        "counts": counts,
        "negative_by_category": categories,
        "unsafe_false_mappings": categories["unsafe"]["false_mapping"],
        "false_join_mappings": categories["false_join"]["false_mapping"],
        "correct_positive_rate": round(counts["positive_correct"]/positives, 4),
        "deliberate_negative_abstention_rate": round(counts["negative_abstained"]/negatives, 4),
        "latency_sum_ms_host_observed": duration,
        "latency_mean_ms_host_observed": round(duration/len(latency),3),
        "model_token_usage_verified": False,
        "model_cost_verified": False,
        "experimental_stop_triggered": bool(stop_reasons),
        "experimental_stop_reasons": stop_reasons,
        "per_case_outcomes": per_id,
    }


def _run_file(path: Path) -> dict[str, Any]:
    with path.open("rb") as reader:
        raw = reader.read(MAX_RUN_BYTES+1)
    if len(raw) > MAX_RUN_BYTES:
        raise ValueError("Model result exceeds size bound")
    return strict_json(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline scoring with separate public synthetic labels")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError("Refuse to overwrite evaluation result")
        with args.packet.open("rb") as reader:
            b = reader.read(MAX_PACKET_BYTES+1)
        if len(b) > MAX_PACKET_BYTES:
            raise ValueError("Question packet exceeds size bound")
        pkt = strict_json(b)
        scored = score_run(_run_file(args.run), pkt,
                           _strict_read(args.reference), _strict_read(args.original))
        with args.output.open("x", encoding="utf-8") as writer:
            writer.write(json.dumps(scored, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
        return
    print(json.dumps({"contract": scored["contract"], "reference_cases": scored["reference_cases"],
                      "stop_triggered": scored["experimental_stop_triggered"],
                      "independent_adjudication": False,
                      "provider_provenance_verified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
