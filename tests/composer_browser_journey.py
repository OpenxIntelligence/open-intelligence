"""Real Chromium journey for the EXISTING synthetic investigation + Composer preview.

Tests case isolation, source-bound preview, the original replay save path,
source-linked report preparation, explicit demo review, amendment invalidation
and reassessment. No real patients, model API requests or clinical use.
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

ROOT = Path(__file__).resolve().parents[1]


def main():
    chrome = next((path for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if (path := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; Composer UI not verified")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="oi-composer-browser-") as directory:
        db = str(Path(directory) / "fictional-composer.sqlite")
        subprocess.run([sys.executable, "-m", "open_intelligence",
                        "seed", "--db", db], cwd=ROOT, env=env, check=True,
                       stdout=subprocess.DEVNULL)
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "open_intelligence", "serve",
             "--db", db, "--port", str(app_port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser, session = None, None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200,
                     "local fictional Composer server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={directory}/chrome", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
               start_new_session=True)
            targets = wait_for(
                lambda: json.load(urlopen(
                    f"http://127.0.0.1:{debug_port}/json/list", timeout=1)),
                "Composer Chrome DevTools target")
            pages = [item for item in targets if item.get("type") == "page"]
            if not pages:
                raise AssertionError("No browser page target")
            session = ChromeSession(pages[0]["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("Page.navigate", {"url": url})
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                "Alpha patient context")
            assert session.evaluate(
                "document.querySelector('#model-investigation-run').disabled"), (
                "Composer must be disabled until a question and source preview exist")

            session.evaluate("""(() => {
              document.querySelector('#question-text').value =
                'Which fictional pathology statement requires source review?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "!document.querySelector('#model-investigation-run').disabled",
                "source and patient-world preview")
            assert session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('PATH-ALPHA')")
            assert session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('Live guidelines: unavailable')")
            assert session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('not verified')") or \
                session.evaluate("document.querySelector('#composer-context').textContent.includes('not_verified')")
            assert session.evaluate(
                "!![...document.querySelectorAll('#composer-context button[data-source-id]')]" +
                ".find(b => b.textContent.includes('PATH-ALPHA'))"), (
                "Source preview must open original source by exact identity and line")
            session.evaluate(
                "[...document.querySelectorAll('#composer-context button[data-source-id]')]" +
                ".find(b => b.textContent.includes('PATH-ALPHA')).click()")
            session.wait("document.querySelector('#source-dialog')?.open === true",
                         "Composer opened original source dialog")
            assert session.evaluate(
                "document.querySelector('#dialog-title').textContent.includes('PATH-ALPHA@1')")
            assert session.evaluate(
                "document.querySelector('#dialog-text mark.source-highlight') !== null")
            session.evaluate("document.querySelector('#dialog-close').click()")
            assert session.evaluate(
                "document.querySelector('#source-dialog')?.open === false")
            assert session.evaluate(
                "document.querySelector('#model-investigation-mode').value === 'replay'")
            session.evaluate(
                "document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait(
                "document.querySelectorAll('#model-investigation-list .snapshot').length === 1",
                "original recorded replay persisted")
            assert session.evaluate(
                "document.querySelector('#model-investigation-list').textContent.includes('Review: pending')")
            original_state = json.load(urlopen(url + "api/cases/CASE-ALPHA/state"))
            assert original_state["questions"][0]["state"] == "open", (
                "Model generation must not acknowledge human review")
            session.evaluate("""[...document.querySelectorAll('#model-investigation-list button')]
              .find(button => button.textContent === 'Prepare review draft').click()""")
            session.wait(
                "document.querySelectorAll('#snapshot-list .snapshot').length === 1 && " +
                "document.querySelector('#snapshot-list .pill')?.textContent === 'draft'",
                "model run prepared as source-linked review draft")
            prepared_state = json.load(urlopen(url + "api/cases/CASE-ALPHA/state"))
            historical_snapshot = prepared_state["snapshots"][0]
            original_report = historical_snapshot["summary"]
            assert prepared_state["questions"][0]["state"] == "open"
            assert historical_snapshot["investigation_origin"]["mode"] == "replay"
            assert "recorded-replay" in original_report
            assert historical_snapshot["investigation_origin"]["citations"]
            session.wait(
                "document.querySelector('#model-investigation-list').textContent.includes('Review draft #')",
                "model run links to the existing report")
            session.evaluate("""[...document.querySelectorAll('#snapshot-list button')]
              .find(button => button.textContent === 'Demo review acknowledgment').click()""")
            session.wait(
                "document.querySelector('#snapshot-list .pill')?.textContent === 'reviewed_in_demo'",
                "explicit human demonstration acknowledgment")
            reviewed_state = json.load(urlopen(url + "api/cases/CASE-ALPHA/state"))
            assert reviewed_state["questions"][0]["state"] == "addressed"
            assert reviewed_state["snapshots"][0]["summary"] == original_report
            alpha_token = session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "!document.querySelector('#model-investigation-run').disabled",
                "new preview after existing investigation")
            # Fetch returned token by CDP, not by interpreting UI as authority.
            alpha_hash = session.evaluate(
                "document.querySelector('#composer-context-fingerprint').value")
            assert len(alpha_hash) == 64

            # A source can change out of band while the form still shows an
            # earlier preview. The server must refuse the pending submission.
            mutation = Request(
                url + "api/cases/CASE-ALPHA/imports",
                data=json.dumps({
                    "text": (ROOT / "examples" / "synthetic" /
                             "alpha-pathology-amended.txt").read_text()
                }).encode(), headers={"Content-Type": "application/json"})
            with urlopen(mutation, timeout=5) as resp:
                assert resp.status == 200
            assert session.evaluate(
                "document.querySelector('#composer-context-fingerprint').value") == alpha_hash
            session.evaluate(
                "document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait(
                "document.querySelector('#notice')?.textContent.includes('stale Composer context')",
                "stale historical source rejected")
            assert session.evaluate(
                "document.querySelectorAll('#model-investigation-list .snapshot').length === 1"), (
                "stale Composer context saved a second result")
            session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "document.querySelector('#composer-context-fingerprint').value !== " +
                json.dumps(alpha_hash),
                "automatic source-context refresh after amendment rejection")
            assert session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('PATH-ALPHA@2')")
            session.wait(
                "document.querySelector('#snapshot-list .pill')?.textContent === 'stale'",
                "source amendment invalidates the prepared and reviewed report")
            stale_state = json.load(urlopen(url + "api/cases/CASE-ALPHA/state"))
            assert stale_state["snapshots"][0]["summary"] == original_report
            assert stale_state["questions"][0]["state"] == "open"
            session.wait(
                "document.querySelector('#changes-stale')?.textContent.includes('Investigation')",
                "what-changed projection explains stale report")

            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Beta'",
                "switch to different patient")
            assert session.evaluate(
                "document.querySelector('#model-investigation-run').disabled"), (
                "Patient switch did not invalidate the previous context")
            assert not session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('PATH-ALPHA')"), (
                "Alpha source leaked into Beta context")
            session.evaluate("""(() => {
              document.querySelector('#question-text').value =
                'What can the Beta synthetic source actually establish?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "!document.querySelector('#model-investigation-run').disabled",
                "Beta scoped preview")
            assert session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('CASE-BETA')")
            assert not session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('PATH-ALPHA')"), (
                "Beta context incorporated Alpha source")

            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                "return to Alpha chart")
            session.wait(
                "document.querySelector('#composer-context-fingerprint')?.value.length === 64 && " +
                "!document.querySelector('#model-investigation-run').disabled",
                "refreshed Alpha context")
            assert session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('PATH-ALPHA@2')")
            assert session.evaluate(
                "document.querySelector('#composer-context-fingerprint').value") != alpha_hash
            session.evaluate(
                "document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait(
                "document.querySelectorAll('#model-investigation-list .snapshot').length === 2",
                "explicit reassessment creates a new model run")
            session.evaluate("""[...document.querySelectorAll('#model-investigation-list button')]
              .find(button => button.textContent === 'Prepare review draft').click()""")
            session.wait(
                "document.querySelectorAll('#snapshot-list .snapshot').length === 2",
                "reassessment creates a distinct report without replacing history")
            reassessed_state = json.load(urlopen(url + "api/cases/CASE-ALPHA/state"))
            old_report = next(item for item in reassessed_state["snapshots"]
                              if item["id"] == historical_snapshot["id"])
            new_report = next(item for item in reassessed_state["snapshots"]
                              if item["id"] != historical_snapshot["id"])
            assert old_report["state"] == "stale"
            assert old_report["summary"] == original_report
            assert new_report["state"] == "draft"
            assert new_report["investigation_origin"]["investigation_id"] != \
                old_report["investigation_origin"]["investigation_id"]
            assert new_report["source_ids"] != old_report["source_ids"]
            with urlopen(url + f"api/cases/CASE-ALPHA/snapshots/{old_report['id']}/export") as exported:
                assert "PATH-ALPHA@1" in exported.read().decode("utf-8")
            print("PASS: source-bound Composer, replay, report preparation, explicit demo review, "
                  "stale denial, patient isolation, amendment and versioned reassessment")
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
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()
