import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {RegistrySession,requestIndex} from '../.test-dist/registry-client.js';
import {readRequests} from '../.test-dist/record-requests.js';
import {cases,deferred,time} from './authored-evidence-fixtures.mjs';
import {patientId,caseId,sourceId,response,sourceIndex,readyImages,transportForImages,token} from './source-images-fixtures.mjs';

const requestId='RECORD-'+'A'.repeat(32),path='/v1/patients/'+patientId+'/record-requests';
const scopedPath=path+'?case_id='+caseId;
const fields={kind:'imaging',record_label:'Fictional scan report',source_organization:'Example Center'};
const row=()=>({request_id:requestId,patient_id:patientId,...fields,status:'requested',revision:1,
  created_at:time,updated_at:time,receipt_status:'not_received',source_reference:null,external_request_sent:false});
const received=()=>({...row(),status:'received',revision:2,receipt_status:'source_current_unreviewed',
  source_reference:{case_id:caseId,source_id:sourceId,version:1,sha256:sourceIndex().sources[0].sha256}});
const list=(...requests)=>({patient_id:patientId,requests,synthetic:true,external_request_sent:false,source_receipts_enabled:true});
async function setup(handler,source=sourceIndex){
  const calls=[];
  const s=new RegistrySession(transportForImages((url,init)=>{
    if(url.includes('/record-requests')){calls.push([url,init]);return handler(url,init);}
  },source));
  await readyImages(s);
  return {s,api:s.recordRequests,index:requestIndex(s.snapshot()),calls,view:()=>s.snapshot().requestsView};
}

test('requests only load on demand in the current disclosure and use the protected patient route',async()=>{
  const {s,api,index,calls,view}=await setup(()=>response(list(row())));
  await api.refresh(index);await api.create(index,fields);assert.equal(calls.length,0);
  api.open(index);assert.equal(calls.length,0);await api.create(index,fields);assert.equal(calls.length,0);
  await api.refresh(index);
  assert.equal(calls.length,1);const [[url,init]]=calls;assert.equal(url,scopedPath);
  assert.equal(init.method,'GET');assert.equal(init.cache,'no-store');assert.equal(init.credentials,'omit');
  assert.equal(init.headers.Authorization,'Bearer '+token);assert.equal(view().rows[0].record_label,fields.record_label);
  api.close(index);assert.equal(view().rows,null);await api.receive(index,requestId,sourceId);assert.equal(calls.length,1);
  assert.equal(s.snapshot().connected,true);
});

test('a lost create receipt blocks further writes and replays only the byte-identical intent after same-case reauthorization',async()=>{
  let posts=0;
  const {s,api,index,calls,view}=await setup((url,init)=>{
    if(init.method==='GET')return response(posts?list(row()):list());
    if(++posts===1)throw Error('reply lost after commit');
    return response({request_id:requestId,duplicate:true},200);
  });
  api.open(index);await api.refresh(index);await api.create(index,{...fields,source_organization:' '+fields.source_organization+' '});
  assert.equal(view().retryCreate,true);assert.equal(view().rows,null);assert.equal(posts,1);
  await api.refresh(index);await api.create(index,{...fields,record_label:'Changed'});
  await api.receive(index,requestId,sourceId);assert.equal(posts,1);
  await s.loadSources(caseId);const newIndex=requestIndex(s.snapshot());
  api.open(newIndex);await api.refresh(newIndex);assert.deepEqual(view().retryFields,fields);
  await api.retryCreate(index);assert.equal(posts,1);
  await api.retryCreate(newIndex);assert.equal(posts,2);assert.equal(view().retryCreate,false);
  const postCalls=calls.filter(([,v])=>v.method==='POST');
  assert.deepEqual(postCalls.map(([url])=>url),[scopedPath,scopedPath]);
  const bodies=postCalls.map(([,v])=>v.body);
  assert.equal(bodies[0],bodies[1]);const parsed=JSON.parse(bodies[0]);assert.match(parsed.request_key,/^[a-f0-9-]{36}$/);
  assert.deepEqual(parsed,{synthetic:true,request_key:parsed.request_key,...fields});
  assert.match(view().message,/recovered/i);assert.equal(view().rows.length,1);
});

