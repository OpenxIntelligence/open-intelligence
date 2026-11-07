"""Actual fictional JSON file -> existing PostgreSQL custody -> React Journey.

The operator grants scope; the UI cannot grant itself access. No external FHIR
service, patient data, terminology expansion or clinical interpretation is used.
"""
import base64
from datetime import datetime
import hashlib
import json
from urllib.request import Request, urlopen

CASE = 'CASE-WEB-LAB'
SUBJECT = 'FICT-WEB-LAB'


def fictional_bundle(*, amended=False):
    """Independently authored numeric, absent and coded fixtures."""
    # Source originals may mix exact fullUrl references with local resource IDs.
    subject = {'reference': 'urn:uuid:10000000-0000-4000-8000-000000000001'}
    specimen = {'reference': 'urn:uuid:10000000-0000-4000-8000-000000000002'}
    category = [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'laboratory'}]}]
    coding = lambda code: {'coding': [{'system': 'http://loinc.org', 'code': code}]}
    issued = '2026-04-05T12:00:00Z' if amended else '2026-04-04T12:00:00Z'
    effective = '2026-04-03T09:05:00-04:00'
    observations = []
    for suffix, code in [('ZERO', '777-3'), ('NUMBER', '718-7'), ('ABSENT', '6690-2'), ('CODED', '999990-1')]:
        row = {'resourceType': 'Observation', 'id': 'FICT-WEB-' + suffix,
               'status': 'final', 'category': category, 'code': coding(code),
               'subject': subject, 'specimen': specimen,
               'effectiveDateTime': effective, 'issued': issued}
        if suffix == 'CODED':
            row['valueCodeableConcept'] = {'coding': [{
                'system': 'urn:oi:synthetic:lab-results', 'version': 'fixture-v1',
                'code': 'DETECTED' if amended else 'NOT-DETECTED',
                'display': 'Detected' if amended else 'Not detected',
            }]}
        elif suffix == 'ABSENT':
            row['dataAbsentReason'] = {'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/data-absent-reason', 'code': 'not-performed'}]}
        else:
            row['valueQuantity'] = {'value': 1 if amended and suffix == 'ZERO' else 0 if suffix == 'ZERO' else -4.25,
                                    'system': 'http://unitsofmeasure.org', 'code': '10*9/L'}
        observations.append(row)
    resources = [
        {'resourceType': 'Patient', 'id': SUBJECT},
        {'resourceType': 'Specimen', 'id': 'FICT-WEB-SPEC', 'subject': subject,
         'type': {'text': 'Fictional sample <script>literal</script>'},
         'collection': {'collectedDateTime': effective}},
        *observations,
        {'resourceType': 'DiagnosticReport', 'id': 'FICT-WEB-REPORT',
         'status': 'final', 'category': [{'coding': [{
             'system': 'http://terminology.hl7.org/CodeSystem/v2-0074', 'code': 'HM'}]}],
         'code': coding('58410-2'),
         'subject': subject, 'specimen': [specimen],
         'result': [{'reference': 'Observation/' + row['id']} for row in observations],
         'effectiveDateTime': effective, 'issued': issued},
    ]
    return json.dumps({'resourceType': 'Bundle', 'type': 'collection',
                       'entry': [{'fullUrl': 'urn:uuid:10000000-0000-4000-8000-%012d' % index,
                                  'resource': row} for index, row in enumerate(resources, 1)]},
                      ensure_ascii=False, indent=2).encode('utf-8')


def independent_bundle():
    """Different report/specimen, deliberately reusing bundle-local Observation IDs."""
    bundle = json.loads(fictional_bundle())
    for entry in bundle['entry']:
        row = entry['resource']
        if row['resourceType'] == 'Specimen':
            row['id'] = 'FICT-WEB-SECOND-SPEC'
            row['type']['text'] = 'Fictional independent sample'
            row['collection']['collectedDateTime'] = '2026-04-06T09:05:00-04:00'
        if row['resourceType'] == 'DiagnosticReport':
            row['id'] = 'FICT-WEB-SECOND-REPORT'
        if row['resourceType'] in ('Observation', 'DiagnosticReport'):
            row['effectiveDateTime'] = '2026-04-06T09:05:00-04:00'
            row['issued'] = '2026-04-07T12:00:00Z'
        if row.get('id') == 'FICT-WEB-NUMBER':
            row['valueQuantity']['code'] = 'mg/L'
        if row.get('id') == 'FICT-WEB-CODED':
            row['valueCodeableConcept']['coding'][0]['version'] = 'fixture-v2'
    return json.dumps(bundle, ensure_ascii=False, indent=2).encode('utf-8')


