"""Keyboard entry to real authorized source history; no replacement HTTP data."""
import base64
import json


def exercise(cd, out):
    def key(name, code):
        cd.command('Input.dispatchKeyEvent', {'type':'rawKeyDown','key':name,'code':name,'windowsVirtualKeyCode':code})
        if name == 'Enter':
            cd.command('Input.dispatchKeyEvent', {'type':'char','text':'\r','key':name,'windowsVirtualKeyCode':code})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':name,'code':name,'windowsVirtualKeyCode':code})

    def request_sources():
        cd.evaluate("document.querySelector('[data-testid=load-sources]').focus()")
        key('Enter', 13)

    def loaded():
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length===2", 'source-entry actual current and historical response')

    # Count actual requests, and optionally delay delivery of a real response.
    # The response body, status and server authorization are never substituted.
    cd.evaluate("""(() => {
      const original=window.fetch;
      const state={original,calls:[],hold:false,release:null,status:null};
      window.__sourceEntry=state;
      window.fetch=async(input,init)=>{
        const path=typeof input==='string'?input:input.url;
        state.calls.push({path,method:init?.method??'GET'});
        const response=await original(input,init);
        if(state.hold&&path.endsWith('/sources')&&(init?.method??'GET')==='GET'){
          state.hold=false;state.status=response.status;
          await new Promise(resolve=>{state.release=()=>{state.release=null;resolve();};});
        }
        return response;
      };
    })()""")
    observations=[]
    try:
        for width,height in ((390,900),(1280,900),(320,256)):
            cd.command('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
            patient=cd.evaluate("document.querySelector('[data-testid=workspace-identity]').textContent")
            cd.evaluate('window.__sourceEntry.calls=[]')
            request_sources();loaded()
            cd.wait("document.activeElement===document.querySelector('#sources-heading')", 'requested source history receives focus')
            cd.wait("(()=>{const r=document.activeElement.getBoundingClientRect();const h=document.querySelector('.topbar');return r.top>=0&&r.bottom<=innerHeight&&(h.dataset.sticky==='false'||r.top>=h.getBoundingClientRect().bottom)})()", 'source heading fully visible below workspace context')
            assert cd.evaluate("(()=>{const r=document.activeElement.getBoundingClientRect();const h=document.querySelector('.topbar');const edge=h.dataset.sticky==='false'?0:h.getBoundingClientRect().bottom;return r.top>=edge&&r.top<=edge+32})()"), 'Entry positions the heading beneath context, leaving room to read instead of focusing at the bottom edge'
            assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), 'Source entry retains narrow reflow'
            assert cd.evaluate("document.querySelector('[data-testid=workspace-identity]').textContent")==patient
            assert cd.evaluate("document.querySelector('#source-filter').value===''&&document.querySelector('#source-state').value==='all'"), 'Existing fresh-response filter reset retained'
            assert cd.evaluate("window.__sourceEntry.calls.length===1&&window.__sourceEntry.calls[0].method==='GET'&&window.__sourceEntry.calls[0].path.endsWith('/sources')"), 'Focus adds no request or write to the explicit source read'
            observations.append(cd.evaluate("(()=>{const r=document.activeElement.getBoundingClientRect();return {width:innerWidth,height:innerHeight,activeId:document.activeElement.id,headingTop:r.top,headingBottom:r.bottom,requests:window.__sourceEntry.calls.length}})()"))
            (out/f'source-entry-{width}-{height}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
            key('Tab',9)
            assert cd.evaluate("document.activeElement===document.querySelector('[data-testid=reviewed-document-disclosure]>summary')"), 'Tab enters the existing source controls in document order'

        cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':900,'deviceScaleFactor':1,'mobile':False})
        # Moving to a different control cancels the pending focus intention.
        cd.evaluate('window.__sourceEntry.hold=true')
        request_sources()
        cd.wait('Boolean(window.__sourceEntry.release)', 'real authorized source response held for focus-choice check')
        assert cd.evaluate('window.__sourceEntry.status===200')
        cd.evaluate("document.querySelector('.workspace-navigation-link').focus()")
        key('Tab',9)
        assert cd.evaluate("document.activeElement===document.querySelector('#reading-view')")
        cd.evaluate('window.__sourceEntry.release()');loaded()
        cd.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        assert cd.evaluate("document.activeElement===document.querySelector('#reading-view')"), 'A late response cannot take focus from the chosen control'
        (out/'source-entry-retained-choice-390.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))

        # Leaving and returning while the response is pending cancels the old intention.
        cd.evaluate('window.__sourceEntry.hold=true')
        request_sources()
        cd.wait('Boolean(window.__sourceEntry.release)', 'real authorized source response held for section-change check')
        for section in ('Overview','Records'):
            cd.evaluate("[...document.querySelectorAll('#workspace-navigation button')].find(e=>e.textContent.startsWith("+json.dumps(section)+")).click()")
            cd.wait("document.activeElement===document.querySelector('h1')", 'section retains its requested heading focus')
        cd.evaluate('window.__sourceEntry.release()');loaded()
        cd.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        assert cd.evaluate("document.activeElement===document.querySelector('h1')&&document.querySelector('h1').textContent==='Records'"), 'Returning to Records must not replay a previous source-entry focus'

        # A new explicit action still works after either cancellation.
        request_sources();loaded()
        cd.wait("document.activeElement===document.querySelector('#sources-heading')", 'fresh deliberate source read recovers focus handoff')
        (out/'source-entry-observations.json').write_text(json.dumps(observations,indent=2))
        print('PASS SOURCE ENTRY: actual authorized reads focus visible source history; native Tab reaches existing controls; one GET and no write; desktop/mobile/short viewport; delayed responses preserve chosen focus and section navigation; fresh action still works.')
    finally:
        cd.evaluate("if(window.__sourceEntry){window.fetch=window.__sourceEntry.original;window.__sourceEntry.release?.();delete window.__sourceEntry;}")
        cd.command('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
