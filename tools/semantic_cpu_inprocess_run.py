"""Actual CPU-weight inference in a network-disabled, no-gold sandbox.

This program is copied with only the approved first-party proposal validator
into a disposable research Docker image. The container is run with network=none
and mounts only the public fictional question packet and immutable model files.
No patient data, gold labels, EHR/clinical API, NVIDIA endpoint or SQL exists.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

import torch
from semantic_cpu_model_server import model, tokenizer, EXPECTED_MODEL_ID, MAX_GENERATION_TOKENS
from semantic_local_model_runner import evaluate_packet, request_body, validate_run
from semantic_question_packet import validate_packet

EXPECTED_MODEL_REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"


def run_only_synthetic(packet: dict, *, model_revision: str):
    if model_revision != EXPECTED_MODEL_REVISION:
        raise ValueError("Model revision does not match pinned experimental input")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise ValueError("Model must be offline")
    validation = validate_packet(packet)
    if validation["task_count"] != 72:
        raise ValueError("Unexpected question count")
    stats = []
    def infer(_url: str, raw_body: bytes, _timeout: float) -> bytes:
        request = json.loads(raw_body)
        if request["model"] != EXPECTED_MODEL_ID:
            raise ValueError("Wrong model request")
        messages = request["messages"]
        assert [m["role"] for m in messages] == ["system", "user"]
        assert len(messages) == 2
        tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                               return_tensors="pt")
        if tokens.shape[-1] > 1500:
            raise ValueError("Oversized synthetic prompt")
        cap = min(MAX_GENERATION_TOKENS, request["max_tokens"])
        started = time.perf_counter_ns()
        with torch.inference_mode():
            generated = model.generate(
                tokens, max_new_tokens=cap, do_sample=False, use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )[0, tokens.shape[-1]:]
        elapsed = round((time.perf_counter_ns() - started) / 1_000_000, 3)
        text = tokenizer.decode(generated, skip_special_tokens=True).strip()
        eos_ids = tokenizer.eos_token_id
        if not isinstance(eos_ids, list):
            eos_ids = [eos_ids]
        finished = generated.numel() < cap or (generated.numel() > 0 and int(generated[-1]) in eos_ids)
        stats.append({"ordinal": len(stats)+1,
                      "prompt_tokens": int(tokens.shape[-1]),
                      "completion_tokens": int(generated.numel()),
                      "model_compute_ms": elapsed})
        if len(stats) % 12 == 0:
            print(f"Synthetic inference progress: {len(stats)} of 72", flush=True)
        return json.dumps({
            "model": EXPECTED_MODEL_ID,
            "choices": [{"message": {"role": "assistant", "content": text},
                         "finish_reason": "stop" if finished else "length"}],
        }, separators=(",", ":"), ensure_ascii=True).encode()

    # Existing first-party harness retains only sanitized field labels + hashes,
    # never generated raw content, token secrets or clinical source statements.
    receipt = evaluate_packet(
        packet, url="http://127.0.0.1:18763/v1/chat/completions",
        model_id=EXPECTED_MODEL_ID, max_tasks=72, timeout_s=30,
        sender=infer,
    )
    checked = validate_run(receipt, packet)
    if not checked["complete"] or len(stats) != 72:
        raise ValueError("Model inference incomplete")
    summary = {
        "runtime_kind": "real_cpu_weights_inprocess_no_network",
        "model": EXPECTED_MODEL_ID,
        "model_revision": model_revision,
        "questions": len(stats),
        "actual_generated_token_count": sum(row["completion_tokens"] for row in stats),
        "actual_prompt_token_count": sum(row["prompt_tokens"] for row in stats),
        "aggregate_model_compute_ms": round(sum(row["model_compute_ms"] for row in stats),3),
        "nvidia_auto_ontology_inference": False,
        "model_provider_api_charge_usd": 0,
        "hosting_cpu_cost_unmeasured": True,
        "model_efficacy_validated": False,
        "clinical_validation": False,
        "model_outputs_do_not_authorize_clinical_actions": True,
        "per_task_token_and_latency": stats,
    }
    return receipt, summary


def main():
    parser = argparse.ArgumentParser(description="Actual CPU model, sealed synthetic-only sandbox")
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--expected-packet-sha256", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--token-report", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.token_report.exists():
        raise FileExistsError("Do not overwrite previous inference evidence")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    if packet.get("packet_sha256") != args.expected_packet_sha256:
        raise ValueError("Unapproved input packet digest")
    receipt, summary = run_only_synthetic(packet, model_revision=args.model_revision)
    with args.output.open("x", encoding="utf-8") as writer:
        json.dump(receipt, writer, sort_keys=True, indent=2)
        writer.write("\n")
    with args.token_report.open("x", encoding="utf-8") as writer:
        json.dump(summary, writer, sort_keys=True, indent=2)
        writer.write("\n")
    print("Actual CPU inference completed; 72 synthetic questions; no NVIDIA/clinical claims", flush=True)


if __name__ == "__main__":
    main()
