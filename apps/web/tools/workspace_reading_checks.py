"""Reading regressions over the existing real API journey; no patient HTTP mocks.

Collect observations/screenshots before asserting, and restore temporary UI state.
Compact viewport and doubled-text stress are not a real browser-zoom certification.
"""
import json
import os
from pathlib import Path
from workspace_ux_checks import capture, navigate, set_value


def observe(cd, results, name, passed, details):
    screenshot = 'ux-reading-' + name + ('-pass.png' if passed else '-fail.png')
    capture(cd, screenshot)
    results.append({'check': name, 'passed': passed, 'details': details, 'screenshot': screenshot})


def source_selection(cd):
    return cd.evaluate("""({query:document.querySelector('#source-filter').value,
      status:document.querySelector('#source-state').value,
      rows:[...document.querySelectorAll('[data-testid=source-version]')].map(e=>({
        document:e.querySelector('h4').textContent.trim(),state:e.querySelector('.badge').textContent})),
      statements:[...document.querySelectorAll('[data-testid=source-statement]')].map(e=>e.textContent)})""")


def check_reading_workspace(cd):
    results = []
    original = cd.evaluate("""({width:innerWidth,height:innerHeight,x:scrollX,y:scrollY,
      view:document.querySelector('#reading-view').value,
      query:document.querySelector('#source-filter').value,status:document.querySelector('#source-state').value})""")
    calls = "performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.startsWith('/v1/')).length"
    expected = {'query': 'DOC-ONE', 'status': 'current',
                'rows': [{'document': 'DOC-ONE v2', 'state': 'current'}],
                'statements': ['Amended fictional marker is reported negative.']}
    try:
        # A return to the same response must retain the reader's narrowing choices.
        set_value(cd, '#source-filter', 'DOC-ONE'); set_value(cd, '#source-state', 'current')
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'active current-version filter')
        before = cd.evaluate(calls)
        navigate(cd, 'Overview'); set_value(cd, '#reading-view', 'clinical')
        cd.wait("document.querySelector('.app').dataset.view==='clinical'", 'changed reading preference')
        navigate(cd, 'Records')
        selection = source_selection(cd)
        requested = cd.evaluate(calls) - before
        observe(cd, results, 'filter-return', selection == expected and requested == 0,
                {'expected': expected, 'actual': selection, 'extra_patient_requests': requested})
        # Retention must not leak an old filter into a newly fetched response.
        set_value(cd, '#source-filter', 'DOC-ONE'); set_value(cd, '#source-state', 'current')
        before = cd.evaluate(calls)
        cd.evaluate("document.querySelector('[data-testid=refresh-sources]').click()")
        cd.wait(calls + '>' + str(before) + " && Boolean(document.querySelector('#source-filter')) && document.querySelector('[data-testid=records-workspace]').getAttribute('aria-busy')==='false'", 'completed real source refresh')
        selection = source_selection(cd)
        observe(cd, results, 'filter-refresh', selection['query'] == '' and selection['status'] == 'all'
                and selection['rows'] == [{'document': 'DOC-ONE v2', 'state': 'current'}, {'document': 'DOC-ONE v1', 'state': 'superseded'}]
                and selection['statements'] == expected['statements'], selection)
        set_value(cd, '#source-filter', ''); set_value(cd, '#source-state', 'all')
        set_value(cd, '#reading-view', 'patient')
        for name, width, height, enlarge in [('compact-focus', 320, 256, False), ('text-spacing-focus', 390, 844, True)]:
            cd.command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            cd.wait(f'innerWidth==={width} && innerHeight==={height}', 'reading stress viewport')
            if enlarge:
                # Snapshot all computed sizes before doubling, avoiding compounded inheritance.
                cd.evaluate("""(()=>{window.__oiReadingStyles=[...document.querySelectorAll('body,body *')]
                  .map(e=>({e,style:e.getAttribute('style'),size:parseFloat(getComputedStyle(e).fontSize)}));
                  for(const {e,size} of window.__oiReadingStyles)e.style.setProperty('font-size',(size*2)+'px','important');
                  const s=document.createElement('style');s.id='oi-reading-spacing';
                  s.textContent='*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';
                  document.head.append(s);})()""")
            # Shift+Tab uses native keyboard focus scrolling, not scrollIntoView.
            cd.evaluate("document.querySelector('#source-state').focus({preventScroll:true})")
            for event in ('keyDown', 'keyUp'):
                cd.command('Input.dispatchKeyEvent', {'type': event, 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9, 'modifiers': 8})
            geometry = cd.evaluate("""(()=>{const r=document.querySelector('#source-filter').getBoundingClientRect();
              const h=document.querySelector('.context-surface'),b=h.getBoundingClientRect();
              const sticky=['sticky','fixed'].includes(getComputedStyle(h).position)&&b.bottom>0&&b.top<innerHeight;
              return {focused:document.activeElement?.id,top:r.top,bottom:r.bottom,height:r.height,
                headerBottom:b.bottom,sticky,viewport:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth+1};})()""")
            visible = geometry['focused'] == 'source-filter' and geometry['height'] > 0 and geometry['top'] >= -1
            visible = visible and geometry['bottom'] <= height + 1 and not geometry['overflow']
            visible = visible and (not geometry['sticky'] or geometry['top'] >= geometry['headerBottom'] - 1)
            observe(cd, results, name, visible, geometry)
    finally:
        cd.evaluate("""(()=>{for(const {e,style} of window.__oiReadingStyles??[]){
          if(style===null)e.removeAttribute('style');else e.setAttribute('style',style);}
          delete window.__oiReadingStyles;document.querySelector('#oi-reading-spacing')?.remove();})()""")
        cd.command('Emulation.setDeviceMetricsOverride', {'width': original['width'], 'height': original['height'], 'deviceScaleFactor': 1, 'mobile': False})
        set_value(cd, '#reading-view', original['view'])
        set_value(cd, '#source-filter', original['query']); set_value(cd, '#source-state', original['status'])
        cd.evaluate(f"window.scrollTo({original['x']},{original['y']})")
    return results


