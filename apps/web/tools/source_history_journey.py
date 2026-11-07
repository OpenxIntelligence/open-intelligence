"""One receipt-time contract in Journey and Records; real PostgreSQL HTTP."""
import base64
import json
from semantic_history_journey import inspect as inspect_semantics


def exercise(cd, original, amended, expected_fingerprint, out, credentials, write_grants):
    previous = list(credentials[0]['actions'])
    try:
        if 'source_original_read' not in credentials[0]['actions']:
            credentials[0]['actions'].append('source_original_read'); write_grants()
        # Journey already shows the original historical context after amendment.
        cd.evaluate("document.querySelector('[data-testid=history-open-original]').click()")
        cd.wait("document.querySelector('[data-testid=server-original]')?.textContent==="+json.dumps(original),
                'Journey resolves exact historical bytes through current Records authority')
        cd.evaluate("document.querySelector('[data-testid=close-original]').click()")
        cd.wait("!document.querySelector('[data-testid=server-original]')", 'Journey original closes')
        credentials[0]['actions'].remove('source_original_read'); write_grants()
        receipts = cd.evaluate("[...document.querySelector('[data-testid=history-cutoff]').options].map(e=>e.value)")
        assert len(receipts) == 2 and receipts[0] != receipts[1]
        for version, (cutoff, raw) in enumerate(zip(receipts, (original, amended)), start=1):
            cd.evaluate("(()=>{const e=document.querySelector('[data-testid=history-cutoff]');e.value="+json.dumps(cutoff)+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
            cd.wait("!document.querySelector('[data-testid=history-result]')", 'receipt change clears the earlier history')
            cd.evaluate("document.querySelector('[data-testid=history-load]').click()")
            cd.wait("document.querySelectorAll('[data-testid=history-source]').length===1", 'one version at receipt cutoff')
            assert cd.evaluate("document.querySelector('[data-testid=history-source] strong').textContent") == 'DOC-ONE v'+str(version)
            if version == 1:
                assert cd.evaluate("document.querySelector('[data-testid=history-fingerprint]').textContent") == expected_fingerprint
            cd.evaluate("document.querySelector('[data-testid=history-open-original]').click()")
            if version == 1:
                cd.wait("document.querySelector('[data-testid=records-status]').textContent.includes('Original unavailable')", 'history does not confer original permission')
                assert not cd.evaluate("Boolean(document.querySelector('[data-testid=server-original]'))")
                inspect_semantics(cd,historical=True,status='missing',original_state='not-reported',
                    fingerprint=expected_fingerprint,
                    source_id=cd.evaluate("document.querySelector('[data-testid=history-source] code').textContent"))
                credentials[0]['actions'].append('source_original_read'); write_grants()
                cd.evaluate("document.querySelector('[data-testid=history-open-original]').click()")
            cd.wait("document.querySelector('[data-testid=server-original]')?.textContent==="+json.dumps(raw), 'exact selected original bytes')
            cd.evaluate("document.querySelector('[data-testid=close-original]').click()")
            cd.wait("document.activeElement===document.querySelector('[data-testid=history-open-original]')", 'focus returns to selected history action')
        for width,height in ((390,844),(1440,960)):
            cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
            cd.evaluate("document.querySelector('[data-testid=source-history]').scrollIntoView({block:'start'})")
            assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'history reflows on mobile'
            (out/f'unified-source-history-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
        cd.command('Emulation.clearDeviceMetricsOverride')
        cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=history-cutoff]')) && !document.querySelector('[data-testid=history-result]')", 'refresh discards history')
        cd.evaluate("[...document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')].find(b=>b.textContent.includes('Journey')).click()")
        cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
        cd.wait("document.querySelector('[data-testid=world-history-count]')?.textContent==='1'", 'current Journey restored')
        assert cd.evaluate("document.querySelector('[data-testid=world-reported-state]').textContent==='negative'")
        print('PASS UNIFIED HISTORY: same historical fingerprint in Journey and Records; exact amended and superseded originals; independent original denial/regrant; focus return; 390/1440 reflow; refresh cancellation; current Journey remains current.')
    finally:
        credentials[0]['actions'] = previous; write_grants()