def exercise(cd, patient_id, directory, token, credentials, write_grants, artifacts):
    grants = {'case_binding_create', 'case_binding_read', 'source_import', 'source_read', 'source_original_read', 'question_read', 'question_create', 'composer_context_read', 'evidence_read', 'evidence_link', 'review_packet_read', 'laboratory_snapshot_create', 'review_queue_read', 'review_return'}
    credentials[0]['actions'] = sorted(set(credentials[0]['actions']) | grants)
    write_grants()
    root = '/v1/patients/' + patient_id
    source_path = '/cases/' + CASE + '/sources'

    def operator(path, payload=None):
        request = Request('http://127.0.0.1:8000' + root + path,
                          data=None if payload is None else json.dumps(payload).encode(),
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    operator('/case-bindings', {'synthetic': True, 'case_id': CASE,
             'source_organization': 'FICT-LAB-ORG', 'source_system': 'FICT-LAB-SYSTEM',
             'source_subject_ref': SUBJECT, 'review_ref': 'FICT-LAB-REVIEW'})

    def navigate(name):
        cd.evaluate('[...document.querySelectorAll("nav button")].find(e=>e.textContent.startsWith(' + json.dumps(name) + ')).click()')

    def reopen_patient():
        navigate('Overview')
        cd.wait("Boolean(document.querySelector('#patient-id'))", 'patient can reopen after independent grant check')
        cd.evaluate("(() => {const e=document.querySelector('#patient-id');"
                    "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e," + json.dumps(patient_id) + ");"
                    "e.dispatchEvent(new Event('input',{bubbles:true}));})()")
        cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
        cd.wait("document.querySelector('[data-testid=patient-card]')?.textContent.includes(" + json.dumps(patient_id) + ")", 'patient reopened under fresh authority')

    def records():
        navigate('Records')
        cd.wait('Boolean(document.querySelector("[data-testid=load-cases]"))', 'laboratory Records workspace')
        cd.evaluate('document.querySelector("[data-testid=load-cases]").click()')
        cd.wait('[...document.querySelectorAll("[data-testid=case-row]")].some(e=>e.textContent.includes(' + json.dumps(CASE) + '))', 'laboratory mapping')
        cd.evaluate('[...document.querySelectorAll("[data-testid=case-row]")].find(e=>e.textContent.includes(' + json.dumps(CASE) + ')).querySelector("[data-testid=load-sources]").click()')
        cd.wait('document.querySelector("[data-testid=source-index]")?.textContent.includes(' + json.dumps(CASE) + ')', 'laboratory source index')
        cd.evaluate('document.querySelector("[data-testid=record-import-disclosure]").open=true')

    def select(raw, name):
        path = directory / name
        path.write_bytes(raw)
        cd.command('DOM.enable')
        document = cd.command('DOM.getDocument')
        node = cd.command('DOM.querySelector', {'nodeId': document['root']['nodeId'], 'selector': '[data-testid=laboratory-file]'})
        cd.command('DOM.setFileInputFiles', {'nodeId': node['nodeId'], 'files': [str(path)]})
        cd.wait('Boolean(document.querySelector("[data-testid=laboratory-local-original]"))', 'local laboratory original preview')
        assert cd.evaluate('document.querySelector("[data-testid=laboratory-local-original]").textContent') == raw.decode()
        assert cd.evaluate('document.querySelectorAll("[data-testid=laboratory-local-original] script").length===0')
        assert cd.evaluate('document.querySelector("[data-testid=laboratory-import]").disabled')

    def inspect(source_id, expected):
        cd.evaluate('[...document.querySelectorAll("[data-testid=source-version]")].find(e=>e.querySelector("[data-testid=source-verify] dl>div:first-child code").textContent===' + json.dumps(source_id) + ').querySelector("[data-testid=open-original]").click()')
        cd.wait('document.querySelector("[data-testid=server-original]")?.textContent===' + json.dumps(expected.decode()), 'authorized exact FHIR original')
        actual = cd.evaluate('document.querySelector("[data-testid=server-original]").textContent')
        assert actual == expected.decode()
        assert hashlib.sha256(actual.encode()).hexdigest() == hashlib.sha256(expected).hexdigest()

    raw = fictional_bundle()
    records()
    cd.evaluate('''(() => {
      window.__oiLabFetch=window.fetch;window.__oiLabWrites=[];window.__oiLabDrop=true;window.__oiLabRequests=0;window.__oiLabPrepareCodes=[];window.__oiLabQuestionPosts=[];window.__oiLabHistoryCodes=[];window.__oiLabCatalog=[];window.__oiLabReviewDrop=true;
      window.fetch=async(input,init)=>{
        window.__oiLabRequests++;
        const laboratory=String(input).endsWith('/laboratory/fhir-r4/sources')&&init?.method==='POST';
        if(laboratory)window.__oiLabWrites.push(JSON.parse(init.body));
        const response=await window.__oiLabFetch(input,init);
        const path=String(input);
        if(path.includes('/composer/laboratory-questions/')&&(path.endsWith('/evidence-links')||path.endsWith('/evidence-search')||path.includes('/source-citation-report'))){
          const item={path,method:init.method,body:init.body??null,status:response.status,result:await response.clone().json()};
          window.__oiLabCatalog.push(item);
          if(path.endsWith('/evidence-links')&&init.method==='POST'&&response.status===201){
            throw Error('Fictional lost laboratory citation acknowledgement');
          }
          if(path.endsWith('/review-returns')&&init.method==='POST'&&response.status===201&&window.__oiLabReviewDrop){
            window.__oiLabReviewDrop=false;
            throw Error('Fictional lost laboratory review return acknowledgement');
          }
        }
        if(String(input).endsWith('/composer/laboratory-questions')&&init?.method==='GET')window.__oiLabHistoryCodes.push(response.status);
        if(String(input).endsWith('/composer/laboratory-questions')&&init?.method==='POST'){
          window.__oiLabQuestionPosts.push({body:JSON.parse(init.body),status:response.status});
          if(window.__oiLabQuestionPosts.length===1&&response.status===201){
            await response.clone().json();throw Error('Fictional lost question save response');
          }
        }
        if(String(input).endsWith('/composer/laboratory-preflight'))window.__oiLabPrepareCodes.push(response.status);
        if(laboratory&&window.__oiLabDrop&&response.ok){window.__oiLabDrop=false;await response.clone().json();throw Error('Fictional lost laboratory response');}
        return response;
      };
    })()''')
    requests_before_selection = cd.evaluate('window.__oiLabRequests')
    select(raw, 'fictional-lab.json')
    assert operator(source_path)['sources'] == []
    assert cd.evaluate('window.__oiLabWrites.length') == 0

    # Native keyboard reading must expose the whole bounded preview, including
    # with enlarged text, before any confirmation or canonical import.
    viewport = cd.evaluate('({width:innerWidth,height:innerHeight})')
    observations = []
    def key(name, code):
        cd.command('Input.dispatchKeyEvent', {'type':'rawKeyDown','key':name,'code':name,'windowsVirtualKeyCode':code})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':name,'code':name,'windowsVirtualKeyCode':code})
    for width, height in ((390, 844), (320, 256)):
        cd.command('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate('''(() => {const p=document.querySelector('[data-testid=laboratory-local-original]');
          p.style.fontSize='32px';p.scrollTop=0;p.closest('details').querySelector('summary').focus();})()''')
        key('Tab', 9)
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        observation = cd.evaluate('''(() => {const p=document.querySelector('[data-testid=laboratory-local-original]');
          const r=p.getBoundingClientRect(),h=document.querySelector('.topbar');return {
          width:innerWidth,height:innerHeight,focused:document.activeElement===p,
          top:r.top,bottom:r.bottom,contextBottom:h.dataset.sticky==='false'?0:h.getBoundingClientRect().bottom,
          scrollY,headerSticky:h.dataset.sticky,headerHeight:h.getBoundingClientRect().height,
          scrollInset:getComputedStyle(document.documentElement).scrollPaddingTop,
          scrollHeight:p.scrollHeight,clientHeight:p.clientHeight,requests:window.__oiLabRequests,
          writes:window.__oiLabWrites.length,confirmed:document.querySelector('[data-testid=laboratory-confirm]').checked};})()''')
        observations.append(observation)
        (artifacts / 'laboratory-preview-keyboard.json').write_text(json.dumps(observations, indent=2))
        (artifacts / f'laboratory-preview-keyboard-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        assert observation['focused'], 'Native Tab must enter the laboratory original before report-version selection'
        assert observation['clientHeight'] > 0 and observation['scrollHeight'] > observation['clientHeight'], 'Enlarged JSON must exercise a bounded scrollable reader'
        assert observation['top'] >= observation['contextBottom'] and observation['bottom'] <= height, 'Entire laboratory reader must be visible below patient context'
        tree = cd.command('Accessibility.getFullAXTree')['nodes']
        assert any(node.get('role', {}).get('value') == 'region' and
                   node.get('name', {}).get('value') == 'Selected laboratory JSON, not imported' for node in tree), 'Keyboard reader needs an accessible name that distinguishes local inspection from import'
        key('PageDown', 34)
        cd.wait('document.querySelector("[data-testid=laboratory-local-original]").scrollTop>0', 'PageDown scrolls exact laboratory JSON')
        if width == 390:
            # Finish the native PageDown animation before recording the reading position.
            position = cd.evaluate('''new Promise(resolve => {
              const reader = document.activeElement;
              let previous = reader.scrollTop, stable = 0;
              function sample() {
                const current = reader.scrollTop;
                stable = current === previous ? stable + 1 : 0;
                previous = current;
                if (stable >= 4) resolve(current); else requestAnimationFrame(sample);
              }
              requestAnimationFrame(sample);
            })''')
            resize_observations = []
            for new_height in (256, height):
                cd.command('Emulation.setDeviceMetricsOverride', {
                    'width':width, 'height':new_height, 'deviceScaleFactor':1, 'mobile':False})
                cd.wait('innerHeight===' + str(new_height), 'viewport resized during reading')
                cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                reading = cd.evaluate('''(() => {
                  const reader = document.querySelector('[data-testid=laboratory-local-original]');
                  const header = document.querySelector('.topbar');
                  const bounds = reader.getBoundingClientRect();
                  return {width:innerWidth, height:innerHeight, focused:document.activeElement===reader,
                    top:bounds.top, bottom:bounds.bottom, position:reader.scrollTop,
                    contextBottom:header.dataset.sticky==='true' ? header.getBoundingClientRect().bottom : 0,
                    requests:window.__oiLabRequests, writes:window.__oiLabWrites.length,
                    confirmed:document.querySelector('[data-testid=laboratory-confirm]').checked};
                })()''')
                resize_observations.append(reading)
                (artifacts / 'laboratory-reading-resize.json').write_text(json.dumps(resize_observations, indent=2))
                assert reading['focused'] and abs(reading['position'] - position) <= 1, reading
                assert reading['top'] >= reading['contextBottom'] and reading['bottom'] <= new_height, (
                    'Resizing while reading must keep the focused preview fully visible', reading)
                assert reading['requests'] == requests_before_selection and reading['writes'] == 0, reading
                assert not reading['confirmed'], reading
            print('PASS READER RESIZE: a native PageDown survives shrinking and expanding the viewport with visible focus, preserved reading position and no inspection requests.')
        assert cd.evaluate('document.querySelector("[data-testid=laboratory-local-original]").textContent') == raw.decode()
        assert cd.evaluate('!document.querySelector("[data-testid=laboratory-confirm]").checked && document.querySelector("[data-testid=laboratory-import]").disabled'), 'Reading must not confirm or import'
        key('Tab', 9)
        assert cd.evaluate('document.activeElement===document.querySelector("[data-testid=laboratory-predecessor]")'), 'Tab must exit the reader to existing report-version selection'
        assert cd.evaluate('window.__oiLabRequests') == requests_before_selection, 'Local keyboard inspection must make no request'
        assert cd.evaluate('window.__oiLabWrites.length') == 0
    assert operator(source_path)['sources'] == [], 'Keyboard inspection must not create a source'
    cd.evaluate('document.querySelector("[data-testid=laboratory-local-original]").style.removeProperty("font-size")')
    cd.command('Emulation.setDeviceMetricsOverride', {**viewport,'deviceScaleFactor':1,'mobile':False})
    print('PASS LABORATORY PREVIEW KEYBOARD: native Tab/PageDown/Tab; named visible reader at 390px and 320x256; exact local JSON; unchecked confirmation; zero requests and no source writes.')
    cd.evaluate('document.querySelector("[data-testid=laboratory-confirm]").click();document.querySelector("[data-testid=laboratory-import]").click()')
    cd.wait('Boolean(document.querySelector("[data-testid=laboratory-retry]"))', 'unknown outcome exposes exact manual retry')
    first, = operator(source_path)['sources']
    assert first['sha256'] == hashlib.sha256(raw).hexdigest()
    assert cd.evaluate('window.__oiLabWrites.length') == 1
    navigate('Overview')
    cd.evaluate('document.querySelector("[data-testid=patient-card] button").click()')
    cd.wait('Boolean(document.querySelector("[data-testid=patient-card]"))', 'same patient access rechecked')
    records()
    cd.wait('Boolean(document.querySelector("[data-testid=laboratory-retry]"))', 'exact uncertain intent survives same-patient access recheck')
    assert cd.evaluate('window.__oiLabWrites.length') == 1
    cd.evaluate('document.querySelector("[data-testid=laboratory-retry]").click()')
    cd.wait('document.querySelector("[data-testid=laboratory-receipt]")?.textContent.includes(' + json.dumps(first['source_id']) + ')', 'same committed laboratory import recovered')
    writes = cd.evaluate('window.__oiLabWrites')
    assert len(writes) == 2 and writes[0] == writes[1]
    assert writes[0]['bundle_json'] == raw.decode()
    assert len(operator(source_path)['sources']) == 1
    inspect(first['source_id'], raw)

    def load_journey(result_count):
        navigate('Journey')
        has_case = '[...document.querySelectorAll(".world-cases li")].some(e=>e.textContent.includes(' + json.dumps(CASE) + '))'
        if not cd.evaluate(has_case):
            cd.evaluate('document.querySelector("[data-testid=world-load-cases]").click()')
            cd.wait(has_case, 'authorized laboratory case available')
        cd.evaluate('[...document.querySelectorAll(".world-cases li")].find(e=>e.textContent.includes(' + json.dumps(CASE) + ')).querySelector("[data-testid=world-load]").click()')
        cd.wait('document.querySelectorAll("[data-testid=world-laboratory-observation]").length===' + str(result_count), 'all expected typed source laboratory results')

    def journey(expected_value):
        load_journey(4)
        rendered = cd.evaluate('[...document.querySelectorAll("[data-testid=world-laboratory-observation]")].map(e=>({text:e.textContent,value:e.querySelector("[data-testid=world-laboratory-value]").textContent}))')
        assert any('777-3' in row['text'] and row['value'] == expected_value + ' 10*9/L (UCUM)' for row in rendered), rendered
        assert any('718-7' in row['text'] and row['value'] == '-4.25 10*9/L (UCUM)' for row in rendered), rendered
        assert any('6690-2' in row['text'] and row['value'] == 'Result absent · source reason: not-performed' for row in rendered), rendered
        coded, = [row for row in rendered if 'Observation/FICT-WEB-CODED' in row['text']]
        literal = 'DETECTED' if expected_value == '1' else 'NOT-DETECTED'
        label = 'Detected' if expected_value == '1' else 'Not detected'
        assert all(part in coded['text'] for part in (literal, label, 'urn:oi:synthetic:lab-results', 'fixture-v1'))
        assert 'Result absent' not in coded['value'] and '(UCUM)' not in coded['value']
        rows = [row['text'] for row in rendered]
        assert all('Specimen/FICT-WEB-SPEC' in row and 'DiagnosticReport/FICT-WEB-REPORT' in row for row in rows)
        assert cd.evaluate('document.querySelectorAll("[data-testid=world-laboratory-observation] script").length===0')
        return rows

    def choose_result(source_id, suffix):
        target = source_id + '|Observation/FICT-WEB-' + suffix
        cd.evaluate("(() => {const e=document.querySelector('[data-testid=lab-question-result]');"
                    "e.value=" + json.dumps(target) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        cd.wait("Boolean(document.querySelector('[data-testid=lab-question-text]'))", 'editable question for selected lab result')

    def filter_results(control_id, value):
        cd.evaluate("(() => {const e=document.getElementById(" + json.dumps(control_id) + ");"
                    "e.value=" + json.dumps(value) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")

    def question_text():
        return cd.evaluate("document.querySelector('[data-testid=lab-question-text]').value")

    def draft_question(source_id, suffix, question):
        before = cd.evaluate('window.__oiLabRequests')
        choose_result(source_id, suffix)
        cd.evaluate("(() => {const e=document.querySelector('[data-testid=lab-question-text]');"
                    "Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e," + json.dumps(question) + ");"
                    "e.dispatchEvent(new Event('input',{bubbles:true}));})()")
        cd.wait("document.querySelector('[data-testid=lab-question-prepare]')?.disabled===false", 'human question ready')
        assert cd.evaluate('window.__oiLabRequests') == before, 'Selection and editing must make no network request'

    def submit_question():
        cd.evaluate("document.querySelector('[data-testid=lab-question-prepare]').click()")

    overview_reads = []
    def inspect_overview_laboratory(current_count, reassessment_count):
        """Inspect the independently read lab history, then return without a write."""
        before = cd.evaluate('window.__oiLabQuestionPosts.length')
        navigate('Overview')
        cd.wait('Boolean(document.querySelector("[data-testid=continuity-lab-questions]"))',
                'Overview exposes the laboratory read separately')
        counts = cd.evaluate('''({
            current:document.querySelector('[data-testid=continuity-lab-current]')?.textContent??null,
            reassessment:document.querySelector('[data-testid=continuity-lab-reassessment]')?.textContent??null
        })''')
        expected = {'current':None if current_count is None else str(current_count),
                    'reassessment':None if reassessment_count is None else str(reassessment_count)}
        assert counts == expected, (counts, expected)
        overview_reads.append(counts)
        if current_count is None:
            assert 'not been checked' in cd.evaluate('document.querySelector("[data-testid=continuity-lab-questions]").textContent')
        else:
            assert cd.evaluate('document.querySelector("[data-testid=second-opinion-lab-questions]").textContent').startswith('Saved laboratory questions')
        cd.evaluate('document.querySelector("[data-testid=continuity-open-lab-questions]").click()')
        cd.wait('Boolean(document.querySelector("[data-testid=lab-questions-reopen]"))',
                'Overview returns to the same saved laboratory question workspace')
        assert cd.evaluate('window.__oiLabQuestionPosts.length') == before

    question = 'What does this report say about my fictional specimen?'
    questions_path = '/cases/' + CASE + '/questions'
    journey('0')
    navigate('Investigations')
    cd.evaluate('document.querySelector("[data-testid=load-source-questions]").click()')
    cd.wait('Boolean(document.querySelector("[data-testid=source-question-history]"))', 'authorized laboratory case question history')
    navigate('Overview')
    cd.wait('document.querySelector("[data-testid=continuity-current]")?.textContent==="0"', 'checked empty laboratory question history')
    assert cd.evaluate('Boolean(document.querySelector("[data-testid=continuity-preparation-item][data-kind=unresolved-statements]"))')
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=continuity-preparation-item][data-kind=prepare-a-question]"))')
    cd.evaluate('document.querySelector("[data-testid=continuity-preparation-item][data-kind=unresolved-statements] button").click()')
    cd.wait('document.querySelectorAll("[data-testid=world-laboratory-observation]").length===4', 'Overview returns to the four source-reported laboratory results')
    assert operator(questions_path)['questions'] == []
    source = first['source_id']
    alternate = 'Which measurement is associated with this second fictional result?'
    requests = cd.evaluate('window.__oiLabRequests')
    draft_question(source, 'ZERO', question)
    # Filtering the authorized timeline must never retarget or erase a separate question draft.
    filter_results('lab-filter-code', '6690-2')
    cd.wait("document.querySelectorAll('[data-testid=world-laboratory-observation]').length===1 && "
            "document.querySelector('[data-testid=world-laboratory-value]').textContent.includes('not-performed')",
            'exact test filter shows its reported absence')
    filter_results('lab-filter-status', 'reported_value')
    cd.wait("!document.querySelector('[data-testid=world-laboratory-observation]') && "
            "document.querySelector('[data-testid=world-laboratory-results]').textContent.includes('No results match')",
            'code and result state combine without fabricating a value')
    assert question_text() == question
    assert cd.evaluate("document.querySelector('[data-testid=lab-question-result]').value") == source + '|Observation/FICT-WEB-ZERO'
    cd.evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Clear laboratory filters').click()")
    cd.wait("document.querySelectorAll('[data-testid=world-laboratory-observation]').length===4",
            'clearing filters restores the original laboratory timeline')
    filter_results('lab-filter-status', 'reported_coded')
    cd.wait("document.querySelectorAll('[data-testid=world-laboratory-observation]').length===1 && "
            "document.querySelector('[data-testid=world-laboratory-observation]').textContent.includes('NOT-DETECTED')",
            'reported coded result stays distinct from a missing result')
    filter_results('lab-filter-status', '')
    assert cd.evaluate('window.__oiLabRequests') == requests, 'Result filters must stay local'
    choose_result(source, 'NUMBER')
    assert question_text() == '', 'Another result must start with its own wording'
    draft_question(source, 'NUMBER', alternate)
    choose_result(source, 'ZERO')
    assert question_text() == question, 'Switching laboratory results lost the first unsaved question'
    choose_result(source, 'NUMBER')
    assert question_text() == alternate, 'The second result must recover its own wording'
    assert cd.evaluate('window.__oiLabRequests') == requests, 'Switching between drafts must stay local'
    assert operator('/cases/' + CASE + '/composer/laboratory-questions')['questions'] == []
    filter_results('lab-filter-code', '718-7')
    journey('0')
    assert cd.evaluate("document.getElementById('lab-filter-code').value") == '', 'A fresh report read resets local filters'
    for suffix in ('ZERO', 'NUMBER'):
        choose_result(source, suffix)
        assert question_text() == '', 'A fresh authorized report view must start with empty drafts'
    draft_question(first['source_id'], 'CODED', question)
    # The subsequent real save and lost-response retry must use the resumed
    # wording and original Observation, even after visiting a different result.
    choose_result(source, 'NUMBER')
    choose_result(source, 'CODED')
    submit_question()
    cd.wait("window.__oiLabPrepareCodes.length===1", 'explicit preparation completed over HTTP')
    assert cd.evaluate("window.__oiLabPrepareCodes") == [200], 'Expected scoped laboratory HTTP success'
    cd.wait("Boolean(document.querySelector('[data-testid=lab-question-receipt]')) || !document.querySelector('[data-testid=world-projection]')", 'client accepted or rejected the prepared source')
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))"), cd.evaluate("document.querySelector('[data-testid=world-status]').textContent")
    prepared = cd.evaluate("document.querySelector('[data-testid=lab-question-receipt]').textContent")
    assert all(x in prepared for x in (question, first['source_id'], first['sha256'], 'Observation/FICT-WEB-CODED', 'ACCESS-'))
    laboratory_history = '/cases/' + CASE + '/composer/laboratory-questions'
    assert operator(laboratory_history)['questions'] == []
    cd.evaluate("document.querySelector('[data-testid=lab-question-save]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=lab-question-retry]'))", 'lost question response exposes exact retry')
    committed, = operator(laboratory_history)['questions']
    assert committed['question'] == question and committed['source_context_state'] == 'current_unreviewed_question'
    assert committed['source_id'] == first['source_id'] and committed['source_sha256'] == first['sha256']
    navigate('Overview')
    cd.evaluate('document.querySelector("[data-testid=patient-card] button").click()')
    cd.wait('Boolean(document.querySelector("[data-testid=patient-card]"))', 'same patient access rechecked before question retry')
    navigate('Journey')
    cd.evaluate('document.querySelector("[data-testid=world-load-cases]").click()')
    cd.wait('[...document.querySelectorAll(".world-cases li")].some(e=>e.textContent.includes(' + json.dumps(CASE) + '))', 'reopen authorized case for question retry')
    journey('0')
    cd.wait("Boolean(document.querySelector('[data-testid=lab-question-retry]'))", 'same patient retains exact question recovery')
    assert cd.evaluate('window.__oiLabQuestionPosts.length') == 1
    cd.evaluate("document.querySelector('[data-testid=lab-question-retry]').click()")
    cd.wait("window.__oiLabQuestionPosts.length===2 && document.querySelector('[data-testid=lab-question-save-status]')?.textContent.includes(" + json.dumps(committed['question_id']) + ")", 'client accepted the recovered question identity')
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-retry]'))")
    assert 'Original save receipt recovered' in cd.evaluate("document.querySelector('[data-testid=lab-question-save-status]').textContent")
    posts = cd.evaluate('window.__oiLabQuestionPosts')
    assert [p['status'] for p in posts] == [201, 200] and posts[0]['body'] == posts[1]['body']
    assert operator(laboratory_history)['questions'] == [committed]
    cd.evaluate("document.querySelector('[data-testid=lab-questions-reopen]').click()")
    cd.wait("document.querySelector('[data-testid=lab-saved-question]')?.textContent.includes(" + json.dumps(question) + ")", 'reopen saved laboratory question')
    inspect_overview_laboratory(1, 0)
    # Use the same seeded, original fictional catalog as the text workflow.
    # Inspect actual response bodies; only suppress delivery of its first write.
    from question_metadata_journey import CITATION, QuestionEvidenceChecks
    from followthrough_journey import click, fill
    question_id = committed['question_id']
    q_selector = '[data-testid=lab-saved-question][data-question-id="' + question_id + '"] '
    control = lambda name: q_selector + '[data-testid=' + name + ']'
    def exists(name):
        return 'Boolean(document.querySelector(' + json.dumps(control(name)) + '))'
    def visible_text(name):
        return cd.evaluate('document.querySelector(' + json.dumps(control(name)) + ').textContent')
    catalog_path = root + laboratory_history + '/' + question_id
    expected_anchor = {k:committed[k] for k in ('source_id','source_version','source_sha256','observation_reference','source_snapshot_sha256','preflight_sha256')}
    click(cd, control('metadata-evidence-open'))
    cd.wait(exists('evidence-saved-links'), 'original question has fresh catalog history')
    first_read = cd.evaluate('window.__oiLabCatalog.at(-1)')
    assert (first_read['method'],first_read['path'],first_read['result']['links']) == ('GET',catalog_path+'/evidence-links',[])
    assert first_read['result']['question_anchor'] == expected_anchor
    fill(cd, control('evidence-query'), 'continuity')
    click(cd, control('evidence-search'))
    cd.wait(exists('evidence-result'), 'permitted fictional laboratory catalog result found')
    searched = cd.evaluate('window.__oiLabCatalog.at(-1)')
    assert searched['path'] == catalog_path+'/evidence-search' and json.loads(searched['body']) == {'synthetic':True,'query':'continuity'}
    assert searched['result']['question_anchor'] == expected_anchor
    catalog_record, = searched['result']['records']
    assert catalog_record['citation'] == CITATION and catalog_record['title'] in visible_text('evidence-result')
    cd.evaluate('document.querySelector(' + json.dumps(control('evidence-result')) + ').open=true')
    click(cd, control('evidence-save'))
    cd.wait(exists('evidence-retry'), 'unknown citation outcome offers exact recovery')
    inspect_overview_laboratory(1, 0)
    cd.wait(exists('evidence-retry'), 'Overview return preserves the exact uncertain citation save')
    click(cd, control('evidence-retry'))
    cd.wait(exists('evidence-saved-link'), 'current citation reopened from PostgreSQL')
    writes = cd.evaluate("window.__oiLabCatalog.filter(r=>r.path.endsWith('/evidence-links')&&r.method==='POST')")
    assert len(writes)==2 and [r['status'] for r in writes]==[201,200]
    assert writes[0]['body']==writes[1]['body'] and writes[0]['path']==writes[1]['path']==catalog_path+'/evidence-links'
    assert writes[1]['result']=={**writes[0]['result'],'duplicate':True}
    saved_link=cd.evaluate('window.__oiLabCatalog.at(-1).result.links[0]')
    assert saved_link['link_id']==writes[0]['result']['link_id'] and saved_link['record']==catalog_record
    click(cd, control('lab-citation-report-open'))
    cd.wait(exists('lab-citation-report'), 'original laboratory question and permitted citation report opened')
    current_report = visible_text('lab-citation-report')
    assert all(part in current_report for part in ('NOT-DETECTED', 'Not detected', 'urn:oi:synthetic:lab-results', 'fixture-v1'))
    assert all(token in current_report for token in (committed['source_id'],committed['source_sha256'],committed['observation_reference'],catalog_record['title']))
    opened_digest = cd.evaluate('window.__oiLabCatalog.at(-1).result.report_sha256')
    click(cd, control('lab-snapshot-capture'))
    cd.wait("window.__oiLabCatalog.some(r=>r.method==='POST'&&r.path.endsWith('/snapshots')&&r.status===201)", 'snapshot captured on the server')
    captured = cd.evaluate("window.__oiLabCatalog.find(r=>r.method==='POST'&&r.path.endsWith('/snapshots')).result")
    snapshot_id = captured['snapshot_id']
    assert captured['captured_report_sha256'] == opened_digest
    cd.wait('document.querySelector('+json.dumps(control('lab-snapshot-status'))+').textContent.includes('+json.dumps(snapshot_id)+')',
            'capture receipt reopened by the browser')
    review_path = laboratory_history + '/' + question_id + '/source-citation-report/snapshots/' + snapshot_id + '/review-returns'
    saved_selector = control('lab-snapshot-row') + '[data-snapshot-id="' + snapshot_id + '"]'

    def reopen_inspection():
        click(cd, control('lab-snapshot-list'))
        cd.wait(exists('lab-snapshot-row'), 'saved laboratory inspection history')
        click(cd, saved_selector + ' [data-testid=lab-snapshot-reopen]')
        cd.wait('Boolean(document.querySelector('+json.dumps(control('lab-citation-report') + '[data-snapshot-id="' + snapshot_id + '"]')+'))',
                'saved inspection opened before independent verification')

    reopen_inspection()
    assert not cd.evaluate(exists('lab-review-return')), 'Returning an inspection requires an explicit current check'
    click(cd, control('lab-review-check'))
    cd.wait(exists('lab-review-reason'), 'fresh review history authorizes the reason form')
    checked_review = cd.evaluate("window.__oiLabCatalog.filter(r=>r.method==='GET'&&r.path.endsWith('/review-returns')).at(-1).result")
    assert checked_review['return_count'] == checked_review['prior_return_count'] == 0
    assert checked_review['review_state'] == 'awaiting_independent_verification'
    assert checked_review['captured_report_sha256'] == checked_review['current_report_sha256'] == opened_digest
    fill(cd, control('lab-review-reason'), 'Please independently verify this fictional result and the cited source context.')
    click(cd, control('lab-review-return'))
    cd.wait(exists('lab-review-retry'), 'lost review acknowledgement exposes exact retry')
    actual_review = operator(review_path)
    original_return, = actual_review['receipts']
    assert actual_review['review_state'] == 'returned_for_independent_verification'
    assert actual_review['current_return_receipt_id'] == original_return['receipt_id']
    assert original_return['captured_report_sha256'] == original_return['report_sha256'] == opened_digest
    assert original_return['action'] == 'returned' and original_return['clinical_approval'] is False
    click(cd, control('lab-review-retry'))
    cd.wait('document.querySelector('+json.dumps(control('lab-review-status'))+')?.textContent.includes('+json.dumps(original_return['receipt_id'])+')',
            'lost review receipt recovered by exact retry')
    review_writes = cd.evaluate("window.__oiLabCatalog.filter(r=>r.method==='POST'&&r.path.endsWith('/review-returns'))")
    assert [item['status'] for item in review_writes] == [201, 200]
    assert review_writes[0]['body'] == review_writes[1]['body']
    assert operator(review_path)['receipts'] == [original_return]
    draft_question(first['source_id'], 'ABSENT', 'Why was the selected result not performed?')
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))"), 'Editing clears previous receipt'
    assert operator(questions_path)['questions'] == []
    records()
    amended = fictional_bundle(amended=True)
    select(amended, 'fictional-lab-amended.json')
    # The replacement is explicit; file selection cannot pick a predecessor.
    cd.evaluate('''(() => {const e=document.querySelector('[data-testid=laboratory-predecessor]');
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,''' + json.dumps(first['source_id']) + ''');
      e.dispatchEvent(new Event('change',{bubbles:true}));})()''')
    cd.evaluate('document.querySelector("[data-testid=laboratory-confirm]").click();document.querySelector("[data-testid=laboratory-import]").click()')
    cd.wait('document.querySelectorAll("[data-testid=source-version]").length===2', 'explicit laboratory amendment history')
    versions = operator(source_path)['sources']
    current = next(row for row in versions if row['state'] == 'current')
    assert current['version'] == 2 and current['supersedes_id'] == first['source_id']
    assert current['sha256'] == hashlib.sha256(amended).hexdigest()
    inspect(first['source_id'], raw)
    inspect(current['source_id'], amended)
    rows = journey('1')
    assert all(current['source_id'] in row and first['source_id'] not in row for row in rows)
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))")
    reopened, = operator(laboratory_history)['questions']
    assert reopened == {**committed, 'source_context_state': 'source_reassessment_required'}
    inspect_overview_laboratory(None, None)
    cd.evaluate("document.querySelector('[data-testid=lab-questions-reopen]').click()")
    cd.wait("document.querySelector('[data-testid=lab-saved-question]')?.textContent.toLowerCase().includes('needs reassessment')", 'amendment flags the historical question')
    row = cd.evaluate("document.querySelector('[data-testid=lab-saved-question]').textContent")
    assert all(v in row for v in (question, first['source_id'], first['sha256'], 'Observation/FICT-WEB-CODED'))
    inspect_overview_laboratory(0, 1)
    click(cd, control('metadata-evidence-open'))
    cd.wait(exists('evidence-stale')+' && '+exists('evidence-saved-link'), 'historical question reopens its original citation')
    assert not cd.evaluate(exists('evidence-query')) and not cd.evaluate(exists('evidence-save'))
    historical_links=cd.evaluate('window.__oiLabCatalog.at(-1).result')
    assert historical_links['question_anchor']==expected_anchor and historical_links['source_context_state']=='source_reassessment_required'
    assert historical_links['links']==[saved_link]
    fixture_rights=QuestionEvidenceChecks(cd, patient_id, CASE, question_id, first['source_id'])
    try:
        fixture_rights.set_fixture_rights(True)
        click(cd, control('metadata-evidence-open'))
        cd.wait(exists('evidence-restricted'), 'withdrawn metadata is withheld for the same immutable citation')
        redacted=cd.evaluate('window.__oiLabCatalog.at(-1).result.links[0]')
        assert redacted=={**saved_link,'record':None,'status':'rights_restricted'}
        assert all(value not in visible_text('evidence-saved-link') for value in (catalog_record['title'],catalog_record['licence'],catalog_record['link']))
        click(cd, control('lab-citation-report-open'))
        cd.wait(exists('lab-citation-report'), 'report independently rechecks metadata rights after withdrawal')
        historical_report=visible_text('lab-citation-report')
        assert all(v in historical_report for v in (committed['source_id'],committed['source_sha256'],committed['observation_reference'],CITATION))
        assert all(part in historical_report for part in ('NOT-DETECTED', 'Not detected', 'urn:oi:synthetic:lab-results', 'fixture-v1'))
        assert 'Detected' not in historical_report
        assert all(v not in historical_report for v in (current['source_id'],catalog_record['title'],catalog_record['licence'],catalog_record['link']))
        reopen_inspection()
        reopened_report = visible_text('lab-citation-report')
        assert 'NOT-DETECTED' in reopened_report and catalog_record['title'] not in reopened_report
        reopened_snapshot = cd.evaluate("window.__oiLabCatalog.filter(r=>r.method==='GET'&&r.path.endsWith('/"+snapshot_id+"')).at(-1).result")
        assert reopened_snapshot['snapshot']['captured_report_sha256'] == opened_digest
        assert reopened_snapshot['inspection']['report_sha256'] != opened_digest
        assert reopened_snapshot['inspection']['citations']['links'][0]['record'] is None
        click(cd, control('lab-review-check'))
        cd.wait(exists('lab-review-reason'), 'amended inspection has fresh review and rights checks')
        changed_review = cd.evaluate("window.__oiLabCatalog.filter(r=>r.method==='GET'&&r.path.endsWith('/review-returns')).at(-1).result")
        assert changed_review['review_state'] == changed_review['source_context_state'] == 'source_reassessment_required'
        assert changed_review['return_count'] == 0 and changed_review['prior_return_count'] == 1
        assert changed_review['current_return_receipt_id'] is None
        assert changed_review['receipts'] == [original_return]
        assert changed_review['captured_report_sha256'] == opened_digest
        assert changed_review['current_report_sha256'] == reopened_snapshot['inspection']['report_sha256']
        assert original_return['receipt_id'] in visible_text('lab-review-history')
        assert catalog_record['title'] not in visible_text('lab-review-history')
        fill(cd, control('lab-review-reason'), 'Please recheck this preserved fictional inspection after the source and citation permissions changed.')
        click(cd, control('lab-review-return'))
        cd.wait("window.__oiLabCatalog.filter(r=>r.method==='POST'&&r.path.endsWith('/review-returns')).length===3",
                'reassessment return saved against the newly opened inspection')
        changed_receipt = cd.evaluate("window.__oiLabCatalog.filter(r=>r.method==='POST'&&r.path.endsWith('/review-returns')).at(-1).result")
        cd.wait('document.querySelector('+json.dumps(control('lab-review-status'))+')?.textContent.includes('+json.dumps(changed_receipt['receipt_id'])+')',
                'reassessment receipt accepted by the browser')
        reassessed = operator(review_path)
        assert reassessed['review_state'] == 'source_reassessment_required'
        assert reassessed['return_count'] == reassessed['prior_return_count'] == 1
        assert original_return in reassessed['receipts']
        current_return, = [row for row in reassessed['receipts'] if row['receipt_id'] == changed_receipt['receipt_id']]
        assert current_return['report_sha256'] == changed_review['current_report_sha256']
        assert current_return['captured_report_sha256'] == opened_digest
        assert current_return['clinical_approval'] is False and current_return['external_notification_sent'] is False
        (artifacts / 'laboratory-inspection-review-returns.json').write_text(json.dumps({
            'synthetic':True, 'question_id':question_id, 'snapshot_id':snapshot_id,
            'captured_report_sha256':opened_digest, 'current_report_sha256':changed_review['current_report_sha256'],
            'original_return_receipt_id':original_return['receipt_id'], 'reassessment_receipt_id':current_return['receipt_id'],
            'create_and_retry_statuses':[item['status'] for item in review_writes],
            'retry_bytes_identical':True, 'prior_receipt_preserved':True,
            'review_state_after_return':reassessed['review_state'], 'clinical_approval':False,
        },indent=2)+'\n')
        (artifacts / 'laboratory-question-citations.json').write_text(json.dumps({
            'synthetic':True,'question_id':question_id,'question_anchor':expected_anchor,'catalog_query':'continuity',
            'citation':CITATION,'link_id':saved_link['link_id'],'metadata_sha256':saved_link['metadata_sha256'],
            'create_and_retry_statuses':[x['status'] for x in writes],'retry_bytes_identical':True,
            'amended_question_state':historical_links['source_context_state'],'withdrawn_metadata_state':redacted['status'],
            'captured_snapshot_id':snapshot_id,'captured_report_sha256':opened_digest,
            'reopened_report_sha256':reopened_snapshot['inspection']['report_sha256'],
            'report_original_observation_preserved':True,'report_withdrawn_metadata_withheld':True,
        },indent=2)+'\n')
    finally:
        if fixture_rights.rights_revoked:
            fixture_rights.set_fixture_rights(False)
    print('PASS LABORATORY CITATIONS: exact Observation search, one durable link, lost response recovery, original anchor after amendment, withdrawn metadata withheld from history and report.')
    print('PASS LABORATORY REVIEW: saved inspection explicitly reopened and checked, lost return acknowledgement recovered exactly, amendment and withdrawn rights preserved prior history, reassessment retained after another return.')
    credentials[0]['actions'].remove('question_read');write_grants()
    cd.evaluate("document.querySelector('[data-testid=lab-questions-reopen]').click()")
    cd.wait("window.__oiLabHistoryCodes.at(-1)===404 && Boolean(document.querySelector('[data-testid=world-no-patient]')) && !document.querySelector('[data-testid=lab-saved-question]')", 'denied question read removes prior history')
    navigate('Overview')
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=continuity-lab-current]"))')
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=second-opinion-lab-questions]"))')
    assert question not in cd.evaluate('document.body.innerText')
    (artifacts / 'laboratory-workflow-convergence.json').write_text(json.dumps({
        'synthetic':True, 'patient_id':patient_id, 'case_id':CASE,
        'question_id':question_id, 'original_source_id':first['source_id'],
        'original_sha256':first['sha256'], 'observation_reference':committed['observation_reference'],
        'overview_reads':overview_reads, 'navigation_created_no_question':True,
        'overview_return_preserved_uncertain_citation':True, 'citation_link_id':saved_link['link_id'],
        'citation_retry_statuses':[x['status'] for x in writes], 'revoked_overview_withheld':True,
        'clinical_approval':False, 'model_executed':False,
    },indent=2)+'\n')
    print('PASS LABORATORY CONVERGENCE: independently checked Overview counts, same-question return, uncertain citation recovery, amended history and revoked overview withholding.')
    credentials[0]['actions'].append('question_read');write_grants()
    reopen_patient()
    journey('1')
    draft_question(current['source_id'], 'ABSENT', question)
    submit_question()
    cd.wait("document.querySelector('[data-testid=lab-question-receipt]')?.textContent.includes('Observation/FICT-WEB-ABSENT')", 'absent result prepared on amended report')
    amended_receipt = cd.evaluate("document.querySelector('[data-testid=lab-question-receipt]').textContent")
    assert current['sha256'] in amended_receipt and first['source_id'] not in amended_receipt
    requests = cd.evaluate('window.__oiLabRequests')
    choose_result(current['source_id'], 'NUMBER')
    choose_result(current['source_id'], 'ABSENT')
    assert question_text() == question
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-save]'))"), 'Returning to a draft must require fresh preparation'
    assert cd.evaluate('window.__oiLabRequests') == requests
    print('PASS LABORATORY QUESTION DRAFTS: switching restores wording only for its exact result, refresh clears drafts, and returning to prepared wording requires a fresh check.')
    credentials[0]['actions'].remove('composer_context_read');write_grants()
    submit_question()
    cd.wait("window.__oiLabPrepareCodes.at(-1)===404 && Boolean(document.querySelector('[data-testid=world-no-patient]'))", 'Composer denial withholds projection and prepared answer')
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))")
    assert operator(questions_path)['questions'] == []
    credentials[0]['actions'].append('composer_context_read');write_grants()
    reopen_patient()
    (artifacts / 'laboratory-question-preparation.json').write_text(json.dumps({
        'synthetic': True, 'case_id': CASE, 'original': prepared, 'amendment': amended_receipt,
        'http_statuses': cd.evaluate('window.__oiLabPrepareCodes'),
        'requests_on_selection_or_edit': 0, 'saved_questions_before_explicit_save': 0,
        'edited_receipt_cleared': True, 'denied_projection_withheld': True,
    }, indent=2) + '\n')
    assert cd.evaluate('window.__oiLabPrepareCodes') == [200, 200, 404]
    (artifacts / 'durable-laboratory-question.json').write_text(json.dumps({
        'synthetic': True, 'case_id': CASE, 'question_id': committed['question_id'],
        'original_source_id': first['source_id'], 'original_sha256': first['sha256'],
        'current_source_id': current['source_id'], 'observation_reference': committed['observation_reference'],
        'save_statuses': [p['status'] for p in posts], 'same_retry_body': posts[0]['body']==posts[1]['body'], 'rechecked_patient_before_retry': True,
        'historical_state': reopened['source_context_state'], 'revoked_history_withheld': True,
        'observed_history_statuses': cd.evaluate('window.__oiLabHistoryCodes'),
    }, indent=2) + '\n')
    print('PASS DURABLE LAB QUESTION: explicit save, lost response recovered, same stored ID and original after amendment, denied history cleared.')
    print('PASS LAB QUESTION: exact current and amended results, explicit human question, zero implicit requests or saves, Composer revocation withheld the preview.')
    journey('1')
    # The integrated Journey action must re-read this case's source metadata
    # without automatically disclosing an original or creating a new source.
    writes_before_navigation = cd.evaluate('window.__oiLabWrites.length')
    cd.evaluate('document.querySelector("[data-testid=world-laboratory-observation] details").open=true;document.querySelector("[data-testid=world-laboratory-records]").click()')
    cd.wait('document.querySelector("[data-testid=source-index]")?.textContent.includes(' + json.dumps(current['source_id']) + ')', 'Journey opens the exact laboratory case source history')
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=server-original]"))')
    assert cd.evaluate('window.__oiLabWrites.length') == writes_before_navigation
    inspect(current['source_id'], amended)
    journey('1')
    cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate('document.querySelector("[data-testid=world-laboratory-observation]").scrollIntoView({block:"start"})')
    assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    (artifacts / 'h1-laboratory-mobile.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))

    records()
    inspect(current['source_id'], amended)
    credentials[0]['actions'].remove('source_original_read');write_grants()
    cd.evaluate('[...document.querySelectorAll("[data-testid=source-version]")].find(e=>e.querySelector("[data-testid=source-verify] dl>div:first-child code").textContent===' + json.dumps(current['source_id']) + ').querySelector("[data-testid=open-original]").click()')
    cd.wait('!document.querySelector("[data-testid=server-original]") && document.querySelector("[data-testid=records-status]").textContent.includes("permission denied")', 'revoked laboratory original withheld')
    credentials[0]['actions'].append('source_original_read');write_grants()
    # Continue the same saved-inspection workflow with another independent report.
    # Reused local Observation IDs must not join specimens or replace the old source.
    records()
    other_raw = independent_bundle()
    select(other_raw, 'fictional-lab-independent.json')
    assert cd.evaluate('document.querySelector("[data-testid=laboratory-predecessor]").value') == ''
    cd.evaluate('document.querySelector("[data-testid=laboratory-confirm]").click();document.querySelector("[data-testid=laboratory-import]").click()')
    cd.wait('document.querySelectorAll("[data-testid=source-version]").length===3', 'second report retained beside amendment history')
    versions = operator(source_path)['sources']
    other, = [row for row in versions if row['document_id'] == 'FICT-WEB-SECOND-REPORT']
    assert other['version'] == 1 and other['supersedes_id'] is None
    assert other['sha256'] == hashlib.sha256(other_raw).hexdigest()
    assert len([row for row in versions if row['state'] == 'current']) == 2
    load_journey(8)
    before_read = cd.evaluate('window.__oiLabRequests')
    writes_before = cd.evaluate('window.__oiLabWrites.length')
    summary = '[data-testid=laboratory-same-test] > summary'
    cd.evaluate('document.querySelector('+json.dumps(summary)+').focus()')
    key('Enter', 13)
    cd.wait('document.querySelector("[data-testid=laboratory-same-test]").open', 'keyboard opens grouped current reports')
    assert cd.evaluate('window.__oiLabRequests') == before_read
    groups = cd.evaluate('''[...document.querySelectorAll('[data-testid=laboratory-same-test] > section')].map(section=>({
      heading:section.querySelector('h5').textContent,
      rows:[...section.querySelectorAll('[data-testid=laboratory-same-test-row]')].map(row=>({
        text:row.textContent,value:row.querySelector('[data-testid=laboratory-same-test-value]').textContent,
        times:[...row.querySelectorAll('time')].map(time=>time.dateTime)}))
    }))''')
    assert len(groups) == 4 and all(len(g['rows']) == 2 for g in groups), groups
    for group in groups:
        # Preserve the existing source timeline's ascending effective-time order.
        earlier, later = group['rows']
        assert all(part in later['text'] for part in (other['source_id'], other['sha256'], 'FICT-WEB-SECOND-SPEC'))
        # PostgreSQL retains the instant, not the original offset spelling.
        assert len(later['times']) == 3
        assert all(datetime.fromisoformat(value) == datetime.fromisoformat('2026-04-06T09:05:00-04:00')
                   for value in later['times'][:2])
        assert all(part in earlier['text'] for part in (current['source_id'], current['sha256'], 'FICT-WEB-SPEC'))
        assert all(first['source_id'] not in row['text'] for row in group['rows'])
    number = next(g for g in groups if g['heading'].startswith('LOINC 718-7 '))
    assert [r['value'] for r in number['rows']] == ['-4.25 10*9/L (source UCUM)', '-4.25 mg/L (source UCUM)']
    coded = next(g for g in groups if g['heading'].startswith('LOINC 999990-1 '))
    assert [r['value'] for r in coded['rows']] == ['Coded result: DETECTED · Source label: Detected', 'Coded result: NOT-DETECTED · Source label: Not detected']
    assert 'fixture-v1' in coded['rows'][0]['text'] and 'fixture-v2' in coded['rows'][1]['text']
    assert all('urn:oi:synthetic:lab-results' in row['text'] for row in coded['rows'])
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=laboratory-same-test] script"))')
    filter_results('lab-filter-status', 'reported_coded')
    cd.wait('document.querySelectorAll("[data-testid=world-laboratory-observation]").length===2', 'ordinary result filter remains independent')
    assert cd.evaluate('document.querySelectorAll("[data-testid=laboratory-same-test-row]").length') == 8
    assert cd.evaluate('window.__oiLabRequests') == before_read
    assert cd.evaluate('window.__oiLabWrites.length') == writes_before
    assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    (artifacts / 'h1-laboratory-same-test-mobile.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
    cd.evaluate('document.querySelector("[data-testid=laboratory-same-test-records]").click()')
    cd.wait('document.querySelector("[data-testid=source-index]")?.textContent.includes('+json.dumps(other['source_id'])+')', 'comparison opens current case source history')
    inspect(first['source_id'], raw)
    inspect(other['source_id'], other_raw)
    # An independent report cannot move the original saved question or inspection.
    retained = operator(review_path.removesuffix('/review-returns'))
    assert retained['snapshot']['captured_report_sha256'] == opened_digest
    assert retained['inspection']['reported_result']['source_id'] == first['source_id']
    assert retained['inspection']['reported_result']['coded_result']['code'] == 'NOT-DETECTED'
    (artifacts / 'laboratory-same-test-connected.json').write_text(json.dumps({
        'synthetic':True, 'case_id':CASE, 'groups':groups,
        'source_ids':[current['source_id'],other['source_id']], 'historical_source_excluded':first['source_id'],
        'snapshot_id':snapshot_id, 'snapshot_source_preserved':True,
        'keyboard_open':True, 'group_and_filter_requests':0, 'new_writes_from_grouping':0,
        'originals_verified':True, 'clinical_comparability_asserted':False,
    },indent=2)+'\n')
    print('PASS CONNECTED LABORATORY COMPARISON: two current reports retain literal quantities, different units, codes, specimen times and source-local identities; keyboard grouping/filtering performs no requests; exact originals and historical saved inspection remain intact.')
    load_journey(8)
    credentials[0]['actions'].remove('source_read');write_grants()
    cd.evaluate('[...document.querySelectorAll(".world-cases li")].find(e=>e.textContent.includes(' + json.dumps(CASE) + ')).querySelector("[data-testid=world-load]").click()')
    cd.wait('!document.querySelector("[data-testid=world-projection]") && document.querySelector("[data-testid=world-status]").textContent.includes("unavailable or revoked")', 'revoked laboratory projection cleared')
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=laboratory-same-test]"))')
    credentials[0]['actions'].append('source_read');write_grants()
    cd.evaluate('window.fetch=window.__oiLabFetch;delete window.__oiLabFetch;delete window.__oiLabWrites;delete window.__oiLabDrop;delete window.__oiLabRequests;delete window.__oiLabPrepareCodes;delete window.__oiLabQuestionPosts;delete window.__oiLabHistoryCodes;delete window.__oiLabCatalog;delete window.__oiLabReviewDrop')
    navigate('Overview')
    (artifacts / 'laboratory-fhir-workflow.json').write_text(json.dumps({
        'synthetic': True, 'case_id': CASE, 'original_source_id': first['source_id'],
        'amended_source_id': current['source_id'], 'original_sha256': first['sha256'],
        'amended_sha256': current['sha256'], 'observation_count': 4,
        'selection_writes': 0, 'lost_response_retry_same_intent': True,
        'preserved_original_and_history': True, 'original_denial': True,
        'projection_denial': True, 'journey_to_records_fresh_metadata_only': True,
        'laboratory_only_overview_inspection': True,
        'clinical_interpretation': False}, indent=2) + '\n')
    print('PASS LABORATORY: actual fictional file selection; zero implicit writes; exact lost-response retry; typed zero/number/absence/coded value; explicit amendment; exact current/historical JSON; original and projection revocation; 390px layout.')
