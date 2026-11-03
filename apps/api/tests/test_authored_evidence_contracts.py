"""Human-only evidence boundaries using newly authored fictional text."""
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import Mock

from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.rights import normalize_permissions
from oi_api.evidence_report import canonical_hash, human_content_allowed, quote_offset, render_evidence_report
from oi_api.authored_evidence import PostgresQuestionEvidence
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.authored_evidence_contracts import EvidencePacket, EvidenceReport, ImportEvidence, AssessEvidence
from pydantic import ValidationError
from test_question_source_brief import fictional_brief_inputs


def permissions(item="abstract", **changes):
    result = normalize_permissions({
        "metadata": {"store": "allowed", "display": "allowed", "redistribute": "allowed"},
        item: {"store": "allowed", "display": "allowed", "redistribute": "allowed"},
    })
    result[item].update(changes)
    return result


def snapshot():
    _, question, source = fictional_brief_inputs()
    evidence = {
        "evidence_id": "EVIDENCE-" + "A" * 32, "evidence_key": "EVIDENCE-ALPHA", "version": 1,
        "sha256": "a" * 64, "statement_line": 6, "content_item": "abstract",
        "rights_sha256": canonical_hash(permissions()), "permissions": permissions(),
        "state": "current", "title": "Fictional comparison experiment",
        "issued_at": "2026-01-10", "statement": "A fictional 🧪 observation stays uncertain.",
        "created_at": "2026-11-03T00:00:00+00:00",
    }
    assessment = {
        "assessment_id": "ASSESSMENT-" + "B" * 32, "question_id": question["question_id"],
        "evidence_id": evidence["evidence_id"], "evidence_sha256": evidence["sha256"],
        "rights_sha256": evidence["rights_sha256"],
        "source_snapshot_sha256": question["source_snapshot_sha256"],
        "preflight_sha256": question["preflight_sha256"], "relation": "contradicts",
        "applicability": "limited", "quote": "observation stays uncertain", "quote_start": 14,
        "rationale": "This fictional passage leaves the claimed result uncertain.",
        "actor_label": "AUTHOR-FIXTURE", "created_at": "2026-11-03T00:00:00+00:00",
        "state": "current_unreviewed",
    }
    assessment["quote_start"] = evidence["statement"].index(assessment["quote"])
    return {"question": question, "selected_source": source,
            "comparisons": [{"assessment": assessment, "evidence": evidence}],
            "prepared_at": "2026-11-03T00:00:00+00:00", "actor_label": "AUTHOR-FIXTURE"}


