"""Real-browser protection for unfinished, independently authored case work.

Run with PYTHONPATH=src and installed Chrome/Chromium on PATH. Reuses the
navigation journey's local server, CDP pointer/keyboard controls and screenshots.
No external requests, browser packages, product-state stubs or patient data.
OI_CASE_SAFETY_ARTIFACT_DIR optionally selects the JSON/screenshots/log directory.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from workspace_navigation_journey import Journey, ROOT, browser_session


QUESTION = 'Which independently authored Alpha observation still needs clarification?'
REPORT = (
    'OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: CONTINUITY-ALPHA\n'
    'Type: pathology\nEvent-Date: 2026-08-02\nIssued-At: 2026-08-03\n'
    'Specimen: FICTIONAL-CONTINUITY\n'
    'Finding: marker|not-reported|Independent fictional observation; café <literal> remains untested.\n'
)
DRAFT = {
    '#draft-observations': 'An unfinished observation belongs to the selected Alpha sources.',
    '#draft-summary': 'This original fictional review narrative is still being written.',
    '#draft-assumptions': 'The question and source selections must stay with Alpha.',
}


def settle(j: Journey) -> None:
    j.cd.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


def observed(j: Journey) -> dict:
    """Read user-facing values and browser resources, without inspecting app state."""
    return j.js("""
      const file = document.querySelector('#source-file').files[0];
      return {
        picker:document.querySelector('#case-picker').value,
        heading:document.querySelector('#case-heading').textContent,
        question:document.querySelector('#question-text').value,
        report:document.querySelector('#report-text').value,
        draft:{
          observations:document.querySelector('#draft-observations').value,
          summary:document.querySelector('#draft-summary').value,
          assumptions:document.querySelector('#draft-assumptions').value,
          question:document.querySelector('#question-choice').value,
          sources:[...document.querySelectorAll('#source-choice input:checked')].map(input => input.value)
        },
        file:file ? {name:file.name, size:file.size, type:file.type,
          sameObject:file === window.__continuitySelectedFile} : null,
        preview:document.querySelector('#source-upload-preview').textContent,
        previewHidden:document.querySelector('#source-preview-details').hidden,
        previewOpen:document.querySelector('#source-preview-details').open,
        confirmed:document.querySelector('#source-upload-confirm').checked,
        importDisabled:document.querySelector('#source-upload-submit').disabled,
        notice:{text:document.querySelector('#notice').textContent,
          visible:visible(document.querySelector('#notice'))},
        stateReads:performance.getEntriesByType('resource')
          .filter(entry => new URL(entry.name).pathname === '/api/cases/CASE-ALPHA/state').length
      };
    """)


def content(state: dict) -> dict:
    return {key:state[key] for key in (
        'question', 'report', 'draft', 'file', 'preview', 'previewHidden',
        'previewOpen', 'confirmed', 'importDisabled',
    )}


def attempt_case(j: Journey, via: str, target: str = 'CASE-BETA') -> dict:
    if via == 'picker':
        # Use the browser's real select interaction. Native change listeners can
        # run microtasks between callbacks, unlike evaluate()/dispatchEvent().
        assert target == 'CASE-BETA'
        j.check(j.visible('#case-picker'), 'Native case picker is visible')
        j.cd.evaluate("""(() => {
          const picker=document.querySelector('#case-picker');
          window.__continuityTrustedPicker=false;
          picker.addEventListener('change',event=>{
            window.__continuityTrustedPicker=event.isTrusted;
          },{once:true});
          picker.focus();
        })()""")
        j.key('ArrowDown', 40)
        j.key('Enter', 13)
        j.check(j.cd.evaluate('window.__continuityTrustedPicker'),
                'Case selection used a trusted native keyboard change')
    else:
        j.follow_nav('incoming-board')
        j.click(f'#incoming-list [data-case-search*="{target}"] button',
                f'Open {target} through the visible worklist')
    settle(j)
    if j.cd.evaluate("document.querySelector('#case-picker').value") == target:
        j.cd.wait('document.querySelector("#case-heading").textContent === ' +
                  json.dumps('Fictional case ' + target.removeprefix('CASE-').title()),
                  'case heading after attempted navigation')
        settle(j)
    return observed(j)


def expect_preserved(j: Journey, before: dict, after: dict, label: str) -> None:
    j.report.setdefault('observations', []).append({'scenario':label, 'before':before, 'after':after})
    j.capture(label)
    j.check(after['picker'] == 'CASE-ALPHA' and after['heading'] == 'Fictional case Alpha'
            and content(after) == content(before), label + ': Alpha and exact unfinished content survive',
            {'before':before, 'after':after})
    j.check(after['notice']['visible'] and bool(after['notice']['text'].strip()),
            label + ': blocked case change has a visible explanation', after['notice'])


def select_source(j: Journey, *, delayed: bool = False) -> None:
    j.go('source-intake')
    j.check(j.visible('#source-file'), 'Original-file input is visible on its routed page')
    if delayed:
        # Delay the real File read, then release its actual bytes. This exercises
        # the interval in which a file is selected but has no inspected preview.
        j.cd.evaluate("""(() => {
          const read = File.prototype.arrayBuffer;
          File.prototype.arrayBuffer = function() {
            const selected = this;
            return new Promise((resolve, reject) => {
              window.__continuityReleaseRead = () => read.call(selected).then(value => {
                resolve(value); window.__continuityReadResolved = true;
              }, reject);
            });
          };
        })()""")
    path = j.output / 'independently-authored-alpha.txt'
    path.write_text(REPORT, encoding='utf-8', newline='')
    j.cd.command('DOM.enable')
    root = j.cd.command('DOM.getDocument')['root']['nodeId']
    node = j.cd.command('DOM.querySelector', {'nodeId':root, 'selector':'#source-file'})['nodeId']
    j.cd.command('DOM.setFileInputFiles', {'nodeId':node, 'files':[str(path)]})
    j.cd.evaluate("window.__continuitySelectedFile = document.querySelector('#source-file').files[0]")
    if delayed:
        j.cd.wait("typeof window.__continuityReleaseRead === 'function'", 'selected real File awaiting read')
        j.check(observed(j)['preview'] == '', 'A delayed File read has not invented a preview')
    else:
        inspect_source(j)


def inspect_source(j: Journey) -> None:
    j.cd.wait('document.querySelector("#source-upload-preview").textContent === ' + json.dumps(REPORT),
              'exact original UTF-8 source preview')
    j.click('#source-preview-details > summary', 'Inspect the original file text')
    j.check(j.visible('#source-upload-preview'), 'The selected original is visibly inspectable')
    j.click('#source-upload-confirm', 'Confirm this independently authored fictional source')
    j.check(not observed(j)['importDisabled'], 'A confirmed inspected file can be imported')


def save_question(j: Journey, text: str) -> int:
    j.go('questions')
    j.fill('#question-text', text)
    j.click('#question-form button[type="submit"]', 'Save a fictional question')
    j.cd.wait('document.querySelector("#question-list").textContent.includes(' + json.dumps(text) + ')',
              'fictional question persisted')
    return next(item['id'] for item in j.state()['questions'] if item['question'] == text)


def write_draft(j: Journey, *, question_id: int | None = None) -> None:
    j.go('investigations')
    if question_id is not None:
        j.select('#question-choice', str(question_id))
    for selector, text in DRAFT.items():
        j.fill(selector, text)
    choices = j.cd.evaluate("[...document.querySelectorAll('#source-choice input')].map(input => input.checked)")
    for index, checked in enumerate(choices):
        if checked != (index == 0):
            j.click_expression(f"[...document.querySelectorAll('#source-choice input')][{index}]",
                               'Bind the draft to exactly one original source')


def unfinished_text(j: Journey, kind: str, via: str) -> None:
    route, selector, text = ('questions', '#question-text', QUESTION) if kind == 'question' else (
        'import', '#report-text', REPORT)
    j.go(route)
    j.fill(selector, text)
    before = observed(j)
    expect_preserved(j, before, attempt_case(j, via), f'{kind}-only-{via}')


def unfinished_file(j: Journey, delayed: bool, via: str) -> None:
    select_source(j, delayed=delayed)
    before = observed(j)
    expect_preserved(j, before, attempt_case(j, via), f'file-{"reading" if delayed else "inspected"}-{via}')
    if delayed:
        j.cd.evaluate('window.__continuityReleaseRead()')
        j.go('source-intake')
        inspect_source(j)
        j.check(observed(j)['file']['sameObject'], 'The original File remains usable after its blocked switch')


def combined_veto(j: Journey, kind: str) -> None:
    if kind == 'question':
        j.go('questions')
        j.fill('#question-text', QUESTION)
    else:
        write_draft(j)
    select_source(j)
    before = observed(j)
    expect_preserved(j, before, attempt_case(j, 'picker' if kind == 'question' else 'worklist'),
                     f'{kind}-with-inspected-file')


def same_case(j: Journey) -> None:
    first = save_question(j, 'First independently authored binding question?')
    save_question(j, 'Second independently authored binding question?')
    write_draft(j, question_id=first)
    j.go('questions')
    j.fill('#question-text', QUESTION)
    j.go('import')
    j.fill('#report-text', REPORT)
    select_source(j)
    before = observed(j)
    after = attempt_case(j, 'worklist', 'CASE-ALPHA')
    j.report['observations'] = [{'before':before, 'after':after}]
    j.capture('same-case-reopened')
    j.check(content(after) == content(before), 'Reopening Alpha preserves every draft, binding and exact File',
            {'before':before, 'after':after})
    j.check(after['stateReads'] == before['stateReads'], 'Reopening the active case performs no state reload',
            {'before':before['stateReads'], 'after':after['stateReads']})
    j.view('overview')


def discard_source(j: Journey) -> None:
    j.click_expression("[...document.querySelectorAll('#source-upload-form button')].find(button => "
                       "button.textContent.trim() === 'Discard selected source')",
                       'Discard selected source explicitly')
    settle(j)


def assert_empty_selection(j: Journey, label: str) -> None:
    state = observed(j)
    j.check(state['file'] is None and state['preview'] == '' and state['previewHidden']
            and not state['confirmed'] and state['importDisabled'], label, state)


def assert_beta_isolated(j: Journey) -> None:
    j.cd.wait("document.querySelector('#case-heading').textContent === 'Fictional case Beta' && "
              "document.querySelectorAll('#source-list .source-card').length === 1", 'Beta source rendering')
    text = j.cd.evaluate("['source-list','assertion-list','snapshot-list'].map(id => "
                         "document.getElementById(id).textContent).join(' | ')")
    j.check('PATH-BETA' in text and 'PATH-ALPHA' not in text and 'IMG-ALPHA' not in text
            and 'CONTINUITY-ALPHA' not in text, 'The successful switch renders only Beta provenance', text)
    j.check(j.cd.evaluate("document.querySelectorAll('#snapshot-list .snapshot').length === 0"),
            'Beta has no Alpha report history')
    assert_empty_selection(j, 'Beta has no unsubmitted Alpha file or preview')


def discard_then_switch(j: Journey) -> None:
    question_id = save_question(j, 'A durable independently authored question for discard verification?')
    write_draft(j, question_id=question_id)
    j.click('#draft-form button[type="submit"]', 'Persist an independent fictional review draft')
    j.cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1", 'durable report history')
    before_alpha, before_beta = j.state(), j.state('CASE-BETA')
    j.go('questions')
    j.fill('#question-text', QUESTION)
    j.go('import')
    j.fill('#report-text', REPORT)
    write_draft(j, question_id=question_id)
    select_source(j)
    before = observed(j)
    discard_source(j)
    after = observed(j)
    j.check(all(after[key] == before[key] for key in ('question', 'report', 'draft')),
            'Discard only clears the selected file and preserves other unfinished work',
            {'before':before, 'after':after})
    assert_empty_selection(j, 'Discard clears File, exact preview and confirmation')
    j.check(j.state() == before_alpha and j.state('CASE-BETA') == before_beta,
            'Discard leaves durable sources, questions, report history and the other case unchanged')
    j.go('questions')
    j.fill('#question-text', '')
    j.go('import')
    j.fill('#report-text', '')
    j.go('investigations')
    for selector in DRAFT:
        j.fill(selector, '')
    attempt_case(j, 'worklist')
    assert_beta_isolated(j)
    j.check(j.state() == before_alpha and j.state('CASE-BETA') == before_beta,
            'Clearing unsubmitted work and switching creates no durable cross-case changes')
    j.capture('discarded-then-beta')


def discard_delayed_read(j: Journey) -> None:
    before_alpha, before_beta = j.state(), j.state('CASE-BETA')
    select_source(j, delayed=True)
    discard_source(j)
    attempt_case(j, 'picker')
    j.cd.evaluate('window.__continuityReleaseRead()')
    j.cd.wait('window.__continuityReadResolved === true', 'discarded real File read released')
    settle(j)
    assert_beta_isolated(j)
    j.check(j.state() == before_alpha and j.state('CASE-BETA') == before_beta,
            'A late discarded read cannot create sources or attach its preview to Beta')
    j.capture('late-read-after-discard')


def import_then_switch(j: Journey) -> None:
    before_beta = j.state('CASE-BETA')
    select_source(j)
    j.click('#source-upload-submit', 'Import the inspected original file')
    j.cd.wait("document.querySelectorAll('#source-list .source-card').length === 3", 'original file persisted')
    source = next(item for item in j.state()['sources'] if item['document_id'] == 'CONTINUITY-ALPHA')
    j.check(source['sha256'] == hashlib.sha256(REPORT.encode('utf-8')).hexdigest(),
            'Successful intake persisted the exact independently authored bytes')
    assert_empty_selection(j, 'Successful intake clears the pending selection')
    attempt_case(j, 'worklist')
    assert_beta_isolated(j)
    j.check(j.state('CASE-BETA') == before_beta, 'Successful Alpha import leaves Beta durable state unchanged')
    j.capture('imported-then-beta')


def main() -> None:
    output = Path(os.environ.get('OI_CASE_SAFETY_ARTIFACT_DIR') or
                  tempfile.mkdtemp(prefix='oi-ux-continuity-case-safety-')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / 'runtime'
    runtime.mkdir(exist_ok=True)
    tempfile.tempdir = str(runtime)
    chrome = next((path for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                   if (path := shutil.which(name))), None)
    if not chrome:
        raise AssertionError('Chromium unavailable: case safety is not verified')
    scenarios = []
    for kind in ('question', 'report'):
        for via in ('picker', 'worklist'):
            scenarios.append((f'{kind}-only-{via}', lambda j, k=kind, v=via: unfinished_text(j, k, v)))
    for delayed in (True, False):
        for via in ('picker', 'worklist'):
            scenarios.append((f'file-{"reading" if delayed else "inspected"}-{via}',
                              lambda j, d=delayed, v=via: unfinished_file(j, d, v)))
    scenarios.extend([
        ('question-with-file', lambda j: combined_veto(j, 'question')),
        ('draft-with-file', lambda j: combined_veto(j, 'draft')),
        ('same-case-all-drafts', same_case),
        ('discard-then-switch', discard_then_switch),
        ('discard-delayed-read', discard_delayed_read),
        ('import-then-switch', import_then_switch),
    ])
    report = {
        'started_at':datetime.now(timezone.utc).isoformat(),
        'git_head':subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'product_sha256':{name:hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ('web/app.js', 'web/intake.js', 'web/workspace-entry.js')},
        'data':'Independently authored fictional Alpha/Beta fixtures and original continuity report only',
        'chrome':chrome, 'scenarios':[],
    }
    for name, exercise in scenarios:
        current = {'name':name, 'checks':[], 'screenshots':[], 'browser_errors':[]}
        scenario_output = output / name
        scenario_output.mkdir(exist_ok=True)
        try:
            with browser_session(chrome, scenario_output, current) as journey:
                journey.cd.wait("document.querySelector('#case-heading').textContent === 'Fictional case Alpha' && "
                                "document.body.dataset.workspaceState === 'ready' && "
                                "document.querySelectorAll('#incoming-list [data-case-search]').length === 2",
                                'initial independently authored cases ready')
                journey.open_case('CASE-ALPHA')
                exercise(journey)
            current['passed'] = True
        except Exception as error:
            current['passed'] = False
            current['failure'] = f'{type(error).__name__}: {error}'
        report['scenarios'].append(current)
        (scenario_output / 'verification.json').write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
        print(('PASS' if current['passed'] else 'FAIL') + ': ' + name +
              (': ' + current['failure'].split(': {', 1)[0] if not current['passed'] else ''), flush=True)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    report['passed'] = all(item['passed'] for item in report['scenarios'])
    destination = output / 'workspace-case-safety-verification.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed':report['passed'], 'scenarios':len(scenarios),
                      'failed':[item['name'] for item in report['scenarios'] if not item['passed']],
                      'report':str(destination)}), flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
