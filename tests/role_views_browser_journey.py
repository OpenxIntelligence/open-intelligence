"""Headless journey for the patient / care-team view layer (connected workspace host).

Original fictional examples only. Checks that existing sections are regrouped,
not removed; that an amendment surfaces a direct source comparison in the
docked inspector; and that the patient view renders the change read-only.
Set OI_VIEWS_ARTIFACT_DIR to save screenshots.
"""
from __future__ import annotations
import base64, json, os, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from browser_journey import ChromeSession, free_port, wait_for  # noqa: E402

AMENDED = (ROOT / 'examples/synthetic/alpha-pathology-amended.txt').read_text(encoding='utf-8')
# Independently authored fictional correction: one finding removed (comparison), one added.
IMAGING_AMENDED = """OI-SYNTHETIC-REPORT/1
Patient: CASE-ALPHA
Document: IMG-ALPHA
Type: imaging
Event-Date: 2026-05-17
Issued-At: 2026-05-20
Amends: IMG-ALPHA@1
Finding: lesion-size|reported|A fictional reference lesion was re-measured as 31 mm in the corrected report.
Finding: new-lesion|pending|A fictional second area is listed for follow-up in the corrected report.
"""
EXPECTED_CARE_SECTIONS = ['incoming-board', 'overview', 'workspace-start', 'source-intake', 'metrics', 'patient-mission',
                          'timeline', 'sources', 'biological-assets', 'import', 'investigations', 'evidence',
                          'bibliography', 'changes-since-review', 'activity', 'options']


