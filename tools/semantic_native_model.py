"""Native NVIDIA Auto Ontology metadata-only sandbox artifacts (offline).

The output matches the *shape* of NVIDIA's AutoOntologyModelDocument at the
pinned upstream commit; it has not been imported by a running NVIDIA instance.
No credentials, live databases, model endpoints, PHI, rows, joins, SQL, or egress.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from semantic_contract_probe import schema_manifest

UPSTREAM_REPO = "NVIDIA/auto-ontology"
UPSTREAM_SHA = "cdaf61e1bd0cf3820d11d72b43bb460816aebbd3"
DB_NAME = "oi_metadata_sandbox"
DB_ID = "oi_metadata_sandbox_database_v1"
SCHEMA_ID = "oi_metadata_sandbox_schema_v1"
MODEL_FILENAME = "oi_native_model.yaml"
DB_FILENAME = DB_NAME + ".sqlite"
RECEIPT_FILENAME = "receipt.json"


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                      allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _table_id(concept: str) -> str:
    return "oi_sandbox_table_" + concept


def _column_id(concept: str, field: str) -> str:
    return "oi_sandbox_col_" + concept + "_" + field


def _field_type(field: str) -> str:
    return "INTEGER" if field in ("version", "source_line") else "TEXT"


def native_model_document() -> dict[str, Any]:
    """Build a deterministic *native format* document with curated field names.

    No generated inference or authorization is represented as clinical truth;
    even these curated semantic labels are not a patient knowledge graph.
    """
    manifest = schema_manifest()
    tables: list[dict[str, Any]] = []
    terms: list[dict[str, Any]] = []
    for concept in manifest["concepts"]:
        name = concept["concept"]
        table_id = _table_id(name)
        columns = [{"id": _column_id(name, field), "name": field,
                    "description": "", "type": _field_type(field),
                    "sample_values": [], "is_nullable": True, "is_unique": False}
                   for field in concept["fields"]]
        tables.append({"id": table_id, "name": name, "description": "",
                       "pk": [], "type": "base table", "columns": columns})
        terms.append({"id": "oi_sandbox_term_" + name,
                      "name": "oi_synthetic_" + name, "description": "",
                      "represents": [table_id],
                      "columns_attributes": [
                          {"id": "oi_sandbox_attr_" + name + "_" + field,
                           "name": field, "description": "", "column_id": _column_id(name, field)}
                          for field in concept["fields"]]})
    return {
        "data_layer": {
            "databases": [{"id": DB_ID, "dialect": "sqlite",
                           "schemas": [{"id": SCHEMA_ID, "name": "main",
                                        "database_name": DB_NAME, "tables": tables}]}],
            "foreign_keys": [], "joins": [],
        },
        "semantic_layer": {
            "terms": terms, "semantic_fks": [],
            "sql_attributes": {"manual": [], "table": [], "sql": [], "bridge_table": []},
            "custom_analyses": [],
        },
        "zones": [],
    }


def validate_native_model(value: Any) -> dict[str, Any]:
    """Reject any model content beyond the *exact* approved synthetic schema.

    Not a validator for arbitrary NVIDIA exports or model-generated semantics.
    Imported metadata must be approved separately; do not leak unexpected input.
    """
    if type(value) is not dict or value != native_model_document():
        raise ValueError("Native model differs from approved zero-data sandbox")
    tables = value["data_layer"]["databases"][0]["schemas"][0]["tables"]
    return {"table_count": len(tables),
            "column_count": sum(len(t["columns"]) for t in tables),
            "term_count": len(value["semantic_layer"]["terms"]),
            "native_model_sha256": _digest(value)}


def _create_empty_sqlite(path: Path) -> None:
    """Create only unpopulated schema tables in a newly named local file."""
    if path.exists() or path.is_symlink():
        raise FileExistsError("Refusing to replace existing sandbox database")
    manifest = schema_manifest()
    connection = sqlite3.connect(str(path))
    try:
        for concept in manifest["concepts"]:
            columns = ", ".join('"' + f + '" ' + _field_type(f)
                                for f in concept["fields"])
            # All identifiers came from the internal static manifest.
            connection.execute('CREATE TABLE "' + concept["concept"] + '" (' + columns + ')')
        connection.commit()
    finally:
        connection.close()
    path.chmod(0o444)  # additionally mount :ro; root may still bypass file mode


def verify_empty_sqlite(path: Path) -> dict[str, int]:
    """Read the synthetic file in SQLite's read-only mode and ensure zero rows."""
    if not path.is_file():
        raise ValueError("No sandbox SQLite database")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        known = schema_manifest()["concepts"]
        table_names = [r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        if table_names != sorted(c["concept"] for c in known):
            raise ValueError("Unexpected sandbox tables")
        results: dict[str, int] = {}
        for concept in known:
            name = concept["concept"]
            actual_fields = [r[1] for r in connection.execute(f'PRAGMA table_info("{name}")')]
            if actual_fields != concept["fields"]:
                raise ValueError("Unexpected sandbox columns")
            count = connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            if count != 0:
                raise ValueError("Nonempty table in metadata-only sandbox")
            results[name] = count
        return results
    finally:
        connection.close()


def write_sandbox(directory: Path) -> dict[str, Any]:
    """Fail closed if the output path already exists; no vendor/runtime calls."""
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise FileExistsError("Sandbox destination already exists; refusing overwrite")
    directory.mkdir(parents=False)
    try:
        document = native_model_document()
        summary = validate_native_model(document)
        model_path = directory / MODEL_FILENAME
        # JSON is a YAML-compatible mapping for NVIDIA's yaml.safe_load importer.
        # No YAML dependency or arbitrary document tags are introduced here.
        model_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if validate_native_model(json.loads(model_path.read_text(encoding="utf-8"))) != summary:
            raise ValueError("Native model readback mismatch")
        db_path = directory / DB_FILENAME
        _create_empty_sqlite(db_path)
        counts = verify_empty_sqlite(db_path)
        receipt = {
            "contract": "oi.synthetic-native-ontology-sandbox/1",
            "upstream_repo": UPSTREAM_REPO, "upstream_sha": UPSTREAM_SHA,
            "schema_manifest_sha256": schema_manifest()["sha256"],
            **summary,
            "synthetic": True, "patient_rows": sum(counts.values()),
            "database_connectivity": "local_sqlite_read_only",
            "vendor_runtime_executed": False,
            "model_endpoint_called": False, "clinical_validation": False,
            "sql_generated_or_executed_by_agent": False,
            "data_samples_included": False,
        }
        (directory / RECEIPT_FILENAME).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                                     encoding="utf-8")
        return receipt
    except BaseException:
        shutil.rmtree(directory)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a zero-row NVIDIA-native metadata sandbox")
    parser.add_argument("--output-dir", required=True, type=Path, help="new directory; never overwritten")
    args = parser.parse_args()
    try:
        receipt = write_sandbox(args.output_dir)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
        return
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
