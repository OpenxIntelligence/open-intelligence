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

    def test_selection_receipt_requires_the_exact_revision_key_and_anchor_hash(self):
        self.expected[0]["event_type"] = "source.document_selection_read_authorized"
        self.expected[0]["metadata_json"].pop("sha256")
        self.expected[0]["metadata_json"].update(annotation_revision_id="ANN-" + "C" * 32,
            selection_key="marker", anchor_sha256="d" * 64)
        self.after["tables"][EVENTS][-1].update(deepcopy(self.expected[0]))
        self.check()
        for field, value in (("annotation_revision_id", "ANN-" + "D" * 32),
                             ("selection_key", "other"), ("anchor_sha256", "e" * 64)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                changed = deepcopy(self.after)
                changed["tables"][EVENTS][-1]["metadata_json"][field] = value
                self.check(after=changed)

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


class SelectionRecoveryAssertions(unittest.TestCase):
    def setUp(self):
        self.anchor = dict(patient_id="PAT-FICTIONAL", case_id="CASE-FICTIONAL",
            source_id="SRC-FICTIONAL", document_id="DOC-FICTIONAL", source_version=1,
            original_sha256="a" * 64, extraction_method="frozen-pdf-fixture",
            extraction_sha256="b" * 64, annotation_revision_id="ANN-" + "C" * 32,
            annotation_revision=1, review_sha256="d" * 64,
            selected_by="ACTOR-FICTIONAL", selected_at="2026-11-03T10:00:00+00:00",
            selection_key="marker", selected_state="pending", quote="Marker pending.", line=2,
            page=2, classification_origin="user_selected", clinical_review="not_performed")
        self.expected = dict(contract="oi.reviewed-document-selection/1", anchor=self.anchor,
            anchor_sha256=self.digest(self.anchor), source_state="current",
            latest_annotation_revision_id="ANN-" + "D" * 32,
            selection_state="selection_reassessment_required", synthetic=True,
            clinical_approval=False, model_execution=False)
        self.actual = deepcopy(self.expected) | {"access_receipt_id": "ACCESS-" + "A" * 32}

    @staticmethod
    def digest(anchor):
        return hashlib.sha256(json.dumps(anchor, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode()).hexdigest()

    def test_only_fresh_access_receipt_may_differ(self):
        probe.assert_selection_recovery(self.actual, self.expected)
        self.actual["access_receipt_id"] = "ACCESS-" + "B" * 32
        probe.assert_selection_recovery(self.actual, self.expected)

    def test_rejects_changed_anchor_even_when_hash_is_recomputed(self):
        changes = dict(patient_id="PAT-OTHER", case_id="CASE-OTHER", source_id="SRC-OTHER",
            original_sha256="e" * 64, extraction_sha256="f" * 64,
            annotation_revision_id="ANN-" + "E" * 32, annotation_revision=2,
            review_sha256="0" * 64, selected_by="ACTOR-OTHER", selected_at="2026-11-03T11:00:00+00:00",
            selection_key="other", selected_state="reported", quote="Corrected passage.",
            line=3, page=1, classification_origin="source_reported", clinical_review="performed")
        for field, value in changes.items():
            with self.subTest(field=field), self.assertRaises(AssertionError):
                changed = deepcopy(self.actual)
                changed["anchor"][field] = value
                changed["anchor_sha256"] = self.digest(changed["anchor"])
                probe.assert_selection_recovery(changed, self.expected)

    def test_rejects_stale_status_promotion_and_extra_fields(self):
        for field, value in (("selection_state", "current_unreviewed_selection"),
                             ("latest_annotation_revision_id", "ANN-" + "E" * 32),
                             ("source_state", "superseded"), ("clinical_approval", True),
                             ("model_execution", True), ("synthetic", False), ("extra", "unexpected"),
                             ("synthetic", 1), ("clinical_approval", 0), ("model_execution", 0)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                probe.assert_selection_recovery(self.actual | {field: value}, self.expected)

    def test_rejects_missing_or_noncanonical_receipt_and_invalid_anchor_digest(self):
        for receipt in (None, "ACCESS-" + "a" * 32, "ACCESS-" + "A" * 32 + "\n"):
            with self.subTest(receipt=receipt), self.assertRaises(AssertionError):
                probe.assert_selection_recovery(self.actual | {"access_receipt_id": receipt}, self.expected)
        with self.assertRaises(AssertionError):
            probe.assert_selection_recovery(self.expected, self.expected)
        # Even an internally matching expected/actual pair must not accept a bad digest.
        with self.assertRaises(AssertionError):
            probe.assert_selection_recovery(self.actual | {"anchor_sha256": "0" * 64},
                                            self.expected | {"anchor_sha256": "0" * 64})


if __name__ == "__main__":
    unittest.main()
