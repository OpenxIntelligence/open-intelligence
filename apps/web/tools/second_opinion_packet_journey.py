"""Actual packet UI -> FastAPI -> PostgreSQL; independently fictional case only."""
import base64
import hashlib
import json
from urllib.request import Request, urlopen

from followthrough_journey import navigate, fill, click, select_case, capture_failure


_OBSERVE = r"""() => {
 const actual=window.fetch;
 const state={writes:[],reads:[],drop:false,hold:false,release:null};
 state.restore=()=>{state.release?.();window.fetch=actual;delete window.__oiPacketChecks;};
 window.fetch=async(input,init)=>{
  const url=new URL(input instanceof Request?input.url:input,location.href);
  const response=await actual.call(window,input,init);
  if(!url.pathname.endsWith('/second-opinion-packets'))return response;
  const body=await response.clone().json();
  if(init?.method==='POST'){
   state.writes.push({path:url.pathname,command:JSON.parse(init.body),status:response.status,body});
   if(state.drop&&response.status===201){state.drop=false;throw new TypeError('Synthetic reply loss after real commit');}
  }else{
   state.reads.push({path:url.pathname,status:response.status,body});
   if(state.hold){state.hold=false;await new Promise(resolve=>{state.release=resolve;});state.release=null;}
  }
  return response;
 };
 window.__oiPacketChecks=state;return true;
}"""