def check_readiness_states(cd):
    """A readiness transition must be an accessible status without stealing focus."""
    results = []
    cd.command('Accessibility.enable'); cd.command('Network.enable')
    script = cd.command('Page.addScriptToEvaluateOnNewDocument', {'source': """(()=>{
      const observer=new MutationObserver(()=>{const field=document.querySelector('#credential');
        const badge=document.querySelector('[data-testid=readiness]');if(!field||!badge)return;
        if(!window.__oiReadinessFocus){field.focus();window.__oiReadinessFocus={
          sawChecking:badge.classList.contains('checking'),before:document.activeElement?.id};}
        if(!badge.classList.contains('checking')){window.__oiReadinessFocus.after=document.activeElement?.id;observer.disconnect();}
      });observer.observe(document,{subtree:true,childList:true,characterData:true});})()"""})['identifier']
    try:
        for expected, blocked in [('unavailable', ['http://127.0.0.1:4173/health/ready']), ('ready', [])]:
            cd.command('Network.setBlockedURLs', {'urls': blocked})
            cd.command('Page.reload', {'ignoreCache': True})
            cd.wait("Boolean(window.__oiReadinessFocus&&Object.hasOwn(window.__oiReadinessFocus,'after')) && document.querySelector('[data-testid=readiness]').classList.contains(" + json.dumps(expected) + ')', 'settled readiness ' + expected)
            root = cd.command('DOM.getDocument')['root']['nodeId']
            node = cd.command('DOM.querySelector', {'nodeId': root, 'selector': '[data-testid=readiness]'})['nodeId']
            ax = cd.command('Accessibility.getPartialAXTree', {'nodeId': node, 'fetchRelatives': False})['nodes'][0]
            props = {p['name']: p['value'].get('value') for p in ax.get('properties', [])}
            details = {'role': ax.get('role', {}).get('value'), 'live': props.get('live'),
                       'message': cd.evaluate("document.querySelector('[data-testid=readiness]').textContent.trim()"),
                       'focus': cd.evaluate('window.__oiReadinessFocus')}
            focus = details['focus']
            passed = details['role'] == 'status' and details['live'] == 'polite' and bool(details['message'])
            passed = passed and focus['sawChecking'] and focus['before'] == 'credential' and focus['after'] == 'credential'
            observe(cd, results, 'readiness-' + expected, passed, details)
    finally:
        cd.command('Network.setBlockedURLs', {'urls': []})
        cd.command('Page.removeScriptToEvaluateOnNewDocument', {'identifier': script})
        cd.command('Page.reload', {'ignoreCache': True})
        cd.wait("(()=>{const e=document.querySelector('[data-testid=readiness]');return e?.classList.contains('ready')&&Boolean(e.textContent.trim());})()", 'restored unblocked readiness')
    return results


def assert_reading_checks(results):
    target = Path(os.environ.get('OI_WEB_ARTIFACT_DIR', Path(__file__).resolve().parents[1] / '.evidence'))
    target.mkdir(parents=True, exist_ok=True)
    (target / 'reading-checks.json').write_text(json.dumps(results, indent=2) + '\n')
    for result in results:
        print('READING CHECK: ' + json.dumps(result), flush=True)
    failures = [result['check'] for result in results if not result['passed']]
    assert not failures, 'Reading regressions: ' + ', '.join(failures) + '; see reading-checks.json and captured screenshots'
