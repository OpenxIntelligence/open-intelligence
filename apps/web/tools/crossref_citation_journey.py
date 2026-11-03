"""Built React -> real H1 HTTP/PostgreSQL with a fictional provider transport.

Only external Crossref bytes are supplied by the explicit verification factory.
Patient/question permissions, stored metadata, citations and receipts are real.
One delivery is dropped after the real citation commits; no receipt is invented.
"""
import base64
import json
from pathlib import Path

from followthrough_journey import click, fill, capture_failure


DOI = '10.5555/oi-synthetic-001'
TITLE = 'Independently authored fictional bibliographic test entry'
_OBSERVE = r"""() => {
 const original=window.fetch;
 const state={lookups:[],writes:[],reads:[],dropNextWrite:false};
 state.restore=()=>{window.fetch=original;delete window.__oiCrossrefChecks;};
 window.fetch=async(input,init)=>{
  const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
  const method=(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase();
  const response=await original.call(window,input,init);
  if(!/\/questions\/QUESTION-[0-9A-F]{32}\/(?:evidence-doi|evidence-links)$/.test(path))return response;
  const payload=await response.clone().json();
  const item={path,status:response.status,payload};
  if(path.endsWith('/evidence-doi'))state.lookups.push({...item,body:JSON.parse(init.body)});
  else if(method==='POST'){
   state.writes.push({...item,body:JSON.parse(init.body),bodyText:init.body});
   if(state.dropNextWrite&&response.status===201){
    state.dropNextWrite=false;
    throw new TypeError('Lost delivery after the actual DOI citation committed');
   }
  }else state.reads.push(item);
  return response;
 };
 window.__oiCrossrefChecks=state;
 return true;
}"""


