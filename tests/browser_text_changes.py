"""Chromium acceptance for the existing source-line comparison; fictional data only.

Uses the established CDP helper, local API and canonical renderer. No second
comparison engine, external network service, package or clinical interpretation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from browser_journey import ChromeSession, ROOT, free_port, wait_for
from browser_source_dialogs import stop


def main():
    chrome = next((p for name in ('google-chrome', 'google-chrome-stable',
                                  'chromium', 'chromium-browser') if (p := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError('Chrome/Chromium required; line comparison NOT verified')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    with tempfile.TemporaryDirectory(prefix='oi-text-comparison-') as tmp:
        db = str(Path(tmp) / 'case.sqlite')
        subprocess.run([sys.executable, '-m', 'open_intelligence', 'seed', '--db', db],
                       cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        port, debug_port = free_port(), free_port()
        server = subprocess.Popen([sys.executable, '-m', 'open_intelligence', 'serve',
                                   '--db', db, '--port', str(port)], cwd=ROOT, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = session = None
        try:
            url = f'http://127.0.0.1:{port}/'
            wait_for(lambda: urlopen(url, timeout=1).status == 200, 'local app')
            browser = subprocess.Popen([
                chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage',
                '--disable-background-networking', '--no-first-run', '--disable-extensions',
                '--remote-allow-origins=*', f'--remote-debugging-port={debug_port}',
                f'--user-data-dir={tmp}/chrome', 'about:blank'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f'http://127.0.0.1:{debug_port}/json/list', timeout=1)), 'browser page')
            page = next(t for t in targets if t.get('type') == 'page')
            session = ChromeSession(page['webSocketDebuggerUrl'])
            session.command('Page.enable')
            session.command('Runtime.enable')
            session.command('Emulation.setDeviceMetricsOverride', {
                'width': 1280, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
            session.command('Page.navigate', {'url': url})
            session.wait("typeof active !== 'undefined' && active?.case.case_id === 'CASE-ALPHA' && renderedCaseId === caseId",
                         'Alpha ready')
            session.evaluate("document.getElementById('example-button').click()")
            session.wait("document.getElementById('report-text').value.includes('Amends: PATH-ALPHA@1')",
                         'authored amendment loaded')
            session.evaluate("document.getElementById('import-form').requestSubmit()")
            session.wait("active.sources.length === 3 && document.querySelector('#source-change-list .change-card')",
                         'source change available')
            versions = session.evaluate("active.sources.filter(s=>s.document_id==='PATH-ALPHA').sort((a,b)=>a.version-b.version).map(s=>s.id)")
            originals = [json.load(urlopen(f'{url}api/cases/CASE-ALPHA/sources/{sid}'))['text'] for sid in versions]
            session.evaluate("document.querySelector('#source-change-list .change-card .actions button').click()")
            session.wait("document.getElementById('compare-dialog').open && document.querySelector('#compare-before mark')",
                         'line highlights in actual comparison')
            assert session.evaluate("document.getElementById('compare-before').textContent") == originals[0]
            assert session.evaluate("document.getElementById('compare-after').textContent") == originals[1]
            for target, original in zip(('compare-before', 'compare-after'), originals):
                marks = session.evaluate("[...document.querySelectorAll('#" + target + " mark')].map(m=>({line:Number(m.dataset.line),text:m.textContent}))")
                assert marks, 'Expected changed original lines to be marked'
                for mark in marks:
                    assert mark['line'] >= 1
                    assert original.splitlines(keepends=True)[mark['line']-1] == mark['text'], 'Highlight lost exact source bytes or line anchor'
            assert 'clinical' in session.evaluate("document.getElementById('compare-context').textContent").lower()

            # Existing originals remain present on narrow displays.
            session.command('Emulation.setDeviceMetricsOverride', {
                'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
            session.wait('window.innerWidth === 390', 'narrow viewport')
            assert session.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'Comparison causes horizontal page overflow'

            # Direct renderer stress inputs do not alter the persisted source ledger.
            hostile = '<img id="unexpected-source-markup" src=x onerror=alert(1)>\n'
            session.evaluate('renderReportLineComparison(' + json.dumps('safe\n') + ',' + json.dumps(hostile) + ')')
            assert session.evaluate("document.getElementById('compare-after').textContent") == hostile
            assert session.evaluate("document.getElementById('unexpected-source-markup') === null"), 'Source markup became an element'
            session.evaluate("renderReportLineComparison('x'.repeat(65537), 'short')")
            assert session.evaluate("document.querySelectorAll('#compare-before mark, #compare-after mark').length === 0")
            assert session.evaluate("document.getElementById('compare-before').textContent.length === 65537")
            assert 'skipped' in session.evaluate("document.getElementById('compare-context').textContent").lower()
            session.evaluate("renderReportLineComparison('same\\n', 'same\\n')")
            assert session.evaluate("document.querySelectorAll('#compare-before mark, #compare-after mark').length === 0")
            assert 'identical' in session.evaluate("document.getElementById('compare-context').textContent").lower()

            session.evaluate("document.getElementById('compare-close').click()")
            session.wait("!document.getElementById('compare-dialog').open", 'comparison closed')
            session.evaluate("document.querySelector('#source-change-list .change-card .actions button').click()")
            session.wait("document.getElementById('compare-dialog').open && document.querySelector('#compare-before mark')",
                         'reopened original comparison')
            assert session.evaluate("document.getElementById('compare-before').textContent") == originals[0]
            assert session.evaluate("document.getElementById('compare-after').textContent") == originals[1]
            print('PASS: real amendment click-through, exact highlighted original lines, inert markup, bounded fallback, identical-state reset, close/reopen and 390px layout')
        finally:
            if session is not None:
                session.close()
            stop(browser, group=True)
            stop(server)


if __name__ == '__main__':
    main()
