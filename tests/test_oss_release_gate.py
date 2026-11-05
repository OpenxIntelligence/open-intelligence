"""Negative tests for OI-17 fail-closed third-party declaration checks."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.oss_release_gate import EVIDENCE_PATHS, validate_manifest


class OssReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"

    def write(self, adopted):
        self.manifest.write_text(
            json.dumps({"schema_version": 1, "adopted_components": adopted}),
            encoding="utf-8",
        )
        return validate_manifest(self.root, self.manifest)

    def complete_record(self):
        record = {
            "name": "example-permissive-library",
            "version": "1.2.3",
            "role": "synthetic-only-test",
            "source_url": "https://github.com/example/project",
            "source_commit": "a" * 40,
            "spdx_license": "MIT",
            "intended_commercial_use": "self-hosted proprietary application",
        }
        for key in EVIDENCE_PATHS:
            relative = f"evidence/{key}.txt"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Fixture receipt; NOT a real clearance.", encoding="utf-8")
            record[key] = relative
        return record

    def test_empty_declared_inventory_is_valid_but_not_inventory_evidence(self):
        self.assertEqual(self.write([]), [])

    def test_complete_record_has_structural_pass_only(self):
        self.assertEqual(self.write([self.complete_record()]), [])

    def test_rejects_missing_sbom_or_signed_approval_record(self):
        record = self.complete_record()
        (self.root / record["sbom_path"]).unlink()
        (self.root / record["human_approval_receipt"]).unlink()
        errors = self.write([record])
        self.assertTrue(any("sbom_path" in e for e in errors))
        self.assertTrue(any("human_approval_receipt" in e for e in errors))

    def test_rejects_prohibited_licenses_even_with_receipts(self):
        record = self.complete_record()
        record["spdx_license"] = "AGPL-3.0-only"
        self.assertTrue(any("not Tier-1 allowlisted" in e for e in self.write([record])))

    def test_nextjs_exclusion_is_independent_of_its_mit_license(self):
        record = self.complete_record()
        record["name"] = "next.js"
        self.assertTrue(any("Next.js excluded" in e for e in self.write([record])))

    def test_rejects_unpinned_shas_and_duplicate_entries(self):
        record = self.complete_record()
        record["source_commit"] = "main"
        errors = self.write([record, record])
        self.assertTrue(any("full 40-hex SHA" in e for e in errors))
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_rejects_evidence_path_escape(self):
        record = self.complete_record()
        record["sbom_path"] = "../outside.json"
        errors = self.write([record])
        self.assertTrue(any("escapes repository root" in e for e in errors))

    def test_rejects_broken_or_missing_manifest(self):
        self.assertTrue(validate_manifest(self.root, self.manifest))
        self.manifest.write_text("{", encoding="utf-8")
        self.assertTrue(validate_manifest(self.root, self.manifest))


if __name__ == "__main__":
    unittest.main()
