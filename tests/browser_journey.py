"""Dependency-free headless Chromium journey for the SYNTHETIC-ONLY local UI.

Requires a Chrome/Chromium executable already installed by the CI runner.
Uses Python's standard library to speak Chrome DevTools Protocol over WebSocket.
No real patient data, network research APIs, or additional browser packages.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(callback, label: str, timeout: float = 12):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            value = callback()
            if value:
                return value
        except (OSError, ValueError, RuntimeError) as error:
            last_error = error
        time.sleep(0.15)
    raise AssertionError(f"Timed out waiting for {label}; last error: {last_error}")


class ChromeSession:
    """Minimal CDP WebSocket: the test code does not need a browser library."""

    def __init__(self, websocket_url: str):
        url = urlsplit(websocket_url)
        self.socket = socket.create_connection((url.hostname, url.port), timeout=8)
        self.reader = self.socket.makefile("rb")
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {url.path} HTTP/1.1\r\n"
            f"Host: {url.hostname}:{url.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Origin: http://127.0.0.1:{url.port}\r\n\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        status = self.reader.readline()
        if b"101" not in status:
            raise RuntimeError(f"CDP handshake failed: {status!r}")
        headers = {}
        while line := self.reader.readline():
            if line in (b"\r\n", b"\n"):
                break
            name, sep, value = line.partition(b":")
            if sep:
                headers[name.decode().strip().lower()] = value.decode().strip()
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
        ).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise RuntimeError("CDP handshake signature mismatch")
        self.sequence = 0

    def close(self):
        self.reader.close()
        self.socket.close()

    def send_frame(self, data: bytes, opcode: int = 1) -> None:
        mask = os.urandom(4)
        n = len(data)
        header = bytes([0x80 | opcode])
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", n)
        self.socket.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def receive_frame(self) -> bytes | None:
        while True:
            prefix = self.reader.read(2)
            if len(prefix) != 2:
                raise RuntimeError("CDP socket closed")
            opcode = prefix[0] & 0x0F
            length = prefix[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.reader.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.reader.read(8))[0]
            mask = self.reader.read(4) if prefix[1] & 0x80 else None
            data = self.reader.read(length)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 8:
                raise RuntimeError("CDP closed the WebSocket")
            if opcode == 9:
                self.send_frame(data, 10)
                continue
            if opcode in (1, 2):
                return data

    def command(self, method: str, params: dict | None = None) -> dict:
        self.sequence += 1
        expected = self.sequence
        data = json.dumps({"id": expected, "method": method, "params": params or {}}).encode()
        self.send_frame(data)
        while True:
            msg = json.loads(self.receive_frame())
            if msg.get("id") == expected:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result", {})

    def evaluate(self, expression: str):
        result = self.command("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
            "userGesture": True,
        })
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS exception: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    def wait(self, expression: str, label: str):
        return wait_for(lambda: self.evaluate(expression), label)


def main() -> None:
    chrome = next((p for name in ("google-chrome", "google-chrome-stable",
                                 "chromium", "chromium-browser") if (p := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable on the runner; browser journey NOT verified")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="oi-browser-") as directory:
        db = str(Path(directory) / "test.sqlite")
        subprocess.run([sys.executable, "-m", "open_intelligence", "seed", "--db", db],
                       cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "open_intelligence", "serve", "--db", db, "--port", str(app_port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        browser = None
        cd = None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "local synthetic server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run",
                "--disable-extensions", "--no-default-browser-check",
                "--remote-allow-origins=*", f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={directory}/chrome", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
              start_new_session=True)
            targets = wait_for(
                lambda: json.load(urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=1)),
                "Chrome DevTools target")
            pages = [x for x in targets if x.get("type") == "page"]
            if not pages:
                raise AssertionError("Chrome did not expose a page target")
            cd = ChromeSession(pages[0]["webSocketDebuggerUrl"])
            cd.command("Page.enable")
            cd.command("Runtime.enable")
            cd.command("Page.navigate", {"url": url})

            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                    "Alpha case loaded")
            cd.wait("document.querySelectorAll('#source-list .source-card').length === 2",
                    "two Alpha sources rendered")
            cd.evaluate("document.querySelector('#source-list .source-card button').click()")
            cd.wait("document.querySelector('#source-dialog').open", "original source modal")
            assert "OI-SYNTHETIC-REPORT/1" in cd.evaluate("document.querySelector('#dialog-text').textContent")
            # Escape closes the native dialog without a mouse.
            cd.command("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "Escape", "code": "Escape",
                "windowsVirtualKeyCode": 27,
            })
            cd.command("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "Escape", "code": "Escape",
                "windowsVirtualKeyCode": 27,
            })
            cd.wait("!document.querySelector('#source-dialog').open",
                    "Escape closes the original-source modal")

            # Browser-enforced Tab focus should proceed from case selection into
            # the navigation without disappearing into a dead control.
            cd.evaluate("document.querySelector('#case-picker').focus()")
            cd.command("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "Tab", "code": "Tab",
                "windowsVirtualKeyCode": 9,
            })
            cd.command("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "Tab", "code": "Tab",
                "windowsVirtualKeyCode": 9,
            })
            cd.wait("document.activeElement?.getAttribute('href') === '#overview'",
                    "keyboard Tab reaches first workspace navigation link")
            cd.command("Accessibility.enable")
            nodes = cd.command("Accessibility.getFullAXTree").get("nodes", [])
            names = [(n.get("role", {}).get("value"), n.get("name", {}).get("value", ""))
                     for n in nodes]
            assert any(role == "combobox" and "synthetic case" in name.lower()
                       for role, name in names), "Case selector lacks accessible combobox name"
            assert any(role == "navigation" for role, _ in names), "Navigation landmark not exposed"
            assert any(role == "main" for role, _ in names), "Main landmark not exposed"

            cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Beta'",
                    "Beta case switch")
            cd.wait("document.querySelectorAll('#source-list .source-card').length === 1",
                    "Beta data rendered without Alpha sources")
            cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                    "return to Alpha")

            cd.evaluate("""(() => {
              document.querySelector('#question-text').value = 'Which pathology results need new review?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#question-list .question').length === 1",
                    "persistent question submitted")
            cd.evaluate("""(() => {
              document.querySelector('#draft-summary').value =
                'This fictional case needs a dated review of the currently reported findings.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1",
                    "source-linked draft persisted")

            # A same-case refresh must preserve an unfinished narrative's
            # question and source bindings rather than silently rebinding.
            cd.evaluate("""(() => {
              document.querySelector('#question-text').value =
                'Second synthetic investigation question for binding verification?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#question-list .question').length === 2",
                    "second question stored")
            first_question = json.load(urlopen(
                f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))["questions"][-1]["id"]
            cd.evaluate("""(question => {
              document.querySelector('#question-choice').value = String(question);
              document.querySelector('#draft-summary').value =
                'This unfinished Alpha-only draft must keep the same question and original sources.';
            })(""" + str(first_question) + ")")
            cd.evaluate("""[...document.querySelectorAll('#snapshot-list button')]
              .find(x => x.textContent.includes('Demo review acknowledgment')).click()""")
            cd.wait("document.querySelector('#snapshot-list .pill')?.textContent === 'reviewed_in_demo'",
                    "explicit demo acknowledgment")

            assert cd.evaluate("document.querySelector('#question-choice').value") == str(first_question), (
                "same-case refresh silently changed an unfinished draft's selected question"
            )
            assert "unfinished Alpha-only" in cd.evaluate(
                "document.querySelector('#draft-summary').value"
            ), "same-case refresh discarded the draft narrative"
            cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            assert cd.evaluate("document.querySelector('#case-picker').value") == "CASE-ALPHA", (
                "a case switch silently rebound the unfinished Alpha narrative"
            )
            assert "unfinished Alpha-only" in cd.evaluate(
                "document.querySelector('#draft-summary').value"
            ), "blocked case switch lost the user's narrative"
            cd.evaluate("document.querySelector('#draft-summary').value = ''")
            cd.evaluate("document.querySelector('#example-button').click()")
            cd.wait("document.querySelector('#report-text').value.includes('Amends: PATH-ALPHA@1')",
                    "amendment loaded")
            cd.evaluate("document.querySelector('#import-form').requestSubmit()")
            cd.wait("document.querySelector('#snapshot-list .pill-alert')?.textContent === 'stale'",
                    "source amendment invalidates review snapshot")
            cd.wait("document.querySelectorAll('#source-list .source-card').length === 3",
                    "original and amended source versions retained")

            assert cd.evaluate("""[...document.querySelectorAll('#source-choice input:checked')]
              .some(x => x.closest('label').textContent.includes('STALE'))"""), (
                "source amendment silently rebound the unfinished draft to the replacement version"
            )

            report = json.load(urlopen(f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            assert len(report["snapshots"]) == 1 and report["snapshots"][0]["state"] == "stale"
            assert any(q["state"] == "open" for q in report["questions"])
            snapshot_id = report["snapshots"][0]["id"]
            export_url = f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/export"
            exported = urlopen(export_url).read().decode()
            assert "stale" in exported and "Marker A was not tested" in exported

            cd.command("Emulation.setDeviceMetricsOverride", {
                "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": False,
            })
            cd.wait("window.innerWidth === 390", "mobile viewport")
            overflow = cd.evaluate("""(() => {
              const screenWidth = document.documentElement.clientWidth;
              const outliers = [...document.querySelectorAll('body *')].map(e => ({
                element: e.tagName.toLowerCase(),
                id: e.id || '',
                cls: typeof e.className === 'string' ? e.className : '',
                right: Math.round(e.getBoundingClientRect().right)
              })).filter(e => e.right > screenWidth + 1).slice(0, 12);
              return {inner: window.innerWidth, client: screenWidth,
                      scroll: document.documentElement.scrollWidth, outliers};
            })()""")
            assert overflow["scroll"] <= overflow["inner"] + 1, (
                f"unexpected horizontal overflow on 390px viewport: {overflow}"
            )
            print("PASS: browser source drilldown, keyboard Escape/Tab and AX landmarks, "
                  "case switching, question/draft, review, amendment invalidation, "
                  "original export, 390px responsive layout")
        finally:
            if cd is not None:
                cd.close()
            if browser is not None:
                # Chromium forks renderer/zygote processes which can outlive
                # the browser parent. Stop the entire process group before
                # TemporaryDirectory deletes its active browser profile.
                try:
                    os.killpg(browser.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(browser.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    browser.wait(timeout=5)
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()
