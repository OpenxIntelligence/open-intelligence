"""Exact text-class rights through the existing patient/EHR/LIS/report owners.

Original fictional sources and injected fixture permissions only. No API call,
patient data, model inference, publisher clearance or clinical authority.
"""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import test_report_review_handoff as fixture
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.store import CaseStore

CASE = fixture.fixture.CASE
TEXT_ITEMS = ("api_output", "abstract", "full_text")
ALL_USES = {use: "allowed" for use in ("store", "display", "ml_use", "redistribute")}


class GovernedReportContentTests(unittest.TestCase):
    # Reuse real domain fixtures, not inherited test cases/counts.
    setUp = fixture.ReportReviewHandoffTests.setUp
    actor = fixture.ReportReviewHandoffTests.actor
    workflow = fixture.ReportReviewHandoffTests.workflow
    _source = fixture.ReportReviewHandoffTests._source
    prepare = fixture.ReportReviewHandoffTests.prepare
    candidate = fixture.ReportReviewHandoffTests.candidate
    setup_service = fixture.ReportReviewHandoffTests.setup_service
    call = fixture.ReportReviewHandoffTests.call

    def setup_content(self, item="api_output"):
        service, q, assessment, sources, quotes = self.setup_service()
        source = sources[0]
        source["content_item"] = item
        source["permissions"] = {
            "metadata": dict(ALL_USES), item: dict(ALL_USES),
        }
        return service, q, assessment, sources, quotes

    def preview(self, service, q, quotes):
        return service.report.packets.preview(
            self.patient_id, CASE, q, selected_quotes=quotes, **self.actor())

    def render(self, service, q, quotes):
        return service.report.render(
            self.patient_id, CASE, q, selected_quotes=quotes, **self.actor())

    def context(self, service, q):
        return service.report.packets.bridge.snapshot(
            self.patient_id, CASE, q, **self.actor())

    def test_exact_api_output_reaches_source_quote_report_and_real_receipt(self):
        service, q, assessment, sources, quotes = self.setup_content()
        before = self.store.state(CASE)
        context = self.context(service, q)
        source = context["knowledge"]["knowledge_sources"][0]
        self.assertEqual(source.get("content_item"), "api_output")
        self.assertEqual(source.get("content_item_basis"), "declared")
        self.assertFalse(context["model_execution_authorized"])
        packet = self.preview(service, q, quotes)
        self.assertEqual(packet["quoted_comparisons"][0]["external_reference"].get(
            "content_item"), "api_output")
        self.assertEqual(self.store.state(CASE), before)  # preview is read-only
        result = self.call(service, q, assessment, quotes)
        self.assertIn('Evidence content item: "api_output"', result["report"]["body"])
        self.assertIn('Content item basis: "declared"', result["report"]["body"])
        self.assertEqual(result["report"]["body_sha256"], hashlib.sha256(
            result["report"]["body"].encode()).hexdigest())
        self.assertEqual(result["receipt"]["result"], "returned_for_independent_review")
        self.assertFalse(result["clinical_signoff"])
        self.assertFalse(result["report"]["model_executed"])
        self.assertEqual(next(r["state"] for r in self.store.state(CASE)["questions"]
                              if r["id"] == q), "open")
        event = next(e for e in self.store.state(CASE)["events"]
                     if e["kind"] == "review_receipt_recorded")
        ref = json.loads(event["details"])["prepared_report"]
        self.assertEqual(ref["packet_sha256"], result["report"]["packet_sha256"])
        self.assertEqual(ref["body_sha256"], result["report"]["body_sha256"])
        self.assertNotIn(sources[0]["evidence_text"], event["details"])
        reopened = CaseStore(self.store.path)
        try:
            self.assertEqual(reopened.review_queue(CASE)["receipts"][0]["id"],
                             result["receipt"]["receipt_id"])
        finally:
            reopened.close()

    def test_abstract_and_full_text_keep_their_own_label_and_original_hash(self):
        service, q, _, sources, quotes = self.setup_content()
        text_hash = hashlib.sha256(sources[0]["evidence_text"].encode()).hexdigest()
        for item in TEXT_ITEMS:
            with self.subTest(item=item):
                sources[0]["content_item"] = item
                sources[0]["permissions"] = {"metadata": dict(ALL_USES), item: dict(ALL_USES)}
                reference = self.preview(service, q, quotes)["quoted_comparisons"][0]["external_reference"]
                self.assertEqual(reference.get("content_item"), item)
                self.assertEqual(reference["evidence_text_sha256"], text_hash)
                self.assertIn(f'Evidence content item: "{item}"', self.render(service, q, quotes)["body"])
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_legacy_omission_is_full_text_but_explicit_invalid_class_never_defaults(self):
        service, q, _, sources, quotes = self.setup_service()
        source = self.context(service, q)["knowledge"]["knowledge_sources"][0]
        self.assertEqual(source.get("content_item"), "full_text")
        self.assertEqual(source.get("content_item_basis"), "legacy_full_text_default")
        self.assertIn('Content item basis: "legacy_full_text_default"',
                      self.render(service, q, quotes)["body"])
        for value in (None, True, 1, {}, [], "", "metadata", "figures", "API_OUTPUT", "api_output "):
            sources[0]["content_item"] = value
            with self.subTest(value=value), self.assertRaises(KnowledgeContextError):
                self.context(service, q)

    def test_permissions_never_cross_between_text_classes(self):
        service, q, assessment, sources, quotes = self.setup_content()
        for declared in TEXT_ITEMS:
            for permitted_item in TEXT_ITEMS:
                if declared == permitted_item:
                    continue
                sources[0]["content_item"] = declared
                sources[0]["permissions"] = {"metadata": dict(ALL_USES), permitted_item: dict(ALL_USES)}
                before = self.store.state(CASE)
                with self.subTest(declared=declared, permitted_item=permitted_item):
                    with self.assertRaises(KnowledgeContextError):
                        self.call(service, q, assessment, quotes)
                self.assertEqual(self.store.state(CASE), before)

    def test_each_exact_class_operation_is_required_and_metadata_is_separate(self):
        service, q, assessment, sources, quotes = self.setup_content()
        for item in TEXT_ITEMS:
            for operation in ("store", "display", "ml_use", "redistribute"):
                for value in ("denied", "unknown", None):
                    sources[0]["content_item"] = item
                    sources[0]["permissions"] = {
                        "metadata": dict(ALL_USES), item: dict(ALL_USES),
                    }
                    if value is None:
                        sources[0]["permissions"][item].pop(operation)
                    else:
                        sources[0]["permissions"][item][operation] = value
                    with self.subTest(item=item, operation=operation, value=value):
                        if operation == "redistribute":
                            self.assertEqual(self.preview(service, q, quotes)["human_review_state"], "pending")
                        with self.assertRaises(KnowledgeContextError):
                            self.call(service, q, assessment, quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])
        sources[0]["content_item"] = "api_output"
        for operation in ("store", "display", "redistribute"):
            sources[0]["permissions"] = {"metadata": dict(ALL_USES), "api_output": dict(ALL_USES)}
            sources[0]["permissions"]["metadata"][operation] = "unknown"
            with self.subTest(metadata_operation=operation), self.assertRaises(KnowledgeContextError):
                self.call(service, q, assessment, quotes)

    def test_allowed_full_text_export_cannot_cover_nonredistributable_api_text(self):
        service, q, assessment, sources, quotes = self.setup_content()
        sources[0]["permissions"]["full_text"] = dict(ALL_USES)
        sources[0]["permissions"]["api_output"]["redistribute"] = "denied"
        self.assertFalse(self.preview(service, q, quotes)["quoted_comparisons"][0]
                         ["external_reference"]["report_export_allowed"])
        with self.assertRaises(KnowledgeContextError):
            self.call(service, q, assessment, quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_source_family_does_not_infer_or_supply_a_content_grant(self):
        service, q, _, sources, _ = self.setup_content()
        sources[0]["family"] = "civic"
        sources[0].pop("content_item")
        with self.assertRaises(KnowledgeContextError):
            self.context(service, q)
        sources[0]["content_item"] = "api_output"
        source = self.context(service, q)["knowledge"]["knowledge_sources"][0]
        self.assertEqual(source.get("content_item"), "api_output")
        self.assertEqual(source["rights_status"], "approved")  # fictional declaration, not legal proof

    def test_identical_words_in_linked_abstract_do_not_inherit_api_rights(self):
        service, q, _, sources, quotes = self.setup_content()
        abstract = copy.deepcopy(sources[0])
        abstract.update(id="SYNTHETIC-LINKED-ABSTRACT", public_identifier="FICTIONAL-PAPER",
                        content_item="abstract")
        sources.append(abstract)
        with self.assertRaises(KnowledgeContextError):
            self.preview(service, q, quotes)
        abstract.pop("evidence_text")
        packet = self.preview(service, q, quotes)
        self.assertEqual(len(packet["quoted_comparisons"]), 1)
        self.assertEqual(packet["missing_or_withheld_evidence"][0]["knowledge_id"], abstract["id"])
        self.assertNotIn("FICTIONAL-PAPER", self.render(service, q, quotes)["body"])

    def test_changing_only_class_changes_report_and_packet_hash(self):
        service, q, _, sources, quotes = self.setup_content()
        sources[0]["permissions"] = {"metadata": dict(ALL_USES), **{
            item: dict(ALL_USES) for item in TEXT_ITEMS}}
        first = self.render(service, q, quotes)
        sources[0]["content_item"] = "abstract"
        second = self.render(service, q, quotes)
        self.assertNotEqual(first["packet_sha256"], second["packet_sha256"])
        self.assertNotEqual(first["body_sha256"], second["body_sha256"])
        self.assertIn('"api_output"', first["body"])
        self.assertIn('"abstract"', second["body"])

    def test_class_change_during_render_rejects_even_when_all_rights_allow(self):
        service, q, assessment, sources, quotes = self.setup_content()
        sources[0]["permissions"] = {"metadata": dict(ALL_USES), **{
            item: dict(ALL_USES) for item in TEXT_ITEMS}}
        original = service.report._render_text
        def change(packet):
            body = original(packet)
            sources[0]["content_item"] = "abstract"
            return body
        with patch.object(service.report, "_render_text", side_effect=change):
            with self.assertRaises(ClinicalContinuityError):
                self.call(service, q, assessment, quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_after_preparation_revocation_withholds_body_but_keeps_nonterminal_history(self):
        service, q, assessment, sources, quotes = self.setup_content()
        original = self.store.add_review_receipt
        def revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            sources[0]["permissions"]["api_output"]["redistribute"] = "denied"
            return result
        with patch.object(self.store, "add_review_receipt", side_effect=revoke):
            with self.assertRaises(KnowledgeContextError):
                self.call(service, q, assessment, quotes)
        queue = self.store.review_queue(CASE)
        self.assertEqual(len(queue["receipts"]), 1)
        self.assertEqual(queue["receipts"][0]["action"], "returned")
        self.assertEqual(queue["resolved"], [])

    def test_source_correction_and_rights_revocation_preserve_previous_receipt(self):
        service, q, assessment, sources, quotes = self.setup_content()
        result = self.call(service, q, assessment, quotes)
        sources[0]["rights_state"] = "revoked"
        with self.assertRaises(KnowledgeContextError):
            self.render(service, q, quotes)
        sources[0]["rights_state"] = "approved"
        self._source("ORDER-CONT-001", "clinical", "order", "negative", amendment=1)
        with self.assertRaises(KnowledgeContextError):
            self.render(service, q, quotes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"][0]["id"], result["receipt"]["receipt_id"])
        self.assertIn('Evidence content item: "api_output"', result["report"]["body"])

    def test_export_and_review_authority_still_fail_before_provider_or_write(self):
        service, q, assessment, _, quotes = self.setup_content()
        bridge = service.report.packets.bridge
        original_export = service.report.export_authorizer
        service.report.export_authorizer = None
        with patch.object(bridge, "source_provider", wraps=bridge.source_provider) as provider:
            with self.assertRaises(PermissionError):
                self.call(service, q, assessment, quotes)
            provider.assert_not_called()
        service.report.export_authorizer = original_export
        for changes in ({"actor": "idp:untrusted"}, {"purpose": "research"},
                        {"case_id": "CASE-CLIN-CONT-OTHER"}, {"question_id": q + 99}):
            with self.subTest(changes=changes), self.assertRaises((PermissionError, ValueError)):
                self.call(service, q, assessment, quotes, **changes)
        self.assertEqual(self.store.review_queue(CASE)["receipts"], [])

    def test_audit_failure_rolls_back_typed_report_preparation(self):
        service, q, assessment, _, quotes = self.setup_content()
        before = self.store.state(CASE)
        with patch.object(self.store, "_event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
                self.call(service, q, assessment, quotes)
        self.assertEqual(self.store.state(CASE), before)


if __name__ == "__main__":
    unittest.main()
