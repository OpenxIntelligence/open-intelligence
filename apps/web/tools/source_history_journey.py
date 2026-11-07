"""Actual received-time report history in React, FastAPI and PostgreSQL."""
import base64
import json


def exercise(cd, original, amended, out):
    receipts = cd.evaluate("[...document.querySelector('#source-history-cutoff').options].map(e=>e.value).filter(Boolean)")
    assert len(receipts) == 2 and receipts[0] != receipts[1]
    for version, (cutoff, text) in enumerate(zip(receipts, (original, amended)), start=1):
        cd.evaluate("(()=>{const e=document.querySelector('#source-history-cutoff');e.value="+json.dumps(cutoff)+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        cd.wait("!document.querySelector('[data-testid=source-history-result]')", 'changing cutoff clears earlier result')
        cd.evaluate("document.querySelector('[data-testid=source-history-check]').click()")
        cd.wait("document.querySelectorAll('[data-testid=source-history-version]').length===1", 'one document version held at the receipt')
        assert cd.evaluate("document.querySelector('[data-testid=source-history-version] strong').textContent") == 'DOC-ONE · version '+str(version)
        assert 'superseded' not in cd.evaluate("document.querySelector('[data-testid=source-history-result]').textContent")
        cd.evaluate("document.querySelector('[data-testid=source-history-version] button').click()")
        cd.wait("document.querySelector('[data-testid=server-original]')?.textContent==="+json.dumps(text), 'history opens exact source bytes')
        cd.evaluate("document.querySelector('[data-testid=close-original]').click()")
        cd.wait("document.activeElement===document.querySelector('[data-testid=source-history-version] button')", 'original closes back to selected history action')
    for width,height in ((390,844),(1440,960)):
        cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("document.querySelector('[data-testid=source-history]').scrollIntoView({block:'start'})")
        assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'historical records reflow'
        (out/f'source-history-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
    cd.command('Emulation.clearDeviceMetricsOverride')
    cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
    cd.wait("document.querySelector('#source-history-cutoff')?.value==='' && !document.querySelector('[data-testid=source-history-result]')", 'record refresh discards historical selection')
    print('PASS SOURCE HISTORY: receipt cutoff selects the prior or amended original; exact bytes, focus return, mobile reflow and refresh invalidation.')
