"""Actual fictional JSON file -> existing PostgreSQL custody -> React Journey.

The operator grants scope; the UI cannot grant itself access. No external FHIR
service, patient data, terminology expansion or clinical interpretation is used.
"""
import base64
import hashlib
import json
from urllib.request import Request, urlopen

CASE = 'CASE-WEB-LAB'
SUBJECT = 'FICT-WEB-LAB'


def fictional_bundle(*, amended=False, patient_resource_id=SUBJECT):
    """Independently authored numeric-zero, negative-number and absent fixtures."""
    # Source originals may mix exact fullUrl references with local resource IDs.
    subject = {'reference': 'urn:uuid:10000000-0000-4000-8000-000000000001'}
    specimen = {'reference': 'urn:uuid:10000000-0000-4000-8000-000000000002'}
    category = [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'laboratory'}]}]
    coding = lambda code: {'coding': [{'system': 'http://loinc.org', 'code': code}]}
    issued = '2026-04-05T12:00:00Z' if amended else '2026-04-04T12:00:00Z'
    effective = '2026-04-03T09:05:00-04:00'
    observations = []
    for suffix, code in [('ZERO', '777-3'), ('NUMBER', '718-7'), ('ABSENT', '6690-2')]:
        row = {'resourceType': 'Observation', 'id': 'FICT-WEB-' + suffix,
               'status': 'final', 'category': category, 'code': coding(code),
               'subject': subject, 'specimen': specimen,
               'effectiveDateTime': effective, 'issued': issued}
        if suffix == 'ABSENT':
            row['dataAbsentReason'] = {'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/data-absent-reason', 'code': 'not-performed'}]}
        else:
            row['valueQuantity'] = {'value': 1 if amended and suffix == 'ZERO' else 0 if suffix == 'ZERO' else -4.25,
                                    'system': 'http://unitsofmeasure.org', 'code': '10*9/L'}
        observations.append(row)
    resources = [
        {'resourceType': 'Patient', 'id': patient_resource_id},
        {'resourceType': 'Specimen', 'id': 'FICT-WEB-SPEC', 'subject': subject,
         'type': {'text': 'Fictional sample <script>literal</script>'},
         'collection': {'collectedDateTime': effective}},
        *observations,
        {'resourceType': 'DiagnosticReport', 'id': 'FICT-WEB-REPORT',
         'status': 'final', 'category': category, 'code': coding('58410-2'),
         'subject': subject, 'specimen': [specimen],
         'result': [{'reference': 'Observation/' + row['id']} for row in observations],
         'effectiveDateTime': effective, 'issued': issued},
    ]
    return json.dumps({'resourceType': 'Bundle', 'type': 'collection',
                       'entry': [{'fullUrl': 'urn:uuid:10000000-0000-4000-8000-%012d' % index,
                                  'resource': row} for index, row in enumerate(resources, 1)]},
                      ensure_ascii=False, indent=2).encode('utf-8')


