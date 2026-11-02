"""Real headless Chromium verification of the synthetic Composer lab tool.

Requires Chrome/Chromium. Tests the *actual* Composer control on two synthetic
patients, exact source drilldown, stale fingerprint refusal and refresh.
This is not a clinical workflow or a substitute for independent validation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

from browser_journey import ChromeSession, free_port, wait_for
from open_intelligence.__main__ import seed
from open_intelligence.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]


def report(doc, value, amendment=False):
    lines = [
        "OI-SYNTHETIC-REPORT/1",
        "Patient: CASE-ALPHA",
        f"Document: {doc}",
        "Type: laboratory",
        "Event-Date: " + ("2026-06-01" if doc == "LAB-002" else "2026-05-01"),
        "Issued-At: " + ("2026-06-01" if doc == "LAB-002" else "2026-05-01"),
        "Specimen: BLOOD-ALPHA",
    ]
    if amendment:
        lines.append("Amends: LAB-002@1")
    lines.append("Finding: hemoglobin|reported|OI-LAB-VALUE/1;"
                 f"value={value};unit=g/dL;qc=passed")
    return "\n".join(lines) + "\n"


def main():
    chrome = next((p for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"
    ) if (p := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chromium installation; no Composer lab browser claim")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="oi-lab-composer-") as directory:
        db = str(Path(directory) / "fictional.sqlite")
        seed(db)
        store = CaseStore(db)
        try:
            store.import_report("CASE-ALPHA", report("LAB-001", "10.2").encode())
            store.import_report("CASE-ALPHA", report("LAB-002", "9.8").encode())
            store.add_question("CASE-ALPHA", "Compare fictional laboratory records by actual source")
        finally:
            store.close()
        port, debug_port = free_port(), free_port()
        server = subprocess.Popen([
            sys.executable, "-m", "open_intelligence", "serve",
            "--db", db, "--port", str(port)
        ], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        browser, session = None, None
        try:
            url = f"http://127.0.0.1:{port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200,
                     "synthetic lab server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={directory}/chrome", "about:blank"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
               start_new_session=True)
            targets = wait_for(
                lambda: json.load(urlopen(
                    f"http://127.0.0.1:{debug_port}/json/list", timeout=1)),
                "Chrome DevTools lab tool")
            pages = [x for x in targets if x.get("type") == "page"]
            if not pages:
                raise AssertionError("No Chromium page target")
            session = ChromeSession(pages[0]["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("Page.navigate", {"url": url})
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                "Alpha record loaded")
            session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "document.querySelector('.composer-lab-tool button')?.disabled === false",
                "source-bound fictional laboratory tool control")
            assert session.evaluate(
                "document.querySelector('.composer-lab-tool select').value === 'hemoglobin'")
            token = session.evaluate(
                "document.querySelector('#composer-context-fingerprint').value")
            session.evaluate(
                "document.querySelector('.composer-lab-tool button').click()")
            session.wait(
                "document.querySelector('.composer-lab-result')?.textContent.includes('Numerical difference: -0.4 g/dL')",
                "verified original numeric computation")
            assert session.evaluate(
                "document.querySelector('.composer-lab-result').textContent.includes('not_performed')")
            assert session.evaluate(
                "document.querySelectorAll('.composer-lab-result button').length === 2")
            session.evaluate(
                "document.querySelector('.composer-lab-result button').click()")
            session.wait("document.querySelector('#source-dialog')?.open === true",
                         "lab source anchor opened")
            assert session.evaluate(
                "document.querySelector('#dialog-text mark.source-highlight') !== null")
            session.evaluate("document.querySelector('#dialog-close').click()")

            request = Request(
                url + "api/cases/CASE-ALPHA/imports",
                data=json.dumps({"text": report("LAB-002", "8.5", amendment=True)}).encode(),
                headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=6) as response:
                assert response.status == 200
            # Cached preview must not authorize another calculation.
            assert session.evaluate(
                "document.querySelector('#composer-context-fingerprint').value") == token
            session.evaluate(
                "document.querySelector('.composer-lab-tool button').click()")
            session.wait(
                "document.querySelector('.composer-lab-result')?.textContent.includes('stale Composer context')",
                "stale context denied by backend")
            assert not session.evaluate(
                "document.querySelector('.composer-lab-result').textContent.includes('Numerical difference: -1.7')")
            session.evaluate("document.dispatchEvent(new Event('oi:composer-refresh'))")
            session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "document.querySelector('#composer-context-fingerprint').value !== " +
                json.dumps(token) + " && " +
                "document.querySelector('.composer-lab-tool button')?.disabled === false",
                "new version-bound preview after amendment")
            session.evaluate(
                "document.querySelector('.composer-lab-tool button').click()")
            session.wait(
                "document.querySelector('.composer-lab-result')?.textContent.includes('Numerical difference: -1.7 g/dL')",
                "recalculation after explicit source refresh")

            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Beta'",
                "switch to unrelated fictional case")
            assert not session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('LAB-001')")
            assert not session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('Numerical difference:')")
            print("PASS: Composer lab numeric run, exact source anchor, stale denial, "
                  "refresh and wrong-case UI isolation")
        finally:
            if session is not None:
                session.close()
            if browser is not None:
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
            try:
                os.killpg(server.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(server.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
