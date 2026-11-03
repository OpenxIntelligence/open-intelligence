"""Real Linux socket tests for the bounded original replica transport."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import math
import os
from pathlib import Path
import socket
import struct
import threading
import time
import traceback
import unittest
from unittest.mock import patch

from archive_socket_fixture import archive_server, http_response, multipart_body
from dicom_integrity_fixture import dicom_bytes

UIDS = ("2.25.101", "2.25.102", "2.25.103")
RAW = dicom_bytes(study_uid=UIDS[0], series_uid=UIDS[1], sop_uid=UIDS[2])
MULTIPART = b'multipart/related; type="application/dicom"; boundary="oi-boundary"'
MAX_BYTES = 2_097_152


class ArchiveSocketTests(unittest.TestCase):
    def setUp(self):
        # Absence is a named feature failure, not a dependency/import error.
        self.assertIsNotNone(importlib.util.find_spec("oi_api.archive_socket"),
                             "The private-socket archive reader is not implemented")
        from oi_api.archive_socket import UnixSocketImageArchive, ArchiveTransportError
        self.Archive = UnixSocketImageArchive
        self.Error = ArchiveTransportError

    def reader(self, path, **changes):
        args = {"expected_peer_uid": os.getuid(), "timeout_seconds": 0.5}
        args.update(changes)
        return self.Archive(path, **args)

    def assert_rejected(self, response, **changes):
        with archive_server(response) as (path, requests):
            with self.assertRaises(self.Error) as caught:
                self.reader(path, **changes).read(*UIDS)
            self.assertEqual(str(caught.exception), "Archive transport unavailable")
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(len(requests), 1)

    def test_exact_original_and_fixed_request_without_caller_credentials(self):
        with archive_server(http_response(RAW)) as (path, requests):
            with patch.dict(os.environ, {"HTTP_PROXY": "http://invalid.test:9999"}), \
                    patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
                self.assertEqual(self.reader(path).read(*UIDS), RAW)
        self.assertEqual(requests, [
            b"GET /studies/2.25.101/series/2.25.102/instances/2.25.103 HTTP/1.1\r\n"
            b"Host: oi-archive\r\n"
            b'Accept: multipart/related; type="application/dicom", application/dicom\r\n'
            b"Accept-Encoding: identity\r\nConnection: close\r\n\r\n"])

    def test_single_multipart_part_preserves_every_byte(self):
        raw = RAW + b"\x00\r\n binary -- ordinary suffix \xff\r\n"
        with archive_server(http_response(multipart_body(raw), content_type=MULTIPART)) as (path, _):
            self.assertEqual(self.reader(path).read(*UIDS), raw)

    def test_fragmented_headers_and_binary_are_reassembled(self):
        wire = http_response(multipart_body(RAW), content_type=MULTIPART)
        def fragmented(conn, _):
            for i in range(0, len(wire), 7):
                conn.sendall(wire[i:i + 7])
        with archive_server(handler=fragmented) as (path, _):
            self.assertEqual(self.reader(path).read(*UIDS), RAW)

    def test_peer_uid_mismatch_sends_no_identifiers(self):
        with archive_server(http_response(RAW)) as (path, requests):
            with self.assertRaises(self.Error):
                self.reader(path, expected_peer_uid=os.getuid() + 1).read(*UIDS)
        self.assertEqual(requests, [])

    def test_invalid_identifiers_are_rejected_before_socket_creation(self):
        for bad in ("", "1", "1.02", ".1", "1.", "1..2", "1/2", "1%2e2",
                    "1.2?x", "1.2\r\nX: y", "１.２", "1.2\x00", "1.2\n",
                    "9" * 63 + ".2", None, 12, True):
            for index in range(3):
                with self.subTest(bad=bad, position=index):
                    ids = list(UIDS); ids[index] = bad
                    with patch.object(socket, "socket", side_effect=AssertionError("must not connect")):
                        with self.assertRaises(self.Error):
                            self.reader("/tmp/oi-test.sock").read(*ids)

    def test_invalid_configuration_is_generic_and_does_not_connect(self):
        configs = [(path, {}) for path in ("", "relative.sock", "\x00abstract", "https://host",
                                            "/tmp/a\x00b", "/" + "x" * 108, None)]
        configs += [("/tmp/oi.sock", {"expected_peer_uid": uid}) for uid in (-1, True, "0", None, 2**32)]
        configs += [("/tmp/oi.sock", {"timeout_seconds": t}) for t in
                    (0, -1, 0.049, 31, math.nan, math.inf, True, "1", None)]
        for path, args in configs:
            with self.subTest(path=path, args=args), \
                    patch.object(socket, "socket", side_effect=AssertionError("must not connect")):
                with self.assertRaises(ValueError) as caught:
                    self.reader(path, **args)
                self.assertEqual(str(caught.exception), "Invalid archive transport configuration")

    def test_configuration_repr_withholds_private_path(self):
        reader = self.reader("/tmp/PRIVATE-ARCHIVE.sock")
        self.assertNotIn("PRIVATE-ARCHIVE", repr(reader))

    def test_missing_socket_error_has_no_path_or_exception_chain(self):
        with self.assertRaises(self.Error) as caught:
            self.reader("/tmp/oi-nonexistent-PRIVATE-ARCHIVE.sock").read(*UIDS)
        self.assertEqual(str(caught.exception), "Archive transport unavailable")
        self.assertIsNone(caught.exception.__context__)
        rendered = "".join(traceback.format_exception(caught.exception))
        self.assertNotIn("No such file", rendered)
        # Tracebacks with locals are outside this guarantee; normal errors do not echo paths.
        self.assertNotIn("FileNotFoundError", rendered)

    def test_non_200_statuses_including_redirect_are_rejected_without_retry(self):
        for status in (b"100 Continue", b"206 Partial Content", b"301 Moved", b"302 Found",
                       b"307 Temporary Redirect", b"401 Denied", b"404 Missing", b"500 PRIVATE"):
            with self.subTest(status=status):
                self.assert_rejected(http_response(RAW, status=status,
                    extra=b"Location: http://invalid.test/PRIVATE\r\n"))

    def test_missing_duplicate_signed_and_ambiguous_content_lengths_are_rejected(self):
        for length in (b"", b"-1", b"+1", b"01", b"1, 1", b"1 1", b"9" * 5000):
            wire = b"HTTP/1.1 200 OK\r\nContent-Type: application/dicom\r\n"
            if length:
                wire += b"Content-Length: " + length + b"\r\n"
            with self.subTest(length=length[:30]):
                self.assert_rejected(wire + b"\r\nx")
        for extra in (b"Content-Length: 1\r\n", b"content-length: 1\r\n"):
            self.assert_rejected(http_response(b"x", extra=extra))

    def test_transfer_encoding_and_content_encoding_are_never_decoded(self):
        for extra in (b"Transfer-Encoding: chunked\r\n", b"Transfer-Encoding: identity\r\n",
                      b"Content-Encoding: gzip\r\n", b"Content-Encoding: identity\r\n"):
            self.assert_rejected(http_response(RAW, extra=extra))

    def test_invalid_header_framing_and_controls_are_rejected(self):
        for extra in (b" Bad: folded\r\n", b"Bad : value\r\n", b"Bad\r\n",
                      b"X: bad\x00value\r\n", b"X: a\nInjected: b\r\n",
                      b"X: a\rInjected: b\r\n", b"X: a\x7f\r\n"):
            self.assert_rejected(http_response(RAW, extra=extra))
        self.assert_rejected(http_response(RAW).replace(b"HTTP/1.1", b"HTTP/2.0"))

    def test_header_byte_line_and_count_limits_are_enforced(self):
        self.assert_rejected(http_response(RAW, extra=b"X: " + b"x" * 4096 + b"\r\n"))
        self.assert_rejected(http_response(RAW, extra=b"".join(
            b"X-" + str(i).encode() + b": x\r\n" for i in range(65))))
        self.assert_rejected(http_response(RAW, extra=b"".join(
            b"X-" + str(i).encode() + b": " + b"x" * 4000 + b"\r\n" for i in range(5))))

    def test_unsupported_media_type_and_duplicate_type_parameters_are_rejected(self):
        for ct in (b"text/html", b"application/octet-stream", b"application/dicom+json",
                   b"application/dicom; charset=utf-8", b"multipart/mixed; boundary=oi-boundary",
                   b'multipart/related; type="application/dicom"',
                   MULTIPART + b'; boundary="second"',
                   MULTIPART + b'; type="text/html"',
                   MULTIPART + b'; start="part"'):
            with self.subTest(ct=ct):
                self.assert_rejected(http_response(RAW, content_type=ct))
        self.assert_rejected(http_response(RAW, extra=b"Content-Type: application/dicom\r\n"))

    def test_empty_truncated_and_surplus_wire_bodies_are_rejected(self):
        for wire in (http_response(b""), http_response(RAW)[:-1], http_response(RAW) + b"x",
                     http_response(RAW) + http_response(RAW)):
            self.assert_rejected(wire)

    def test_raw_instance_exact_limit_succeeds_and_one_over_fails(self):
        raw = b"x" * MAX_BYTES
        with archive_server(http_response(raw)) as (path, _):
            self.assertEqual(self.reader(path, timeout_seconds=2).read(*UIDS), raw)
        self.assert_rejected(http_response(raw + b"x"), timeout_seconds=2)

    def test_multipart_exact_instance_limit_and_one_over(self):
        raw = b"x" * MAX_BYTES
        with archive_server(http_response(multipart_body(raw), content_type=MULTIPART)) as (path, _):
            self.assertEqual(self.reader(path, timeout_seconds=2).read(*UIDS), raw)
        self.assert_rejected(http_response(multipart_body(raw + b"x"), content_type=MULTIPART), timeout_seconds=2)

    def test_declared_oversize_is_rejected_without_waiting_for_body(self):
        closed = threading.Event()
        def oversized(conn, _):
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/dicom\r\n"
                         b"Content-Length: 999999999\r\n\r\n")
            if conn.recv(1) == b"":
                closed.set()
        with archive_server(handler=oversized) as (path, _):
            with self.assertRaises(self.Error):
                self.reader(path).read(*UIDS)
        self.assertTrue(closed.is_set())

    def test_multipart_preamble_epilogue_missing_close_and_extra_part_fail(self):
        body = multipart_body(RAW)
        bodies = (b"preamble\r\n" + body, body + b"epilogue", body[:-4],
                  body.replace(b"--oi-boundary--\r\n", b"--oi-boundary\r\n"
                               b"Content-Type: application/dicom\r\n\r\n" + RAW
                               + b"\r\n--oi-boundary--\r\n"),
                  multipart_body(b""))
        for malformed in bodies:
            self.assert_rejected(http_response(malformed, content_type=MULTIPART))

    def test_multipart_part_headers_reject_nested_encoding_and_bad_lengths(self):
        for extra in (b"Content-Encoding: gzip\r\n", b"Content-Transfer-Encoding: base64\r\n",
                      b"Transfer-Encoding: chunked\r\n", b"Content-Length: 1\r\n",
                      b"Content-Type: multipart/mixed\r\n", b" X: fold\r\n"):
            self.assert_rejected(http_response(multipart_body(RAW, extra=extra), content_type=MULTIPART))

    def test_multipart_boundary_validation_rejects_controls_and_unbounded_tokens(self):
        for boundary in (b"", b"x" * 71, b"semi;colon", b"bad\\escape", b"bad\tvalue"):
            ct = b'multipart/related; type="application/dicom"; boundary="' + boundary + b'"'
            self.assert_rejected(http_response(multipart_body(RAW, boundary=boundary), content_type=ct))

    def test_single_quoted_boundary_with_spaces_preserves_payload(self):
        boundary = b"DICOM DATA BOUNDARY"
        ct = b'multipart/related; boundary="DICOM DATA BOUNDARY"; type="application/dicom"'
        with archive_server(http_response(multipart_body(RAW, boundary=boundary), content_type=ct)) as (path, _):
            self.assertEqual(self.reader(path).read(*UIDS), RAW)

    def test_header_trickle_cannot_extend_total_deadline(self):
        def trickle(conn, _):
            for byte in http_response(RAW):
                conn.sendall(bytes([byte])); time.sleep(0.02)
        with archive_server(handler=trickle) as (path, _):
            start = time.monotonic()
            with self.assertRaises(self.Error):
                self.reader(path, timeout_seconds=0.12).read(*UIDS)
            self.assertLess(time.monotonic() - start, 0.8)

    def test_body_trickle_cannot_extend_total_deadline(self):
        header = http_response(RAW).split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
        def trickle(conn, _):
            conn.sendall(header)
            for byte in RAW:
                conn.sendall(bytes([byte])); time.sleep(0.02)
        with archive_server(handler=trickle) as (path, _):
            start = time.monotonic()
            with self.assertRaises(self.Error):
                self.reader(path, timeout_seconds=0.12).read(*UIDS)
            self.assertLess(time.monotonic() - start, 0.8)

    def test_complete_body_without_eof_is_bounded_and_rejected(self):
        def stalled(conn, _):
            conn.sendall(http_response(RAW)); time.sleep(0.25)
        with archive_server(handler=stalled) as (path, _):
            with self.assertRaises(self.Error):
                self.reader(path, timeout_seconds=0.08).read(*UIDS)

    def test_peer_disconnect_before_headers_fails_closed(self):
        with archive_server(handler=lambda conn, request: None) as (path, _):
            with self.assertRaises(self.Error):
                self.reader(path).read(*UIDS)

    def test_repeated_and_concurrent_calls_do_not_share_socket_or_cache(self):
        with archive_server(http_response(RAW)) as (path, requests):
            reader = self.reader(path, timeout_seconds=2)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: reader.read(*UIDS), range(12)))
            self.assertEqual(results, [RAW] * 12)
            self.assertEqual(reader.read(*UIDS), RAW)
        self.assertEqual(len(requests), 13)

    def test_repeated_failure_does_not_leak_file_descriptors(self):
        if not Path("/proc/self/fd").is_dir():
            self.skipTest("Linux /proc/self/fd is unavailable")
        before = len(list(Path("/proc/self/fd").iterdir()))
        with archive_server(http_response(RAW, status=b"500 PRIVATE")) as (path, _):
            reader = self.reader(path)
            for _ in range(20):
                with self.assertRaises(self.Error):
                    reader.read(*UIDS)
        self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)

    def test_huge_timeout_integer_is_a_generic_configuration_error(self):
        with self.assertRaises(ValueError) as caught:
            self.reader("/tmp/oi.sock", timeout_seconds=10**1000)
        self.assertEqual(str(caught.exception), "Invalid archive transport configuration")

    def test_peer_uid_decodes_as_unsigned_kernel_uid_t(self):
        # Host cannot create every uid_t; only the kernel credential bytes are
        # injected here. Request/response still travel through a real socket.
        high_uid = 2**31 + 7
        credentials = struct.pack("=iII", os.getpid(), high_uid, os.getgid())
        with archive_server(http_response(RAW)) as (path, _):
            with patch.object(socket.socket, "getsockopt", return_value=credentials):
                self.assertEqual(self.reader(path, expected_peer_uid=high_uid).read(*UIDS), RAW)

    def test_part_content_location_and_length_match_the_one_requested_object(self):
        path_header = (b"Content-Location: /studies/2.25.101/series/2.25.102/instances/2.25.103\r\n"
                       b"Content-Length: " + str(len(RAW)).encode() + b"\r\n")
        with archive_server(http_response(multipart_body(RAW, extra=path_header),
                                         content_type=MULTIPART)) as (path, _):
            self.assertEqual(self.reader(path).read(*UIDS), RAW)
        self.assert_rejected(http_response(multipart_body(RAW, extra=path_header.replace(
            b"2.25.103", b"2.25.104")), content_type=MULTIPART))

    def test_short_peer_credential_record_is_generic_failure_before_request(self):
        with archive_server(http_response(RAW)) as (path, requests):
            with patch.object(socket.socket, "getsockopt", return_value=b"bad"):
                with self.assertRaises(self.Error) as caught:
                    self.reader(path).read(*UIDS)
        self.assertEqual(requests, [])
        self.assertIsNone(caught.exception.__context__)

    def test_header_deadline_closes_the_peer_connection(self):
        closed = threading.Event()
        def wait_for_client_close(conn, _):
            if conn.recv(1) == b"":
                closed.set()
        with archive_server(handler=wait_for_client_close) as (path, _):
            with self.assertRaises(self.Error):
                self.reader(path, timeout_seconds=0.08).read(*UIDS)
        self.assertTrue(closed.is_set())

    def test_linux_peer_credential_capability_is_required(self):
        with patch.object(socket, "SO_PEERCRED", None):
            with self.assertRaises(ValueError) as caught:
                self.reader("/tmp/oi.sock")
        self.assertEqual(str(caught.exception), "Invalid archive transport configuration")


if __name__ == "__main__":
    unittest.main()

