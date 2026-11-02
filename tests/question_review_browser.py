"""Source-to-review navigation through the actual existing synthetic workspace."""
from __future__ import annotations

import base64
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # the app imports its existing root tools package

from browser_journey import ChromeSession, free_port, wait_for
from open_intelligence.__main__ import Handler, seed


def main() -> None:
    chrome = next((shutil.which(n) for n in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(n)), None)
    if not chrome:
        raise AssertionError('Chromium unavailable; question-review browser flow NOT verified')
    with tempfile.TemporaryDirectory(prefix='oi-question-review-') as directory:
        db = str(Path(directory) / 'case.sqlite')
        seed(db)
        server = ThreadingHTTPServer(('127.0.0.1', 0), type('ReviewHandler', (Handler,), {'db_path': db}))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        port = free_port()
        browser = subprocess.Popen([chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
            '--disable-dev-shm-usage', '--disable-background-networking', '--no-first-run',
            '--remote-allow-origins=*', '--window-size=1440,1000',
            f'--remote-debugging-port={port}', f'--user-data-dir={directory}/chrome', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        session = None
        try:
            pages = wait_for(lambda: json.load(urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1)), 'Chromium page')
            page = next(p for p in pages if p.get('type') == 'page')
            session = ChromeSession(page['webSocketDebuggerUrl'])
            session.command('Page.enable')
            session.command('Runtime.enable')
            navigation = session.command('Page.navigate', {'url': f'http://127.0.0.1:{server.server_port}/'})
            if navigation.get('errorText'):
                raise AssertionError('Browser navigation failed: ' + navigation['errorText'])
            session.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'", 'loaded case')
            session.wait("document.querySelector('#review-question-list')?.textContent.includes('does not establish')", 'honest empty state')
            session.evaluate("""(() => {
              document.querySelector('#question-text').value = 'Which fictional report needs reconciliation?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            session.wait("document.querySelectorAll('#question-choice option').length === 1", 'question saved')
            session.evaluate("""(() => {
              document.querySelector('#draft-observations').value = 'Fictional initial source state; no clinical conclusion.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1", 'original draft')
            session.evaluate("document.querySelector('#example-button').click()")
            session.wait("document.querySelector('#report-text').value.includes('Amends: PATH-ALPHA@1')", 'amendment loaded')
            session.evaluate("document.querySelector('#import-form').requestSubmit()")
            session.wait("document.querySelectorAll('#review-question-list .review-question').length === 1", 'question review row')
            session.evaluate("""[...document.querySelectorAll('#review-question-list button')]
              .find(b => b.textContent.startsWith('Compare')).click()""")
            session.wait("document.querySelector('#compare-dialog').open", 'comparison from overview')
            assert session.evaluate("document.querySelector('#compare-before-title').textContent.includes('PATH-ALPHA@1')")
            assert session.evaluate("document.querySelector('#compare-after-title').textContent.includes('PATH-ALPHA@2')")
            session.evaluate("document.querySelector('#compare-close').click()")
            session.evaluate("""[...document.querySelectorAll('#review-question-list button')]
              .find(b => b.textContent.startsWith('Open')).click()""")
            session.wait("document.querySelector('#source-dialog').open", 'original source from overview')
            assert session.evaluate("document.querySelector('#dialog-text').textContent.includes('Marker A was not tested')")
            session.evaluate("document.querySelector('#dialog-close').click()")
            session.evaluate("""(() => {
              document.querySelector('#question-text').value = 'Another fictional question with unfinished work.';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            session.wait("document.querySelectorAll('#question-choice option').length === 2", 'second question')
            session.evaluate("""(() => {
              const select = document.querySelector('#question-choice');
              select.value = '2'; select.dispatchEvent(new Event('change'));
              document.querySelector('#draft-observations').value = 'Preserve this unfinished narrative.';
              [...document.querySelectorAll('#review-question-list button')]
                .find(b => b.textContent.startsWith('Prepare review')).click();
            })()""")
            session.wait("document.querySelector('#notice').textContent.includes('unfinished')", 'unsaved guard')
            assert session.evaluate("document.querySelector('#question-choice').value === '2'")
            assert session.evaluate("document.querySelector('#draft-observations').value.includes('Preserve this')")
            session.evaluate("""(() => {
              document.querySelector('#draft-observations').value = '';
              [...document.querySelectorAll('#review-question-list button')]
                .find(b => b.textContent.startsWith('Prepare review')).click();
            })()""")
            session.wait("document.activeElement?.id === 'draft-observations'", 'existing form focused')
            assert session.evaluate("document.querySelector('#question-choice').value === '1'")
            assert session.evaluate("document.querySelectorAll('#snapshot-list .snapshot').length === 1")
            assert session.evaluate("""[...document.querySelectorAll('#source-choice input:checked')]
              .some(input => input.closest('label').textContent.includes('Needs review'))""")
            # Capture an actual rendered review queue, not a design mock-up.
            session.evaluate("document.querySelector('#overview').scrollIntoView()")
            output = ROOT / 'verification-artifacts'
            output.mkdir(exist_ok=True)
            shot = session.command('Page.captureScreenshot', {'format': 'png'})
            (output / 'question-review-overview.png').write_bytes(base64.b64decode(shot['data']))
            session.evaluate("""(() => {
              document.querySelectorAll('#source-choice input').forEach(input => {
                input.checked = !input.closest('label').textContent.includes('Needs review');
              });
              document.querySelector('#draft-observations').value = 'Current fictional sources explicitly reconciled; no clinical conclusion.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 2", 'replacement saved')
            session.evaluate("""[...document.querySelectorAll('#snapshot-list .snapshot button')]
              .find(b => b.textContent.includes('Demo review acknowledgment')).click()""")
            session.wait("document.querySelectorAll('#review-question-list .review-question').length === 0", 'resolved item leaves queue')
            assert session.evaluate("[...document.querySelectorAll('#snapshot-list .pill')].some(p => p.textContent === 'stale')")
            assert session.evaluate("document.querySelector('#question-list').textContent.includes('Another fictional')")
            print('PASS: overview -> linked comparison -> exact original -> protected question handoff -> explicit replacement -> history preserved')
        finally:
            if session:
                session.close()
            try:
                os.killpg(browser.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL)
                browser.wait(timeout=5)
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == '__main__':
    main()