test('only a listed requested item and an explicitly chosen current same-kind version can produce one receive',async()=>{
  let reads=0;
  const gate=deferred(),wrong='SRC-'+'D'.repeat(32),old='SRC-'+'E'.repeat(32);
  const {api,index,calls,view}=await setup((url,init)=>init.method==='POST'?gate.promise:response(list(++reads===1?row():received())),
    ()=>{const i=sourceIndex();i.sources.push({...i.sources[0],source_id:wrong,kind:'pathology'},
      {...i.sources[0],source_id:old,state:'superseded'});return i;});
  api.open(index);await api.refresh(index);
  await api.receive(index,requestId,wrong);await api.receive(index,requestId,old);await api.receive(index,'RECORD-INVALID',sourceId);
  assert.equal(calls.length,1);
  const sending=api.receive(index,requestId,sourceId);
  await api.receive(index,requestId,sourceId);await api.create(index,fields);await api.refresh(index);
  assert.equal(calls.length,2);assert.equal(calls[1][0],path+'/'+requestId+'/receive');
  assert.deepEqual(JSON.parse(calls[1][1].body),{synthetic:true,case_id:caseId,source_id:sourceId});
  gate.resolve(response({request_id:requestId,source_id:sourceId,version:1,duplicate:false},201));await sending;
  assert.equal(calls.length,3);assert.equal(view().rows[0].source.source_id,sourceId);
  assert.equal(view().rows[0].receipt_status,'source_current_unreviewed');
  await api.receive(index,requestId,sourceId);assert.equal(calls.length,3);
});

test('receipt versions must resolve exactly in this case; revoked, withheld and other-case references never expose a reader',()=>{
  const index=sourceIndex();const historical=received();
  historical.receipt_status='source_superseded_reconciliation_required';index.sources[0].state='superseded';
  assert.equal(readRequests(list(historical),index)[0].source.version,1);
  assert.equal(readRequests(list(received()),index)[0].source,null,'current receipt contradicts superseded index');
  assert.equal(readRequests(list(historical),sourceIndex())[0].source,null,'superseded receipt contradicts current index');
  for(const ref of [null,{...historical.source_reference,case_id:'CASE-BETA'},
    {...historical.source_reference,sha256:'1'.repeat(64)},{...historical.source_reference,version:2}]){
    const out=readRequests(list({...historical,source_reference:ref}),index)[0];assert.equal(out.source,null);
    assert.equal(out.receipt_status,'source_superseded_reconciliation_required');
    assert.equal(JSON.stringify(out).includes(sourceId),false);
  }
  assert.equal(readRequests(list({...received(),receipt_status:'binding_revoked_not_usable',source_reference:null}),index)[0].source,null);
  assert.equal(readRequests(list({...row(),status:'cancelled',revision:2}),index)[0].status,'cancelled');
});

test('an unqualified or contradictory patient list replaces previously verified rows with nothing',async()=>{
  let value=list(row());
  const {api,index,view}=await setup(()=>response(value));
  api.open(index);
  for(const invalid of [
    {...list(row()),patient_id:'PATIENT-OTHER'},list({...row(),patient_id:'PATIENT-OTHER'}),list(row(),row()),
    list({...row(),record_label:'\rHidden'}),list({...row(),revision:2}),list({...row(),external_request_sent:true}),
    list({...received(),receipt_status:'binding_revoked_not_usable'}),list({...received(),source_reference:{...received().source_reference,sha256:'broken'}}),
    list({...row(),status:'received'}),list({...row(),created_at:'2026-02-31T12:00:00Z'}),
    {...list(),source_receipts_enabled:false},list({...row(),raw:'unexpected'}),list({...row(),request_id:requestId+'\n'}),
  ]){
    value=list(row());await api.refresh(index);assert.equal(view().rows.length,1);
    value=invalid;await api.refresh(index);assert.equal(view().rows,null);assert.match(view().message,/could not be verified/);
  }
});

