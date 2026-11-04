"""Built React -> actual API/PostgreSQL acceptance for fictional citation links.

Uses the canonical question created by the existing source-question journey.
Only delivery of actual responses is dropped or held; no response body, question,
patient, catalog hit, metadata right, or citation receipt is fabricated here.
"""
import base64
from contextlib import contextmanager
import hashlib
import json

from followthrough_journey import artifacts_directory, click, fill, navigate, select_case


RECORD_ID = 'FICT-RECORD-CONTINUITY'
VERSION = '1'
CITATION = RECORD_ID + '@' + VERSION
ACTIONS = {'evidence_read', 'evidence_link'}

_OBSERVE = r"""() => {
  if(window.__oiMetadataEvidenceChecks) throw Error('Evidence observer already installed');
  const actualFetch=window.fetch;
  const state={searches:[],reads:[],writes:[],dropNextWrite:false,
    holdNextSearch:false,held:false,released:0,release:null};
  state.restore=()=>{state.release?.();window.fetch=actualFetch;delete window.__oiMetadataEvidenceChecks;};
  window.fetch=async(input,init)=>{
    const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
    const watched=/\/questions\/QUESTION-[0-9A-F]{32}\/(?:evidence-search|evidence-links)$/.test(path);
    const method=(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase();
    const response=await actualFetch.call(window,input,init);
    if(!watched)return response;
    const payload=await response.clone().json();
    // Record fictional bodies and receipts only; never inspect request headers.
    const observed={path,status:response.status,payload};
    if(path.endsWith('/evidence-search')){
      state.searches.push({...observed,body:JSON.parse(init.body)});
      if(state.holdNextSearch&&response.status===200){
        state.holdNextSearch=false;state.held=true;
        await new Promise(resolve=>{state.release=resolve;});
        state.held=false;state.release=null;state.released++;
      }
    }else if(method==='POST'){
      state.writes.push({...observed,body:JSON.parse(init.body),bodyText:init.body});
      if(state.dropNextWrite&&response.status===201){
        state.dropNextWrite=false;
        throw new TypeError('Synthetic delivery loss after the actual citation committed');
      }
    }else if(method==='GET')state.reads.push(observed);
    return response;
  };
  window.__oiMetadataEvidenceChecks=state;
  return true;
}"""


def capture_failure(cd):
    """Keep bounded fixture diagnostics without credentials, headers or input values."""
    try:
        out = artifacts_directory()
        image = cd.command('Page.captureScreenshot', {'format': 'png'})
        (out / 'h1-question-evidence-failure.png').write_bytes(base64.b64decode(image['data']))
        info = cd.evaluate("({text:[...document.querySelectorAll('[data-testid=question-evidence-panel],"
                           "[data-testid=evidence-operation],[data-testid=evidence-recovery]')]"
                           ".map(e=>e.textContent).join(' ').slice(0,12000),"
                           "writes:window.__oiMetadataEvidenceChecks?.writes.map(x=>({path:x.path,status:x.status})),"
                           "reads:window.__oiMetadataEvidenceChecks?.reads.map(x=>({path:x.path,status:x.status})),"
                           "searches:window.__oiMetadataEvidenceChecks?.searches.map(x=>({path:x.path,status:x.status}))})")
        (out / 'h1-question-evidence-failure.json').write_text(
            json.dumps(info, indent=2) + '\n', encoding='utf-8')
    except Exception:
        print('Evidence failure capture unavailable; original failure retained.')


