import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { RegistrySession } from '../.test-dist/registry-client.js';

const p='PAT-EXAMPLE-001', q='PAT-EXAMPLE-002', base='/v1/patients/'+p+'/encounters';
const token='fictional_test_credential_000000000001', at='2026-11-02T10:00:00+00:00';
const receipt='ACCESS-'+'A'.repeat(32), key='NOTE-ONE';
const sha=body=>createHash('sha256').update(body).digest('hex');
const patient=(patient_id,status='active')=>({patient_id,origin_org:'FICT-ORG',created_at:at,status,revision:1});
const visit=id=>({id,patient_id:p,external_key:'VISIT-'+id,kind:'outpatient',service_date:'2026-06-12',
  status:'scheduled',revision:1,created_at:at,updated_at:at});
const visits=(rows=[visit(1)],next=null)=>({patient_id:p,access_receipt_id:receipt,encounters:rows,next_after_id:next});
const notes=()=>({patient_id:p,encounter_id:1,notes:[{id:1,note_key:key,latest_version:2}],next_after_id:null,access_receipt_id:receipt});
const version=(n,body='Fictional draft '+n)=>({id:n*2,version:n,status:'draft',body,sha256:sha(body),authored_by:'FICT-ACTOR',
  created_at:at,supersedes_id:n===1?null:2*(n-1),amendment_reason:null,facility_id:null,department_id:null,note_kind:'consultation'});
