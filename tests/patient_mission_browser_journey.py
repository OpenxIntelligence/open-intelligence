"""Headless browser journey for the synthetic-only Patient Mission panel."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from browser_journey import ChromeSession, free_port, wait_for

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    chrome = next((
        path for name in (
            "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"
        ) if (path := shutil.which(name))
    ), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; Patient Mission UI was not verified")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="oi-mission-browser-") as directory:
        db = str(Path(directory) / "mission.sqlite")
        subprocess.run(
            [sys.executable, "-m", "open_intelligence", "seed", "--db", db],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "open_intelligence",
                "serve",
                "--db",
                db,
                "--port",
                str(app_port),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        browser = None
        session = None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "local mission server")
            browser = subprocess.Popen(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                    "--no-first-run",
                    "--disable-extensions",
                    "--no-default-browser-check",
                    "--remote-allow-origins=*",
                    f"--remote-debugging-port={debug_port}",
                    f"--user-data-dir={directory}/chrome",
                    "about:blank",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            targets = wait_for(
                lambda: json.load(urlopen(
                    f"http://127.0.0.1:{debug_port}/json/list", timeout=1
                )),
                "Chrome DevTools target",
            )
            pages = [item for item in targets if item.get("type") == "page"]
            if not pages:
                raise AssertionError("Chrome did not expose a page target")
            session = ChromeSession(pages[0]["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("Page.navigate", {"url": url})

            session.wait(
                "document.querySelector('#mission-status')?.textContent === 'Ready to define question'",
                "Alpha mission status",
            )
            session.wait(
                "document.querySelectorAll('#mission-known .finding').length === 5",
                "Alpha mission statements",
            )
            assert session.evaluate(
                "document.querySelector('#mission-known').textContent.includes('Marker A was not tested')"
            )
            assert session.evaluate(
                "document.querySelector('#patient-mission').textContent.includes('Not a diagnosis or treatment recommendation')"
            )

            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Beta'",
                "Beta case switch",
            )
            session.wait(
                "document.querySelectorAll('#mission-known .finding').length === 2",
                "Beta mission statements",
            )
            assert not session.evaluate(
                "document.querySelector('#mission-known').textContent.includes('Marker A was not tested')"
            ), "Alpha statement leaked into Beta Patient Mission panel"
            assert session.evaluate(
                "document.querySelector('#mission-known').textContent.includes('not assessed for this sample')"
            )

            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#mission-status')?.textContent === 'Ready to define question'",
                "return to Alpha mission",
            )
            # First-party source → question UI: no invented diagnosis, no
            # implicit persistence, and no second question/record ledger.
            session.evaluate("""document.querySelector('#world-model-detail').open = true""")
            session.wait(
                "document.querySelector('#world-model-observations li button') !== null",
                "current source-backed World Model loaded",
            )
            session.evaluate("""document.querySelector('#world-model-observations li button').click()""")
            assert session.evaluate(
                "document.querySelector('#question-text').value.includes('source line')"
            ), "source reference did not reach the existing question form"
            assert session.evaluate(
                "location.hash === '#investigations'"
            ), "source handoff did not navigate to the investigation workflow"
            assert session.evaluate(
                "document.querySelectorAll('#question-list .question').length === 0"
            ), "source handoff must not silently persist the question"
            session.evaluate("document.querySelector('#question-form').requestSubmit()")
            session.wait(
                "document.querySelectorAll('#question-list .question').length === 1",
                "mission question persisted",
            )
            session.evaluate("""(() => {
              document.querySelector('#draft-observations').value =
                'Synthetic observation recorded for the mission draft journey.';
              document.querySelector('#draft-summary').value =
                'This synthetic investigation records the source state before an amendment.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            session.wait(
                "document.querySelectorAll('#snapshot-list .snapshot').length === 1",
                "mission draft persisted",
            )
            session.evaluate("""[...document.querySelectorAll('#snapshot-list button')]
              .find(button => button.textContent.includes('Demo review acknowledgment')).click()""")
            session.wait(
                "document.querySelector('#snapshot-list .pill')?.textContent === 'reviewed_in_demo'",
                "mission draft acknowledged in demo",
            )
            session.evaluate("document.querySelector('#example-button').click()")
            session.wait(
                "document.querySelector('#report-text').value.includes('Amends: PATH-ALPHA@1')",
                "amendment loaded",
            )
            session.evaluate("document.querySelector('#import-form').requestSubmit()")
            session.wait(
                "document.querySelector('#snapshot-list .pill-alert')?.textContent === 'stale'",
                "amendment invalidated investigation",
            )
            session.wait(
                "document.querySelector('#mission-status')?.textContent === 'Review required'",
                "mission panel reflects review requirement",
            )
            session.wait(
                "document.querySelector('#mission-changes').textContent.includes('PATH-ALPHA@2')",
                "mission panel reflects material amendment",
            )
            assert session.evaluate(
                "document.querySelector('#mission-actions').textContent.includes('Reconcile source changes')"
            )
            session.wait(
                "document.querySelector('#world-model-history').textContent.includes('PATH-ALPHA')",
                "World Model retains original source after amendment",
            )
            assert session.evaluate(
                "document.querySelector('#world-model-history').textContent.includes('Stale snapshots:')"
            ), "amendment review state did not reach the source inspector"
        finally:
            if session is not None:
                session.close()
            if browser is not None:
                # Chromium forks renderer/zygote processes which can outlive
                # the browser parent. Stop the entire process group before
                # TemporaryDirectory deletes its active browser profile,
                # or teardown races Chrome shutdown and fails the journey
                # after every assertion passed (seen 3x in CI).
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
