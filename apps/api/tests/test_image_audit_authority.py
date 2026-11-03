"""Actual PG16/HTTP image authority after the real journal append.

Only fictional credentials change, after PostgresPatientRegistry.append_event
has performed its real SQL. The original encoders, transactions, and socket
transport remain in use. Collect only these new methods, not inherited tests.
"""
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from archive_socket_fixture import archive_server, http_response
from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
import test_image_disclosure_authority as disclosure
import test_socket_archive_report_continuity as socket_continuity
from test_image_custody import AMENDED, REPORT, image_bytes


class AuditTailObservation:
    @contextmanager
    def after_real_image_event(self, event, effect):
        """Run the actual append before changing the current credential."""
        append = PostgresPatientRegistry.append_event
        observed = []

        def append_then_change(registry, patient_id, kind, **details):
            result = append(registry, patient_id, kind, **details)
            if kind == event:
                observed.append((kind, dict(details)))
                effect()
            return result

        with patch.object(PostgresPatientRegistry, "append_event", append_then_change):
            yield observed

    def change_authority(self, change):
        if change == "provider_missing":
            self.access.unlink()
            return
        if change == "credential_removed":
            self.creds.pop(0)
        else:
            self.creds[0].update(change)
        self.write()


class ImageAuditAuthorityTests(AuditTailObservation, disclosure.ImageDisclosureAuthorityTests):
    def withheld_after_append(self, base, path, event, change, *, raw=None, status=404):
        initial = copy.deepcopy(self.creds)
        before = self.custody_state()
        reads_before = self.read_events()
        try:
            with self.after_real_image_event(
                    event, lambda: self.change_authority(change)) as observed:
                response = disclosure.read_image_route(base, path, raw=raw)
        finally:
            self.creds = initial
            self.write()
        self.assertEqual([kind for kind, _ in observed], [event])
        unchanged = self.custody_state() == before
        self.assertEqual((response[0], unchanged), (status, True))
        self.assert_withheld(response, status, reads_before)
        self.assertEqual(response[1], {"detail": {
            404: "Image unavailable",
            401: "Authentication required",
            503: "Access service unavailable",
        }[status]})
        return before

    def test_new_import_after_audit_grant_withdrawal_rolls_back_then_retries(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, source, _ = self.ingest(base, patient, REPORT)
            self.assertEqual(status, 201)
            path = self.url(patient) + "/" + source["source_id"] + "/images"
            raw = image_bytes()
            before = self.withheld_after_append(
                base, path, "image.original_imported", {
                    "actions": [a for a in self.creds[0]["actions"] if a != "image_import"],
                }, raw=raw)
            status, image, _ = disclosure.read_image_route(base, path, raw=raw)
            self.assertEqual((status, image["result"]), (201, "imported"))
            after = self.custody_state()
            self.assertEqual(len(after["objects"]), len(before["objects"]) + 1)
            self.assertEqual(len(after["links"]), len(before["links"]) + 1)
            self.assertEqual(after["events"][:-1], before["events"])
            self.assertEqual(after["events"][-1][1], "image.original_imported")
            self.assertEqual(disclosure.read_image_route(base, path, raw=raw)[:2],
                             (200, {**image, "result": "duplicate"}))
            self.assertEqual(self.custody_state(), after)

    def test_amendment_relink_after_audit_patient_withdrawal_rolls_back_then_retries(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, image_id, raw = self.prepare(base)
            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amendment["version"]), (201, 2))
            path = self.url(patient) + "/" + amendment["source_id"] + "/images"
            before = self.withheld_after_append(
                base, path, "image.source_linked", {"patient_ids": []}, raw=raw)
            status, image, _ = disclosure.read_image_route(base, path, raw=raw)
            self.assertEqual((status, image["result"], image["image_id"]),
                             (201, "linked", image_id))
            after = self.custody_state()
            self.assertEqual(after["objects"], before["objects"])
            self.assertEqual(len(after["links"]), len(before["links"]) + 1)
            self.assertEqual(after["events"][:-1], before["events"])
            self.assertEqual(after["events"][-1][1], "image.source_linked")
            self.assertEqual(disclosure.read_image_route(base, path, raw=raw)[:2],
                             (200, {**image, "result": "duplicate"}))
            self.assertEqual(self.custody_state(), after)

    def test_index_after_audit_context_change_withholds_metadata_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            _, path, image_id, _ = self.prepare(base)
            before = self.withheld_after_append(
                base, path, "image.read_authorized", {"organization": "ORG-CHANGED"})
            status, index, headers = disclosure.read_image_route(base, path)
            self.assertEqual(status, 200)
            self.assertEqual([image["image_id"] for image in index["images"]], [image_id])
            self.assertEqual(headers["Cache-Control"], "no-store")
            after = self.custody_state()
            self.assertEqual(after["objects"], before["objects"])
            self.assertEqual(after["links"], before["links"])
            self.assertEqual(after["events"][:-1], before["events"])
            self.assertEqual(after["events"][-1][1], "image.read_authorized")
            self.assertEqual(after["events"][-1][2]["receipt_id"], index["access_receipt_id"])

    def test_binary_after_audit_authority_changes_withholds_bytes_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            _, path, image_id, raw = self.prepare(base)
            path += "/" + image_id
            changes = (
                ("patient_read", {"actions": [a for a in self.creds[0]["actions"]
                                               if a != "patient_read"]}, 404),
                ("actor", {"actor": "ACTOR-CHANGED"}, 404),
                ("purpose", {"purpose": "research"}, 404),
                ("expired", {"expires_at": (datetime.now(timezone.utc)
                                            - timedelta(minutes=1)).isoformat()}, 401),
                ("removed", "credential_removed", 401),
                ("provider", "provider_missing", 503),
            )
            for name, change, status in changes:
                with self.subTest(authority=name):
                    before = self.withheld_after_append(
                        base, path, "image.original_read_authorized", change, status=status)
                    code, body, headers = disclosure.read_image_route(base, path)
                    self.assertEqual((code, body), (200, raw))
                    self.assertEqual(headers["Cache-Control"], "no-store")
                    after = self.custody_state()
                    self.assertEqual(after["objects"], before["objects"])
                    self.assertEqual(after["links"], before["links"])
                    self.assertEqual(after["events"][:-1], before["events"])
                    self.assertEqual(after["events"][-1][1], "image.original_read_authorized")
                    self.assertEqual(after["events"][-1][2]["receipt_id"],
                                     headers["X-OI-Access-Receipt"])