def exercise(cd, patient_id, token, credentials, write_grants, add_synthetic, artifacts):
    case_id = 'CASE-PACKET-UI'
    root = '/v1/patients/' + patient_id
    case_root = root + '/cases/' + case_id
    before = list(credentials[0]['actions'])
    credentials[0]['actions'] = sorted(set(before) | {
        'patient_read', 'case_binding_read', 'case_binding_create', 'source_read',
        'source_import', 'composer_context_read', 'question_create', 'question_read',
        'second_opinion_packet_create', 'second_opinion_packet_read'})
    write_grants()

    def read_api(path):
        request = Request('http://127.0.0.1:8000' + path,
                          headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
        with urlopen(request, timeout=10) as response:
            assert response.status == 200
            return json.load(response)

    def open_case(target):
        navigate(cd, 'Investigations')
        click(cd, '[data-testid=world-load-cases]')
        select_case(cd, target)
        click(cd, '[data-testid=load-source-questions]')
        cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent.includes('Clinical approval')",
                'independent saved-question read for packet case')
        navigate(cd, 'Overview')

    try:
        status, _ = add_synthetic(root + '/case-bindings', {
            'synthetic': True, 'case_id': case_id, 'source_organization': 'ORG-FICTIONAL-PACKET',
            'source_system': 'SYS-SYNTH', 'source_subject_ref': 'FICTIONAL-PACKET-SUBJECT',
            'review_ref': 'FICTIONAL-PACKET-REVIEW'})
        assert status == 201
        original = ('OI-SYNTHETIC-REPORT/1\nPatient: CASE-PACKET-UI\nDocument: PACKET-DOC\n'
                    'Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n'
                    'Specimen: FICTIONAL-SPECIMEN\n'
                    'Finding: marker|not-reported|Independently fictional packet marker remains unresolved.\n')
        status, source = add_synthetic(case_root + '/sources', {'synthetic': True, 'original_text': original})
        assert status == 201
        source_id = source['source_id']
        model = read_api(case_root + '/world-model')
        focus = 'Which exact fictional source wording belongs in the discussion packet?'
        status, preflight = add_synthetic(case_root + '/composer/source-preflight', {
            'synthetic': True, 'expected_source_snapshot_sha256': model['snapshot_fingerprint'],
            'source_id': source_id, 'source_line': 8, 'question': focus})
        assert status == 200
        status, question = add_synthetic(case_root + '/questions', {
            'synthetic': True, 'request_key': 'PACKET-UI-QUESTION-ONE', 'question': focus,
            'source_id': source_id, 'source_line': 8,
            'expected_source_snapshot_sha256': preflight['source_snapshot_sha256'],
            'expected_preflight_sha256': preflight['preflight_sha256']})
        assert status == 201
        question_id = question['question_id']
        cd.evaluate('(' + _OBSERVE + ')()')
        open_case(case_id)
        cd.wait("Boolean(document.querySelector('[data-testid=packet-source]'))", 'exact selectable packet source')
        assert cd.evaluate("document.querySelectorAll('.packet-compose input[type=checkbox]:checked').length") == 0
        assert cd.evaluate('window.__oiPacketChecks.writes.length') == 0
        assert cd.evaluate("document.querySelector('[data-testid=packet-save]').disabled")
        click(cd, '[data-testid=packet-refresh]')
        cd.wait("Boolean(document.querySelector('[data-testid=packet-empty]'))", 'verified empty packet list')
        cd.evaluate("document.querySelector('.packet-compose').open=true")
        fill(cd, '[data-testid=packet-title]', 'Fictional source discussion packet')
        click(cd, '[data-testid=packet-source][data-source-id="' + source_id + '"]')
        click(cd, '[data-testid=packet-question][data-question-id="' + question_id + '"]')
        # Navigation is read-only and retains literal unsent selection.
        navigate(cd, 'Records')
        navigate(cd, 'Overview')
        assert cd.evaluate("document.querySelector('[data-testid=packet-title]').value") == 'Fictional source discussion packet'
        assert cd.evaluate('window.__oiPacketChecks.writes.length') == 0
        click(cd, '[data-testid=packet-confirm]')
        cd.evaluate('window.__oiPacketChecks.drop=true')
        click(cd, '[data-testid=packet-save]')
        cd.wait("document.querySelector('[data-testid=packet-write-status]')?.dataset.phase==='unknown'", 'lost committed packet reply')
        assert cd.evaluate("document.querySelector('[data-testid=packet-title]').matches(':disabled')")
        click(cd, '[data-testid=packet-retry]')
        cd.wait("document.querySelector('[data-testid=packet-write-status]')?.dataset.phase==='saved'", 'exact packet receipt recovery')
        writes = cd.evaluate('window.__oiPacketChecks.writes')
        assert len(writes) == 2 and writes[0]['command'] == writes[1]['command']
        assert [w['status'] for w in writes] == [201, 200]
        packet_id = writes[0]['body']['packet_id']
        assert writes[1]['body'] == {'packet_id': packet_id, 'duplicate': True}
        assert writes[0]['command']['source_ids'] == [source_id]
        assert writes[0]['command']['question_ids'] == [question_id]
        click(cd, '[data-testid=packet-refresh]')
        cd.wait("document.querySelector('[data-testid=saved-packet]')?.dataset.packetId===" + json.dumps(packet_id), 'durable packet reopened')
        assert cd.evaluate("document.querySelectorAll('[data-testid=saved-packet]').length") == 1
        assert cd.evaluate("document.querySelector('[data-testid=saved-packet]').dataset.state") == 'current_preparation'
        authorized = read_api(case_root + '/second-opinion-packets')
        assert len(authorized['packets']) == 1
        assert authorized['packets'][0]['sources'][0]['sha256'] == hashlib.sha256(original.encode()).hexdigest()
        credentials[0]['actions'].remove('second_opinion_packet_read'); write_grants()
        click(cd, '[data-testid=packet-refresh]')
        cd.wait("document.querySelector('[data-testid=packet-read-status]')?.dataset.phase==='error'", 'independent packet denial')
        assert cd.evaluate("document.querySelectorAll('[data-testid=saved-packet]').length") == 0
        assert cd.evaluate("Boolean(document.querySelector('[data-testid=packet-question]'))"), 'Independent questions stay readable'
        credentials[0]['actions'].append('second_opinion_packet_read'); write_grants()
        amended = original.replace('Issued-At: 2026-01-11', 'Issued-At: 2026-01-12').replace(
            'marker|not-reported|Independently fictional packet marker remains unresolved.',
            'marker|negative|Independently fictional amended packet marker is reported negative.')
        assert add_synthetic(case_root + '/sources', {'synthetic': True, 'original_text': amended})[0] == 201
        open_case(case_id)
        click(cd, '[data-testid=packet-refresh]')
        cd.wait("document.querySelector('[data-testid=saved-packet]')?.dataset.state==='source_reassessment_required'", 'historical packet after amendment')
        assert cd.evaluate("document.querySelector('[data-testid=saved-packet]').dataset.packetId") == packet_id
        assert source_id in cd.evaluate("document.querySelector('[data-testid=saved-packet]').textContent")
        assert cd.evaluate("document.querySelectorAll('[data-testid=packet-question]').length") == 0
        assert cd.evaluate('window.__oiPacketChecks.writes.length') == 2, 'Amendment/navigation never writes a new packet'
        # Hold a real authorized old-case read, switch away, then deliver it.
        cd.evaluate('window.__oiPacketChecks.hold=true')
        click(cd, '[data-testid=packet-refresh]')
        cd.wait('Boolean(window.__oiPacketChecks.release)', 'held real packet read')
        assert cd.evaluate("!document.querySelector('[data-testid=saved-packet]')")
        navigate(cd, 'Investigations'); select_case(cd, 'CASE-ALPHA')
        click(cd, '[data-testid=load-source-questions]')
        cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent.includes('Clinical approval')", 'other case questions')
        navigate(cd, 'Overview')
        cd.evaluate('window.__oiPacketChecks.release()')
        cd.wait('window.__oiPacketChecks.release===null', 'release obsolete packet result')
        assert cd.evaluate("!document.querySelector('[data-testid=saved-packet]')")
        open_case(case_id);click(cd, '[data-testid=packet-refresh]')
        cd.wait("Boolean(document.querySelector('[data-testid=saved-packet]'))", 'fresh historical packet reread')
        for width in (1440, 390):
            cd.command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})
            cd.wait('window.innerWidth===' + str(width), 'packet capture viewport')
            cd.evaluate("document.querySelector('[data-testid=second-opinion-packets]').scrollIntoView({block:'start'})")
            assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            image=cd.command('Page.captureScreenshot', {'format':'png'})
            (artifacts / ('second-opinion-packet-' + str(width) + '.png')).write_bytes(base64.b64decode(image['data']))
        assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')
        (artifacts / 'second-opinion-packet-receipts.json').write_text(json.dumps({
            'patient_id': patient_id, 'case_id': case_id, 'packet_id': packet_id,
            'source_id': source_id, 'question_id': question_id, 'writes': writes,
            'final_projection': read_api(case_root + '/second-opinion-packets'),
            'no_navigation_writes': True, 'delayed_case_response_discarded': True,
            'independent_read_denial_clears_details': True, 'browser_storage_empty': True,
            'external_request_sent': False, 'clinical_approval': False,
        }, indent=2)+'\n', encoding='utf-8')
        print('PASS SECOND OPINION PACKETS: explicit exact selection; actual save and same-command retry; independent read denial; immutable historical source references after amendment; delayed-case response discarded; 1440/390 layout; no navigation writes or external dispatch.')
    except Exception:
        capture_failure(cd, 'second-opinion-packet-failure')
        raise
    finally:
        cd.evaluate('window.__oiPacketChecks?.restore()')
        credentials[0]['actions']=before;write_grants()
        navigate(cd, 'Overview')
