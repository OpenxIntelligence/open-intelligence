"""Existing real PG/HTTP custody with actual private Unix-socket transport.

Independently authored fictional records only. This is a local responder, not a
live PACS or a deployment isolation test. Run with the inherited H1 database gate.
"""
import os
import unittest

from oi_api.app import create_app
from oi_api.archive_socket import UnixSocketImageArchive
from archive_socket_fixture import archive_server, http_response, multipart_body
from http_support import running_server
from test_image_custody import ImageCustodyHTTPTests, image_bytes, image_request, AMENDED
from test_patients import TOKEN_A, TOKEN_B


class ArchiveSocketCustodyTests(ImageCustodyHTTPTests):
    @staticmethod
    def archive(path, **changes):
        values = {"expected_peer_uid": os.getuid(), "timeout_seconds": 3.0}
        values.update(changes)
        return UnixSocketImageArchive(path, **values)

    def test_exact_socket_original_and_denial_before_archive_request(self):
        raw = image_bytes()
        response = http_response(multipart_body(raw), content_type=(
            b'multipart/related; type="application/dicom"; boundary="oi-boundary"'))
        with archive_server(response) as (socket_path, requests):
            with running_server(create_app(self.settings, image_archive=self.archive(socket_path))) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                self.assertEqual(image_request(base, path + "/" + image, token=TOKEN_B)[0], 404)
                self.assertEqual(requests, [])
                code, body, headers = image_request(base, path + "/" + image)
                self.assertEqual((code, body), (200, raw))
                self.assertTrue(headers["X-OI-Access-Receipt"])
                self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(len(requests), 1)
        self.assertNotIn(TOKEN_A.encode(), requests[0])
        self.assertNotIn(TOKEN_B.encode(), requests[0])
        self.assertIn(b"/studies/2.25.101/series/2.25.102/instances/2.25.103 ", requests[0])
        self.assertEqual(len(self.events("AND event_type='image.original_read_authorized'")), 1)

    def test_changed_replica_is_withheld_without_local_fallback_or_receipt(self):
        raw = image_bytes()
        with archive_server(http_response(raw + b"changed")) as (socket_path, requests):
            with running_server(create_app(self.settings, image_archive=self.archive(socket_path))) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                before = self.events()
                code, body, headers = image_request(base, path + "/" + image)
                self.assertEqual((code, body), (503, {"detail": "Patient registry unavailable"}))
                self.assertIsNone(headers.get("X-OI-Access-Receipt"))
                self.assertEqual(self.events(), before)
        self.assertEqual(len(requests), 1)

    def test_source_amendment_can_commit_while_socket_read_is_in_flight(self):
        raw = image_bytes()
        amendment_status = []
        def during_read(conn, _):
            amendment_status.append(self.ingest(base, patient, AMENDED)[0])
            conn.sendall(http_response(raw))
        with archive_server(handler=during_read) as (socket_path, requests):
            with running_server(create_app(self.settings, image_archive=self.archive(socket_path))) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                self.assertEqual(image_request(base, path + "/" + image)[0], 404)
                self.assertEqual(amendment_status, [201])
                self.assertEqual(image_request(base, path + "/" + image)[0], 404)
        self.assertEqual(len(requests), 1)
        self.assertEqual(self.events("AND event_type='image.original_read_authorized'"), [])

    def test_grant_revocation_during_socket_read_withholds_returned_bytes(self):
        raw = image_bytes()
        def revoke(conn, _):
            self.creds[0]["actions"].remove("image_original_read")
            self.write()
            conn.sendall(http_response(raw))
        with archive_server(handler=revoke) as (socket_path, requests):
            with running_server(create_app(self.settings, image_archive=self.archive(socket_path))) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                self.assertEqual(image_request(base, path + "/" + image)[0], 404)
        self.assertEqual(len(requests), 1)
        self.assertEqual(self.events("AND event_type='image.original_read_authorized'"), [])

    def test_wrong_socket_peer_is_sanitized_without_request_or_success_receipt(self):
        raw = image_bytes()
        with archive_server(http_response(raw)) as (socket_path, requests):
            adapter = self.archive(socket_path, expected_peer_uid=os.getuid() + 1)
            with running_server(create_app(self.settings, image_archive=adapter)) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                before = self.events()
                code, body, headers = image_request(base, path + "/" + image)
                self.assertEqual((code, body), (503, {"detail": "Patient registry unavailable"}))
                self.assertIsNone(headers.get("X-OI-Access-Receipt"))
                self.assertEqual(self.events(), before)
        self.assertEqual(requests, [])


def load_tests(loader, tests, pattern):
    # Do not count the inherited owner tests twice.
    return unittest.TestSuite(ArchiveSocketCustodyTests(name)
                              for name in ArchiveSocketCustodyTests.__dict__
                              if name.startswith("test_"))
