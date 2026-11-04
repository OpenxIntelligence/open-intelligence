"""Disposable NVIDIA Auto Ontology catalog import experiment, synthetic only.

This file is NEVER part of the clinical API. It requires an explicitly named
localhost PostgreSQL sandbox, an unpopulated OI SQLite fixture, an allowlisted
metadata document and disabled model/embedding credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from semantic_native_model import validate_native_model, verify_empty_sqlite

CONTRACT = "oi.nvidia-disposable-import/1"
SANDBOX_DB = "oi_nvidia_import_sandbox"
SANDBOX_USER = "oi_sandbox_ci"
EXPECTED_COUNTS = {
    "catalog_database": 1,
    "catalog_schema": 1,
    "catalog_table": 3,
    "catalog_column": 22,
    "term": 3,
    "column_attribute": 22,
    "column__foreign_key": 0,
    "table__join": 0,
    "sql_attribute": 0,
    "custom_analysis": 0,
}


def _preflight() -> None:
    if os.environ.get("OI_DISPOSABLE_VENDOR_IMPORT") != "ONLY_SYNTHETIC_AND_EMPTY":
        raise ValueError("Disposable import gate not enabled")
    if os.environ.get("POSTGRES_HOST") not in ("localhost", "127.0.0.1"):
        raise ValueError("Vendor database must be localhost")
    if os.environ.get("POSTGRES_DATABASE") != SANDBOX_DB:
        raise ValueError("Unexpected vendor sandbox database")
    if os.environ.get("POSTGRES_USER") != SANDBOX_USER:
        raise ValueError("Unexpected sandbox database user")
    if os.environ.get("POSTGRES_PORT", "5432") != "5432":
        raise ValueError("Unexpected database port")
    if not os.environ.get("POSTGRES_PASSWORD"):
        raise ValueError("Synthetic sandbox password not set")
    for key in (
        "CONNECTION_STRINGS", "NVIDIA_API_KEY", "DEFAULT_MODELS_API_KEY",
        "REASONING_API_KEY", "NON_REASONING_API_KEY", "EMBED_API_KEY", "RERANK_API_KEY",
    ):
        if os.environ.get(key):
            raise ValueError("External connection or model credentials disallowed")


def _counts(connection) -> dict[str, int]:
    # Fixed table names, no LLM SQL, only the isolated vendor catalog database.
    with connection.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db_name, username = cur.fetchone()
        if db_name != SANDBOX_DB or username != SANDBOX_USER:
            raise ValueError("Wrong database principal or catalog")
        counts: dict[str, int] = {}
        for name in EXPECTED_COUNTS:
            cur.execute('SELECT COUNT(*) FROM public."' + name + '"')
            counts[name] = cur.fetchone()[0]
        return counts


def run(model_path: Path, sqlite_path: Path) -> dict:
    _preflight()
    raw = Path(model_path).read_bytes()
    if len(raw) > 65_536:
        raise ValueError("Native model exceeds 64 KiB limit")
    model = json.loads(raw)
    summary = validate_native_model(model)
    if (summary["table_count"], summary["column_count"], summary["term_count"]) != (3, 22, 3):
        raise ValueError("Unexpected allowlist size")
    if any(verify_empty_sqlite(Path(sqlite_path)).values()):
        raise ValueError("Nonempty clinical-looking fixture forbidden")

    # Import only AFTER strict first-party authorization-free metadata checks.
    import psycopg
    from auto_ontology.server.model_interchange import service
    from auto_ontology.server.model_interchange.schemas import ExportRequest

    conn = psycopg.connect(
        host=os.environ["POSTGRES_HOST"], port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DATABASE"], connect_timeout=3,
    )
    try:
        before = _counts(conn)
        if any(before.values()):
            raise ValueError("Vendor sandbox catalog is not empty")

        # These are actual NVIDIA service/importer calls, not a Pydantic mock.
        first = service.import_model(raw.decode("utf-8"), replace=False, embed=False)
        if first.get("format") != "auto_ontology" or first.get("replace") is not False:
            raise ValueError("Vendor import did not respect safe options")
        if first.get("created") != {
            "databases": 1, "schemas": 1, "tables": 3, "columns": 22,
            "terms": 3, "column_attributes": 22, "sql_attributes": 0, "custom_analyses": 0,
        }:
            raise ValueError("Unexpected vendor import entity counts")
        after_first = _counts(conn)
        if after_first != EXPECTED_COUNTS:
            raise ValueError("Unexpected vendor catalog contents after import")
        if len(first.get("database_ids", [])) != 1:
            raise ValueError("Expected exactly one imported database")

        second = service.import_model(raw.decode("utf-8"), replace=False, embed=False)
        if any(second.get("created", {}).values()):
            raise ValueError("Second vendor import was not idempotent")
        if _counts(conn) != after_first:
            raise ValueError("Second vendor import changed catalog counts")

        # Use NVIDIA's own export path; this MAY detect an extra connector or
        # global catalog scope bug, which fails rather than returning rows.
        yaml_model = service.export_model(ExportRequest(databases=first["database_ids"]))
        import yaml
        exported = yaml.safe_load(yaml_model)
        if type(exported) is not dict or set(exported) != {"data_layer", "semantic_layer", "zones"}:
            raise ValueError("Vendor exported wrong model shape")
        assert len(exported["data_layer"]["databases"]) == 1
        tables = exported["data_layer"]["databases"][0]["schemas"][0]["tables"]
        terms = exported["semantic_layer"]["terms"]
        if (len(tables), sum(len(t["columns"]) for t in tables), len(terms)) != (3, 22, 3):
            raise ValueError("Vendor export lost fields or terms")
        if any(c.get("sample_values") for t in tables for c in t["columns"]):
            raise ValueError("Vendor export included unexpected samples")
        if exported["data_layer"]["foreign_keys"] or exported["data_layer"]["joins"]:
            raise ValueError("Vendor generated unauthorized join")
        if any(exported["semantic_layer"]["sql_attributes"].values()) or exported["semantic_layer"]["custom_analyses"]:
            raise ValueError("Vendor generated SQL or analyses")
        return {
            "contract": CONTRACT,
            "synthetic": True,
            "vendor_importer_executed": True,
            "vendor_exporter_executed": True,
            "vendor_first_created": first["created"],
            "vendor_second_created": second["created"],
            "vendor_catalog_counts": after_first,
            "zero_source_rows": True,
            "model_inference_executed": False,
            "embeddings_executed": False,
            "production_connections_used": False,
            "clinical_validation": False,
        }
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Isolated NVIDIA vendor PG catalog test (never patient data)")
    ap.add_argument("--native-model", type=Path, required=True)
    ap.add_argument("--empty-sqlite", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    result = run(a.native_model, a.empty_sqlite)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("Vendor import/export synthetic-only check completed; full receipt saved locally")


if __name__ == "__main__":
    main()
