"""Real Chromium checks for worklist freshness over the existing case owner.

Uses the existing fictional launchers and CDP harness. All writes use visible
application forms; read-only HTTP state is an independent persistence oracle.
OI_WORKLIST_ARTIFACT_DIR selects reports, screenshots and process logs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from workspace_navigation_journey import ROOT, Journey, browser_session


ALPHA = {'date': '2026-05-17', 'sources': 2, 'questions': 0, 'stale': 0}
BETA = {'date': '2026-06-02', 'sources': 1, 'questions': 0, 'stale': 0}


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


def save_question(j: Journey, text: str, case_id: str = 'CASE-ALPHA') -> int:
    j.go('questions')
    revision = j.cd.evaluate('window.__worklistChartRenders')
    j.fill('#question-text', text)
    j.click('#question-form button[type="submit"]', 'Save an independently authored fictional question')
    rendered_after(j, revision, case_id)
    state = j.state(case_id)
    return next(item['id'] for item in state['questions'] if item['question'] == text)


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
        'data': 'Existing independently authored fictional Alpha/Beta fixtures and authored test questions only',
        'chrome': chrome, 'scenarios': [],
    }
    for name, exercise in [('question-count', question_count)]:
        current = {'name': name, 'checks': [], 'screenshots': [], 'browser_errors': []}
        directory = output / name
        directory.mkdir(exist_ok=True)
        try:
            with browser_session(chrome, directory, current) as journey:
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