test('401/403/404 remain authoritative even when the denied response is HTML',async()=>{
  for(const status of [401,403,404]){
    let denied=false;
    const {s,api,index,view}=await setup(()=>denied?new Response('PRIVATE',{status}):response(list(received())));
    api.open(index);await api.refresh(index);assert.equal(view().rows[0].source.source_id,sourceId);
    denied=true;await api.refresh(index);
    assert.equal(view().rows,null);assert.equal(requestIndex(s.snapshot()),null);assert.equal(s.snapshot().original,null);
    assert.equal(s.snapshot().connected,status!==401);assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE'));
  }
});

test('late responses after a close, source refresh, case/patient change or disconnect cannot disclose old requests or expire a new context',async()=>{
  for(const change of ['close','source refresh','case','patient','credential']){
    const gate=deferred();
    const {s,api,index,view,calls}=await setup(()=>gate.promise);api.open(index);const checking=api.refresh(index);
    if(change==='close')api.close(index);
    if(change==='source refresh')await s.loadSources(caseId);
    if(change==='case')await s.loadSources('CASE-BETA');
    if(change==='patient')await s.read('PAT-EXAMPLE-002');
    if(change==='credential')s.connect('next-session-credential'.repeat(2));
    assert.equal(calls[0][1].signal.aborted,true);
    gate.resolve(change==='credential'?new Response(null,{status:401}):response(list(row())));await checking;
    assert.equal(view().rows,null);assert.equal(s.snapshot().connected,true);
    assert.equal(JSON.stringify(view()).includes(fields.record_label),false);
  }
});

test('an interrupted create cannot auto-refresh a closed panel or recover another case’s command',async()=>{
  const gate=deferred();
  const {s,api,index,view,calls}=await setup((_,init)=>init.method==='POST'?gate.promise:response(list()));
  api.open(index);await api.refresh(index);
  const first=api.create(index,fields);await api.create(index,fields);api.close(index);
  gate.resolve(response({request_id:requestId,duplicate:false},201));await first;
  assert.equal(calls.length,2);assert.equal(view().rows,null);
  await s.loadSources('CASE-BETA');const other=requestIndex(s.snapshot());api.open(other);
  await api.retryCreate(other);await api.retryCreate(index);
  assert.equal(calls.length,2);assert.equal(view().retryCreate,false);
});

test('malformed or mismatched write receipts cannot report success or start another request automatically',async()=>{
  for(const type of ['create','receive']){
    const bad=type==='create'?{request_id:requestId,duplicate:true}:
      {request_id:requestId,source_id:sourceId,version:2,duplicate:false};
    const {api,index,calls,view}=await setup((_,init)=>init.method==='POST'?response(bad,201):response(list(row())));
    api.open(index);await api.refresh(index);
    if(type==='create')await api.create(index,fields);else await api.receive(index,requestId,sourceId);
    assert.equal(calls.length,2);assert.equal(view().rows,null);assert.equal(view().retryCreate,type==='create');
    assert.match(view().message,/uncertain/);
  }
});

test('an explicit authority denial destroys the exact create intent and cannot leak or replay it on same-case reentry',async()=>{
  for(const status of [401,403,404])for(const denyOn of ['create','list']){
    let denied=false,posts=0;
    const {s,api,index,view}=await setup((_,init)=>{
      if(init.method==='POST'){
        posts++;
        if(denyOn==='create')return new Response(null,{status});
        throw Error('Unknown write outcome');
      }
      return denied?new Response(null,{status}):response(list());
    });
    api.open(index);await api.refresh(index);await api.create(index,fields);
    if(denyOn==='list'){
      assert.equal(view().retryCreate,true);denied=true;await api.refresh(index);denied=false;
    }
    assert.equal(s.snapshot().sourceIndex,null);assert.equal(view().retryCreate,false);
    if(status===401)s.connect(token);
    await s.read(patientId);await s.loadCases();await s.loadSources(caseId);
    const next=requestIndex(s.snapshot());api.open(next);await api.refresh(next);
    assert.equal(view().retryFields,null);assert.equal(view().retryCreate,false);
    await api.retryCreate(next);assert.equal(posts,1);
  }
});