def main() -> None:
    chrome = next((p for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser') if (p := shutil.which(n))), None)
    if not chrome:
        raise AssertionError('Chromium unavailable; journey not verified')
    artifacts = os.environ.get('OI_VIEWS_ARTIFACT_DIR')
    with tempfile.TemporaryDirectory(prefix='oi-role-views-') as tmp:
        db = str(Path(tmp) / 'views.sqlite'); app_port = free_port(); debug = free_port()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        server = subprocess.Popen([sys.executable, str(ROOT / 'run_open_intelligence.py'), '--db', db, '--port', str(app_port),
                                   '--with-examples'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = cd = None
        try:
            url = f'http://127.0.0.1:{app_port}/'
            wait_for(lambda: urlopen(url, timeout=1).status == 200, 'workspace server', timeout=20)
            browser = subprocess.Popen([chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage', '--disable-background-networking',
                                        '--no-first-run', '--disable-extensions', '--no-default-browser-check', '--remote-allow-origins=*',
                                        f'--remote-debugging-port={debug}', f'--user-data-dir={Path(tmp) / "chrome"}', 'about:blank'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(f'http://127.0.0.1:{debug}/json/list', timeout=1)), 'browser debugger', timeout=30)
            cd = ChromeSession(next(t['webSocketDebuggerUrl'] for t in targets if t['type'] == 'page'))
            cd.command('Page.enable'); cd.command('Runtime.enable')
            cd.command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})

            def shot(name: str) -> None:
                if artifacts:
                    Path(artifacts).mkdir(parents=True, exist_ok=True)
                    data = cd.command('Page.captureScreenshot', {'format': 'png'})['data']
                    (Path(artifacts) / name).write_bytes(base64.b64decode(data))

            def visible(selector: str) -> bool:
                return cd.evaluate(f"(() => {{ const n = document.querySelector({selector!r}); return !!n && !!n.offsetParent; }})()")

            def no_overflow(label: str) -> None:
                assert cd.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), label + ': page overflows horizontally'

            cd.command('Page.navigate', {'url': url + '?role=careteam'})
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha' && document.querySelectorAll('#view-nav a').length === 7",
                    'care-team view with grouped navigation')
            # Every original section is still in the page, inside a panel and never duplicated.
            for section in EXPECTED_CARE_SECTIONS:
                assert cd.evaluate(f"document.querySelectorAll('#{section}').length === 1 && !!document.querySelector('#{section}').closest('.view-panel, #view-parking')"), section
            # All seven destinations stay directly in the sidebar (no "More" menu).
            assert cd.evaluate("document.querySelectorAll('#view-nav > a').length === 7 && !document.querySelector('#view-nav details')"), 'seven flat tabs'
            # Clinicians start on the cross-case worklist, then open a focused case workspace.
            cd.wait("!document.querySelector('#view-board').hidden && document.querySelectorAll('#view-worklist tbody tr').length === 2", 'clinician starts on the worklist')
            assert cd.evaluate("document.querySelector('#view-casebar').hidden"), 'no case header on the cross-case worklist'
            cd.evaluate("[...document.querySelectorAll('#view-worklist tbody tr')].find(r => r.textContent.includes('CASE-ALPHA')).querySelector('button').click()")
            cd.wait("!document.querySelector('#view-overview').hidden && !document.querySelector('#view-casebar').hidden && document.querySelector('#view-casebar').textContent.includes('CASE-ALPHA')",
                    'worklist opens the case under a persistent case header')
            assert visible('#assertions') and not visible('#investigations'), 'Overview tab shows facts, hides authoring'
            cd.evaluate("document.querySelector('#view-nav a[data-tab=investigations]').click()")
            cd.wait("!document.querySelector('#view-investigations').hidden && document.querySelector('#view-overview').hidden", 'Investigations tab')
            assert cd.evaluate("!!document.querySelector('#view-review #view-mission #patient-mission') && !document.querySelector('#view-mission').open"), \
                'Patient Mission kept, collapsed, in Review & changes'
            cd.evaluate("document.querySelector('#view-nav a[data-tab=board]').click()")
            cd.wait("!document.querySelector('#view-board').hidden && document.querySelectorAll('#incoming-list button').length === 2", 'Incoming board')
            cd.evaluate("[...document.querySelectorAll('#incoming-list .question')].find(r => r.textContent.includes('CASE-BETA')).querySelector('button').click()")
            cd.wait("document.querySelector('#case-heading').textContent === 'Fictional case Beta' && !document.querySelector('#view-overview').hidden", 'Open this case lands on its Overview')
            cd.evaluate("document.querySelector('#case-picker').value='CASE-ALPHA';document.querySelector('#case-picker').dispatchEvent(new Event('change'))")
            cd.wait("document.querySelector('#case-heading').textContent === 'Fictional case Alpha' && document.querySelectorAll('#assertion-list .finding').length === 5", 'back to Alpha')
            order = cd.evaluate("[...document.querySelector('#investigations').children].map(n => n.id || n.className)")
            assert order.index('model-investigation') < order.index('investigation-history') < order.index('view-manual-draft'), order
            assert cd.evaluate("!!document.querySelector('#view-manual-draft #draft-form') && !document.querySelector('#view-manual-draft').open"), \
                'hand-written draft form kept, collapsed'
            cd.evaluate("location.hash = '#assertions'")
            cd.wait("!document.querySelector('#view-overview').hidden", 'existing in-page link routes to its tab')
            no_overflow('care team 1440')

            def tab_from_picker() -> str:
                cd.evaluate("document.querySelector('#case-picker').focus()")
                for kind in ('keyDown', 'keyUp'):
                    cd.command('Input.dispatchKeyEvent', {'type': kind, 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                return cd.evaluate("(() => { const a = document.activeElement; return a.id === 'case-picker' ? 'stuck' : a.offsetParent ? 'visible' : 'hidden'; })()")
            assert tab_from_picker() == 'visible', 'care team: Tab leaves the case picker for a visible control'
            # Only pills repeating the global fictional-data banner are hidden.
            assert not visible('#incoming-board .panel-head .pill-warn'), 'duplicate FICTIONAL DEMO pill hidden'
            assert cd.evaluate("[...document.querySelectorAll('#options .panel-head .pill-warn')].some(p => p.textContent.includes('DISCUSSION ONLY') && getComputedStyle(p).display !== 'none')"), \
                'DISCUSSION ONLY boundary label stays visible'
            assert 'treatment recommendations' in cd.evaluate("document.querySelector('.main > footer').innerText"), 'footer keeps the boundary statement'
            # Inspector opened after scrolling keeps its title and Close button on screen.
            cd.evaluate("document.querySelector('#view-nav a[data-tab=records]').click()")
            cd.evaluate('scrollTo(0, 700)')
            cd.evaluate("[...document.querySelectorAll('#source-list button')].find(b => b.offsetParent).click()")
            cd.wait("document.querySelector('#source-dialog').open", 'source inspector after scrolling')
            assert cd.evaluate("document.querySelector('#source-dialog').getBoundingClientRect().top >= 0 && document.querySelector('#dialog-close').getBoundingClientRect().top >= 0"), \
                'inspector top and Close button are on screen'
            cd.evaluate("document.querySelector('#dialog-close').click(); scrollTo(0, 0)")

            # Existing workflow: question -> recorded replay -> draft citing PATH-ALPHA v1.
            cd.evaluate("document.querySelector('#question-text').value='Was Marker A tested, and what did it show?';document.querySelector('#question-form').requestSubmit()")
            cd.wait("document.querySelector('#composer-context-fingerprint').value.length===64 && !document.querySelector('#model-investigation-run').disabled", 'composer context')
            cd.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
            cd.wait("document.querySelectorAll('#model-investigation-list .snapshot').length===1", 'recorded replay')
            cd.evaluate("[...document.querySelectorAll('#model-investigation-list button')].find(b=>b.textContent==='Prepare review draft').click()")
            cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===1", 'draft report')
            # Origin labels: a recorded replay is never presented as a live AI run.
            cd.wait("document.querySelector('#model-investigation-list .view-origin')?.textContent === 'Recorded replay · not a live AI run' && "
                    "(document.querySelector('#snapshot-list .view-origin')?.textContent || '').startsWith('Draft from a recorded replay')", 'honest origin labels')

            # Side-by-side demo mode: a patient window with ?live=1 stays open while the
            # corrected report arrives elsewhere through the existing import API.
            cd.command('Page.navigate', {'url': url + '?role=patient&live=1'})
            cd.wait("document.documentElement.dataset.viewRole === 'patient' && (document.querySelector('#pt-home .view-eyebrow')?.textContent || '').startsWith('Alpha')", 'patient demo window')
            assert not cd.evaluate("!!document.querySelector('#pt-home .view-change')"), 'no change shown before the amendment'
            request = Request(url + 'api/cases/CASE-ALPHA/imports', data=json.dumps({'text': AMENDED}).encode(), headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=5) as response:
                assert json.load(response)['result'] == 'imported'
            cd.wait("!!document.querySelector('#pt-home .view-change')", 'live patient window picks up the amendment without a reload')
            cd.evaluate("document.querySelector('.view-role-group button[data-role=careteam]').click()")
            cd.wait("document.querySelectorAll('#view-nav a').length === 7", 'care-team view')
            cd.wait("(document.querySelector('#view-worklist tbody tr')?.textContent || '').includes('Source amended')", 'worklist lists the case needing reassessment first')
            cd.wait("document.querySelector('#review-attention').dataset.state === 'needs-review' && !!document.querySelector('#view-compare-changed:not([hidden])')",
                    'needs-review offers a direct comparison')
            cd.evaluate("location.hash = '#overview'")
            shot('careteam-needs-review.png')
            cd.evaluate("document.querySelector('#view-compare-changed').click()")
            cd.wait("document.querySelector('#compare-dialog').open && document.body.classList.contains('view-inspector-open')", 'comparison docked as inspector')
            assert not cd.evaluate("document.querySelector('#compare-dialog').matches(':modal')"), 'inspector must not block the workspace'
            cd.wait("!document.querySelector('#view-review').hidden", 'Review & changes tab beside the inspector')
            assert 'PATH-ALPHA' in cd.evaluate("document.querySelector('#compare-title').textContent")
            no_overflow('care team with inspector')
            shot('careteam-inspector.png')
            cd.evaluate("document.querySelector('#compare-close').click()")
            cd.wait("!document.querySelector('#compare-dialog').open && !document.body.classList.contains('view-inspector-open')", 'inspector closes')

            # Patient view: same record, read-only regrouping.
            cd.evaluate("document.querySelector('.view-role-group button[data-role=patient]').click()")
            cd.wait("document.documentElement.dataset.viewRole === 'patient' && document.querySelectorAll('#view-nav a').length === 4", 'patient view')
            cd.wait("document.querySelector('#pt-home .view-change')?.textContent.includes('Marker A')", 'patient sees what changed')
            change = cd.evaluate("document.querySelector('#pt-home .view-change').textContent")
            assert 'Not reported' in change and 'Negative' in change, change
            assert 'The earlier summary needs another look' in change, 'plain wording for an amended report'
            assert cd.evaluate("document.querySelector('#pt-home .view-primary').textContent") == 'See what changed'
            assert cd.evaluate("[...document.querySelectorAll('#pt-next li')].some(li => li.textContent.includes('Reopened'))"), 'next-conversation list shows the reopened question'
            assert cd.evaluate("!!document.querySelector('#view-parking #investigations') && !!document.querySelector('#view-parking #options')"), 'care-team tools parked, not removed'
            assert not visible('#investigations') and visible('#pt-home'), 'patient sees no authoring tools'
            assert not cd.evaluate("!document.querySelector('#notice').hidden && document.querySelector('#notice').textContent.includes('while you were editing')"), \
                'care-team draft warning is not shown to the patient'
            assert cd.evaluate("!!document.querySelector('#view-questions #pt-next')"), 'My questions holds the next-conversation list'
            no_overflow('patient 1440')
            shot('patient-home.png')
            cd.evaluate("document.querySelector('#view-nav a[data-tab=reports]').click()")
            cd.wait("!document.querySelector('#view-reports').hidden && !!document.querySelector('#pt-results .view-table button')", 'My records lists results')
            cd.evaluate("document.querySelector('#pt-results .view-table button').click()")
            cd.wait("document.querySelector('#source-dialog').open && !!document.querySelector('#dialog-text mark.source-highlight')", 'patient opens the exact source line')
            cd.evaluate("document.querySelector('#dialog-close').click()")

            cd.command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
            cd.wait('window.innerWidth === 390', 'mobile viewport')
            no_overflow('patient 390')
            shot('patient-mobile.png')
            cd.evaluate("document.querySelector('.view-role-group button[data-role=careteam]').click()")
            cd.wait("document.querySelectorAll('#view-nav a').length === 7", 'back to care team')
            no_overflow('care team 390')
            cd.command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})

            def post(path: str, payload: dict) -> dict:
                req = Request(url + path.lstrip('/'), data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
                with urlopen(req, timeout=5) as response:
                    return json.load(response)

            def load(role: str) -> None:
                cd.command('Page.navigate', {'url': url + '?role=' + role})
                cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha' && document.querySelectorAll('#view-nav a').length > 0", role + ' reload')

            load('patient')
            assert tab_from_picker() != 'stuck', 'patient: Tab is not trapped on the case picker'

            # A second correction after the first was reviewed: the comparison and the
            # patient summary must follow the newest change, including added/removed results.
            state = json.load(urlopen(url + 'api/cases/CASE-ALPHA/state', timeout=5))
            question = next(q for q in state['questions'] if q['state'] == 'open')
            current = [s['id'] for s in state['sources'] if s['state'] == 'current']
            snapshot = post('/api/cases/CASE-ALPHA/snapshots', {'question_id': question['id'], 'summary': 'Fictional reviewed draft.', 'source_ids': current})['snapshot_id']
            post(f'/api/cases/CASE-ALPHA/snapshots/{snapshot}/review', {'reviewer_label': 'Synthetic reviewer'})
            assert post('/api/cases/CASE-ALPHA/imports', {'text': IMAGING_AMENDED})['result'] == 'imported'
            load('careteam')
            cd.wait("document.querySelector('#review-attention').dataset.state === 'needs-review' && !!document.querySelector('#view-compare-changed:not([hidden])')", 'second amendment needs review')
            label = cd.evaluate("document.querySelector('#view-compare-changed').textContent")
            assert 'IMG-ALPHA' in label, 'compare targets the newest correction, not the reviewed one: ' + label
            load('patient')
            cd.wait("document.querySelector('#pt-home .view-change')?.textContent.includes('IMG-ALPHA')", 'patient sees the imaging correction')
            box = cd.evaluate("document.querySelector('#pt-home .view-change').innerText")
            assert 'New lesion' in box and 'New in the corrected report' in box, box
            assert 'Comparison' in box and 'No longer in the corrected report' in box, box
            assert 'PATH-ALPHA' not in cd.evaluate("[...document.querySelectorAll('#pt-home .view-change')].map(b => b.textContent).join(' ')"), \
                'reviewed correction no longer listed as new'
            print('PASS: grouped care-team tabs keep every original section; live patient window picks up the amendment; '
                  'needs review -> docked v1/v2 comparison; '
                  'patient view shows the change, results and reopened question read-only; no horizontal overflow at 1440/390.')
        except Exception:
            if cd:
                print('BROWSER_DIAGNOSTIC', cd.evaluate("JSON.stringify({role:document.documentElement.dataset.viewRole,state:document.body.dataset.workspaceState,notice:document.querySelector('#notice')?.textContent,hash:location.hash})"))
            raise
        finally:
            if cd: cd.close()
            if browser:
                try: os.killpg(browser.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError): pass
                try: browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(browser.pid, signal.SIGKILL); browser.wait(timeout=5)
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)


if __name__ == '__main__':
    main()
