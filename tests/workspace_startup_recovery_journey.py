"""Real-browser recovery of the first roster read and initial creation.

Only selected GET outcomes are delayed or failed before a fresh document loads.
Successful reads and all writes use the actual application/server. Existing
fictional fixtures and independently authored fictional text are the only data.
OI_STARTUP_SCENARIOS selects a focused subset; the default executes all scenarios.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.request import Request, urlopen

from workspace_navigation_journey import ROOT, Journey, browser_session
from workspace_scope_recovery_journey import STRICT_VISIBLE


SOURCE = (
    'OI-SYNTHETIC-REPORT/1\nPatient: CASE-GAMMA\nDocument: STARTUP-GAMMA\n'
    'Type: pathology\nEvent-Date: 2026-08-03\nIssued-At: 2026-08-04\n'
    'Finding: workflow-note|not-assessed|Independently authored fictional startup café <literal> observation.\n'
)


def settle(j: Journey) -> None:
    j.cd.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


def ready(j: Journey, case_id: str = 'CASE-ALPHA') -> None:
    value = json.dumps(case_id)
    j.cd.wait(f'caseId === {value} && active?.case.case_id === {value} && renderedCaseId === {value}',
              case_id + ' canonical chart ready')
    settle(j)


def observe(j: Journey) -> dict:
    result = j.cd.evaluate(f"""(() => {{
      const visible={STRICT_VISIBLE};
      const region=document.querySelector('#workspace-startup');
      const retry=document.querySelector('#workspace-startup-retry');
      const picker=document.querySelector('#case-picker');
      const current=document.querySelector('[data-workspace-view="'+document.body.dataset.view+'"]');
      return {{caseId, active:active?.case.case_id || null, rendered:renderedCaseId,
        route:document.body.dataset.view, audience:document.documentElement.dataset.audience,
        regionVisible:visible(region), message:region?.textContent.trim() || '',
        busy:region?.getAttribute('aria-busy'), retryVisible:visible(retry),
        retryDisabled:retry?.disabled, retryInForm:Boolean(retry?.form),
        pickerDisabled:picker.disabled, options:[...picker.options].map(o=>o.value),
        selected:picker.value, viewVisible:visible(current),
        rows:[...document.querySelectorAll('#incoming-list [data-case-id]')].map(r=>r.dataset.caseId),
        notice:document.querySelector('#notice').textContent,
        probe:{{rosters:window.__startupProbe.rosters, posts:window.__startupProbe.posts,
          failures:window.__startupProbe.failures, states:window.__startupProbe.states}},
        creation:document.querySelector('#case-create-status')?.textContent || ''}};
    }})()""")
    j.report.setdefault('observations', []).append(result)
    return result


def load(j: Journey, *, failures: int = 0, mode: str = 'http', route: str = 'incoming-board') -> None:
    config = json.dumps({'remaining': failures, 'mode': mode})
    script = r"""(() => {
      const config=CONFIG, original=window.fetch.bind(window);
      const probe=window.__startupProbe={rosters:0, posts:0, failures:0, completed:0,
        states:{}, remaining:config.remaining, mode:config.mode, held:false, released:false};
      window.fetch=async (input,init) => {
        const path=new URL(typeof input==='string' ? input : input.url, location.href).pathname;
        const method=(init?.method || input?.method || 'GET').toUpperCase();
        if(path==='/api/cases' && method==='POST') probe.posts++;
        const state=path.match(/^\/api\/cases\/([^/]+)\/state$/);
        if(state && method==='GET') {
          probe.states[state[1]]=(probe.states[state[1]] || 0)+1;
          if(probe.failCanonical && state[1]==='CASE-ALPHA' && probe.states[state[1]]===2)
            return new Response(JSON.stringify({error:'controlled initial chart failure'}),
              {status:503,headers:{'Content-Type':'application/json'}});
        }
        if(path!=='/api/cases' || method!=='GET') return original(input,init);
        const number=++probe.rosters;
        try {
          if(number===1 && probe.mode.startsWith('hold')) {
            const response=await original(input,init);
            await response.clone().text();
            probe.held=true;
            await new Promise(resolve=>{probe.release=()=>{probe.released=true;resolve();};});
            if(probe.mode==='hold-failure') throw Error('PRIVATE-STARTUP-DETAIL');
            return response;
          }
          if(probe.remaining>0) {
            probe.remaining--;probe.failures++;
            if(probe.mode==='network') throw Error('PRIVATE-STARTUP-DETAIL');
            if(probe.mode==='malformed') return new Response(JSON.stringify({unexpected:'shape'}),
              {status:200,headers:{'Content-Type':'application/json'}});
            return new Response(JSON.stringify({error:'PRIVATE-STARTUP-DETAIL'}),
              {status:503,headers:{'Content-Type':'application/json'}});
          }
          return await original(input,init);
        } finally {probe.completed++;}
      };
      if(config.mode==='chart-failure') probe.failCanonical=true;
    })();""".replace('CONFIG', config)
    j.cd.command('Page.addScriptToEvaluateOnNewDocument', {'source': script})
    # A fragment-only navigation can reuse the initial document and skip the
    # new-document interceptor. The query forces a fresh app initialization.
    j.cd.command('Page.navigate', {'url': j.url + '?startup-recovery=1#' + route})
    j.cd.wait('!!window.__startupProbe && document.body.classList.contains("ux-ready")', 'fresh startup document')
    j.cd.wait('window.__startupProbe.rosters >= 1', 'first real startup roster request')
    if mode.startswith('hold'):
        j.cd.wait('window.__startupProbe.held', 'captured first roster response')
    else:
        j.cd.wait('window.__startupProbe.completed >= 1', 'initial roster outcome')
    settle(j)


def recovery_action(j: Journey, *, keyboard: bool = False) -> None:
    state = observe(j)
    j.check(state['regionVisible'] and state['retryVisible'] and state['retryDisabled'] is False,
            'An unavailable or empty startup has an actionable global recovery control', state)
    j.check(not state['retryInForm'], 'Startup recovery cannot submit an existing form')
    if keyboard:
        j.cd.evaluate("document.querySelector('#workspace-startup-retry').focus()")
        j.key('Enter', 13)
    else:
        j.click('#workspace-startup-retry', 'Retry or refresh startup through its visible control')


def expect_failed(j: Journey) -> None:
    state = observe(j)
    j.check(state['caseId'] is None and state['active'] is None,
            'A failed first roster read does not establish a selected record', state)
    j.check(state['regionVisible'] and state['retryVisible'] and state['retryDisabled'] is False,
            'First roster failure exposes visible in-app retry without a page reload', state)
    j.check(state['busy'] == 'false' and state['pickerDisabled'],
            'Failed startup ends loading and prevents selection from an unknown roster', state)
    j.check('PRIVATE-STARTUP-DETAIL' not in state['message'] + state['notice'],
            'Startup explains the unavailable list without echoing raw server or exception details')


def expect_initial_case(j: Journey, case_id: str, expected_options: list[str]) -> None:
    ready(j, case_id)
    state = observe(j)
    j.check(not state['regionVisible'], 'Successful startup removes only its recovery region', state)
    j.check(state['options'] == expected_options and len(state['options']) == len(set(state['options'])),
            'The accepted roster creates unique picker options in server order', state)
    j.check(state['selected'] == case_id and set(state['rows']) == set(expected_options),
            'Picker, ready chart and worklist agree with accepted initial selection', state)
    j.check(state['probe']['posts'] == 0, 'Startup retry and refresh perform no case-creation writes')


def initial_failure(j: Journey, *, mode: str = 'http', route: str = 'incoming-board', repeats: int = 1) -> None:
    load(j, failures=repeats, mode=mode, route=route)
    expect_failed(j)
    before = observe(j)
    for attempt in range(repeats):
        recovery_action(j, keyboard=attempt == 0)
        if attempt + 1 < repeats:
            j.cd.wait(f'window.__startupProbe.failures === {attempt + 2}', 'next failed startup attempt')
            settle(j)
            expect_failed(j)
    expect_initial_case(j, 'CASE-ALPHA', ['CASE-ALPHA', 'CASE-BETA'])
    after = observe(j)
    j.check(after['route'] == before['route'] and after['audience'] == before['audience'],
            'Startup recovery preserves the requested destination and presentation', {'before': before, 'after': after})
    j.check(after['probe']['rosters'] == repeats + 1, 'Each completed retry adds one roster read')
    j.go('overview')
    beta_before = j.cd.evaluate("window.__startupProbe.states['CASE-BETA'] || 0")
    j.cd.evaluate("document.querySelector('#case-picker').focus()")
    j.key('ArrowDown', 40)
    ready(j, 'CASE-BETA')
    j.check(j.cd.evaluate("window.__startupProbe.states['CASE-BETA']") == beta_before + 1,
            'A native case selection after recovery makes exactly one canonical state request')
    j.capture('startup-recovered')


def delayed_loading(j: Journey) -> None:
    load(j, mode='hold-success', route='patient-home')
    state = observe(j)
    j.check(state['regionVisible'] and state['busy'] == 'true' and state['retryDisabled'] is True,
            'A pending first roster is visibly loading and cannot be retried through a disabled control', state)
    j.check(state['pickerDisabled'] and not state['viewVisible'] and state['caseId'] is None,
            'A pending roster exposes neither a usable picker nor fabricated patient content', state)
    j.cd.evaluate("document.querySelector('#workspace-startup-retry').click()")
    j.check(j.cd.evaluate('window.__startupProbe.rosters') == 1, 'Disabled retry does not add a duplicate request')
    j.cd.evaluate('window.__startupProbe.release()')
    expect_initial_case(j, 'CASE-ALPHA', ['CASE-ALPHA', 'CASE-BETA'])
    j.check(observe(j)['route'] == 'patient-home', 'Delayed startup retains the patient destination')
    j.capture('startup-delayed-patient')


def open_creation(j: Journey) -> None:
    j.go('workspace-start')
    for selector in ('#workspace-start', '#new-case-panel'):
        if not j.cd.evaluate(f'document.querySelector({json.dumps(selector)}).open'):
            j.click(selector + ' > summary', 'Open the existing creation disclosure')


def enter_creation(j: Journey, code: str = 'CASE-GAMMA', alias: str = 'Gamma') -> None:
    open_creation(j)
    j.fill('#case-create-alias', alias)
    j.fill('#case-create-code', code)
    if not j.cd.evaluate("document.querySelector('#case-create-confirm').checked"):
        j.click('#case-create-confirm', 'Confirm independently authored fictional creation')


def creation_fields(j: Journey) -> dict:
    return j.cd.evaluate("""({alias:document.querySelector('#case-create-alias').value,
      code:document.querySelector('#case-create-code').value,
      confirmed:document.querySelector('#case-create-confirm').checked})""")


def create(j: Journey, code: str = 'CASE-GAMMA', alias: str = 'Gamma') -> None:
    enter_creation(j, code, alias)
    j.click('#case-create-submit', 'Create the actual fictional workspace')


def empty_recovery_creation(j: Journey) -> None:
    load(j, failures=1)
    expect_failed(j)
    enter_creation(j)
    before = creation_fields(j)
    recovery_action(j)
    j.cd.wait("document.body.dataset.workspaceState === 'empty'", 'proven empty workspace after retry')
    settle(j)
    state = observe(j)
    j.check(j.read('api/cases') == [] and state['caseId'] is None and not state['options'] and not state['rows'],
            'An empty state comes from a successful genuinely empty server roster', state)
    j.check(state['regionVisible'] and state['retryVisible'] and not state['retryDisabled'],
            'Empty connected setup retains an accessible list refresh control', state)
    j.check(creation_fields(j) == before, 'Failed-to-empty recovery retains all entered creation fields')
    j.click('#case-create-submit', 'Submit the retained fictional creation once')
    ready(j, 'CASE-GAMMA')
    j.cd.wait("document.body.dataset.view === 'source-intake'", 'original creation destination')
    j.check(j.read('api/cases') == [{'case_id': 'CASE-GAMMA', 'label': 'Fictional case Gamma', 'synthetic': 1}],
            'The first actual creation is persisted once')
    j.check(j.cd.evaluate('window.__startupProbe.posts') == 1, 'First creation performs one POST')
    source_path = j.output / 'independently-authored-startup-gamma.txt'
    source_path.write_bytes(SOURCE.encode('utf-8'))
    document = j.cd.command('DOM.getDocument')
    field = j.cd.command('DOM.querySelector', {'nodeId': document['root']['nodeId'], 'selector': '#source-file'})
    j.cd.command('DOM.setFileInputFiles', {'nodeId': field['nodeId'], 'files': [str(source_path)]})
    j.cd.wait("!document.querySelector('#source-preview-details').hidden", 'original source inspected')
    j.click('#source-upload-confirm', 'Confirm the independently authored source')
    j.click('#source-upload-submit', 'Import the actual original source after recovered startup')
    j.cd.wait("document.querySelectorAll('#source-list .source-card').length === 1", 'imported source rendered')
    state = j.state('CASE-GAMMA')
    j.check(len(state['sources']) == 1, 'Recovered first creation reaches the existing real source-intake flow')
    original = j.read('api/cases/CASE-GAMMA/sources/' + str(state['sources'][0]['id']))
    j.check(original['text'].encode('utf-8') == source_path.read_bytes(), 'Startup recovery preserves exact imported source bytes')
    j.capture('empty-recovery-intake')


def empty_external_creation(j: Journey) -> None:
    load(j)
    j.cd.wait("document.body.dataset.workspaceState === 'empty'", 'empty connected workspace')
    # A second client creates the workspace through the actual existing API.
    request = Request(j.url + 'api/cases', data=json.dumps({'case_id': 'CASE-DELTA', 'label': 'Fictional case Delta'}).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=5) as response:
        j.check(response.status in (200, 201), 'Another client really creates the new workspace')
    recovery_action(j)
    expect_initial_case(j, 'CASE-DELTA', ['CASE-DELTA'])
    j.capture('empty-refresh-discovery')


def creation_supersedes_initial(j: Journey, *, fail: bool = False) -> None:
    load(j, mode='hold-failure' if fail else 'hold-success')
    create(j)
    ready(j, 'CASE-GAMMA')
    j.cd.wait("document.body.dataset.view === 'source-intake'", 'created case intake destination')
    before = observe(j)
    j.check(before['probe']['posts'] == 1 and before['options'] == ['CASE-ALPHA', 'CASE-BETA', 'CASE-GAMMA'],
            'Creation starts a fresh roster read and activates the newly created case', before)
    j.cd.evaluate('window.__startupProbe.release()')
    j.cd.wait('window.__startupProbe.completed >= 2', 'obsolete startup result completed')
    settle(j)
    after = observe(j)
    j.check(after['caseId'] == after['active'] == after['rendered'] == after['selected'] == 'CASE-GAMMA',
            'Late initial success/error cannot replace the created case', after)
    j.check(after['options'] == before['options'] and after['rows'] == before['rows'] and
            not after['regionVisible'] and after['route'] == 'source-intake',
            'Late initial completion cannot duplicate options, regress the list or replace the current destination', after)
    j.check('PRIVATE-STARTUP-DETAIL' not in after['notice'] + after['message'],
            'An obsolete startup error is not presented after successful creation')
    j.capture('creation-wins-over-startup')


def saved_creation_failed_load(j: Journey) -> None:
    load(j)
    j.cd.wait("document.body.dataset.workspaceState === 'empty'", 'initial empty workspace')
    j.cd.evaluate('window.__startupProbe.remaining=1')
    create(j)
    j.cd.wait('window.__startupProbe.failures === 1', 'post-creation roster failure')
    j.cd.wait("!document.querySelector('#case-create-submit').disabled", 'creation callback settled')
    settle(j)
    expect_failed(j)
    before = observe(j)
    j.check(j.read('api/cases') == [{'case_id': 'CASE-GAMMA', 'label': 'Fictional case Gamma', 'synthetic': 1}],
            'Creation is durable even though activation failed')
    j.check('created' in before['creation'].lower() and 'retry' in before['creation'].lower(),
            'Creation feedback distinguishes a saved workspace from unavailable activation', before)
    recovery_action(j)
    ready(j, 'CASE-GAMMA')
    j.cd.wait("document.body.dataset.view === 'source-intake'", 'deferred creation activation completes intake navigation')
    after = observe(j)
    j.check(after['probe']['posts'] == 1 and len(j.read('api/cases')) == 1,
            'Activation retry does not repeat the successful creation write', after)
    j.check(not after['regionVisible'] and 'retry' not in after['creation'].lower(),
            'Successful activation clears its obsolete retry guidance', after)
    j.capture('saved-creation-recovered')


def unrelated_notice_and_ready_guard(j: Journey) -> None:
    load(j, failures=1)
    expect_failed(j)
    j.cd.evaluate("notice('Independent research-library status remains available.')")
    recovery_action(j)
    ready(j)
    j.check(observe(j)['notice'] == 'Independent research-library status remains available.',
            'Successful startup clears its own error without deleting another feature notice')
    j.go('questions')
    j.fill('#question-text', 'Keep this independently authored question while startup is already complete.')
    before = j.cd.evaluate('({caseId, active:active.case.case_id, sequence:refreshSequence, rosters:window.__startupProbe.rosters})')
    j.cd.evaluate('initialize()')
    settle(j)
    after = j.cd.evaluate('({caseId, active:active.case.case_id, sequence:refreshSequence, rosters:window.__startupProbe.rosters})')
    j.check(before == after and j.cd.evaluate("document.querySelector('#question-text').value").startswith('Keep this'),
            'Repeated initialization cannot refetch or reset an already ready chart and its unfinished question')
    j.go('overview')
    j.select('#case-picker', 'CASE-BETA')
    j.check(j.cd.evaluate("caseId === 'CASE-ALPHA' && document.querySelector('#case-picker').value === 'CASE-ALPHA'"),
            'The recovered owner preserves the existing unfinished-work case-switch veto')
    j.capture('startup-owner-preserved')


def initial_chart_failure(j: Journey) -> None:
    load(j, mode='chart-failure')
    j.cd.wait("window.__startupProbe.states['CASE-ALPHA'] === 2", 'initial canonical state failure after board summary')
    settle(j)
    state = observe(j)
    j.check(not state['regionVisible'] and state['caseId'] == 'CASE-ALPHA' and state['active'] is None,
            'Known roster availability remains separate from failed chart readiness', state)
    reads = state['probe']['rosters']
    j.go('incoming-board')
    j.click('#incoming-list [data-case-id="CASE-ALPHA"] button', 'Retry the initial unavailable chart through its original Open action')
    ready(j)
    j.check(j.cd.evaluate('window.__startupProbe.rosters') == reads,
            'Initial chart recovery reuses the canonical state owner without restarting the roster')
    j.capture('initial-chart-recovered')


def main() -> None:
    output = Path(os.environ.get('OI_STARTUP_ARTIFACT_DIR', ROOT / '.ui-artifacts' / 'startup')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    chrome = os.environ.get('OI_CHROME') or next((p for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                                                 if (p := shutil.which(name))), None)
    if not chrome:
        raise AssertionError('Chromium unavailable: startup recovery is not verified')
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'scenarios': [], 'chrome': chrome,
              'data': 'Independently authored fictional Alpha/Beta/Gamma/Delta only',
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'runtime_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in ('web/app.js', 'web/index.html', 'web/workspace-entry.js', 'web/intake.js')}}
    scenarios = [
        ('initial-failure-connected', initial_failure, False, True),
        ('repeated-failure', lambda j: initial_failure(j, repeats=2), False, True),
        ('network-failure-standard', lambda j: initial_failure(j, mode='network'), True, True),
        ('malformed-roster', lambda j: initial_failure(j, mode='malformed'), False, True),
        ('patient-deep-link', lambda j: initial_failure(j, route='patient-home'), False, True),
        ('delayed-loading', delayed_loading, False, True),
        ('empty-recovery-creation', empty_recovery_creation, False, False),
        ('empty-external-creation', empty_external_creation, False, False),
        ('late-initial-success', creation_supersedes_initial, False, True),
        ('late-initial-failure', lambda j: creation_supersedes_initial(j, fail=True), False, True),
        ('saved-creation-failed-load', saved_creation_failed_load, False, False),
        ('notice-and-ready-owner', unrelated_notice_and_ready_guard, False, True),
        ('initial-chart-failure', initial_chart_failure, False, True),
    ]
    requested = os.environ.get('OI_STARTUP_SCENARIOS')
    if requested:
        selected = {name.strip() for name in requested.split(',') if name.strip()}
        unknown = selected - {name for name, _, _, _ in scenarios}
        if not selected or unknown:
            raise AssertionError('Invalid startup scenario selection: ' + repr(sorted(unknown)))
        scenarios = [item for item in scenarios if item[0] in selected]
    for name, exercise, standard, with_examples in scenarios:
        current = {'name': name, 'checks': [], 'screenshots': [], 'browser_errors': []}
        directory = output / name
        directory.mkdir(exist_ok=True)
        try:
            with browser_session(chrome, directory, current, standard=standard, with_examples=with_examples) as journey:
                exercise(journey)
        except Exception as error:
            if not current['checks'] or current['checks'][-1]['passed']:
                current['checks'].append({'check': 'Scenario completed', 'passed': False,
                                          'details': f'{type(error).__name__}: {error}'})
        current['passed'] = bool(current['checks']) and all(check['passed'] for check in current['checks'])
        report['scenarios'].append(current)
        (directory / 'verification.json').write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
        print(('PASS' if current['passed'] else 'FAIL') + ': ' + name, flush=True)
    checks = [check for scenario in report['scenarios'] for check in scenario['checks']]
    failures = [check for check in checks if not check['passed']]
    report['summary'] = {'scenarios': len(report['scenarios']), 'checks': len(checks),
                         'passed': len(checks) - len(failures), 'failed': len(failures)}
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    (output / 'workspace-startup-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'summary': report['summary'], 'failures': failures}), flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