const history=(rows,next=null)=>({patient_id:p,encounter_id:1,note_key:key,versions:rows,next_after_version:next,access_receipt_id:receipt});
const json=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json'}});
const pending=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve};};
async function setup(handler,status='active'){
  const calls=[];
  const session=new RegistrySession(async (url,init)=>{
    if([p,q].some(id=>url==='/v1/patients/'+id))return json(patient(url.split('/').at(-1),status));
    calls.push([url,init]);return handler(url,init);
  });
  session.connect(token);await session.read(p);
  return {session,calls,api:session.encounterChart(p)};
}
test('list visits, note headers, and attributed history through protected canonical routes',async()=>{
  const body='Fictional café 🧬 <literal>\nSecond line.';
  const rows=[version(1,body),version(2)];
  const {api,calls,session}=await setup(url=>json(url.includes('/versions?')?history(rows):url.includes('/notes?')?notes():visits()));
  assert.deepEqual(await api.visits(),visits());assert.deepEqual(await api.notes(1),notes());
  assert.deepEqual(await api.versions(1,key),history(rows));
  assert.deepEqual(calls.map(([url])=>url),[base+'?after_id=0&limit=25',base+'/1/notes?after_id=0&limit=25',base+'/1/notes/'+key+'/versions?after_version=0&limit=25']);
  for(const [,init] of calls){
    assert.equal(init.method,'GET');assert.equal(init.body,undefined);
    assert.equal(init.headers.Authorization,'Bearer '+token);assert.equal(init.credentials,'omit');
    assert.equal(init.cache,'no-store');assert.equal(init.redirect,'error');
  }
  assert.ok(!JSON.stringify([api,session.snapshot()]).includes(token));
});
test('bounded pages reject foreign subjects, extra fields, malformed receipt, row order, dates and cursor drift',async()=>{
  const cases=[
    visits([{...visit(1),patient_id:q}]), {...visits(),patient_id:q}, visits([{...visit(1),service_date:'2026-02-30'}]),
    visits([{...visit(1),diagnosis:'unverified'}]), visits([visit(1),visit(1)]), visits([visit(1)],2),
    visits(Array.from({length:26},(_,i)=>visit(i+1))),{...visits(),access_receipt_id:'wrong'}
  ];
  for(const payload of cases){const {api}=await setup(()=>json(payload));await assert.rejects(api.visits());}
  const {api}=await setup(()=>json(visits()));await assert.rejects(api.visits(1));
  for(const payload of [{...notes(),encounter_id:2},{...notes(),patient_id:q},{...notes(),notes:[...notes().notes,{id:2,note_key:key,latest_version:1}]}]){
    const {api}=await setup(()=>json(payload));await assert.rejects(api.notes(1));
  }
});
test('history verifies body bytes, version continuity, previous row identity, status and first-page scope',async()=>{
  for(const payload of [{...history([]),note_key:'NOTE-OTHER'}, {...history([]),encounter_id:2},history([version(2)]),
    history([version(1),{...version(2),supersedes_id:7}]),history([{...version(1),body:'changed'}]),
    history([{...version(1),status:'approved'}]),history([{...version(1),supersedes_id:1}]),
    history([{...version(1),status:'draft_correction',amendment_reason:null}])]){
    const {api}=await setup(()=>json(payload));await assert.rejects(api.versions(1,key));
  }
});
test('all 25 maximum Unicode note bodies fit and the next page must supersede the verified preceding row',async()=>{
  const body='🧬'.repeat(20000),initial=history(Array.from({length:25},(_,i)=>version(i+1,body)),25);
  let bad=true;
  const {api}=await setup(url=>json(url.includes('after_version=0')?initial:
    history([{...version(26),supersedes_id:bad?49:50}])));
  assert.equal((await api.versions(1,key)).next_after_version,25);
  await assert.rejects(api.versions(1,key,25));bad=false;
  assert.equal((await api.versions(1,key,25)).versions[0].version,26);
});
const schedule={synthetic:true,request_key:'SCHEDULE-ONE',external_key:'VISIT-ONE',kind:'outpatient',service_date:'2026-11-05'};
const move={synthetic:true,request_key:'TRANSITION-ONE',target:'in_progress',expected_revision:1};
const draft={synthetic:true,request_key:'WRITE-ONE',expected_version:0,body:' Fictional note 🧬\n',note_kind:'progress'};
const scheduled={encounter_id:3,status:'scheduled',revision:1},moved={encounter_id:3,status:'in_progress',revision:2};
const saved={note_id:6,note_key:key,version:1,status:'draft',sha256:sha('Fictional note 🧬')};
test('commands bind exact stable synthetic intent, transition revision and note digest to receipts',async()=>{
  const {api,calls}=await setup(url=>json(url===base?scheduled:url.endsWith('/transitions')?moved:saved));
  assert.deepEqual(await api.schedule(schedule),scheduled);assert.deepEqual(await api.transition(3,move),moved);
  assert.deepEqual(await api.saveNote(3,key,draft),saved);await api.saveNote(3,key,draft);
  assert.deepEqual(calls.map(([url])=>url),[base,base+'/3/transitions',base+'/3/notes/'+key+'/versions',base+'/3/notes/'+key+'/versions']);
  assert.deepEqual(calls.map(([,o])=>JSON.parse(o.body)),[schedule,move,draft,draft]);
  assert.ok(calls.every(([,o])=>o.method==='POST'));assert.equal(calls[2][1].body,calls[3][1].body);
  for(const value of [{...moved,encounter_id:2},{...moved,revision:1},{...moved,status:'completed'}]){
    const {api}=await setup(()=>json(value));await assert.rejects(api.transition(3,move));
  }
  for(const value of [{...saved,version:2},{...saved,note_key:'NOTE-OTHER'},{...saved,sha256:'0'.repeat(64)}]){
    const {api}=await setup(()=>json(value));await assert.rejects(api.saveNote(3,key,draft));
  }
});
test('bad paths, commands, unsafe integers, excessive text and inactive patients make no chart requests',async()=>{
  const {api,calls,session}=await setup(()=>json({}));
  for(const invoke of [()=>api.visits(-1),()=>api.notes(1.5),()=>api.versions(1,'NOTE/../../X'),
    ()=>api.schedule({...schedule,synthetic:false}),()=>api.schedule({...schedule,request_key:'short'}),
    ()=>api.transition(1,{...move,expected_revision:Number.MAX_SAFE_INTEGER+1}),
    ()=>api.schedule({...schedule,service_date:'2026-02-31'}),()=>api.saveNote(1,key,{...draft,expected_version:2147483647}),
    ()=>api.saveNote(1,key,{...draft,body:'🧬'.repeat(20001)}),()=>api.saveNote(1,key,{...draft,body:'\ud800'}),
    ()=>api.saveNote(1,key,{...draft,body:'   '}),()=>api.saveNote(1,key,{...draft,actor:'FORGED'}),
    ()=>session.encounterChart(q).visits()])await assert.rejects(async()=>invoke());
  assert.equal(calls.length,0);
  const suspended=await setup(()=>json(visits()),'suspended');
  await assert.rejects(async()=>suspended.api.visits());assert.equal(suspended.calls.length,0);
});
test('HTTP denial clears active patient (401 disconnects); errors and pending writes never expose server/transport details',async()=>{
  for(const code of [401,403,404,409,422,503]){
    const {api,session,calls}=await setup(()=>new Response('sensitive server text '+token,{status:code}));
    await assert.rejects(api.schedule(schedule),e=>e.status===code&&!String(e).includes('sensitive')&&!String(e).includes(token));
    assert.equal(calls.length,1);assert.equal(session.snapshot().connected,code!==401);
    assert.equal(session.snapshot().patient?.patient_id,[401,403,404].includes(code)?undefined:p);
  }
  const {api}=await setup(()=>{throw Error(token)});await assert.rejects(api.visits(),e=>!String(e).includes(token));
});
test('a stale success or denial, even for a reopened patient ID, cannot affect the new selection',async()=>{
  for(const code of [200,401,404]){
    const gate=pending();const {session,api}=await setup(()=>gate.promise);
    const loading=api.visits();await session.read(q);await session.read(p);
    gate.resolve(json(visits(),code));await assert.rejects(loading);
    assert.equal(session.snapshot().patient?.patient_id,p);assert.equal(session.snapshot().connected,true);
    await assert.rejects(api.visits());
  }
});
test('patient/credential switch during response body streaming withholds note content',async()=>{
  const started=pending();let controller;
  const response=new Response(new ReadableStream({start(c){controller=c;},pull(){started.resolve();}},{highWaterMark:0}),{headers:{'Content-Type':'application/json'}});
  const {api,session}=await setup(()=>response);const loading=api.versions(1,key);
  await started.promise;await session.read(q);
  controller.enqueue(new TextEncoder().encode(JSON.stringify(history([version(1)]))));controller.close();
  await assert.rejects(loading);assert.equal(session.snapshot().patient.patient_id,q);
});
const caseId='CASE-ALPHA',sourceId='SRC-'+'A'.repeat(32);
async function withSources(handler){
  const row={case_id:caseId,patient_id:p,source_organization:'ORG-ONE',source_system:'SYS-ONE',source_subject_ref:'SUBJ-ONE',
    review_ref:'REV-ONE',status:'active',revision:1,created_at:at,revoked_at:null,source_identity_verified:false,
    clinical_sources_linked:false,clinical_conclusions:false};
  const source={source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:'f'.repeat(64),kind:'clinical',event_date:'2026-06-12',
    issued_at:'2026-06-12',received_at:at,specimen_id:null,state:'current',supersedes_id:null};
  const {session,calls}=await setup((url,init)=>{
    if(url.endsWith('/case-bindings'))return json({patient_id:p,mappings:[row],synthetic:true,source_identity_verified:false,clinical_sources_linked:false});
    if(url.endsWith('/sources'))return json({contract:'oi.synthetic-original-sources/1',patient_id:p,case_id:caseId,access_receipt_id:receipt,
      sources:[source],source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false});
    return handler(url,init);
  });
  await session.loadCases();await session.loadSources(caseId);assert.ok(session.snapshot().sourceIndex);
  const body={synthetic:true,request_key:'LINK-ONE',source_id:sourceId,expected_version:1,expected_sha256:source.sha256};
  return {session,calls,body};
}
test('source links bind to the live index, use a protected request, and preserve an exact replay body',async()=>{
  const {session,calls,body}=await withSources((url,init)=>json(init.body?{id:2,duplicate:false}:{ok:true},init.body?201:200));
  for(const [subject,id,c,after,command] of [[q,1,caseId,0],[p,0,caseId,0],[p,1,'CASE-FOREIGN',0],
    [p,1,caseId,-1],[p,1,caseId,null],[p,1,caseId,0,JSON.stringify(body)],
    [p,1,caseId,null,JSON.stringify({...body,expected_sha256:'b'.repeat(64)})]]){
    await assert.rejects(session.encounterSourceRequest(subject,id,c,after,command));
  }
  assert.equal(calls.length,2);
  assert.deepEqual(await session.encounterSourceRequest(p,1,caseId,0),{ok:true});
  const wire=JSON.stringify(body);assert.deepEqual(await session.encounterSourceRequest(p,1,caseId,null,wire),{id:2,duplicate:false});
  assert.equal(calls[2][0],base+'/1/cases/'+caseId+'/source-links?after_id=0&limit=25');
  assert.equal(calls[3][0],base+'/1/cases/'+caseId+'/source-links');assert.equal(calls[3][1].body,wire);
  assert.equal(calls[3][1].headers.Authorization,'Bearer '+token);assert.equal(calls[3][1].credentials,'omit');
});
test('reloading the same source index discards a late denial; current denial erases original and patient scope',async()=>{
  const gate=pending();let n=0;
  const {session}=await withSources(()=>++n===1?gate.promise:new Response(null,{status:404}));
  const old=session.encounterSourceRequest(p,1,caseId,0);
  await session.loadSources(caseId);const latest=session.snapshot().sourceIndex;assert.ok(latest);
  gate.resolve(new Response(null,{status:401}));await assert.rejects(old);
  assert.equal(session.snapshot().sourceIndex,latest);assert.equal(session.snapshot().connected,true);
  await assert.rejects(session.encounterSourceRequest(p,1,caseId,0),e=>e.status===404);
  assert.equal(session.snapshot().sourceIndex,null);assert.equal(session.snapshot().cases,null);
  assert.equal(session.snapshot().patient,null);assert.equal(session.snapshot().connected,true);
});
test('a timed-out transport that ignores AbortSignal cannot use a late denial to clear a valid selection',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const gate=pending(),{api,session,calls}=await setup(()=>gate.promise);
  const waiting=api.visits();t.mock.timers.tick(10001);assert.ok(calls[0][1].signal.aborted);
  gate.resolve(new Response(null,{status:401}));await assert.rejects(waiting);
  assert.equal(session.snapshot().patient.patient_id,p);assert.equal(session.snapshot().connected,true);
});
test('a patient switch while the note digest is being verified cannot disclose the old note',async t=>{
  const started=pending(),gate=pending(),subtle=crypto.subtle,original=subtle.digest.bind(subtle);
  t.mock.method(subtle,'digest',async (...args)=>{started.resolve();await gate.promise;return original(...args);});
  const {session,api}=await setup(()=>json(history([version(1)])));const waiting=api.versions(1,key);
  await started.promise;await session.read(q);gate.resolve();await assert.rejects(waiting);
  assert.equal(session.snapshot().patient.patient_id,q);
});
