"""Real PG16/HTTP + Unix sockets on the joined image/question/report owner.

Reuse the independently authored combined-history fixture, not a second ledger.
Only the three new methods are collected; inherited test methods are not rerun.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import unittest

from archive_socket_fixture import archive_server, http_response
from http_support import running_server
from oi_api.app import create_app
from oi_api.archive_socket import ArchiveReadCapacity, UnixSocketImageArchive
import test_archive_image_evidence_integration as connected
from test_image_custody import AMENDED, image_request
from test_patients import TOKEN_B


class SocketArchiveReportContinuityTests(connected.ArchiveImageEvidenceIntegrationHTTPTests):
    def socket_reader(self, path, *, uid=None):
        return UnixSocketImageArchive(
            path, os.getuid() if uid is None else uid, timeout_seconds=7.0,
            capacity=ArchiveReadCapacity(max_in_flight=1))

    def read_socket_original(self, base, path):
        before = self.durable_state()
        code, body, headers = image_request(base, path)
        self.assertEqual((code, body), (200, self.raw))
        self.assertEqual(headers["Cache-Control"], "no-store")
        after = self.durable_state()
        self.assert_preserved(before, after, except_for={"events"})
        self.assertEqual(after["events"][:-1], before["events"])
        self.assertEqual(after["events"][-1][1], "image.original_read_authorized")
        self.assertEqual(after["events"][-1][2]["receipt_id"], headers["X-OI-Access-Receipt"])
        return headers["X-OI-Access-Receipt"]

    def test_socket_originals_preserve_current_and_historical_reports_across_relink(self):
        with archive_server(http_response(self.raw)) as (path, calls):
            with running_server(create_app(self.settings, image_archive=self.socket_reader(path))) as base:
                flow, image, _ = self.populated_case(base)
                original_path = self.image_path(flow["patient"], flow["source"]) + "/" + image["image_id"]
                self.assertEqual(len(calls), 1)
                old_state = self.durable_state()
                self.read_socket_original(base, original_path)
                self.assert_preserved_report(base, flow, "current_unreviewed")
                status, amendment, _ = self.ingest(base, flow["patient"], AMENDED)
                self.assertEqual((status, amendment["version"]), (201, 2))
                self.assert_preserved_report(base, flow, "historical_reassessment_required")
                current = self.image_path(flow["patient"], amendment["source_id"])
                before_denial = self.durable_state()
                count = len(calls)
                self.assert_withheld(image_request(base, original_path), 404, before_denial)
                self.assert_withheld(image_request(base, current + "/" + image["image_id"]), 404, before_denial)
                self.assertEqual(len(calls), count)
                status, linked, _ = image_request(base, current, raw=self.raw)
                self.assertEqual((status, linked["result"], linked["image_id"]),
                                 (201, "linked", image["image_id"]))
                self.assertEqual(len(calls), count, "Import/relink is not an archive read")
                fresh = self.populate_question(base, flow["patient"], amendment["source_id"], version=2)
                self.read_socket_original(base, current + "/" + image["image_id"])
                self.assert_preserved_report(base, flow, "historical_reassessment_required")
                self.assert_preserved_report(base, fresh, "current_unreviewed")
                self.assertNotEqual(fresh["report"]["report_id"], flow["report"]["report_id"])
                self.assertNotEqual(fresh["question"], flow["question"])
                self.retry(base, flow["writes"] + fresh["writes"])
                final = self.durable_state()
                for owner in ("questions", "returns", "tasks", "evidence_links",
                              "question_evidence_assessments", "question_evidence_reports",
                              "evidence_commands", "evidence_command_origins"):
                    for row in old_state[owner]:
                        self.assertIn(row, final[owner], owner)
                self.assertEqual((len(final["images"]), len(final["image_links"])), (1, 2))
                self.assertEqual(len(calls), count + 1)
                for wire in calls:
                    self.assertNotIn(b"Authorization", wire)
                    self.assertTrue(wire.startswith(b"GET /studies/2.25.101/series/2.25.102/instances/2.25.103 "))

    def test_content_withdrawal_preserves_image_access_and_transport_failure_preserves_history(self):
        selected = [self.raw]

        def reply(conn, request):
            conn.sendall(http_response(selected[0]))

        with archive_server(handler=reply) as (path, calls):
            with running_server(create_app(self.settings, image_archive=self.socket_reader(path))) as base:
                flow, image, _ = self.populated_case(base)
                original_path = self.image_path(flow["patient"], flow["source"]) + "/" + image["image_id"]
                before = self.durable_state()
                withdrawal = self.command(
                    base, flow["question_path"] + "/evidence/" + flow["evidence"]["evidence_id"] + "/withdraw", {
                        "synthetic": True, "request_key": "SOCKET-REPORT-WITHDRAWAL",
                        "reason": "Withdraw independently authored comparison content, not original-image authority.",
                    })
                self.assert_preserved(before, self.durable_state(),
                                      except_for={"case_evidence_withdrawals", "evidence_commands", "events"})
                withheld = self.read_json(base, flow["report_path"])
                self.assertEqual((withheld["state"], withheld["body"], withheld["snapshot"]),
                                 ("content_withheld", None, None))
                for key in ("report_id", "prepared_at", "body_sha256", "snapshot_sha256"):
                    self.assertEqual(withheld[key], flow["report"][key])
                self.read_socket_original(base, original_path)
                self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
                self.assertEqual(self.read_json(base, self.case_path(flow["patient"]) + "/followthrough")["tasks"],
                                 [flow["task"]])
                for corrupted in (self.raw[:-1] + bytes([self.raw[-1] ^ 1]), b"not-a-dicom"):
                    selected[0] = corrupted
                    unchanged = self.durable_state()
                    count = len(calls)
                    self.assert_withheld(image_request(base, original_path), 503, unchanged)
                    self.assertEqual(len(calls), count + 1)
                selected[0] = self.raw
                self.read_socket_original(base, original_path)
                self.retry(base, flow["writes"] + [withdrawal])
                expected = self.durable_state()
            # A wrong service identity must send no canonical identifiers, even
            # though the database has valid local bytes and immutable reports.
            count = len(calls)
            with running_server(create_app(self.settings, image_archive=self.socket_reader(path, uid=os.getuid() + 1))) as base:
                self.assert_withheld(image_request(base, original_path), 503, expected)
                self.assertEqual(len(calls), count)

    def test_socket_overload_leaves_reports_available_and_revocation_still_withholds_image(self):
        block, entered, release = threading.Event(), threading.Event(), threading.Event()

        def reply(conn, request):
            if block.is_set():
                entered.set()
                if not release.wait(10):
                    raise AssertionError("Test did not release the held socket")
            conn.sendall(http_response(self.raw))

        with archive_server(handler=reply) as (path, calls):
            with running_server(create_app(self.settings, image_archive=self.socket_reader(path))) as base:
                flow, image, _ = self.populated_case(base)
                original_path = self.image_path(flow["patient"], flow["source"]) + "/" + image["image_id"]
                business = self.durable_state()
                block.set()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    active = pool.submit(image_request, base, original_path)
                    try:
                        self.assertTrue(entered.wait(2))
                        self.assert_withheld(image_request(base, original_path), 503, business)
                        self.assert_withheld(image_request(base, original_path, token=TOKEN_B), 404, business)
                        self.assertEqual(len(calls), 2)
                        # The archive read holds no database owner locks: the
                        # separately authorized frozen report remains readable.
                        self.assert_preserved_report(base, flow, "current_unreviewed")
                        self.creds[0]["actions"].remove("image_original_read")
                        self.write()
                        before_withhold = self.durable_state()
                    finally:
                        release.set()
                    self.assert_withheld(active.result(timeout=8), 404, before_withhold)
                self.assertEqual(len(calls), 2)
                self.creds[0]["actions"].append("image_original_read")
                self.write()
                self.read_socket_original(base, original_path)
                self.assertEqual(len(calls), 3)
                self.assert_preserved_report(base, flow, "current_unreviewed")
                self.retry(base, flow["writes"])
                self.assert_preserved(business, self.durable_state(), except_for={"events"})


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(SocketArchiveReportContinuityTests(name)
                              for name in SocketArchiveReportContinuityTests.__dict__
                              if name.startswith("test_"))
