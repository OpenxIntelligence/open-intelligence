"""Concurrent transport bounds using event-controlled, actual Unix sockets."""
from concurrent.futures import ThreadPoolExecutor
import os
import socket
import threading
import unittest
from unittest.mock import patch

from oi_api import archive_socket
from archive_socket_fixture import archive_server, http_response

UIDS = ("2.25.201", "2.25.202", "2.25.203")
# Arbitrary authored transport payload, not clinical image/parser acceptance.
RAW = b"independently authored capacity fixture\x00\xff"


class ArchiveCapacityTests(unittest.TestCase):
    def capacity(self, count=4):
        cls = getattr(archive_socket, "ArchiveReadCapacity", None)
        self.assertIsNotNone(cls, "Shared archive read capacity is not implemented")
        return cls(max_in_flight=count)

    def reader(self, path, **changes):
        return archive_socket.UnixSocketImageArchive(
            path, os.getuid(), changes.pop("timeout_seconds", 2.0), **changes)

    def assert_unavailable(self, reader):
        with self.assertRaises(archive_socket.ArchiveTransportError) as caught:
            reader.read(*UIDS)
        self.assertEqual(str(caught.exception), "Archive transport unavailable")
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)

    def exercise_limit(self, limit, capacity=None):
        """Hold N peers; excess callers must finish before those peers are freed."""
        entered, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        count = 0

        def hold(conn, _):
            nonlocal count
            with lock:
                count += 1
                position = count
                if position == limit:
                    entered.set()
            if position <= limit:
                if not release.wait(4):
                    raise AssertionError("test did not release admitted peers")
            conn.sendall(http_response(RAW))

        with archive_server(handler=hold) as (path, requests):
            kwargs = {} if capacity is None else {"capacity": capacity}
            reader = self.reader(path, **kwargs)
            with ThreadPoolExecutor(max_workers=limit + 1) as pool:
                active = [pool.submit(reader.read, *UIDS) for _ in range(limit)]
                try:
                    self.assertTrue(entered.wait(2), "expected reads did not reach archive")
                    # The legacy reader succeeds here: an actual excess admission,
                    # not a missing-symbol or mock-only reproduction.
                    self.assert_unavailable(reader)
                    self.assertEqual(len(requests), limit)
                    # Refusal must precede socket allocation, not just identifier send.
                    with patch.object(socket, "socket", side_effect=AssertionError("excess socket")):
                        for _ in range(10):
                            self.assert_unavailable(reader)
                finally:
                    release.set()
                self.assertEqual([f.result(timeout=2) for f in active], [RAW] * limit)
            self.assertEqual(reader.read(*UIDS), RAW)
            self.assertEqual(len(requests), limit + 1)

    def test_default_capacity_refuses_fifth_read_without_waiting(self):
        self.exercise_limit(4)

    def test_custom_single_slot_recovers_after_repeated_refusal(self):
        self.exercise_limit(1, self.capacity(1))

    def test_maximum_capacity_is_enforced(self):
        self.exercise_limit(16, self.capacity(16))

    def test_configuration_rejects_unbounded_or_ambiguous_capacity(self):
        for value in (0, -1, 17, True, False, 1.0, "4", None, 10**1000):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError) as caught:
                    self.capacity(value)
                self.assertEqual(str(caught.exception), "Invalid archive read capacity")
                self.assertIsNone(caught.exception.__context__)

    def test_reader_refuses_fake_or_disabled_capacity(self):
        for capacity in (None, 4, "unlimited", object()):
            with self.subTest(capacity_type=type(capacity).__name__):
                with self.assertRaises(ValueError) as caught:
                    self.reader("/tmp/PRIVATE.sock", capacity=capacity)
                self.assertEqual(str(caught.exception), "Invalid archive transport configuration")

    def test_capacity_configuration_cannot_be_mutated(self):
        from dataclasses import FrozenInstanceError
        capacity = self.capacity(1)
        with self.assertRaises(FrozenInstanceError):
            capacity.max_in_flight = 16

    def test_two_adapters_share_one_capacity_without_sharing_connections(self):
        capacity = self.capacity(1)
        entered, release = threading.Event(), threading.Event()

        def hold(conn, _):
            entered.set()
            if not release.wait(4):
                raise AssertionError("test did not release peer")
            conn.sendall(http_response(RAW))

        with archive_server(handler=hold) as (path_a, requests_a), \
                archive_server(http_response(b"second original")) as (path_b, requests_b):
            first = self.reader(path_a, capacity=capacity)
            second = self.reader(path_b, capacity=capacity)
            with ThreadPoolExecutor(max_workers=1) as pool:
                active = pool.submit(first.read, *UIDS)
                try:
                    self.assertTrue(entered.wait(2))
                    self.assert_unavailable(second)
                    self.assertEqual(requests_b, [])
                finally:
                    release.set()
                self.assertEqual(active.result(timeout=2), RAW)
            self.assertEqual(second.read(*UIDS), b"second original")
            self.assertEqual(len(requests_a), 1)
            self.assertEqual(len(requests_b), 1)

    def test_separate_default_capacities_do_not_block_unrelated_adapters(self):
        entered, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        count = 0

        def hold(conn, _):
            nonlocal count
            with lock:
                count += 1
                if count == 4:
                    entered.set()
            if not release.wait(4):
                raise AssertionError("test did not release peers")
            conn.sendall(http_response(RAW))

        with archive_server(handler=hold) as (path_a, _), \
                archive_server(http_response(RAW)) as (path_b, _):
            first = self.reader(path_a)
            second = self.reader(path_b)
            with ThreadPoolExecutor(max_workers=4) as pool:
                active = [pool.submit(first.read, *UIDS) for _ in range(4)]
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(second.read(*UIDS), RAW)
                finally:
                    release.set()
                self.assertEqual([f.result(timeout=2) for f in active], [RAW] * 4)

    def test_simultaneous_refusals_do_not_increase_available_slots(self):
        capacity = self.capacity(2)
        entered, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        count = 0

        def hold(conn, _):
            nonlocal count
            with lock:
                count += 1
                if count == 2:
                    entered.set()
            if not release.wait(4):
                raise AssertionError("test did not release peers")
            conn.sendall(http_response(RAW))

        with archive_server(handler=hold) as (path, requests):
            reader = self.reader(path, capacity=capacity)
            with ThreadPoolExecutor(max_workers=10) as pool:
                active = [pool.submit(reader.read, *UIDS) for _ in range(2)]
                try:
                    self.assertTrue(entered.wait(2))
                    refused = [pool.submit(self.assert_unavailable, reader) for _ in range(32)]
                    for result in refused:
                        result.result(timeout=1)
                    self.assertEqual(len(requests), 2)
                    self.assert_unavailable(reader)
                finally:
                    release.set()
                self.assertEqual([f.result(timeout=2) for f in active], [RAW] * 2)
            self.assertEqual(reader.read(*UIDS), RAW)

    def test_capacity_is_held_until_parsing_finishes(self):
        capacity = self.capacity(1)
        entered, release = threading.Event(), threading.Event()
        parse = archive_socket._instance

        def hold_parse(*args):
            entered.set()
            if not release.wait(4):
                raise AssertionError("test did not release parser")
            return parse(*args)

        with archive_server(http_response(RAW)) as (path, requests):
            reader = self.reader(path, capacity=capacity)
            with ThreadPoolExecutor(max_workers=1) as pool:
                with patch.object(archive_socket, "_instance", side_effect=hold_parse):
                    active = pool.submit(reader.read, *UIDS)
                    try:
                        self.assertTrue(entered.wait(2))
                        self.assert_unavailable(reader)
                        self.assertEqual(len(requests), 1)
                    finally:
                        release.set()
                    self.assertEqual(active.result(timeout=2), RAW)
            self.assertEqual(reader.read(*UIDS), RAW)

    def test_transport_failures_release_shared_capacity(self):
        capacity = self.capacity(1)
        with archive_server(http_response(RAW)) as (good_path, _):
            good = self.reader(good_path, capacity=capacity)
            for wire in (b"", b"invalid", http_response(RAW)[:-1], http_response(RAW) + b"extra"):
                with archive_server(wire) as (bad_path, _):
                    self.assert_unavailable(self.reader(bad_path, capacity=capacity))
                self.assertEqual(good.read(*UIDS), RAW)
            wrong_peer = archive_socket.UnixSocketImageArchive(
                good_path, os.getuid() + 1, capacity=capacity)
            self.assert_unavailable(wrong_peer)
            self.assertEqual(good.read(*UIDS), RAW)
            self.assert_unavailable(self.reader(good_path + ".missing", capacity=capacity))
            self.assertEqual(good.read(*UIDS), RAW)

    def test_timed_out_read_releases_capacity_and_closes_socket(self):
        capacity = self.capacity(1)
        closed = threading.Event()

        def await_close(conn, _):
            if conn.recv(1) == b"":
                closed.set()

        with archive_server(handler=await_close) as (stalled_path, _), \
                archive_server(http_response(RAW)) as (good_path, _):
            self.assert_unavailable(self.reader(stalled_path, capacity=capacity, timeout_seconds=0.08))
            self.assertTrue(closed.wait(1))
            self.assertEqual(self.reader(good_path, capacity=capacity).read(*UIDS), RAW)

    def test_exceptional_unwinding_releases_slot_without_swallowing_cancel(self):
        class Cancelled(BaseException):
            pass

        capacity = self.capacity(1)
        with archive_server(http_response(RAW)) as (path, _):
            reader = self.reader(path, capacity=capacity)
            with patch.object(archive_socket, "_instance", side_effect=Cancelled):
                with self.assertRaises(Cancelled):
                    reader.read(*UIDS)
            self.assertEqual(reader.read(*UIDS), RAW)

    def test_invalid_identifiers_do_not_consume_capacity(self):
        capacity = self.capacity(1)
        with archive_server(http_response(RAW)) as (path, requests):
            reader = self.reader(path, capacity=capacity)
            with self.assertRaises(archive_socket.ArchiveTransportError):
                reader.read("bad/uid", UIDS[1], UIDS[2])
            self.assertEqual(requests, [])
            self.assertEqual(reader.read(*UIDS), RAW)


if __name__ == "__main__":
    unittest.main()
