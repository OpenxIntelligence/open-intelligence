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

from browser_journey import ChromeSession, free_port, wait_for, wait_for_browser

ROOT = Path(__file__).resolve().parents[1]


def assert_patient_timeline(session: ChromeSession, app_url: str, case_id: str) -> None:
    """Compare rendered dates to the actual local source ledger, not derived dates."""
    with urlopen(app_url + '/api/cases/' + case_id + '/state', timeout=5) as response:
        state = json.load(response)
    rows = session.evaluate("""[...document.querySelectorAll('#patient-timeline > .question')]
      .map(row => row.textContent)""")
    assert len(rows) == len({source['document_id'] for source in state['sources']})
    for source in state['sources']:
        matches = [text for text in rows if '(' + source['document_id'] + ')' in text]
        assert len(matches) == 1, 'Each report has one event group across versions'
        text = matches[0]
        assert 'Reported event date: ' + source['event_date'] in text
        assert ('Report version ' + str(source['version']) + ' (' + source['state'] + ')' +
                ' · Issued: ' + source['issued_at'] +
                ' · Received by this workspace: ' + source['received_at']) in text
        assert 'was recorded' not in text, 'Event date must not become recording date'


def main() -> None:
    chrome = next((
        path for name in (
            "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"
        ) if (path := shutil.which(name))
    ), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; Patient Mission UI was not verified")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="oi-mission-browser-") as directory, \
            (Path(directory) / "chrome-stderr.log").open("wb") as chrome_stderr:
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
                stderr=chrome_stderr,
                start_new_session=True,
            )
            targets = wait_for_browser(browser, Path(chrome_stderr.name), debug_port)
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
                "!document.querySelector('#patient-uncertainty').textContent.includes('Nothing in this fictional case')"
            )
            assert session.evaluate(
                "document.querySelector('#patient-uncertainty').textContent.includes('not certain yet')"
            )
            assert_patient_timeline(session, url.rstrip('/'), 'CASE-ALPHA')
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
            assert_patient_timeline(session, url.rstrip('/'), 'CASE-BETA')

            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA';
              picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#mission-status')?.textContent === 'Ready to define question'",
                "return to Alpha mission",
            )
            session.evaluate("""(() => {
              document.querySelector('#question-text').value =
                'Which pathology result requires review after a source amendment?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
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
                "document.querySelector('#patient-uncertainty').textContent.includes('1 open source-change review(s)')",
                "patient view preserves unresolved source-change review",
            )
            assert_patient_timeline(session, url.rstrip('/'), 'CASE-ALPHA')
            session.wait(
                "[...document.querySelectorAll('#incoming-list .question')].some(row => "
                "row.textContent.includes('CASE-ALPHA') && row.textContent.includes('Open source-change reviews: 1'))",
                "case list refreshed after amendment",
            )
            session.evaluate("""(() => {
              document.querySelectorAll('#source-choice input').forEach(input => {
                input.checked = !input.closest('label').textContent.includes('Needs review');
              });
              document.querySelectorAll('#evidence-choice input').forEach(input => input.checked = false);
              document.querySelector('#draft-observations').value =
                'Current fictional source versions inspected; no clinical conclusion.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            session.wait(
                "document.querySelector('#snapshot-list .snapshot .pill')?.textContent === 'draft'",
                "replacement draft persisted",
            )
            session.evaluate("""[...document.querySelectorAll('#snapshot-list .snapshot button')]
              .find(button => button.textContent.includes('Demo review acknowledgment')).click()""")
            session.wait(
                "document.querySelector('#review-attention')?.dataset.state === 'no-open-review'",
                "replacement demo acknowledgment clears current review",
            )
            session.wait(
                "document.querySelector('#patient-uncertainty').textContent.includes('0 open source-change review(s)')",
                "patient view does not confuse retained history with unresolved work",
            )
            session.wait(
                "[...document.querySelectorAll('#incoming-list .question')].some(row => "
                "row.textContent.includes('CASE-ALPHA') && row.textContent.includes('Open source-change reviews: 0') "
                "&& row.textContent.includes('Historical stale drafts: 1'))",
                "case list refreshed after acknowledgment without erasing history",
            )
            assert session.evaluate(
                "document.querySelector('#patient-uncertainty').textContent.includes('not clinical sign-off')"
            )
            assert session.evaluate(
                "[...document.querySelectorAll('#snapshot-list .pill')].some(pill => pill.textContent === 'stale')"
            )
            print('PASS: patient/worklist review counts follow amendment and replacement acknowledgment; historical draft retained; event/issue/receipt dates preserved across case switches and amendments')
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