def exercise(cd, patient_id, case_id, question_id, credentials, write_grants,
             artifacts, report, restart_api):
    row = f'.question-items li[data-question-id="{question_id}"]'
    scope = f'/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}'
    previous_actions = list(credentials[0]['actions'])

    def control(name):
        return row + ' [data-testid=' + name + ']'

    def observed(name):
        return cd.evaluate('window.__oiCrossrefChecks.' + name)

    def history():
        count = len(observed('reads'))
        click(cd, control('metadata-evidence-open'))
        cd.wait('window.__oiCrossrefChecks.reads.length>' + str(count)
                + ' && Boolean(document.querySelector(' + json.dumps(control('evidence-saved-links')) + '))',
                'fresh DOI citation history from actual PostgreSQL')
        last = observed('reads')[-1]
        assert last['path'] == scope + '/evidence-links' and last['status'] == 200
        return last['payload']

    def lookup(*, allowed=True):
        count = len(observed('lookups'))
        click(cd, control('evidence-doi-lookup'))
        cd.wait('window.__oiCrossrefChecks.lookups.length>' + str(count), 'real DOI lookup HTTP response')
        last = observed('lookups')[-1]
        assert last['path'] == scope + '/evidence-doi'
        assert last['body'] == {'synthetic': True, 'public_doi_acknowledged': True, 'doi': DOI}
        if allowed:
            assert last['status'] == 200, last
            cd.wait('Boolean(document.querySelector(' + json.dumps(control('evidence-bibliography')) + '))',
                    'governed bibliography decoded and displayed')
        else:
            assert last['status'] in (403, 404)
            cd.wait('!document.querySelector(' + json.dumps(control('evidence-result')) + ')',
                    'lookup authority denial clears prior metadata search')
        return last

    assert cd.evaluate('(' + _OBSERVE + ')()')
    try:
        credentials[0]['actions'] = sorted(set(previous_actions) | {'evidence_lookup'})
        write_grants()
        before = history()
        assert len(before['links']) == 1
        assert before['links'][0]['citation'] == 'FICT-TRIAL-PREPARATION@1'
        fill(cd, control('evidence-doi-input'), 'This is not a publication DOI')
        assert cd.evaluate('document.querySelector(' + json.dumps(control('evidence-doi-lookup')) + ').disabled')
        fill(cd, control('evidence-doi-input'), DOI.upper())
        assert cd.evaluate('document.querySelector(' + json.dumps(control('evidence-doi-lookup')) + ').disabled')
        click(cd, control('evidence-doi-acknowledge'))
        first_lookup = lookup()
        payload = first_lookup['payload']
        assert (payload['patient_id'], payload['case_id'], payload['question_id']) == (patient_id, case_id, question_id)
        assert payload['model_executed'] is payload['content_appraised'] is payload['clinical_approval'] is False
        record, = payload['records']
        assert record['id'] == DOI and record['source_kind'] == 'crossref'
        assert record['citation'] == DOI + '@' + record['version']
        assert len(record['version']) == 64 and record['title'] == TITLE
        assert record['bibliography']['acquisition_mode'] == 'protocol_fixture'
        assert record['bibliography']['doi'] == DOI
        assert record['bibliography']['projection_sha256'] == record['version']
        assert record['bibliography']['journal'] == 'Fictional Examples Journal'
        assert record['bibliography']['year'] == 2026
        assert record['bibliography']['authors'] == ['Ari Example', 'Rin Invented']
        assert record['availability'] == 'metadata_only'
        encoded = json.dumps(payload)
        assert 'COPYRIGHTED ABSTRACT' not in encoded and 'example.net' not in encoded
        cd.evaluate('document.querySelector(' + json.dumps(control('evidence-result')) + ').open=true')
        assert cd.evaluate('document.querySelector(' + json.dumps(control('evidence-doi-link')) + ').getAttribute("href")') == record['link']
        assert 'protocol fixture' in cd.evaluate('document.querySelector(' + json.dumps(control('evidence-result')) + ').textContent').lower()
        assert cd.evaluate("document.querySelector('[data-testid=evidence-report-body]')?.textContent") == report['body']

        # Save explicitly through the existing canonical link owner. Dropping
        # delivery after commit must retain that exact DOI/version intent.
        cd.evaluate('window.__oiCrossrefChecks.dropNextWrite=true')
        click(cd, control('evidence-save'))
        cd.wait("window.__oiCrossrefChecks.writes.length===1 && Boolean(document.querySelector('[data-testid=evidence-recovery]'))",
                'unknown committed DOI citation retains exact recovery')
        first_write = observed('writes')[0]
        assert first_write['status'] == 201 and first_write['payload']['duplicate'] is False
        click(cd, '[data-testid=evidence-retry]')
        cd.wait("window.__oiCrossrefChecks.writes.length===2 && !document.querySelector('[data-testid=evidence-recovery]')",
                'same intent recovers the original DOI citation receipt')
        retry = observed('writes')[1]
        assert retry['status'] == 200 and retry['payload']['duplicate'] is True
        assert retry['bodyText'] == first_write['bodyText']
        assert retry['payload']['link_id'] == first_write['payload']['link_id']
        assert retry['body']['citation'] == record['citation']
        assert retry['body']['expected_metadata_sha256'] == record['metadata_sha256']
        assert retry['body']['expected_source_snapshot_sha256'] == report['snapshot']['question']['source_snapshot_sha256']
        assert retry['body']['expected_preflight_sha256'] == report['snapshot']['question']['preflight_sha256']
        linked = history()
        doi_link = next(item for item in linked['links'] if item['citation'] == record['citation'])
        assert len(linked['links']) == 2 and doi_link['record'] == record

        restart_api()
        restarted = history()
        assert restarted['links'] == linked['links']
        assert restarted['source_access_receipt_id'] != linked['source_access_receipt_id']

        # Looking up public metadata is a separate operation from reading an
        # already saved citation or an independently authorized authored report.
        credentials[0]['actions'].remove('evidence_lookup')
        write_grants()
        denied = lookup(allowed=False)
        assert history()['links'] == linked['links']
        credentials[0]['actions'] = sorted(set(previous_actions) | {'evidence_lookup'})
        write_grants()
        repeated = lookup()['payload']['records'][0]
        assert repeated == record, 'An identical projection changed the immutable metadata snapshot'
        assert cd.evaluate("document.querySelector('[data-testid=evidence-report-body]')?.textContent") == report['body']
        cd.evaluate('document.querySelector(' + json.dumps(control('evidence-result')) + ').open=true')
        out = Path(artifacts)
        for width, height, name in ((1440, 1100, 'desktop'), (390, 844, 'mobile')):
            cd.command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            cd.evaluate('document.querySelector(' + json.dumps(control('evidence-workspace')) + ').scrollIntoView({block:"start"})')
            cd.wait('window.innerWidth===' + str(width), 'DOI bibliography viewport')
            assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            image = cd.command('Page.captureScreenshot', {'format': 'png'})
            (out / ('h1-crossref-' + name + '.png')).write_bytes(base64.b64decode(image['data']))
        cd.command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        history()
        receipt = {
            'contract': 'oi.h1-crossref-citation-browser/1', 'acquisition_mode': 'protocol_fixture',
            'live_provider_verified': False, 'patient_id': patient_id, 'case_id': case_id,
            'question_id': question_id, 'citation': record['citation'],
            'metadata_sha256': record['metadata_sha256'], 'projection_sha256': record['version'],
            'first_retrieved_at': record['bibliography']['retrieved_at'],
            'link_receipt': first_write['payload'], 'exact_retry_receipt': retry['payload'],
            'report_id': report['report_id'], 'report_body_sha256': report['body_sha256'],
            'lookup_denial_status': denied['status'], 'api_restart_preserved_citation': True,
            'provider_restricted_fields_discarded': True, 'explicit_save_only': True,
            'synthetic': True, 'model_executed': False, 'clinical_approval': False,
        }
        (out / 'h1-crossref-citation-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print('PASS CROSSREF CITATION: explicit DOI protocol fixture -> actual H1 API/PostgreSQL -> '
              'governed native DOI snapshot -> explicit citation -> exact uncertain retry -> API restart; '
              'independent lookup denial, preserved authored report and mobile layout. '
              'No live provider verification, article content, model or clinical approval.')
    except Exception:
        capture_failure(cd, 'h1-crossref-failure')
        raise
    finally:
        cd.evaluate('window.__oiCrossrefChecks?.restore()')
        credentials[0]['actions'] = previous_actions
        write_grants()
