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
            cd.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 960, "deviceScaleFactor": 1, "mobile": False,
            })
            cd.command("Page.navigate", {"url": url})

            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                    "Alpha case loaded")
            cd.wait("document.querySelectorAll('#source-list .source-card').length === 2",
                    "two Alpha sources rendered")
            assert cd.evaluate("document.querySelector('#investigations .panel-head').textContent.includes('Human-authored, no AI call')"), (
                "the investigation draft must disclose that it is human-authored"
            )
            cd.wait("document.querySelector('#workspace-nav a[aria-current=location]')?.getAttribute('href') === '#overview'",
                    "current workspace section is announced")
            assert cd.evaluate("document.querySelector('.section-menu')?.open === true"), (
                "desktop section navigation should be expanded"
            )
            assert cd.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
                "desktop viewport has unexpected horizontal overflow"
            )

            # Chronology is derived entirely from existing source event dates
            # rather than invented diagnosis/progression assertions.
            cd.wait("document.querySelectorAll('#timeline-events .timeline-entry').length === 2",
                    "two chronological Alpha source events")
            assert cd.evaluate("document.querySelector('#timeline-events .timeline-entry .timeline-doc').textContent") == "IMG-ALPHA"
            assert cd.evaluate("""[...document.querySelectorAll('#timeline-events time')]
              .map(x => x.dateTime).join(',')""") == "2026-05-17,2026-05-03"
            cd.evaluate("""(() => {
              const filter = document.querySelector('#timeline-filter');
              filter.value = 'pathology'; filter.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelectorAll('#timeline-events .timeline-entry').length === 1",
                    "source timeline pathology filter")
            assert cd.evaluate("document.querySelector('#timeline-events .timeline-entry').textContent.includes('PATH-ALPHA')")
            cd.evaluate("""(() => {
              const filter = document.querySelector('#timeline-filter');
              filter.value = 'molecular'; filter.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelector('#timeline-events').textContent.includes('No source events')",
                    "no invented molecular events")
            cd.evaluate("""(() => {
              const filter = document.querySelector('#timeline-filter');
              filter.value = 'all'; filter.dispatchEvent(new Event('change'));
            })()""")

            # Claim → exact source-line requires one action, and the report
            # remains literal text with no markup execution.
            cd.wait("document.querySelectorAll('#assertion-list .source-jump').length >= 1",
                    "source-linked claim actions")
            assert "No amended report" in cd.evaluate(
                "document.querySelector('#source-change-list').textContent"), (
                "unamended sources were presented as revisions"
            )
            cd.evaluate("document.querySelector('#assertion-list .source-jump').click()")
            cd.wait("document.querySelector('#source-dialog').open && !!document.querySelector('#dialog-text mark.source-highlight')",
                    "exact line highlighted in original source")
            assert "Finding:" in cd.evaluate(
                "document.querySelector('#dialog-text mark.source-highlight').textContent"), (
                "highlighted source line does not match a finding"
            )
            assert "highlighted original line" in cd.evaluate(
                "document.querySelector('#dialog-context').textContent")
            assert not cd.evaluate("document.querySelector('#dialog-text script')"), (
                "source material became active HTML"
            )
            cd.evaluate("document.querySelector('#dialog-close').click()")
            cd.wait("!document.querySelector('#source-dialog').open", "anchored source modal closes")

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
            assert cd.evaluate("document.querySelector('#workspace-nav a[aria-current=location]')?.getAttribute('href')") == "#overview", (
                "Current section is not exposed in workspace navigation"
            )
            for group_name in (
                "Source versions",
                "Evidence assessments",
            ):
                assert any(role == "group" and name == group_name for role, name in names), (
                    f"Checkbox group lacks an accessible name: {group_name}"
                )

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
              document.querySelector('#draft-observations').value = '          ';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            cd.wait("document.querySelector('#notice').textContent.includes('Add reported observations')",
                    "whitespace-only observations are rejected")
            assert cd.evaluate("document.querySelectorAll('#snapshot-list .snapshot').length") == 0, (
                "whitespace-only observations created a draft"
            )
            cd.evaluate("""(() => {
              document.querySelector('#draft-observations').value =
                'PATH-ALPHA reports classification pending external review; IMG-ALPHA reports a 31 mm measurement.';
              document.querySelector('#draft-summary').value =
                'No hypothesis is proposed from the current source set.';
              document.querySelector('#draft-assumptions').value =
                'Prior images are unavailable; classification awaits external review.';
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
              document.querySelector('#draft-observations').value =
                'The selected source versions are retained for this unfinished draft.';
              document.querySelector('#draft-summary').value =
                'This unfinished Alpha-only draft must keep the same question and original sources.';
              document.querySelector('#draft-assumptions').value =
                'This draft must remain bound to CASE-ALPHA.';
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
            assert "selected source versions" in cd.evaluate(
                "document.querySelector('#draft-observations').value"
            ), "same-case refresh discarded reported observations"
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
            assert "remain bound" in cd.evaluate(
                "document.querySelector('#draft-assumptions').value"
            ), "blocked case switch lost the draft's stated assumptions"
            cd.evaluate("""['draft-observations', 'draft-summary', 'draft-assumptions']
              .forEach(id => document.querySelector('#' + id).value = '')""")
            cd.evaluate("document.querySelector('#example-button').click()")
            cd.wait("document.querySelector('#report-text').value.includes('Amends: PATH-ALPHA@1')",
                    "amendment loaded")
            cd.evaluate("document.querySelector('#import-form').requestSubmit()")
            cd.wait("document.querySelector('#snapshot-list .pill-alert')?.textContent === 'stale'",
                    "source amendment invalidates review snapshot")
            cd.wait("document.querySelector('#review-attention')?.dataset.state === 'needs-review'",
                    "amendment surfaces unresolved review attention")
            assert "reopened question(s)" in cd.evaluate(
                "document.querySelector('#review-attention-summary').textContent")
            cd.wait("document.querySelectorAll('#source-change-list .change-card').length === 1",
                    "source amendment appears in change explorer")
            assert "version 1 → 2" in cd.evaluate(
                "document.querySelector('#source-change-list').textContent")
            assert "saved investigation(s)" in cd.evaluate(
                "document.querySelector('#source-change-list').textContent")
            cd.evaluate("document.querySelector('#source-change-list .change-card button').click()")
            cd.wait("document.querySelector('#compare-dialog').open", "read-only source comparison opens")
            previous_text = cd.evaluate("document.querySelector('#compare-before').textContent")
            amended_text = cd.evaluate("document.querySelector('#compare-after').textContent")
            assert "OI-SYNTHETIC-REPORT/1" in previous_text and "OI-SYNTHETIC-REPORT/1" in amended_text
            assert previous_text != amended_text, "amendment comparison lost original version difference"
            assert "PATH-ALPHA" in cd.evaluate("document.querySelector('#compare-title').textContent")
            assert "no clinical or treatment determination" in cd.evaluate(
                "document.querySelector('#compare-context').textContent")
            cd.evaluate("document.querySelector('#compare-close').click()")
            cd.wait("!document.querySelector('#compare-dialog').open",
                    "source comparison closes without losing the current case")
            cd.wait("document.querySelectorAll('#source-list .source-card').length === 3",
                    "original and amended source versions retained")


            # Two versions of the same pathology document refer to one
            # original specimen event, with separate original/amended sources.
            cd.wait("document.querySelectorAll('#timeline-events .timeline-entry').length === 2",
                    "amendment retains same source event grouping")
            assert cd.evaluate("""[...document.querySelectorAll('#timeline-events .timeline-entry')]
              .find(e => e.querySelector('.timeline-doc')?.textContent === 'PATH-ALPHA')
              ?.querySelectorAll('button').length""") == 2
            assert cd.evaluate("""[...document.querySelectorAll('#timeline-events .timeline-entry')]
              .find(e => e.querySelector('.timeline-doc')?.textContent === 'PATH-ALPHA')
              ?.textContent.includes('2 report versions')""")
            cd.evaluate("""[...document.querySelectorAll('#timeline-events .timeline-entry')]
              .find(e => e.querySelector('.timeline-doc')?.textContent === 'PATH-ALPHA')
              ?.querySelector('button').click()""")
            cd.wait("document.querySelector('#source-dialog').open", "original pathology accessible from timeline")
            assert cd.evaluate("document.querySelector('#dialog-title').textContent.includes('PATH-ALPHA@1')")
            cd.evaluate("document.querySelector('#dialog-close').click()")

            assert cd.evaluate("""[...document.querySelectorAll('#source-choice input:checked')]
              .some(x => x.closest('label').textContent.includes('Needs review'))"""), (
                "source amendment silently rebound the unfinished draft to the replacement version"
            )
            # Explicit operator reconciliation before creating the evidence-linked draft.
            cd.evaluate("""[...document.querySelectorAll('#source-choice input')]
              .forEach(x => { x.checked = !x.closest('label').textContent.includes('Needs review'); })""")

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
            cd.wait("document.querySelector('.section-menu')?.open === false",
                    "responsive workspace navigation collapsed")
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

            # The research layer is synthetic only: register a fictional
            # source, review its exact content, assess it against this case's
            # question, and attach that assessment to a new dated draft.
            cd.evaluate("document.querySelector('#example-evidence-button').click()")
            cd.wait("document.querySelector('#evidence-text').value.includes('OI-SYNTHETIC-EVIDENCE/1')",
                    "fictional evidence example loaded")
            cd.evaluate("document.querySelector('#evidence-import-form').requestSubmit()")
            cd.wait("document.querySelectorAll('#evidence-list .source-card').length === 1",
                    "fictional evidence persisted in UI")
            cd.evaluate("document.querySelector('#evidence-list .source-card button').click()")
            cd.wait("document.querySelector('#source-dialog').open", "evidence original source dialog")
            assert "original-synthetic" in cd.evaluate("document.querySelector('#dialog-text').textContent")
            cd.evaluate("document.querySelector('#dialog-close').click()")

            # Two distinct current evidence sources make selection integrity
            # observable: a refresh must not silently change a written
            # withdrawal reason's target to the first option.
            cd.evaluate("document.querySelector('#example-evidence-button').click()")
            cd.wait("document.querySelector('#evidence-text').value.includes('EVID-ASSAY')",
                    "second synthetic evidence template")
            cd.evaluate("""(() => {
              const input = document.querySelector('#evidence-text');
              input.value = input.value.replace('Evidence: EVID-ASSAY', 'Evidence: EVID-SECOND')
                .replace('Title: Fictional assay methods example', 'Title: Fictional second-source example');
              document.querySelector('#evidence-import-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#evidence-list .source-card').length === 2",
                    "two distinct synthetic evidence versions registered")
            evidence_state = json.load(urlopen(
                f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            second_id = next(x["id"] for x in evidence_state["evidence"]
                             if x["evidence_key"] == "EVID-SECOND")
            cd.evaluate("""(target => {
              document.querySelector('#evidence-withdraw-id').value = String(target);
              document.querySelector('#evidence-withdraw-reason').value =
                'This second fictional item is only a target-selection regression fixture.';
              document.querySelector('#question-text').value =
                'Third synthetic question to trigger an evidence-selector refresh?';
              document.querySelector('#question-form').requestSubmit();
            })(""" + str(second_id) + ")")
            cd.wait("document.querySelectorAll('#question-list .question').length === 3",
                    "state refresh after selecting second evidence withdrawal")
            assert cd.evaluate("document.querySelector('#evidence-withdraw-id').value") == str(second_id), (
                "withdrawal refresh changed the target under an unfinished reason"
            )
            assert "second fictional item" in cd.evaluate(
                "document.querySelector('#evidence-withdraw-reason').value"
            ), "withdrawal refresh lost the authored reason"
            cd.evaluate("document.querySelector('#evidence-withdraw-reason').value = ''")

            cd.evaluate("""(() => {
              document.querySelector('#evidence-rationale').value =
                'This is independently authored fictional context, not an appraisal of an actual study.';
              document.querySelector('#evidence-assessment-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#evidence-assessment-list .finding').length === 1",
                    "question-specific fictional assessment persisted")
            cd.evaluate("""(() => {
              document.querySelector('#evidence-choice input').checked = true;
              document.querySelector('#draft-observations').value =
                'The fictional source states a bounded research claim.';
              document.querySelector('#draft-summary').value =
                'No patient-specific conclusion is drawn.';
              document.querySelector('#draft-assumptions').value =
                'The relationship and applicability labels are human-authored and unverified.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 2",
                    "draft with fictional evidence attached")
            state = json.load(urlopen(f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            latest = state["snapshots"][0]
            assert latest["state"] == "draft" and len(latest["evidence_assessment_ids"]) == 1
            assert "Reported observations:" in latest["summary"]
            assert "Working hypothesis or mechanism:" in latest["summary"]
            assert "Assumptions, contradictions, and gaps:" in latest["summary"]
            evidence_version_id = state["evidence"][0]["id"]

            # Withdrawal must not silently keep that draft current.
            cd.evaluate("""(evidenceId => {
              document.querySelector('#evidence-withdraw-id').value = evidenceId;
              document.querySelector('#evidence-withdraw-reason').value =
                'Original fictional evidence retired to test dependency invalidation.';
              document.querySelector('#evidence-withdraw-form').requestSubmit();
            })(""" + str(evidence_version_id) + ")")
            cd.wait("document.querySelectorAll('#snapshot-list .snapshot .pill-alert').length >= 2",
                    "withdrawal invalidates dependent fictional draft")
            state = json.load(urlopen(f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            latest = next(x for x in state["snapshots"] if x["id"] == latest["id"])
            assert latest["state"] == "stale"
            assert state["evidence"][0]["state"] == "withdrawn"
            assert state["evidence_changes"][0]["kind"] == "withdrawn"
            assert cd.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
                "evidence controls overflow the 390px synthetic demo viewport"
            )


            # Bibliography view is publicly sourced, not case-linked: its
            # offline synthetic metadata must never surface copyrighted
            # abstract canaries or enable live egress by default.
            cd.wait("document.querySelector('#bibliography-live-button').disabled",
                    "live DOI lookup disabled in default server mode")
            cd.evaluate("document.querySelector('#bibliography-example-button').click()")
            cd.wait("document.querySelector('#bibliography-result .source-card strong')?.textContent.includes('fictional bibliographic')",
                    "offline Crossref-format metadata example")
            assert not cd.evaluate("document.querySelector('#bibliography-result').textContent.includes('COPYRIGHTED ABSTRACT')")
            assert cd.evaluate("document.querySelector('#bibliography-result').textContent.includes('No abstract')")


            # A historical stale snapshot must remain inspectable after the
            # corresponding reopened question receives a NEW demo acknowledgment.
            # The current-attention counter then clears, without deleting history.
            state = json.load(urlopen(f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            stale_ids = {snapshot["id"] for snapshot in state["snapshots"]
                         if snapshot["state"] == "stale"}
            reopened_ids = sorted({snapshot["question_id"] for snapshot in state["snapshots"]
                                   if snapshot["state"] == "stale" and
                                   any(q["id"] == snapshot["question_id"] and q["state"] == "open"
                                       for q in state["questions"])})
            assert stale_ids and reopened_ids, "missing synthetic stale review fixture"
            for qid in reopened_ids:
                cd.evaluate("""(qid => {
                  const selectedQuestion = document.querySelector('#question-choice');
                  selectedQuestion.value = String(qid);
                  selectedQuestion.dispatchEvent(new Event('change'));
                  document.querySelectorAll('#source-choice input').forEach(input => {
                    input.checked = !input.closest('label').textContent.includes('Needs review');
                  });
                  document.querySelectorAll('#evidence-choice input').forEach(input => input.checked = false);
                  document.querySelector('#draft-observations').value =
                    'Current synthetic source versions have been re-inspected; no clinical conclusion is drawn.';
                  document.querySelector('#draft-summary').value = '';
                  document.querySelector('#draft-assumptions').value =
                    'Earlier investigation remains historical and the amended report needs reviewer interpretation.';
                  document.querySelector('#draft-form').requestSubmit();
                })(""" + str(qid) + ")")
                cd.wait("document.querySelector('#snapshot-list .snapshot .pill')?.textContent === 'draft'",
                        "new source-scoped draft saved")
                cd.evaluate("""[...document.querySelector('#snapshot-list .snapshot').querySelectorAll('button')]
                  .find(button => button.textContent.includes('Demo review acknowledgment')).click()""")
                cd.wait("document.querySelector('#snapshot-list .snapshot .pill')?.textContent === 'reviewed_in_demo'",
                        "replacement demo acknowledgment persisted")
            cd.wait("document.querySelector('#review-attention')?.dataset.state === 'no-open-review'",
                    "review attention must clear after replacement acknowledgment")
            assert "No unresolved source-change review" in cd.evaluate(
                "document.querySelector('#review-attention-summary').textContent")
            assert cd.evaluate("""[...document.querySelectorAll('#metrics .metric')]
              .some(item => item.textContent.includes('Review required') &&
                 item.querySelector('.number')?.textContent === '0')"""), (
                "historical stale snapshots were mistakenly counted as unresolved work"
            )
            state = json.load(urlopen(f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            assert stale_ids.issubset({snapshot["id"] for snapshot in state["snapshots"]
                                      if snapshot["state"] == "stale"}), (
                "review resolution erased historical source-dependent snapshots"
            )
            assert cd.evaluate("document.querySelectorAll('#source-change-list .change-card').length") == 1, (
                "review resolution erased document-version history"
            )

            # Issue #3 rejection paths, exercised through the browser rather
            # than only at the store layer: a byte-identical re-import and a
            # wrong-patient import must both be refused without new facts.
            cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                    "return to Alpha for rejection checks")
            cards_before = cd.evaluate("document.querySelectorAll('#source-list .source-card').length")
            state_before = json.load(urlopen(
                f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            original_id = next(x["id"] for x in state_before["sources"]
                               if x["document_id"] == "PATH-ALPHA" and x["version"] == 1)
            cd.evaluate("""(async (sourceId) => {
              const text = (await (await fetch('/api/cases/CASE-ALPHA/sources/' + sourceId)).json()).text;
              document.querySelector('#report-text').value = text;
              document.querySelector('#import-form').requestSubmit();
            })(""" + str(original_id) + ")")
            cd.wait("document.querySelector('#notice')?.textContent.includes('Import: duplicate')",
                    "duplicate import refused in browser")
            assert cd.evaluate("document.querySelectorAll('#source-list .source-card').length") == cards_before, (
                "duplicate import added a source card"
            )
            state_after_dup = json.load(urlopen(
                f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            assert len(state_after_dup["sources"]) == len(state_before["sources"]), (
                "duplicate import added a source version"
            )

            cd.evaluate("""(async () => {
              const text = (await (await fetch('/api/examples/wrong-patient')).json()).text;
              document.querySelector('#report-text').value = text;
              document.querySelector('#import-form').requestSubmit();
            })()""")
            cd.wait("document.querySelector('#notice')?.textContent.includes('Import: quarantined')",
                    "wrong-patient import quarantined in browser")
            cd.wait("document.querySelectorAll('#quarantine-list .quarantine').length === 1",
                    "quarantine receipt rendered")
            assert "CASE-BETA" in cd.evaluate("document.querySelector('#quarantine-list').textContent"), (
                "quarantine receipt hides the declared patient"
            )
            assert cd.evaluate("document.querySelectorAll('#source-list .source-card').length") == cards_before, (
                "wrong-patient import added a source card"
            )
            # A repeated wrong-patient delivery keeps one receipt, not two.
            cd.evaluate("""(async () => {
              const text = (await (await fetch('/api/examples/wrong-patient')).json()).text;
              document.querySelector('#report-text').value = text;
              document.querySelector('#import-form').requestSubmit();
            })()""")
            cd.wait("document.querySelector('#notice')?.textContent.includes('Import: quarantined')",
                    "repeated wrong-patient import quarantined in browser")
            assert cd.evaluate("document.querySelectorAll('#quarantine-list .quarantine').length") == 1, (
                "repeated wrong-patient delivery duplicated the quarantine receipt"
            )
            state_after_q = json.load(urlopen(
                f"http://127.0.0.1:{app_port}/api/cases/CASE-ALPHA/state"))
            assert len(state_after_q["quarantines"]) == 1, (
                "repeated wrong-patient delivery duplicated quarantine state"
            )
            assert len(state_after_q["sources"]) == len(state_before["sources"]), (
                "wrong-patient import added a source version"
            )

            print("PASS: browser source drilldown, source comparison, review-attention resolution, "
                  "keyboard Escape/Tab and AX landmarks, "
                  "case switching, question/draft, review, amendment invalidation, "
                  "original export, source-derived timeline, fictional evidence lifecycle, offline bibliography, 390px responsive layout, "
                  "browser duplicate and wrong-patient rejection")
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
