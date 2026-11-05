"""Real subprocess/loopback checks for browser startup failure evidence."""
import contextlib
import http.server
import json
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import browser_journey


class BrowserStartupTests(unittest.TestCase):
    @contextlib.contextmanager
    def process(self, script):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stderr.log"
            with path.open("wb") as stderr:
                process = subprocess.Popen([sys.executable, "-c", script], stderr=stderr)
                try:
                    yield process, path
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=5)

    def wait(self, process, path, port, timeout=0.2):
        return browser_journey.wait_for_browser(process, path, port, timeout=timeout)

    def test_early_exit_retains_code_and_bounded_escaped_stderr_tail(self):
        script = "import sys; sys.stderr.write('discard-me' + 'x'*10000 + '\\n::error::fixture\\x1b[31m\\xff'); sys.exit(23)"
        with self.process(script) as (process, path):
            process.wait(timeout=5)
            with self.assertRaises(AssertionError) as raised:
                self.wait(process, path, browser_journey.free_port())
            message = str(raised.exception)
            self.assertIn("exit=23", message)
            self.assertIn("::error::fixture", message)
            self.assertNotIn("discard-me", message)
            self.assertNotIn("\n", message)
            self.assertNotIn("\x1b", message)
            self.assertLess(len(message), 26000)

    def test_live_process_timeout_is_failure_with_diagnostics(self):
        with self.process("import time; time.sleep(30)") as (process, path):
            with self.assertRaises(AssertionError) as raised:
                self.wait(process, path, browser_journey.free_port())
            self.assertIn("Timed out", str(raised.exception))
            self.assertIn("exit=None", str(raised.exception))
            self.assertIsNone(process.poll())

    def test_missing_log_does_not_replace_startup_failure(self):
        with self.process("raise SystemExit(7)") as (process, path):
            process.wait(timeout=5)
            with self.assertRaises(AssertionError) as raised:
                self.wait(process, path.with_name("absent"), browser_journey.free_port())
            self.assertIn("exit=7", str(raised.exception))
            self.assertIn("unavailable", str(raised.exception))

    def test_slow_start_waits_for_an_attachable_page(self):
        page = {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1/fixture"}
        responses = [
            ConnectionRefusedError(),
            BytesIO(b'[{"type":"service_worker"}]'),
            BytesIO(b'[{"type":"page"}]'),
            BytesIO(json.dumps([page]).encode()),
        ]
        # Simulate a cold runner without adding a wall-clock delay to CI.
        clock = iter([0, 0, 13, 14, 15])
        with patch.object(browser_journey.time, "monotonic", side_effect=clock), \
             patch.object(browser_journey.time, "sleep"), \
             patch.object(browser_journey, "urlopen", side_effect=responses) as probe:
            targets = browser_journey.wait_for_browser(
                Mock(poll=Mock(return_value=None)), Path("unused.log"), 9222)
        self.assertEqual(targets, [page])
        self.assertEqual(probe.call_count, 4)

    def test_ready_target_returns_original_payload(self):
        payload = [{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1/fixture"}]
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())
            def log_message(self, *args):
                pass
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.process("import time; time.sleep(30)") as (process, path):
                    self.assertEqual(self.wait(process, path, server.server_port), payload)
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