test('case/source denial or a revoked case mapping invalidates an uncertain create before the case can reopen',async()=>{
  for(const denial of ['source','case','revoked']){
    let deny=false,posts=0;
    const s=new RegistrySession(transportForImages((url,init)=>{
      if(url===scopedPath){
        if(init.method==='POST'){posts++;return response({},503);}
        return response(list());
      }
      if(deny && denial==='source' && url.endsWith('/sources'))return response({},404);
      if(deny && url.endsWith('/case-bindings') && denial!=='source'){
        if(denial==='case')return response({},403);
        const mappings=cases();mappings.mappings[0].status='revoked';mappings.mappings[0].revoked_at=time;return response(mappings);
      }
    }));
    await readyImages(s);const api=s.recordRequests,index=requestIndex(s.snapshot());api.open(index);
    await api.refresh(index);await api.create(index,fields);assert.equal(s.snapshot().requestsView.retryCreate,true);
    deny=true;if(denial==='source')await s.loadSources(caseId);else await s.loadCases();deny=false;
    await s.loadCases();await s.loadSources(caseId);const next=requestIndex(s.snapshot());api.open(next);
    assert.equal(s.snapshot().requestsView.retryCreate,false);await api.retryCreate(next);assert.equal(posts,1);
  }
});

test('a case-scoped read still includes this patient’s historical receipts from other cases and withholds their sources',async()=>{
  const elsewhere={...received(),request_id:'RECORD-'+'B'.repeat(32),receipt_status:'source_superseded_reconciliation_required',
    source_reference:{...received().source_reference,case_id:'CASE-BETA'}};
  const {api,index,view,calls}=await setup(()=>response(list(row(),elsewhere)));
  api.open(index);await api.refresh(index);
  assert.equal(calls[0][0],scopedPath);assert.equal(view().rows.length,2);
  assert.equal(view().rows[1].receipt_status,'source_superseded_reconciliation_required');
  assert.equal(view().rows[1].source,null);
});

test('fresh source metadata removes an externally amended version from choices and reopens its historical receipt',async()=>{
  const replacement='SRC-'+'D'.repeat(32),openId='RECORD-'+'D'.repeat(32);
  let amended=false,sourceReads=0,posts=0;
  const s=new RegistrySession(transportForImages((url,init)=>{
    if(url===scopedPath){
      const linked=received();
      if(amended)linked.receipt_status='source_superseded_reconciliation_required';
      return response(list({...row(),request_id:openId},linked));
    }
    if(url===path+'/'+openId+'/receive'){posts++;return response({},409);}
    if(url.endsWith('/sources')){
      sourceReads++;const idx=sourceIndex();
      if(amended){
        idx.access_receipt_id='ACCESS-'+'9'.repeat(32);
        idx.sources[0].state='superseded';
        idx.sources.push({...idx.sources[0],source_id:replacement,version:2,state:'current',supersedes_id:sourceId,sha256:'2'.repeat(64)});
        idx.source_reported_assertions[0].source_id=replacement;
      }
      return response(idx);
    }
  }));
  await readyImages(s);const api=s.recordRequests,index=requestIndex(s.snapshot());
  api.open(index);await api.refresh(index);assert.equal(sourceReads,2);
  assert.equal(s.snapshot().requestsView.rows[1].source.state,'current');
  amended=true;await api.refresh(index);
  assert.equal(sourceReads,3);assert.equal(s.snapshot().requestsView.rows,null);
  assert.match(s.snapshot().recordMessage,/Source versions changed/);
  const now=requestIndex(s.snapshot());assert.notEqual(now,index);api.open(now);await api.refresh(now);
  assert.equal(s.snapshot().requestsView.rows[1].source.version,1);
  assert.equal(s.snapshot().requestsView.rows[1].source.state,'superseded');
  await api.receive(index,openId,sourceId);await api.receive(now,openId,sourceId);assert.equal(posts,0);
  await api.receive(now,openId,replacement);assert.equal(posts,1);
});

