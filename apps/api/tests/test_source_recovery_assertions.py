"""Negative controls for the actual source recovery acceptance oracle.

These execute the probe's assertion, not a substitute database/application.
The full HTTP/PG behavior remains the Compose gate's responsibility.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "source_recovery", Path(__file__).resolve().parents[1] / "tools/verify_sources_compose.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

EVENTS = "identity.identity_domain_events"
SEQUENCE = "identity.identity_domain_events_id_seq"


class SourceRecoveryAssertions(unittest.TestCase):
    def setUp(self):
        self.before = {
            "tables": {
                "clinical_source.source_versions": [{"source_id": "SRC-FICTIONAL", "raw": "\\x4142"}],
                "clinical_source.annotation_revisions": [{"revision_id": "ANN-FICTIONAL", "revision": 2}],
                "public.alembic_version": [{"version_num": "0014_manual_report_context"}],
                EVENTS: [{"id": 7, "patient_id": "PAT-FICTIONAL", "event_type": "source.original.imported",
                          "metadata_json": {"source_id": "SRC-FICTIONAL"}, "occurred_at": "2026-01-01"}],
            },
            "sequences": {SEQUENCE: {"last_value": 7, "is_called": True},
                          "coordination.business_id_seq": {"last_value": 1, "is_called": False}},
        }
        self.expected = [{"patient_id": "PAT-FICTIONAL", "event_type": "source.document_read_authorized",
                          "metadata_json": {"receipt_id": "ACCESS-" + "A" * 32,
                                            "case_id": "CASE-FICTIONAL", "actor": "ACTOR-FICTIONAL",
                                            "purpose": "operations", "binding_revision": 1,
                                            "source_id": "SRC-FICTIONAL", "sha256": "a" * 64}}]
        self.after = deepcopy(self.before)
        self.after["tables"][EVENTS].append({**deepcopy(self.expected[0]), "id": 8, "occurred_at": "2026-01-02"})
        self.after["sequences"][SEQUENCE]["last_value"] = 8

    def check(self, before=None, after=None, expected=None):
        return probe.assert_read_only_recovery(
            self.before if before is None else before,
            self.after if after is None else after,
            self.expected if expected is None else expected)

    def test_accepts_only_expected_restored_receipts(self):
        self.check()

    def test_rejects_modified_or_missing_business_rows(self):
        for table in ("clinical_source.source_versions", "clinical_source.annotation_revisions", "public.alembic_version"):
            for operation in ("modify", "remove"):
                with self.subTest(table=table, operation=operation), self.assertRaises(AssertionError):
                    changed = deepcopy(self.after)
                    if operation == "modify": changed["tables"][table][0]["unexpected"] = True
                    else: del changed["tables"][table]
                    self.check(after=changed)

    def test_rejects_altered_historical_event(self):
        changed = deepcopy(self.after)
        changed["tables"][EVENTS][0]["metadata_json"]["source_id"] = "SRC-OTHER"
        with self.assertRaises(AssertionError): self.check(after=changed)

    def test_rejects_missing_extra_or_duplicate_event(self):
        for operation in ("missing", "extra", "duplicate_id"):
            with self.subTest(operation=operation), self.assertRaises(AssertionError):
                changed = deepcopy(self.after)
                if operation == "missing": changed["tables"][EVENTS].pop()
                elif operation == "extra": changed["tables"][EVENTS].append({**deepcopy(changed["tables"][EVENTS][-1]), "id": 9})
                else: changed["tables"][EVENTS][-1]["id"] = 7
                self.check(after=changed)

    def test_rejects_wrong_scope_receipt_or_business_event(self):
        for field, value in (("receipt_id", "ACCESS-" + "B" * 32), ("case_id", "CASE-OTHER"),
                             ("actor", "ACTOR-OTHER"), ("binding_revision", 2), ("source_id", "SRC-OTHER"),
                             ("sha256", "b" * 64), ("purpose", "research")):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                changed = deepcopy(self.after)
                changed["tables"][EVENTS][-1]["metadata_json"][field] = value
                self.check(after=changed)
        for field, value in (("patient_id", "PAT-OTHER"), ("event_type", "source.annotations.revised")):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                changed = deepcopy(self.after)
                changed["tables"][EVENTS][-1][field] = value
                self.check(after=changed)

    def test_rejects_reused_returned_receipt(self):
        with self.assertRaises(AssertionError): self.check(expected=self.expected * 2)
        before = deepcopy(self.before)
        before["tables"][EVENTS][0]["metadata_json"]["receipt_id"] = self.expected[0]["metadata_json"]["receipt_id"]
        after = deepcopy(self.after)
        after["tables"][EVENTS][0] = deepcopy(before["tables"][EVENTS][0])
        with self.assertRaises(AssertionError): self.check(before=before, after=after)

    def test_rejects_sequence_mutation_beyond_expected_access(self):
        for sequence, field, value in ((SEQUENCE, "last_value", 9), (SEQUENCE, "is_called", False),
                                       ("coordination.business_id_seq", "last_value", 2),
                                       ("coordination.business_id_seq", "is_called", True)):
            with self.subTest(sequence=sequence, field=field), self.assertRaises(AssertionError):
                changed = deepcopy(self.after)
                changed["sequences"][sequence][field] = value
                self.check(after=changed)

    def test_rejects_unaccounted_sequence_allocation_before_read(self):
        changed = deepcopy(self.after)
        changed["tables"][EVENTS][-1]["id"] = 9
        changed["sequences"][SEQUENCE]["last_value"] = 9
        with self.assertRaises(AssertionError): self.check(after=changed)

    def test_rejects_empty_evidence_or_added_owner(self):
        with self.assertRaises(AssertionError): self.check(after=self.before, expected=[])
        changed = deepcopy(self.after)
        changed["tables"]["clinical_source.unexpected"] = []
        with self.assertRaises(AssertionError): self.check(after=changed)


class RestoredSelectionJSONAssertions(unittest.TestCase):
    """Adversarial wire-level controls; no external service or database."""

    def setUp(self):
        anchor = {
            "patient_id": "PAT-FICTIONAL", "case_id": "CASE-FICTIONAL",
            "source_id": "SRC-" + "A" * 32, "document_id": "DOC-FICTIONAL",
            "source_version": 1, "original_sha256": "a" * 64,
            "extraction_method": "frozen-pdf-fixture", "extraction_sha256": "b" * 64,
            "annotation_revision_id": "ANN-" + "C" * 32,
            "annotation_revision": 2, "review_sha256": "d" * 64,
            "selected_by": "ACTOR-FICTIONAL", "selected_at": "2026-11-03T10:00:00+00:00",
            "selection_key": "marker", "selected_state": "reported",
            "quote": "Corrected fictional passage.", "line": 3, "page": 2,
            "classification_origin": "user_selected", "clinical_review": "not_performed",
        }
        self.expected = {
            "contract": "oi.reviewed-document-selection/1",
            "anchor": anchor, "anchor_sha256": self.digest(anchor),
            "source_state": "current",
            "latest_annotation_revision_id": "ANN-" + "C" * 32,
            "selection_state": "current_unreviewed_selection",
            "synthetic": True, "clinical_approval": False, "model_execution": False,
        }
        self.actual = deepcopy(self.expected)
        self.actual["access_receipt_id"] = "ACCESS-" + "A" * 32

    @staticmethod
    def digest(anchor):
        return hashlib.sha256(json.dumps(anchor, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()

    def check(self, actual=None, expected=None):
        probe.assert_restored_selection_response(
            self.actual if actual is None else actual,
            self.expected if expected is None else expected)

    def test_accepts_exact_selection_and_fresh_receipt(self):
        self.check()
        changed = deepcopy(self.actual)
        changed["access_receipt_id"] = "ACCESS-" + "B" * 32
        self.check(actual=changed)

    def test_rejects_boolean_integer_substitution_and_stale_status(self):
        for key, value in (("synthetic", 1), ("clinical_approval", 0),
                           ("model_execution", 0), ("source_state", "superseded"),
                           ("selection_state", "selection_reassessment_required")):
            with self.subTest(field=key), self.assertRaises(AssertionError):
                changed = deepcopy(self.actual)
                changed[key] = value
                self.check(actual=changed)

    def test_rejects_recomputed_digest_on_changed_provenance(self):
        for key, value in (("source_id", "SRC-" + "B" * 32),
                           ("annotation_revision_id", "ANN-" + "D" * 32),
                           ("selected_state", "pending"), ("quote", "Unrelated passage."),
                           ("page", 1)):
            with self.subTest(field=key), self.assertRaises(AssertionError):
                changed = deepcopy(self.actual)
                changed["anchor"][key] = value
                changed["anchor_sha256"] = self.digest(changed["anchor"])
                self.check(actual=changed)

    def test_rejects_malformed_receipt_digest_and_shape(self):
        for receipt in (None, "ACCESS-" + "a" * 32, "ACCESS-" + "A" * 32 + "X"):
            with self.subTest(receipt=receipt), self.assertRaises(AssertionError):
                changed = deepcopy(self.actual)
                changed["access_receipt_id"] = receipt
                self.check(actual=changed)
        for key in ("source_state", "synthetic", "anchor"):
            with self.subTest(missing=key), self.assertRaises(AssertionError):
                changed = deepcopy(self.actual)
                del changed[key]
                self.check(actual=changed)
        with self.assertRaises(AssertionError):
            self.check(actual={**self.actual, "unexpected": True})
        with self.assertRaises(AssertionError):
            self.check(actual={**self.actual, "anchor_sha256": "0" * 64})
        with self.assertRaises(AssertionError):
            self.check(expected={**self.expected, "anchor_sha256": "0" * 64})



if __name__ == "__main__":
    unittest.main()
