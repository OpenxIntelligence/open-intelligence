"""Real Chromium checks for worklist freshness over the existing case owner.

Uses the existing fictional launchers and CDP harness. All writes use visible
application forms; read-only HTTP state is an independent persistence oracle.
OI_WORKLIST_ARTIFACT_DIR selects reports, screenshots and process logs.
OI_WORKLIST_SCENARIOS can select comma-separated scenario names for a focused
diagnostic run; the default runs every scenario, including the original launcher.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from workspace_navigation_journey import ROOT, Journey, ObservedChromeSession, browser_session


ALPHA = {'date': '2026-05-17', 'sources': 2, 'questions': 0, 'stale': 0}
BETA = {'date': '2026-06-02', 'sources': 1, 'questions': 0, 'stale': 0}
LATER_SOURCE = (
    'OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: WORKLIST-ALPHA-LATE\n'
    'Type: imaging\nEvent-Date: 2026-07-09\nIssued-At: 2026-07-10\n'
    'Finding: workflow-note|not-assessed|Independently authored fictional café <literal> observation for worklist verification.\n'
)
LATER_ALPHA = {**ALPHA, 'date': '2026-07-09', 'sources': 3}
EVIDENCE = (
    'OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVID-WORKLIST\n'
    'Title: Independently authored fictional worklist methods note\n'
    'Issued-At: 2026-07-01\nRights: original-synthetic\n'
    'Statement: This fictional note exercises source dependencies only; it establishes no clinical applicability.\n'
)
AMENDED_EVIDENCE = (
    'OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVID-WORKLIST\n'
    'Title: Independently authored fictional worklist methods correction\n'
    'Issued-At: 2026-07-02\nRights: original-synthetic\nAmends: EVID-WORKLIST@1\n'
    'Statement: This fictional correction preserves uncertainty and tests dependency invalidation only.\n'
)


def settle(j: Journey) -> None:
    j.cd.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


def record(j: Journey, condition: bool, label: str, details=None) -> None:
    entry = {'mode': j.mode, 'check': label, 'passed': bool(condition)}
    if details is not None:
        entry['details'] = details
    j.report['checks'].append(entry)


def ready(j: Journey, case_id: str = 'CASE-ALPHA') -> None:
    value = json.dumps(case_id)
    j.cd.wait(f'caseId === {value} && active?.case.case_id === {value} && '
              f'renderedCaseId === {value}', 'canonical case ready: ' + case_id)
    settle(j)


def watch_chart(j: Journey) -> None:
    ready(j)
    j.cd.evaluate("""(() => {
      window.__worklistChartRenders=0;
      new MutationObserver(()=>window.__worklistChartRenders++)
        .observe(document.querySelector('#case-heading'),{childList:true});
    })()""")


def rendered_after(j: Journey, revision: int, case_id: str = 'CASE-ALPHA') -> None:
    j.cd.wait(f'window.__worklistChartRenders > {revision}', 'accepted state rendered after the action')
    ready(j, case_id)


def rows(j: Journey) -> list[dict]:
    result = j.js("""return [...document.querySelectorAll('#incoming-list [data-case-search]')].map(row=>({
      caseId:row.dataset.caseId || row.dataset.caseSearch.match(/CASE-[A-Z0-9-]+/)?.[0],
      text:row.textContent, visible:visible(row),
      focused:row.contains(document.activeElement)
    }));""")
    patterns = {
        'date': r'Most recent source event:\s*([^·]+)',
        'sources': r'Current source documents:\s*(\d+)',
        'questions': r'Open questions:\s*(\d+)',
        'stale': r'Historical drafts[^:]*:\s*(\d+)',
    }
    for row in result:
        row['summary'] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, row['text'])
            row['summary'][key] = (match.group(1).strip() if key == 'date'
                                   else int(match.group(1))) if match else None
    return result


def expect_row(j: Journey, case_id: str, expected: dict, label: str) -> None:
    observed = next((row for row in rows(j) if row['caseId'] == case_id), None)
    record(j, observed is not None and observed['summary'] == expected, label,
           {'expected': expected, 'observed': observed})


def board(j: Journey) -> None:
    j.go('incoming-board')
    settle(j)


def canonical_selection(j: Journey) -> dict:
    return j.cd.evaluate("""({selected:caseId, active:active?.case.case_id,
      rendered:renderedCaseId, sequence:refreshSequence,
      picker:document.querySelector('#case-picker').value,
      questions:active?.questions.map(item=>[item.id,item.state,item.question]),
      sources:active?.sources.map(item=>[item.id,item.state,item.event_date]),
      snapshots:active?.snapshots.map(item=>[item.id,item.state])})""")


def expect_order(j: Journey, expected: list[str], label: str) -> None:
    actual = [row['caseId'] for row in rows(j)]
    record(j, actual == expected, label, {'expected': expected, 'actual': actual})


def save_question(j: Journey, text: str, case_id: str = 'CASE-ALPHA') -> int:
    j.go('questions')
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.fill('#question-text', text)
    j.click('#question-form button[type="submit"]', 'Save an independently authored fictional question')
    rendered_after(j, revision, case_id)
    state = j.state(case_id)
    return next(item['id'] for item in state['questions'] if item['question'] == text)


def save_draft(j: Journey, question_id: int, case_id: str = 'CASE-ALPHA',
               evidence_id: int | None = None) -> int:
    state = j.state(case_id)
    previous = {item['id'] for item in state['snapshots']}
    source = next(item for item in state['sources']
                  if item['state'] == 'current' and item['document_id'] == 'PATH-' + case_id[5:])
    j.go('investigations')
    j.select('#question-choice', str(question_id))
    selections = j.cd.evaluate("[...document.querySelectorAll('#source-choice input')].map(input=>({id:Number(input.value),checked:input.checked}))")
    for choice in selections:
        if choice['checked'] != (choice['id'] == source['id']):
            j.click(f'#source-choice input[value="{choice["id"]}"]', 'Choose the exact current fictional source version')
    if evidence_id is not None:
        j.click(f'#evidence-choice input[value="{evidence_id}"]', 'Bind the draft to its own case evidence assessment')
    j.fill('#draft-observations', 'An independently authored fictional observation retains its exact source for this worklist check.')
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.click('#draft-form button[type="submit"]', 'Save the fictional source-bound review draft')
    rendered_after(j, revision, case_id)
    saved = next(item for item in j.state(case_id)['snapshots'] if item['id'] not in previous)
    record(j, saved['source_ids'] == [source['id']], 'Draft retains exactly its own selected source version', saved)
    if evidence_id is not None:
        record(j, saved['evidence_assessment_ids'] == [evidence_id],
               'Draft retains exactly its own evidence-assessment binding', saved)
    return saved['id']


def acknowledge(j: Journey, snapshot_id: int, case_id: str = 'CASE-ALPHA') -> None:
    j.go('reports')
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.click_expression(f"[...document.querySelector('#snapshot-{snapshot_id}').querySelectorAll('button')].find(button=>button.textContent==='Demo review acknowledgment')",
                       'Record the existing fictional demo review acknowledgment')
    rendered_after(j, revision, case_id)
    record(j, next(item for item in j.state(case_id)['snapshots'] if item['id'] == snapshot_id)['state'] == 'reviewed_in_demo',
           'The existing ledger recorded the demo review')


def paste_source(j: Journey, text: str, case_id: str = 'CASE-ALPHA') -> None:
    j.go('import')
    j.fill('#report-text', text)
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.click('#import-form button[type="submit"]', 'Import independently authored original text through the existing form')
    rendered_after(j, revision, case_id)
    record(j, j.cd.evaluate("document.querySelector('#report-text').value === ''"),
           'The successful existing import clears only its submitted text')


def review_amendment(j: Journey) -> None:
    watch_chart(j)
    qid = save_question(j, 'Which fictional Alpha statement requires an original-source review?')
    first = save_draft(j, qid)
    board(j)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1},
               'Saving a draft keeps its question open and does not count it as historical stale work')
    acknowledge(j, first)
    board(j)
    expect_row(j, 'CASE-ALPHA', ALPHA, 'Demo review removes the addressed question from the open count')
    original = next(item for item in j.state()['snapshots'] if item['id'] == first)
    paste_source(j, (ROOT / 'examples/synthetic/alpha-pathology-amended.txt').read_text())
    board(j)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1, 'stale': 1},
               'A pasted amendment reopens the question and counts the preserved historical draft')
    expect_order(j, ['CASE-BETA', 'CASE-ALPHA'],
                 'A later amendment issue date does not change the source event ordering')
    amended = next(item for item in j.state()['snapshots'] if item['id'] == first)
    record(j, amended['state'] == 'stale' and amended['summary'] == original['summary']
           and amended['source_ids'] == original['source_ids'],
           'Amendment preserves the original draft text and exact historical binding')
    second = save_draft(j, qid)
    acknowledge(j, second)
    board(j)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'stale': 1},
               'Replacement review closes the question while the earlier historical stale count remains one')
    expect_row(j, 'CASE-BETA', BETA, 'Alpha review and amendment leave Beta summary unchanged')
    j.capture('review-amendment-history')


def source_recency(j: Journey) -> None:
    watch_chart(j)
    paste_source(j, LATER_SOURCE)
    board(j)
    expect_row(j, 'CASE-ALPHA', LATER_ALPHA, 'A distinct pasted source updates current count and event date')
    expect_order(j, ['CASE-ALPHA', 'CASE-BETA'], 'A genuinely later source event moves Alpha ahead of Beta')
    source = next(item for item in j.state()['sources'] if item['document_id'] == 'WORKLIST-ALPHA-LATE')
    record(j, source['sha256'] == hashlib.sha256(LATER_SOURCE.encode()).hexdigest(),
           'Pasted import preserves the exact independently authored UTF-8 source bytes')
    paste_source(j, LATER_SOURCE)
    board(j)
    expect_row(j, 'CASE-ALPHA', LATER_ALPHA, 'Duplicate original bytes do not inflate worklist source counts')
    wrong_subject = LATER_SOURCE.replace('Patient: CASE-ALPHA', 'Patient: CASE-BETA').replace(
        'Document: WORKLIST-ALPHA-LATE', 'Document: WORKLIST-WRONG-SUBJECT')
    paste_source(j, wrong_subject)
    board(j)
    expect_row(j, 'CASE-ALPHA', LATER_ALPHA, 'Quarantined wrong-subject text does not change current count or recency')
    expect_row(j, 'CASE-BETA', BETA, 'Quarantined text is not silently attached to the other case')
    record(j, len(j.state()['quarantines']) == 1, 'Wrong-subject import is actually represented in the existing quarantine ledger')
    expect_order(j, ['CASE-ALPHA', 'CASE-BETA'], 'Duplicate and quarantine paths preserve event-date ordering')
    j.capture('pasted-source-order')


def file_intake(j: Journey) -> None:
    watch_chart(j)
    j.go('source-intake')
    path = j.output / 'independently-authored-worklist-source.txt'
    path.write_text(LATER_SOURCE, encoding='utf-8', newline='')
    j.cd.command('DOM.enable')
    root = j.cd.command('DOM.getDocument')['root']['nodeId']
    target = j.cd.command('DOM.querySelector', {'nodeId': root, 'selector': '#source-file'})['nodeId']
    j.cd.command('DOM.setFileInputFiles', {'nodeId': target, 'files': [str(path)]})
    j.cd.wait('document.querySelector("#source-upload-preview").textContent === ' + json.dumps(LATER_SOURCE),
              'real file preview contains the original exact bytes')
    j.click('#source-preview-details > summary', 'Inspect the actual original file text')
    j.click('#source-upload-confirm', 'Confirm independently authored fictional source provenance')
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.click('#source-upload-submit', 'Import the actual selected original file')
    rendered_after(j, revision)
    j.cd.wait("!document.querySelector('#source-file').files.length && document.querySelectorAll('#incoming-list [data-case-search]').length === 2",
              'file import and worklist presentation completed')
    board(j)
    expect_row(j, 'CASE-ALPHA', LATER_ALPHA, 'File intake has the same summary semantics as pasted intake')
    expect_order(j, ['CASE-ALPHA', 'CASE-BETA'], 'File intake follows the same source-event ordering')
    source = next(item for item in j.state()['sources'] if item['document_id'] == 'WORKLIST-ALPHA-LATE')
    record(j, source['sha256'] == hashlib.sha256(LATER_SOURCE.encode()).hexdigest(),
           'File intake preserves the same exact independently authored bytes')
    j.capture('file-intake-order')


def require_refresh_controls(j: Journey) -> None:
    board(j)
    j.check(j.visible('#worklist-refresh'), 'Refresh list is visibly reachable on the worklist')
    record(j, j.cd.evaluate("document.querySelector('#worklist-refresh').type === 'button' && !document.querySelector('#worklist-refresh').closest('form')"),
           'Refresh list is a non-submit action outside the original forms')
    record(j, j.cd.evaluate("['polite','assertive'].includes(document.querySelector('#worklist-status')?.getAttribute('aria-live'))"),
           'Worklist refresh status has an explicit live announcement')


def wait_board_idle(j: Journey) -> None:
    j.cd.wait("document.querySelector('#incoming-list').getAttribute('aria-busy') !== 'true'",
              'worklist read no longer busy')
    settle(j)


def open_details(j: Journey, expression: str, label: str) -> None:
    if not j.cd.evaluate(f'({expression}).open'):
        j.click_expression(f'({expression}).querySelector(":scope > summary")', label)


@contextmanager
def other_tab(j: Journey):
    """A real second UI session against the same isolated fictional server."""
    host, port = j.cd.socket.getpeername()[:2]
    target = j.cd.command('Target.createTarget', {'url': j.url})['targetId']
    cd = None
    try:
        cd = ObservedChromeSession(f'ws://{host}:{port}/devtools/page/{target}')
        for domain in ('Page', 'Runtime', 'Log'):
            cd.command(domain + '.enable')
        other = Journey(cd, j.url, j.output, j.downloads, j.report, 'other-session')
        cd.command('Page.bringToFront')
        other.viewport(1440)
        cd.wait("document.body.classList.contains('ux-ready')", 'second real application session initialized')
        watch_chart(other)
        yield other
        other.check(not cd.browser_errors, 'Second UI session has no JavaScript exceptions', cd.browser_errors)
    finally:
        if cd:
            j.report['browser_errors'].extend({'mode': 'other-session', **error} for error in cd.browser_errors)
            cd.close()
        j.cd.command('Target.closeTarget', {'targetId': target})
        j.cd.command('Page.bringToFront')
        settle(j)


def hold_alpha_response(j: Journey) -> None:
    """Hold a real HTTP response once; later calls still reach the local server."""
    j.cd.evaluate("""(() => {
      const original=window.__worklistOriginalFetch || window.fetch;
      window.__worklistOriginalFetch=original;
      window.__worklistGate=null;
      let armed=true;
      window.fetch=async(input,options)=>{
        const hold=armed && String(input).endsWith('/api/cases/CASE-ALPHA/state');
        if(hold)armed=false;
        const response=await original(input,options);
        if(!hold)return response;
        const observed=await response.clone().json();
        return new Promise((resolve,reject)=>{
          window.__worklistGate={observed,
            release:()=>resolve(response),
            fail:()=>reject(new Error('Controlled fictional worklist summary failure'))};
        });
      };
    })()""")


def start_board_read(j: Journey, token: str) -> None:
    cases = j.read('api/cases')
    j.cd.evaluate(f"""(() => {{
      window[{json.dumps(token)}]=false;
      window[{json.dumps(token + 'Error')}]=null;
      renderIncomingBoard({json.dumps(cases)}).then(
        ()=>window[{json.dumps(token)}]=true,
        error=>{{window[{json.dumps(token + 'Error')}]=String(error);window[{json.dumps(token)}]=true;}});
    }})()""")


def wait_board_read(j: Journey, token: str) -> None:
    j.cd.wait('window[' + json.dumps(token) + '] === true', 'full-worklist read completed')
    error = j.cd.evaluate('window[' + json.dumps(token + 'Error') + ']')
    record(j, error is None, 'Full-worklist owner handles completion without an unexpected rejection', error)
    settle(j)


def release_board_read(j: Journey, token: str, *, fail: bool = False) -> None:
    j.cd.evaluate('window.__worklistGate.' + ('fail' if fail else 'release') + '()')
    wait_board_read(j, token)


def late_board_read(j: Journey, *, fail: bool = False) -> None:
    watch_chart(j)
    board(j)
    hold_alpha_response(j)
    start_board_read(j, '__worklistOldBoardDone')
    j.cd.wait('!!window.__worklistGate', 'old real Alpha response held for the worklist')
    record(j, len(rows(j)) == 2, 'A background worklist read retains the existing openable rows')
    save_question(j, 'Can the newer fictional Alpha question survive an older worklist response?')
    j.select('#case-picker', 'CASE-BETA')
    ready(j, 'CASE-BETA')
    board(j)
    j.fill('#case-search', 'Alpha')
    j.cd.evaluate("""window.__worklistFocusedButton=document.querySelector('#incoming-list [data-case-search*="CASE-ALPHA"] button');
      window.__worklistFocusedButton?.focus();""")
    before = canonical_selection(j)
    release_board_read(j, '__worklistOldBoardDone', fail=fail)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1},
               ('An older failed summary' if fail else 'An older successful summary') + ' cannot overwrite newer Alpha after switching to Beta')
    expect_row(j, 'CASE-BETA', BETA, 'Late worklist completion retains Beta summary')
    record(j, canonical_selection(j) == before, 'Board-only completion does not mutate canonical selection or chart sequence',
           {'before': before, 'after': canonical_selection(j)})
    record(j, j.cd.evaluate("document.querySelector('#case-search').value === 'Alpha'")
           and [row['caseId'] for row in rows(j) if row['visible']] == ['CASE-ALPHA'],
           'Late worklist completion preserves the current search and filtering')
    record(j, j.cd.evaluate('!!window.__worklistFocusedButton && document.activeElement === window.__worklistFocusedButton && window.__worklistFocusedButton.isConnected'),
           'Late worklist completion preserves the original Open button and its keyboard focus')
    j.capture('late-board-failure' if fail else 'late-board-success')


def initial_summary_recovery(j: Journey) -> None:
    ready(j)
    j.cd.command('Page.addScriptToEvaluateOnNewDocument', {'source': """(() => {
      const original=window.fetch;
      let first=true;
      window.fetch=async(input,options)=>{
        const fail=first && String(input).endsWith('/api/cases/CASE-ALPHA/state');
        if(fail)first=false;
        const response=await original(input,options);
        if(fail)throw new Error('Controlled initial fictional Alpha summary failure');
        return response;
      };
    })();"""})
    j.cd.command('Page.navigate', {'url': j.url + '?worklist-initial-recovery=1'})
    j.cd.wait("location.search === '?worklist-initial-recovery=1' && document.body.classList.contains('ux-ready')",
              'fresh page with one controlled summary read failure')
    ready(j)
    board(j)
    expect_row(j, 'CASE-ALPHA', ALPHA, 'Successful canonical initialization replaces an obsolete initial summary error')
    expect_row(j, 'CASE-BETA', BETA, 'Another initial summary remains isolated from the failed Alpha read')
    j.capture('initial-summary-recovered')


def manual_refresh(j: Journey) -> None:
    watch_chart(j)
    require_refresh_controls(j)
    j.go('questions')
    unfinished = 'Keep this independently authored question unsaved during worklist refresh.'
    j.fill('#question-text', unfinished)
    j.go('source-intake')
    path = j.output / 'independently-authored-pending-source.txt'
    path.write_text(LATER_SOURCE, encoding='utf-8', newline='')
    j.cd.command('DOM.enable')
    root = j.cd.command('DOM.getDocument')['root']['nodeId']
    target = j.cd.command('DOM.querySelector', {'nodeId': root, 'selector': '#source-file'})['nodeId']
    j.cd.command('DOM.setFileInputFiles', {'nodeId': target, 'files': [str(path)]})
    j.cd.wait('document.querySelector("#source-upload-preview").textContent === ' + json.dumps(LATER_SOURCE),
              'unsubmitted original read completed')
    j.click('#source-upload-confirm', 'Confirm the pending original without submitting it')
    j.cd.evaluate("window.__worklistPendingFile=document.querySelector('#source-file').files[0]")
    board(j)
    j.fill('#case-search', 'Alpha')
    before = canonical_selection(j)
    hold_alpha_response(j)
    j.click('#worklist-refresh', 'Refresh the actual worklist through its explicit control')
    j.cd.wait('!!window.__worklistGate', 'explicit refresh holds a real state response')
    record(j, j.cd.evaluate("document.querySelector('#incoming-list').getAttribute('aria-busy') === 'true' && !!document.querySelector('#worklist-status').textContent.trim()"),
           'Explicit refresh exposes loading through busy state and a live status')
    record(j, len(rows(j)) == 2, 'Explicit refresh retains existing rows while requests are pending')
    j.cd.evaluate("""window.__worklistFocusedButton=document.querySelector('#incoming-list [data-case-search*="CASE-ALPHA"] button');
      window.__worklistFocusedButton?.focus();""")
    j.cd.evaluate('window.__worklistGate.release()')
    wait_board_idle(j)
    record(j, j.cd.evaluate('!!window.__worklistFocusedButton && document.activeElement === window.__worklistFocusedButton && window.__worklistFocusedButton.isConnected'),
           'Refreshing the list preserves the original focused Open button')
    record(j, canonical_selection(j) == before, 'Explicit refresh leaves selected state and chart request sequence unchanged')
    record(j, j.cd.evaluate('document.querySelector("#question-text").value === ' + json.dumps(unfinished) +
                           ' && document.querySelector("#source-file").files[0] === window.__worklistPendingFile' +
                           ' && document.querySelector("#source-upload-confirm").checked' +
                           ' && document.querySelector("#source-upload-preview").textContent === ' + json.dumps(LATER_SOURCE)),
           'Explicit worklist refresh preserves unsaved question, exact browser File, preview and confirmation')
    record(j, j.cd.evaluate("document.querySelector('#case-search').value === 'Alpha'")
           and [row['caseId'] for row in rows(j) if row['visible']] == ['CASE-ALPHA'],
           'Explicit refresh preserves search input and actual row filtering')

    hold_alpha_response(j)
    j.click('#worklist-refresh', 'Refresh the worklist with a controlled single-case failure')
    j.cd.wait('!!window.__worklistGate', 'partial-failure request reached the real server')
    j.cd.evaluate('window.__worklistGate.fail()')
    wait_board_idle(j)
    failed = next(row for row in rows(j) if row['caseId'] == 'CASE-ALPHA')
    record(j, 'unavailable' in failed['text'].lower()
           and all(value is None for value in failed['summary'].values()),
           'A failed summary is explicitly unavailable rather than fabricated as zero counts', failed)
    expect_row(j, 'CASE-BETA', BETA, 'Partial refresh failure preserves successful Beta results')
    record(j, j.cd.evaluate("!!document.querySelector('#worklist-status').textContent.trim() && !document.querySelector('#worklist-refresh').disabled"),
           'Partial failure leaves visible feedback and a usable retry action')
    j.click('#worklist-refresh', 'Retry the failed worklist summary using Refresh list')
    j.cd.wait("document.querySelector('#incoming-list [data-case-search*=\"CASE-ALPHA\"]').textContent.includes('Current source documents: 2')",
              'explicit retry recovered the unavailable summary')
    wait_board_idle(j)
    expect_row(j, 'CASE-ALPHA', ALPHA, 'Explicit retry restores the actual Alpha source and question summary')
    record(j, canonical_selection(j) == before, 'Failure and retry never reload or switch the selected chart')
    record(j, j.cd.evaluate('document.querySelector("#question-text").value === ' + json.dumps(unfinished) +
                           ' && document.querySelector("#source-file").files[0] === window.__worklistPendingFile'),
           'Failed and retried worklist reads retain unfinished case work')
    j.capture('manual-refresh-recovery')


def outside_session_refresh(j: Journey) -> None:
    watch_chart(j)
    require_refresh_controls(j)
    before = canonical_selection(j)
    with other_tab(j) as other:
        save_question(other, 'A fictional Alpha question saved in another real browser tab.')
        other.go('workspace-start')
        open_details(other, "document.querySelector('#new-case-panel')", 'Open existing workspace creation')
        other.fill('#case-create-alias', 'Gamma')
        other.fill('#case-create-code', 'CASE-GAMMA')
        other.click('#case-create-confirm', 'Confirm the new workspace is independently authored fiction')
        other.click('#case-create-submit', 'Create a new fictional workspace in the second session')
        ready(other, 'CASE-GAMMA')
    board(j)
    expect_row(j, 'CASE-ALPHA', ALPHA, 'Another session does not fabricate a local canonical chart refresh')
    j.click('#worklist-refresh', 'Explicitly check changes made in another real UI session')
    j.cd.wait("document.querySelectorAll('#incoming-list [data-case-search]').length === 3 && !!document.querySelector('#case-picker option[value=\"CASE-GAMMA\"]')",
              'refresh discovers and makes the new case selectable')
    wait_board_idle(j)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1}, 'Explicit refresh sees the question saved by another session')
    expect_row(j, 'CASE-GAMMA', {'date': 'none recorded', 'sources': 0, 'questions': 0, 'stale': 0},
               'New roster membership has an actual empty-state summary')
    record(j, canonical_selection(j) == before, 'Discovering outside changes and a new case does not alter the current chart')
    j.open_case('CASE-GAMMA')
    ready(j, 'CASE-GAMMA')
    record(j, canonical_selection(j)['selected'] == 'CASE-GAMMA',
           'A refreshed newly discovered row opens through the existing picker and canonical owner')
    j.capture('outside-session-refresh')


def newer_full_refresh(j: Journey) -> None:
    watch_chart(j)
    board(j)
    hold_alpha_response(j)
    start_board_read(j, '__worklistOlderSweepDone')
    j.cd.wait('!!window.__worklistGate', 'older sweep holds its actual Alpha snapshot')
    with other_tab(j) as other:
        save_question(other, 'A newer complete worklist read must observe this independently authored external question.')
    before = canonical_selection(j)
    start_board_read(j, '__worklistNewerSweepDone')
    wait_board_read(j, '__worklistNewerSweepDone')
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1}, 'The newer complete list reads the real external change')
    release_board_read(j, '__worklistOlderSweepDone')
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1}, 'An older full list cannot replace a newer complete list')
    record(j, canonical_selection(j) == before, 'Competing full-list reads leave canonical chart ownership untouched')
    j.capture('newer-full-refresh-wins')


def import_evidence(j: Journey, text: str, case_id: str) -> None:
    j.go('evidence')
    open_details(j, "document.querySelector('#evidence-tools')", 'Open existing fictional evidence import')
    j.fill('#evidence-text', text)
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.click('#evidence-import-form button[type="submit"]', 'Register independently authored fictional evidence')
    rendered_after(j, revision, case_id)
    wait_board_idle(j)


def assess_evidence(j: Journey, question_id: int, evidence_id: int, case_id: str) -> int:
    j.go('evidence')
    open_details(j, "document.querySelector('#evidence-assessment-form').closest('details')",
                 'Open the existing evidence assessment form')
    j.select('#evidence-question-choice', str(question_id))
    j.select('#evidence-source-choice', str(evidence_id))
    j.select('#evidence-relation', 'context')
    j.select('#evidence-applicability', 'limited')
    j.fill('#evidence-rationale', 'This independently authored fictional text demonstrates provenance only and makes no clinical claim.')
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.click('#evidence-assessment-form button[type="submit"]', 'Record the question-scoped fictional evidence assessment')
    rendered_after(j, revision, case_id)
    return next(item['id'] for item in j.state(case_id)['evidence_assessments']
                if item['question_id'] == question_id and item['evidence_version_id'] == evidence_id)


def shared_evidence(j: Journey, *, amend: bool = False) -> None:
    watch_chart(j)
    import_evidence(j, EVIDENCE, 'CASE-ALPHA')
    evidence_id = next(item['id'] for item in j.state()['evidence'] if item['evidence_key'] == 'EVID-WORKLIST')
    saved = {}
    for case_id in ('CASE-ALPHA', 'CASE-BETA'):
        if case_id == 'CASE-BETA':
            board(j)
            j.open_case(case_id)
            ready(j, case_id)
        qid = save_question(j, 'Which independently authored evidence supports the fictional ' + case_id + ' source?', case_id)
        assessment = assess_evidence(j, qid, evidence_id, case_id)
        snapshot = save_draft(j, qid, case_id, assessment)
        acknowledge(j, snapshot, case_id)
        state = j.state(case_id)
        saved[case_id] = next(item for item in state['snapshots'] if item['id'] == snapshot)
        record(j, next(item for item in state['questions'] if item['id'] == qid)['state'] == 'addressed',
               case_id + ' question was genuinely addressed before shared-evidence invalidation')
    board(j)
    expect_row(j, 'CASE-ALPHA', ALPHA, 'Reviewed Alpha starts with no open question or stale report')
    expect_row(j, 'CASE-BETA', BETA, 'Reviewed Beta starts with no open question or stale report')
    if amend:
        import_evidence(j, AMENDED_EVIDENCE, 'CASE-BETA')
    else:
        j.go('evidence')
        open_details(j, "document.querySelector('#evidence-withdraw-tools')", 'Open the existing evidence withdrawal form')
        j.select('#evidence-withdraw-id', str(evidence_id))
        j.fill('#evidence-withdraw-reason', 'The independently authored fictional evidence is retired to test dependency invalidation.')
        revision = j.cd.evaluate('window.__worklistChartRenders')
        j.click('#evidence-withdraw-form button[type="submit"]', 'Withdraw shared fictional evidence through its existing form')
        rendered_after(j, revision, 'CASE-BETA')
        wait_board_idle(j)
    before = canonical_selection(j)
    board(j)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1, 'stale': 1},
               'Shared evidence ' + ('amendment' if amend else 'withdrawal') + ' refreshes the nonselected Alpha row')
    expect_row(j, 'CASE-BETA', {**BETA, 'questions': 1, 'stale': 1},
               'Shared evidence invalidation refreshes the selected Beta row')
    for case_id, original in saved.items():
        state = j.state(case_id)
        snapshot = next(item for item in state['snapshots'] if item['id'] == original['id'])
        record(j, snapshot['state'] == 'stale'
               and snapshot['source_ids'] == original['source_ids']
               and snapshot['evidence_assessment_ids'] == original['evidence_assessment_ids']
               and snapshot['summary'] == original['summary']
               and next(item for item in state['questions'] if item['id'] == snapshot['question_id'])['state'] == 'open',
               case_id + ' retains the historical report and exact bindings while its question reopens')
    record(j, canonical_selection(j) == before and before['selected'] == 'CASE-BETA',
           'Refreshing shared-evidence results never selects or renders Alpha as the current chart')
    j.capture('shared-evidence-amended' if amend else 'shared-evidence-withdrawn')


def question_count(j: Journey) -> None:
    watch_chart(j)
    board(j)
    expect_row(j, 'CASE-ALPHA', ALPHA, 'Initial Alpha summary has the seeded source facts and no questions')
    save_question(j, 'Which independently authored Alpha observation needs a source check?')
    board(j)
    expect_row(j, 'CASE-ALPHA', {**ALPHA, 'questions': 1},
               'A successful question save updates its worklist count without a reload or file import')
    expect_row(j, 'CASE-BETA', BETA, 'Saving an Alpha question leaves Beta summary unchanged')
    j.capture('question-count')


def main() -> None:
    output = Path(os.environ.get('OI_WORKLIST_ARTIFACT_DIR', ROOT / '.ui-artifacts' / 'worklist')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    chrome = os.environ.get('OI_CHROME') or next((path for name in
        ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
        if (path := shutil.which(name))), None)
    if not chrome:
        raise AssertionError('Chrome/Chromium unavailable: worklist freshness not verified')
    report = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'product_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                           for name in ('web/app.js', 'web/index.html', 'web/workspace-entry.js')},
        'data': 'Existing independently authored fictional Alpha/Beta fixtures plus original fictional questions, sources and evidence',
        'chrome': chrome, 'scenarios': [],
    }
    scenarios = [
        ('question-count', question_count, False),
        ('review-amendment-history', review_amendment, False),
        ('pasted-source-recency', source_recency, False),
        ('file-intake-parity', file_intake, False),
        ('manual-refresh-recovery', manual_refresh, False),
        ('outside-session-refresh', outside_session_refresh, False),
        ('late-board-success', late_board_read, False),
        ('late-board-failure', lambda j: late_board_read(j, fail=True), False),
        ('newer-full-list', newer_full_refresh, False),
        ('initial-summary-recovery', initial_summary_recovery, False),
        ('shared-evidence-withdrawal', shared_evidence, False),
        ('shared-evidence-amendment', lambda j: shared_evidence(j, amend=True), False),
        ('question-count-standard', question_count, True),
    ]
    requested = os.environ.get('OI_WORKLIST_SCENARIOS')
    if requested:
        selected = {name.strip() for name in requested.split(',') if name.strip()}
        unknown = selected - {name for name, _, _ in scenarios}
        if not selected or unknown:
            raise AssertionError('Unknown or empty worklist scenario selection: ' + repr(sorted(unknown)))
        scenarios = [scenario for scenario in scenarios if scenario[0] in selected]
    for name, exercise, standard in scenarios:
        current = {'name': name, 'checks': [], 'screenshots': [], 'browser_errors': []}
        directory = output / name
        directory.mkdir(exist_ok=True)
        try:
            with browser_session(chrome, directory, current, standard=standard) as journey:
                exercise(journey)
        except Exception as error:
            current['checks'].append({'check': 'Scenario completed', 'passed': False,
                                      'details': f'{type(error).__name__}: {error}'})
        current['passed'] = all(check['passed'] for check in current['checks'])
        report['scenarios'].append(current)
        (directory / 'verification.json').write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
        print(('PASS' if current['passed'] else 'FAIL') + ': ' + name, flush=True)
    checks = [check for scenario in report['scenarios'] for check in scenario['checks']]
    failures = [check for check in checks if not check['passed']]
    report['summary'] = {'scenarios': len(report['scenarios']), 'checks': len(checks),
                         'passed': len(checks) - len(failures), 'failed': len(failures)}
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    (output / 'workspace-worklist-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'summary': report['summary'], 'failures': failures}), flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
