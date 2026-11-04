"""Adversarial tests requiring exact pinned public NVIDIA schema (no vendor service)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from semantic_upstream_contract import check_model, UPSTREAM_BLOB, UPSTREAM_SHA256
from semantic_native_model import write_sandbox


class PinnedUpstreamSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("OI_PINNED_NVIDIA_SCHEMA_PATH")
        if not value:
            raise RuntimeError("OI_PINNED_NVIDIA_SCHEMA_PATH required for upstream schema tests")
        cls.upstream = Path(value)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.sandbox = self.folder / "sandbox"
        write_sandbox(self.sandbox)
        self.model = self.sandbox / "oi_native_model.yaml"
        self.db = self.sandbox / "oi_metadata_sandbox.sqlite"

    def check(self, upstream=None, model=None, db=None):
        return check_model(upstream or self.upstream, model or self.model, db or self.db)

    def test_actual_nvidia_model_accepts_exact_first_party_sandbox(self):
        out = self.check()
        self.assertEqual(out["upstream_git_blob_sha1"], UPSTREAM_BLOB)
        self.assertEqual(out["upstream_source_sha256"], UPSTREAM_SHA256)
        self.assertEqual((out["tables"], out["columns"], out["terms"]), (3, 22, 3))
        self.assertEqual(out["sqlite_total_rows"], 0)
        self.assertTrue(out["nvidia_pydantic_validation"])
        self.assertTrue(out["byte_equivalent_roundtrip"])
        self.assertTrue(out["strict_oi_validation"])
        self.assertTrue(out["oi_rejected_unknown_root_key"])
        for key in ("nvidia_app_started", "nvidia_catalog_imported", "nvidia_inference_called", "patient_data_used", "clinical_validation"):
            self.assertIs(out[key], False)

    def test_upstream_ignores_unknown_key_so_oi_must_reject(self):
        out = self.check()
        self.assertEqual(out["nvidia_unknown_root_key_policy"], "ignored_unknown_key")
        self.assertTrue(out["oi_rejected_unknown_root_key"])

    def test_receipt_is_reproducible(self):
        self.assertEqual(self.check(), self.check())

    def test_tampered_upstream_file_fails_before_execution(self):
        corrupted = self.folder / "schemas-corrupt.py"
        corrupted.write_bytes(self.upstream.read_bytes().replace(b"ModelTerm", b"ModelFake", 1))
        with self.assertRaisesRegex(ValueError, "source SHA-256 differs"):
            self.check(upstream=corrupted)

    def test_unrelated_python_code_is_never_loaded(self):
        corrupted = self.folder / "untrusted.py"
        corrupted.write_text("raise RuntimeError('must not execute')\n")
        with self.assertRaises(ValueError):
            self.check(upstream=corrupted)

    def test_extra_patient_field_fails_oi_validation(self):
        obj = json.loads(self.model.read_text())
        obj["patient_id"] = "test-case-unapproved"
        self.model.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, "differs from approved"):
            self.check()

    def test_foreign_key_and_join_proposals_fail_first_party_gate(self):
        for bucket, value in (("foreign_keys", [{"source_column_id":"a", "target_column_id":"b"}]),
                              ("joins", [{"source_table_id":"a", "target_table_id":"b"}])):
            obj = json.loads(self.model.read_text())
            obj["data_layer"][bucket] = value
            self.model.write_text(json.dumps(obj))
            with self.subTest(bucket=bucket), self.assertRaises(ValueError):
                self.check()
            # Restore the canonical fixture independently of the tested validator.
            self.model.write_text(json.dumps(self._canonical()))

    def _canonical(self):
        from semantic_native_model import native_model_document
        return native_model_document()

    def test_sql_attribute_is_rejected_before_nvidia_validation(self):
        obj = self._canonical()
        obj["semantic_layer"]["sql_attributes"]["manual"] = [
            {"id": "synthetic", "sql": "SELECT 1", "name": "forbidden"}
        ]
        self.model.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            self.check()

    def test_sample_values_are_rejected_even_without_personal_identifiers(self):
        obj = self._canonical()
        obj["data_layer"]["databases"][0]["schemas"][0]["tables"][0]["columns"][0]["sample_values"] = ["synthetic-sample"]
        self.model.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            self.check()

    def test_nonempty_sqlite_is_rejected(self):
        self.db.chmod(0o644)
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('INSERT INTO source_version (source_id) VALUES (?)', ("synthetic-only",))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(ValueError, "Nonempty table"):
            self.check()

    def test_malformed_model_is_rejected(self):
        self.model.write_text("{ broken JSON")
        with self.assertRaises(ValueError):
            self.check()

    def test_oversized_upstream_input_is_not_executed(self):
        other = self.folder / "too-large-schema.py"
        other.write_bytes(b"# harmless\n" * 2500)
        with self.assertRaisesRegex(ValueError, "exceeds maximum"):
            self.check(upstream=other)

    def test_oversized_model_is_rejected(self):
        self.model.write_bytes(b"{" + b" " * 66000 + b"}")
        with self.assertRaisesRegex(ValueError, "exceeds maximum"):
            self.check()


if __name__ == "__main__":
    unittest.main()