class QuestionEvidenceChecks:
    def __init__(self, cd, patient_id, case_id, question_id, source_id):
        self.cd, self.patient_id, self.case_id = cd, patient_id, case_id
        self.question_id, self.source_id = question_id, source_id
        self.record = self.first_write = self.recovered_write = self.original_link = None
        self.rights_revoked = False
        self.rights_decision_id = None

    def question(self, question_id=None):
        return '.question-items li[data-question-id="' + (question_id or self.question_id) + '"]'

    def control(self, testid):
        return self.question() + ' [data-testid=' + testid + ']'

    def assert_scope(self, payload):
        assert (payload['patient_id'], payload['case_id'], payload['question_id']) == (
            self.patient_id, self.case_id, self.question_id)
        assert payload['synthetic'] is True
        assert payload['model_executed'] is False
        assert payload['content_appraised'] is False
        assert payload['clinical_approval'] is False
        assert payload['source_access_receipt_id'].startswith('ACCESS-')

    def open_history(self, expected_status=None):
        count = self.cd.evaluate('window.__oiMetadataEvidenceChecks.reads.length')
        click(self.cd, self.control('metadata-evidence-open'))
        self.cd.wait('window.__oiMetadataEvidenceChecks.reads.length===' + str(count + 1)
                     + ' && Boolean(document.querySelector(' + json.dumps(self.control('evidence-saved-links')) + '))',
                     'fresh canonical citation history')
        observed = self.cd.evaluate('window.__oiMetadataEvidenceChecks.reads.at(-1)')
        assert observed['status'] == 200
        payload = observed['payload']
        self.assert_scope(payload)
        assert payload['contract'] == 'oi.pg-question-evidence-links/1'
        if expected_status is None:
            assert payload['links'] == []
        else:
            assert len(payload['links']) == 1
            assert payload['links'][0]['status'] == expected_status
            assert payload['links'][0]['citation'] == CITATION
        return payload

    def search(self, *, wait_for_delivery=True):
        count = self.cd.evaluate('window.__oiMetadataEvidenceChecks.searches.length')
        fill(self.cd, self.control('evidence-query'), 'continuity')
        click(self.cd, self.control('evidence-search'))
        condition = 'window.__oiMetadataEvidenceChecks.searches.length===' + str(count + 1)
        if wait_for_delivery:
            condition += ' && Boolean(document.querySelector(' + json.dumps(self.control('evidence-result')) + '))'
        self.cd.wait(condition, 'actual fictional catalog search')
        observed = self.cd.evaluate('window.__oiMetadataEvidenceChecks.searches.at(-1)')
        assert observed['status'] == 200
        assert observed['body'] == {'synthetic': True, 'query': 'continuity'}
        payload = observed['payload']
        self.assert_scope(payload)
        assert payload['contract'] == 'oi.pg-question-evidence-search/1'
        assert len(payload['records']) == 1
        record = payload['records'][0]
        assert (record['id'], record['version'], record['citation']) == (RECORD_ID, VERSION, CITATION)
        assert record['source_kind'] == 'fictional' and record['availability'] == 'metadata_only'
        assert record['rights_status'] == 'granted'
        assert record['link'] == 'https://example.invalid/fictional/' + RECORD_ID + '/' + VERSION
        assert len(record['metadata_sha256']) == 64
        if wait_for_delivery:
            self.cd.evaluate('document.querySelector(' + json.dumps(self.control('evidence-result')) + ').open=true')
            text = self.cd.evaluate('document.querySelector(' + json.dumps(self.control('evidence-result')) + ').textContent')
            assert all(record[field] in text for field in ('id', 'version', 'citation', 'licence', 'metadata_sha256'))
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.control('evidence-fixture-link'))
                                    + ').getAttribute("href")') == record['link']
        return payload

    def start(self):
        navigate(self.cd, 'Investigations')
        click(self.cd, '[data-testid=load-source-questions]')
        self.cd.wait('Boolean(document.querySelector(' + json.dumps(self.question()) + '))',
                     'existing canonical question for citation linking')
        self.open_history()
        found = self.search()
        assert found['source_context_state'] == 'current_unreviewed_question'
        self.record = found['records'][0]
        self.cd.evaluate('window.__oiMetadataEvidenceChecks.dropNextWrite=true')
        click(self.cd, self.control('evidence-save'))
        self.cd.wait("window.__oiMetadataEvidenceChecks.writes.length===1 && Boolean(document.querySelector('[data-testid=evidence-recovery]'))",
                     'lost committed citation response leaves explicit recovery')
        first = self.cd.evaluate('window.__oiMetadataEvidenceChecks.writes[0]')
        assert first['status'] == 201 and first['payload']['duplicate'] is False
        assert first['body']['synthetic'] is True and first['body']['citation'] == CITATION
        assert first['body']['expected_metadata_sha256'] == self.record['metadata_sha256']
        assert first['body']['source_snapshot_contract'] == 'oi.pg-source-world-model/1'
        recovery = self.cd.evaluate("document.querySelector('[data-testid=evidence-recovery]').textContent")
        assert CITATION in recovery and self.question_id in recovery and 'does not cancel or undo' in recovery
        assert self.cd.evaluate("!document.querySelector('[data-testid=evidence-link-receipt]')")
        assert self.cd.evaluate('document.querySelector(' + json.dumps(self.control('evidence-query')) + ').disabled')
        click(self.cd, '[data-testid=evidence-retry]')
        self.cd.wait("window.__oiMetadataEvidenceChecks.writes.length===2 && Boolean(document.querySelector('[data-testid=evidence-link-receipt]'))"
                     + ' && Boolean(document.querySelector(' + json.dumps(self.control('evidence-saved-link')) + '))',
                     'same citation receipt recovered and server history refreshed')
        recovered = self.cd.evaluate('window.__oiMetadataEvidenceChecks.writes[1]')
        assert recovered['status'] == 200
        assert recovered['path'] == first['path'] and recovered['bodyText'] == first['bodyText']
        assert recovered['payload'] == {**first['payload'], 'duplicate': True}
        self.first_write, self.recovered_write = first, recovered
        history = self.open_history('available')
        self.original_link = history['links'][0]
        assert self.original_link['link_id'] == first['payload']['link_id']
        assert self.original_link['metadata_sha256'] == self.record['metadata_sha256']
        assert self.original_link['record'] == self.record
        assert self.original_link['actor_label'] == 'ACTOR-0'
        assert self.cd.evaluate('document.querySelectorAll(' + json.dumps(self.control('evidence-saved-link')) + ').length') == 1

    def set_fixture_rights(self, revoked):
        # Operator-only original fixture port. There is no patient rights-grant API.
        from oi_api.config import Settings
        from oi_api.database import Database
        from oi_api.evidence_catalog import append_rights_decision
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        database = Database(Settings.from_env())
        try:
            with database.registry_connection() as connection:
                decision = append_rights_decision(
                    PostgresPatientRegistry(connection, lambda *args: False), RECORD_ID, VERSION,
                    permissions={'metadata': {'store': 'allowed', 'display': 'allowed'}},
                    revoked=revoked, superseded=False, recorded_by='FIXTURE-OPERATOR',
                    reason=('Revoke original fictional metadata for browser acceptance.' if revoked else
                            'Restore the original fictional fixture declaration after browser acceptance.'))
            self.rights_revoked = revoked
            return decision
        finally:
            database.close()

    def capture(self, screenshots):
        screenshots.mkdir(parents=True, exist_ok=True)
        for width, height, suffix in ((1440, 1100, 'desktop'), (390, 844, 'mobile')):
            self.cd.command('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            self.cd.wait('window.innerWidth===' + str(width), 'evidence viewport')
            assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            selector = self.control('question-evidence-panel')
            self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ").scrollIntoView({block:'start'})")
            clip = self.cd.evaluate('(()=>{const r=document.querySelector(' + json.dumps(selector)
                                    + ').getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1};})()')
            image = self.cd.command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True, 'clip': clip})
            (screenshots / ('h1-question-evidence-' + suffix + '.png')).write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})

    def assert_redacted(self):
        text = self.cd.evaluate('document.querySelector(' + json.dumps(self.control('question-evidence-panel')) + ').textContent')
        assert self.record['title'] not in text and self.record['licence'] not in text and self.record['link'] not in text
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.control('evidence-fixture-link')) + ')')
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.control('evidence-result')) + ')')

    def finish(self, credentials, write_grants, screenshots, *, current_question_id):
        navigate(self.cd, 'Investigations')
        select_case(self.cd, self.case_id)
        click(self.cd, '[data-testid=load-source-questions]')
        self.cd.wait('Boolean(document.querySelector(' + json.dumps(self.question()) + '))', 'original question remains in amendment history')
        stale = self.open_history('available')
        assert stale['source_context_state'] == 'source_reassessment_required'
        assert stale['links'][0] == self.original_link
        found = self.search()
        assert found['source_context_state'] == 'source_reassessment_required'
        assert self.cd.evaluate('document.querySelector(' + json.dumps(self.control('evidence-save')) + ').disabled')
        assert self.cd.evaluate('Boolean(document.querySelector(' + json.dumps(self.control('evidence-stale')) + '))')
        self.capture(screenshots)

        # Hold an actual permitted result, switch the selected canonical question,
        # then revoke fixture rights before the old result can reach React.
        self.cd.evaluate('window.__oiMetadataEvidenceChecks.holdNextSearch=true')
        self.search(wait_for_delivery=False)
        self.cd.wait('window.__oiMetadataEvidenceChecks.held', 'real allowed catalog response held before delivery')
        click(self.cd, self.question(current_question_id) + ' [data-testid=source-quote-packet-open]')
        self.cd.wait("document.querySelector('[data-testid=source-quote-packet]')?.textContent.includes("
                     + json.dumps(current_question_id) + ')', 'another existing question selected through its source reader')
        self.rights_decision_id = self.set_fixture_rights(True)
        restricted = self.open_history('rights_restricted')
        row = restricted['links'][0]
        assert row['record'] is None
        assert {key: value for key, value in row.items() if key not in ('record', 'status')} == {
            key: value for key, value in self.original_link.items() if key not in ('record', 'status')}
        self.assert_redacted()
        self.cd.evaluate('window.__oiMetadataEvidenceChecks.release()')
        self.cd.wait('window.__oiMetadataEvidenceChecks.released===1', 'earlier permitted search delivery released')
        self.cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
        self.assert_redacted()

        credentials[0]['actions'].remove('evidence_read')
        write_grants()
        count = self.cd.evaluate('window.__oiMetadataEvidenceChecks.reads.length')
        click(self.cd, self.control('metadata-evidence-open'))
        self.cd.wait('window.__oiMetadataEvidenceChecks.reads.length===' + str(count + 1)
                     + ' && document.querySelector(' + json.dumps(self.control('evidence-links-status'))
                     + ")?.textContent.includes('unavailable')", 'independent evidence-read denial clears the displayed history')
        denied = self.cd.evaluate('window.__oiMetadataEvidenceChecks.reads.at(-1)')
        assert denied['status'] in (403, 404)
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.control('evidence-saved-links')) + ')')
        self.assert_redacted()
        credentials[0]['actions'].append('evidence_read')
        write_grants()
        self.open_history('rights_restricted')
        assert self.cd.evaluate('window.__oiMetadataEvidenceChecks.writes.length===2'), 'Stale or restricted inspection cannot create another citation'
        receipt = {
            'contract': 'oi.synthetic-question-evidence-browser-receipt/1',
            'patient_id': self.patient_id, 'case_id': self.case_id,
            'question_id': self.question_id, 'source_id': self.source_id,
            'first_save_receipt': self.first_write['payload'],
            'recovered_save_receipt': self.recovered_write['payload'],
            'identical_retry_body_sha256': hashlib.sha256(self.first_write['bodyText'].encode()).hexdigest(),
            'source_snapshot_sha256': self.first_write['body']['expected_source_snapshot_sha256'],
            'preflight_sha256': self.first_write['body']['expected_preflight_sha256'],
            'after_amendment_state': stale['source_context_state'],
            'rights_decision_id': self.rights_decision_id,
            'restricted_link': row, 'read_denial_status': denied['status'],
            'delayed_authorized_search_discarded': True,
            'synthetic': True, 'model_executed': False, 'content_appraised': False, 'clinical_approval': False,
        }
        (screenshots / 'h1-question-evidence-receipts.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        navigate(self.cd, 'Journey')
        print('PASS QUESTION EVIDENCE: actual saved canonical question -> original fictional catalog -> exact citation link; '
              'lost committed response recovered with byte-identical request and one server link; source amendment retains '
              'original history and disables new saving; operator metadata-rights revocation redacts record/title/URL; '
              'delayed allowed search cannot restore them; independent read denial clears history; desktop/mobile capture. '
              'No content appraisal, model execution or clinical approval.')


@contextmanager
def exercise(cd, patient_id, case_id, question_id, source_id, credentials, write_grants):
    previous = list(credentials[0]['actions'])
    checks = None
    try:
        credentials[0]['actions'] = sorted(set(previous) | ACTIONS)
        write_grants()
        cd.evaluate('(' + _OBSERVE + ')()')
        checks = QuestionEvidenceChecks(cd, patient_id, case_id, question_id, source_id)
        checks.start()
        yield checks
    except Exception:
        capture_failure(cd)
        raise
    finally:
        try:
            cd.evaluate('window.__oiMetadataEvidenceChecks?.restore()')
        finally:
            try:
                if checks and checks.rights_revoked:
                    checks.set_fixture_rights(False)
            finally:
                credentials[0]['actions'] = previous
                write_grants()
