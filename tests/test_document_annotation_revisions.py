"""Synthetic manual-annotation corrections retain originals and prior reasoning."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from open_intelligence.composer import build_composer_context
from open_intelligence.durable_runs import DurableComposerRuns
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.store import CaseStore, InvalidInput


class DocumentAnnotationRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "annotation-revisions.sqlite"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Independently fictional annotation case")
        self.store.add_case("CASE-BETA", "Unrelated fictional case")
        self.raw = (b"\xef\xbb\xbfIndependent fictional report\r\n"
                    b"Marker Q was not assessed.\r\n"
                    b"Follow-up date remains unknown.\r\n")
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.metadata = {"document_id": "PLAIN-ALPHA", "kind": "pathology",
                         "event_date": "2026-04-05", "issued_at": "2026-04-07",
                         "manual_transcription_confirmed": True}
        self.findings = [{"key": "marker-q", "state": "negative",
                          "quote": "Marker Q was not assessed.", "line": 2}]
        self.corrected = [{**self.findings[0], "state": "not-assessed"}]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ingest(self, findings=None, case="CASE-ALPHA"):
        return self.store.import_document(case, self.raw, "fictional-report.txt",
            self.metadata, self.findings if findings is None else findings,
            self.digest, case)["source_id"]

    def revise(self, source_id, *, store=None, **kwargs):
        payload = {"findings": self.corrected, "expected_revision": 1,
                   "expected_sha256": self.digest, "confirmed_case_id": "CASE-ALPHA",
                   "manual_transcription_confirmed": True,
                   "reason": "Correct the manually selected status to match the literal quotation."}
        payload.update(kwargs)
        return (store or self.store).revise_document_annotations("CASE-ALPHA", source_id, **payload)

    def dump(self):
        return tuple(self.store.db.iterdump())

    def model(self, question):
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        validated = ValidatedInvestigation("abstained", [], [], [], "recorded-replay", "replay")
        return self.store.save_investigation("CASE-ALPHA", question, "evidence-summary",
            validated, "replay", context_fingerprint=context["fingerprint"])

    def test_add_to_original_only_upload_and_remove_without_replacing_original(self):
        source = self.ingest(findings=[])
        before = self.store.document_annotations("CASE-ALPHA", source)
        self.assertEqual(before["current_revision"]["revision"], 1)
        self.assertEqual(before["current_revision"]["findings"], [])
        self.assertEqual(before["text"].encode(), self.raw)
        self.assertTrue(before["writable"])
        added = self.revise(source)
        self.assertEqual((added["result"], added["annotation_revision"]), ("revised", 2))
        self.assertEqual(self.store.state("CASE-ALPHA")["assertions"][0]["certainty"], "not-assessed")
        removed = self.revise(source, expected_revision=2, findings=[], reason="Remove this optional selection.")
        self.assertEqual(removed["annotation_revision"], 3)
        self.assertEqual(self.store.state("CASE-ALPHA")["assertions"], [])
        self.assertEqual(self.store.source_document("CASE-ALPHA", source)["raw"], self.raw)
        self.assertEqual(len(self.store.state("CASE-ALPHA")["sources"]), 1)

    def test_history_and_initial_receipt_are_immutable_and_survive_restart(self):
        source = self.ingest()
        original_receipt = dict(self.store.db.execute(
            "SELECT * FROM document_intake_metadata WHERE source_version_id=?", (source,)).fetchone())
        self.revise(source)
        self.store.close()
        self.store = CaseStore(self.path)
        before = self.dump()
        view = self.store.document_annotations("CASE-ALPHA", source)
        self.assertEqual(self.dump(), before)
        self.assertEqual([r["revision"] for r in view["history"]], [1, 2])
        self.assertEqual(view["history"][0]["findings"], self.findings)
        self.assertEqual(view["history"][1]["findings"], self.corrected)
        self.assertIn("literal quotation", view["history"][1]["reason"])
        self.assertEqual(dict(self.store.db.execute(
            "SELECT * FROM document_intake_metadata WHERE source_version_id=?", (source,)).fetchone()), original_receipt)
        for sql in ("UPDATE document_annotation_revisions SET reason='rewritten'",
                    "DELETE FROM document_annotation_revisions"):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.store.db:
                    self.store.db.execute(sql)
        self.assertEqual(self.dump(), before)

    def test_exact_retry_and_unchanged_selection_write_nothing(self):
        source = self.ingest()
        revised = self.revise(source)
        before = self.dump()
        duplicate = self.revise(source)
        self.assertEqual(duplicate["result"], "duplicate")
        self.assertEqual(duplicate["annotation_revision_id"], revised["annotation_revision_id"])
        self.assertEqual(self.dump(), before)
        unchanged = self.revise(source, expected_revision=2, reason="No selected content changed.")
        self.assertEqual(unchanged["result"], "unchanged")
        self.assertEqual(self.dump(), before)
        with self.assertRaises(InvalidInput):
            self.revise(source, reason="Different retry reason must not create another event.")
        self.assertEqual(self.dump(), before)

    def test_correction_stales_bound_work_preserves_history_and_other_case(self):
        source = self.ingest()
        other = self.ingest(case="CASE-BETA")
        question = self.store.add_question("CASE-ALPHA", "What did this fictional source state?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "A human draft made before the manual status correction.", [source])
        option = self.store.create_option("CASE-ALPHA", snapshot, "Fictional discussion item",
            "A fictional question for discussion based on the captured source.", "unknown")
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot, "Fictional reviewer")
        model_id = self.model(question)
        other_question = self.store.add_question("CASE-BETA", "What does the unrelated fictional source state?")
        other_snapshot = self.store.create_snapshot("CASE-BETA", other_question,
            "An unrelated independently fictional draft remains current.", [other])
        initial_export = self.store.export_markdown("CASE-ALPHA", snapshot)
        initial_hash = self.store.document_annotations("CASE-ALPHA", source)["current_revision"]["review_sha256"]
        result = self.revise(source)
        self.assertEqual(result["invalidated_snapshots"], [snapshot])
        self.assertEqual(result["invalidated_model_investigation_ids"], [model_id])
        self.assertIn(option, result["invalidated_options"])
        self.assertEqual(self.store.option_view("CASE-ALPHA")["options"][0]["review_state"], "needs_review")
        current = self.store.state("CASE-ALPHA")
        self.assertEqual(current["snapshots"][0]["state"], "stale")
        self.assertEqual(current["questions"][0]["state"], "open")
        self.assertEqual(self.store.state("CASE-BETA")["snapshots"][0]["id"], other_snapshot)
        self.assertEqual(self.store.state("CASE-BETA")["snapshots"][0]["state"], "draft")
        exported = self.store.export_markdown("CASE-ALPHA", snapshot)
        self.assertIn(initial_hash, exported)
        self.assertIn("negative", exported)
        self.assertIn("Annotation revision: 1", exported)
        self.assertIn("Marker Q was not assessed.", exported)
        self.assertNotIn(result["review_sha256"], exported)
        self.assertIn("Annotation revision: 1", initial_export)
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_demo_review("CASE-ALPHA", snapshot, "Fictional reviewer")
        model = self.store.get_investigation("CASE-ALPHA", model_id)
        self.assertTrue(model["stale"])
        self.assertEqual(model["input_annotations"]["capture_state"], "recorded")
        self.assertEqual(model["input_annotations"]["context_revisions"][0]["revision"], 1)
        self.assertEqual(model["input_annotations"]["prompt_assertions"][0]["certainty"], "negative")

    def test_snapshot_save_requires_current_revision_after_first_correction(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "Which annotation revision was reviewed?")
        self.revise(source)
        for revisions in (None, {str(source): 1}, {str(source): True}, {str(source): 2, "999": 1}):
            with self.subTest(revisions=revisions):
                with self.assertRaises(InvalidInput):
                    self.store.create_snapshot("CASE-ALPHA", question,
                        "A draft must bind the source annotations actually selected.", [source],
                        expected_annotation_revisions=revisions)
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "A draft binds the current manually corrected selections.", [source],
            expected_annotation_revisions={str(source): 2})
        self.assertIn("Annotation revision: 2", self.store.export_markdown("CASE-ALPHA", snapshot))

    def test_revert_cannot_make_old_composer_context_valid_again(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "Which exact selection was used?")
        original = build_composer_context(self.store, "CASE-ALPHA", question)
        first_hash = self.store.document_annotations("CASE-ALPHA", source)["current_revision"]["review_sha256"]
        self.revise(source)
        reverted = self.revise(source, expected_revision=2, findings=self.findings,
            reason="Restore the earlier selection as a new, unreviewed revision.")
        self.assertEqual(reverted["review_sha256"], first_hash)
        now = build_composer_context(self.store, "CASE-ALPHA", question)
        self.assertNotEqual(now["fingerprint"], original["fingerprint"])
        self.assertEqual(now["source_anchors"][0]["annotation_revision"], 3)
        with self.assertRaises(InvalidInput):
            self.revise(source)
        with self.assertRaisesRegex(InvalidInput, "stale"):
            self.store.save_investigation("CASE-ALPHA", question, "evidence-summary",
                ValidatedInvestigation("abstained", [], [], [], "recorded-replay", "replay"),
                "replay", context_fingerprint=original["fingerprint"])

    def test_existing_durable_run_owner_reconciles_revision_freshness(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "Does saved tool work retain a current input context?")
        runs = DurableComposerRuns(self.store)
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        queued = runs.queue("CASE-ALPHA", question, context["fingerprint"], "marker-q", "annotation-test-1")
        self.assertEqual(queued["state"], "queued")
        self.revise(source)
        reconciled = runs.get("CASE-ALPHA", queued["run_id"])
        self.assertEqual(reconciled["state"], "stale")
        self.assertEqual(reconciled["failure_code"], "source_context_changed")
        self.assertEqual(reconciled["context_fingerprint"], context["fingerprint"])
        self.assertIsNone(reconciled["result"])
        with self.assertRaises(InvalidInput):
            runs.execute("CASE-ALPHA", queued["run_id"])

    def test_invalid_case_hash_confirmation_quote_and_ids_never_write(self):
        source = self.ingest()
        before = self.dump()
        invalid = [
            {"confirmed_case_id": "CASE-BETA"}, {"expected_sha256": "0" * 64},
            {"manual_transcription_confirmed": False}, {"expected_revision": True},
            {"expected_revision": 0}, {"expected_revision": 2**63},
            {"reason": " "}, {"reason": "x" * 501},
            {"findings": [{**self.corrected[0], "quote": "An invented quote."}]},
            {"findings": [{**self.corrected[0], "line": True}]},
            {"findings": self.corrected * 31},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(InvalidInput):
                    self.revise(source, **payload)
                self.assertEqual(self.dump(), before)
        for source_id in (True, 0, -1, "1", 2**63):
            with self.subTest(source_id=source_id):
                with self.assertRaises(InvalidInput):
                    self.store.document_annotations("CASE-ALPHA", source_id)
                with self.assertRaises(InvalidInput):
                    self.revise(source_id)
        with self.assertRaises(InvalidInput):
            self.store.document_annotations("CASE-BETA", source)
        self.assertEqual(self.dump(), before)

    def test_structured_and_superseded_sources_are_not_editable(self):
        legacy = self.store.import_report("CASE-ALPHA", (
            b"OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: LEGACY\n"
            b"Type: clinical\nEvent-Date: 2026-04-05\nIssued-At: 2026-04-07\n"
            b"Finding: marker-q|not-assessed|Marker Q was not assessed.\n"))["source_id"]
        with self.assertRaises(InvalidInput):
            self.store.document_annotations("CASE-ALPHA", legacy)
        with self.assertRaises(InvalidInput):
            self.revise(legacy)
        source = self.ingest()
        amended = self.raw + b"Independently authored later source amendment.\r\n"
        self.store.import_document("CASE-ALPHA", amended, "fictional-amendment.txt",
            {**self.metadata, "amends_version": 1}, self.corrected,
            hashlib.sha256(amended).hexdigest(), "CASE-ALPHA")
        view = self.store.document_annotations("CASE-ALPHA", source)
        self.assertEqual(view["state"], "superseded")
        self.assertFalse(view["writable"])
        before = self.dump()
        with self.assertRaises(InvalidInput):
            self.revise(source)
        self.assertEqual(self.dump(), before)

    def test_two_concurrent_edits_cannot_both_replace_same_revision(self):
        source = self.ingest()

        def revise(state):
            store = CaseStore(self.path)
            try:
                return self.revise(source, store=store,
                    findings=[{**self.findings[0], "state": state}])["result"]
            except InvalidInput:
                return "rejected"
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(revise, ["not-assessed", "pending"]))
        self.assertEqual(sorted(results), ["rejected", "revised"])
        self.assertEqual(len(self.store.document_annotations("CASE-ALPHA", source)["history"]), 2)

    def test_late_failure_rolls_back_revision_projection_and_invalidations(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "Does every write commit atomically?")
        self.store.create_snapshot("CASE-ALPHA", question, "A fictional draft must remain current if saving fails.", [source])
        self.model(question)
        self.store.db.execute("""CREATE TRIGGER reject_annotation_event BEFORE INSERT ON events
            WHEN NEW.kind='document_annotations_revised' BEGIN
            SELECT RAISE(ABORT, 'simulated receipt failure'); END""")
        self.store.db.commit()
        before = self.dump()
        with self.assertRaises(sqlite3.IntegrityError):
            self.revise(source)
        self.assertEqual(self.dump(), before)

    def test_pre_revision_database_migrates_known_snapshot_binding_without_inventing_model_inputs(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "What input history was actually recorded?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "A preserved fictional draft created before annotation revisions.", [source])
        model_id = self.model(question)
        original_context = self.store.get_investigation("CASE-ALPHA", model_id)["input_context"]
        # Reproduce the actual prior schema boundary: these new ownership
        # extensions did not exist, while originals/assertions/snapshots did.
        with self.store.db:
            self.store.db.execute("DROP TABLE snapshot_annotation_revisions")
            self.store.db.execute("DROP TABLE investigation_annotation_inputs")
            self.store.db.execute("DROP TABLE document_annotation_revisions")
        self.store.close()
        self.store = CaseStore(self.path)
        view = self.store.document_annotations("CASE-ALPHA", source)
        self.assertEqual(view["current_revision"]["revision"], 1)
        self.assertEqual(view["current_revision"]["origin"], "legacy_intake_migration")
        self.assertIn("Annotation revision: 1", self.store.export_markdown("CASE-ALPHA", snapshot))
        model = self.store.get_investigation("CASE-ALPHA", model_id)
        self.assertEqual(model["input_annotations"]["capture_state"], "not_recorded")
        self.assertEqual(model["input_context"], original_context)
        self.revise(source)
        self.assertIn("Annotation revision: 1", self.store.export_markdown("CASE-ALPHA", snapshot))


if __name__ == "__main__":
    unittest.main()
