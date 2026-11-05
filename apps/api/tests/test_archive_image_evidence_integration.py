"""Real PG16/HTTP archive acceptance across questions, tasks and authored reports.

Reuse #313/#327's independently authored fixtures and helpers, without inheriting
their test methods. Comparisons remain human-authored and unreviewed; this makes
no clinical or model claim. The controlled archive is not live PACS qualification.
"""
import hashlib
import json
from unittest.mock import Mock

from http_support import running_server
from oi_api.app import create_app
from oi_api.database import Database
from oi_api.evidence_catalog import (
    append_rights_decision, fictional_records, seed_fictional_records,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
import test_archive_question_review_integration as archive_reviews
import test_image_evidence_integration as connected
import test_image_report_convergence as report_fixtures
from test_evidence_owner_convergence import AUTHORED_ACTIONS, ORIGINAL_EVIDENCE, QUOTE
from test_image_custody import AMENDED, image_bytes, image_request
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class ArchiveImageEvidenceIntegrationHTTPTests(SourceVersionFixture):
    case_path = staticmethod(connected.ImageEvidenceIntegrationHTTPTests.case_path)
    image_path = connected.ImageEvidenceIntegrationHTTPTests.image_path
    read_json = connected.ImageEvidenceIntegrationHTTPTests.read_json
    prepare_question = connected.ImageEvidenceIntegrationHTTPTests.prepare_question
    question_intent = staticmethod(connected.ImageEvidenceIntegrationHTTPTests.question_intent)
    save_question = connected.ImageEvidenceIntegrationHTTPTests.save_question
    rows = connected.ImageEvidenceIntegrationHTTPTests.rows
    queue = connected.ImageEvidenceIntegrationHTTPTests.queue
    return_url = connected.ImageEvidenceIntegrationHTTPTests.return_url
    return_question = connected.ImageEvidenceIntegrationHTTPTests.return_question
    assert_preserved = connected.ImageEvidenceIntegrationHTTPTests.assert_preserved
    command = connected.ImageEvidenceIntegrationHTTPTests.command
    retry = connected.ImageEvidenceIntegrationHTTPTests.retry
    denied = connected.ImageEvidenceIntegrationHTTPTests.denied
    context_intent = staticmethod(connected.ImageEvidenceIntegrationHTTPTests.context_intent)
    packet_and_brief = connected.ImageEvidenceIntegrationHTTPTests.packet_and_brief
    populated_case = connected.ImageEvidenceIntegrationHTTPTests.populated_case
    assert_withheld = archive_reviews.ArchiveQuestionReviewIntegrationHTTPTests.assert_withheld
    assert_preserved_report = report_fixtures.ImageReportConvergenceHTTPTests.assert_preserved_report

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_packet_read", "source_brief_export", "review_queue_read", "review_return",
            "image_import", "image_read", "image_original_read",
            "followthrough_create", "followthrough_read", "followthrough_update",
            "evidence_read", "evidence_link",
            *AUTHORED_ACTIONS,
        ))
        self.write()
        database = Database(self.settings)
        try:
            with database.registry_connection() as connection:
                seed_fictional_records(
                    PostgresPatientRegistry(connection, lambda *args: False),
                    fictional_records(), recorded_by="FIXTURE-AUTHOR",
                )
        finally:
            database.close()
        self.raw = image_bytes()
        self.archive = Mock()
        self.archive.read.return_value = self.raw

    def durable_state(self):
        state = connected.ImageEvidenceIntegrationHTTPTests.durable_state(self)
        for table in (
            "case_evidence_versions", "case_evidence_withdrawals",
            "question_evidence_assessments", "question_evidence_reports",
            "evidence_commands", "evidence_command_origins",
        ):
            state[table] = self.rows(
                f"SELECT row_to_json(t)::text FROM investigation.{table} t ORDER BY row_to_json(t)::text")
        return state

    def populate_question(self, base, patient, source, *, version=1):
        flow = connected.ImageEvidenceIntegrationHTTPTests.populate_question(
            self, base, patient, source, version=version)
        prefix = flow["question_path"]
        packet = self.read_json(base, prefix + "/evidence")
        self.assertEqual((packet["assessments"], packet["reports"]), ([], []))
        authored_writes = []
        if version == 1:
            self.assertEqual(packet["evidence"], [], "A citation is not an authored passage")
            authored_writes.append(self.command(base, prefix + "/evidence", {
                "synthetic": True, "request_key": "ARCHIVE-REPORT-ORIGINAL",
                "original_text": ORIGINAL_EVIDENCE, "content_item": "api_output",
                "permissions": report_fixtures.declared_rights(),
            }))
            packet = self.read_json(base, prefix + "/evidence")
        evidence, = packet["evidence"]
        comparison = self.command(base, prefix + "/evidence-assessments", {
            "synthetic": True, "request_key": f"ARCHIVE-COMPARISON-V{version}",
            "evidence_id": evidence["evidence_id"], "evidence_sha256": evidence["sha256"],
            "rights_sha256": evidence["rights_sha256"],
            "expected_source_snapshot_sha256": flow["prepared"]["source_snapshot_sha256"],
            "expected_preflight_sha256": flow["prepared"]["preflight_sha256"],
            "quote": QUOTE, "relation": "context", "applicability": "limited",
            "rationale": "An independently authored continuity comparison; image custody is not clinical evidence.",
        })
        packet = self.read_json(base, prefix + "/evidence")
        preparation = self.command(base, prefix + "/evidence-reports", {
            "synthetic": True, "request_key": f"ARCHIVE-REPORT-V{version}",
            "expected_packet_sha256": packet["packet_sha256"],
            "assessment_ids": [comparison[2]["assessment_id"]],
        })
        report_path = prefix + "/evidence-reports/" + preparation[2]["report_id"]
        report = self.read_json(base, report_path)
        self.assertEqual((report["state"], report["question_id"]),
                         ("current_unreviewed", flow["question"]))
        self.assertEqual(report["body_sha256"], hashlib.sha256(report["body"].encode()).hexdigest())
        self.assertEqual(report["snapshot"]["selected_source"], flow["prepared"]["selected_source"])
        self.assertEqual(report["snapshot"]["prepared_at"], report["prepared_at"])
        self.assertFalse(report["clinical_approval"])
        self.assertFalse(report["model_executed"])
        self.assertEqual(report["human_review_state"], "not_performed")
        self.assertNotIn(flow["metadata"]["citation"], report["body"])
        authored_writes.extend((comparison, preparation))
        flow.update(report_path=report_path, report=report, evidence=evidence,
                    authored_writes=authored_writes)
        flow["writes"].extend(authored_writes)
        return flow

    def read_archive(self, base, path):
        """A real read appends only its own receipt; other owners stay unchanged."""
        before = self.durable_state()
        calls = self.archive.read.call_count
        code, raw, headers = image_request(base, path)
        self.assertEqual((code, raw), (200, self.raw))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.archive.read.call_count, calls + 1)
        self.archive.read.assert_called_with("2.25.101", "2.25.102", "2.25.103")
        after = self.durable_state()
        self.assert_preserved(before, after, except_for={"events"})
        self.assertEqual(after["events"][:-1], before["events"])
        event = after["events"][-1]
        self.assertEqual(event[1], "image.original_read_authorized")
        self.assertEqual(event[2]["receipt_id"], headers["X-OI-Access-Receipt"])
        return headers["X-OI-Access-Receipt"]

    def test_archive_amendment_relink_preserves_question_return_task_and_citation_history(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            flow, image, raw = self.populated_case(base)
            self.assertEqual(raw, self.raw)
            self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            patient, source = flow["patient"], flow["source"]
            prefix = self.case_path(patient)
            old_path = self.image_path(patient, source) + "/" + image["image_id"]
            queue = self.queue(base, patient)
            history = self.durable_state()
            self.read_archive(base, old_path)
            self.assert_preserved_report(base, flow, "current_unreviewed")
            self.assertEqual(self.read_json(base, prefix + "/world-model")["snapshot_fingerprint"],
                             flow["world"]["snapshot_fingerprint"])
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            self.assertEqual(self.queue(base, patient)["receipts"], queue["receipts"])

            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amendment["version"]), (201, 2))
            self.assert_preserved_report(base, flow, "historical_reassessment_required")
            current_source = amendment["source_id"]
            current_path = self.image_path(patient, current_source)
            after_amendment = self.durable_state()
            for owner in connected.HISTORY_OWNERS:
                self.assertEqual(after_amendment[owner], history[owner], owner)
            task = self.read_json(base, prefix + "/followthrough")["tasks"][0]
            self.assertEqual(task, {**flow["task"], "source_context_state": "source_reassessment_required",
                                    "needs_recheck": True})
            links = self.read_json(base, flow["citation"][0])
            self.assertEqual(links["source_context_state"], "source_reassessment_required")
            self.assertEqual(links["links"], flow["links"])
            self.assertEqual(self.queue(base, patient)["receipts"], queue["receipts"])
            calls = self.archive.read.call_count
            before_denial = self.durable_state()
            for path in (old_path, current_path + "/" + image["image_id"]):
                self.assert_withheld(image_request(base, path), 404, before_denial)
            self.assertEqual(self.archive.read.call_count, calls)
            self.retry(base, flow["writes"])
            stale = [(path, {**body, "request_key": body["request_key"] + "-NEW"})
                     for path, body, _ in (flow["writes"][0], flow["writes"][1],
                                           flow["writes"][2], flow["citation"])]
            self.denied(base, stale, status=409)
            self.assert_preserved_report(base, flow, "historical_reassessment_required")

            before_link = self.durable_state()
            status, linked, _ = image_request(base, current_path, raw=self.raw)
            self.assertEqual((status, linked["result"], linked["image_id"]),
                             (201, "linked", image["image_id"]))
            self.assertEqual(self.archive.read.call_count, calls)
            self.assert_preserved(before_link, self.durable_state(), except_for={"image_links", "events"})
            fresh = self.populate_question(base, patient, current_source, version=2)
            self.assertNotEqual(fresh["question"], flow["question"])
            self.assertNotEqual(fresh["writes"][1][2]["receipt_id"], flow["writes"][1][2]["receipt_id"])
            self.assertNotEqual(fresh["task"]["task_id"], flow["task"]["task_id"])
            self.assertNotEqual(fresh["citation"][2]["link_id"], flow["citation"][2]["link_id"])
            self.assertNotEqual(fresh["report"]["report_id"], flow["report"]["report_id"])
            self.assertNotEqual(fresh["report"]["snapshot_sha256"], flow["report"]["snapshot_sha256"])
            self.assertEqual(fresh["evidence"]["evidence_id"], flow["evidence"]["evidence_id"])
            self.read_archive(base, current_path + "/" + image["image_id"])
            self.retry(base, flow["writes"] + fresh["writes"])
            self.assert_preserved_report(base, flow, "historical_reassessment_required")
            self.assert_preserved_report(base, fresh, "current_unreviewed")
            final = self.durable_state()
            for owner in (*connected.HISTORY_OWNERS, "case_evidence_versions",
                          "question_evidence_assessments", "question_evidence_reports",
                          "evidence_commands", "evidence_command_origins"):
                for row in history[owner]:
                    self.assertIn(row, final[owner], owner)
            self.assertEqual(len(final["images"]), 1)
            self.assertEqual(len(final["image_links"]), 2)
            for owner in ("questions", "returns", "tasks", "evidence_links"):
                self.assertEqual(len(final[owner]), 2, owner)
            self.assertEqual(len(final["question_evidence_reports"]), 2)

    def test_independent_grants_metadata_rights_and_binding_revocation_control_archive_access(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            flow, image, _ = self.populated_case(base)
            patient = flow["patient"]
            prefix = self.case_path(patient)
            path = self.image_path(patient, flow["source"]) + "/" + image["image_id"]
            actions = list(self.creds[0]["actions"])
            for missing in ("image_original_read", "patient_read"):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"] = [action for action in actions if action != missing]
                    self.write()
                    self.archive.read.reset_mock()
                    before_denial = self.durable_state()
                    self.assert_withheld(image_request(base, path), 404, before_denial)
                    self.archive.read.assert_not_called()
                    if missing == "image_original_read":
                        self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
                        self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
                        self.assert_preserved_report(base, flow, "current_unreviewed")
            for missing, operations in (
                ("source_read", [(prefix + "/sources", None)]),
                ("image_read", [(self.image_path(patient, flow["source"]), None)]),
                ("followthrough_read", [(prefix + "/followthrough", None)]),
                ("followthrough_create", [flow["writes"][2][:2]]),
                ("followthrough_update", [flow["writes"][3][:2]]),
                ("evidence_read", [(flow["citation"][0], None), flow["citation"][:2]]),
                ("evidence_link", [flow["citation"][:2]]),
                ("authored_evidence_read", [(flow["question_path"] + "/evidence", None),
                                           (flow["report_path"], None)]),
                ("authored_evidence_original_read", [
                    (flow["question_path"] + "/evidence/" + flow["evidence"]["evidence_id"] + "/original", None)]),
                ("evidence_report_export", [(flow["report_path"], None)]),
            ):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"] = [action for action in actions if action != missing]
                    self.write()
                    self.denied(base, operations)
                    self.read_archive(base, path)
                    if missing.startswith("authored_evidence") or missing == "evidence_report_export":
                        self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
                    if missing in {"image_read", "evidence_read", "evidence_link", "authored_evidence_original_read"}:
                        self.assert_preserved_report(base, flow, "current_unreviewed")
            self.creds[0]["actions"] = actions
            self.write()
            before = self.durable_state()
            database = Database(self.settings)
            try:
                with database.registry_connection() as connection:
                    append_rights_decision(
                        PostgresPatientRegistry(connection, lambda *args: False),
                        "FICT-RECORD-CONTINUITY", "1",
                        permissions={"metadata": {"store": "allowed", "display": "allowed"}},
                        revoked=True, superseded=False, recorded_by="FIXTURE-REVIEWER",
                        reason="Withdraw independently fictional citation display rights",
                    )
            finally:
                database.close()
            self.assert_preserved(before, self.durable_state(), except_for={"evidence_rights"})
            redacted = self.read_json(base, flow["citation"][0])
            self.assertEqual(redacted["links"],
                             [{**flow["links"][0], "status": "rights_restricted", "record": None}])
            for restricted in (flow["metadata"]["title"], flow["metadata"]["link"]):
                self.assertNotIn(restricted, json.dumps(redacted))
            self.denied(base, [(flow["citation"][0],
                               {**flow["citation"][1], "request_key": "ARCHIVE-REVOKED-CITATION"})])
            self.retry(base, flow["writes"])
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assert_preserved_report(base, flow, "current_unreviewed")
            self.read_archive(base, path)

            before_withdrawal = self.durable_state()
            withdrawal = self.command(
                base, flow["question_path"] + "/evidence/" + flow["evidence"]["evidence_id"] + "/withdraw", {
                    "synthetic": True, "request_key": "ARCHIVE-COMPARISON-WITHDRAWAL",
                    "reason": "Withdraw the independently fictional comparison family pending review.",
                })
            self.assert_preserved(before_withdrawal, self.durable_state(),
                                  except_for={"case_evidence_withdrawals", "evidence_commands", "events"})
            flow["writes"].append(withdrawal)
            withheld = self.read_json(base, flow["report_path"])
            self.assertEqual((withheld["state"], withheld["body"], withheld["snapshot"]),
                             ("content_withheld", None, None))
            for field in ("report_id", "question_id", "prepared_at", "body_sha256", "snapshot_sha256"):
                self.assertEqual(withheld[field], flow["report"][field], field)
            self.denied(base, [(flow["question_path"] + "/evidence/"
                               + flow["evidence"]["evidence_id"] + "/original", None)])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], redacted["links"])
            self.retry(base, flow["writes"])
            self.read_archive(base, path)

            status, revoked, _ = request(
                base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke", token=TOKEN_A,
                body={"synthetic": True, "reason": "Withdraw the fictional archive/evidence binding"})
            self.assertEqual((status, revoked["duplicate"]), (200, False))
            self.archive.read.reset_mock()
            before = self.durable_state()
            self.assert_withheld(image_request(base, path), 404, before)
            self.denied(base, [(prefix + "/questions", None), (prefix + "/review-queue", None),
                               (prefix + "/followthrough", None), (flow["citation"][0], None),
                               (flow["question_path"] + "/evidence", None), (flow["report_path"], None)]
                        + [(url, body) for url, body, _ in flow["writes"]])
            self.assertEqual(self.durable_state(), before)
            self.archive.read.assert_not_called()

    def test_archive_and_receipt_failures_preserve_connected_business_history_without_fallback(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            flow, image, _ = self.populated_case(base)
            path = self.image_path(flow["patient"], flow["source"]) + "/" + image["image_id"]
            before = self.durable_state()
            self.assertEqual(bytes(self.rows(
                "SELECT raw FROM clinical_source.dicom_objects WHERE image_id=:image",
                {"image": image["image_id"]})[0][0]), self.raw)
            for name, value, error in (
                ("archive_error", None, RuntimeError("PRIVATE-ARCHIVE-DETAIL")),
                ("missing_original", None, FileNotFoundError("PRIVATE-ARCHIVE-DETAIL")),
                ("corrupt_bytes", self.raw + b"changed", None),
                ("wrong_subject", image_bytes(patient_id="SUBJECT-OTHER"), None),
                ("non_bytes", bytearray(self.raw), None),
            ):
                with self.subTest(outcome=name):
                    self.archive.read.reset_mock()
                    self.archive.read.side_effect = error
                    self.archive.read.return_value = value
                    self.assert_withheld(image_request(base, path), 503, before)
                    self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            self.archive.read.side_effect = None
            self.archive.read.return_value = self.raw
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.reject_archive_connected_read() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                        IF NEW.event_type='image.original_read_authorized' THEN
                            RAISE EXCEPTION 'INDEPENDENT-FICTIONAL-ARCHIVE-RECEIPT-FAILURE';
                        END IF;
                        RETURN NEW;
                    END; $$;
                    CREATE TRIGGER reject_archive_connected_read
                    BEFORE INSERT ON identity.identity_domain_events
                    FOR EACH ROW EXECUTE FUNCTION identity.reject_archive_connected_read();
                """)
            try:
                self.archive.read.reset_mock()
                self.assert_withheld(image_request(base, path), 503, before)
                self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            finally:
                with self.engine.begin() as connection:
                    connection.exec_driver_sql("DROP TRIGGER reject_archive_connected_read ON identity.identity_domain_events")
                    connection.exec_driver_sql("DROP FUNCTION identity.reject_archive_connected_read()")
            self.read_archive(base, path)
            self.assert_preserved(before, self.durable_state(), except_for={"events"})
            self.assert_preserved_report(base, flow, "current_unreviewed")
            self.retry(base, flow["writes"])
