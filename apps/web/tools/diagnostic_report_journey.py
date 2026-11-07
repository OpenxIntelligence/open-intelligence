"""Exercise diagnostic filtering on persisted fictional sources in the real UI."""
import base64
import json


def select(cd, selector, value):
    cd.evaluate(f"""(()=>{{const e=document.querySelector({json.dumps(selector)});
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,{json.dumps(value)});
      e.dispatchEvent(new Event('change',{{bubbles:true}}));}})()""")


def pathology(cd, value, original):
    cd.wait("!!document.querySelector('#diagnostic-reported-state')", 'pathology report controls')
    value('#source-filter', 'Amended fictional marker')
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'statement search finds current amendment')
    select(cd, '#diagnostic-reported-state', 'state:negative')
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-finding]').length===1")
    assert cd.evaluate("document.querySelector('[data-testid=source-statement]').textContent.includes('negative')")
    value('#source-filter', 'no-matching-fictional-statement')
    cd.wait("!!document.querySelector('[data-testid=source-no-match]')", 'explicit no-match state')
    cd.evaluate("document.querySelector('[data-testid=clear-source-filters]').click()")
    cd.wait("document.activeElement.id==='source-filter'", 'clear returns focus to search')
    select(cd, '#source-state', 'superseded')
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'earlier pathology version remains inspectable')
    assert cd.evaluate("!document.querySelector('[data-testid=source-statement]') && !document.querySelector('[data-testid=ask-source-question]')")
    cd.evaluate("document.querySelector('[data-testid=open-original]').click()")
    cd.wait("document.querySelector('[data-testid=server-original]')?.textContent==="+json.dumps(original), 'exact earlier pathology bytes')


def molecular(cd, value, add_synthetic, root, case, original, out):
    # A collection larger than a page, with distinct explicit reported states.
    for i in range(13):
        text=original.replace('DOC-PATHOLOGY-LABEL',f'DOC-MOLECULAR-{i:02d}')
        text=text.replace('SPECIMEN-ONE',f'SPECIMEN-{i:02d}')
        state=('negative','pending','indeterminate')[i % 3]
        text=text.replace('marker|not-reported|Fictional café <script>literal</script>.',
                          f'marker|{state}|Fictional molecular statement {i:02d}.')
        status,_=add_synthetic(root+'/cases/'+case+'/sources',{'synthetic':True,'original_text':text})
        assert status==201
    row="[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.querySelector('code').textContent==="+json.dumps(case)+")"
    cd.evaluate(f"{row}.querySelector('[data-testid=load-sources]').click()")
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===12 && !!document.querySelector('[data-testid=diagnostic-report-pagination]')", 'bounded first report page')
    first=cd.evaluate("[...document.querySelectorAll('[data-testid=source-version]')].map(e=>e.dataset.sourceId)")
    cd.evaluate("[...document.querySelectorAll('[data-testid=diagnostic-report-pagination] button')].find(e=>e.textContent==='Next reports').click()")
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===2 && document.activeElement.matches('[data-testid=source-version] h4')", 'next page and keyboard focus')
    second=cd.evaluate("[...document.querySelectorAll('[data-testid=source-version]')].map(e=>e.dataset.sourceId)")
    assert len(set(first+second))==14
    select(cd, '#diagnostic-specimen', 'id:SPECIMEN-04')
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'specimen change returns to first matching page')
    assert cd.evaluate("document.querySelector('[data-testid=source-version] h4').textContent.includes('DOC-MOLECULAR-04')")
    assert cd.evaluate("!document.querySelector('[data-testid=diagnostic-report-pagination]')")
    cd.evaluate("document.querySelector('[data-testid=clear-source-filters]').click()")
    select(cd, '#diagnostic-reported-state', 'state:pending')
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===4", 'only pending statements, no negative or indeterminate conflation')
    assert cd.evaluate("[...document.querySelectorAll('[data-testid=source-finding] > p')].every(e=>e.textContent.includes('reported state: pending'))")
    value('#source-filter', 'statement 04')
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'state and literal quotation intersect')
    for width in (320,390,1440):
        cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("document.querySelector('[data-testid=diagnostic-report-controls]').scrollIntoView({block:'start'})")
        assert cd.evaluate("document.documentElement.scrollWidth<=innerWidth"), 'diagnostic controls reflow'
        png=cd.command('Page.captureScreenshot',{'format':'png'})
        (out/f'diagnostic-molecular-{width}.png').write_bytes(base64.b64decode(png['data']))
    cd.command('Emulation.clearDeviceMetricsOverride')
    selected=cd.evaluate("document.querySelector('[data-testid=source-version]').dataset.sourceId")
    cd.evaluate("document.querySelector('[data-testid=ask-source-question]').click()")
    cd.wait("document.querySelector('#workspace-navigation [aria-current=page]').textContent==='Investigations'", 'exact selected statement hands off to existing question owner')
    cd.wait("document.querySelector('[data-testid=question-draft-editor] code')?.textContent==="+json.dumps(selected), 'question draft retains the exact filtered original')
    assert cd.evaluate("document.querySelector('[data-testid=question-draft-editor]').textContent.includes('line 8.')")
