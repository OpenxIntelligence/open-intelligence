"""Pinned real Qwen2.5 0.5B weights: synthetic metadata research only.

These are separate from NVIDIA Auto Ontology and from clinical workflows.
The module is loaded exclusively inside the research image with network=none.
"""
from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

EXPECTED_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_PATH = "/weights"

torch.set_num_threads(2)
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    trust_remote_code=False,
)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    trust_remote_code=False,
    use_safetensors=True,
    torch_dtype=torch.float32,
).eval()