class SocketImageAuditAuthorityTests(
        AuditTailObservation, socket_continuity.SocketArchiveReportContinuityTests):
    def test_socket_post_audit_withdrawal_preserves_joined_history_and_retry(self):
        with archive_server(http_response(self.raw)) as (socket_path, calls):
            app = create_app(self.settings, image_archive=self.socket_reader(socket_path))
            with running_server(app) as base:
                flow, image, _ = self.populated_case(base)
                path = self.image_path(flow["patient"], flow["source"]) + "/" + image["image_id"]
                initial = copy.deepcopy(self.creds)
                before = self.durable_state()
                calls_before = len(calls)
                try:
                    with self.after_real_image_event(
                            "image.original_read_authorized",
                            lambda: self.change_authority({
                                "actions": [a for a in initial[0]["actions"]
                                            if a != "image_original_read"],
                            })) as observed:
                        result = disclosure.read_image_route(base, path)
                finally:
                    self.creds = initial
                    self.write()
                self.assertEqual([kind for kind, _ in observed], ["image.original_read_authorized"])
                unchanged = self.durable_state() == before
                self.assertEqual((result[0], unchanged), (404, True))
                self.assertEqual(result[1], {"detail": "Image unavailable"})
                self.assert_withheld(result, 404, before)
                self.assertEqual(len(calls), calls_before + 1)
                self.read_socket_original(base, path)
                self.assertEqual(len(calls), calls_before + 2)
                self.assert_preserved_report(base, flow, "current_unreviewed")
                self.retry(base, flow["writes"])
                self.assert_preserved(before, self.durable_state(), except_for={"events"})
                for wire in calls:
                    self.assertNotIn(b"Authorization", wire)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(
        owner(name)
        for owner in (ImageAuditAuthorityTests, SocketImageAuditAuthorityTests)
        for name in owner.__dict__
        if name.startswith("test_")
    )
