"""Capacity admission composed with existing actual PostgreSQL/HTTP custody.

The archive is a real local Unix socket, not a live PACS or a network-isolation
proof. Only independently authored fictional reports and DICOM bytes are used.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import unittest

from oi_api.app import create_app
from oi_api import archive_socket
from archive_socket_fixture import archive_server, http_response
from http_support import running_server
from test_image_custody import ImageCustodyHTTPTests, image_bytes, image_request
from test_patients import TOKEN_B


class ArchiveCapacityCustodyTests(ImageCustodyHTTPTests):
    def archive(self, path, *, timeout_seconds=3.0):
        cls = getattr(archive_socket, "ArchiveReadCapacity", None)
        self.assertIsNotNone(cls, "Shared archive read capacity is not implemented")
        return archive_socket.UnixSocketImageArchive(
            path, os.getuid(), timeout_seconds, capacity=cls(max_in_flight=1))

    def assert_capacity_denied(self, base, path):
        code, body, headers = image_request(base, path)
        self.assertEqual((code, body), (503, {"detail": "Patient registry unavailable"}))
        self.assertIsNone(headers.get("X-OI-Access-Receipt"))

    def test_saturated_read_has_no_receipt_or_fallback_then_recovers(self):
        raw = image_bytes()
        entered, release = threading.Event(), threading.Event()

        def hold(conn, _):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test did not release admitted archive read")
            conn.sendall(http_response(raw))

        with archive_server(handler=hold) as (socket_path, requests):
            with running_server(create_app(self.settings, image_archive=self.archive(socket_path))) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                original_path = path + "/" + image
                before = self.events()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    active = pool.submit(image_request, base, original_path)
                    try:
                        self.assertTrue(entered.wait(2))
                        # An intact original already exists locally: overload must
                        # not silently substitute it or claim successful disclosure.
                        self.assert_capacity_denied(base, original_path)
                        self.assertEqual(self.events(), before)
                        self.assertEqual(image_request(base, original_path, token=TOKEN_B)[0], 404)
                        self.assertEqual(self.events(), before)
                        self.assertEqual(len(requests), 1)
                    finally:
                        release.set()
                    code, body, headers = active.result(timeout=5)
                    self.assertEqual((code, body), (200, raw))
                    first_receipt = headers["X-OI-Access-Receipt"]
                    self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(len(self.events("AND event_type='image.original_read_authorized'")), 1)
                code, body, headers = image_request(base, original_path)
                self.assertEqual((code, body), (200, raw))
                self.assertNotEqual(headers["X-OI-Access-Receipt"], first_receipt)
                self.assertEqual(len(requests), 2)
                self.assertEqual(len(self.events("AND event_type='image.original_read_authorized'")), 2)
                self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 1)
                self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links")[0][0], 1)

    def test_revocation_still_withholds_active_read_after_capacity_refusal(self):
        raw = image_bytes()
        entered, release = threading.Event(), threading.Event()

        def hold(conn, _):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test did not release admitted archive read")
            conn.sendall(http_response(raw))

        with archive_server(handler=hold) as (socket_path, requests):
            adapter = self.archive(socket_path)
            with running_server(create_app(self.settings, image_archive=adapter)) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                original_path = path + "/" + image
                before = self.events()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    active = pool.submit(image_request, base, original_path)
                    try:
                        self.assertTrue(entered.wait(2))
                        self.assert_capacity_denied(base, original_path)
                        self.creds[0]["actions"].remove("image_original_read")
                        self.write()
                        self.assertEqual(image_request(base, original_path)[0], 404)
                        self.assertEqual(len(requests), 1)
                    finally:
                        release.set()
                    code, body, headers = active.result(timeout=5)
                    self.assertEqual(code, 404)
                    self.assertIsNone(headers.get("X-OI-Access-Receipt"))
                self.assertEqual(self.events(), before)
                # Re-authorize only this fictional fixture to prove no slot leak
                # after the canonical owner withheld the prior transport result.
                self.creds[0]["actions"].append("image_original_read")
                self.write()
                self.assertEqual(image_request(base, original_path)[:2], (200, raw))
                self.assertEqual(len(requests), 2)
                self.assertEqual(len(self.events("AND event_type='image.original_read_authorized'")), 1)

    def test_archive_timeout_releases_capacity_without_success_receipt(self):
        raw = image_bytes()
        closed = threading.Event()
        lock = threading.Lock()
        count = 0

        def first_stalls(conn, _):
            nonlocal count
            with lock:
                count += 1
                first = count == 1
            if first:
                if conn.recv(1) == b"":
                    closed.set()
            else:
                conn.sendall(http_response(raw))

        with archive_server(handler=first_stalls) as (socket_path, requests):
            adapter = self.archive(socket_path, timeout_seconds=0.2)
            with running_server(create_app(self.settings, image_archive=adapter)) as base:
                patient, source, path = self.prepare(base)
                image = image_request(base, path, raw=raw)[1]["image_id"]
                original_path = path + "/" + image
                before = self.events()
                self.assert_capacity_denied(base, original_path)
                self.assertTrue(closed.wait(1))
                self.assertEqual(self.events(), before)
                self.assertEqual(image_request(base, original_path)[:2], (200, raw))
                self.assertEqual(len(requests), 2)
                self.assertEqual(len(self.events("AND event_type='image.original_read_authorized'")), 1)


def load_tests(loader, tests, pattern):
    # Only newly authored methods; do not multiply the inherited custody suite.
    return unittest.TestSuite(ArchiveCapacityCustodyTests(name)
                              for name in ArchiveCapacityCustodyTests.__dict__
                              if name.startswith("test_"))
