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


def fictional_bundle(*, amended=False):
    """Independently authored numeric-zero, negative-number and absent fixtures."""
    subject = {'reference': 'Patient/' + SUBJECT}
    specimen = {'reference': 'Specimen/FICT-WEB-SPEC'}
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
        {'resourceType': 'Patient', 'id': SUBJECT},
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
    grants = {'case_binding_create', 'case_binding_read', 'source_import', 'source_read', 'source_original_read', 'question_read', 'composer_context_read'}
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
      window.__oiLabFetch=window.fetch;window.__oiLabWrites=[];window.__oiLabDrop=true;window.__oiLabRequests=0;window.__oiLabPrepareCodes=[];
      window.fetch=async(input,init)=>{
        window.__oiLabRequests++;
        const laboratory=String(input).endsWith('/laboratory/fhir-r4/sources')&&init?.method==='POST';
        if(laboratory)window.__oiLabWrites.push(JSON.parse(init.body));
        const response=await window.__oiLabFetch(input,init);
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

    def journey(expected_value):
        navigate('Journey')
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

    def draft_question(source_id, suffix, question):
        before = cd.evaluate('window.__oiLabRequests')
        target = source_id + '|Observation/FICT-WEB-' + suffix
        cd.evaluate("(() => {const e=document.querySelector('[data-testid=lab-question-result]');"
                    "e.value=" + json.dumps(target) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        cd.wait("Boolean(document.querySelector('[data-testid=lab-question-text]'))", 'editable question for selected lab result')
        cd.evaluate("(() => {const e=document.querySelector('[data-testid=lab-question-text]');"
                    "Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e," + json.dumps(question) + ");"
                    "e.dispatchEvent(new Event('input',{bubbles:true}));})()")
        cd.wait("document.querySelector('[data-testid=lab-question-prepare]')?.disabled===false", 'human question ready')
        assert cd.evaluate('window.__oiLabRequests') == before, 'Selection and editing must make no network request'

    def submit_question():
        cd.evaluate("document.querySelector('[data-testid=lab-question-prepare]').click()")

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
    cd.wait('document.querySelectorAll("[data-testid=world-laboratory-observation]").length===3', 'Overview returns to the three source-reported laboratory results')
    assert operator(questions_path)['questions'] == []
    draft_question(first['source_id'], 'ZERO', question)
    submit_question()
    cd.wait("window.__oiLabPrepareCodes.length===1", 'explicit preparation completed over HTTP')
    assert cd.evaluate("window.__oiLabPrepareCodes") == [200], 'Expected scoped laboratory HTTP success'
    cd.wait("Boolean(document.querySelector('[data-testid=lab-question-receipt]')) || !document.querySelector('[data-testid=world-projection]')", 'client accepted or rejected the prepared source')
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))"), cd.evaluate("document.querySelector('[data-testid=world-status]').textContent")
    prepared = cd.evaluate("document.querySelector('[data-testid=lab-question-receipt]').textContent")
    assert all(x in prepared for x in (question, first['source_id'], first['sha256'], 'Observation/FICT-WEB-ZERO', 'ACCESS-'))
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
    draft_question(current['source_id'], 'ABSENT', question)
    submit_question()
    cd.wait("document.querySelector('[data-testid=lab-question-receipt]')?.textContent.includes('Observation/FICT-WEB-ABSENT')", 'absent result prepared on amended report')
    amended_receipt = cd.evaluate("document.querySelector('[data-testid=lab-question-receipt]').textContent")
    assert current['sha256'] in amended_receipt and first['source_id'] not in amended_receipt
    credentials[0]['actions'].remove('composer_context_read');write_grants()
    submit_question()
    cd.wait("!document.querySelector('[data-testid=world-projection]') && document.querySelector('[data-testid=world-status]').textContent.includes('Recheck access')", 'Composer denial withholds projection and prepared answer')
    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=lab-question-receipt]'))")
    assert operator(questions_path)['questions'] == []
    credentials[0]['actions'].append('composer_context_read');write_grants()
    (artifacts / 'laboratory-question-preparation.json').write_text(json.dumps({
        'synthetic': True, 'case_id': CASE, 'original': prepared, 'amendment': amended_receipt,
        'http_statuses': cd.evaluate('window.__oiLabPrepareCodes'),
        'requests_on_selection_or_edit': 0, 'saved_questions_after_preparation': 0,
        'edited_receipt_cleared': True, 'denied_projection_withheld': True,
    }, indent=2) + '\n')
    assert cd.evaluate('window.__oiLabPrepareCodes') == [200, 200, 404]
    print('PASS LAB QUESTION: exact current and amended results, explicit human question, zero implicit requests or saved questions, Composer revocation withheld the preview.')
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
    cd.evaluate('window.fetch=window.__oiLabFetch;delete window.__oiLabFetch;delete window.__oiLabWrites;delete window.__oiLabDrop;delete window.__oiLabRequests;delete window.__oiLabPrepareCodes')
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
