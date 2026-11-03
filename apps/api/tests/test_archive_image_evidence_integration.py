"""Real PG16/HTTP archive reads with canonical tasks and citation history.

The archive is a controlled boundary double returning independently authored
DICOM bytes. These cases do not qualify a live PACS or external-archive recovery.
Only this module's new methods run; the inherited owner suite runs separately.
"""
import json
import unittest
from unittest.mock import Mock

from http_support import running_server
from oi_api.app import create_app
from oi_api.database import Database
from oi_api.evidence_catalog import append_rights_decision
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_image_custody import AMENDED, image_bytes, image_request
from test_image_evidence_integration import ImageEvidenceIntegrationHTTPTests, HISTORY_OWNERS
from test_patients import TOKEN_A, request


class ArchiveImageEvidenceIntegrationHTTPTests(ImageEvidenceIntegrationHTTPTests):
    def setUp(self):
        super().setUp()
        self.raw = image_bytes()
        self.archive = Mock()
        self.archive.read.return_value = self.raw

    def assert_archive_read(self, base, path):
        before = self.durable_state()
        calls = self.archive.read.call_count
        status, raw, headers = image_request(base, path)
        self.assertEqual((status, raw), (200, self.raw))
        self.assertEqual(self.archive.read.call_count, calls + 1)
        self.archive.read.assert_called_with("2.25.101", "2.25.102", "2.25.103")
        after = self.durable_state()
        self.assert_preserved(before, after, except_for={"events"})
        self.assertEqual(after["events"][:-1], before["events"])
        self.assertEqual(after["events"][-1][1], "image.original_read_authorized")
        self.assertEqual(after["events"][-1][2]["receipt_id"], headers["X-OI-Access-Receipt"])

    def assert_archive_withheld(self, base, path, status):
        before = self.durable_state()
        code, body, headers = image_request(base, path)
        self.assertEqual(code, status, body)
        self.assertEqual(set(body), {"detail"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", headers)
        for private in (TOKEN_A, "PRIVATE-ARCHIVE-DETAIL", "DICM", "2.25.103"):
            self.assertNotIn(private, json.dumps(body))
        self.assertEqual(self.durable_state(), before)

    def test_archive_amendment_relink_and_restart_preserve_tasks_citations_and_exact_retries(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            flow, image, raw = self.populated_case(base)
            self.assertEqual(raw, self.raw)
            self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            patient = flow["patient"]
            prefix = self.case_path(patient)
            old_path = self.image_path(patient, flow["source"]) + "/" + image["image_id"]
            self.assert_archive_read(base, old_path)
            before_amendment = self.durable_state()
            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amendment["version"]), (201, 2))
            historical = self.durable_state()
            for owner in HISTORY_OWNERS:
                self.assertEqual(historical[owner], before_amendment[owner], owner)
            current_path = self.image_path(patient, amendment["source_id"])
            calls = self.archive.read.call_count
            self.assert_archive_withheld(base, old_path, 404)
            self.assert_archive_withheld(base, current_path + "/" + image["image_id"], 404)
            self.assertEqual(self.archive.read.call_count, calls)
            before_relink = self.durable_state()
            status, linked, _ = image_request(base, current_path, raw=raw)
            self.assertEqual((status, linked["result"], linked["image_id"]),
                             (201, "linked", image["image_id"]))
            self.assertEqual(self.archive.read.call_count, calls)
            self.assert_preserved(before_relink, self.durable_state(), except_for={"image_links", "events"})
            self.assert_archive_read(base, current_path + "/" + image["image_id"])
            task = self.read_json(base, prefix + "/followthrough")["tasks"][0]
            self.assertEqual(task, {**flow["task"], "source_context_state": "source_reassessment_required",
                                    "needs_recheck": True})
            links = self.read_json(base, flow["citation"][0])
            self.assertEqual(links["source_context_state"], "source_reassessment_required")
            self.assertEqual(links["links"], flow["links"])
            fresh = self.populate_question(base, patient, amendment["source_id"], version=2)
            for key in ("question",):
                self.assertNotEqual(fresh[key], flow[key])
            self.assertNotEqual(fresh["task"]["task_id"], flow["task"]["task_id"])
            self.assertNotEqual(fresh["citation"][2]["link_id"], flow["citation"][2]["link_id"])
            after = self.durable_state()
            for owner in HISTORY_OWNERS:
                for row in historical[owner]:
                    self.assertIn(row, after[owner], owner)
            self.assertEqual(len(after["images"]), 1)
            self.assertEqual(len(after["image_links"]), 2)
            tasks = self.read_json(base, prefix + "/followthrough")["tasks"]
            returns = self.queue(base, patient)["receipts"]
            self.retry(base, flow["writes"] + fresh["writes"])

        with running_server(create_app(self.settings, image_archive=self.archive)) as restarted:
            self.assert_archive_read(restarted, current_path + "/" + image["image_id"])
            self.assertEqual(self.read_json(restarted, prefix + "/followthrough")["tasks"], tasks)
            self.assertEqual(self.queue(restarted, patient)["receipts"], returns)
            for item in (flow, fresh):
                self.assertEqual(self.read_json(restarted, item["citation"][0])["links"], item["links"])
            self.retry(restarted, flow["writes"] + fresh["writes"])

    def test_failed_archive_reads_preserve_populated_tasks_citations_and_local_custody(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            flow, image, raw = self.populated_case(base)
            path = self.image_path(flow["patient"], flow["source"]) + "/" + image["image_id"]
            self.assertEqual(bytes(self.rows(
                "SELECT raw FROM clinical_source.dicom_objects WHERE image_id=:image",
                {"image": image["image_id"]})[0][0]), raw)
            outcomes = (
                ("missing", None, FileNotFoundError("PRIVATE-ARCHIVE-DETAIL")),
                ("altered", raw + b"changed", None),
                ("wrong_subject", image_bytes(patient_id="SUBJECT-OTHER"), None),
                ("non_bytes", bytearray(raw), None),
            )
            for name, content, error in outcomes:
                with self.subTest(outcome=name):
                    self.archive.read.reset_mock()
                    self.archive.read.side_effect = error
                    self.archive.read.return_value = content
                    self.assert_archive_withheld(base, path, 503)
                    self.archive.read.assert_called_once_with("2.25.101", "2.25.102", "2.25.103")
            self.archive.read.side_effect = None
            self.archive.read.return_value = raw
            self.assert_archive_read(base, path)
            self.assertEqual(self.read_json(base, self.case_path(flow["patient"]) + "/followthrough")["tasks"],
                             [flow["task"]])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            self.retry(base, flow["writes"])

    def test_archive_authority_remains_independent_of_task_grants_and_revoked_metadata(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            flow, image, _ = self.populated_case(base)
            patient = flow["patient"]
            prefix = self.case_path(patient)
            path = self.image_path(patient, flow["source"]) + "/" + image["image_id"]
            actions = list(self.creds[0]["actions"])
            for missing, operation in (("followthrough_read", prefix + "/followthrough"),
                                       ("evidence_read", flow["citation"][0])):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"] = [action for action in actions if action != missing]
                    self.write()
                    self.denied(base, [(operation, None)])
                    self.assert_archive_read(base, path)
            self.creds[0]["actions"] = [action for action in actions if action != "source_read"]
            self.write()
            self.assert_archive_read(base, path)
            self.creds[0]["actions"] = list(actions)
            self.write()

            database = Database(self.settings)
            try:
                with database.registry_connection() as connection:
                    append_rights_decision(
                        PostgresPatientRegistry(connection, lambda *args: False),
                        "FICT-RECORD-CONTINUITY", "1",
                        permissions={"metadata": {"store": "allowed", "display": "allowed"}},
                        revoked=True, superseded=False, recorded_by="FIXTURE-REVIEWER",
                        reason="Withdraw independently fictional metadata while preserving image custody",
                    )
            finally:
                database.close()
            redacted = self.read_json(base, flow["citation"][0])
            self.assertEqual(redacted["links"], [{**flow["links"][0], "status": "rights_restricted", "record": None}])
            for restricted in (flow["metadata"]["title"], flow["metadata"]["link"]):
                self.assertNotIn(restricted, json.dumps(redacted))
            self.assert_archive_read(base, path)
            self.retry(base, flow["writes"])
            self.creds[0]["actions"].remove("image_original_read")
            self.write()
            calls = self.archive.read.call_count
            self.assert_archive_withheld(base, path, 404)
            self.assertEqual(self.archive.read.call_count, calls)
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], redacted["links"])
            self.creds[0]["actions"] = list(actions)
            self.write()
            status, _, _ = request(base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                                    token=TOKEN_A, body={"synthetic": True,
                                                        "reason": "Withdraw the fictional archive-linked case"})
            self.assertEqual(status, 200)
            self.assert_archive_withheld(base, path, 404)
            self.assertEqual(self.archive.read.call_count, calls)
            self.denied(base, [(prefix + "/followthrough", None), (flow["citation"][0], None),
                               *[(url, body) for url, body, _ in flow["writes"]]])


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ArchiveImageEvidenceIntegrationHTTPTests(name)
                              for name in ArchiveImageEvidenceIntegrationHTTPTests.__dict__
                              if name.startswith("test_"))
