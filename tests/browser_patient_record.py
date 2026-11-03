"""Real-browser patient record -> investigation -> amendment on fictional data.

Uses the existing stdlib CDP helper and loopback server. No network knowledge
retrieval, downloaded case files, live model, or new browser dependencies.
"""
from __future__ import annotations

import base64
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
    chrome = next((path for name in ('google-chrome', 'google-chrome-stable',
                                     'chromium', 'chromium-browser')
                   if (path := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError('Chrome/Chromium required; patient record journey NOT verified')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    output = Path(os.environ.get('OI_UI_ARTIFACT_DIR', 'ui-artifacts'))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oi-patient-record-') as tmp:
        db = str(Path(tmp) / 'case.sqlite')
        subprocess.run([sys.executable, '-m', 'open_intelligence', 'seed', '--db', db],
                       cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        port, debug_port = free_port(), free_port()
        command = [sys.executable, '-m', 'open_intelligence', 'serve', '--db', db, '--port', str(port)]
        server = subprocess.Popen(command, cwd=ROOT, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = cd = None
        try:
            url = f'http://127.0.0.1:{port}/'
            wait_for(lambda: urlopen(url, timeout=1).status == 200, 'local application')
            flags = [chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage',
                     '--disable-background-networking', '--no-first-run', '--disable-extensions',
                     '--remote-allow-origins=*', f'--remote-debugging-port={debug_port}',
                     f'--user-data-dir={tmp}/chrome']
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                flags.append('--no-sandbox')
            browser = subprocess.Popen(flags + ['about:blank'], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f'http://127.0.0.1:{debug_port}/json/list', timeout=1)), 'browser target')
            page = next(item for item in targets if item.get('type') == 'page')
            cd = ChromeSession(page['webSocketDebuggerUrl'])
            cd.command('Page.enable')
            cd.command('Runtime.enable')
            cd.command('Emulation.setDeviceMetricsOverride', {
                'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})
            cd.command('Page.navigate', {'url': url})

            def ready(case='CASE-ALPHA'):
                cd.wait("document.querySelector('#patient-view')?.dataset.state === 'ready' && "
                        f"active?.case.case_id === {json.dumps(case)}", f'{case} record ready')

            def state():
                return json.load(urlopen(url + 'api/cases/CASE-ALPHA/state'))

            def screenshot(name):
                cd.evaluate("document.querySelector('#patient-view').scrollIntoView()")
                data = cd.command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
                (output / name).write_bytes(base64.b64decode(data['data']))

            ready()
            assert cd.evaluate("document.querySelectorAll('#patient-findings button[data-source-line]').length") == len(state()['assertions'])
            cd.evaluate("document.querySelector('#patient-findings button[data-source-line]').click()")
            cd.wait("document.querySelector('#source-dialog').open", 'exact original source')
            assert cd.evaluate("!!document.querySelector('#dialog-text mark.source-highlight')")
            assert cd.evaluate("document.querySelector('#dialog-context').textContent.includes('Not clinically reviewed')")
            cd.evaluate("document.querySelector('#dialog-close').click()")

            # Existing question and evidence forms remain the only write owners.
            cd.evaluate("""(() => {
              document.querySelector('#question-text').value = 'Which fictional source uncertainties need review?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            cd.wait("!!document.querySelector('#patient-questions button[data-question-id]')", 'question in patient view')
            ready()
            qid = state()['questions'][0]['id']
            cd.evaluate("""(() => {
              document.querySelector('#question-text').value = 'A separate fictional question must retain its own context.';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#patient-questions button[data-question-id]').length === 2", 'two distinct questions')
            ready()
            cd.evaluate(f"document.querySelector('#patient-questions button[data-question-id=\"{qid}\"]').click()")
            assert cd.evaluate("document.querySelector('#model-investigation-question').value") == str(qid)
            assert cd.evaluate("document.querySelector('#question-choice').value") == str(qid)
            assert cd.evaluate("document.activeElement.id") == 'model-investigation-question'

            cd.evaluate("document.querySelector('#example-evidence-button').click()")
            cd.wait("document.querySelector('#evidence-text').value.includes('OI-SYNTHETIC-EVIDENCE/1')", 'fictional evidence example')
            cd.evaluate("document.querySelector('#evidence-import-form').requestSubmit()")
            cd.wait("document.querySelectorAll('#evidence-source-choice option').length === 1", 'evidence stored')
            ready()
            for selector in ('question-choice', 'model-investigation-question', 'evidence-question-choice'):
                assert cd.evaluate(f"document.querySelector('#{selector}').value") == str(qid), 'Refresh changed investigation question'
            cd.evaluate("""(() => {
              document.querySelector('#evidence-relation').value = 'context';
              document.querySelector('#evidence-applicability').value = 'limited';
              document.querySelector('#evidence-rationale').value = 'Fictional method context only; no patient-specific efficacy is established.';
              document.querySelector('#evidence-assessment-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#evidence-assessment-list article').length === 1", 'question-scoped assessment')
            ready()
            cd.wait("!!document.querySelector('#model-investigation-template option[value=\"evidence-summary\"]')", 'bounded template loaded')
            cd.evaluate("""(() => {
              document.querySelector('#model-investigation-template').value = 'evidence-summary';
              document.querySelector('#model-investigation-mode').value = 'replay';
              document.querySelector('#model-investigation-form').requestSubmit();
            })()""")
            cd.wait("document.querySelector('#model-investigation-list').textContent.includes('recorded-replay')", 'labeled replay investigation')
            ready()
            assert next(q for q in state()['questions'] if q['id'] == qid)['state'] == 'open', 'Unreviewed replay closed its question'
            assert cd.evaluate(f"!!document.querySelector('#patient-questions button[data-question-id=\"{qid}\"]')")

            cd.evaluate("""(() => {
              document.querySelector('#draft-observations').value = 'Source statements retain pending and indeterminate findings; no clinical conclusion is made.';
              document.querySelector('#draft-assumptions').value = 'This is an independently authored fictional review exercise.';
              const evidence = document.querySelector('#evidence-choice input');
              if (evidence) evidence.checked = true;
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1", 'source-linked report persisted')
            ready()
            before = state()
            snapshot_id = before['snapshots'][0]['id']
            old_source = next(source for source in before['sources'] if source['document_id'] == 'PATH-ALPHA')
            cd.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent.includes('Demo review acknowledgment')).click()")
            cd.wait("active.snapshots[0].state === 'reviewed_in_demo'", 'explicit simulation review')
            ready()
            assert not cd.evaluate(f"!!document.querySelector('#patient-questions button[data-question-id=\"{qid}\"]')")
            assert cd.evaluate("document.querySelector('#patient-record-status').textContent.includes('not been clinically reviewed')")

            cd.evaluate("document.querySelector('#example-button').click()")
            cd.wait("document.querySelector('#report-text').value.includes('Amends: PATH-ALPHA@1')", 'synthetic amendment example')
            cd.evaluate("document.querySelector('#import-form').requestSubmit()")
            cd.wait("active.snapshots[0].state === 'stale'", 'source-dependent report stale')
            ready()
            assert state()['snapshots'][0]['id'] == snapshot_id
            assert cd.evaluate("document.querySelector('#patient-questions').textContent.includes('1 earlier reports need reassessment')")
            assert cd.evaluate("!!document.querySelector('#patient-questions button[data-question-id]')")
            assert cd.evaluate("document.querySelector('#patient-findings').textContent.includes('Negative')")
            cd.evaluate(f"document.querySelector('#patient-timeline details').open = true; document.querySelector('#patient-timeline details button[data-source-id=\"{old_source['id']}\"]').click()")
            cd.wait("document.querySelector('#source-dialog').open", 'preserved original after amendment')
            assert cd.evaluate("document.querySelector('#dialog-title').textContent.includes('PATH-ALPHA@1')")
            cd.evaluate("document.querySelector('#dialog-close').click()")
            assert next(s for s in state()['sources'] if s['id'] == old_source['id'])['sha256'] == old_source['sha256']

            # Delay only local projection responses; all underlying reads remain real.
            cd.evaluate(r"""(() => {
              const original = window.fetch.bind(window);
              window.__heldRecord = []; window.__holdRecord = false; window.__badRecordCutoff = false;
              window.fetch = async (url, options) => {
                if (!/\/world-model$/.test(String(url))) return original(url, options);
                const response = await original(url, options);
                if (window.__badRecordCutoff) {
                  window.__badRecordCutoff = false;
                  const data = await response.json(); data.as_of_ledger.event_id += 1000;
                  return new Response(JSON.stringify(data), {headers: {'Content-Type': 'application/json'}});
                }
                if (!window.__holdRecord) return response;
                return new Promise(resolve => window.__heldRecord.push(() => resolve(response)));
              };
            })()""")
            cd.evaluate("window.__holdRecord = true; refresh(); true")
            cd.wait("window.__heldRecord.length === 1", 'held Alpha projection')
            assert cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker'); picker.value = 'CASE-BETA';
              picker.dispatchEvent(new Event('change'));
              return document.querySelectorAll('#patient-view button[data-source-id]').length === 0;
            })()"""), 'Old patient source actions remained during case load'
            cd.wait("window.__heldRecord.length === 2", 'held Beta projection')
            cd.evaluate("window.__heldRecord[1](); true")
            ready('CASE-BETA')
            cd.evaluate("window.__heldRecord[0](); true")
            assert 'PATH-ALPHA' not in cd.evaluate("document.querySelector('#patient-view').textContent")
            assert 'PATH-BETA' in cd.evaluate("document.querySelector('#patient-view').textContent")
            # Accepted Unicode separators share Python's source-line numbering.
            cd.evaluate("window.__holdRecord = false")
            unicode_report = (
                'OI-SYNTHETIC-REPORT/1\nPatient: CASE-BETA\nDocument: UNICODE-BETA\n'
                'Type: pathology\nEvent-Date: 2026-06-01\nIssued-At: 2026-06-02\u2028'
                'Specimen: INVENTED-BETA\nFinding: marker-a|reported|Fictional statement A.\n'
                'Finding: marker-b|negative|Fictional statement B.\n'
            )
            cd.evaluate("document.querySelector('#report-text').value = " + json.dumps(unicode_report) +
                        "; document.querySelector('#import-form').requestSubmit();")
            cd.wait("document.querySelector('#patient-findings').textContent.includes('UNICODE-BETA')", 'Unicode-delimited source projected')
            ready('CASE-BETA')
            cd.evaluate("[...document.querySelectorAll('#patient-findings article')].find(item => item.querySelector('.quoted')?.textContent === 'Fictional statement A.' && item.querySelector('button')?.textContent.includes('UNICODE-BETA')).querySelector('button').click()")
            cd.wait("document.querySelector('#source-dialog').open", 'Unicode source anchor')
            assert cd.evaluate("document.querySelector('#dialog-text mark').textContent") == 'Finding: marker-a|reported|Fictional statement A.'
            assert cd.evaluate("document.querySelector('#dialog-text').textContent") == unicode_report
            cd.evaluate("document.querySelector('#dialog-close').click()")
            cd.evaluate("""window.__holdRecord = false;
              document.querySelector('#case-picker').value = 'CASE-ALPHA';
              document.querySelector('#case-picker').dispatchEvent(new Event('change'));""")
            ready()

            # A state/projection race fails closed, with a working refresh action.
            cd.evaluate("window.__badRecordCutoff = true; refresh(); true")
            cd.wait("document.querySelector('#patient-record-status button')?.textContent === 'Retry'", 'mismatched ledger denied')
            assert cd.evaluate("document.querySelectorAll('#patient-view button[data-source-id], #patient-view button[data-question-id]').length") == 0
            cd.evaluate("document.querySelector('#patient-record-status button').click()")
            ready()

            # Acknowledging a replacement clears current reassessment work, while
            # the prior stale report stays visible in history.
            cd.evaluate(f"document.querySelector('#patient-questions button[data-question-id=\"{qid}\"]').click()")
            cd.evaluate("""(() => {
              document.querySelector('#draft-observations').value = 'Updated fictional source wording has been inspected; no clinical conclusion is made.';
              document.querySelector('#draft-form').requestSubmit();
            })()""")
            cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 2", 'replacement report persisted')
            ready()
            cd.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent.includes('Demo review acknowledgment')).click()")
            cd.wait("active.snapshots[0].state === 'reviewed_in_demo'", 'replacement acknowledged in simulation')
            ready()
            assert cd.evaluate("document.querySelector('#patient-questions').textContent.includes('0 earlier reports need reassessment')")
            assert cd.evaluate("document.querySelector('#patient-questions').textContent.includes('1 historical stale version')")

            screenshot('patient-record-desktop.png')
            cd.command('Emulation.setDeviceMetricsOverride', {
                'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
            assert cd.evaluate("document.documentElement.scrollWidth <= innerWidth"), 'Patient record causes horizontal overflow'
            screenshot('patient-record-narrow.png')

            # Persisted sources, questions, stale reports and audit receipts survive restart.
            saved = state()
            stop(server)
            server = subprocess.Popen(command, cwd=ROOT, env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait_for(lambda: urlopen(url, timeout=1).status == 200, 'restarted local application')
            cd.command('Page.navigate', {'url': url})
            ready()
            restored = state()
            for key in ('sources', 'assertions', 'questions', 'snapshots', 'events'):
                assert restored[key] == saved[key], f'{key} changed after server restart'
            receipt = {'status': 'passed', 'synthetic_only': True, 'live_model': False,
                       'external_evidence_retrieved': False, 'case': restored['case']['case_id'],
                       'snapshot_id': snapshot_id, 'old_source_sha256': old_source['sha256'],
                       'checks': ['source anchors', 'question handoff', 'fictional evidence assessment',
                                  'labeled replay remains unreviewed', 'explicit demo review',
                                  'amendment and source history', 'replacement review preserves stale history',
                                  'two-question handoff persists across refresh', 'Unicode source anchors', 'case-switch race',
                                  'ledger mismatch and retry', 'responsive layout', 'restart persistence']}
            (output / 'patient-record-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
            print('PASS: patient record, exact sources, question/evidence/replay, demo review, '
                  'amendment, original history, case race, cutoff failure/retry and restart')
        finally:
            if cd is not None:
                cd.close()
            stop(browser, group=True)
            stop(server)


if __name__ == '__main__':
    main()
