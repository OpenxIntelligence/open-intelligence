"""Real Chromium source-reader event checks on fictional local data only.

Reuse the project's CDP helper. Delay responses from the real local API to
exercise user-event wiring; never contact an external research service.
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
from urllib.request import urlopen

from browser_journey import ChromeSession, ROOT, free_port, wait_for


def stop(process, *, group=False):
    if process is None:
        return
    try:
        if group:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        if group:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def main():
    chrome = next((p for name in ('google-chrome', 'google-chrome-stable',
                                  'chromium', 'chromium-browser') if (p := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError('Chrome/Chromium required; source dialog wiring NOT verified')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    with tempfile.TemporaryDirectory(prefix='oi-source-view-') as tmp:
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
            session.command('Page.navigate', {'url': url})
            session.wait("typeof active !== 'undefined' && active?.case.case_id === 'CASE-ALPHA' && renderedCaseId === caseId",
                         'Alpha ready')
            session.evaluate(r"""(() => {
              const original = window.fetch.bind(window);
              window.__held = []; window.__holdSources = false;
              window.fetch = (url, options) => {
                if (!window.__holdSources || !/^\/api\/cases\/[^/]+\/sources\/\d+$/.test(String(url)))
                  return original(url, options);
                const received = original(url, options).then(value => ({value}), error => ({error}));
                return new Promise((resolve, reject) => window.__held.push({url,
                  release: async () => { const result = await received;
                    if (result.error) reject(result.error); else resolve(result.value); }}));
              };
              window.__release = index => window.__held[index].release();
              window.__pick = value => { const picker = document.getElementById('case-picker');
                picker.value = value; picker.dispatchEvent(new Event('change')); };
            })()""")

            # Close is clicked while a newer source read is outstanding.
            session.evaluate('openSource(active.sources[0])')
            session.wait("document.getElementById('source-dialog').open", 'source open')
            session.evaluate("window.__holdSources = true; window.__read = openSource(active.sources[1]); true")
            session.evaluate("document.getElementById('dialog-close').click()")
            session.evaluate('(async()=>{await window.__release(0); await window.__read;})()')
            assert session.evaluate("!document.getElementById('source-dialog').open"), 'Close was undone by a delayed response'

            # Native Escape must also invalidate a pending source read.
            session.evaluate('window.__holdSources = false; openSource(active.sources[0])')
            session.evaluate('window.__holdSources = true; window.__read = openSource(active.sources[1]); true')
            for kind in ('keyDown', 'keyUp'):
                session.command('Input.dispatchKeyEvent', {'type': kind, 'key': 'Escape',
                                'code': 'Escape', 'windowsVirtualKeyCode': 27})
            session.wait("!document.getElementById('source-dialog').open", 'Escape dismissed source')
            session.evaluate('(async()=>{await window.__release(1); await window.__read;})()')
            assert session.evaluate("!document.getElementById('source-dialog').open"), 'Escape was undone by a delayed response'

            # Real picker events: A -> B -> A must not revive an earlier A read.
            session.evaluate('window.__read = openSource(active.sources[0]); true')
            session.evaluate("window.__pick('CASE-BETA')")
            session.wait("active?.case.case_id === 'CASE-BETA' && renderedCaseId === caseId", 'Beta ready')
            session.evaluate("window.__pick('CASE-ALPHA')")
            session.wait("active?.case.case_id === 'CASE-ALPHA' && renderedCaseId === caseId", 'Alpha returned')
            session.evaluate('(async()=>{await window.__release(2); await window.__read;})()')
            assert session.evaluate("!document.getElementById('source-dialog').open"), 'Case round trip revived an old read'

            # Two real source-card actions; the last click wins out-of-order delivery.
            session.evaluate("document.querySelectorAll('#source-list .source-card button')[0].click(); document.querySelectorAll('#source-list .source-card button')[1].click()")
            session.evaluate('window.__release(4)')
            session.wait("document.getElementById('source-dialog').open", 'newer source response')
            current = session.evaluate("document.getElementById('dialog-title').textContent")
            session.evaluate('window.__release(3)')
            session.evaluate('new Promise(resolve=>setTimeout(resolve,30))')
            assert session.evaluate("document.getElementById('dialog-title').textContent") == current, 'Older click replaced newer selection'
            session.evaluate("document.getElementById('dialog-close').click(); window.__holdSources = false")

            # Membership alone cannot establish a before/after amendment relation.
            session.evaluate('openComparison(active.sources[0], active.sources[1])')
            assert session.evaluate("!document.getElementById('compare-dialog').open"), 'Unrelated reports were compared'
            assert session.evaluate("document.getElementById('notice').textContent.includes('Only linked consecutive')")
            print('PASS: actual Close, native Escape, A-B-A picker events, out-of-order source-card clicks, and unrelated-comparison rejection')
        finally:
            if session is not None:
                session.close()
            stop(browser, group=True)
            stop(server)


if __name__ == '__main__':
    main()
