"""Reassessment resolves report lineage and finding keys without inferring an origin."""
import hashlib
from pathlib import Path
import unittest

from oi_api.attribution_reassessment import compare_versions
from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.store import parse_report


class ReassessmentTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[3] / "examples/synthetic"
        self.raw = (directory / "episode-origin-consult-v1.txt").read_text()
        digest = hashlib.sha256(self.raw.encode()).hexdigest()
        self.source = dict(source_id="SRC-"+"A"*32, document_id="DOC-CONSULT", version=1, sha256=digest)
        self.later = dict(self.source, source_id="SRC-"+"B"*32, version=2, sha256="b"*64)
        self.anchor = {"source_id": self.source["source_id"], "source_version": 1,
                       "source_sha256": digest, "source_line": 8}
        self.original = dict(self.source, original_text=self.raw)
        self.finding = {"source_id": self.later["source_id"], "source_line": 11, "finding_key": "nodule",
                        "reported_state":"indeterminate", "source_statement":"Fictional amended passage.",
                        "oncology":{"role":"metastasis","episode_id":None}, "clinical_review_state":"not_established"}

    def test_follows_key_after_line_moves_and_keeps_unassigned_distinct_from_untyped(self):
        for typed in (True, False):
            current = self.finding.copy()
            if not typed:
                del current["oncology"]
            pair = compare_versions(self.anchor, self.original, self.later, [current])
            old, new = (pair[side]["finding"] for side in ("recorded", "latest"))
            self.assertEqual(old["source_line"], 8)
            self.assertEqual(old["oncology"]["episode_id"], "EP-A")
            self.assertEqual(old["source_statement"], parse_report(self.raw.encode(), allow_oncology=True).findings[0].quote)
            self.assertEqual(new, current)

    def test_unrelated_or_removed_finding_never_substitutes_for_old_line(self):
        entries = [dict(self.finding, source_line=8, finding_key="other"),
                   dict(self.finding, source_id="SRC-"+"C"*32)]
        pair = compare_versions(self.anchor, self.original, self.later, entries)
        self.assertIsNone(pair["latest"]["finding"])
        self.assertEqual(pair["latest"]["source_id"], self.later["source_id"])

    def test_wrong_original_receipt_line_hash_version_and_document_are_rejected(self):
        for changes in ({"source_line":7},{"source_sha256":"f"*64},{"source_version":2},
                        {"source_id":"SRC-"+"E"*32}):
            with self.subTest(changes=changes), self.assertRaises(PatientRegistryError):
                compare_versions(dict(self.anchor, **changes), self.original, self.later, [self.finding])
        with self.assertRaises(PatientRegistryError):
            compare_versions(self.anchor, self.original, dict(self.later, document_id="DOC-OTHER"), [])
