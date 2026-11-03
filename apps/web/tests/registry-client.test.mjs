import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const token='fictional_test_credential_000000000001';
const token2='fictional_test_credential_000000000002';
const patient=(id='PAT-EXAMPLE-001')=>({patient_id:id,origin_org:'FICT-ORG',created_at:'2026-11-02T10:00:00Z',status:'active',revision:1});
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return {promise:new Promise(r=>{resolve=r}),resolve:(x)=>resolve(x)}};
test('default session has no authority and does not call transport',async()=>{let calls=0;const s=new RegistrySession(async()=>{calls++;return response(patient())});await s.read('PAT-EXAMPLE-001');assert.equal(calls,0);assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null)});
test('credential is absent from public state; session replacement clears patient',async()=>{const s=new RegistrySession(async()=>response(patient()));s.connect(token);await s.read('PAT-EXAMPLE-001');assert.ok(s.snapshot().patient);assert.ok(!JSON.stringify(s.snapshot()).includes(token));s.connect(token2);assert.equal(s.snapshot().patient,null);s.disconnect();assert.equal(s.snapshot().connected,false)});
test('create is explicit synthetic and does not auto-read or grant patient access',async()=>{const calls=[];const s=new RegistrySession(async(url,options)=>{calls.push([url,options]);return response({patient_id:'PAT-EXAMPLE-001',duplicate:false},201)});s.connect(token);await s.create('REQUEST-ONE',true);assert.equal(calls.length,1);assert.equal(calls[0][0],'/v1/patients');assert.deepEqual(JSON.parse(calls[0][1].body),{synthetic:true,request_key:'REQUEST-ONE'});assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().created.patient_id,'PAT-EXAMPLE-001')});
test('unconfirmed and malformed request keys never reach backend',async()=>{let calls=0;const s=new RegistrySession(async()=>{calls++;return response({})});s.connect(token);for(const key of ['','a','bad key','../other'])await s.create(key,true);await s.create('REQUEST-ONE',false);assert.equal(calls,0)});
test('fetch sends credential only to fixed same-origin API with no cookies or redirects',async()=>{let call;const s=new RegistrySession(async(...args)=>{call=args;return response(patient())});s.connect(token);await s.read('PAT-EXAMPLE-001');assert.equal(call[0],'/v1/patients/PAT-EXAMPLE-001');assert.equal(call[1].headers.Authorization,'Bearer '+token);assert.equal(call[1].credentials,'omit');assert.equal(call[1].redirect,'error');assert.equal(call[1].cache,'no-store');await s.read('https://attacker.invalid');assert.equal(call[0],'/v1/patients/PAT-EXAMPLE-001');assert.equal(s.snapshot().patient,null)});
test('HTTP 404 clears prior patient without exposing server detail',async()=>{let n=0;const s=new RegistrySession(async()=>++n===1?response(patient()):response({detail:'secret identity detail'},404));s.connect(token);await s.read('PAT-EXAMPLE-001');await s.read('PAT-EXAMPLE-002');assert.equal(s.snapshot().patient,null);assert.ok(!JSON.stringify(s.snapshot()).includes('secret'));assert.equal(s.snapshot().connected,true)});
test('HTTP 401 expires session and removes old patient and creation receipt',async()=>{let n=0;const s=new RegistrySession(async()=>++n===1?response(patient()):response({},401));s.connect(token);await s.read('PAT-EXAMPLE-001');await s.read('PAT-EXAMPLE-001');assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().created,null)});
test('late old patient response cannot replace a newer selection',async()=>{const a=deferred(),b=deferred();let n=0;const s=new RegistrySession(()=>++n===1?a.promise:b.promise);s.connect(token);const pa=s.read('PAT-EXAMPLE-001'),pb=s.read('PAT-EXAMPLE-002');b.resolve(response(patient('PAT-EXAMPLE-002')));await pb;a.resolve(response(patient()));await pa;assert.equal(s.snapshot().patient.patient_id,'PAT-EXAMPLE-002')});
test('old response after disconnect/reconnect is discarded even for same patient',async()=>{const a=deferred();const s=new RegistrySession(()=>a.promise);s.connect(token);const p=s.read('PAT-EXAMPLE-001');s.disconnect();s.connect(token);a.resolve(response(patient()));await p;assert.equal(s.snapshot().patient,null)});
test('mismatched or extra response fields and malformed values are withheld',async()=>{for(const value of [patient('PAT-WRONG'),{...patient(),secret:'raw-text'},{...patient(),revision:0},{...patient(),status:'approved'},{...patient(),created_at:'unknown'}]){const s=new RegistrySession(async()=>response(value));s.connect(token);await s.read('PAT-EXAMPLE-001');assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().phase,'error')}});
test('explicit retry uses same request key; no hidden automatic retry',async()=>{const requests=[];const s=new RegistrySession(async(url,options)=>{requests.push(options.body);if(requests.length===1)throw Error('network token '+token);return response({patient_id:'PAT-EXAMPLE-001',duplicate:true})});s.connect(token);await s.create('REQUEST-SAME',true);assert.equal(requests.length,1);assert.ok(!JSON.stringify(s.snapshot()).includes(token));await s.create('REQUEST-SAME',true);assert.equal(requests[0],requests[1]);assert.equal(s.snapshot().created.duplicate,true)});
test('concurrent create clicks do not produce extra network calls',async()=>{const d=deferred();let count=0;const s=new RegistrySession(()=>{count++;return d.promise});s.connect(token);const p=s.create('REQUEST-ONE',true);await s.create('REQUEST-TWO',true);assert.equal(count,1);d.resolve(response({patient_id:'PAT-EXAMPLE-001',duplicate:false},201));await p});
test('response after read grant failure cannot restore stale content',async()=>{const d=deferred();let n=0;const s=new RegistrySession(()=>++n===1?d.promise:Promise.resolve(response({},404)));s.connect(token);const p=s.read('PAT-EXAMPLE-001');await s.read('PAT-EXAMPLE-002');d.resolve(response(patient()));await p;assert.equal(s.snapshot().patient,null)});
test('oversized or non-JSON data is rejected without retaining content',async()=>{for(const r of [new Response('x'.repeat(65537),{headers:{'content-type':'application/json'}}),new Response('<html>secret</html>',{headers:{'content-type':'text/html'}})]){const s=new RegistrySession(async()=>r);s.connect(token);await s.read('PAT-EXAMPLE-001');assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().phase,'error')}});
test('invalid replacement credential clears any earlier session',async()=>{const s=new RegistrySession(async()=>response(patient()));s.connect(token);await s.read('PAT-EXAMPLE-001');s.connect('not valid');assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null)});
test('terminal newline cannot pass opaque identifier or credential validation',async()=>{let calls=0;const s=new RegistrySession(async()=>{calls++;return response(patient())});s.connect(token+'\n');assert.equal(s.snapshot().connected,false);s.connect(token);await s.read('PAT-EXAMPLE-001\n');assert.equal(calls,0)});
test('creating a different identity clears prior selection and invalidates an older pending read',async()=>{const d=deferred();const s=new RegistrySession((url)=>url==='/v1/patients'?Promise.resolve(response({patient_id:'PAT-NEW-001',duplicate:false},201)):d.promise);s.connect(token);const old=s.read('PAT-EXAMPLE-001');await s.create('REQUEST-NEW',true);d.resolve(response(patient()));await old;assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().created.patient_id,'PAT-NEW-001')});


