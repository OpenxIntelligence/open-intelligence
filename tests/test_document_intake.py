"""Original-fictional text intake, exact transcription, and existing ledger continuity."""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from open_intelligence.composer import build_composer_context, composer_context_fingerprint
from open_intelligence.changes import changes_since_review
from open_intelligence.mission import build_patient_mission
from open_intelligence.investigation import ValidatedInvestigation, build_prompt
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.timeline import case_timeline


class DocumentIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "intake.sqlite"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Independent fictional intake case")
        self.store.add_case("CASE-BETA", "Unrelated fictional intake case")
        self.raw = (b"\xef\xbb\xbfIndependent fictional report\r\n"
                    b"Marker Q was not assessed.\r\n"
                    b"Follow-up date remains unknown.\r\n")
        self.metadata = {
            "document_id": "PLAIN-ALPHA", "kind": "pathology",
            "event_date": "2026-04-05", "issued_at": "2026-04-07",
            "specimen_id": "SPEC-ALPHA", "manual_transcription_confirmed": True,
        }
        self.findings = [{"key": "marker-q", "state": "not-assessed",
                          "quote": "Marker Q was not assessed.", "line": 2}]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def import_text(self, *, store=None, case="CASE-ALPHA", raw=None,
                    filename="fictional-report.txt", metadata=None,
                    findings=None, expected_sha256=None, confirmed_case_id=None):
        raw = self.raw if raw is None else raw
        return (store or self.store).import_document(
            case, raw, filename, self.metadata if metadata is None else metadata,
            self.findings if findings is None else findings,
            hashlib.sha256(raw).hexdigest() if expected_sha256 is None else expected_sha256,
            case if confirmed_case_id is None else confirmed_case_id)

    def snapshot_rows(self):
        return tuple(self.store.db.iterdump())

    def save_model(self, case="CASE-ALPHA"):
        question = self.store.add_question(case, "What did the fictional source explicitly report?")
        context = build_composer_context(self.store, case, question)
        result = ValidatedInvestigation(
            "abstained", [], [{"topic": "Fictional transcription",
                               "reason": "insufficient_evidence"}],
            [], "recorded-replay", "replay")
        return self.store.save_investigation(
            case, question, "evidence-summary", result, "replay",
            context_fingerprint=context["fingerprint"])

    def test_preview_preserves_bom_crlf_and_has_no_persistent_side_effect(self):
        before = self.snapshot_rows()
        preview = self.store.preview_document("CASE-ALPHA", self.raw, "fictional-report.txt")
        self.assertEqual(preview["text"].encode("utf-8"), self.raw)
        self.assertEqual(preview["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(preview["byte_count"], len(self.raw))
        self.assertEqual(preview["lines"], [
            {"line": 1, "text": "\ufeffIndependent fictional report"},
            {"line": 2, "text": "Marker Q was not assessed."},
            {"line": 3, "text": "Follow-up date remains unknown."},
        ])
        self.assertEqual(preview["clinical_review"], "not_performed")
        self.assertEqual(preview["extraction_method"], "utf8-plain-text-v1")
        self.assertEqual(self.snapshot_rows(), before)

    def test_commit_keeps_original_and_review_provenance_after_restart(self):
        result = self.import_text()
        self.assertEqual(result["result"], "imported")
        self.store.close()
        self.store = CaseStore(self.path)
        source = self.store.source_document("CASE-ALPHA", result["source_id"])
        self.assertEqual(source["raw"], self.raw)
        self.assertEqual(source["filename"], "fictional-report.txt")
        self.assertEqual(source["media_type"], "text/plain; charset=utf-8")
        self.assertTrue(source["manual_transcription_confirmed"])
        self.assertEqual(self.store.source_text("CASE-ALPHA", result["source_id"]).encode(), self.raw)
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(state["assertions"][0]["quote"], "Marker Q was not assessed.")
        self.assertEqual(state["assertions"][0]["source_line"], 2)
        self.assertEqual(state["assertions"][0]["certainty"], "not-assessed")
        receipt = state["sources"][0]["document_intake"]
        self.assertEqual(receipt["filename"], "fictional-report.txt")
        self.assertEqual(receipt["annotation_method"], "manual-exact-line-selection")
        self.assertEqual(receipt["clinical_review"], "not_performed")
        with self.assertRaises(InvalidInput):
            self.store.source_document("CASE-BETA", result["source_id"])

    def test_zero_findings_organizes_source_without_inventing_assertions(self):
        source = self.import_text(findings=[])
        self.assertEqual(self.store.state("CASE-ALPHA")["assertions"], [])
        timeline = case_timeline(self.store, "CASE-ALPHA")
        self.assertEqual(timeline["entries"][0]["source_id"], source["source_id"])
        self.assertEqual(timeline["entries"][0]["reported_findings"], [])
        self.assertEqual(timeline["entries"][0]["occurred"], "2026-04-05")
        self.assertEqual(timeline["entries"][0]["documented"], "2026-04-07")

    def test_original_lookup_rejects_malformed_or_unrepresentable_ids(self):
        self.import_text()
        for source_id in (0, -1, True, 1.0, "1", 2 ** 63):
            with self.subTest(source_id=source_id):
                with self.assertRaises(InvalidInput):
                    self.store.source_document("CASE-ALPHA", source_id)

    def test_quote_must_be_exact_nonempty_substring_of_selected_original_line(self):
        before = self.snapshot_rows()
        bad = [
            [{**self.findings[0], "quote": "Marker Q was negative."}],
            [{**self.findings[0], "line": 3}],
            [{**self.findings[0], "line": True}],
            [{**self.findings[0], "line": 0}],
            [{**self.findings[0], "line": 4}],
            [{**self.findings[0], "quote": ""}],
            [{**self.findings[0], "quote": " "}],
            [{**self.findings[0], "quote": "Marker Q was not assessed.\r\n"}],
            [{**self.findings[0], "quote": "x" * 1201}],
            [{**self.findings[0], "quote": ["Marker Q"]}],
            [{**self.findings[0], "state": "confirmed"}],
            [{**self.findings[0], "key": "INVALID KEY"}],
            [self.findings[0], self.findings[0]],
            [{**self.findings[0], "extra": "not accepted"}],
            [None], None, "findings",
        ]
        for findings in bad:
            with self.subTest(findings=findings):
                with self.assertRaises(InvalidInput):
                    self.store.import_document(
                        "CASE-ALPHA", self.raw, "fictional-report.txt", self.metadata,
                        findings, hashlib.sha256(self.raw).hexdigest(), "CASE-ALPHA")
                self.assertEqual(self.snapshot_rows(), before)
        self.import_text(findings=[{**self.findings[0], "quote": "not assessed"}])
        self.assertEqual(self.store.state("CASE-ALPHA")["assertions"][0]["quote"], "not assessed")

    def test_target_confirmation_and_preview_hash_are_required(self):
        before = self.snapshot_rows()
        for confirmation, digest in [("CASE-BETA", hashlib.sha256(self.raw).hexdigest()),
                                     ("CASE-ALPHA", "0" * 64),
                                     (True, hashlib.sha256(self.raw).hexdigest()),
                                     ("CASE-ALPHA", None), ("CASE-ALPHA", [])]:
            with self.subTest(confirmation=confirmation, digest=digest):
                with self.assertRaises(InvalidInput):
                    self.store.import_document("CASE-ALPHA", self.raw, "fictional-report.txt",
                                               self.metadata, self.findings, digest, confirmation)
                self.assertEqual(self.snapshot_rows(), before)
        with self.assertRaises(InvalidInput):
            self.store.preview_document("CASE-UNKNOWN", self.raw, "fictional-report.txt")

    def test_format_filename_and_size_boundaries_reject_without_writes(self):
        before = self.snapshot_rows()
        for raw, filename in [
            (b"", "record.txt"), (b"\xff\xfe\x00\x00", "record.txt"),
            (b"Text\x00binary", "record.txt"), (b"Text\x1b[2J", "record.txt"),
            (b"Text\x7f", "record.txt"), (b"Text\rbare return", "record.txt"),
            (b"%PDF-1.7\nfictional", "record.txt"),
            (b"{\\rtf1 text}", "record.txt"), (b"<html>text</html>", "record.txt"),
            ("Text\u202econtrol".encode(), "record.txt"),
            (b"text", "../record.txt"), (b"text", "folder/record.txt"),
            (b"text", "folder\\record.txt"), (b"text", "/record.txt"),
            (b"text", "record.pdf"), (b"text", "record.txt\r\nX: y"),
            (b"text", ".txt"), (b"text", "a" * 121 + ".txt"),
            (b"x" * 65537, "record.txt"),
            (b"line\n" * 513, "record.txt"), (b"text", None),
        ]:
            with self.subTest(filename=filename, prefix=raw[:30]):
                with self.assertRaises(InvalidInput):
                    self.store.preview_document("CASE-ALPHA", raw, filename)
                self.assertEqual(self.snapshot_rows(), before)
        self.assertEqual(self.store.preview_document(
            "CASE-ALPHA", b"x" * 65536, "record.txt")["byte_count"], 65536)
        self.assertEqual(len(self.store.preview_document(
            "CASE-ALPHA", b"line\n" * 512, "record.txt")["lines"]), 512)

    def test_metadata_and_findings_limits_are_explicit(self):
        before = self.snapshot_rows()
        for mutation in [
            {"document_id": "bad id"}, {"kind": "unsupported"}, {"kind": []},
            {"event_date": "2026-02-30"},
            {"event_date": None}, {"specimen_id": ""},
            {"amends_version": True}, {"amends_version": 0},
            {"manual_transcription_confirmed": False},
            {"manual_transcription_confirmed": "true"}, {"extra": "ignored?"},
        ]:
            with self.subTest(mutation=mutation):
                with self.assertRaises(InvalidInput):
                    self.import_text(metadata={**self.metadata, **mutation})
                self.assertEqual(self.snapshot_rows(), before)
        for missing in ("document_id", "kind", "event_date", "issued_at", "manual_transcription_confirmed"):
            metadata = {k: v for k, v in self.metadata.items() if k != missing}
            with self.assertRaises(InvalidInput):
                self.import_text(metadata=metadata)
        many = [{**self.findings[0], "key": f"finding-{i}"} for i in range(31)]
        with self.assertRaises(InvalidInput):
            self.import_text(findings=many)
        self.assertEqual(self.snapshot_rows(), before)

    def test_valid_dates_preserve_a_source_reported_future_event(self):
        self.import_text(metadata={**self.metadata, "event_date": "2026-04-20"})
        source = self.store.state("CASE-ALPHA")["sources"][0]
        self.assertEqual(source["event_date"], "2026-04-20")
        self.assertEqual(source["issued_at"], "2026-04-07")
        timeline = case_timeline(self.store, "CASE-ALPHA")["entries"][0]
        self.assertEqual(timeline["occurred"], "2026-04-20")
        self.assertEqual(timeline["documented"], "2026-04-07")

    def test_identical_review_is_idempotent_across_renames_and_restart(self):
        first = self.import_text()
        before = self.snapshot_rows()
        duplicate = self.import_text(filename="renamed-report.txt")
        self.assertEqual(duplicate, {"result": "duplicate", "source_id": first["source_id"], "version": 1})
        self.assertEqual(self.snapshot_rows(), before)
        self.store.close()
        self.store = CaseStore(self.path)
        self.assertEqual(self.import_text(), duplicate)
        self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["filename"],
                         "fictional-report.txt")

    def test_same_bytes_cannot_silently_change_reviewed_metadata_or_findings(self):
        self.import_text()
        before = self.snapshot_rows()
        for changes in ({"document_id": "OTHER-DOC"}, {"kind": "clinical"},
                        {"event_date": "2026-04-04"}, {"issued_at": "2026-04-08"},
                        {"specimen_id": "OTHER-SPECIMEN"}, {"amends_version": 1}):
            with self.subTest(changes=changes):
                with self.assertRaises(InvalidInput):
                    self.import_text(metadata={**self.metadata, **changes})
                self.assertEqual(self.snapshot_rows(), before)
        for findings in ([], [{**self.findings[0], "state": "negative"}],
                         [{**self.findings[0], "quote": "not assessed"}]):
            with self.assertRaises(InvalidInput):
                self.import_text(findings=findings)
            self.assertEqual(self.snapshot_rows(), before)

    def test_invalid_or_stale_amendment_rolls_back_originals_receipts_and_history(self):
        with self.assertRaises(InvalidInput):
            self.import_text(metadata={**self.metadata, "amends_version": 1})
        first = self.import_text()
        amended = self.raw.replace(b"not assessed", b"reported as pending")
        findings = [{**self.findings[0], "state": "pending",
                     "quote": "Marker Q was reported as pending."}]
        before = self.snapshot_rows()
        for metadata in [self.metadata, {**self.metadata, "amends_version": 2},
                         {**self.metadata, "amends_version": 1, "specimen_id": "NEW-SPECIMEN"},
                         {**self.metadata, "amends_version": 1, "event_date": "2026-04-04"}]:
            with self.assertRaises(InvalidInput):
                self.import_text(raw=amended, metadata=metadata, findings=findings)
            self.assertEqual(self.snapshot_rows(), before)
        second = self.import_text(raw=amended, metadata={**self.metadata, "amends_version": 1}, findings=findings)
        self.assertEqual(second["version"], 2)
        current = self.snapshot_rows()
        with self.assertRaises(InvalidInput):
            self.import_text(raw=amended + b"Different revision.\r\n",
                             metadata={**self.metadata, "amends_version": 1}, findings=findings)
        self.assertEqual(self.snapshot_rows(), current)
        self.assertEqual(self.import_text()["source_id"], first["source_id"])
        self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["raw"], self.raw)

    def test_amendment_reuses_snapshot_model_and_timeline_freshness(self):
        first = self.import_text()
        question = self.store.add_question("CASE-ALPHA", "What source passage remains unassessed?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
                                             "Fictional source transcription awaiting review.",
                                             [first["source_id"]])
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot, "Fictional unverified reviewer")
        model = self.save_model()
        unrelated = self.save_model("CASE-BETA")
        amended = self.raw.replace(b"not assessed", b"reported as pending")
        second = self.import_text(raw=amended,
            metadata={**self.metadata, "amends_version": 1, "issued_at": "2026-04-08"},
            findings=[{**self.findings[0], "state": "pending", "quote": "Marker Q was reported as pending."}])
        self.assertEqual(second["invalidated_snapshots"], [snapshot])
        self.assertEqual(second["invalidated_model_investigation_ids"], [model])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(state["snapshots"][0]["state"], "stale")
        self.assertEqual(next(q for q in state["questions"] if q["id"] == question)["state"], "open")
        self.assertTrue(self.store.get_investigation("CASE-ALPHA", model)["stale"])
        self.assertFalse(self.store.get_investigation("CASE-BETA", unrelated)["stale"])
        timeline = case_timeline(self.store, "CASE-ALPHA")
        self.assertEqual(timeline["entries"][0]["source_id"], second["source_id"])
        self.assertEqual(timeline["history"][0]["source_id"], first["source_id"])
        current_finding = timeline["entries"][0]["reported_findings"][0]
        self.assertEqual(current_finding["finding_key"], "marker-q")
        self.assertEqual(current_finding["reported_state"], "pending")
        self.assertEqual(current_finding["classification_origin"], "user_selected")
        amended = changes_since_review(self.store, "CASE-ALPHA")["amendments"][0]
        self.assertEqual(amended["classification_origin"], "user_selected")
        self.assertEqual(amended["previous_classification_origin"], "user_selected")

    def test_receipt_failure_rolls_back_shared_source_and_invalidation_transaction(self):
        first = self.import_text()
        model = self.save_model()
        self.store.db.execute("""CREATE TRIGGER reject_intake_receipt
            BEFORE INSERT ON document_intake_metadata BEGIN
            SELECT RAISE(ABORT, 'receipt unavailable'); END""")
        self.store.db.commit()
        before = self.snapshot_rows()
        amended = self.raw + b"An independently authored amendment.\r\n"
        with self.assertRaises(sqlite3.IntegrityError):
            self.import_text(raw=amended, metadata={**self.metadata, "amends_version": 1})
        self.assertEqual(self.snapshot_rows(), before)
        self.assertFalse(self.store.get_investigation("CASE-ALPHA", model)["stale"])
        self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["raw"], self.raw)

    def test_two_concurrent_amendments_cannot_both_replace_same_version(self):
        self.import_text()

        def amend(suffix):
            store = CaseStore(self.path)
            try:
                return self.import_text(store=store, raw=self.raw + suffix,
                                        metadata={**self.metadata, "amends_version": 1})["result"]
            except InvalidInput:
                return "rejected"
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(amend, [b"First correction.\r\n", b"Second correction.\r\n"]))
        self.assertEqual(sorted(results), ["imported", "rejected"])
        self.assertEqual(len(self.store.state("CASE-ALPHA")["sources"]), 2)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM document_intake_metadata").fetchone()[0], 2)

    def test_user_status_never_becomes_source_authored_through_composer_or_prompt(self):
        self.import_text(findings=[{**self.findings[0], "state": "negative"}])
        question = self.store.add_question("CASE-ALPHA", "What does the literal fictional source say?")
        state = self.store.state("CASE-ALPHA")
        assertion = state["assertions"][0]
        self.assertEqual(assertion["certainty"], "negative")
        self.assertEqual(assertion["quote"], "Marker Q was not assessed.")
        receipt_hash = state["sources"][0]["document_intake"]["review_sha256"]
        provenance = {"classification_origin": "user_selected",
                      "annotation_method": "manual-exact-line-selection",
                      "clinical_review": "not_performed",
                      "transcription_review_sha256": receipt_hash}
        facts = self.store.investigation_facts("CASE-ALPHA", question)
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        mission_statement = build_patient_mission(state)["what_we_know"][0]
        timeline_statement = case_timeline(self.store, "CASE-ALPHA")["entries"][0]["reported_findings"][0]
        change_statement = changes_since_review(self.store, "CASE-ALPHA")["new_sources"][0]["reported_findings"][0]
        for row in (assertion, facts["assertions"][0], context["source_anchors"][0],
                    context["current_sources"][0], mission_statement, timeline_statement, change_statement):
            for key, expected in provenance.items():
                self.assertEqual(row.get(key), expected, key)
        prompt = build_prompt("evidence-summary", facts["question"]["question"],
                              facts["assertions"], facts["assessments"])
        self.assertIn("quote='Marker Q was not assessed.'", prompt)
        self.assertIn("classification_origin=user_selected", prompt)
        self.assertIn("user_selected_status=negative", prompt)
        self.assertIn("clinical_review=not_performed", prompt)
        self.assertIn("not source-authored or clinically verified", prompt)
        self.assertIn("literal quote is primary", prompt)
        self.assertNotIn("certainty=negative", prompt)

    def test_composer_fingerprint_binds_manual_review_receipt_and_method(self):
        imported = self.import_text()
        question = self.store.add_question("CASE-ALPHA", "Which fictional source anchors are available?")
        before = build_composer_context(self.store, "CASE-ALPHA", question)
        self.assertEqual(before["fingerprint"], composer_context_fingerprint(self.store, "CASE-ALPHA", question))
        for column, replacement in (("review_sha256", "f" * 64),
                                    ("annotation_method", "different-manual-method")):
            # Simulate a changed source-owned receipt between preview and save.
            # Production has no receipt-update endpoint; this directly tests
            # whether a later context can silently lose its provenance binding.
            with self.store.db:
                self.store.db.execute(f"UPDATE document_intake_metadata SET {column}=? WHERE source_version_id=?",
                                      (replacement, imported["source_id"]))
            after = build_composer_context(self.store, "CASE-ALPHA", question)
            self.assertEqual(after["fingerprint"], composer_context_fingerprint(self.store, "CASE-ALPHA", question))
            self.assertNotEqual(before["fingerprint"], after["fingerprint"], column)
            result = ValidatedInvestigation("abstained", [], [], [], "recorded-replay", "replay")
            with self.assertRaisesRegex(InvalidInput, "stale"):
                self.store.save_investigation("CASE-ALPHA", question, "evidence-summary", result,
                                              "replay", context_fingerprint=before["fingerprint"])
            before = after

    def test_historical_snapshot_export_keeps_manual_origin_and_receipt(self):
        first = self.import_text(findings=[{**self.findings[0], "state": "negative"}])
        receipt = self.store.state("CASE-ALPHA")["sources"][0]["document_intake"]["review_sha256"]
        question = self.store.add_question("CASE-ALPHA", "What requires independent source review?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "The manually classified source still requires independent review.", [first["source_id"]])
        self.import_text(raw=self.raw + b"Fictional later amendment.\r\n",
                         metadata={**self.metadata, "amends_version": 1})
        exported = self.store.export_markdown("CASE-ALPHA", snapshot)
        self.assertIn("**stale**", exported)
        self.assertIn("classification_origin=user_selected", exported)
        self.assertIn("manual-exact-line-selection", exported)
        self.assertIn("clinical_review=not_performed", exported)
        self.assertIn(receipt, exported)
        self.assertIn("Marker Q was not assessed.", exported)

    def test_legacy_v2_fingerprint_and_prompt_remain_byte_identical(self):
        # Golden values captured before this intake provenance extension, for
        # the existing v2 contract with a fixed fictional source receipt time.
        self.store.import_report("CASE-ALPHA", (
            b"OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: LEGACY-DOC\n"
            b"Type: clinical\nEvent-Date: 2026-04-05\nIssued-At: 2026-04-07\n"
            b"Finding: marker-q|not-assessed|Marker Q was not assessed.\n"))
        with self.store.db:
            self.store.db.execute("UPDATE source_versions SET received_at='2026-04-07T09:00:00+00:00'")
        question = self.store.add_question("CASE-ALPHA", "What does the fictional source state?")
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        self.assertEqual(context["fingerprint"],
                         "f12075caff5210635b78d947f98c39770dc2b0069c27d894759236bc8b2a0d0f")
        facts = self.store.investigation_facts("CASE-ALPHA", question)
        prompt = build_prompt("evidence-summary", facts["question"]["question"],
                              facts["assertions"], facts["assessments"], facts["external_evidence"])
        self.assertEqual(hashlib.sha256(prompt.encode()).hexdigest(),
                         "52b3e5a4052154dc458758423ce57e53927bab8541d86a425a8e8a002c0ace0a")
        self.assertNotIn("classification_origin", context["source_anchors"][0])


if __name__ == "__main__":
    unittest.main()
