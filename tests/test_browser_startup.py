"""Real subprocess/loopback checks for browser startup failure evidence."""
import contextlib
import http.server
import json
import inspect
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

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

    def test_default_chrome_startup_budget_is_bounded_and_does_not_change_app_waits(self):
        startup = inspect.signature(browser_journey.wait_for_browser).parameters['timeout'].default
        application = inspect.signature(browser_journey.wait_for).parameters['timeout'].default
        self.assertGreaterEqual(startup, 20, 'cold Chrome startup must not expire at 12 seconds')
        self.assertLessEqual(startup, 30, 'readiness must still fail within a bounded time')
        self.assertEqual(application, 12, 'do not weaken in-page application waits')

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