const syntheticCase=()=>({
  case_id:'CASE-ALPHA',patient_id:'PAT-EXAMPLE-001',
  source_organization:'ORG-INSTITUTION',source_system:'SYS-SYNTH',
  source_subject_ref:'SUBJECT-SYNTH',review_ref:'REVIEW-SYNTH',
  status:'active',revision:1,created_at:'2026-11-02T20:00:00+00:00',
  revoked_at:null,source_identity_verified:false,
  clinical_sources_linked:false,clinical_conclusions:false,
});
const sourceId='SRC-'+'A'.repeat(32);
const sourceRecord=()=>({
  source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:'b'.repeat(64),
  kind:'pathology',event_date:'2026-01-10',issued_at:'2026-01-11',
  received_at:'2026-11-02T20:00:00+00:00',specimen_id:'SPECIMEN-ONE',
  state:'current',supersedes_id:null,
});
const caseList=()=>({
  patient_id:'PAT-EXAMPLE-001',mappings:[syntheticCase()],synthetic:true,
  source_identity_verified:false,clinical_sources_linked:false,
});
const sourceIndex=()=>({
  contract:'oi.synthetic-original-sources/1',
  patient_id:'PAT-EXAMPLE-001',case_id:'CASE-ALPHA',access_receipt_id:'ACCESS-'+'A'.repeat(32),
  sources:[sourceRecord()],source_reported_assertions:[{
    source_id:sourceId,finding_key:'marker',reported_state:'not-reported',
    source_statement:'Fictional café <script>literal</script>.',source_line:8,
    clinical_review_state:'not_established',
  }],synthetic:true,clinical_interpretation:false,
  research_review_invalidation_integrated:false,
});
test('read-only Records requests use exact canonical patient/case URLs and no local clinical authority',async()=>{
  const seen=[];
  const s=new RegistrySession(async (url,init)=>{
    seen.push([url,init]);
    if(url==='/v1/patients/PAT-EXAMPLE-001')return response(patient());
    if(url==='/v1/patients/PAT-EXAMPLE-001/case-bindings')return response(caseList());
    if(url==='/v1/patients/PAT-EXAMPLE-001/cases/CASE-ALPHA/sources')return response(sourceIndex());
    throw Error('unrecognized URL');
  });
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();
  assert.equal(s.snapshot().cases.length,1);
  assert.equal(s.snapshot().sourceIndex,null);
  await s.loadSources('CASE-ALPHA');
  const v=s.snapshot();
  assert.equal(v.sourceIndex.sources.length,1);
  assert.equal(v.sourceIndex.source_reported_assertions[0].clinical_review_state,'not_established');
  assert.equal(v.sourceIndex.clinical_interpretation,false);
  assert.equal(seen.length,3);
  for(const [url,init] of seen){
    assert.ok(url.startsWith('/v1/patients/PAT-EXAMPLE-001'));
    assert.equal(init.method,'GET');
    assert.equal(init.headers.Authorization,'Bearer '+token);
    assert.equal(init.credentials,'omit');assert.equal(init.redirect,'error');
    assert.equal(init.cache,'no-store');assert.equal(init.body,undefined);
  }
  assert.equal(JSON.stringify(v).includes(token),false);
});
test('unbound case, revoked case or fabricated case ID never generates source request',async()=>{
  let requests=0;
  const s=new RegistrySession(async (url)=>{
    requests++;if(url.endsWith('/case-bindings'))return response(caseList());
    return response(patient());
  });
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();
  await s.loadSources('CASE-FOREIGN');await s.loadSources('https://other.example');
  assert.equal(requests,2);assert.equal(s.snapshot().sourceIndex,null);
  const revoked=caseList();revoked.mappings[0].status='revoked';
  const s2=new RegistrySession(async url=>response(url.endsWith('/case-bindings')?revoked:patient()));
  s2.connect(token);await s2.read('PAT-EXAMPLE-001');await s2.loadCases();
  await s2.loadSources('CASE-ALPHA');assert.equal(s2.snapshot().recordsPhase,'error');
});
test('mismatched patient, forged authority and wrong-case source evidence fail closed',async()=>{
  const wrongCase=caseList();wrongCase.patient_id='PAT-OTHER';
  const forgedCase=caseList();forgedCase.mappings[0].clinical_conclusions=true;
  for(const value of [wrongCase,forgedCase]){
    const s=new RegistrySession(async url=>response(url.endsWith('/case-bindings')?value:patient()));
    s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();
    assert.equal(s.snapshot().cases,null);assert.equal(s.snapshot().recordsPhase,'error');
  }
  for(const mutate of [
    x=>{x.patient_id='PAT-OTHER';},
    x=>{x.clinical_interpretation=true;},
    x=>{x.source_reported_assertions[0].source_id='SRC-'+'F'.repeat(32);},
    x=>{x.source_reported_assertions[0].clinical_review_state='approved';},
    x=>{x.sources[0].sha256='not-a-hash';},
    x=>{x.case_id='CASE-OTHER';},
  ]){
    const source=sourceIndex();mutate(source);
    const s=new RegistrySession(async url=>response(url.endsWith('/case-bindings')?caseList():
      url.endsWith('/sources')?source:patient()));
    s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();await s.loadSources('CASE-ALPHA');
    assert.equal(s.snapshot().sourceIndex,null);assert.equal(s.snapshot().recordsPhase,'error');
  }
});
test('renewed patient selection clears old case and source data immediately',async()=>{
  const delay=deferred();
  const s=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/sources'))return response(sourceIndex());
    if(url.endsWith('/PAT-OTHER'))return delay.promise;
    return response(patient());
  });
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();await s.loadSources('CASE-ALPHA');
  assert.ok(s.snapshot().sourceIndex);
  const waiting=s.read('PAT-OTHER');
  assert.equal(s.snapshot().cases,null);assert.equal(s.snapshot().sourceIndex,null);
  delay.resolve(response(patient('PAT-OTHER')));await waiting;
  assert.equal(s.snapshot().patient.patient_id,'PAT-OTHER');
  assert.equal(s.snapshot().sourceIndex,null);
  s.disconnect();assert.equal(s.snapshot().cases,null);
});
test('late source response after patient switch cannot restore wrong-patient findings',async()=>{
  const delay=deferred();
  const s=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/sources'))return delay.promise;
    if(url.endsWith('/PAT-OTHER'))return response(patient('PAT-OTHER'));
    return response(patient());
  });
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();
  const inFlight=s.loadSources('CASE-ALPHA');
  await s.read('PAT-OTHER');
  delay.resolve(response(sourceIndex()));await inFlight;
  assert.equal(s.snapshot().patient.patient_id,'PAT-OTHER');
  assert.equal(s.snapshot().sourceIndex,null);assert.equal(s.snapshot().cases,null);
});
test('source-read denial, contract failure and credential expiry erase prior source state',async()=>{
  let count=0;
  const s=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/sources'))return ++count===1?response(sourceIndex()):response({detail:'sensitive'},404);
    return response(patient());
  });
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();
  await s.loadSources('CASE-ALPHA');assert.ok(s.snapshot().sourceIndex);
  await s.loadSources('CASE-ALPHA');
  assert.equal(s.snapshot().sourceIndex,null);assert.equal(s.snapshot().cases,null);
  assert.equal(JSON.stringify(s.snapshot()).includes('sensitive'),false);
  const expired=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/sources'))return response({},401);
    return response(patient());
  });
  expired.connect(token);await expired.read('PAT-EXAMPLE-001');await expired.loadCases();
  await expired.loadSources('CASE-ALPHA');
  assert.equal(expired.snapshot().connected,false);
  assert.equal(expired.snapshot().sourceIndex,null);
});
test('new identity creation cannot retain old patient source versions',async()=>{
  const s=new RegistrySession(async(url)=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/sources'))return response(sourceIndex());
    if(url==='/v1/patients')return response({patient_id:'PAT-NEW-001',duplicate:false},201);
    return response(patient());
  });
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();await s.loadSources('CASE-ALPHA');
  assert.ok(s.snapshot().sourceIndex);
  await s.create('REQUEST-NEW',true);
  assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().sourceIndex,null);
  assert.equal(s.snapshot().cases,null);
});

