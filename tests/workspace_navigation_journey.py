"""Real-browser navigation of the connected, fictional-only workspace.

Run with PYTHONPATH=src and an existing Chrome/Chromium on PATH. The connected
launcher seeds the repository's Alpha/Beta fixtures; all model work uses the
existing offline replay. No extra browser package or external service is used.

OI_UI_ARTIFACT_DIR selects screenshots, browser/server logs, and the JSON report.
Set OI_UI_STANDARD_SMOKE=1 to also check the original seeded stdlib launcher,
which does not compose the connected intake nodes.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
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
VISIBLE = """element => !!element && !element.closest('[hidden]') &&
  element.getClientRects().length > 0 &&
  getComputedStyle(element).display !== 'none' &&
  getComputedStyle(element).visibility !== 'hidden'"""
NAV_LINKS = '#workspace-nav a[href], #chart-nav a[href], #section-nav a[href]'
PROFESSIONAL_FORMS = (
    '#draft-form', '#model-investigation-form', '#evidence-assessment-form',
    '#evidence-withdraw-form', '#option-form', '#option-dependency-form',
    '#option-task-form', '#option-threat-form', '#option-review-form',
)


class ObservedChromeSession(ChromeSession):
    """Keep real runtime errors which the shared command helper otherwise skips."""

    def __init__(self, websocket_url: str):
        self.browser_errors: list[dict] = []
        super().__init__(websocket_url)

    def receive_frame(self) -> bytes | None:
        data = super().receive_frame()
        if data:
            message = json.loads(data)
            method, params = message.get('method'), message.get('params', {})
            if method == 'Runtime.exceptionThrown':
                self.browser_errors.append({'event': method, 'details': params.get('exceptionDetails')})
            elif method == 'Runtime.consoleAPICalled' and params.get('type') == 'error':
                self.browser_errors.append({'event': method, 'arguments': params.get('args', [])})
            elif method == 'Log.entryAdded':
                entry = params.get('entry', {})
                if entry.get('level') == 'error' and entry.get('source') == 'javascript':
                    self.browser_errors.append({'event': method, 'details': entry})
        return data


class Journey:
    def __init__(self, cd: ObservedChromeSession, url: str, output: Path,
                 downloads: Path, report: dict, mode: str):
        self.cd, self.url, self.output = cd, url, output
        self.downloads, self.report, self.mode = downloads, report, mode

    def js(self, body: str):
        return self.cd.evaluate(f'(() => {{ const visible = {VISIBLE}; {body} }})()')

    def check(self, condition: bool, label: str, details=None) -> None:
        entry = {'mode': self.mode, 'check': label, 'passed': bool(condition)}
        if details is not None:
            entry['details'] = details
        self.report['checks'].append(entry)
        if not condition:
            raise AssertionError(label + (f': {details}' if details is not None else ''))

    def visible(self, selector: str) -> bool:
        return self.js(f'return visible(document.querySelector({json.dumps(selector)}));')

    def read(self, path: str):
        with urlopen(self.url + path.lstrip('/'), timeout=5) as response:
            return json.load(response)

    def state(self, case_id: str = 'CASE-ALPHA') -> dict:
        return self.read(f'api/cases/{case_id}/state')

    def viewport(self, width: int) -> None:
        self.cd.command('Emulation.setDeviceMetricsOverride', {
            'width': width, 'height': 844 if width < 768 else 1000,
            'deviceScaleFactor': 1, 'mobile': False,
        })
        self.cd.wait(f'innerWidth === {width}', f'{width}px viewport')
        # CDP can acknowledge metrics before the media-query change event runs.
        # Let the browser render the resized navigation before testing its real
        # pointer and keyboard reachability, including when the hash is unchanged.
        self.cd.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

    def capture(self, name: str) -> None:
        self.cd.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        shot = self.cd.command('Page.captureScreenshot', {
            'format': 'png', 'captureBeyondViewport': False,
        })
        filename = f'navigation-{self.mode}-{name}.png'
        (self.output / filename).write_bytes(base64.b64decode(shot['data']))
        self.report['screenshots'].append(filename)

    def key(self, key: str, code: int) -> None:
        self.cd.command('Input.dispatchKeyEvent', {
            'type': 'keyDown', 'key': key, 'code': key, 'windowsVirtualKeyCode': code,
        })
        self.cd.command('Input.dispatchKeyEvent', {
            'type': 'keyUp', 'key': key, 'code': key, 'windowsVirtualKeyCode': code,
        })

    def click_expression(self, expression: str, label: str) -> None:
        point = self.js(f"""
          const target = ({expression});
          if (!visible(target)) return {{visible:false}};
          target.scrollIntoView({{block:'center', inline:'nearest', behavior:'instant'}});
          const r = target.getBoundingClientRect();
          const x = r.left + r.width / 2, y = r.top + r.height / 2;
          const hit = document.elementFromPoint(x, y);
          return {{visible:true, x, y, hit:hit === target || target.contains(hit)}};
        """)
        self.check(point.get('visible') and point.get('hit'), f'{label} is reachable by pointer', point)
        for event in ('mousePressed', 'mouseReleased'):
            self.cd.command('Input.dispatchMouseEvent', {
                'type': event, 'x': point['x'], 'y': point['y'],
                'button': 'left', 'clickCount': 1,
            })

    def click(self, selector: str, label: str) -> None:
        self.click_expression(f'document.querySelector({json.dumps(selector)})', label)

    def fill(self, selector: str, text: str) -> None:
        self.check(self.visible(selector), f'{selector} is visible for editing')
        self.cd.evaluate(f"""(() => {{
          const input = document.querySelector({json.dumps(selector)});
          input.focus(); input.select();
        }})()""")
        if text:
            self.cd.command('Input.insertText', {'text': text})
        else:
            self.key('Backspace', 8)

    def select(self, selector: str, value: str) -> None:
        self.check(self.visible(selector), f'{selector} is visible for selection')
        self.cd.evaluate(f"""(() => {{
          const select = document.querySelector({json.dumps(selector)});
          const value = {json.dumps(value)};
          if (![...select.options].some(option => option.value === value))
            throw Error('Requested option is absent');
          select.value = value;
          select.dispatchEvent(new Event('change', {{bubbles:true}}));
        }})()""")

    def view(self, expected: str) -> None:
        self.cd.wait(f'document.body.dataset.view === {json.dumps(expected)}', f'{expected} route active')
        self.cd.wait(f"""(() => {{ const visible = {VISIBLE};
          return visible(document.querySelector('[data-workspace-view="{expected}"]'));
        }})()""", f'{expected} case content ready')
        state = self.js("""
          return {
            active:[...document.querySelectorAll('.workspace-view[data-workspace-view]')]
              .filter(visible).map(view => view.dataset.workspaceView),
            title:document.querySelector('#workspace-title')?.textContent.trim(),
            titleVisible:visible(document.querySelector('#workspace-title')),
            width:innerWidth, audience:document.documentElement.dataset.audience
          };
        """)
        self.check(state['active'] == [expected], f'{expected}: exactly one visible workspace', state)
        self.check(bool(state['title']) and state['titleVisible'], f'{expected}: visible page title')

    def go(self, route: str) -> None:
        self.cd.evaluate(f'location.hash = {json.dumps("#" + route)}')
        self.view('reports' if route.startswith('snapshot-') else route)

    def nav_links(self, selector: str) -> list[str]:
        return self.js(f"""return [...document.querySelectorAll({json.dumps(selector)})]
          .map(link => link.getAttribute('href')).filter(href => href?.startsWith('#'))
          .map(href => href.slice(1));""")

    def follow_nav(self, route: str) -> None:
        target = json.dumps('#' + route)
        links = f'[...document.querySelectorAll({json.dumps(NAV_LINKS)})]'
        if not self.js(f'return {links}.some(link => link.getAttribute("href") === {target} && visible(link));'):
            in_rail = self.js(f"""return [...document.querySelectorAll('#workspace-rail a[href]')]
              .some(link => link.getAttribute('href') === {target});""")
            if in_rail and self.visible('#menu-toggle'):
                self.click('#menu-toggle', 'Open navigation menu')
            elif self.visible('#chart-section-picker'):
                value = self.cd.evaluate(f"""[...document.querySelector('#chart-section-picker').options]
                  .find(option => option.value.replace(/^#/, '') === {json.dumps(route)})?.value""")
                if value:
                    self.select('#chart-section-picker', value)
                    self.view(route)
                    return
        self.click_expression(
            f'{links}.find(link => link.getAttribute("href") === {target} && visible(link))',
            f'Navigate to {route}',
        )
        self.view(route)

    def no_overflow(self, label: str) -> None:
        size = self.js("""
          const width = innerWidth, scroll = document.documentElement.scrollWidth;
          return {width, scroll, route:document.body.dataset.view,
            offenders:scroll > width + 1 ? [...document.querySelectorAll('body *')]
              .filter(visible).filter(e => e.getBoundingClientRect().right > width + 1)
              .slice(0, 8).map(e => e.id || e.tagName + '.' + e.className) : []};
        """)
        self.check(size['scroll'] <= size['width'] + 1, f'{label}: no page-level horizontal overflow', size)

    def open_case(self, case_id: str) -> None:
        self.click(f'#incoming-list [data-case-search*="{case_id}"] button', f'Open {case_id} worklist row')
        self.view('overview')
        label = 'Fictional case ' + case_id.removeprefix('CASE-').title()
        self.cd.wait(f'document.querySelector("#case-heading")?.textContent === {json.dumps(label)}', label)
        self.check(self.visible('#case-context'), 'Patient identity remains visible in the chart')

    def inspect_first_source(self, patient: bool = False) -> None:
        assertion = self.state()['assertions'][0]
        original = self.read(f'api/cases/CASE-ALPHA/sources/{assertion["source_version_id"]}')['text']
        selector = '#patient-findings .source-jump' if patient else '#assertion-list .source-jump'
        self.click(selector, 'Open the finding’s exact source')
        self.cd.wait("document.querySelector('#source-dialog').open && !!document.querySelector('#dialog-text mark.source-highlight')",
                     'exact source inspector')
        source = self.cd.evaluate("({text:document.querySelector('#dialog-text').textContent, highlight:document.querySelector('#dialog-text mark').textContent})")
        self.check(source['text'] == original, 'Source inspector preserves the complete original text')
        self.check(source['highlight'] == original.split('\n')[assertion['source_line'] - 1],
                   'Source inspector highlights the exact recorded source line')
        self.capture('patient-source' if patient else 'clinician-source')
        self.key('Escape', 27)
        self.cd.wait("!document.querySelector('#source-dialog').open", 'Escape closes source inspector')

    def draft_values(self) -> dict:
        return self.cd.evaluate("""({
          observations:document.querySelector('#draft-observations').value,
          summary:document.querySelector('#draft-summary').value,
          assumptions:document.querySelector('#draft-assumptions').value,
          question:document.querySelector('#question-choice').value,
          sources:[...document.querySelectorAll('#source-choice input:checked')].map(input => input.value)
        })""")

    def patient_only(self) -> None:
        self.check(self.cd.evaluate("document.documentElement.dataset.audience === 'patient'"),
                   'Patient presentation is explicitly selected')
        exposed = self.js(f"""return [...document.querySelectorAll({json.dumps(', '.join(PROFESSIONAL_FORMS))})]
          .filter(visible).map(element => element.id);""")
        self.check(not exposed, 'Patient presentation has no visible professional authoring forms', exposed)


@contextmanager
def browser_session(chrome: str, output: Path, report: dict, *, standard: bool = False):
    mode = 'standard' if standard else 'connected'
    with tempfile.TemporaryDirectory(prefix=f'oi-navigation-{mode}-', ignore_cleanup_errors=True) as directory:
        temporary = Path(directory)
        database, downloads = temporary / 'case.sqlite', temporary / 'downloads'
        downloads.mkdir()
        app_port, debug_port = free_port(), free_port()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        if standard:
            subprocess.run([sys.executable, '-m', 'open_intelligence', 'seed', '--db', str(database)],
                           cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
            command = [sys.executable, '-m', 'open_intelligence', 'serve', '--db', str(database), '--port', str(app_port)]
        else:
            command = [sys.executable, str(ROOT / 'run_open_intelligence.py'), '--with-examples',
                       '--db', str(database), '--port', str(app_port)]
        browser = cd = server = None
        with (output / f'navigation-{mode}-server.log').open('w') as server_log, \
             (output / f'navigation-{mode}-chromium.log').open('w') as browser_log:
            try:
                server = subprocess.Popen(command, cwd=ROOT, env=env, stdout=server_log, stderr=subprocess.STDOUT)
                url = f'http://127.0.0.1:{app_port}/'
                wait_for(lambda: urlopen(url, timeout=1).status == 200, f'{mode} fictional server')
                # Match the established ui_glance_journey flags; no downloaded dependencies.
                flags = [chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage',
                         '--disable-background-networking', '--no-first-run', '--disable-extensions',
                         '--no-default-browser-check', '--remote-allow-origins=*',
                         f'--remote-debugging-port={debug_port}', f'--user-data-dir={temporary / "chrome"}']
                if hasattr(os, 'geteuid') and os.geteuid() == 0:
                    flags.append('--no-sandbox')
                browser = subprocess.Popen(flags + ['about:blank'], stdout=browser_log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                targets = wait_for(lambda: json.load(urlopen(
                    f'http://127.0.0.1:{debug_port}/json/list', timeout=1)), 'Chromium page target')
                cd = ObservedChromeSession(next(target['webSocketDebuggerUrl'] for target in targets
                                               if target.get('type') == 'page'))
                for domain in ('Page', 'Runtime', 'Log'):
                    cd.command(domain + '.enable')
                cd.command('Browser.setDownloadBehavior', {
                    'behavior': 'allow', 'downloadPath': str(downloads),
                })
                journey = Journey(cd, url, output, downloads, report, mode)
                journey.viewport(1440)
                cd.command('Page.navigate', {'url': url})
                cd.wait("document.body.classList.contains('ux-ready')", 'workspace presentation initialized')
                yield journey
                cd.evaluate('document.readyState')  # Drain pending runtime events before reporting.
                journey.check(not cd.browser_errors, 'No JavaScript exceptions or console errors', cd.browser_errors)
            except Exception:
                if cd:
                    try:
                        Journey(cd, url, output, downloads, report, mode).capture('failure')
                        diagnostic = cd.evaluate("""({url:location.href, body:document.body?.dataset,
                          audience:document.documentElement.dataset.audience,
                          title:document.querySelector('#workspace-title')?.textContent,
                          notice:document.querySelector('#notice')?.textContent})""")
                        report.setdefault('diagnostics', []).append({'mode': mode, **diagnostic})
                    except Exception as diagnostic_error:
                        report.setdefault('diagnostics', []).append({'mode': mode, 'error': str(diagnostic_error)})
                raise
            finally:
                if cd:
                    report['browser_errors'].extend({'mode': mode, **error} for error in cd.browser_errors)
                    cd.close()
                if browser:
                    try:
                        os.killpg(browser.pid, signal.SIGTERM)
                        browser.wait(timeout=5)
                    except ProcessLookupError:
                        pass
                    except subprocess.TimeoutExpired:
                        os.killpg(browser.pid, signal.SIGKILL)
                        browser.wait(timeout=5)
                if server:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)


def exercise_connected(j: Journey) -> None:
    j.view('incoming-board')
    j.cd.wait("document.querySelectorAll('#incoming-list [data-case-search]').length === 2", 'Alpha/Beta worklist')
    j.check(not j.visible('#case-context'), 'Global worklist is distinct from the active patient chart')
    j.check(j.visible('#case-search'), 'Worklist exposes case search')
    cases = j.read('api/cases')
    states = {case['case_id']: j.state(case['case_id']) for case in cases}
    expected_order = [case['case_id'] for case in sorted(cases, key=lambda case:
        max((source['event_date'] for source in states[case['case_id']]['sources']), default=''), reverse=True)]
    rows = j.cd.evaluate("[...document.querySelectorAll('#incoming-list [data-case-search]')].map(row => row.dataset.caseSearch)")
    j.check(all(case in row for case, row in zip(expected_order, rows)) and len(rows) == len(expected_order),
            'Worklist retains source-event recency ordering', {'expected': expected_order, 'rows': rows})
    j.fill('#case-search', 'beta')
    j.cd.wait("[...document.querySelectorAll('#incoming-list [data-case-search]')].filter(row => !row.hidden).length === 1", 'case search filters rows')
    j.check(j.js("return [...document.querySelectorAll('#incoming-list [data-case-search]')].filter(visible).every(row => row.textContent.includes('CASE-BETA'));"),
            'Case search matches the actual Beta row')
    j.check('1' in j.cd.evaluate("document.querySelector('#case-search-count').textContent"), 'Case search announces its result count')
    j.fill('#case-search', 'no-matching-fictional-case')
    j.cd.wait("!document.querySelector('#case-search-empty').hidden", 'case search empty state')
    j.check(not j.js("return [...document.querySelectorAll('#incoming-list [data-case-search]')].some(visible);"),
            'Unmatched case search exposes no case rows')
    j.fill('#case-search', '')
    j.cd.wait("[...document.querySelectorAll('#incoming-list [data-case-search]')].every(row => !row.hidden)", 'case search cleared')
    j.check(j.cd.evaluate("[...document.querySelectorAll('#incoming-list [data-case-search]')].map(row => row.dataset.caseSearch)") == rows,
            'Clearing search preserves the original worklist order')
    clinician_primary = j.nav_links('#workspace-nav a[href]')
    j.check({'incoming-board', 'bibliography', 'workspace-start'}.issubset(clinician_primary), 'Clinical global destinations remain available')
    j.capture('desktop-worklist')
    j.open_case('CASE-ALPHA')
    chart_primary = j.nav_links('#chart-nav a[href]')
    j.check(len(chart_primary) == 6 and len(set(chart_primary)) == 6, 'Patient chart has six distinct navigation groups', chart_primary)
    j.check(j.js("return [...document.querySelectorAll('#chart-nav a')].filter(visible).length === 6;"), 'All six chart groups are visible on desktop')
    j.capture('desktop-chart')
    j.follow_nav('assertions')
    j.check(j.visible('#section-nav') and len(j.nav_links('#section-nav a[href]')) > 1, 'Chart group exposes its section navigation')
    j.inspect_first_source()

    j.follow_nav('sources')
    j.fill('#document-search', 'PATH-ALPHA')
    j.cd.wait("[...document.querySelectorAll('#source-list .source-card')].filter(row => !row.hidden).length === 1", 'document search filters source versions')
    j.check('1' in j.cd.evaluate("document.querySelector('#document-search-count').textContent"), 'Document search announces its result count')
    j.fill('#document-search', 'no-matching-document')
    j.cd.wait("!document.querySelector('#document-search-empty').hidden", 'document empty state')
    j.fill('#document-search', '')
    j.cd.wait("[...document.querySelectorAll('#source-list .source-card')].every(row => !row.hidden)", 'all original documents restored')
    j.follow_nav('assertions')
    j.cd.evaluate('history.back()')
    j.view('sources')
    j.check(j.visible('#case-context'), 'Browser Back restores the previous chart page and patient context')
    before_skip = j.cd.evaluate("({hash:location.hash, route:document.body.dataset.view, caseId:document.querySelector('#case-picker').value})")
    j.key('Tab', 9)  # Establish keyboard focus visibility before reaching the skip control.
    j.cd.evaluate("document.querySelector('.skip-link').focus()")
    j.click('.skip-link', 'Skip to the current main content')
    j.cd.wait("document.activeElement.id === 'main-content'", 'skip link focuses main content')
    after_skip = j.cd.evaluate("({hash:location.hash, route:document.body.dataset.view, caseId:document.querySelector('#case-picker').value})")
    j.check(after_skip == before_skip, 'Skip link preserves the nondefault route, hash, and selected case', after_skip)
    j.check(j.cd.evaluate("document.activeElement.id === 'main-content'"), 'Skip link transfers keyboard focus to main content')

    question = 'Which pathology results need new review?'
    j.go('workspace-start')
    j.click_expression("[...document.querySelectorAll('#journey-steps a')].find(link => link.textContent === '3. Questions')", 'Follow connected progress step 3')
    j.view('questions')
    j.check(j.visible('#question-form'), 'Connected progress step 3 exposes the actual question form')
    j.fill('#question-text', question)
    j.click('#question-form button[type="submit"]', 'Persist a question')
    j.cd.wait(f'document.querySelector("#question-list").textContent.includes({json.dumps(question)})', 'question persisted')
    question_id = next(item['id'] for item in j.state()['questions'] if item['question'] == question)
    j.go('model-investigation-heading')
    j.select('#model-investigation-mode', 'replay')
    j.cd.wait("document.querySelector('#composer-context-fingerprint').value.length === 64 && !document.querySelector('#model-investigation-run').disabled", 'offline replay source context ready')
    j.click('#model-investigation-run', 'Run the existing offline replay')
    j.cd.wait("document.querySelectorAll('#model-investigation-list .snapshot').length === 1", 'replay investigation recorded')
    j.click_expression("[...document.querySelectorAll('#model-investigation-list button')].find(button => button.textContent === 'Prepare review draft')", 'Prepare a report from the replay')
    j.cd.wait("!!document.querySelector('#model-investigation-list a[href^=\"#snapshot-\"]')", 'generated report link')
    snapshot_hash = j.cd.evaluate("document.querySelector('#model-investigation-list a[href^=\"#snapshot-\"]').getAttribute('href')")
    snapshot_id = int(snapshot_hash.removeprefix('#snapshot-'))
    j.click('#model-investigation-list a[href^="#snapshot-"]', 'Follow the generated snapshot link')
    j.view('reports')
    j.check(j.visible(snapshot_hash), 'Generated snapshot link reveals the specific report')
    target = j.cd.evaluate(f"""(() => {{
      const target = document.querySelector({json.dumps(snapshot_hash)});
      const rect = target.getBoundingClientRect();
      return {{activeId:document.activeElement.id, top:rect.top, bottom:rect.bottom, viewport:innerHeight}};
    }})()""")
    j.check(target['activeId'] == snapshot_hash[1:], 'Generated snapshot link immediately focuses its exact report', target)
    j.check(0 <= target['top'] < target['viewport'] and target['bottom'] > 0,
            'Generated snapshot link scrolls the report into the viewport', target)
    j.check(next(item for item in j.state()['snapshots'] if item['id'] == snapshot_id)['state'] == 'draft',
            'Preparing and opening a report does not acknowledge its review')
    j.capture('desktop-report')
    j.go('workspace-start')
    j.click_expression("[...document.querySelectorAll('#journey-steps a')].find(link => link.textContent === '5. Review & updates')", 'Follow connected progress step 5')
    j.view('reports')
    j.check(j.visible(snapshot_hash), 'Connected progress step 5 exposes the actual saved report')

    j.go('questions')
    second_question = 'Second synthetic investigation question for binding verification?'
    j.fill('#question-text', second_question)
    j.click('#question-form button[type="submit"]', 'Persist a second question')
    j.cd.wait("document.querySelectorAll('#question-list .question').length === 2", 'two distinct questions')
    j.go('investigations')
    j.select('#question-choice', str(question_id))
    j.fill('#draft-observations', 'The selected source versions are retained for this unfinished draft.')
    j.fill('#draft-summary', 'This unfinished Alpha-only draft must keep the same question and original sources.')
    j.fill('#draft-assumptions', 'This draft must remain bound to CASE-ALPHA.')
    j.cd.evaluate("""[...document.querySelectorAll('#source-choice input')].forEach((input, index) => {
      input.checked = index === 0; input.dispatchEvent(new Event('change', {bubbles:true}));
    })""")
    unfinished = j.draft_values()
    j.go('sources')
    j.go('investigations')
    j.check(j.draft_values() == unfinished, 'Text, question, and source bindings survive chart navigation')
    j.capture('desktop-unfinished-draft')

    j.select('#presentation-view', 'patient')
    j.view('patient-home')
    j.patient_only()
    patient_primary = j.nav_links('#workspace-nav a[href]')
    j.check({'patient-home', 'patient-view', 'sources', 'questions', 'changes-since-review'}.issubset(patient_primary),
            'Patient primary destinations remain available', patient_primary)
    j.capture('patient-home')
    j.follow_nav('patient-view')
    j.inspect_first_source(patient=True)
    j.go('reports')
    j.patient_only()
    review = j.js(f"""return [...document.querySelector({json.dumps(snapshot_hash)}).querySelectorAll('button')]
      .filter(button => button.textContent.includes('Demo review acknowledgment')).map(button => visible(button));""")
    j.check(review == [False], 'Patient reports retain the draft while hiding professional review acknowledgment', review)
    j.click_expression(f"[...document.querySelector({json.dumps(snapshot_hash)}).querySelectorAll('button')].find(button => button.textContent === 'Export with sources')", 'Export the source-linked report in patient presentation')
    downloaded = j.downloads / f'synthetic-investigation-{snapshot_id}.md'
    wait_for(lambda: downloaded.is_file(), 'browser report download')
    with urlopen(j.url + f'api/cases/CASE-ALPHA/snapshots/{snapshot_id}/export', timeout=5) as response:
        expected_export = response.read()
    j.check(downloaded.read_bytes() == expected_export, 'Browser export contains the unchanged canonical report bytes')
    j.check(next(item for item in j.state()['snapshots'] if item['id'] == snapshot_id)['state'] == 'draft',
            'Patient export does not change review state')
    j.capture('patient-report')
    j.select('#presentation-view', 'clinician')
    j.view('incoming-board')
    j.go('investigations')
    j.check(j.draft_values() == unfinished, 'Unfinished draft and bindings survive both presentation switches')
    j.select('#case-picker', 'CASE-BETA')
    j.cd.wait("document.querySelector('#case-picker').value === 'CASE-ALPHA'", 'original dirty-case veto')
    j.check(j.draft_values() == unfinished, 'Dirty-case veto preserves the Alpha draft')
    j.check(j.visible('#notice') and 'Save or explicitly clear the unfinished investigation draft, question or pasted record, or discard the selected source before switching cases.'
            in j.cd.evaluate("document.querySelector('#notice').textContent"),
            'Unfinished-draft veto remains visibly explained while the case switch is blocked')
    j.go('incoming-board')
    j.click('#incoming-list [data-case-search*="CASE-BETA"] button', 'Attempt Beta from a dirty worklist')
    j.view('incoming-board')
    j.check(j.cd.evaluate("document.querySelector('#case-picker').value === 'CASE-ALPHA'"), 'Worklist respects the existing case-change veto')
    j.go('investigations')
    j.check(j.draft_values() == unfinished, 'Vetoed worklist navigation retains all unfinished content')
    for selector in ('#draft-observations', '#draft-summary', '#draft-assumptions'):
        j.fill(selector, '')
    j.go('incoming-board')
    j.open_case('CASE-BETA')
    j.cd.wait("document.querySelector('#notice').hidden", 'resolved switch-veto notice removed after Beta loads')
    j.check(not j.visible('#notice'), 'Successful switch after clearing the draft removes the resolved veto notice')
    j.cd.wait("document.querySelectorAll('#source-list .source-card').length === 1", 'Beta-only sources')
    text = j.cd.evaluate("['assertion-list','source-list','patient-findings','timeline-events','snapshot-list'].map(id => document.getElementById(id).textContent).join(' | ')")
    j.check('PATH-BETA' in text and 'PATH-ALPHA' not in text and 'IMG-ALPHA' not in text,
            'Successful case switch isolates rendered source provenance')
    j.check(j.cd.evaluate("document.querySelectorAll('#snapshot-list .snapshot').length === 0"), 'Beta does not retain Alpha reports')
    j.go('incoming-board')
    j.open_case('CASE-ALPHA')
    j.cd.wait(f'!!document.querySelector({json.dumps(snapshot_hash)})', 'Alpha report restored')

    for width in (320, 390, 768, 1024, 1440):
        j.viewport(width)
        j.go('incoming-board')
        if j.visible('#menu-toggle'):
            j.cd.wait("document.querySelector('#workspace-rail').hidden", 'closed responsive rail')
            j.click('#menu-toggle', 'Open responsive rail')
            j.cd.wait("!document.querySelector('#workspace-rail').hidden && document.querySelector('#menu-toggle').getAttribute('aria-expanded') === 'true'", 'open responsive navigation')
            j.click('#menu-toggle', 'Close responsive rail')
            j.cd.wait("document.querySelector('#workspace-rail').hidden && document.querySelector('#menu-toggle').getAttribute('aria-expanded') === 'false'", 'closed rail leaves the tab order')
            j.cd.evaluate("document.querySelector('#menu-toggle').focus()")
            for _ in range(10):
                j.key('Tab', 9)
                j.check(j.cd.evaluate("!document.activeElement.closest('#workspace-rail')"), f'{width}px: Tab cannot enter the closed rail')
            # Finish this keyboard subtest at a known control before the pointer
            # journey. Its fixed Tab count can wrap onto the focused skip link,
            # which correctly appears above the menu until focus moves away.
            j.cd.evaluate("document.querySelector('#menu-toggle').focus()")
        for route in dict.fromkeys(clinician_primary):
            j.follow_nav(route)
            j.no_overflow(f'{width}px clinician {route}')
        j.follow_nav('incoming-board')
        j.capture(f'{width}-worklist')
        j.open_case('CASE-ALPHA')
        for route in chart_primary:
            j.follow_nav(route)
            j.no_overflow(f'{width}px chart {route}')
        j.go('incoming-board')
        j.select('#presentation-view', 'patient')
        j.view('patient-home')
        j.capture(f'{width}-patient-home')
        for route in dict.fromkeys(patient_primary):
            j.follow_nav(route)
            if route == 'workspace-start':
                j.check(j.cd.evaluate("document.documentElement.dataset.audience === 'clinician'"),
                        'Explicit clinical setup link leaves patient presentation')
                j.no_overflow(f'{width}px clinical setup from patient tools')
                j.select('#presentation-view', 'patient')
                j.view('patient-home')
            else:
                j.patient_only()
                j.no_overflow(f'{width}px patient {route}')
        j.select('#presentation-view', 'clinician')
        j.view('incoming-board')

    exercise_option_disclosures(j, snapshot_id)


def exercise_option_disclosures(j: Journey, snapshot_id: int) -> None:
    """Submit the existing five Options forms through their native disclosures."""
    j.go('options')
    before = j.state()
    source = next(item for item in before['sources']
                  if item['document_id'] == 'PATH-ALPHA' and item['state'] == 'current')
    j.check(j.cd.evaluate("document.querySelectorAll('#options details.contextual-form').length === 5"),
            'Options contains the five existing contextual form disclosures')

    def summary(form: str) -> str:
        return f'document.querySelector({json.dumps(form)}).closest("details.contextual-form").querySelector("summary")'

    def open_form(form: str) -> None:
        j.check(j.cd.evaluate(f'!document.querySelector({json.dumps(form)}).closest("details").open'),
                f'{form}: starts collapsed')
        j.click_expression(summary(form), f'Open {form} by its summary')
        j.check(j.js(f"""const form = document.querySelector({json.dumps(form)});
          return form.closest('details').open && visible(form) &&
            [...form.querySelectorAll('input, select, textarea, button')].every(visible);"""),
                f'{form}: disclosed controls are visible')

    def invalid_submit(form: str, field: str, validity: str = 'valueMissing') -> None:
        previous = j.state()['options']
        j.click(form + ' button[type="submit"]', f'Try native validation in {form}')
        j.check(j.cd.evaluate(f"""document.activeElement.id === {json.dumps(field[1:])} &&
          document.querySelector({json.dumps(field)}).validity[{json.dumps(validity)}]"""),
                f'{form}: native validation focuses the invalid visible control')
        j.check(j.state()['options'] == previous,
                f'{form}: invalid submission does not change canonical option state')

    def submit(form: str, expected_text: str) -> dict:
        j.check(j.cd.evaluate(f'document.querySelector({json.dumps(form)}).checkValidity()'),
                f'{form}: completed values satisfy native validation')
        j.click(form + ' button[type="submit"]', f'Submit {form}')
        j.cd.wait(f'document.querySelector("#option-list").textContent.includes({json.dumps(expected_text)})',
                  f'{form} result rendered')
        j.check(j.visible('#option-list'), f'{form}: canonical result is visible in the option list')
        j.click_expression(summary(form), f'Close completed {form}')
        return j.state()['options'][0]

    open_form('#option-form')
    invalid_submit('#option-form', '#option-label')
    j.select('#option-snapshot-choice', str(snapshot_id))
    j.fill('#option-label', 'Fictional discussion item A')
    j.fill('#option-description', 'A fictional item discussed for planning purposes only.')
    j.select('#option-epistemic', 'unknown')
    option = submit('#option-form', 'Fictional discussion item A')
    option_id = option['id']
    j.check(option['snapshot_id'] == snapshot_id and option['epistemic_status'] == 'unknown'
            and option['operational_status'] == 'proposed',
            'Option proposal keeps its saved-report association, uncertainty, and proposed status')

    open_form('#option-dependency-form')
    j.select('#dependency-option-choice', str(option_id))
    j.select('#dependency-kind', 'source')
    j.select('#dependency-source-choice', str(source['id']))
    j.fill('#dependency-lead', '-1')
    invalid_submit('#option-dependency-form', '#dependency-lead', 'rangeUnderflow')
    j.fill('#dependency-lead', '2')
    option = submit('#option-dependency-form', 'source: PATH-ALPHA@1')
    dependency = option['dependencies'][0]
    j.check(len(option['dependencies']) == 1 and dependency['source_version_id'] == source['id']
            and dependency['kind'] == 'source' and dependency['lead_time_days'] == 2
            and dependency['deadline_date'] is None and dependency['deadline_basis'] == 'unknown',
            'Source dependency retains the exact original source and an unknown deadline')

    open_form('#option-task-form')
    invalid_submit('#option-task-form', '#task-label')
    j.select('#task-option-choice', str(option_id))
    j.fill('#task-label', 'Fictional preparation step')
    j.fill('#task-owner', 'Synthetic owner')
    j.fill('#task-lead', '3')
    option = submit('#option-task-form', 'Fictional preparation step')
    task = option['preparation_tasks'][0]
    j.check(len(option['preparation_tasks']) == 1 and task['owner_label'] == 'Synthetic owner'
            and task['status'] == 'not_started' and task['lead_time_days'] == 3,
            'Preparation task records its fictional human owner and untouched task status')

    open_form('#option-threat-form')
    invalid_submit('#option-threat-form', '#threat-description')
    j.select('#threat-option-choice', str(option_id))
    j.select('#threat-kind', 'expiring_window')
    j.fill('#threat-description', 'A fictional window may close at an unknown date.')
    option = submit('#option-threat-form', 'A fictional window may close at an unknown date.')
    threat = option['threats'][0]
    j.check(len(option['threats']) == 1 and threat['kind'] == 'expiring_window'
            and threat['threat_date'] is None and threat['threat_basis'] == 'unknown',
            'Optionality threat preserves its explicitly unknown date')

    open_form('#option-review-form')
    invalid_submit('#option-review-form', '#reviewer-label')
    j.select('#review-option-choice', str(option_id))
    j.fill('#reviewer-label', 'Synthetic reviewer')
    j.select('#review-action', 'abstain')
    scope = 'Abstaining on this discussion item for now.'
    j.fill('#review-scope', scope)
    j.capture('options-review-disclosure')
    option = submit('#option-review-form', 'abstain by Synthetic reviewer')
    review = option['review_events'][0]
    j.check(len(option['review_events']) == 1 and review['action'] == 'abstain'
            and review['reviewer_label'] == 'Synthetic reviewer' and review['scope'] == scope
            and review['snapshot_id'] == snapshot_id and option['operational_status'] == 'proposed',
            'Abstention records fictional actor, scope, and report without approving the option')
    after = j.state()
    j.check(after['sources'] == before['sources'] and
            {item['id']: item['state'] for item in after['snapshots']} ==
            {item['id']: item['state'] for item in before['snapshots']},
            'Options form submissions preserve canonical sources and report review states')
    j.check(not j.state('CASE-BETA')['options'], 'Alpha option submissions remain isolated from Beta')
    j.no_overflow('Desktop Options after all five form submissions')
    j.cd.evaluate("document.querySelector('#option-list').scrollIntoView({block:'center'})")
    j.capture('options-result')


def exercise_standard(j: Journey) -> None:
    j.view('incoming-board')
    j.cd.wait("document.querySelectorAll('#incoming-list [data-case-search]').length === 2", 'standard seeded worklist')
    j.check(j.cd.evaluate("!document.querySelector('#case-create-form') && !document.querySelector('#source-upload-form')"),
            'Standard launcher is exercised without connected intake forms')
    j.open_case('CASE-ALPHA')
    j.go('assertions')
    j.inspect_first_source()
    j.go('overview')
    j.no_overflow('Standard desktop chart')
    j.capture('desktop-smoke')


def main() -> None:
    output = Path(os.environ.get('OI_UI_ARTIFACT_DIR', ROOT / '.ui-artifacts' / 'navigation'))
    output.mkdir(parents=True, exist_ok=True)
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'data': 'Existing, independently authored Alpha/Beta fictional fixtures only',
              'checks': [], 'screenshots': [], 'browser_errors': []}
    try:
        chrome = next((path for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                       if (path := shutil.which(name))), None)
        if not chrome:
            raise AssertionError('Chromium unavailable: workspace navigation is not verified')
        report['chrome'] = chrome
        with browser_session(chrome, output, report) as journey:
            exercise_connected(journey)
        if os.environ.get('OI_UI_STANDARD_SMOKE', '').lower() in ('1', 'true'):
            with browser_session(chrome, output, report, standard=True) as journey:
                exercise_standard(journey)
    except Exception as error:
        report['failure'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        (output / 'workspace-navigation-verification.json').write_text(
            json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'checks': len(report['checks']), 'screenshots': report['screenshots'],
                          'browser_errors': report['browser_errors'], 'failure': report.get('failure')}))


if __name__ == '__main__':
    main()
