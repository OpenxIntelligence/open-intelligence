"""Reassessment resolves report lineage and finding keys without inferring an origin."""
import hashlib
from pathlib import Path
import unittest

from oi_api.attribution_reassessment import compare_versions, comparison_snapshot
from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.store import parse_report


class ReassessmentTests(unittest.TestCase):
    def test_snapshot_binds_scope_and_content_without_mutable_aliases(self):
        from copy import deepcopy
        pair = {"recorded": {"finding": {"source_statement": "Fictional old passage"}},
                "latest": {"finding": None}}
        args = dict(patient_id="PAT-A", case_id="CASE-A", question_id="QUESTION-A",
                    receipt_id="REVIEW-A", first=pair, second=deepcopy(pair))
        original = comparison_snapshot(**args)
        self.assertEqual(original, comparison_snapshot(**args))
        for key in ("patient_id", "case_id", "question_id", "receipt_id"):
            self.assertNotEqual(original["sha256"], comparison_snapshot(**dict(args, **{key: "OTHER"}))["sha256"])
        pair["latest"]["finding"] = {"source_statement": "Fictional amended passage"}
        self.assertIsNone(original["content"]["first"]["latest"]["finding"])
        self.assertNotEqual(original["sha256"], comparison_snapshot(**args)["sha256"])
        self.assertFalse(original["content"]["clinical_approval"])

    def test_comparison_service_writes_primitive_journal_metadata(self):
        from contextlib import nullcontext
        from unittest.mock import Mock, patch
        import json
        from oi_api.question_review_returns import PostgresQuestionReviewReturns
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        registry = object.__new__(PostgresPatientRegistry)
        registry._transaction_active = True
        registry.transaction = lambda: nullcontext()
        registry.require_patient = Mock()
        registry._execute = Mock()
        owner = PostgresQuestionReviewReturns(registry)
        question = dict(self.anchor, question_id="QUESTION-A")
        receipt = dict(receipt_id="REVIEW-A", question_id="QUESTION-A", comparison_source=self.anchor)
        index = {"sources": [dict(self.later, state="current")],
                 "source_reported_assertions": [self.finding], "access_receipt_id": "ACCESS-A"}
        with patch.object(owner, "_read_locked", return_value=([question], [receipt])), \
             patch("oi_api.question_review_returns.PostgresSourceVersions") as source_class:
            sources = source_class.return_value
            sources.list_locked.side_effect = lambda *args, **kwargs: kwargs["prepare_response"](index)
            sources.original_locked.return_value = dict(self.original, access_receipt_id="ACCESS-B")
            packet = owner.compare_attributions("PAT-A", "CASE-A", "REVIEW-A", organization="ORG-A",
                actor="ACTOR-A", purpose="operations", recheck_authority=lambda: None)
        metadata = json.loads(registry._execute.call_args.args[1][2])
        expected = comparison_snapshot(patient_id="PAT-A", case_id="CASE-A", question_id="QUESTION-A",
            receipt_id="REVIEW-A", first=packet["first"], second=packet["second"])
        self.assertEqual(metadata["comparison_sha256"], expected["sha256"])
        self.assertEqual(metadata["comparison_contract"], expected["content"]["contract"])
        self.assertNotIn("comparison_snapshot", metadata)
        registry._execute.assert_called_once()
        # Replay through the same service and real journal validator. A saved
        # digest is scoped by the journal query and is not permission to use new content.
        from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied
        registry._fetchone = Mock(return_value=(metadata,))
        with patch.object(owner, "_read_locked", return_value=([question], [receipt])), \
             patch("oi_api.question_review_returns.PostgresSourceVersions") as source_class:
            sources = source_class.return_value
            sources.list_locked.side_effect = lambda *args, **kwargs: kwargs["prepare_response"](index)
            sources.original_locked.return_value = dict(self.original, access_receipt_id="ACCESS-B")
            def recheck():
                return owner.compare_attributions("PAT-A", "CASE-A", "REVIEW-A", organization="ORG-A",
                    actor="ACTOR-A", purpose="operations", recheck_authority=lambda: None,
                    expected_comparison_sha256=expected["sha256"])
            self.assertEqual(recheck()["comparison_sha256"], expected["sha256"])
            self.assertEqual(registry._fetchone.call_args.args[1],
                ("PAT-A", "CASE-A", "QUESTION-A", "REVIEW-A", expected["sha256"]))
            index["source_reported_assertions"] = [dict(self.finding, source_statement="Fictional changed statement")]
            with self.assertRaises(PatientRegistryConflict):
                recheck()
            registry._fetchone.return_value = None
            with self.assertRaises(PatientRegistryDenied):
                recheck()

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
