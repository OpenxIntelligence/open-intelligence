"""Actual pinned CPU model, single-token masked field-option classification.

This RESEARCH-ONLY runner executes genuine weights (one forward pass per
fictional question) in a Docker --network none image, with only the labels-free
question packet and weights mounted. It NEVER generates free-form JSON or SQL.
No patient data, external inference keys, gold labels or EHR access.

Restricted choice probability is not calibrated clinical confidence and a
forced option is not evidence of correct semantics or safe patient action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

import torch

from semantic_cpu_model_server import model, tokenizer, EXPECTED_MODEL_ID
from semantic_choice_contract import (
    METHOD, ABSTAIN_CODE, MODEL_CHOICE_COUNT, build_choices,
    task_messages, token_ids, choice_to_proposal,
)
from semantic_question_packet import validate_packet
from semantic_local_model_runner import CONTRACT as RUN_CONTRACT, validate_run
from semantic_benchmark import digest

EXPECTED_MODEL_REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
MAX_PROMPT_TOKENS = 1500
MAX_PACKET_BYTES = 65536


def choose_one(task: dict[str, str], packet: dict, options: list[dict[str, str]],
               allowed_token_ids: list[int]) -> tuple[dict[str, str], dict]:
    messages = task_messages(task, options)
    tokens = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt",
    )
    if tokens.shape[-1] > MAX_PROMPT_TOKENS:
        raise ValueError("Prompt too long for sealed model evaluation")
    started = time.perf_counter_ns()
    with torch.inference_mode():
        logits = model(input_ids=tokens, use_cache=False).logits[0, -1].float()
        subset = logits[torch.tensor(allowed_token_ids, dtype=torch.int64)]
        if not bool(torch.isfinite(subset).all()):
            raise ValueError("Non-finite next-token logits")
        probabilities = torch.softmax(subset, dim=0)
        winner = int(torch.argmax(subset).item())
        ordered = torch.topk(subset, k=2).values
    elapsed = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    code = options[winner]["code"]
    proposal = choice_to_proposal(code, options, packet["schema_manifest_sha256"])
    # This is a hash of a *constrained token selection record*, not a raw LLM
    # JSON completion, provider-signed receipt or free-text transcript.
    record_bytes = json.dumps({
        "one_token_choice": code,
        "token_id": allowed_token_ids[winner],
        "method": METHOD,
    }, sort_keys=True, separators=(",", ":")).encode()
    proposal["response_sha256"] = hashlib.sha256(record_bytes).hexdigest()
    stats = {
        "id": task["id"],
        "selected_code": code,
        "selected_token_id": allowed_token_ids[winner],
        "selected_field_or_abstain": proposal["status"],
        "prompt_token_count": int(tokens.shape[-1]),
        "model_choice_token_count": 1,
        "model_compute_ms": elapsed,
        "restricted_23_choice_probability_uncalibrated": round(float(probabilities[winner]), 6),
        "restricted_top_two_logit_margin": round(float(ordered[0] - ordered[1]), 6),
    }
    if not math.isfinite(stats["model_compute_ms"]):
        raise ValueError("Invalid model timing")
    return proposal, stats


def run(packet: dict, *, model_revision: str) -> tuple[dict, dict]:
    if model_revision != EXPECTED_MODEL_REVISION:
        raise ValueError("Wrong model weights revision")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise ValueError("Local model MUST run offline")
    validate_packet(packet)
    options = build_choices(packet)
    labels = token_ids(tokenizer, options)
    rows = []
    stats = []
    for task in packet["tasks"]:
        proposal, meta = choose_one(task, packet, options, labels)
        # These are real model logits, constrained to exactly 23 predeclared
        # tokens. The structured mapping is a deterministic postprocessor.
        rows.append({"id": task["id"], "latency_ms": meta["model_compute_ms"], **proposal})
        stats.append(meta)
        if len(rows) % 12 == 0:
            print(f"Constrained real-weight classification: {len(rows)}/72", flush=True)
    receipt = {
        "contract": RUN_CONTRACT,
        "packet_sha256": packet["packet_sha256"],
        "schema_manifest_sha256": packet["schema_manifest_sha256"],
        "declared_model_id": EXPECTED_MODEL_ID,
        "endpoint_kind": "inprocess_masked_logits_no_network",
        "endpoint_port": 0,
        "total_questions": 72,
        "attempted_questions": len(rows),
        "complete": len(rows) == 72,
        "source_attestation": "self_reported_unsigned",
        "nvidia_auto_ontology_verified": False,
        "model_weights_verified": False,  # separate host-side pinned hash receipt
        "no_patient_records_in_packet": True,
        "raw_responses_retained": False,
        "cost_verified": False,
        "results": rows,
    }
    receipt["run_sha256"] = digest(receipt)
    validate_run(receipt, packet)
    evidence = {
        "contract": "oi.synthetic-masked-next-token-evidence/1",
        "method": METHOD,
        "model_name": EXPECTED_MODEL_ID,
        "model_revision": model_revision,
        "model_input": "synthetic_schema_names_and_fictional_questions_only",
        "choices": options,
        "candidate_token_ids": labels,
        "questions": len(stats),
        "unconstrained_freeform_json_generated": False,
        "actual_model_forward_passes": len(stats),
        "generated_text_tokens": 0,
        "forced_choice_tokens": len(stats),
        "prompt_tokens": sum(x["prompt_token_count"] for x in stats),
        "total_model_compute_ms": round(sum(x["model_compute_ms"] for x in stats),3),
        "nvidia_model_or_auto_ontology_inference": False,
        "clinical_validation": False,
        "network_interfaces_available": False,
        "host_compute_cost_unmeasured": True,
        "model_choice_probabilities_are_calibrated": False,
        "run_sha256": receipt["run_sha256"],
        "per_task": stats,
    }
    return receipt, evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Real pinned CPU model: forced field or abstain, offline")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--expected-packet-sha256", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if any(p.exists() or p.is_symlink() for p in (args.output, args.evidence)):
        raise FileExistsError("Cannot overwrite previous model-run evidence")
    with args.packet.open("rb") as source:
        b = source.read(MAX_PACKET_BYTES + 1)
    if len(b) > MAX_PACKET_BYTES:
        raise ValueError("Question packet oversized")
    packet = json.loads(b)
    if packet.get("packet_sha256") != args.expected_packet_sha256:
        raise ValueError("Unapproved question packet")
    run_receipt, evidence = run(packet, model_revision=args.model_revision)
    for path, payload in ((args.output, run_receipt), (args.evidence, evidence)):
        with path.open("x", encoding="utf-8") as dest:
            json.dump(payload, dest, sort_keys=True, indent=2, allow_nan=False)
            dest.write("\n")
    print("Pinned real-weight masked-logit classification finished; no freeform generation", flush=True)


if __name__ == "__main__":
    main()
