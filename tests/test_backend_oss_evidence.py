"""Checks for the Open Intelligence OSS research evidence gate."""
import copy
import json
import unittest
from pathlib import Path

from tools.verify_backend_oss_evidence import validate

SOURCE=Path(__file__).resolve().parents[1]/"docs/research/backend_oss_evidence_2026-11-02.json"


class BackendOssEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_pinned_evidence_is_structurally_complete(self):
        self.assertGreaterEqual(len(self.manifest["entries"]),8)
        self.assertEqual(validate(self.manifest),[])

    def test_no_root_license_implies_commercial_adoption(self):
        for row in self.manifest["entries"]:
            with self.subTest(repo=row["repo"]):
                self.assertFalse(row["commercial_cleared"])
                self.assertNotIn(row["decision"],{"ADOPT","INTEGRATE","BUILD"})

    def test_missing_dependency_clearance_cannot_be_promoted(self):
        value=copy.deepcopy(self.manifest)
        value["entries"][0]["commercial_cleared"]=True
        self.assertTrue(validate(value))

    def test_corrupted_commit_rejected(self):
        value=copy.deepcopy(self.manifest)
        value["entries"][0]["commit_sha"]="main"
        self.assertTrue(validate(value))

    def test_mismatched_license_url_rejected(self):
        value=copy.deepcopy(self.manifest)
        value["entries"][0]["source_url"]="https://example.net/license"
        self.assertTrue(validate(value))

    def test_duplicate_repository_cannot_pass_as_two_candidates(self):
        value=copy.deepcopy(self.manifest)
        value["entries"].append(copy.deepcopy(value["entries"][0]))
        self.assertTrue(validate(value))


if __name__=="__main__":
    unittest.main()