test('reviewed document transport accepts the complete bounded Unicode revision history',async()=>{
  const quote='é'.repeat(1200);
  const document={patient_id:'PAT-EXAMPLE-001',case_id:'CASE-ALPHA',revisions:Array.from({length:64},(_,i)=>({revision:i+1,findings:Array.from({length:30},(_,j)=>({key:'finding-'+j,state:'pending',line:1,quote}))}))};
  assert.ok(new TextEncoder().encode(JSON.stringify(document)).length>4_000_000);
  const s=new RegistrySession(async url=>response(url.endsWith('/documents/'+sourceId)?document:url.endsWith('/case-bindings')?caseList():url.endsWith('/sources')?sourceIndex():patient()));
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();await s.loadSources('CASE-ALPHA');
  assert.deepEqual((await s.documentRequest('CASE-ALPHA','/'+sourceId)).body,document);
});
test('document transport cancels an oversized undeclared stream before consuming its remainder',async()=>{
  let cancelled=false,pulls=0;
  const oversized=()=>new Response(new ReadableStream({pull(c){pulls++;if(pulls>36)c.close();else c.enqueue(new Uint8Array(1024*1024));},cancel(){cancelled=true;}}),{headers:{'Content-Type':'application/json'}});
  const s=new RegistrySession(async url=>url.includes('/documents')?oversized():response(url.endsWith('/case-bindings')?caseList():url.endsWith('/sources')?sourceIndex():patient()));
  s.connect(token);await s.read('PAT-EXAMPLE-001');await s.loadCases();await s.loadSources('CASE-ALPHA');
  await assert.rejects(s.documentRequest('CASE-ALPHA','/'+sourceId));
  assert.equal(cancelled,true);assert.ok(pulls<=35);
});
