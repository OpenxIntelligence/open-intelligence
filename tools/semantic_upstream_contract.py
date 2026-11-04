"""Offline, exact-upstream schema compatibility check for a zero-row OI sandbox.

No network, secrets, database writes, model calls, or NVIDIA service startup.
The upstream NVIDIA Pydantic schema is supplied by an operator or a separate
pinned-hash fetch step, not vendored into Open Intelligence application code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types
from typing import Any

from semantic_native_model import validate_native_model, verify_empty_sqlite

UPSTREAM_COMMIT = "cdaf61e1bd0cf3820d11d72b43bb460816aebbd3"
UPSTREAM_PATH = "auto_ontology/server/model_interchange/schemas.py"
UPSTREAM_BLOB = "8e00725dc481ac485b6c55105181fa163dea9ce5"
UPSTREAM_SHA256 = "54e3d56e3ffb1178d5b4bfc2872fce761ede8461c3d8ea0a753f7a0fa7ecfc39"
SCHEMA_MAX_BYTES = 16_384
MODEL_MAX_BYTES = 65_536
RECEIPT_CONTRACT = "oi.nvidia-schema-compat/1"


def _read_exact(path: Path, max_bytes: int) -> bytes:
    with path.open("rb") as source:
        value = source.read(max_bytes + 1)
    if len(value) > max_bytes:
        raise ValueError("File exceeds maximum allowed size")
    return value


def _load_pinned_upstream_schema(source: bytes):
    if hashlib.sha256(source).hexdigest() != UPSTREAM_SHA256:
        raise ValueError("NVIDIA upstream source SHA-256 differs from pinned version")
    sha1 = hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()
    if sha1 != UPSTREAM_BLOB:
        raise ValueError("NVIDIA upstream Git blob differs from pinned version")
    # Run only the byte-for-byte audited upstream schema, not arbitrary input.
    # It imports Pydantic and defines data contracts; no application connection.
    name = "oi_pinned_nvidia_schema_contract"
    module = types.ModuleType(name)
    module.__file__ = UPSTREAM_PATH
    sys.modules[name] = module  # Pydantic v2 resolves forward refs by module name.
    try:
        exec(compile(source, UPSTREAM_PATH, "exec"), module.__dict__)
        return module
    except BaseException:
        sys.modules.pop(name, None)
        raise


def check_model(upstream_schema: Path, model_path: Path, database_path: Path) -> dict[str, Any]:
    """Validate the exact empty synthetic model with NVIDIA's real Pydantic types.

    OI's strict allowlist is validated before passing a document to upstream.
    This guards against Pydantic's default ignoring unrecognized extra keys.
    """
    source = _read_exact(Path(upstream_schema), SCHEMA_MAX_BYTES)
    encoded = _read_exact(Path(model_path), MODEL_MAX_BYTES)
    try:
        payload = json.loads(encoded)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("The synthetic model must be strict JSON (YAML-compatible)") from exc
    if type(payload) is not dict:
        raise ValueError("Expected native model object")
    summary = validate_native_model(payload)  # no vendor parsing before this.
    zero_counts = verify_empty_sqlite(Path(database_path))
    module = _load_pinned_upstream_schema(source)
    try:
        document = module.AutoOntologyModelDocument.model_validate(payload)
        normalized = document.model_dump(mode="json")
        if normalized != payload:
            raise ValueError("Native Pydantic validation changed model content")

        # Negative probe: some upstream versions permit unknown keys by default.
        # Record this behavior, but never permit such data through OI's gate.
        candidate = {**payload, "unrecognized_private_field": "blocked"}
        try:
            vendor_extra = module.AutoOntologyModelDocument.model_validate(candidate)
            upstream_extra_policy = (
                "ignored_unknown_key" if vendor_extra.model_dump(mode="json") == normalized
                else "preserved_unknown_key"
            )
        except Exception:
            upstream_extra_policy = "rejected_unknown_key"
        try:
            validate_native_model(candidate)
        except ValueError:
            oi_extra_rejected = True
        else:
            raise ValueError("OI allowlist did not reject an unknown field")
    finally:
        sys.modules.pop(module.__name__, None)

    return {
        "contract": RECEIPT_CONTRACT,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_git_blob_sha1": UPSTREAM_BLOB,
        "upstream_source_sha256": UPSTREAM_SHA256,
        "model_bytes_sha256": hashlib.sha256(encoded).hexdigest(),
        "synthetic": True,
        "strict_oi_validation": True,
        "nvidia_pydantic_validation": True,
        "byte_equivalent_roundtrip": normalized == payload,
        "oi_rejected_unknown_root_key": oi_extra_rejected,
        "nvidia_unknown_root_key_policy": upstream_extra_policy,
        "tables": summary["table_count"],
        "columns": summary["column_count"],
        "terms": summary["term_count"],
        "sqlite_total_rows": sum(zero_counts.values()),
        "nvidia_app_started": False,
        "nvidia_catalog_imported": False,
        "nvidia_inference_called": False,
        "patient_data_used": False,
        "clinical_validation": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a pinned NVIDIA interchange schema, offline")
    parser.add_argument("--upstream-schema", type=Path, required=True)
    parser.add_argument("--native-model", type=Path, required=True)
    parser.add_argument("--empty-sqlite", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        receipt = check_model(args.upstream_schema, args.native_model, args.empty_sqlite)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
