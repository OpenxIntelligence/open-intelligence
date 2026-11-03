"""Real PG16/HTTP archive acceptance across canonical question/task/citation owners.

Reuse #313's independently authored fixtures and helpers, without inheriting its
test methods. The controlled archive is not live PACS or transport qualification.
"""
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
    durable_state = connected.ImageEvidenceIntegrationHTTPTests.durable_state
    assert_preserved = connected.ImageEvidenceIntegrationHTTPTests.assert_preserved
    command = connected.ImageEvidenceIntegrationHTTPTests.command
    retry = connected.ImageEvidenceIntegrationHTTPTests.retry
    denied = connected.ImageEvidenceIntegrationHTTPTests.denied
    context_intent = staticmethod(connected.ImageEvidenceIntegrationHTTPTests.context_intent)
    packet_and_brief = connected.ImageEvidenceIntegrationHTTPTests.packet_and_brief
    populate_question = connected.ImageEvidenceIntegrationHTTPTests.populate_question
    populated_case = connected.ImageEvidenceIntegrationHTTPTests.populated_case
    assert_withheld = archive_reviews.ArchiveQuestionReviewIntegrationHTTPTests.assert_withheld

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_packet_read", "source_brief_export", "review_queue_read", "review_return",
            "image_import", "image_read", "image_original_read",
            "followthrough_create", "followthrough_read", "followthrough_update",
            "evidence_read", "evidence_link",
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
            self.assertEqual(self.read_json(base, prefix + "/world-model")["snapshot_fingerprint"],
                             flow["world"]["snapshot_fingerprint"])
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            self.assertEqual(self.queue(base, patient)["receipts"], queue["receipts"])

            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amendment["version"]), (201, 2))
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
            self.read_archive(base, current_path + "/" + image["image_id"])
            self.retry(base, flow["writes"] + fresh["writes"])
            final = self.durable_state()
            for owner in connected.HISTORY_OWNERS:
                for row in history[owner]:
                    self.assertIn(row, final[owner], owner)
            self.assertEqual(len(final["images"]), 1)
            self.assertEqual(len(final["image_links"]), 2)
            for owner in ("questions", "returns", "tasks", "evidence_links"):
                self.assertEqual(len(final[owner]), 2, owner)

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
            for missing, operations in (
                ("source_read", [(prefix + "/sources", None)]),
                ("followthrough_read", [(prefix + "/followthrough", None)]),
                ("followthrough_create", [flow["writes"][2][:2]]),
                ("followthrough_update", [flow["writes"][3][:2]]),
                ("evidence_read", [(flow["citation"][0], None), flow["citation"][:2]]),
                ("evidence_link", [flow["citation"][:2]]),
            ):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"] = [action for action in actions if action != missing]
                    self.write()
                    self.denied(base, operations)
                    self.read_archive(base, path)
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
            self.read_archive(base, path)

            status, revoked, _ = request(
                base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke", token=TOKEN_A,
                body={"synthetic": True, "reason": "Withdraw the fictional archive/evidence binding"})
            self.assertEqual((status, revoked["duplicate"]), (200, False))
            self.archive.read.reset_mock()
            before = self.durable_state()
            self.assert_withheld(image_request(base, path), 404, before)
            self.denied(base, [(prefix + "/questions", None), (prefix + "/review-queue", None),
                               (prefix + "/followthrough", None), (flow["citation"][0], None)]
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