test('independent original or import denials withhold an uncertain create until fresh case, source and request reads allow exact recovery',async()=>{
  const raw=['OI-SYNTHETIC-REPORT/1','Patient: '+caseId,'Document: SAMPLE-ONE','Type: imaging','Event-Date: 2026-01-01',
    'Issued-At: 2026-01-02','Specimen: SAMPLE-SPEC','Finding: marker|not-reported|Fictional sample.',''].join('\n');
  const lab=readFileSync(new URL('../../../examples/synthetic/fictional-fhir-r4-lab-bundle.json',import.meta.url),'utf8');
  for(const action of ['original','text import','lab import','document original','document import']){
    const bodies=[],denied=[];
    const s=new RegistrySession(transportForImages((url,init)=>{
      if(url===scopedPath){
        if(init.method==='GET')return response(list());
        bodies.push(init.body);return bodies.length===1?response({},503):response({request_id:requestId,duplicate:true},200);
      }
      if(url.endsWith('/sources/'+sourceId) || init.method==='POST' || url.endsWith('/original')){
        denied.push(url);return new Response(null,{status:403});
      }
    }));
    await readyImages(s);const api=s.recordRequests,index=requestIndex(s.snapshot());api.open(index);
    await api.refresh(index);await api.create(index,fields);assert.equal(s.snapshot().requestsView.retryCreate,true);
    if(action==='original')await s.loadOriginal(sourceId);
    if(action==='text import')await s.importSource(caseId,raw,true);
    if(action==='lab import')await s.importLaboratory(caseId,lab,true);
    if(action==='document original')await s.documentRequest(caseId,'/'+sourceId+'/original');
    if(action==='document import')await s.documentRequest(caseId,'','{}');
    assert.equal(denied.length,1,action);assert.equal(requestIndex(s.snapshot()),null);
    assert.equal(s.snapshot().requestsView.retryFields,null);assert.equal(s.snapshot().requestsView.retryCreate,false);
    await s.loadCases();await s.loadSources(caseId);
    const next=requestIndex(s.snapshot());api.open(next);await api.retryCreate(next);
    assert.equal(bodies.length,1);assert.equal(s.snapshot().requestsView.retryFields,null);
    await api.refresh(next);assert.deepEqual(s.snapshot().requestsView.retryFields,fields);
    await api.retryCreate(next);assert.deepEqual(bodies,[bodies[0],bodies[0]]);
    assert.equal(s.snapshot().requestsView.retryCreate,false);
  }
});

test('an overdue source recheck cannot replace a newly selected case or expire a new credential',async()=>{
  for(const credentialChange of [false,true]){
    let delay=false;
    const started=deferred(),gate=deferred();
    const s=new RegistrySession(transportForImages((url)=>{
      if(url===scopedPath)return response(list(row()));
      if(delay&&url.endsWith('/'+caseId+'/sources')){started.resolve();return gate.promise;}
    }));
    await readyImages(s);const api=s.recordRequests,index=requestIndex(s.snapshot());api.open(index);
    delay=true;const checking=api.refresh(index);await started.promise;
    if(credentialChange)s.connect('another-authorized-credential'.repeat(2));else await s.loadSources('CASE-BETA');
    const older=sourceIndex();older.sources=[];
    gate.resolve(credentialChange?new Response(null,{status:401}):response(older));await checking;
    assert.equal(s.snapshot().connected,true);assert.equal(s.snapshot().requestsView.rows,null);
    assert.equal(requestIndex(s.snapshot())?.case_id,credentialChange?undefined:'CASE-BETA');
  }
});

