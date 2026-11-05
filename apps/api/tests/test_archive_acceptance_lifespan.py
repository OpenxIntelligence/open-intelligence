"""Lifecycle contract of the explicit, synthetic socket recovery factory.

The app-construction boundary is a small injected double so these tests need no
PostgreSQL or third-party runtime. The published factory, context managers,
transport and Unix sockets are real. These are not database acceptance tests.
"""
import asyncio
from contextlib import asynccontextmanager, contextmanager
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from oi_api.archive_socket import ArchiveTransportError

MODULE = Path(__file__).resolve().parents[1] / "tools/archive_acceptance_app.py"
UIDS = ("2.25.101", "2.25.102", "2.25.103")
RAW = b"INDEPENDENTLY-AUTHORED-LIFESPAN-FIXTURE\x00\xff"


class Reader:
    def read(self, *identifiers):
        if identifiers != UIDS:
            raise ValueError("Invalid fictional identifier tuple")
        return RAW


class ArchiveAcceptanceLifespanTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("oi_lifespan_fixture", MODULE)
        self.fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.fixture)
        self.archive = None
        self.events = []

    def app(self, previous_lifespan, *, construction_error=None):
        app_module = ModuleType("oi_api.app")

        def construct(*, image_archive):
            self.archive = image_archive
            if construction_error is not None:
                raise construction_error
            return SimpleNamespace(router=SimpleNamespace(lifespan_context=previous_lifespan))

        app_module.create_app = construct
        # Only the application/manifest boundaries are doubled, never sockets
        # or the transport and lifespan under test.
        with patch.dict(sys.modules, {"oi_api.app": app_module}), patch.object(
            self.fixture, "AcceptanceArchive", return_value=Reader()
        ):
            result = self.fixture.create_acceptance_app()
        self.assertFalse(Path(self.archive.socket_path).exists())
        return result

    def assert_closed(self):
        path = Path(self.archive.socket_path)
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())
        with self.assertRaises(ArchiveTransportError):
            self.archive.read(*UIDS)

    def test_delegated_state_and_startup_shutdown_order_are_preserved(self):
        for state in ({"synthetic_resource": object()}, {}, None):
            with self.subTest(state_kind=type(state).__name__):
                self.events = []

                @asynccontextmanager
                async def previous(application):
                    self.events.append("startup")
                    self.assertEqual(self.archive.read(*UIDS), RAW)
                    try:
                        yield state
                    finally:
                        self.assertEqual(self.archive.read(*UIDS), RAW)
                        self.events.append("shutdown")

                application = self.app(previous)

                async def exercise():
                    async with application.router.lifespan_context(application) as exposed:
                        self.assertIs(exposed, state, "The wrapper discarded delegated lifespan state")
                        self.assertEqual(self.archive.read(*UIDS), RAW)
                        self.events.append("serving")

                try:
                    asyncio.run(exercise())
                    self.assertEqual(self.events, ["startup", "serving", "shutdown"])
                finally:
                    self.assert_closed()

    def test_parent_startup_failure_preserves_error_and_cleans_listener(self):
        failure = RuntimeError("Authored startup failure")

        @asynccontextmanager
        async def previous(application):
            self.events.append("startup")
            self.assertEqual(self.archive.read(*UIDS), RAW)
            raise failure
            yield  # pragma: no cover -- establishes the async context contract

        application = self.app(previous)

        async def exercise():
            async with application.router.lifespan_context(application):
                self.fail("Startup failure must prevent application serving")

        with self.assertRaises(RuntimeError) as caught:
            asyncio.run(exercise())
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.events, ["startup"])
        self.assert_closed()

    def test_parent_shutdown_failure_preserves_error_and_cleans_listener(self):
        failure = RuntimeError("Authored shutdown failure")

        @asynccontextmanager
        async def previous(application):
            yield
            self.assertEqual(self.archive.read(*UIDS), RAW)
            self.events.append("shutdown")
            raise failure

        application = self.app(previous)

        async def exercise():
            async with application.router.lifespan_context(application):
                self.assertEqual(self.archive.read(*UIDS), RAW)

        with self.assertRaises(RuntimeError) as caught:
            asyncio.run(exercise())
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.events, ["shutdown"])
        self.assert_closed()

    def test_cancellation_reaches_parent_cleanup_and_is_not_swallowed(self):
        cancellation = asyncio.CancelledError("Authored cancellation")

        @asynccontextmanager
        async def previous(application):
            try:
                yield
            finally:
                self.assertEqual(self.archive.read(*UIDS), RAW)
                self.events.append("cleanup")

        application = self.app(previous)

        async def exercise():
            async with application.router.lifespan_context(application):
                raise cancellation

        with self.assertRaises(asyncio.CancelledError) as caught:
            asyncio.run(exercise())
        self.assertIs(caught.exception, cancellation)
        self.assertEqual(self.events, ["cleanup"])
        self.assert_closed()

    def test_application_construction_failure_cleans_temporary_directory(self):
        failure = RuntimeError("Authored factory failure")
        with self.assertRaises(RuntimeError) as caught:
            self.app(None, construction_error=failure)
        self.assertIs(caught.exception, failure)
        self.assert_closed()

    def test_service_startup_failure_does_not_enter_parent_lifespan(self):
        failure = RuntimeError("Authored listener startup failure")

        @asynccontextmanager
        async def previous(application):
            self.events.append("unexpected startup")
            yield

        @contextmanager
        def failed_service(*args):
            raise failure
            yield  # pragma: no cover

        application = self.app(previous)

        async def exercise():
            async with application.router.lifespan_context(application):
                self.fail("A failed archive service must not serve the application")

        with patch.object(self.fixture, "socket_archive_service", failed_service):
            with self.assertRaises(RuntimeError) as caught:
                asyncio.run(exercise())
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.events, [])
        self.assert_closed()

    def test_worker_start_failure_closes_bound_socket_before_app_startup(self):
        failure = RuntimeError("Authored worker startup failure")

        @asynccontextmanager
        async def previous(application):
            self.events.append("unexpected startup")
            yield

        application = self.app(previous)

        async def exercise():
            async with application.router.lifespan_context(application):
                self.fail("A failed socket worker must not serve the application")

        with patch.object(self.fixture.threading.Thread, "start", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                asyncio.run(exercise())
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.events, [])
        self.assert_closed()
