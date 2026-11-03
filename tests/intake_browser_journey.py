"""An actual empty-DB → file intake → source-bound review → correction journey.

All inputs are existing independently authored fictional reports. File selection
uses CDP's real file input, not a mock import API; no seed CLI or external model.
"""
from __future__ import annotations

import base64
import hashlib
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


def main():
    chrome = next((p for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                   if (p := shutil.which(n))), None)
    if not chrome:
        raise AssertionError('Chromium absent; case-intake browser workflow not verified')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    with tempfile.TemporaryDirectory(prefix='oi-intake-browser-') as temporary:
        directory = Path(temporary)
        db = directory / 'empty.sqlite'
        app_port, debug_port = free_port(), free_port()
        url = f'http://127.0.0.1:{app_port}/'

        def start_server():
            return subprocess.Popen([sys.executable, '-m', 'open_intelligence', 'serve',
                                     '--db', str(db), '--port', str(app_port)], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        server = start_server()
        browser = session = None
        try:
            wait_for(lambda: urlopen(url, timeout=1).status == 200, 'empty-case local server')
            assert json.load(urlopen(url + 'api/cases')) == [], 'This journey must begin without seeded cases'
            args = [chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage',
                    '--disable-background-networking', '--no-first-run', '--disable-extensions',
                    '--no-default-browser-check', '--remote-allow-origins=*',
                    f'--remote-debugging-port={debug_port}', f'--user-data-dir={directory}/chrome', 'about:blank']
            # Explicitly test-only root container accommodation; hosted CI is non-root.
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                args.insert(1, '--no-sandbox')
            browser = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(f'http://127.0.0.1:{debug_port}/json/list', timeout=1)),
                               'Chromium DevTools target')
            page = next(t for t in targets if t['type'] == 'page')
            session = ChromeSession(page['webSocketDebuggerUrl'])
            session.command('Page.enable')
            session.command('Runtime.enable')
            session.command('DOM.enable')
            session.command('Emulation.setDeviceMetricsOverride', {'width':1440, 'height':1000, 'deviceScaleFactor':1, 'mobile':False})
            navigation = session.command('Page.navigate', {'url': url})
            if navigation.get('errorText'):
                raise AssertionError('Browser navigation failed before application: ' + navigation['errorText'])
            session.wait("document.querySelector('#new-case-details')?.open === true", 'create-case empty state')

            def screenshot(name, selector):
                session.evaluate('document.querySelector(' + json.dumps(selector) + ').scrollIntoView()')
                image = session.command('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':False})
                target = ROOT / 'verification-artifacts'
                target.mkdir(exist_ok=True)
                (target / name).write_bytes(base64.b64decode(image['data']))

            def create_case(case_id, label):
                session.evaluate("document.querySelector('#new-case-details').open = true")
                session.evaluate("document.querySelector('#intake-case-id').value = " + json.dumps(case_id))
                session.evaluate("document.querySelector('#intake-case-label').value = " + json.dumps(label))
                session.evaluate("document.querySelector('#intake-case-fictional').checked = true; document.querySelector('#new-case-form').requestSubmit()")
                session.wait("document.querySelector('#case-heading').textContent === " + json.dumps('Fictional case ' + label),
                             'created case active')
                session.wait("document.querySelector('#case-intake').getAttribute('aria-busy') === 'false'", 'creation completed')

            def import_files(paths, expected):
                dom = session.command('DOM.getDocument')
                field = session.command('DOM.querySelector', {'nodeId': dom['root']['nodeId'], 'selector':'#intake-files'})
                session.command('DOM.setFileInputFiles', {'nodeId': field['nodeId'], 'files':[str(p.resolve()) for p in paths]})
                # The explicit attestation must be made after each selection.
                assert session.evaluate("document.querySelector('#intake-file-fictional').checked") is False
                session.evaluate("document.querySelector('#intake-file-fictional').checked = true; document.querySelector('#file-intake-form').requestSubmit()")
                session.wait("document.querySelectorAll('#intake-receipts li').length === " + str(len(paths)), 'per-file receipts')
                session.wait("document.querySelector('#case-intake').getAttribute('aria-busy') === 'false'", 'batch complete')
                actual = session.evaluate("[...document.querySelectorAll('#intake-receipts li')].map(x=>x.dataset.status)")
                assert actual == expected, (actual, expected)

            create_case('CASE-ALPHA', 'Alpha')
            data = ROOT / 'examples' / 'synthetic'
            duplicate = directory / 'duplicate.txt'
            original = (data / 'alpha-pathology-original.txt').read_bytes()
            duplicate.write_bytes(original)
            unsupported = directory / 'not-a-report.pdf'
            unsupported.write_bytes(b'%PDF-1.4\nFICTIONAL TEST ONLY')
            import_files([data/'alpha-pathology-original.txt', data/'alpha-imaging.txt', duplicate,
                          data/'wrong-patient.txt', unsupported],
                         ['imported','imported','duplicate','quarantined','rejected'])
            state = json.load(urlopen(url+'api/cases/CASE-ALPHA/state'))
            assert len(state['sources']) == 2 and len(state['quarantines']) == 1
            source = next(s for s in state['sources'] if s['document_id']=='PATH-ALPHA')
            assert source['sha256'] == hashlib.sha256(original).hexdigest()
            retrieved = json.load(urlopen(url+f"api/cases/CASE-ALPHA/sources/{source['id']}"))
            assert retrieved['text'].encode('utf-8') == original
            screenshot('intake-file-receipts.png', '#case-intake')

            session.evaluate("document.querySelector('#question-text').value='Which original fictional findings need review?'; document.querySelector('#question-form').requestSubmit()")
            session.wait("document.querySelector('#composer-context-fingerprint').value.length === 64 && !document.querySelector('#model-investigation-run').disabled", 'investigation context')
            assert session.evaluate("document.querySelector('#model-investigation-mode').value") == 'replay'
            session.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait("document.querySelectorAll('#model-investigation-list .snapshot').length === 1", 'recorded replay')
            session.wait("!![...document.querySelectorAll('#model-investigation-list button')].find(b=>b.textContent==='Prepare review draft')", 'report action')
            session.evaluate("[...document.querySelectorAll('#model-investigation-list button')].find(b=>b.textContent==='Prepare review draft').click()")
            session.wait("document.querySelector('#snapshot-list .pill')?.textContent === 'draft'", 'prepared report remains unreviewed')
            state = json.load(urlopen(url+'api/cases/CASE-ALPHA/state'))
            old = state['snapshots'][0]
            assert state['questions'][0]['state'] == 'open'
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(b=>b.textContent==='Demo review acknowledgment').click()")
            session.wait("document.querySelector('#snapshot-list .pill')?.textContent === 'reviewed_in_demo'", 'explicit demonstration review')
            import_files([data/'alpha-pathology-amended.txt'], ['imported'])
            session.wait("document.querySelector('#snapshot-list .pill')?.textContent === 'stale'", 'file amendment invalidates report')
            state = json.load(urlopen(url+'api/cases/CASE-ALPHA/state'))
            assert state['snapshots'][0]['summary'] == old['summary']
            assert state['questions'][0]['state'] == 'open'
            with urlopen(url+f"api/cases/CASE-ALPHA/snapshots/{old['id']}/export") as output:
                report = output.read().decode()
                assert 'PATH-ALPHA@1' in report and 'stale' in report
            session.wait("document.querySelector('#composer-context-fingerprint').value.length === 64 && !document.querySelector('#model-investigation-run').disabled", 'current reassessment context')
            session.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait("document.querySelectorAll('#model-investigation-list .snapshot').length === 2", 'second investigation')
            session.evaluate("[...document.querySelectorAll('#model-investigation-list button')].find(b=>b.textContent==='Prepare review draft').click()")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 2", 'versioned reassessment report')
            state = json.load(urlopen(url+'api/cases/CASE-ALPHA/state'))
            assert {s['state'] for s in state['snapshots']} == {'stale','draft'}
            screenshot('intake-report-history.png', '#snapshot-list')

            create_case('CASE-BETA', 'Beta')
            # Unsubmitted source-linked questions must survive a blocked
            # patient switch, matching the established PR #163 behavior.
            session.evaluate("document.querySelector('#question-text').value='Which fictional finding still needs review?'")
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            assert session.evaluate("document.querySelector('#case-picker').value") == 'CASE-BETA'
            assert session.evaluate("document.querySelector('#question-text').value") == 'Which fictional finding still needs review?'
            assert 'clear' in session.evaluate("document.querySelector('#notice').textContent")
            session.evaluate("document.querySelector('#question-text').value=''")

            # The fallback paste field is also original case-scoped source
            # input; a case change must not destroy its unsubmitted bytes.
            session.evaluate("document.querySelector('#report-text').value=" +
                             json.dumps('OI-SYNTHETIC-REPORT/1\\nPatient: CASE-BETA\\n'))
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            assert session.evaluate("document.querySelector('#case-picker').value") == 'CASE-BETA'
            assert session.evaluate("document.querySelector('#report-text').value") == 'OI-SYNTHETIC-REPORT/1\\nPatient: CASE-BETA\\n'
            session.evaluate("document.querySelector('#report-text').value=''")

            # Real selected file bytes must remain selected; intake.js clears
            # the input on an accepted case switch, so this guard matters.
            dom = session.command('DOM.getDocument')
            file_input = session.command('DOM.querySelector', {
                'nodeId': dom['root']['nodeId'], 'selector': '#intake-files'})
            session.command('DOM.setFileInputFiles', {
                'nodeId': file_input['nodeId'],
                'files': [str((data / 'beta-pathology.txt').resolve())]})
            assert session.evaluate("document.querySelector('#intake-files').files.length") == 1
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            assert session.evaluate("document.querySelector('#case-picker').value") == 'CASE-BETA'
            assert session.evaluate("document.querySelector('#intake-files').files.length") == 1
            session.evaluate("document.querySelector('#intake-files').value=''; document.querySelector('#intake-files').dispatchEvent(new Event('change'))")

            # After explicit clearing, the existing case guard permits a
            # genuine switch in either direction without leaking source UI.
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait("document.querySelector('#case-picker').value === 'CASE-ALPHA' && document.querySelector('#case-heading').textContent === 'Fictional case Alpha'", 'cleared draft case switch')
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA'; picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait("document.querySelector('#case-heading').textContent === 'Fictional case Beta'", 'return to clean beta case')
            assert session.evaluate("document.querySelectorAll('#source-list .source-card').length") == 0
            assert session.evaluate("document.querySelectorAll('#intake-receipts li').length") == 0
            import_files([data/'beta-pathology.txt'], ['imported'])
            assert len(json.load(urlopen(url+'api/cases/CASE-BETA/state'))['sources']) == 1
            assert len(json.load(urlopen(url+'api/cases/CASE-ALPHA/state'))['sources']) == 3

            server.terminate(); server.wait(timeout=5)
            server = start_server()
            wait_for(lambda: urlopen(url+'api/cases', timeout=1).status == 200, 'restarted server')
            session.command('Page.reload', {'ignoreCache': True})
            session.wait("document.querySelectorAll('#case-picker option').length === 2", 'cases survive restart')
            final = json.load(urlopen(url+'api/cases/CASE-ALPHA/state'))
            assert len(final['sources']) == 3 and len(final['snapshots']) == 2
            assert next(s for s in final['snapshots'] if s['id']==old['id'])['summary'] == old['summary']
            assert final['quarantines'][0]['declared_patient_id'] == 'CASE-BETA'
            print('PASS: empty database → create case → actual file input → per-file receipts → exact original bytes → question → recorded replay → reviewable report → explicit demo acknowledgment → amendment → stale history → reassessment → second case → restart persistence')
        except Exception:
            if session is not None:
                print('BROWSER DIAGNOSTIC:', session.evaluate("JSON.stringify({url:location.href,title:document.title,notice:document.querySelector('#notice')?.textContent,body:document.body?.innerText.slice(0,1600)})"))
            raise
        finally:
            if session is not None:
                session.close()
            if browser is not None:
                try: os.killpg(browser.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try: os.killpg(browser.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    browser.wait(timeout=5)
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)


if __name__ == '__main__':
    main()
