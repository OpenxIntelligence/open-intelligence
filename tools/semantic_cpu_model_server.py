"""Minimal actual-weight CPU model serving a synthetic-only OpenAI-shaped interface.

This module is used *only* inside a disposable Docker image built from this
single file, not the Open Intelligence application or NVIDIA Auto Ontology.
No agent tools, SQL, model downloads, authentication, patient records, or
retrieval exist in this server. Model files must already be locally mounted.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_PATH = "/weights"
EXPECTED_MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
MAX_BODY = 8192
MAX_PROMPT_TOKENS = 1500
MAX_GENERATION_TOKENS = 64

torch.set_num_threads(2)
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH, local_files_only=True, trust_remote_code=False
)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH, local_files_only=True, trust_remote_code=False,
    use_safetensors=True, torch_dtype=torch.float32,
).eval()


class Handler(BaseHTTPRequestHandler):
    """Scripted API shape only; every response derives from actual weights."""

    def log_message(self, _fmt, *_args):
        return  # Do not accidentally print questions or generated model text.

    def reply(self, status: int, data: dict) -> None:
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health/live":
            self.reply(200, {"ready": True, "model_kind": "actual_cpu_weights"})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.reply(404, {"error": "not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if size < 1 or size > MAX_BODY:
                raise ValueError("Invalid request size")
            raw = self.rfile.read(size)
            body = json.loads(raw)
            if type(body) is not dict or set(body) != {
                "model", "temperature", "stream", "max_tokens", "messages",
            }:
                raise ValueError("Unexpected request shape")
            if (body["model"] != EXPECTED_MODEL_ID
                    or body["temperature"] != 0
                    or body["stream"] is not False
                    or type(body["max_tokens"]) is not int
                    or not 1 <= body["max_tokens"] <= 128):
                raise ValueError("Unexpected inference config")
            messages = body["messages"]
            if (type(messages) is not list or len(messages) != 2
                    or [m.get("role") for m in messages] != ["system", "user"]
                    or any(type(m) is not dict or set(m) != {"role", "content"}
                           or type(m["content"]) is not str
                           for m in messages)):
                raise ValueError("Unexpected message content")
            tokens = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                return_tensors="pt",
            )
            if tokens.shape[-1] > MAX_PROMPT_TOKENS:
                raise ValueError("Oversized prompt")
            cap = min(body["max_tokens"], MAX_GENERATION_TOKENS)
        except (ValueError, TypeError, KeyError, AttributeError):
            self.reply(400, {"error": "invalid synthetic-only request"})
            return
        try:
            with torch.inference_mode():
                output = model.generate(
                    tokens, max_new_tokens=cap, do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    use_cache=True,
                )
            generated = output[0, tokens.shape[-1]:]
            text = tokenizer.decode(generated, skip_special_tokens=True).strip()
            eos_ids = tokenizer.eos_token_id
            if not isinstance(eos_ids, list):
                eos_ids = [eos_ids]
            stop = generated.numel() < cap or (generated.numel() > 0 and int(generated[-1]) in eos_ids)
            self.reply(200, {
                "model": EXPECTED_MODEL_ID,
                "choices": [{
                    "index": 0, "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop" if stop else "length",
                }],
                "usage": {
                    "prompt_tokens": int(tokens.shape[-1]),
                    "completion_tokens": int(generated.numel()),
                },
            })
        except Exception:
            self.reply(500, {"error": "local inference failed"})


if __name__ == "__main__":
    print("Loaded pinned local CPU weights; synthetic prompts only", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 18763), Handler).serve_forever()
