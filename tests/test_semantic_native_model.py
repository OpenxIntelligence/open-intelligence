"""Zero-row, offline NVIDIA-native metadata model boundary verification."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("semantic_native_model", ROOT / "tools" / "semantic_native_model.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class NativeModelTests(unittest.TestCase):
    def setUp(self):
        self.document = mod.native_model_document()

    def test_native_schema_is_exactly_three_concepts_and_22_columns(self):
        self.assertEqual(mod.validate_native_model(self.document)["table_count"], 3)
        self.assertEqual(mod.validate_native_model(self.document)["column_count"], 22)
        self.assertEqual(mod.validate_native_model(self.document)["term_count"], 3)
        self.assertEqual(set(self.document), {"data_layer", "semantic_layer", "zones"})
        self.assertEqual(self.document["data_layer"]["databases"][0]["dialect"], "sqlite")

    def test_model_has_no_values_sql_joins_or_out_of_scope_databases(self):
        self.assertEqual(self.document["data_layer"]["joins"], [])
        self.assertEqual(self.document["data_layer"]["foreign_keys"], [])
        self.assertEqual(self.document["semantic_layer"]["semantic_fks"], [])
        self.assertEqual(self.document["semantic_layer"]["custom_analyses"], [])
        self.assertEqual(self.document["semantic_layer"]["sql_attributes"],
                         {"manual": [], "table": [], "sql": [], "bridge_table": []})
        self.assertEqual(self.document["zones"], [])
        self.assertNotIn("patient_id", json.dumps(self.document))
        for table in self.document["data_layer"]["databases"][0]["schemas"][0]["tables"]:
            self.assertTrue(all(col["sample_values"] == [] for col in table["columns"]))

    def test_ids_and_references_are_stable_and_scoped(self):
        self.assertEqual(self.document, mod.native_model_document())
        tables = self.document["data_layer"]["databases"][0]["schemas"][0]["tables"]
        ids = {table["id"] for table in tables}
        colids = {column["id"] for table in tables for column in table["columns"]}
        self.assertEqual(len(colids), 22)
        self.assertEqual(len(ids), 3)
        for term in self.document["semantic_layer"]["terms"]:
            self.assertEqual(len(term["represents"]), 1)
            self.assertIn(term["represents"][0], ids)
            self.assertTrue(all(attr["column_id"] in colids for attr in term["columns_attributes"]))

    def test_json_interchange_is_round_trippable_and_unreviewed(self):
        serialized = json.dumps(self.document, sort_keys=True)
        self.assertEqual(mod.validate_native_model(json.loads(serialized)), mod.validate_native_model(self.document))
        self.assertNotIn("clinical_review_authorized", serialized)

    def test_changed_column_or_sample_is_refused(self):
        for key, value in (("name", "patient_name"), ("sample_values", ["sensitive"])):
            changed = copy.deepcopy(self.document)
            changed["data_layer"]["databases"][0]["schemas"][0]["tables"][0]["columns"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.validate_native_model(changed)

    def test_injected_sql_and_generated_joins_are_refused(self):
        for key, addition in (("joins", [{"source_table_id": "a", "target_table_id": "b"}]),
                              ("foreign_keys", [{"source_column_id": "a", "target_column_id": "b"}])):
            changed = copy.deepcopy(self.document)
            changed["data_layer"][key] = addition
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.validate_native_model(changed)
        changed = copy.deepcopy(self.document)
        changed["semantic_layer"]["custom_analyses"] = [{"sql": "select * from patients"}]
        with self.assertRaises(ValueError):
            mod.validate_native_model(changed)

    def test_unapproved_term_and_database_are_refused(self):
        changed = copy.deepcopy(self.document)
        changed["semantic_layer"]["terms"][0]["name"] = "clinical diagnosis"
        with self.assertRaises(ValueError):
            mod.validate_native_model(changed)
        changed = copy.deepcopy(self.document)
        changed["data_layer"]["databases"].append(changed["data_layer"]["databases"][0])
        with self.assertRaises(ValueError):
            mod.validate_native_model(changed)

    def test_sqlite_fixture_is_zero_row_and_readable_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sandbox"
            receipt = mod.write_sandbox(out)
            self.assertEqual(receipt["patient_rows"], 0)
            self.assertFalse(receipt["vendor_runtime_executed"])
            self.assertFalse(receipt["model_endpoint_called"])
            self.assertFalse(receipt["data_samples_included"])
            self.assertEqual(len(mod.verify_empty_sqlite(out / mod.DB_FILENAME)), 3)
            connection = sqlite3.connect((out / mod.DB_FILENAME).resolve().as_uri() + "?mode=ro", uri=True)
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute('INSERT INTO source_version (source_id) VALUES ("x")')
            connection.close()
            self.assertEqual(json.loads((out / mod.MODEL_FILENAME).read_text()), self.document)
            self.assertEqual(json.loads((out / mod.RECEIPT_FILENAME).read_text()), receipt)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "sandbox"
            first = mod.write_sandbox(folder)
            with self.assertRaises(FileExistsError):
                mod.write_sandbox(folder)
            self.assertEqual(json.loads((folder / mod.RECEIPT_FILENAME).read_text()), first)

    def test_nonempty_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "sandbox"
            mod.write_sandbox(folder)
            db = folder / mod.DB_FILENAME
            db.chmod(0o644)
            with sqlite3.connect(db) as con:
                con.execute('INSERT INTO source_version (source_id) VALUES (?)', ("made-up",))
            with self.assertRaises(ValueError):
                mod.verify_empty_sqlite(db)


if __name__ == "__main__":
    unittest.main()
