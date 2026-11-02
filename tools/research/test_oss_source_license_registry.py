"""Fail closed: upstream LICENSE reconnaissance must not become an adoption claim."""
import json
import re
import unittest
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / "docs" / "research" / "OSS_LICENSE_DISCOVERY_WAVE1.json"
SHA = re.compile(r"[0-9a-f]{40}\Z")


class OpenSourceDiscoveryContract(unittest.TestCase):
    def test_machine_readable_candidate_licenses_do_not_claim_clearance(self):
        doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "oi.oss-license-discovery/1")
        rows = doc["records"]
        self.assertGreaterEqual(len(rows), 8)
        self.assertEqual(len(set(r["repository"] for r in rows)), len(rows))
        for row in rows:
            with self.subTest(row=row["project"]):
                self.assertRegex(row["source_commit"], SHA)
                self.assertRegex(row["license_blob_sha"], SHA)
                self.assertTrue(row["license_path"])
                self.assertEqual(row["version_pin_status"], "upstream_source_head_only_not_release_pin")
                self.assertEqual(row["transitive_sbom_status"], "NOT_GENERATED")
                self.assertEqual(row["commercial_adoption_status"], "NOT_APPROVED")
                self.assertIn(row["decision"], {"HOLD", "RESEARCH"})
                self.assertTrue(row["rights_notes"])


if __name__ == "__main__":
    unittest.main()
