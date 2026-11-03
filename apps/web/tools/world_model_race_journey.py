"""Delay delivery of real World Model responses; never fabricate API content."""

import json
import re


_INSTALL_HOLD = """(path) => {
  if (window.__oiWorldModelRace) throw Error('World Model fetch guard already installed');
  const actualFetch = window.fetch;
  const target = new URL(path, location.origin).href;
  const state = {armed:false, held:null, reads:[], release:null, restored:false, failed:false};
  state.restore = () => {
    state.restored = true;
    window.fetch = actualFetch;
    state.release?.();
    delete window.__oiWorldModelRace;
  };
  window.__oiWorldModelRace = state;
  window.fetch = async (input, init) => {
    const url = input instanceof Request ? input.url : new URL(input, location.href).href;
    if (url !== target) return actualFetch.call(window, input, init);
    const hold = state.armed;
    state.armed = false;
    const startedAt = performance.now();
    const signal = init?.signal ?? (input instanceof Request ? input.signal : null);
    try {
      const response = await actualFetch.call(window, input, init);
      const body = await response.clone().json();
      const observed = {status:response.status, patient:body.patient_id, case:body.case_id,
        receipt:body.access_receipt_id, fingerprint:body.snapshot_fingerprint};
      state.reads.push(observed);
      if (hold && !state.restored) {
        await new Promise(resolve => {
          state.held = {...observed, number:state.reads.length, startedAt, signal, delivered:false};
          state.release = resolve;
        });
        state.held.delivered = true;
        state.release = null;
      }
      return response;
    } catch (error) {
      state.failed = true;
      throw error;
    }
  };
  return true;
}"""


def exercise(cd, *, patient_id, case_id, source_id, original, fingerprint,
             credentials, write_grants):
    """Enter/leave Journey with its existing source index and completed view."""
    previous_actions = list(credentials[0]['actions'])

    def navigate(section):
        cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("
                    + json.dumps(section) + ")).click()")
        test_id = 'records-workspace' if section == 'Records' else 'world-workspace'
        cd.wait(f"Boolean(document.querySelector('[data-testid={test_id}]'))", section+' screen')

    def open_original():
        cd.evaluate("[...document.querySelectorAll('[data-testid=source-version]')].find(e=>e.textContent.includes("
                    + json.dumps(source_id) + ")).querySelector('[data-testid=open-original]').click()")
        cd.wait("document.querySelector('[data-testid=server-original]')?.textContent==="
                + json.dumps(original), 'real separately authorized original bytes')

    def close_original():
        cd.evaluate("document.querySelector('[data-testid=opened-original] button').click()")
        cd.wait("!document.querySelector('[data-testid=opened-original]')", 'original closed')

    def completed_world():
        cd.wait("document.querySelector('[data-testid=world-fingerprint]')?.textContent==="
                + json.dumps(fingerprint), 'unchanged source fingerprint')
        assert cd.evaluate("!document.querySelector('[data-testid=world-load]').disabled")

    def observed_read(index):
        value = cd.evaluate(f"window.__oiWorldModelRace.reads[{index}]")
        assert value['status'] == 200 and value['patient'] == patient_id and value['case'] == case_id
        assert value['fingerprint'] == fingerprint
        assert re.fullmatch(r'ACCESS-[0-9A-F]{32}', value['receipt'])
        return value['receipt']

    try:
        credentials[0]['actions'] = sorted(set(previous_actions) | {'source_original_read'})
        write_grants()
        path = f'/v1/patients/{patient_id}/cases/{case_id}/world-model'
        cd.evaluate(f"({_INSTALL_HOLD})({json.dumps(path)})")
        for action in ('opening', 'closing'):
            navigate('Records')
            if action == 'closing':
                open_original()
            else:
                assert cd.evaluate("!document.querySelector('[data-testid=opened-original]')")
            navigate('Journey')
            completed_world()
            before = cd.evaluate('window.__oiWorldModelRace.reads.length')
            cd.evaluate("window.__oiWorldModelRace.armed=true;document.querySelector('[data-testid=world-load]').click()")
            cd.wait(f"window.__oiWorldModelRace.failed || window.__oiWorldModelRace.held?.number==={before+1}",
                    'actual completed World Model response held before delivery')
            assert not cd.evaluate('window.__oiWorldModelRace.failed')
            held_receipt = observed_read(before)
            assert cd.evaluate("!document.querySelector('[data-testid=world-projection]') && document.querySelector('[data-testid=world-load]').disabled")

            navigate('Records')
            open_original() if action == 'opening' else close_original()
            navigate('Journey')
            idle = ("!document.querySelector('[data-testid=world-projection]') && "
                    "!document.querySelector('[data-testid=world-load]').disabled && "
                    "!document.querySelector('[data-testid=world-load-cases]').disabled")
            cd.wait(idle, action+' original releases Journey loading controls')
            assert cd.evaluate('window.__oiWorldModelRace.reads.length') == before+1
            cd.evaluate("""(() => {
              const state=window.__oiWorldModelRace, held=state.held;
              if (!held.signal || held.signal.aborted || performance.now()-held.startedAt>=10000)
                throw Error('World Model race exceeded the client request deadline');
              state.release();
            })()""")
            cd.wait('window.__oiWorldModelRace.held.delivered', 'real held response delivered')
            # Render barrier, not a timer: let the released response and React updates settle.
            cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
            assert cd.evaluate(idle), 'A discarded response restored a World Model view'

            cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
            completed_world()
            assert cd.evaluate('window.__oiWorldModelRace.reads.length') == before+2
            assert observed_read(before+1) != held_receipt
            # Original inspection must preserve an already completed projection and its fingerprint.
            navigate('Records')
            if cd.evaluate("Boolean(document.querySelector('[data-testid=opened-original]'))"):
                close_original()
            open_original()
            close_original()
            navigate('Journey')
            completed_world()
            assert cd.evaluate('window.__oiWorldModelRace.reads.length') == before+2
    finally:
        try:
            cd.evaluate('window.__oiWorldModelRace?.restore()')
        finally:
            credentials[0]['actions'] = previous_actions
            write_grants()
    print('PASS WORLD MODEL RACES: actual completed PG/FastAPI responses held; original open/close releases loading; stale responses discarded; explicit retries have new receipts and unchanged fingerprints; completed views preserved; fetch and grants restored.')