test('question access denial preserves the exact create only when its case and source access survive independent rechecks',async()=>{
  for(const denied of ['question only','source','mapping','revoked case']){
    const writes=[];
    let checking=false;
    const s=new RegistrySession(transportForImages((url,init)=>{
      if(url===scopedPath){
        if(init.method==='GET')return response(list());
        writes.push(init.body);return writes.length===1?response({},503):response({request_id:requestId,duplicate:true},200);
      }
      if(checking){
        if(url.endsWith('/questions'))return response({},404);
        if(denied==='source' && url.endsWith('/sources'))return response({},404);
        if(denied==='mapping' && url.endsWith('/case-bindings'))return response({},403);
        if(denied==='revoked case' && url.endsWith('/case-bindings')){
          const mapped=cases();mapped.mappings[0].status='revoked';mapped.mappings[0].revoked_at=time;return response(mapped);
        }
      }
    }));
    await readyImages(s);const api=s.recordRequests,index=requestIndex(s.snapshot());
    api.open(index);await api.refresh(index);await api.create(index,fields);
    assert.equal(s.snapshot().requestsView.retryCreate,true);
    await s.loadWorldModel(caseId);checking=true;await s.loadSavedQuestions(caseId);checking=false;
    assert.equal(s.snapshot().questionListPhase,'error');
    assert.equal(s.snapshot().requestsView.retryFields,null);
    if(denied==='question only')assert.ok(requestIndex(s.snapshot()));
    else {assert.equal(requestIndex(s.snapshot()),null);await s.loadCases();await s.loadSources(caseId);}
    const next=requestIndex(s.snapshot());api.open(next);await api.retryCreate(next);
    assert.equal(writes.length,1);
    await api.refresh(next);
    const recoverable=denied==='question only';
    assert.equal(s.snapshot().requestsView.retryCreate,recoverable,denied);
    await api.retryCreate(next);
    assert.deepEqual(writes,recoverable?[writes[0],writes[0]]:[writes[0]]);
  }
});

test('create and receive reload the source owner after a confirmed write and retain its receipt notice if sources changed',async()=>{
  for(const action of ['create','receive']){
    const nextSource='SRC-'+'9'.repeat(32);
    let changed=false,indexReads=0;
    const s=new RegistrySession(transportForImages((url,init)=>{
      if(url===scopedPath && init.method==='GET'){
        const linked=received();linked.receipt_status='source_superseded_reconciliation_required';
        return response(list(changed && action==='receive'?linked:row()));
      }
      if(init.method==='POST' && (url===scopedPath || url===path+'/'+requestId+'/receive')){
        changed=true;
        return response(action==='create'?{request_id:requestId,duplicate:false}:{request_id:requestId,duplicate:false,source_id:sourceId,version:1},201);
      }
      if(url.endsWith('/sources')){
        indexReads++;
        const i=sourceIndex();
        if(changed){
          i.access_receipt_id='ACCESS-'+'9'.repeat(32);
          i.sources[0].state='superseded';
          i.sources.push({...i.sources[0],source_id:nextSource,version:2,state:'current',supersedes_id:sourceId,sha256:'2'.repeat(64)});
          i.source_reported_assertions[0].source_id=nextSource;
        }
        return response(i);
      }
    }));
    await readyImages(s);const api=s.recordRequests,index=requestIndex(s.snapshot());
    api.open(index);await api.refresh(index);assert.equal(indexReads,2);
    if(action==='create')await api.create(index,fields);else await api.receive(index,requestId,sourceId);
    assert.equal(indexReads,3,action+' needs a new source check');
    assert.equal(s.snapshot().requestsView.rows,null);
    assert.match(s.snapshot().recordMessage,action==='create'?/Local request saved/:/Source receipt confirmed/);
    assert.match(s.snapshot().recordMessage,/Source versions changed/);
    assert.equal(requestIndex(s.snapshot()).sources.find(s=>s.source_id===sourceId).state,'superseded');
  }
});
