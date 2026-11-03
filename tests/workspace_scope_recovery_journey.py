"""Real Chromium regressions for selected-case presentation and recovery.

Uses the existing fictional Alpha/Beta fixtures, launcher and CDP utilities.
OI_SCOPE_ARTIFACT_DIR selects the JSON observations/screenshots directory;
OI_CHROME can select an already installed Chrome executable. No browser package,
external provider, actual patient record or production dependency is added.

Assertions aggregate across three independently launched browser sessions so a
baseline run records every defect rather than stopping at the first failure.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from workspace_navigation_journey import ROOT, browser_session


# Chromium can return rectangles for descendants of closed native <details>.
# Those descendants are not visible or usable. Account for each disclosure's
# summary exception instead of treating rectangles alone as visibility evidence.
STRICT_VISIBLE = """element => {
  if (!element || element.closest('[hidden]') || !element.getClientRects().length ||
      getComputedStyle(element).display === 'none' ||
      getComputedStyle(element).visibility === 'hidden') return false;
  for (let parent=element.parentElement; parent; parent=parent.parentElement) {
    if (parent.tagName === 'DETAILS' && !parent.open) {
      const summary=parent.querySelector(':scope > summary');
      if (!summary || !summary.contains(element)) return false;
    }
  }
  return true;
}"""


def ready(journey, case_id: str) -> None:
    encoded = json.dumps(case_id)
    journey.cd.wait(f'caseId === {encoded} && active?.case.case_id === {encoded} && '
                    f'renderedCaseId === {encoded}', f'{case_id} ready')
    settled(journey)


def settled(journey) -> None:
    journey.cd.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


def record(journey, condition: bool, label: str, details=None) -> None:
    entry = {'mode': 'scope-recovery', 'check': label, 'passed': bool(condition)}
    if details is not None:
        entry['details'] = details
    journey.report['checks'].append(entry)


def inspect(journey) -> dict:
    return journey.cd.evaluate(f"""(() => {{
      const visible={STRICT_VISIBLE};
      const text=id => {{
        const element=document.getElementById(id);
        if (!visible(element)) return '';
        const walker=document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        const result=[];
        while(walker.nextNode()) if(visible(walker.currentNode.parentElement))
          result.push(walker.currentNode.textContent.trim());
        return result.filter(Boolean).join(' ');
      }};
      const route=document.body.dataset.view;
      const currentView=document.querySelector('[data-workspace-view="'+route+'"]');
      return {{
        caseId, ready:Boolean(active && active.case.case_id === caseId && renderedCaseId === caseId), route,
        intakeOpen:document.querySelector('#source-intake').open,
        fileVisible:visible(document.querySelector('#source-file')),
        notice:text('notice'),
        noticeLinks:[...document.querySelectorAll('#notice a')].filter(visible).map(a=>a.getAttribute('href')),
        setup:text('workspace-start'),
        journeyVisible:visible(document.querySelector('#journey-steps')),
        journey:text('journey-steps'),
        currentViewVisible:visible(currentView),
        loadingVisible:visible(document.querySelector('#workspace-loading')),
        sourceLabel:text('source-intake-case'),
        chartText:['case-heading','case-reference','assertion-list','source-list','snapshot-list','patient-findings']
          .map(text).join(' | ')
      }};
    }})()""")


def observe(journey, label: str) -> dict:
    result=inspect(journey)
    journey.report['observations'].append({'label':label, **result})
    return result


def no_alpha_presentation(journey, label: str, snapshot_id: int) -> None:
    state=observe(journey, label)
    exposed=' '.join([state['setup'],state['chartText'],state['sourceLabel'],state['notice']])
    record(journey, 'ALPHA' not in exposed.upper(), label+': no Alpha text in visible selected-case surfaces', state)
    record(journey, '#snapshot-'+str(snapshot_id) not in state['noticeLinks'],
           label+': no Alpha saved-report action', state)


def save_alpha_report(journey, *, first_question: bool = False) -> int:
    ready(journey,'CASE-ALPHA')
    if first_question:
        journey.go('questions')
        journey.fill('#question-text', 'What original source supports this independently authored Alpha observation?')
        journey.click('#question-form button[type="submit"]','Save fictional Alpha question')
        journey.cd.wait("document.querySelector('#question-list .question') && !document.querySelector('#question-text').value",
                        'question persisted')
    question_id=journey.state()['questions'][0]['id']
    journey.go('investigations')
    journey.select('#question-choice',str(question_id))
    journey.fill('#draft-observations','A fictional Alpha observation is retained with its original source version for this regression.')
    journey.cd.evaluate("document.querySelector('#source-choice input').checked=true")
    previous={item['id'] for item in journey.state()['snapshots']}
    journey.click('#draft-form button[type="submit"]','Save source-bound fictional Alpha draft')
    journey.cd.wait("!!document.querySelector('#notice a[href^=\"#snapshot-\"]') && !document.querySelector('#draft-observations').value",
                    'saved-report action visible')
    ready(journey,'CASE-ALPHA')
    snapshot_id=int(journey.cd.evaluate("document.querySelector('#notice a[href^=\"#snapshot-\"]').getAttribute('href').slice(10)"))
    journey.cd.wait(f'active.snapshots.some(item=>item.id === {snapshot_id})','saved report in rendered state')
    record(journey,snapshot_id not in previous,'A new Alpha report was actually saved',{'snapshot_id':snapshot_id})
    return snapshot_id


def exercise_disclosures(journey) -> None:
    ready(journey,'CASE-ALPHA')
    journey.cd.command('Page.navigate',{'url':journey.url+'?scope-recovery=initial#source-intake'})
    journey.cd.wait("location.search === '?scope-recovery=initial' && document.body.classList.contains('ux-ready')",
                    'fresh source-intake deep link')
    ready(journey,'CASE-ALPHA')
    state=observe(journey,'Initial source-intake deep link with existing sources')
    record(journey,state['route']=='source-intake' and state['intakeOpen'] and state['fileVisible'],
           'Initial source-intake deep link exposes the file control after the first case load',state)
    journey.capture('scope-initial-intake')

    journey.cd.evaluate("workspacePresentation.navigate('source-intake')")
    settled(journey)
    journey.click('#source-intake > summary','Manually collapse the active intake disclosure')
    settled(journey)
    state=inspect(journey)
    record(journey,not state['intakeOpen'] and not state['fileVisible'],
           'Closed native disclosure really hides the file control',state)
    journey.cd.evaluate('refresh()')
    ready(journey,'CASE-ALPHA')
    state=observe(journey,'Ordinary same-case refresh after manual disclosure collapse')
    record(journey,not state['intakeOpen'] and not state['fileVisible'],
           'Ordinary same-case rerender preserves the user-collapsed disclosure',state)

    journey.cd.evaluate("workspacePresentation.navigate('source-intake')")
    settled(journey)
    journey.select('#case-picker','CASE-BETA')
    ready(journey,'CASE-BETA')
    state=observe(journey,'Same-route case change to another case with sources')
    record(journey,state['route']=='source-intake' and state['intakeOpen'] and state['fileVisible'],
           'Same-route case change keeps the active intake form reachable',state)
    journey.capture('scope-case-change-intake')
    # Independently reopen before the next assertion, even on the failing
    # baseline. A prior case-change defect must not manufacture a second defect.
    journey.cd.evaluate("workspacePresentation.navigate('source-intake')")
    settled(journey)
    journey.cd.evaluate('refresh()')
    ready(journey,'CASE-BETA')
    state=inspect(journey)
    record(journey,state['intakeOpen'] and state['fileVisible'],
           'Ordinary same-case rerender preserves the user-open disclosure',state)


def exercise_saved_notice(journey) -> None:
    snapshot_id=save_alpha_report(journey,first_question=True)
    journey.select('#case-picker','CASE-BETA')
    ready(journey,'CASE-BETA')
    state=observe(journey,'Saved Alpha notice after successful Beta transition')
    record(journey,'#snapshot-'+str(snapshot_id) not in state['noticeLinks'] and
           ('Draft #'+str(snapshot_id)+' saved') not in state['notice'],
           'Successful Beta transition removes the Alpha saved-report notice and action',state)
    record(journey,not journey.state('CASE-BETA')['snapshots'],'Beta has no Alpha report in its canonical state')
    journey.capture('scope-saved-notice')

    journey.select('#case-picker','CASE-ALPHA')
    ready(journey,'CASE-ALPHA')
    save_alpha_report(journey)
    warning='Fictional global research-service warning for the scope regression.'
    journey.cd.evaluate('notice('+json.dumps(warning)+',true)')
    journey.select('#case-picker','CASE-BETA')
    ready(journey,'CASE-BETA')
    state=observe(journey,'Global notice replacing a report notice before a case change')
    record(journey,state['notice']==warning,
           'Unrelated global notice survives a case change after replacing a saved-report notice',state)


def exercise_loading_failure(journey) -> None:
    snapshot_id=save_alpha_report(journey,first_question=True)
    journey.go('overview')
    journey.cd.evaluate("""(() => {
      const originalFetch=window.fetch;
      const isBeta=input=>String(input).endsWith('/api/cases/CASE-BETA/state');
      window.__oiScopeBetaReads=0;
      window.__oiScopeRestoreFetch=()=>{
        window.fetch=(input,options)=>{
          if(isBeta(input))window.__oiScopeBetaReads++;
          return originalFetch(input,options);
        };
      };
      window.fetch=(input,options)=>{
        if(!isBeta(input))return originalFetch(input,options);
        window.__oiScopeBetaReads++;
        return new Promise((resolve,reject)=>{window.__oiScopeFail=()=>reject(new Error('Controlled fictional Beta state-load failure'));});
      };
    })()""")
    # A native change can run microtasks between event listeners. A surrounding
    # evaluate/dispatchEvent call keeps a script on the stack and misses that
    # ordering, so use real keyboard input for this pending/failure transition.
    journey.check(journey.visible('#case-picker'), 'Case picker is visible for native keyboard selection')
    journey.cd.evaluate("""(() => {
      const picker=document.querySelector('#case-picker');
      if(picker.value!=='CASE-ALPHA' || picker.options[picker.selectedIndex+1]?.value!=='CASE-BETA')
        throw Error('Native selection requires Alpha followed by Beta');
      window.__oiScopeNativeChange=null;
      picker.addEventListener('change',event=>{
        window.__oiScopeNativeChange={trusted:event.isTrusted,value:picker.value};
      },{once:true});
      picker.focus();
    })()""")
    journey.key('ArrowDown',40)
    journey.key('Enter',13)
    native_change=journey.cd.evaluate('window.__oiScopeNativeChange')
    record(journey,native_change=={'trusted':True,'value':'CASE-BETA'},
           'The Alpha-to-Beta transition came from a native trusted picker change',native_change)
    journey.cd.wait("caseId === 'CASE-BETA' && active === null && typeof window.__oiScopeFail === 'function'",
                    'Beta request held pending')
    settled(journey)
    no_alpha_presentation(journey,'Beta loading in the patient chart',snapshot_id)
    state=inspect(journey)
    record(journey,not state['currentViewVisible'] and state['loadingVisible'],
           'Pending Beta state hides prior chart contents and exposes loading status',state)
    journey.go('workspace-start')
    settled(journey)
    no_alpha_presentation(journey,'Beta loading in global workspace setup',snapshot_id)
    record(journey,not inspect(journey)['journeyVisible'],
           'Global setup hides case-specific progress while Beta is pending')
    journey.cd.evaluate('window.__oiScopeFail()')
    journey.cd.wait("document.querySelector('#notice').textContent.includes('Controlled fictional Beta state-load failure')",
                    'controlled Beta failure displayed')
    settled(journey)
    no_alpha_presentation(journey,'Beta failure in global workspace setup',snapshot_id)
    record(journey,not inspect(journey)['journeyVisible'],
           'Global setup keeps prior case progress hidden after Beta fails')
    journey.capture('scope-failed-case-setup')
    journey.cd.evaluate("workspacePresentation.navigate('reports')")
    settled(journey)
    no_alpha_presentation(journey,'Beta failure in patient report view',snapshot_id)
    state=inspect(journey)
    record(journey,not state['currentViewVisible'] and state['loadingVisible'],
           'Failed Beta state keeps prior report content hidden and exposes unavailable status',state)
    journey.cd.evaluate('window.__oiScopeRestoreFetch()')
    journey.go('incoming-board')
    reads_before=journey.cd.evaluate('window.__oiScopeBetaReads')
    journey.click('#incoming-list [data-case-search*="CASE-BETA"] button',
                  'Retry the unavailable Beta chart from its actual worklist row')
    reads_after=journey.cd.evaluate('window.__oiScopeBetaReads')
    record(journey,reads_after==reads_before+1,
           'Reopening the unavailable case starts one real state retry immediately',
           {'before':reads_before,'after':reads_after})
    # The normal event handler starts fetch synchronously. Fail promptly if the
    # worklist action was incorrectly treated as a ready-case no-op; do not wait
    # for a state response that was never requested.
    if reads_after!=reads_before+1:
        return
    ready(journey,'CASE-BETA')
    journey.go('workspace-start')
    state=observe(journey,'Beta recovered through the existing refresh owner')
    record(journey,state['journeyVisible'] and 'CASE-BETA' in state['journey'] and 'CASE-ALPHA' not in state['journey'],
           'Recovery restores only Beta progress through the existing state owner',state)
    record(journey,len(journey.state('CASE-ALPHA')['snapshots'])==1 and not journey.state('CASE-BETA')['snapshots'],
           'Failure and recovery preserve the saved Alpha report and Beta isolation')


def main() -> None:
    output=Path(os.environ.get('OI_SCOPE_ARTIFACT_DIR',ROOT/'.ui-artifacts'/'scope-recovery'))
    output.mkdir(parents=True,exist_ok=True)
    report={'started_at':datetime.now(timezone.utc).isoformat(),
            'data':'Existing independently authored Alpha/Beta fictional fixtures only',
            'checks':[],'observations':[],'screenshots':[],'browser_errors':[]}
    chrome=os.environ.get('OI_CHROME') or next((path for name in
        ('google-chrome','google-chrome-stable','chromium','chromium-browser')
        if (path:=shutil.which(name))),None)
    if not chrome:
        raise AssertionError('Chrome/Chromium is unavailable: scope/recovery journey not verified')
    report['chrome']=chrome
    for name,exercise in (('disclosures',exercise_disclosures),('saved-notice',exercise_saved_notice),
                          ('loading-failure',exercise_loading_failure)):
        scenario_output=output/name
        scenario_output.mkdir(exist_ok=True)
        try:
            with browser_session(chrome,scenario_output,report) as journey:
                exercise(journey)
        except Exception as error:
            report['checks'].append({'mode':'scope-recovery','check':name+' scenario completed',
                                     'passed':False,'details':f'{type(error).__name__}: {error}'})
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    failures=[check for check in report['checks'] if not check['passed']]
    report['summary']={'checks':len(report['checks']),'passed':len(report['checks'])-len(failures),'failed':len(failures)}
    (output/'workspace-scope-recovery-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'summary':report['summary'],'failures':failures,'browser_errors':report['browser_errors']}))
    if failures:
        raise AssertionError(f'{len(failures)} scope/recovery assertions failed; see aggregated JSON evidence')


if __name__=='__main__':
    main()