class QuestionEvidencePureTests(unittest.TestCase):
    def test_declared_item_and_historical_item_rights_are_independent(self):
        original = permissions("full_text")
        current = permissions("abstract")
        self.assertTrue(human_content_allowed(original, original, "full_text"))
        self.assertFalse(human_content_allowed(original, current, "full_text"))
        self.assertFalse(human_content_allowed(original, original, "full_text", withdrawn=True))
        self.assertTrue(human_content_allowed(permissions(), permissions(), "abstract"))
        self.assertEqual(permissions()["abstract"]["ml_use"], "unknown")

    def test_display_does_not_grant_redistribution_or_metadata(self):
        rights = permissions(redistribute="unknown")
        self.assertTrue(human_content_allowed(rights, rights, "abstract"))
        self.assertFalse(human_content_allowed(rights, rights, "abstract", export=True))
        rights["metadata"]["display"] = "denied"
        self.assertFalse(human_content_allowed(rights, rights, "abstract"))

    def test_quote_is_unique_literal_and_unicode_codepoint_anchored(self):
        statement = "🧪 Fictional café evidence remains pending."
        self.assertEqual(quote_offset(statement, "café evidence"), 12)
        for quote in ("", "not present", "x" * 401):
            with self.subTest(quote=quote), self.assertRaises(PatientRegistryError):
                quote_offset(statement, quote)
        with self.assertRaises(PatientRegistryError):
            quote_offset("Fictional repeated repeated passage.", "repeated")
        with self.assertRaises(PatientRegistryError):
            quote_offset("Fictional aaa overlap.", "aa")

    def test_report_preserves_literal_provenance_and_human_proposal_meaning(self):
        value = snapshot()
        before = deepcopy(value)
        body = render_evidence_report(value)
        self.assertEqual(value, before)
        for expected in ("PROPOSED CONTRADICTION", "limited", "AUTHOR-FIXTURE", "abstract",
                         value["comparisons"][0]["assessment"]["quote"], "not performed",
                         value["selected_source"]["source_id"], "not an exhaustive"):
            self.assertIn(expected, body)
        self.assertNotIn("clinically approved", body)

    def test_download_body_includes_frozen_metadata_and_declared_item_permissions(self):
        value = snapshot()
        body = render_evidence_report(value)
        for item in ("metadata", "abstract"):
            for use in ("store", "display", "redistribute", "ml_use"):
                expected = value["comparisons"][0]["evidence"]["permissions"][item][use]
                self.assertIn(f"{item}/{use}: {expected}", body)
        self.assertIn("not independently verified clearance", body)

    def test_legacy_report_renderer_preserves_the_published_0009_body_bytes(self):
        body = render_evidence_report(snapshot(), renderer="oi.h1-evidence-text/1")
        # Independently checked against the immutable 7ce75e9 renderer before
        # this compatibility assertion was added; no old report is re-rendered
        # into the new format or assigned a replacement digest at migration.
        self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(),
                         "0537833d93e8c73bd21bfc182f3b8dfb0a1cfdcd8f0fa3f28a61df9a86c4e050")
        self.assertNotIn("metadata/store: allowed", body)
        self.assertIn("metadata/store: allowed", render_evidence_report(snapshot()))

    def test_report_rejects_invalid_or_noncanonical_evidence_issue_dates(self):
        for issued in ("2026-02-30", "2025-02-29", "2026-1-10", "20260110",
                       "2026-W02-6", "2026-01-10T00:00:00Z",
                       "2026-01-10\nUNVERIFIED EXTRA REPORT LINE"):
            value = snapshot()
            value["comparisons"][0]["evidence"]["issued_at"] = issued
            for renderer in ("oi.h1-evidence-text/1", "oi.h1-evidence-text/2"):
                with self.subTest(issued=issued, renderer=renderer), self.assertRaises(PatientRegistryError):
                    render_evidence_report(value, renderer=renderer)

    def test_report_rejects_nonwire_timestamps_before_rendering(self):
        paths = (("prepared_at",), ("question", "created_at"),
                 ("comparisons", 0, "evidence", "created_at"),
                 ("comparisons", 0, "assessment", "created_at"))
        for timestamp in ("2026-11-03\n00:00:00+00:00", "2026-11-03\t00:00:00+00:00",
                          "2026-11-03\u202e00:00:00+00:00", "2026-11-03 00:00:00+00:00",
                          "20261103T000000+0000", "2026-11-03T00:00:00"):
            for path in paths:
                value = snapshot()
                target = value
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = timestamp
                with self.subTest(timestamp=timestamp, path=path), self.assertRaises(PatientRegistryError):
                    render_evidence_report(value)

    def test_valid_dates_and_timezone_strings_are_preserved_without_normalization(self):
        for issued in ("2000-02-29", "2024-02-29", "2026-01-10"):
            for timestamp in ("2026-11-03T00:00:00Z", "2026-11-03T05:30:00.123456+05:30",
                              "2026-11-02T19:00:00-05:00", "2026-11-03T00:00+00:00"):
                value = snapshot()
                value["prepared_at"] = timestamp
                value["comparisons"][0]["evidence"]["issued_at"] = issued
                before = deepcopy(value)
                body = render_evidence_report(value)
                self.assertIn(f"Prepared: {timestamp} |", body)
                self.assertIn(f" | Issued: {issued}\n", body)
                self.assertEqual(value, before)

    def test_exact_command_recovery_accepts_pg8000_list_rows(self):
        registry = object.__new__(PostgresPatientRegistry)
        owner = PostgresQuestionEvidence(registry)
        eid = "EVIDENCE-" + "C" * 32
        payload = {"synthetic": True, "request_key": "PG8000-LIST-RETRY", "original_text": "fictional bytes",
                   "content_item": "abstract", "permissions": permissions()}
        context = {"patient_id": "PAT-" + "D" * 32, "case_id": "CASE-ALPHA", "question_id": "QUESTION-" + "E" * 32,
                   "organization": "ORG-FIXTURE", "actor": "ACTOR-FIXTURE", "purpose": "operations",
                   "versions": {eid: {"version": 1, "original_bytes": b"fictional bytes",
                                      "content_item": "abstract", "permissions": permissions()}}}
        intent = canonical_hash({**{key: context[key] for key in (
            "patient_id", "case_id", "question_id", "organization", "actor", "purpose")},
            "operation": "import", "payload": payload})
        registry._fetchone = Mock(return_value=[intent, {"evidence_id": eid, "version": 1},
                                               "ORG-FIXTURE", "ACTOR-FIXTURE", "operations"])
        apply = Mock(side_effect=AssertionError("Exact recovery must not invoke a new write"))
        self.assertEqual(owner._command(context, "import", payload, apply),
                         {"evidence_id": eid, "version": 1, "duplicate": True})
        apply.assert_not_called()

    def test_withdrawal_recovery_accepts_pg8000_list_rows(self):
        registry = object.__new__(PostgresPatientRegistry)
        owner = PostgresQuestionEvidence(registry)
        eid, wid = "EVIDENCE-" + "D" * 32, "WITHDRAWAL-" + "E" * 32
        context = {"patient_id": "PAT-" + "D" * 32, "case_id": "CASE-ALPHA", "organization": "ORG-FIXTURE", "actor": "ACTOR-FIXTURE"}
        payload = {"evidence_id": eid, "reason": "The fictional declaration was withdrawn for review."}
        registry._fetchone = Mock(return_value=[eid, payload["reason"], context["actor"]])
        result = {"evidence_id": eid, "withdrawal_id": wid}
        self.assertEqual(owner._recovered_result(context, "withdraw", payload, result),
                         {**result, "duplicate": True})

    def test_snapshot_rejects_forged_patient_source_and_evidence_alignment(self):
        for path, field, value in (
            (("question",), "source_sha256", "0" * 64),
            (("comparisons", 0, "assessment"), "evidence_id", "EVIDENCE-" + "F" * 32),
            (("comparisons", 0, "assessment"), "quote_start", 0),
            (("comparisons", 0, "assessment"), "state", "reassessment_required"),
        ):
            modified = snapshot()
            target = modified
            for component in path:
                target = target[component]
            target[field] = value
            with self.subTest(field=field), self.assertRaises(PatientRegistryError):
                render_evidence_report(modified)

    def test_control_characters_are_visible_in_report_literals(self):
        value = snapshot()
        value["selected_source"]["statement"] += "\u202e reverse\ntext"
        body = render_evidence_report(value)
        self.assertNotIn("\u202e", body)
        self.assertIn("\\u202e", body)
        self.assertIn("\\n", body)

    def test_write_shapes_reject_wrong_flags_and_support_not_applicable(self):
        with self.assertRaises(ValidationError):
            ImportEvidence(synthetic=False, request_key="REQUEST-A", original_text="fictional",
                           content_item="abstract", permissions=permissions())
        assessment = snapshot()["comparisons"][0]["assessment"]
        payload = {"synthetic": True, "request_key": "REQUEST-A", "evidence_id": assessment["evidence_id"],
                   "evidence_sha256": assessment["evidence_sha256"], "rights_sha256": assessment["rights_sha256"],
                   "expected_source_snapshot_sha256": assessment["source_snapshot_sha256"],
                   "expected_preflight_sha256": assessment["preflight_sha256"], "quote": assessment["quote"],
                   "relation": "supports", "applicability": "not_applicable", "rationale": assessment["rationale"]}
        with self.assertRaises(ValidationError):
            AssessEvidence(**payload)

    def test_report_contract_hashes_and_withheld_shape_fail_closed(self):
        value = snapshot()
        body = render_evidence_report(value)
        response = {"contract": "oi.h1-evidence-report/1", "patient_id": value["question"]["patient_id"],
                    "case_id": value["question"]["case_id"], "question_id": value["question"]["question_id"],
                    "report_id": "REPORT-" + "E" * 32, "prepared_at": value["prepared_at"],
                    "state": "current_unreviewed", "body": body,
                    "body_sha256": hashlib.sha256(body.encode()).hexdigest(), "snapshot": value,
                    "snapshot_sha256": canonical_hash(value), "access_receipt_id": "ACCESS-" + "F" * 32,
                    "synthetic": True, "human_review_state": "not_performed",
                    "clinical_approval": False, "model_executed": False}
        EvidenceReport(**response)
        for change in ({"body_sha256": "0" * 64}, {"state": "content_withheld"},
                       {"clinical_approval": True}, {"question_id": "QUESTION-" + "F" * 32}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                EvidenceReport(**{**response, **change})
        EvidenceReport(**{**response, "state": "content_withheld", "body": None, "snapshot": None})


if __name__ == "__main__":
    unittest.main()