def exercise(cd, patient_id, directory, token, credentials, write_grants, artifacts):
    grants = {'case_binding_create', 'case_binding_read', 'source_import', 'source_read', 'source_original_read', 'question_read', 'question_create', 'composer_context_read', 'evidence_read', 'evidence_link', 'review_packet_read',
              'followthrough_create', 'followthrough_read', 'followthrough_update'}
    credentials[0]['actions'] = sorted(set(credentials[0]['actions']) | grants)
    write_grants()
    root = '/v1/patients/' + patient_id
    source_path = '/cases/' + CASE + '/sources'

    def operator(path, payload=None, *, accept='application/json'):
        request = Request('http://127.0.0.1:8000' + root + path,
                          data=None if payload is None else json.dumps(payload).encode(),
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': accept})
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
      window.__oiPrepTaskReads=[];window.__oiLabReports=[];window.__oiLabMutations=0;window.__oiLabFetch=window.fetch;window.__oiLabWrites=[];window.__oiLabDrop=true;window.__oiLabRequests=0;window.__oiLabPrepareCodes=[];window.__oiLabQuestionPosts=[];window.__oiLabHistoryCodes=[];window.__oiLabCatalog=[];
      window.fetch=async(input,init)=>{
        window.__oiLabRequests++;
        const method=init?.method??input?.method??'GET';
        if(['POST','PUT','PATCH','DELETE'].includes(method))window.__oiLabMutations++;
        if(window.__oiLabPreviewOffline && String(input).endsWith('/laboratory/fhir-r4/preview')){
          window.__oiLabPreviewOffline=false;
          return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});
        }
        const laboratory=String(input).endsWith('/laboratory/fhir-r4/sources')&&init?.method==='POST';
        if(laboratory)window.__oiLabWrites.push(JSON.parse(init.body));
        const response=await window.__oiLabFetch(input,init);
        const path=String(input);
        if(method==='GET' && path.endsWith('/followthrough')){
          window.__oiPrepTaskReads.push({path,status:response.status,accept:new Headers(init.headers).get('Accept')});
        }
        if(path.endsWith('/source-citation-report'))window.__oiLabReports.push({path,method,status:response.status});
        if(init.method==='POST' && path.endsWith('/followthrough') && response.status===201){
          window.__oiLabTaskReceipt=await response.clone().json();
        }
        if(path.includes('/composer/laboratory-questions/')&&(path.endsWith('/evidence-links')||path.endsWith('/evidence-search'))){
          const item={path,method:init.method,body:init.body??null,status:response.status,result:await response.clone().json()};
          window.__oiLabCatalog.push(item);
          if(path.endsWith('/evidence-links')&&init.method==='POST'&&response.status===201){
            throw Error('Fictional lost laboratory citation acknowledgement');
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
    preview_button = 'document.querySelector("[data-testid=laboratory-preview]")'
    preview_results = 'document.querySelector("[data-testid=laboratory-preview-results]")'
    cd.evaluate('window.__oiLabPreviewOffline=true')
    cd.evaluate(preview_button + '.click()')
    cd.wait('document.querySelector("[data-testid=laboratory-intake]").textContent.includes("Preview unavailable.")',
            'a temporary preview outage is visible')
    cd.evaluate('document.querySelector("[data-testid=laboratory-confirm]").click()')
    assert cd.evaluate('!document.querySelector("[data-testid=laboratory-import]").disabled'), 'direct import remains available'
    assert cd.evaluate('window.__oiLabWrites.length') == 0
    cd.evaluate(preview_button + '.click()')
    cd.wait('Boolean(' + preview_results + ')', 'server preview shows the selected specimen and results')
    rendered = cd.evaluate(preview_results + '.textContent')
    assert all(item in rendered for item in (
        'Specimen/FICT-WEB-SPEC', 'DiagnosticReport/FICT-WEB-REPORT',
        '0 10*9/L (UCUM)', '-4.25 10*9/L (UCUM)', 'Result absent · source reason: not-performed',
    )), rendered
    assert cd.evaluate(preview_results + '.querySelectorAll("script").length') == 0
    assert cd.evaluate('document.querySelector("[data-testid=laboratory-import]").disabled')
    assert operator(source_path)['sources'] == []
    wrong_subject = fictional_bundle(patient_resource_id='FICT-OTHER')
    select(wrong_subject, 'fictional-unmatched-lab.json')
    assert cd.evaluate(preview_results + '===null')
    cd.evaluate(preview_button + '.click()')
    cd.wait('document.querySelector("[data-testid=laboratory-intake]").textContent.includes("does not match the supported laboratory format or the case mapping")',
            'unmatched subject rejected on preview')
    assert cd.evaluate(preview_results + '===null')
    assert cd.evaluate('document.querySelector("[data-testid=laboratory-confirm]").disabled')
    assert operator(source_path)['sources'] == [] and cd.evaluate('window.__oiLabWrites.length') == 0
    select(raw, 'fictional-lab.json')
    print('PASS STRUCTURED LAB PREVIEW: authorized values and specimen, unmatched case refused, zero original writes before confirmation.')
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

    def journey(expected_value, section='Journey'):
        navigate(section)
        has_case = '[...document.querySelectorAll(".world-cases li")].some(e=>e.textContent.includes(' + json.dumps(CASE) + '))'
        if not cd.evaluate(has_case):
            cd.evaluate('document.querySelector("[data-testid=world-load-cases]").click()')
            cd.wait(has_case, 'authorized laboratory case available')
        cd.evaluate('[...document.querySelectorAll(".world-cases li")].find(e=>e.textContent.includes(' + json.dumps(CASE) + ')).querySelector("[data-testid=world-load]").click()')
        cd.wait('document.querySelectorAll("[data-testid=world-laboratory-observation]").length===3', 'three typed source laboratory results')
        rendered = cd.evaluate('[...document.querySelectorAll("[data-testid=world-laboratory-observation]")].map(e=>({text:e.textContent,value:e.querySelector("[data-testid=world-laboratory-value]").textContent}))')
        assert any('777-3' in row['text'] and row['value'] == expected_value + ' 10*9/L (UCUM)' for row in rendered), rendered
        assert any('718-7' in row['text'] and row['value'] == '-4.25 10*9/L (UCUM)' for row in rendered), rendered
        assert any('6690-2' in row['text'] and row['value'] == 'Result absent · source reason: not-performed' for row in rendered), rendered
        rows = [row['text'] for row in rendered]
        assert all('Specimen/FICT-WEB-SPEC' in row and 'DiagnosticReport/FICT-WEB-REPORT' in row for row in rows)
        assert cd.evaluate('document.querySelectorAll("[data-testid=world-laboratory-observation] script").length===0')
        return rows

    def choose_result(source_id, suffix):
        target = source_id + '|Observation/FICT-WEB-' + suffix
        cd.evaluate("(() => {const e=document.querySelector('[data-testid=lab-question-result]');"
                    "e.value=" + json.dumps(target) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        cd.wait("Boolean(document.querySelector('[data-testid=lab-question-text]'))", 'editable question for selected lab result')

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
    journey('0', 'Labs')
    cd.wait("document.querySelector('h1').textContent==='Labs' && Boolean(document.querySelector('[data-testid=labs-results]'))", 'first-class Labs workspace')
    cd.evaluate("const statusFilter=document.querySelector('#lab-filter-status');statusFilter.value='reported_absent';statusFilter.dispatchEvent(new Event('change',{bubbles:true}))")
    cd.wait("document.querySelectorAll('[data-testid=world-laboratory-observation]').length===1 && document.querySelector('[data-testid=world-laboratory-value]').textContent.includes('not-performed')", 'an absent result remains distinct in Labs')
    cd.evaluate("document.querySelector('#lab-filter-status').scrollIntoView({block:'center'})")
    (artifacts/'labs-workspace.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
    navigate('Investigations')
    cd.evaluate('document.querySelector("[data-testid=load-source-questions]").click()')
    cd.wait('Boolean(document.querySelector("[data-testid=source-question-history]"))', 'authorized laboratory case question history')
    navigate('Overview')
    cd.wait('document.querySelector("[data-testid=continuity-current]")?.textContent==="0"', 'checked empty laboratory question history')
    assert cd.evaluate('Boolean(document.querySelector("[data-testid=continuity-preparation-item][data-kind=unresolved-statements]"))')
    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=continuity-preparation-item][data-kind=prepare-a-question]"))')
    cd.evaluate('document.querySelector("[data-testid=continuity-preparation-item][data-kind=unresolved-statements] button").click()')
    cd.wait('document.querySelectorAll("[data-testid=world-laboratory-observation]").length===3', 'Overview returns to the three source-reported laboratory results')
    assert operator(questions_path)['questions'] == []
    source = first['source_id']
    alternate = 'Which measurement is associated with this second fictional result?'
    requests = cd.evaluate('window.__oiLabRequests')
    draft_question(source, 'ZERO', question)
    choose_result(source, 'NUMBER')
    assert question_text() == '', 'Another result must start with its own wording'
    draft_question(source, 'NUMBER', alternate)
    choose_result(source, 'ZERO')
    assert question_text() == question, 'Switching laboratory results lost the first unsaved question'
    choose_result(source, 'NUMBER')
    assert question_text() == alternate, 'The second result must recover its own wording'
    assert cd.evaluate('window.__oiLabRequests') == requests, 'Switching between drafts must stay local'
    assert operator('/cases/' + CASE + '/composer/laboratory-questions')['questions'] == []
    journey('0')
    for suffix in ('ZERO', 'NUMBER'):
        choose_result(source, suffix)
        assert question_text() == '', 'A fresh authorized report view must start with empty drafts'
    draft_question(first['source_id'], 'ZERO', question)
    # The subsequent real save and lost-response retry must use the resumed
    # wording and original Observation, even after visiting a different result.
    choose_result(source, 'NUMBER')
    choose_result(source, 'ZERO')
    submit_question()
    cd.wait("window.__oiLabPrepareCodes.length===1", 'explicit preparation completed over HTTP')
    assert cd.evaluate("window.__oiLabPrepareCodes") == [200], 'Expected scoped laboratory HTTP success'
    cd.wait("Boolean(document.querySelector('[data-testid=lab-question-receipt]')) || !document.querySelector('[data-testid=world-projection]')", 'client accepted or rejected the prepared source')
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))"), cd.evaluate("document.querySelector('[data-testid=world-status]').textContent")
    prepared = cd.evaluate("document.querySelector('[data-testid=lab-question-receipt]').textContent")
    assert all(x in prepared for x in (question, first['source_id'], first['sha256'], 'Observation/FICT-WEB-ZERO', 'ACCESS-'))
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
    assert all(token in current_report for token in (committed['source_id'],committed['source_sha256'],committed['observation_reference'],catalog_record['title']))
    draft_question(first['source_id'], 'ABSENT', 'Why was the selected result not performed?')
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))"), 'Editing clears previous receipt'
    assert operator(questions_path)['questions'] == []
    # A saved question about an Observation can own actual coordination work.
    # Keep the source lines empty for laboratory tasks; the Observation is the locator.
    task_title = 'Request the original laboratory report for the next visit'
    click(cd, control('followthrough-open-create'))
    fill(cd, control('followthrough-title'), task_title)
    fill(cd, control('followthrough-detail'), 'Bring the original laboratory report to the second opinion.')
    fill(cd, control('followthrough-due-date'), '2026-11-12')
    fill(cd, control('followthrough-trigger'), 'When the laboratory issues a correction')
    fill(cd, control('followthrough-reason'), 'Prepare the saved specimen question for discussion.')
    click(cd, control('followthrough-create'))
    cd.wait('Boolean(window.__oiLabTaskReceipt)', 'laboratory task committed through the patient workspace')
    task_receipt = cd.evaluate('window.__oiLabTaskReceipt')
    assert task_receipt['question_id'] == question_id and task_receipt['revision'] == 1
    task_id = task_receipt['task_id']
    task_card = '[data-testid=followthrough-task][data-task-id="' + task_id + '"]'
    task_dom = 'document.querySelector(' + json.dumps(task_card) + ')'
    task_list_path = '/cases/' + CASE + '/followthrough'
    task_media = 'application/vnd.open-intelligence.followthrough.v2+json'

    def open_recorded_task():
        navigate('Investigations')
        click(cd, '[data-testid=followthrough-refresh]')
        cd.wait(task_dom + '?.textContent.includes(' + json.dumps(task_title) + ')',
                'exact laboratory work item reopened from the case list')

    def task_at_revision(revision):
        cd.wait(task_dom + '?.dataset.revision===' + json.dumps(str(revision)),
                'rendered laboratory follow-up revision ' + str(revision))
        packet = operator(task_list_path, accept=task_media)
        assert packet['contract'] == 'oi.pg-question-followthrough/2'
        task, = packet['tasks']
        assert task['task_id'] == task_id and task['question_id'] == question_id
        assert task['source_line'] is None and task['revision'] == revision
        assert all(task[key] == value for key, value in expected_anchor.items())
        return task

    open_recorded_task()
    picker = '[data-testid=preparation-lab-select]'
    preparation_row_selector = '[data-testid=preparation-lab-question]'
    work_panel = '[data-testid=preparation-lab-followup]'
    task_summary = '[data-testid=preparation-lab-task]'
    recheck = '[data-testid=preparation-lab-task-recheck]'

    def choose_preparation_question(target):
        cd.wait('[...document.querySelectorAll('+json.dumps(picker+' option')+')].some(e=>e.value==='+json.dumps(target)+')',
                'saved question available under current laboratory history')
        requests = cd.evaluate('window.__oiLabRequests')
        cd.evaluate("(()=>{const e=document.querySelector("+json.dumps(picker)+");e.value="+json.dumps(target)+
                    ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        cd.wait('document.querySelector('+json.dumps(preparation_row_selector)+')?.dataset.questionId==='+json.dumps(target),
                'selected laboratory question identified by its saved ID')
        assert cd.evaluate('window.__oiLabRequests') == requests

    def check_preparation_tasks(status):
        start = cd.evaluate('window.__oiPrepTaskReads.length')
        click(cd, '[data-testid=preparation-lab-followup-refresh]')
        cd.wait('window.__oiPrepTaskReads.length>'+str(start),'independent follow-up access check')
        call, = cd.evaluate('window.__oiPrepTaskReads.slice('+str(start)+')')
        assert call['path'] == root+task_list_path and call['status'] == status and task_media in call['accept']

    def inspect_recorded_task(expected_recheck):
        cd.wait('document.querySelector('+json.dumps(task_summary)+')?.dataset.taskId==='+json.dumps(task_id),
                'next action belongs to the selected laboratory question')
        contents = cd.evaluate('document.querySelector('+json.dumps(task_summary)+').textContent')
        assert all(text in contents for text in (task_title,'Fictional coordinator','acknowledged',
                   '2026-11-12','When the laboratory issues a correction','Bring the original laboratory report'))
        assert cd.evaluate('Boolean(document.querySelector('+json.dumps(recheck)+'))') == expected_recheck

    def enter_preparation_task(status=200):
        reads = cd.evaluate('window.__oiPrepTaskReads.length')
        mutations = cd.evaluate('window.__oiLabMutations')
        click(cd, '[data-testid=preparation-lab-open-task]')
        cd.wait('window.__oiPrepTaskReads.length>'+str(reads), 'task handoff requests fresh permission')
        calls = cd.evaluate('window.__oiPrepTaskReads.slice('+str(reads)+')')
        assert len(calls) == 1 and calls[0]['status'] == status and task_media in calls[0]['accept']
        cd.wait("Boolean(document.querySelector('[data-testid=followthrough-entry]'))",
                'selected result opens the canonical follow-up workspace')
        if status == 200:
            cd.wait(task_dom + ' && document.activeElement.id===' + json.dumps('followthrough-task-'+task_id),
                    'keyboard focus reaches the freshly authorized exact task')
            assert cd.evaluate("document.querySelectorAll('[data-testid=followthrough-task]').length") == 1
            assert committed['observation_reference'] in cd.evaluate(task_dom + '.textContent')
        else:
            cd.wait("document.querySelector('[data-testid=followthrough-status]')?.dataset.phase==='error'",
                    'task handoff denial completes')
            assert not cd.evaluate("Boolean(document.querySelector('[data-testid=followthrough-task]'))")
            assert task_title not in cd.evaluate("document.querySelector('[data-testid=followthrough-panel]').textContent")
        assert cd.evaluate('window.__oiLabMutations') == mutations

    def return_to_preparation():
        navigate('Overview')
        choose_preparation_question(question_id)
        check_preparation_tasks(200)

    before = task_at_revision(1)
    assert before['status'] == 'created' and not before['needs_recheck']
    assert committed['observation_reference'] in cd.evaluate(task_dom + '.textContent')
    assert operator(task_list_path)['tasks'] == [], 'legacy text-only list preserves its contract'
    navigate('Overview')
    click(cd, '[data-testid=preparation-lab-refresh]')
    choose_preparation_question(question_id)
    check_preparation_tasks(200)
    enter_preparation_task()
    for action, revision in [('assign', 2), ('acknowledge', 3)]:
        if action == 'assign':
            fill(cd, task_card + ' [data-testid=followthrough-transition-owner]', 'Fictional coordinator')
        fill(cd, task_card + ' [data-testid=followthrough-transition-reason]', 'Record this coordination step.')
        click(cd, task_card + ' [data-testid=followthrough-' + action + ']')
        task_at_revision(revision)
    navigate('Overview')
    current_writes = cd.evaluate('window.__oiLabMutations')
    click(cd, '[data-testid=preparation-lab-refresh]')
    choose_preparation_question(question_id)
    check_preparation_tasks(200)
    inspect_recorded_task(False)
    assert cd.evaluate('window.__oiLabMutations') == current_writes
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
    assert all(v in row for v in (question, first['source_id'], first['sha256'], 'Observation/FICT-WEB-ZERO'))
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
        assert all(v not in historical_report for v in (current['source_id'],catalog_record['title'],catalog_record['licence'],catalog_record['link']))
        (artifacts / 'laboratory-question-citations.json').write_text(json.dumps({
            'synthetic':True,'question_id':question_id,'question_anchor':expected_anchor,'catalog_query':'continuity',
            'citation':CITATION,'link_id':saved_link['link_id'],'metadata_sha256':saved_link['metadata_sha256'],
            'create_and_retry_statuses':[x['status'] for x in writes],'retry_bytes_identical':True,
            'amended_question_state':historical_links['source_context_state'],'withdrawn_metadata_state':redacted['status'],
            'report_original_observation_preserved':True,'report_withdrawn_metadata_withheld':True,
        },indent=2)+'\n')
        # Use the same wording on a different Observation in the amended report.
        # Selecting a question in preparation must use its identity, not its text.
        case_path = '/cases/' + CASE
        context = operator(case_path + '/world-model')
        second = dict(synthetic=True, source_id=current['source_id'],
                      observation_reference='Observation/FICT-WEB-ABSENT', question=question,
                      expected_source_snapshot_sha256=context['snapshot_fingerprint'])
        checked = operator(case_path + '/composer/laboratory-preflight', second)
        second_receipt = operator(laboratory_history, {**second, 'request_key':'PREPARATION-ABSENT',
                                  'expected_preflight_sha256':checked['preflight_sha256']})
        second_id = second_receipt['question_id']
        assert second_id != question_id
        journey('1')
        navigate('Overview')
        cd.wait("Boolean(document.querySelector('[data-testid=preparation-lab-refresh]'))",
                'preparation can request laboratory history for the current case')
        assert not cd.evaluate("Boolean(document.querySelector('[data-testid=preparation-lab-select]'))")
        prior_history_reads = cd.evaluate('window.__oiLabHistoryCodes.length')
        inspection_writes_before = cd.evaluate('window.__oiLabMutations')
        click(cd, '[data-testid=preparation-lab-refresh]')
        cd.wait('window.__oiLabHistoryCodes.length>'+str(prior_history_reads),
                'fresh laboratory history request from preparation')
        assert cd.evaluate('window.__oiLabHistoryCodes.slice('+str(prior_history_reads)+')') == [200]
        action = preparation_row_selector + ' [data-testid=lab-citation-report-open]'
        report = preparation_row_selector + ' [data-testid=lab-citation-report]'
        cd.wait("document.querySelectorAll('[data-testid=preparation-lab-select] option').length===3",
                'both authorized questions offered for preparation')
        assert not cd.evaluate('Boolean(document.querySelector('+json.dumps(report)+'))')
        for target,source,reference,value in (
                (second_id,current,second['observation_reference'],'No value reported.'),
                (question_id,first,committed['observation_reference'],'0 10*9/L')):
            read_count = cd.evaluate('window.__oiLabReports.length')
            choose_preparation_question(target)
            assert not cd.evaluate('Boolean(document.querySelector('+json.dumps(report)+'))')
            check_preparation_tasks(200)
            if target == question_id:
                inspect_recorded_task(True)
            else:
                cd.wait("Boolean(document.querySelector('[data-testid=preparation-lab-no-open-work]'))",
                        'authorized task check returned empty for the other question')
                assert task_title not in cd.evaluate('document.querySelector('+json.dumps(work_panel)+').textContent')
            click(cd,action)
            cd.wait('Boolean(document.querySelector('+json.dumps(report)+'))','fresh protected preparation report')
            calls = cd.evaluate('window.__oiLabReports.slice('+str(read_count)+')')
            assert calls == [dict(path=root+laboratory_history+'/'+target+'/source-citation-report',method='GET',status=200)]
            contents = cd.evaluate('document.querySelector('+json.dumps(report)+').textContent')
            assert all(token in contents for token in (question,target,reference,source['sha256'],value))
            if target == question_id:
                assert 'Needs reassessment' in contents and CITATION in contents
                assert catalog_record['title'] not in contents and 'not-performed' not in contents
            else:
                assert 'not-performed' in contents and CITATION not in contents and first['sha256'] not in contents
        enter_preparation_task()
        assert cd.evaluate(task_dom + '?.dataset.revision') == '3'
        assert 'Source context changed' in cd.evaluate(task_dom + '.textContent')
        fill(cd, task_card + ' [data-testid=followthrough-transition-reason]', 'Review the original before changing this task.')
        assert cd.evaluate(task_dom + '.querySelector("[data-testid=followthrough-complete]").matches(":disabled")')
        return_to_preparation()
        enter_preparation_task()
        assert cd.evaluate(task_dom + '.querySelector("[data-testid=followthrough-transition-reason]").value') == 'Review the original before changing this task.'
        return_to_preparation()
        click(cd, action)
        cd.wait('Boolean(document.querySelector('+json.dumps(report)+'))', 'permitted report reopens after task navigation')
        cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate('document.querySelector('+json.dumps(report)+').scrollIntoView({block:"center"})')
        assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        (artifacts/'second-opinion-laboratory-result.png').write_bytes(base64.b64decode(
            cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        cd.evaluate('document.querySelector('+json.dumps(work_panel)+').scrollIntoView({block:"center"})')
        (artifacts/'laboratory-result-followup-mobile.png').write_bytes(base64.b64decode(
            cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        credentials[0]['actions'].remove('followthrough_read');write_grants()
        try:
            check_preparation_tasks(404)
            cd.wait("Boolean(document.querySelector('[data-testid=preparation-lab-followup-unavailable]'))",
                    'task access withdrawal clears the recorded assignment')
            assert not cd.evaluate('Boolean(document.querySelector('+json.dumps(task_summary)+'))')
            assert not cd.evaluate("Boolean(document.querySelector('[data-testid=preparation-lab-no-open-work]'))")
            assert task_title not in cd.evaluate('document.querySelector('+json.dumps(work_panel)+').textContent')
            assert first['sha256'] in cd.evaluate('document.querySelector('+json.dumps(report)+').textContent')
        finally:
            credentials[0]['actions'].append('followthrough_read');write_grants()
        check_preparation_tasks(200)
        inspect_recorded_task(True)
        credentials[0]['actions'].remove('followthrough_read');write_grants()
        try:
            enter_preparation_task(404)
        finally:
            credentials[0]['actions'].append('followthrough_read');write_grants()
        return_to_preparation()
        enter_preparation_task()
        click(cd, '[data-testid=followthrough-entry-clear]')
        cd.wait("!document.querySelector('[data-testid=followthrough-entry]') && Boolean(document.querySelector('[data-testid=followthrough-filter-all]'))",
                'explicitly return to all authorized follow-up work')
        return_to_preparation()
        click(cd, action)
        cd.wait('Boolean(document.querySelector('+json.dumps(report)+'))', 'report stays independently available after restored task handoff')
        confirmed = operator(task_list_path,accept=task_media)['tasks']
        assert len(confirmed) == 1 and confirmed[0]['task_id'] == task_id and confirmed[0]['revision'] == 3
        inspection_writes = cd.evaluate('window.__oiLabMutations') - inspection_writes_before
        assert inspection_writes == 0
        (artifacts/'preparation-laboratory-followup.json').write_text(json.dumps({
            'synthetic':True,'selected_question':question_id,'other_question':second_id,'task':task_id,
            'owner':confirmed[0]['owner_label'],'status':confirmed[0]['status'],'revision':confirmed[0]['revision'],
            'due_date':confirmed[0]['due_date'],'review_trigger':confirmed[0]['review_trigger'],
            'recheck_after_amendment':confirmed[0]['needs_recheck'],'other_result_empty':True,
            'task_denial_withheld_owner':True,'permitted_report_survived_task_denial':True,
            'inspection_mutation_requests':inspection_writes,'task_access_http':[200,404,200],
            'direct_task_handoff':True,'fresh_handoff_access_http':[200,404,200],
            'exact_task_focused':True,'canonical_status_controls_used':True,
            'unsent_reason_retained_on_matching_task':True,'amended_completion_disabled':True,
        },indent=2)+'\n')
        credentials[0]['actions'].remove('review_packet_read');write_grants()
        try:
            click(cd,action)
            cd.wait("window.__oiLabReports.at(-1)?.status===404 && !document.querySelector('[data-testid=preparation-lab-select]')",
                    'withdrawing report access removes the report and saved laboratory questions')
            assert question not in cd.evaluate('document.body.innerText')
            assert cd.evaluate('window.__oiLabMutations') == inspection_writes_before
        finally:
            credentials[0]['actions'].append('review_packet_read');write_grants()
        (artifacts/'second-opinion-laboratory-results.json').write_text(json.dumps({
            'synthetic': True, 'historical_question': question_id, 'current_question': second_id,
            'same_question_wording': True, 'history_read_from_preparation': True,
            'historical_zero_and_current_absence_distinct': True,
            'restricted_title_withheld': True, 'report_refresh_denial': 404, 'inspection_writes': 0,
        }, indent=2)+'\n')
        reopen_patient()
        journey('1')
        click(cd, '[data-testid=lab-questions-reopen]')
        cd.wait("document.querySelectorAll('[data-testid=lab-saved-question]').length===2",
                'questions reopened after explicit reauthorization')
    finally:
        if fixture_rights.rights_revoked:
            fixture_rights.set_fixture_rights(False)
    print('PASS LABORATORY CITATIONS: exact Observation search, one durable link, lost response recovery, original anchor after amendment, withdrawn metadata withheld from history and report.')
    assert cd.evaluate('document.querySelector(' + json.dumps(control('followthrough-open-create')) + ').disabled')
    open_recorded_task()
    after = task_at_revision(3)
    assert after['needs_recheck'] and after['source_context_state'] == 'source_reassessment_required'
    assert [event['status'] for event in after['history']] == ['created', 'assigned', 'acknowledged']
    cd.wait('Boolean(' + task_dom + '?.querySelector("[data-testid=followthrough-recheck]"))',
            'amendment requires the original task to be rechecked')
    fill(cd, task_card + ' [data-testid=followthrough-transition-reason]', 'This original now needs review.')
    complete = task_dom + '.querySelector("[data-testid=followthrough-complete]")'
    assert cd.evaluate('!(' + complete + ') || ' + complete + '.matches(":disabled")')
    # A task can lead back to its own superseded original, even when the
    # current version uses the same local Observation identifier.
    click(cd, task_card + ' [data-testid=followthrough-open-laboratory-original]')
    cd.wait('document.querySelector("[data-testid=server-original]")?.textContent===' + json.dumps(raw.decode()),
            'task opens exact earlier laboratory original after amendment')
    original_text = cd.evaluate('document.querySelector("[data-testid=server-original]").textContent')
    assert hashlib.sha256(original_text.encode()).hexdigest() == committed['source_sha256']
    assert original_text != amended.decode()
    # Reading a task never grants permission to disclose its original bytes.
    journey('1')
    open_recorded_task()
    credentials[0]['actions'].remove('source_original_read')
    write_grants()
    try:
        click(cd, task_card + ' [data-testid=followthrough-open-laboratory-original]')
        cd.wait('Boolean(document.querySelector("[data-testid=records-status]")) && '
                'document.querySelector("[data-testid=records-status]").textContent.toLowerCase().includes("denied")',
                'task original requires an independent current original-read grant')
        assert not cd.evaluate('Boolean(document.querySelector("[data-testid=server-original]"))')
    finally:
        credentials[0]['actions'].append('source_original_read')
        write_grants()
    (artifacts / 'laboratory-task-reassessment.json').write_text(json.dumps({
        'synthetic': True, 'task_id': task_id, 'question_id': question_id, 'origin': expected_anchor,
        'initial_status': before['status'], 'current_source_id': current['source_id'],
        'inspected_task_original_sha256': hashlib.sha256(original_text.encode()).hexdigest(),
        'task_source_state_after_amendment': after['source_context_state'],
        'task_status_after_amendment': after['status'], 'history': [e['status'] for e in after['history']],
        'clinical_approval': after['clinical_approval'],
    }, indent=2) + '\n')
    print('PASS LABORATORY FOLLOW-UP: created from saved Observation, assigned and acknowledged, '
          'then reopened against its original report after amendment with stale completion blocked.')
    journey('1')
    click(cd, '[data-testid=lab-questions-reopen]')
    cd.wait(exists('followthrough-open-create'), 'saved laboratory history reloaded before revocation')
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
    journey('1')
    credentials[0]['actions'].remove('source_read');write_grants()
    cd.evaluate('[...document.querySelectorAll(".world-cases li")].find(e=>e.textContent.includes(' + json.dumps(CASE) + ')).querySelector("[data-testid=world-load]").click()')
    cd.wait('!document.querySelector("[data-testid=world-projection]") && document.querySelector("[data-testid=world-status]").textContent.includes("unavailable or revoked")', 'revoked laboratory projection cleared')
    credentials[0]['actions'].append('source_read');write_grants()
    cd.evaluate('window.fetch=window.__oiLabFetch;delete window.__oiLabFetch;delete window.__oiLabWrites;delete window.__oiLabDrop;delete window.__oiLabRequests;delete window.__oiLabPrepareCodes;delete window.__oiLabQuestionPosts;delete window.__oiLabHistoryCodes;delete window.__oiLabCatalog')
    navigate('Overview')
    (artifacts / 'laboratory-fhir-workflow.json').write_text(json.dumps({
        'synthetic': True, 'case_id': CASE, 'original_source_id': first['source_id'],
        'amended_source_id': current['source_id'], 'original_sha256': first['sha256'],
        'amended_sha256': current['sha256'], 'observation_count': 3,
        'selection_writes': 0, 'lost_response_retry_same_intent': True,
        'preserved_original_and_history': True, 'original_denial': True,
        'projection_denial': True, 'journey_to_records_fresh_metadata_only': True,
        'laboratory_only_overview_inspection': True,
        'clinical_interpretation': False}, indent=2) + '\n')
    print('PASS LABORATORY: actual fictional file selection; zero implicit writes; exact lost-response retry; typed zero/number/absence; explicit amendment; exact current/historical JSON; original and projection revocation; 390px layout.')
