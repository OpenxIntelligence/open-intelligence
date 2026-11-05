"""Exercise the documented persistent fictional demo through the built browser.

Only the uniquely owned, newly created test project is removed in cleanup.
The operator-facing launcher never removes volumes.
"""
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

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import h1_demo as demo
from browser_journey import ChromeSession, free_port, wait_for, wait_for_browser


def main():
    chrome = next((p for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                   if (p := shutil.which(name))), None)
    if not chrome:
        raise RuntimeError('Chromium required for demo acceptance')
    artifacts = Path(os.environ.get('OI_WEB_ARTIFACT_DIR', 'verification-web/screenshots'))
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oi-demo-acceptance-') as temporary:
        directory = Path(temporary) / 'owned-demo'
        state = demo.load_or_create(directory)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=str(directory / 'access'))
        command = demo.compose_command(state)
        browser = web = cd = None
        with (Path(temporary) / 'chrome-stderr.log').open('w+') as chrome_log:
            try:
                demo.up(directory, state)
                first = dict(state)
                demo.up(directory, state)
                assert state == first, 'Repeated setup must recover the same patient and source'
                web = subprocess.Popen(['npm', 'run', 'preview'], cwd=ROOT / 'apps/web',
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                from urllib.request import urlopen
                wait_for(lambda: urlopen('http://127.0.0.1:4173', timeout=2).status == 200, 'built demo UI', 30)
                port = free_port()
                browser = subprocess.Popen([chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage',
                    '--disable-background-networking', '--no-first-run', '--disable-extensions',
                    '--no-default-browser-check', '--remote-allow-origins=*', f'--remote-debugging-port={port}',
                    f'--user-data-dir={temporary}/chrome', 'about:blank'], stdout=subprocess.DEVNULL,
                    stderr=chrome_log, start_new_session=True)
                targets = wait_for_browser(browser, Path(chrome_log.name), port, timeout=30)
                cd = ChromeSession(next(row['webSocketDebuggerUrl'] for row in targets if row['type'] == 'page'))
                cd.command('Page.enable'); cd.command('Runtime.enable')
                cd.command('Page.navigate', {'url': 'http://127.0.0.1:4173'})

                def click(selector):
                    cd.wait('Boolean(document.querySelector(' + json.dumps(selector) + ')) && !document.querySelector(' + json.dumps(selector) + ').disabled', selector)
                    cd.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')

                def value(selector, text):
                    cd.evaluate('''(()=>{const e=document.querySelector(''' + json.dumps(selector) + ''');
                        const proto=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:
                          e instanceof HTMLSelectElement?HTMLSelectElement.prototype:HTMLInputElement.prototype;
                        Object.getOwnPropertyDescriptor(proto,'value').set.call(e,''' + json.dumps(text) + ''');
                        e.dispatchEvent(new Event(e instanceof HTMLSelectElement?'change':'input',{bubbles:true}));})()''')

                def navigate(section):
                    cd.evaluate('[...document.querySelectorAll(' + json.dumps('nav[aria-label="Patient workspace"] button') + ')].find(e=>e.textContent.includes(' + json.dumps(section) + ')).click()')

                cd.wait("document.querySelector('[data-testid=readiness]')?.textContent==='PostgreSQL API ready'", 'demo ready')
                value('#credential', state['token']); cd.evaluate("document.querySelector('#credential').form.requestSubmit()")
                value('#patient-id', state['patient_id']); cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
                cd.wait("Boolean(document.querySelector('[data-testid=patient-card]'))", 'seeded patient')
                navigate('Records'); click('[data-testid=load-cases]'); click('[data-testid=load-sources]')
                click('[data-testid=open-original]')
                cd.wait("document.querySelector('[data-testid=server-original]')?.textContent.includes('assay as pending')", 'seeded exact original')
                click('[data-testid=ask-source-question]')
                cd.wait("Boolean(document.querySelector('[data-testid=question-draft]'))", 'question editor')
                value('[data-testid=question-draft]', 'What record would resolve the pending assay in this fictional report?')
                click('[data-testid=prepare-custom-question]'); click('[data-testid=save-source-question]')
                cd.wait("Boolean(document.querySelector('[data-testid=saved-source-question] code'))", 'persisted question')
                qid = cd.evaluate("document.querySelector('[data-testid=saved-source-question] code').textContent")
                click('[data-testid=load-source-questions]'); click('[data-testid=authored-evidence-open]')
                cd.wait("Boolean(document.querySelector('[data-testid=evidence-file]'))", 'evidence import')
                document = cd.command('DOM.getDocument')['root']['nodeId']
                node = cd.command('DOM.querySelector', {'nodeId': document, 'selector': '[data-testid=evidence-file]'})['nodeId']
                cd.command('DOM.setFileInputFiles', {'nodeId': node, 'files': [str(ROOT / 'examples/synthetic/demo-evidence.txt')]})
                click('[data-testid=evidence-fictional]'); click('[data-testid=evidence-import]'); click('[data-testid=evidence-select]')
                value('[data-testid=evidence-quote]', 'an assay limitation')
                value('[data-testid=evidence-relation]', 'context')
                value('[data-testid=evidence-applicability]', 'limited')
                value('[data-testid=evidence-rationale]', 'Fictional methods context only; it cannot resolve the missing assay result.')
                click('[data-testid=evidence-assess]'); click('[data-testid=evidence-report-select]'); click('[data-testid=evidence-report-prepare]')
                click('[data-testid=evidence-report-open]')
                cd.wait("Boolean(document.querySelector('[data-testid=evidence-report-body]'))", 'preserved report')
                body = cd.evaluate("document.querySelector('[data-testid=evidence-report-body]').textContent")
                click('[data-testid=followthrough-open-create]')
                value('[data-testid=followthrough-title]', 'Obtain the fictional final assay report')
                value('[data-testid=followthrough-owner]', 'Fictional coordinator')
                value('[data-testid=followthrough-trigger]', 'When the final report is available')
                value('[data-testid=followthrough-reason]', 'Resolve the pending source information before further preparation.')
                click('[data-testid=followthrough-create]')
                cd.wait("document.querySelectorAll('[data-testid=followthrough-task]').length===1", 'recorded follow-up')
                root = '/v1/patients/' + state['patient_id'] + '/cases/' + demo.CASE
                scope = root + '/questions/' + qid
                packet = demo.request(scope + '/evidence', state['token'])
                report_id = packet['reports'][0]['report_id']
                report = demo.request(scope + '/evidence-reports/' + report_id, state['token'])
                assert report['body'] == body
                assert hashlib.sha256(body.encode()).hexdigest() == report['body_sha256']
                before = demo.request(root + '/followthrough', state['token'])['tasks']
                assert len(before) == 1 and before[0]['question_id'] == qid
                navigate('Overview')
                cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
                assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                (artifacts / 'h1-demo-mobile.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
                subprocess.run(command + ['stop'], env=env, cwd=ROOT, check=True)
                demo.up(directory, state)
                assert state == first
                restored = demo.request(scope + '/evidence-reports/' + report_id, state['token'])
                assert restored['body'] == body and restored['snapshot_sha256'] == report['snapshot_sha256']
                assert demo.request(root + '/followthrough', state['token'])['tasks'] == before
                (artifacts / 'demo-journey.json').write_text(json.dumps({
                    'synthetic': True, 'patient_id': state['patient_id'], 'source_id': state['source_id'],
                    'question_id': qid, 'report_id': report_id, 'report_body_sha256': report['body_sha256'],
                    'task_id': before[0]['task_id'], 'repeat_setup_same_identity': True,
                    'restart_preserves_report_and_task': True, 'clinical_approval': False}, indent=2) + '\n')
                print('PASS PERSISTENT DEMO: exact seeded original → authored question → fictional evidence → preserved report → follow-up; repeated setup and restart retain identities and history.')
            except Exception:
                if cd:
                    (artifacts / 'h1-demo-failure.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
                    (artifacts / 'h1-demo-failure-status.json').write_text(json.dumps(cd.evaluate('''({
                      statuses:[...document.querySelectorAll('[role=status]')].map(e=>e.textContent),
                      reports:document.querySelectorAll('[data-testid=evidence-report-row]').length,
                      tasks:document.querySelectorAll('[data-testid=followthrough-task]').length
                    })'''), indent=2) + '\n')
                raise
            finally:
                if cd: cd.close()
                for process in (browser, web):
                    if not process: continue
                    try: os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                subprocess.run(command + ['down', '--volumes'], env=env, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
