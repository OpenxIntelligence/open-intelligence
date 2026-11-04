"""Actual socket checks for test-only restored-image acceptance infrastructure."""
from contextlib import redirect_stderr
from io import StringIO
import importlib.util
import os
from pathlib import Path
import socket
import tempfile
import unittest

from oi_api.archive_socket import UnixSocketImageArchive, ArchiveTransportError

MODULE = Path(__file__).resolve().parents[1] / "tools/archive_acceptance_app.py"
UIDS = ("2.25.101", "2.25.102", "2.25.103")
RAW = b"INDEPENDENTLY-AUTHORED-SOCKET-FIXTURE\x00\xff"
REQUEST = (
    b"GET /studies/2.25.101/series/2.25.102/instances/2.25.103 HTTP/1.1\r\n"
    b"Host: oi-archive\r\n"
    b'Accept: multipart/related; type="application/dicom", application/dicom\r\n'
    b"Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
)


class Reader:
    def __init__(self, value=RAW):
        self.calls = []
        self.value = value

    def read(self, *ids):
        self.calls.append(ids)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class SocketArchiveAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), "Socket-backed recovery acceptance is missing")
        spec = importlib.util.spec_from_file_location("oi_socket_acceptance_test", MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory(prefix="oi-as-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "archive.sock")

    def read(self):
        return UnixSocketImageArchive(self.path, os.getuid(), timeout_seconds=1).read(*UIDS)

    def raw_request(self, request, *, reset_after_denial=False):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect(self.path)
            conn.sendall(request)
            conn.shutdown(socket.SHUT_WR)
            data = b""
            try:
                while chunk := conn.recv(4096):
                    data += chunk
                    self.assertLessEqual(len(data), 4096)
            except ConnectionResetError:
                # A bounded responder does not drain excess input. Our actual
                # oversize probe receives the complete denial then a reset.
                if not reset_after_denial:
                    raise
                self.assertEqual(data, self.module._FAILURE)
            return data

    def test_exact_original_uses_only_canonical_identifiers(self):
        reader = Reader()
        with self.module.socket_archive_service(reader, self.path):
            self.assertEqual(self.read(), RAW)
            self.assertEqual(self.read(), RAW)
        self.assertEqual(reader.calls, [UIDS, UIDS])
        self.assertFalse(Path(self.path).exists())

    def test_ambiguous_route_credentials_and_surplus_requests_never_reach_reader(self):
        variants = (
            REQUEST.replace(b"GET ", b"POST ", 1),
            REQUEST.replace(b"2.25.101", b"2.025.101", 1),
            REQUEST.replace(b"/instances/", b"/frames/", 1),
            REQUEST.replace(b" HTTP/1.1", b"?token=secret HTTP/1.1", 1),
            REQUEST.replace(b"Connection: close", b"Authorization: Bearer SECRET\r\nConnection: close"),
            REQUEST.replace(b"Host: oi-archive", b"Host: external.test"),
            REQUEST + b"EXTRA",
            b"GET /private HTTP/1.1\r\n\r\n",
        )
        reader = Reader()
        with self.module.socket_archive_service(reader, self.path):
            for req in variants:
                with self.subTest(request=req[:60]):
                    response = self.raw_request(req)
                    self.assertTrue(response.startswith(b"HTTP/1.1 503 "))
                    self.assertNotIn(b"SECRET", response)
        self.assertEqual(reader.calls, [])

    def test_reader_failure_wrong_type_and_oversize_are_sanitized_and_recoverable(self):
        reader = Reader()
        errors = StringIO()
        with redirect_stderr(errors), self.module.socket_archive_service(reader, self.path):
            for bad in (FileNotFoundError("PRIVATE-PATH"), b"", "not bytes", b"x" * (2_097_152 + 1)):
                reader.value = bad
                with self.assertRaises(ArchiveTransportError):
                    self.read()
            reader.value = RAW
            self.assertEqual(self.read(), RAW)
        self.assertNotIn("PRIVATE-PATH", errors.getvalue())
        self.assertEqual(len(reader.calls), 5)

    def test_incomplete_and_oversized_requests_are_refused_without_lookup(self):
        reader = Reader()
        with self.module.socket_archive_service(reader, self.path):
            for req in (b"GET /incomplete", b"x" * 2048):
                self.assertTrue(self.raw_request(req, reset_after_denial=len(req) > 1024).startswith(b"HTTP/1.1 503 "))
        self.assertEqual(reader.calls, [])

    def test_shutdown_after_client_disconnect_allows_fresh_listener(self):
        reader = Reader()
        with self.module.socket_archive_service(reader, self.path):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.connect(self.path)
        self.assertFalse(Path(self.path).exists())
        with self.module.socket_archive_service(reader, self.path):
            self.assertEqual(self.read(), RAW)
        self.assertEqual(reader.calls, [UIDS])

    def test_failed_context_still_closes_listener_and_removes_socket(self):
        reader = Reader()
        with self.assertRaisesRegex(RuntimeError, "test shutdown"):
            with self.module.socket_archive_service(reader, self.path):
                self.assertEqual(self.read(), RAW)
                raise RuntimeError("test shutdown")
        self.assertFalse(Path(self.path).exists())
        with self.assertRaises(ArchiveTransportError):
            self.read()
